"""The ledger's persistence, and the state machine that governs it.

ADR-0004 Contract 2 is a table of transitions with preconditions, and this
module is where the table becomes refusals. The instruction the breakdown gives
is the shape of the work: *"where a transition is illegal, refuse it — in the
schema where possible, in a validator otherwise, and in both cases with a
message naming the rule."*

Three things are enforced here, and the division between them is deliberate.

**In the schema** are the facts a CHECK can see: that a record past ``planned``
carries an anchor, a span, its hash and a source hash; that a C2 log entry has
a profile and a non-C2 one does not; that a C4 entry is never a pass. Those
constraints were built in revision 0005 and are not repeated here.

**In the model** are the facts a validator can see: that a status past
``planned`` has located evidence, that ``verified_by_rule`` needs a passing
entry from C1-C3, that ``user_attested`` needs a user creator, that a record
cannot be both endpoints. ``EvidenceRecord`` already refuses all of those.

**Here**, at the store boundary, are the two facts neither of the above can
reach. The first is the **rule catalog**: a ``verified_by_rule`` record needs a
passing entry whose ``checker_id`` names a rule this build implements, and the
model's validator accepts any non-empty ``checker_id`` because a *human*
attestation is logged by a human's id. The second is **which transitions exist
at all** — Contract 2's table is a list of pairs, and a pair not on it has to
be refused by something.

Why the store re-checks what the model already checks
------------------------------------------------------
A :class:`~labcairn.evidence.record.EvidenceRecord` is a Pydantic model, and
the model is what most callers will build. But the store is a *boundary*: a row
can be written by a SQL client, a migration, or a future contributor who never
imports the model. Re-checking at the boundary costs a few lines and is the
difference between a rule that holds and a rule that holds for the callers who
remembered it.

What this module does not decide
--------------------------------
**The shape of a conflict.** ADR-0004 says two records "of the same kind on the
same claim/numeric key" conflict, and never says what a key is. The schema
rules out one reading — ``uq_evidence_task_span`` is ``UNIQUE(task_id,
extracted_span_sha256)``, so two records cannot share a span hash within a
task — which leaves the anchor. :func:`detect_conflicts` uses the **primary**
anchor, position 0, because the schema's own comment says position 0 is the
primary address and a report that cites the wrong anchor first is citing
something real in the wrong role. Records that merely mention a common
background page are not in conflict.

**Whether a conflicted or unsupported record can come back.** Contract 2 lists
``any → conflicted`` and ``any → unsupported`` as catch-alls, and lists
``→ extracted`` only for ``planned`` and — by I1 — for the two endpoints. A
transition not on the table is refused here, so ``conflicted → extracted`` and
``unsupported → extracted`` are refused too. A record that has to be re-located
is expressed the way the schema provides for: a new record, with the old one
kept and ``superseded_by`` set.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Final

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.evidence.catalog import is_registered_rule
from labcairn.evidence.checks.c2 import quotation_match
from labcairn.evidence.cite_support import LocationResolution, SourceIndex, Verdict
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    NormalizationProfile,
    VerificationStatus,
)

__all__ = [
    "LedgerError",
    "UnknownRecordError",
    "advance",
    "append_record",
    "append_verification",
    "attest",
    "detect_conflicts",
    "load_record",
    "load_task_records",
]

#: ADR-0004 Contract 2's transition table, as data. A pair that is not here has
#: no transition, and :func:`advance` refuses it.
#:
#: I1 is why ``verified_by_rule`` and ``user_attested`` can each go back to
#: ``extracted``: a change of mind goes through the located state rather than
#: across the two endpoints.
ALLOWED_TRANSITIONS: Final[dict[VerificationStatus, frozenset[VerificationStatus]]] = {
    VerificationStatus.PLANNED: frozenset(
        {
            VerificationStatus.EXTRACTED,
            VerificationStatus.CONFLICTED,
            VerificationStatus.UNSUPPORTED,
        }
    ),
    VerificationStatus.EXTRACTED: frozenset(
        {
            VerificationStatus.VERIFIED_BY_RULE,
            VerificationStatus.USER_ATTESTED,
            VerificationStatus.CONFLICTED,
            VerificationStatus.UNSUPPORTED,
        }
    ),
    VerificationStatus.VERIFIED_BY_RULE: frozenset(
        {
            VerificationStatus.EXTRACTED,
            VerificationStatus.CONFLICTED,
            VerificationStatus.UNSUPPORTED,
        }
    ),
    VerificationStatus.USER_ATTESTED: frozenset(
        {
            VerificationStatus.EXTRACTED,
            VerificationStatus.CONFLICTED,
            VerificationStatus.UNSUPPORTED,
        }
    ),
    VerificationStatus.CONFLICTED: frozenset({VerificationStatus.UNSUPPORTED}),
    VerificationStatus.UNSUPPORTED: frozenset(),
}

#: The checks whose ``pass`` may move a record to ``verified_by_rule``.
UPGRADING_CHECKS: Final[frozenset[CheckKind]] = frozenset(
    {CheckKind.C1, CheckKind.C2, CheckKind.C3}
)


class LedgerError(RuntimeError):
    """A refusal by the ledger, with the rule named in the message."""


class UnknownRecordError(LedgerError):
    """No record with that id."""


def append_record(connection: Connection, record: EvidenceRecord) -> None:
    """Persist a record, its anchors, and its verification log.

    The record is written whole, or not at all. A ledger that holds half a
    record -- a row with its anchors but no log -- is worse than one that
    holds nothing, because the half is a record whose status claims more than
    its log supports, which is exactly what I3 forbids and exactly what a
    reader cannot see from the row alone.
    """
    _require_catalog_backed(record)
    connection.execute(
        sql_text(
            "INSERT INTO evidence_records (evidence_id, schema_version, task_id, kind, text,"
            " value, unit, tolerance, anchor_key, extracted_span, extracted_span_sha256,"
            " source_content_hash, status, created_by, created_by_id, created_at, superseded_by)"
            " VALUES (:eid,:ver,:tid,:kind,:text,:value,:unit,:tol,:akey,:span,:ssha,:shash,"
            ":status,:by,:byid,:now,:sup)"
        ),
        {
            "eid": record.evidence_id,
            "ver": record.schema_version,
            "tid": record.task_id,
            "kind": record.kind.value,
            "text": record.text,
            "value": record.value,
            "unit": record.unit,
            "tol": record.tolerance,
            "akey": render_anchor_key(record.anchor_ids),
            "span": record.extracted_span,
            "ssha": record.extracted_span_sha256,
            "shash": record.source_content_hash,
            "status": record.status.value,
            "by": record.created_by.value,
            "byid": record.created_by_id,
            "now": record.created_at,
            "sup": record.superseded_by,
        },
    )
    for position, anchor_id in enumerate(record.anchor_ids):
        connection.execute(
            sql_text(
                "INSERT INTO evidence_anchors (evidence_id, position, anchor_id)"
                " VALUES (:eid,:pos,:aid)"
            ),
            {"eid": record.evidence_id, "pos": position, "aid": anchor_id},
        )
    for entry in record.verification_log:
        _insert_verification(connection, record.evidence_id, entry)


def render_anchor_key(anchor_ids: tuple[str, ...]) -> str:
    """The canonical rendering of a record's anchors.

    The column exists because a CHECK cannot read a join table, and revision
    0005 fixes the empty rendering as ``"[]"``. This is the one place the
    rendering is produced, so the column and the join table cannot disagree.
    """
    return json.dumps(list(anchor_ids))


def load_record(connection: Connection, evidence_id: str) -> EvidenceRecord | None:
    """Read a record back, or ``None`` if there is no such id.

    The round trip is exact: what :func:`append_record` wrote is what
    :class:`~labcairn.evidence.record.EvidenceRecord` says. A store that could
    not read its own writes back would make every check above it untestable.
    """
    row = connection.execute(
        sql_text(
            "SELECT evidence_id, schema_version, task_id, kind, text, value, unit, tolerance,"
            " extracted_span, extracted_span_sha256, source_content_hash, status, created_by,"
            " created_by_id, created_at, superseded_by"
            "  FROM evidence_records WHERE evidence_id = :eid"
        ),
        {"eid": evidence_id},
    ).fetchone()
    if row is None:
        return None

    anchor_ids: list[str] = list(
        connection.execute(
            sql_text(
                "SELECT anchor_id FROM evidence_anchors WHERE evidence_id = :eid ORDER BY position"
            ),
            {"eid": evidence_id},
        ).scalars()
    )
    anchors = tuple(str(anchor_id) for anchor_id in anchor_ids)
    log = tuple(_read_verification(connection, evidence_id))

    return EvidenceRecord.model_validate(
        {
            "evidence_id": row[0],
            "schema_version": row[1],
            "task_id": row[2],
            "kind": row[3],
            "text": row[4],
            "value": row[5],
            "unit": row[6],
            "tolerance": row[7],
            "anchor_ids": anchors,
            "extracted_span": row[8],
            "extracted_span_sha256": row[9],
            "source_content_hash": row[10],
            "status": row[11],
            "verification_log": list(log),
            "created_by": row[12],
            "created_by_id": row[13],
            "created_at": row[14],
            "superseded_by": row[15],
        }
    )


def load_task_records(connection: Connection, task_id: str) -> tuple[EvidenceRecord, ...]:
    """Every record belonging to a task, in a stable order.

    Ordered by creation time and then by id, so a caller that renders a list of
    them sees the same order every time. The order is *not* a ranking: ADR-0004
    A5 says a conflict is not resolved by taking the newer row, and an ordering
    that looks like a preference is a trap for whoever reads it next.
    """
    ids: list[str] = list(
        connection.execute(
            sql_text(
                "SELECT evidence_id FROM evidence_records WHERE task_id = :tid"
                " ORDER BY created_at, evidence_id"
            ),
            {"tid": task_id},
        ).scalars()
    )
    records: list[EvidenceRecord] = []
    for evidence_id in ids:
        record = load_record(connection, str(evidence_id))
        if record is not None:
            records.append(record)
    return tuple(records)


def append_verification(
    connection: Connection, evidence_id: str, entry: VerificationRecord
) -> VerificationRecord:
    """Append one log entry, with the sequence number the ledger assigns.

    The sequence is dense from 1 and the ledger allocates it, not the caller: a
    caller-chosen ``seq`` would let two writers claim the same position, and
    ``uq_verification_records_seq`` would refuse the second as a constraint
    error rather than as a duplicate append.
    """
    return _insert_verification(connection, evidence_id, entry, allocate_seq=True)


def advance(
    connection: Connection,
    evidence_id: str,
    to_status: VerificationStatus,
    *,
    index: SourceIndex,
    checks: tuple[CheckKind, ...] = (),
    checked_at: dt.datetime,
) -> EvidenceRecord:
    """Move a record to *to_status*, enforcing ADR-0004 Contract 2.

    The named *checks* are run and their verdicts appended to the log before the
    preconditions are judged. That order matters: a transition to
    ``verified_by_rule`` needs a ``pass`` entry, and the entry is produced by
    running the check, not by asserting one.

    Nothing is written unless the whole move is legal. The checks' verdicts are
    appended first because they are evidence and stay true whether or not the
    transition itself turns out to be refused; the *status* is written last.
    """
    record = load_record(connection, evidence_id)
    if record is None:
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    _require_transition(record.status, to_status)

    for check in checks:
        verdict, profile = _run_check(check, record, index)
        append_verification(
            connection,
            evidence_id,
            VerificationRecord(
                check=verdict.check,
                checker_id=verdict.checker_id,
                outcome=verdict.outcome,
                detail=verdict.detail,
                checked_at=checked_at,
                normalization_profile=profile,
            ),
        )

    updated = load_record(connection, evidence_id)
    if updated is None:  # pragma: no cover - the row was read a moment ago
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    _require_precondition(connection, updated, to_status, index=index)

    connection.execute(
        sql_text("UPDATE evidence_records SET status = :status WHERE evidence_id = :eid"),
        {"status": to_status.value, "eid": evidence_id},
    )
    final = load_record(connection, evidence_id)
    if final is None:  # pragma: no cover
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    return final


def attest(
    connection: Connection,
    evidence_id: str,
    *,
    user_id: str,
    note: str,
    checked_at: dt.datetime,
) -> EvidenceRecord:
    """Move a record to ``user_attested`` on a person's word.

    The attestation is logged as a **C4** entry. C4 is the check whose only
    verdict is ``not_checked`` -- ADR-0004 I2 makes it the permanent terminal
    for interpretation -- so a C4 entry is exactly the statement "no machine
    checked this, and a person is standing behind it". The ``checker_id`` is
    the person's id, which is what keeps an attestation distinguishable from a
    rule's pass: only the latter names an id in the rule catalog.
    """
    record = load_record(connection, evidence_id)
    if record is None:
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    _require_transition(record.status, VerificationStatus.USER_ATTESTED)
    if not user_id.strip():
        raise LedgerError(
            "Contract 2: extracted -> user_attested requires a non-empty user "
            "identity. An attestation nobody signs is not an attestation."
        )
    if record.created_by.value != "user":
        raise LedgerError(
            f"Contract 2: extracted -> user_attested requires created_by='user', "
            f"and this record's creator is {record.created_by.value!r}. The record "
            f"model requires the same, and a record a rule wrote cannot become a "
            f"person's attestation without being rewritten -- which would erase "
            f"who actually wrote it."
        )

    append_verification(
        connection,
        evidence_id,
        VerificationRecord(
            check=CheckKind.C4,
            checker_id=user_id,
            outcome=CheckOutcome.NOT_CHECKED,
            detail=f"attested by {user_id!r}: {note}",
            checked_at=checked_at,
        ),
    )
    updated = load_record(connection, evidence_id)
    if updated is None:  # pragma: no cover
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    connection.execute(
        sql_text("UPDATE evidence_records SET status = :status WHERE evidence_id = :eid"),
        {"status": VerificationStatus.USER_ATTESTED.value, "eid": evidence_id},
    )
    final = load_record(connection, evidence_id)
    if final is None:  # pragma: no cover
        raise UnknownRecordError(f"no record with id {evidence_id!r}")
    return final


def detect_conflicts(connection: Connection, record: EvidenceRecord) -> tuple[str, ...]:
    """The other records that conflict with *record*, by ADR-0004 A5's rule.

    Same task, same kind, same **primary** anchor, and C3 verdicts that
    disagree. The primary anchor is position 0: the schema's own comment says it
    is the primary address, so two records that merely mention a common
    background page are not making claims about the same thing.

    "Disagree" means one verdict of ``pass`` and another of ``fail``. Two records
    about the same cell cannot both pass C3, and one of them failing is exactly
    the disagreement A5 exists to surface rather than resolve. An
    ``indeterminate`` against a ``fail`` is *not* a disagreement about the cell:
    it says one record had some other anchor it could not read, which is a
    different fact.
    """
    if not record.anchor_ids or record.kind.value != "numeric":
        return ()
    primary = record.anchor_ids[0]
    rows = connection.execute(
        sql_text(
            "SELECT r.evidence_id, r.kind FROM evidence_records AS r"
            "  JOIN evidence_anchors AS a ON a.evidence_id = r.evidence_id"
            " WHERE r.task_id = :tid AND r.kind = :kind AND a.anchor_id = :aid"
            "   AND a.position = 0 AND r.evidence_id <> :eid"
        ),
        {
            "tid": record.task_id,
            "kind": record.kind.value,
            "aid": primary,
            "eid": record.evidence_id,
        },
    ).fetchall()
    if not rows:
        return ()

    mine = _latest_c3_outcome(connection, record.evidence_id)
    if mine is None:
        return ()
    conflicting: list[str] = []
    for other_id, _kind in rows:
        theirs = _latest_c3_outcome(connection, str(other_id))
        if theirs is None or theirs == mine:
            continue
        # A disagreement means one record's number fits the cell and the other's
        # does not. ``indeterminate`` against ``fail`` is not that: it says one
        # record had some *other* anchor it could not read, which is a
        # different fact and not a conflict over the cell.
        if {mine, theirs} != {CheckOutcome.PASS, CheckOutcome.FAIL}:
            continue
        conflicting.append(str(other_id))
    return tuple(conflicting)


# --------------------------------------------------------------------------- #
# the rules
# --------------------------------------------------------------------------- #


def _require_transition(current: VerificationStatus, target: VerificationStatus) -> None:
    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise LedgerError(
            f"ADR-0004 Contract 2 does not allow {current.value!r} -> "
            f"{target.value!r}. Allowed from {current.value!r}: "
            f"{sorted(s.value for s in allowed) or 'nothing'}."
        )


def _require_precondition(
    connection: Connection,
    record: EvidenceRecord,
    target: VerificationStatus,
    *,
    index: SourceIndex,
) -> None:
    """Judge the target's preconditions against the record and its log."""
    if target is VerificationStatus.EXTRACTED:
        located = _resolving_anchors(record, index)
        if located == 0:
            raise LedgerError(
                "Contract 2: planned -> extracted requires at least one anchor_id "
                "resolving under C1, and none of this record's anchors resolves. "
                "A record that is located nowhere is not extracted."
            )
        return

    if target is VerificationStatus.VERIFIED_BY_RULE:
        passing = [
            entry
            for entry in record.verification_log
            if entry.check in UPGRADING_CHECKS and entry.outcome is CheckOutcome.PASS
        ]
        if not passing:
            raise LedgerError(
                "Contract 2: extracted -> verified_by_rule requires a "
                "VerificationRecord with check in {c1, c2, c3} and outcome 'pass'. "
                "This record's log has no such entry."
            )
        for entry in passing:
            if not is_registered_rule(entry.checker_id):
                raise LedgerError(
                    f"Contract 2: extracted -> verified_by_rule requires the "
                    f"passing entry to come from a checker_id in the registered rule "
                    f"catalog, and {entry.checker_id!r} is not one. A rule id this "
                    f"build does not implement cannot have verified anything."
                )
        return

    if target is VerificationStatus.UNSUPPORTED:
        if not record.anchor_ids:
            return
        failing = [
            entry
            for entry in record.verification_log
            if entry.check in UPGRADING_CHECKS and entry.outcome is CheckOutcome.FAIL
        ]
        if not failing:
            raise LedgerError(
                "Contract 2: extracted -> unsupported requires a C1, C2 or C3 "
                "failure, or a record with no anchor at all. This record cites "
                "anchors and its log has no failing entry."
            )
        return

    if target is VerificationStatus.CONFLICTED:
        if not detect_conflicts(connection, record):
            raise LedgerError(
                "Contract 2: -> conflicted requires at least two records of the "
                "same kind on the same claim/numeric key whose C3 verdicts "
                "disagree. This record has no such sibling."
            )
        return

    if target is VerificationStatus.USER_ATTESTED:  # pragma: no cover
        raise LedgerError(
            "user_attested is reached through attest(), which logs the "
            "attestation as part of the move."
        )


def _resolving_anchors(record: EvidenceRecord, index: SourceIndex) -> int:
    """How many of the record's anchors resolve to addressable material.

    Counted per anchor rather than asked of C1, because Contract 2 asks for
    *at least one* resolving anchor and C1's verdict is about all of them. A
    record citing three anchors where one has drifted is still partly located,
    and refusing to extract it would lose that.
    """
    resolved = 0
    for anchor_id in record.anchor_ids:
        anchor = index.load_anchor(anchor_id)
        if anchor is None:
            continue
        located = index.locate(anchor)
        if located is None:
            continue
        if located.resolution is LocationResolution.RESOLVED:
            resolved += 1
    return resolved


def _require_catalog_backed(record: EvidenceRecord) -> None:
    """A ``verified_by_rule`` record must be backed by a registered rule.

    The model's validator requires a passing C1-C3 entry but accepts any
    ``checker_id``, because a human attestation is logged by a human's id. The
    catalog check is the extra half, and it belongs at the store boundary: the
    model cannot know which ids this build implements.
    """
    if record.status is not VerificationStatus.VERIFIED_BY_RULE:
        return
    for entry in record.verification_log:
        if (
            entry.check in UPGRADING_CHECKS
            and entry.outcome is CheckOutcome.PASS
            and not is_registered_rule(entry.checker_id)
        ):
            raise LedgerError(
                f"Contract 2: a verified_by_rule record needs a passing entry "
                f"from a checker_id in the registered rule catalog, and "
                f"{entry.checker_id!r} is not one."
            )


def _run_check(
    check: CheckKind, record: EvidenceRecord, index: SourceIndex
) -> tuple[Verdict, NormalizationProfile | None]:
    """Run one check and return its verdict with the profile it used, if any."""
    if check is CheckKind.C1:
        from labcairn.evidence.checks.c1 import check_source_exists

        return check_source_exists(record, index=index), None
    if check is CheckKind.C2:
        match = quotation_match(record, index=index)
        return match.to_verdict(), match.profile
    if check is CheckKind.C3:
        from labcairn.evidence.checks.c3 import check_numeric_consistency

        return check_numeric_consistency(record, index=index), None
    raise LedgerError(f"{check.value} is not a check this store can run.")


# --------------------------------------------------------------------------- #
# the log
# --------------------------------------------------------------------------- #


def _insert_verification(
    connection: Connection,
    evidence_id: str,
    entry: VerificationRecord,
    *,
    allocate_seq: bool = False,
) -> VerificationRecord:
    if allocate_seq:
        next_seq = int(
            connection.execute(
                sql_text(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM verification_records"
                    " WHERE evidence_id = :eid"
                ),
                {"eid": evidence_id},
            ).scalar_one()
        )
    else:
        next_seq = _next_seq(connection, evidence_id)
    connection.execute(
        sql_text(
            "INSERT INTO verification_records (evidence_id, seq, schema_version, check_kind,"
            " checker_id, outcome, detail, checked_at, normalization_profile)"
            " VALUES (:eid,:seq,:ver,:kind,:cid,:outcome,:detail,:at,:profile)"
        ),
        {
            "eid": evidence_id,
            "seq": next_seq,
            "ver": entry.schema_version,
            "kind": entry.check.value,
            "cid": entry.checker_id,
            "outcome": entry.outcome.value,
            "detail": entry.detail,
            "at": entry.checked_at,
            "profile": (
                entry.normalization_profile.value
                if entry.normalization_profile is not None
                else None
            ),
        },
    )
    return entry


def _next_seq(connection: Connection, evidence_id: str) -> int:
    return int(
        connection.execute(
            sql_text(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM verification_records"
                " WHERE evidence_id = :eid"
            ),
            {"eid": evidence_id},
        ).scalar_one()
    )


def _read_verification(connection: Connection, evidence_id: str) -> list[VerificationRecord]:
    rows = connection.execute(
        sql_text(
            "SELECT check_kind, checker_id, outcome, detail, checked_at, normalization_profile"
            "  FROM verification_records WHERE evidence_id = :eid ORDER BY seq"
        ),
        {"eid": evidence_id},
    ).fetchall()
    entries: list[VerificationRecord] = []
    for kind, checker_id, outcome, detail, checked_at, profile in rows:
        entries.append(
            VerificationRecord.model_validate(
                {
                    "check": kind,
                    "checker_id": checker_id,
                    "outcome": outcome,
                    "detail": detail,
                    "checked_at": checked_at,
                    "normalization_profile": profile,
                }
            )
        )
    return entries


def _latest_c3_outcome(connection: Connection, evidence_id: str) -> CheckOutcome | None:
    """The most recent C3 verdict for a record, or ``None`` if it has none."""
    outcome = connection.execute(
        sql_text(
            "SELECT outcome FROM verification_records"
            " WHERE evidence_id = :eid AND check_kind = 'c3' ORDER BY seq DESC LIMIT 1"
        ),
        {"eid": evidence_id},
    ).scalar()
    if outcome is None:
        return None
    return CheckOutcome(outcome)
