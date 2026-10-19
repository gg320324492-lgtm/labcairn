"""The final evidence gate.

What the work order's acceptance actually tests: a fabricated DOI or source, a
wrong locator, missing evidence and conflicting numbers must all fail. This
module is where they fail.

What the gate answers
---------------------
Two questions, and they are not the same one:

* **May this report go out?** A gate that answers only per-record, and leaves
  the caller to decide, is a gate weakened into a suggestion -- a caller under
  pressure will cite the records that passed. The gate refuses as a whole.
* **Which records raised the objection?** Still answered, because a report that
  is refused must be able to say *which* part of it failed, and a reader told
  only "the evidence gate failed" learns nothing.

The gate refuses rather than degrades, which is the work order's phrase. It
refuses by naming everything that is wrong, not the first thing it found.

**The gate re-runs the checks; it does not read their verdicts.**
-------------------------------------------------------------
A stored verdict is a statement about the moment it was made. ADR-0004 I4 says
a record whose source has drifted is *invalidated* -- not quietly kept, with a
stale "pass" still in its log. So the gate re-runs each check the log records
and compares. A re-run that **disagrees with the log** is itself a finding,
reported as such: the record's recorded verification no longer holds, which is
a different fact from "the check failed today", and a report needs to know
which it is.

This is not duplication of C1-C3. The checks run at transition time and their
verdicts are the durable audit trail; the gate asks a different question, which
is whether that trail is still true.

**A conflict is surfaced, not resolved.**
-------------------------------------
ADR-0004 A5: two records whose C3 verdicts disagree beyond the declared
tolerance both become ``conflicted``, and *neither wins by recency*. The
conflict is displayed; it is not settled by taking the newer row. So the gate
names both records and prefers neither, and the records it loads are ordered by
creation time purely so that a caller rendering a list sees a stable order --
not a ranking, and :func:`~labcairn.evidence.store.load_task_records` says so
in its own docstring, because an ordering that looks like a preference is a
trap for whoever reads it next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sqlalchemy.engine import Connection

from labcairn.evidence.checks.c1 import check_source_exists
from labcairn.evidence.checks.c2 import quotation_match
from labcairn.evidence.checks.c3 import check_numeric_consistency
from labcairn.evidence.cite_support import SourceIndex, Verdict
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CheckKind, CheckOutcome, VerificationStatus
from labcairn.evidence.store import detect_conflicts, load_task_records

__all__ = ["Finding", "GateResult", "evaluate_task"]

#: The states a report may cite from. ``verified_by_rule`` is a rule's pass and
#: ``user_attested`` is a person's word; the other four are all "not yet" or
#: "not any more", and citing them would put an unexamined claim in front of a
#: reader as though it had been examined.
CITABLE_STATUSES: Final[frozenset[VerificationStatus]] = frozenset(
    {VerificationStatus.VERIFIED_BY_RULE, VerificationStatus.USER_ATTESTED}
)


@dataclass(frozen=True)
class Finding:
    """One reason a record may not be cited.

    ``kind`` is a stable machine-readable tag, so a renderer can group or
    filter without parsing ``reason``. ``reason`` is the sentence a person
    reads, and it is not optional: a finding nobody can read is a finding
    nobody acts on.
    """

    evidence_id: str
    kind: str
    reason: str


@dataclass(frozen=True)
class GateResult:
    """What the gate concluded, and what it objected to.

    ``passed`` is the gate's verdict on the whole set. ``findings`` is every
    objection, not the first one: a gate that reports the first failure and
    stops is a gate that hides the rest, and the rest is usually the part that
    matters. ``considered`` is every record the gate looked at, so a caller
    can say "three records, one of them failed" rather than only naming the
    failure.
    """

    passed: bool
    findings: tuple[Finding, ...]
    considered: tuple[str, ...] = ()

    @property
    def citable(self) -> tuple[str, ...]:
        """The ids that may be cited.

        Empty when the gate failed, because a report that may not go out may
        not cite anything either. This is the "cites nothing" half of ADR-0004
        A1, and it is why the property returns nothing rather than "the records
        that were fine": a partial list invites a caller to cite the ones that
        survived, which is the degradation the gate exists to prevent.
        """
        if not self.passed:
            return ()
        return self.considered


def evaluate_task(
    connection: Connection,
    *,
    task_id: str,
    index: SourceIndex,
) -> GateResult:
    """Every record a task holds, judged against the ledger and the source.

    The gate is the last thing that runs before a report says something, so it
    is the last place a fabricated source, an unlocated locator, an unverified
    claim or a contradicted number can be caught.
    """
    records = load_task_records(connection, task_id)
    findings: list[Finding] = []
    for record in records:
        findings.extend(_judge_status(record))
        findings.extend(_reverify(record, index))
    findings.extend(_conflicts(connection, records))
    return GateResult(
        passed=not findings,
        findings=tuple(findings),
        considered=tuple(record.evidence_id for record in records),
    )


def _judge_status(record: EvidenceRecord) -> list[Finding]:
    """A record in a state a report may not cite from."""
    if record.status in CITABLE_STATUSES:
        return []
    return [
        Finding(
            evidence_id=record.evidence_id,
            kind="status",
            reason=f"the record is {record.status.value!r}, which is not a state a "
            f"report may cite. A claim is citable once a rule has verified it or "
            f"a person has attested to it; this one is neither",
        )
    ]


def _reverify(record: EvidenceRecord, index: SourceIndex) -> list[Finding]:
    """Re-run the checks the log records, and compare.

    A disagreement is a finding in its own right: the record's recorded
    verification no longer holds, which is not the same as the check failing
    today. The source may have been edited since, which is ADR-0004 I4's drift
    and A2's condition.
    """
    findings: list[Finding] = []
    logged = _logged_outcomes(record)
    for check, logged_outcome in sorted(logged.items(), key=lambda item: item[0].value):
        verdict = _run(check, record, index)
        if verdict.outcome is logged_outcome:
            continue
        findings.append(
            Finding(
                evidence_id=record.evidence_id,
                kind="drift",
                reason=f"the record's log says {check.value} concluded "
                f"{logged_outcome.value!r}, but re-running it now concludes "
                f"{verdict.outcome.value!r}. The verification recorded against this "
                f"record no longer holds, and the source it was taken from has "
                f"most likely changed",
            )
        )
    return findings


def _logged_outcomes(record: EvidenceRecord) -> dict[CheckKind, CheckOutcome]:
    """The most recent verdict the log holds for each check."""
    outcomes: dict[CheckKind, CheckOutcome] = {}
    for entry in record.verification_log:
        outcomes[entry.check] = entry.outcome
    return outcomes


def _run(check: CheckKind, record: EvidenceRecord, index: SourceIndex) -> Verdict:
    if check is CheckKind.C1:
        return check_source_exists(record, index=index)
    if check is CheckKind.C2:
        return quotation_match(record, index=index).to_verdict()
    if check is CheckKind.C3:
        return check_numeric_consistency(record, index=index)
    return Verdict(
        check=check,
        outcome=CheckOutcome.NOT_CHECKED,
        checker_id="c4.not_implemented",
        detail="C4 is never checked in Phase 1.",
    )


def _conflicts(connection: Connection, records: tuple[EvidenceRecord, ...]) -> list[Finding]:
    """Records that contradict each other, with neither preferred.

    Each conflict is reported from both sides, because A5's rule is that
    neither wins: a report that named only one of them would be naming a
    winner.
    """
    findings: list[Finding] = []
    for record in records:
        for other_id in detect_conflicts(connection, record):
            findings.append(
                Finding(
                    evidence_id=record.evidence_id,
                    kind="conflict",
                    reason=describe_conflict(record, other_id),
                )
            )
    return findings


def describe_conflict(record: EvidenceRecord, other_id: str) -> str:
    """How a conflict is put to the reader.

    TODO(human): write the sentence a person reads when two records disagree
    about the same number.

    The facts available, and the ones that are not:

    - ``record`` is one side and ``other_id`` names the other. The other
      record's own value and unit are **not** passed in, because the gate has
      them and the renderer may not; if the sentence should name both numbers,
      the other record has to be looked up and this function's signature has to
      change to allow it.
    - The two records share a **primary anchor** -- the same cell or page --
      which is what makes them claims about the same thing. That anchor's
      address is on ``record`` and is the single most useful thing to name,
      because it is what a reader would go and look at.
    - ``record.value`` and ``record.unit`` are the record's own claim.

    The constraint ADR-0004 A5 puts on the answer: **neither wins by recency.**
    A sentence that implies the newer row is right -- by ordering them, by
    saying "instead of", by any other means -- is wrong however well it reads.
    Two records that disagree are both shown, and the disagreement is what is
    shown.

    Two shapes worth considering, and they are not equivalent:

    - One sentence naming both records, the shared address and the number,
      saying plainly that neither is preferred. Self-contained, and a renderer
      can print it as-is.
    - A structured result the renderer formats, so a report can lay the two
      numbers out side by side. More useful to a reader, and it moves the
      wording decision into LC-P1-11 -- which is where a report's presentation
      belongs, and where this project's other presentation decisions were
      deliberately put.

    Whatever you choose, the sentence must not read as though one of the two
    had been chosen over the other.
    """
    return f"the record conflicts with {other_id!r} about the same number, and neither is preferred"
