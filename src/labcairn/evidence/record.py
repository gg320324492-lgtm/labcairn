"""``VerificationRecord`` and ``EvidenceRecord`` — the ledger row and its audit trail.

:class:`VerificationRecord`
    One entry in the append-only ``verification_log``. ADR-0004 Contract 1:
    *"``docs/ARCHITECTURE.md``'s 'Verification records include what was actually
    checked' is implemented by this table, not by the status column."*

:class:`EvidenceRecord`
    A claim, a number or a result, bound to anchors and a verification state.

Three structural decisions worth reading before the field lists
--------------------------------------------------------------
**1. The status cannot move without a log entry that says why (I3).**
``verified_by_rule``, ``user_attested``, ``conflicted`` and ``unsupported`` are
each rejected unless the record carries the audit rows ADR-0004's transition
table demands. "Status without a log entry is a schema violation" is not left to
a database check constraint that some future writer might forget — it raises at
construction, in every path, including a hand-written JSON file.

**2. The kind decides which fields mean anything.**
A ``numeric`` record may not carry ``text`` and must carry ``value`` *and*
``unit``; a ``claim`` or ``result`` record must carry ``text`` and may not carry
``value``, ``unit`` or ``tolerance``. This is the cross-type field-mixing
rejection — a claim string riding along on a number, or a unit silently attached
to a sentence, are both ways a report ends up saying something its record does
not support.

``unit`` is **declared, never inferred** (ADR-0004 Contract 1). A dimensionless
quantity says ``"dimensionless"``; it does not leave the field ``None``, because
``None`` is how "we did not record a unit" looks, and that is a different claim.

``tolerance`` is an addition to Contract 1's field list, and a necessary one:
C3's own docstring requires a *"declared tolerance"* and returns
``indeterminate`` when it is absent — *"an undeclared tolerance is never 0"*.
There is nowhere else for it to live. Its default is ``None``, never ``0.0``,
and a test locks that.

**3. C4 cannot be recorded as anything but ``not_checked`` (I2).**
:class:`VerificationRecord` refuses to exist with ``check=c4`` and any outcome
other than ``not_checked``. The corresponding guarantee on the *call side* —
that ``check_scientific_interpretation`` cannot return a pass — lives in
:mod:`labcairn.evidence.cite_support`, where a dedicated verdict type makes it
unrepresentable rather than merely discouraged.

What is **not** checked here
---------------------------
Two things, both named so their absence is a decision rather than a gap:

* **Cross-record conflicts.** ADR-0004's transition table makes ``conflicted``
  conditional on *two* records of the same numeric key whose C3 verdicts
  disagree. A single record cannot see its sibling, so this model checks only
  what is locally true (``conflicted`` carries an anchor and a non-empty log)
  and leaves the two-record test to the ledger at LC-P1-09.
* **Hash currency.** ADR-0004 I4 invalidates a record when ``source_content_hash``
  stops matching the source. That comparison needs the source bytes and is C1's
  job; this model records the hash it was written against and nothing more.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, model_validator

from labcairn.evidence.states import (
    CHECK_KINDS,
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    NormalizationProfile,
    VerificationStatus,
)
from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    StrictFloat,
    StrictNonNegFloat,
    require_schema_version,
)

#: The evidence schema version this build reads. Bumped only with a migration.
EVIDENCE_SCHEMA_VERSION: int = 1

#: The checks that can move a record out of ``extracted``. C4 is excluded by
#: construction: it is not in this set, and
#: :class:`VerificationRecord` will not let it report any other outcome, so no
#: sequence of log entries can make C4 an upgrade path.
UPGRADING_CHECKS: frozenset[CheckKind] = frozenset({CheckKind.C1, CheckKind.C2, CheckKind.C3})


def _record_version(value: int) -> int:
    return require_schema_version(value, expected=EVIDENCE_SCHEMA_VERSION, schema="EvidenceRecord")


def _verification_version(value: int) -> int:
    return require_schema_version(
        value, expected=EVIDENCE_SCHEMA_VERSION, schema="VerificationRecord"
    )


class VerificationRecord(BaseModel):
    """One immutable entry in an :attr:`EvidenceRecord.verification_log`.

    Append-only by construction: ``frozen=True``, and the only way to change an
    evidence record's history is to build a new record and point
    ``superseded_by`` at the new one. Rewriting a log entry would erase exactly
    the thing ADR-0004 I3 exists to protect — the evidence for why the status
    says what it says.

    ``normalization_profile`` is required exactly when ``check`` is C2, and
    forbidden otherwise. It records how lenient the comparison was, which is the
    fact ADR-0004 R2 is worried about: a matcher whose aggressiveness is
    invisible generates false negatives, and false negatives teach users to turn
    the check off.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_verification_version)] = EVIDENCE_SCHEMA_VERSION
    check: CheckKind
    #: The registered rule id, user id or model run id that produced this. Free
    #: text on purpose — the rule catalogue is LC-P1-09's; what matters here is
    #: that it is never empty, so "verified" always names its verifier.
    checker_id: NonEmptyText
    outcome: CheckOutcome
    detail: NonEmptyText
    checked_at: AwareDatetime
    normalization_profile: NormalizationProfile | None = None

    @model_validator(mode="after")
    def _c4_is_never_anything_but_not_checked(self) -> Self:
        """The I2 lock, at the record layer.

        ADR-0004 I2: *"There is no state meaning 'scientifically established.'
        ``not_checked`` from C4 is the permanent terminal for interpretation."*
        A log entry is the only place a verdict becomes durable, so this is the
        place a C4 pass would become real. It is rejected here rather than
        warned about: by the time the row exists, the log is append-only and
        the claim has been made.
        """
        if self.check is CheckKind.C4 and self.outcome is not CheckOutcome.NOT_CHECKED:
            raise ValueError(
                f"a C4 verification entry may only record outcome="
                f"{CheckOutcome.NOT_CHECKED.value!r}, not {self.outcome.value!r}. "
                f"ADR-0004 I2: scientific interpretation is not machine-verifiable in "
                f"Phase 1, and there is no seventh state that could hold a pass. "
                f"Implementing C4 requires a superseding ADR with its own evidence "
                f"standard."
            )
        return self

    @model_validator(mode="after")
    def _normalization_profile_belongs_to_c2_only(self) -> Self:
        is_c2 = self.check is CheckKind.C2
        if is_c2 and self.normalization_profile is None:
            raise ValueError(
                "a C2 entry must declare normalization_profile. 'How lenient was this "
                "comparison' is the question a reader of the log has to be able to "
                "answer, and an absent profile answers it as 'unknown', which is not "
                "the same as 'exact'."
            )
        if not is_c2 and self.normalization_profile is not None:
            raise ValueError(
                f"normalization_profile applies to C2 only; a {self.check.value!r} entry "
                f"does not compare text, so a profile on it is a claim about a "
                f"comparison that did not happen."
            )
        return self


class EvidenceRecord(BaseModel):
    """A claim, a number or a result, with its provenance and its audit trail.

    ``text`` is **required** and may be ``None``. That is deliberate: a numeric
    record must say ``"text": null`` out loud rather than omitting the key, so a
    claim string cannot end up riding along on a number unnoticed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_record_version)] = EVIDENCE_SCHEMA_VERSION
    evidence_id: NonEmptyText
    #: The owning Task, as an opaque id. Not a :class:`~labcairn.runtime.task.Task`:
    #: this ledger must be loadable without importing the runtime.
    task_id: NonEmptyText
    kind: EvidenceKind

    #: The statement as written, for ``CLAIM`` and ``RESULT``; ``None`` for ``NUMERIC``.
    text: NonEmptyText | None
    #: For ``NUMERIC`` only. The compared quantity, not a display string.
    value: StrictFloat | None = None
    #: For ``NUMERIC`` only. **Declared, never inferred.** A dimensionless
    #: quantity writes ``"dimensionless"`` rather than leaving this ``None``.
    unit: NonEmptyText | None = None
    #: For ``NUMERIC`` only. The declared comparison tolerance. Defaults to
    #: ``None``, never ``0.0`` — an undeclared tolerance is not an exact-match
    #: requirement, and C3 returns ``indeterminate`` when it is absent.
    tolerance: StrictNonNegFloat | None = None

    #: Ids of :class:`~labcairn.sources.source.SourceAnchor` rows. Ids, not
    #: embedded objects: the anchor is looked up so a source cannot be mutated
    #: by editing the record that cites it. Order is meaningful (primary anchor
    #: first); duplicates are not.
    anchor_ids: tuple[NonEmptyText, ...] = ()
    #: The literal text copied out of the source. Both this and the hash below
    #: are required together for any status past ``planned``.
    extracted_span: NonEmptyText | None = None
    extracted_span_sha256: ContentHash | None = None

    status: VerificationStatus
    #: Append-only. Never rewritten; see :class:`VerificationRecord`.
    verification_log: tuple[VerificationRecord, ...] = ()

    #: Who or what produced this record, and which one specifically. A final
    #: state that does not name its verifier is a claim without an author.
    created_by: EvidenceCreator
    created_by_id: NonEmptyText
    #: Hash of the source as read at extraction. Compared, never refreshed:
    #: ADR-0004 I4 invalidates on drift rather than silently re-reading.
    source_content_hash: ContentHash | None = None
    created_at: AwareDatetime
    #: Set when a newer record replaces this one; the old row is kept, not
    #: deleted, so the history of a claim is still auditable.
    superseded_by: NonEmptyText | None = None

    # -- helpers used by the invariants below ------------------------------

    def _entries_with(
        self, *, checks: frozenset[CheckKind], outcome: CheckOutcome
    ) -> tuple[VerificationRecord, ...]:
        return tuple(
            entry
            for entry in self.verification_log
            if entry.check in checks and entry.outcome is outcome
        )

    def _is_located(self) -> bool:
        """The ``planned → extracted`` preconditions, as one predicate.

        ADR-0004 Contract 2 requires ≥1 resolving anchor, a non-empty
        ``extracted_span`` and its hash, and a recorded ``source_content_hash``.
        (Resolution itself is C1's call; this checks only that the record
        carries the evidence a resolution would be made against.)
        """
        return (
            len(self.anchor_ids) > 0
            and self.extracted_span is not None
            and self.extracted_span_sha256 is not None
            and self.source_content_hash is not None
        )

    # -- invariants -------------------------------------------------------

    @model_validator(mode="after")
    def _kind_decides_which_fields_mean_anything(self) -> Self:
        """Cross-type field mixing is rejected, not tolerated."""
        if self.kind is EvidenceKind.NUMERIC:
            if self.text is not None:
                raise ValueError(
                    f"a {self.kind.value} record may not carry text. The value and its "
                    f"declared unit are the record; a sentence alongside them is a "
                    f"second, unchecked claim riding on a verified number."
                )
            if self.value is None:
                raise ValueError(
                    f"a {self.kind.value} record must carry a value. There is no "
                    f"quantity to reconcile against the anchored cell."
                )
            if self.unit is None:
                raise ValueError(
                    "a numeric record must declare its unit. The unit is declared, "
                    "never inferred (ADR-0004 Contract 1); a dimensionless quantity "
                    "writes 'dimensionless' rather than leaving this null."
                )
            return self

        if self.text is None:
            raise ValueError(
                f"a {self.kind.value} record must carry the text of the statement. "
                f"An evidence record with nothing stated attests to nothing."
            )
        for field_name, value in (
            ("value", self.value),
            ("unit", self.unit),
            ("tolerance", self.tolerance),
        ):
            if value is not None:
                raise ValueError(
                    f"a {self.kind.value} record may not carry {field_name!r}; that field "
                    f"belongs to kind={EvidenceKind.NUMERIC.value!r}. A number "
                    f"attached to a sentence is a second record that no check will "
                    f"ever look at."
                )
        return self

    @model_validator(mode="after")
    def _extraction_is_all_or_nothing(self) -> Self:
        if (self.extracted_span is None) != (self.extracted_span_sha256 is None):
            raise ValueError(
                "extracted_span and extracted_span_sha256 are both set or both "
                "omitted. Quoted text without its hash cannot be checked for drift; "
                "a hash without the text cannot be shown to anyone."
            )
        return self

    @model_validator(mode="after")
    def _anchors_are_unique(self) -> Self:
        if len(set(self.anchor_ids)) != len(self.anchor_ids):
            raise ValueError(
                f"anchor_ids contains duplicates: {list(self.anchor_ids)}. One address "
                f"cited twice is one anchor; two rows for it make 'how many sources "
                f"back this' answerable two ways."
            )
        return self

    @model_validator(mode="after")
    def _status_is_backed_by_what_the_record_carries(self) -> Self:
        """``planned`` is the only state that may exist without located evidence."""
        if self.status is VerificationStatus.PLANNED:
            return self

        if self.status is VerificationStatus.UNSUPPORTED:
            # ADR-0004 Contract 2 allows "C2 fail, or C1 fail, or C3 fail, **or no
            # anchor at all**". An unsupported record is therefore the one state
            # where a missing anchor is the evidence, so it needs either a
            # failing check entry or an empty anchor list to be explicable.
            failed = self._entries_with(checks=CHECK_KINDS, outcome=CheckOutcome.FAIL)
            if not failed and self.anchor_ids:
                raise ValueError(
                    "an unsupported record that cites anchors must say which check "
                    "failed. 'Unsupported' with a locatable anchor and no failing "
                    "entry is indistinguishable from 'not yet checked'."
                )
            return self

        if not self._is_located():
            raise ValueError(
                f"status={self.status.value!r} requires a located record: at least one "
                f"anchor id, a non-empty extracted_span, its sha256, and a recorded "
                f"source_content_hash (ADR-0004 Contract 2, planned -> extracted). "
                f"Missing: "
                f"{_unmet_extraction_preconditions(self)}"
            )
        return self

    @model_validator(mode="after")
    def _an_upgrade_requires_the_entry_that_earned_it(self) -> Self:
        """I3: a status may never be upgraded without appending a VerificationRecord."""
        if self.status is VerificationStatus.VERIFIED_BY_RULE:
            passing = self._entries_with(checks=UPGRADING_CHECKS, outcome=CheckOutcome.PASS)
            if not passing:
                raise ValueError(
                    "verified_by_rule requires a verification_log entry with check in "
                    "{c1, c2, c3} and outcome 'pass' (ADR-0004 Contract 2). Status "
                    "without a log entry is a schema violation (I3). Note what this "
                    "state means: a rule confirmed a number or a structure. It does "
                    "not mean the scientific interpretation holds — that is C4, which "
                    "is never checked in Phase 1."
                )
            return self

        if self.status is VerificationStatus.USER_ATTESTED:
            if self.created_by is not EvidenceCreator.USER:
                raise ValueError(
                    f"user_attested requires created_by="
                    f"{EvidenceCreator.USER.value!r}, not {self.created_by.value!r}. An "
                    f"attestation is something a person did; a rule or a model "
                    f"proposal reaching this state would misreport who stands behind "
                    f"the claim."
                )
            if not self.verification_log:
                raise ValueError(
                    "user_attested requires a verification_log entry. ADR-0004 "
                    "Contract 2 requires the attestation action itself to be logged, "
                    "and I3 requires a status to be backed by one."
                )
            return self

        if self.status is VerificationStatus.CONFLICTED and not self.verification_log:
            raise ValueError(
                "conflicted requires a verification_log entry. A conflict that no "
                "check reported is not a conflict; it is two records that happen to "
                "disagree, and that is a different thing to show a user."
            )
        return self


def _unmet_extraction_preconditions(record: EvidenceRecord) -> str:
    """Name the missing parts, so the error says what to fix rather than 'invalid'."""
    missing: list[str] = []
    if not record.anchor_ids:
        missing.append("anchor_ids")
    if record.extracted_span is None:
        missing.append("extracted_span")
    if record.extracted_span_sha256 is None:
        missing.append("extracted_span_sha256")
    if record.source_content_hash is None:
        missing.append("source_content_hash")
    return ", ".join(missing) if missing else "none"
