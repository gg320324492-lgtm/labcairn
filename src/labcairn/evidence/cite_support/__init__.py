"""The four cite-support validators of ADR-0004 Contract 3 — and what Phase 1
can honestly answer.

What exists here
----------------
* The **types** every check returns and is given: :class:`Verdict`,
  :class:`NotCheckedVerdict`, :class:`LocatedContent`, :class:`LocationResolution`,
  :class:`SourceIndex`, :class:`NormalizationProfile`.
* **C4**, implemented, exactly as ADR-0004 specifies: a function with a body that
  always returns ``not_checked`` and must never be deleted.

What does not exist here, and why
---------------------------------
**C1, C2 and C3 raise :class:`CiteSupportNotImplementedError`.** They are declared
with ADR-0004's exact signatures so that the call sites, the signature and the
failure mode are all fixed now, but the behaviour is LC-P1-09's: deciding what
"verbatim" means needs a real index, and deciding that a number "agrees" needs
the parsed cell behind the anchor. Writing a plausible-looking implementation
here would mean writing one that never has an index to ask — and a check that
answers from a stub is worse than a check that refuses, because a caller cannot
tell the difference between "it passed" and "there was nothing to pass against".

Raising is the *safe* direction and is not the same as the ADR's "none may raise
past its boundary" rule, which governs the eventual implementations: it says a
finished check must return a verdict rather than leaking an exception to its
caller. A check with no implementation has nothing to leak.

:class:`~labcairn.evidence.states.IMPLEMENTED_CHECKS` says the same thing as
data — it is currently ``{C4}`` — so a report or a gate can ask "what can this
build actually establish?" and get the honest answer.

C4 is structurally unable to pass
---------------------------------
Three separate mechanisms, none of them a comment:

1. :class:`NotCheckedVerdict` declares ``outcome`` as
   ``Literal[CheckOutcome.NOT_CHECKED]`` and ``checker_id`` as
   ``Literal[C4_CHECKER_ID]``. Constructing one with ``pass`` raises
   :class:`~pydantic.ValidationError` — the value is unrepresentable, not merely
   discouraged.
2. :func:`check_scientific_interpretation` is annotated
   ``-> NotCheckedVerdict``. A reimplementation that returns a pass does not fail
   a test; it fails ``mypy``.
3. :class:`~labcairn.evidence.record.VerificationRecord` refuses to hold
   ``check=c4`` with any outcome but ``not_checked``, so even a hand-written
   log entry cannot turn a ``not_checked`` verdict into a C4 pass in the ledger.

And the reason it stays that way: **C4 cannot be implemented honestly.** ADR-0004
reaches this from three directions — PaperSpine already demotes interpretation
to a warning, ``docs/ARCHITECTURE.md`` forbids ``verified_by_rule`` from implying
a hypothesis is established, and no Phase 1 system has an evidence standard for
"is this inference warranted". Removing the function would leave every call site
unobliged to handle the case; the ADR's own phrasing is that it "is never absent
(so callers must handle it) and never green (so callers cannot be misled)".

No timestamp on a verdict
-------------------------
ADR-0004's four signatures take no clock, so a :class:`Verdict` carries none —
reading the wall clock inside a pure function would break
``docs/plans/LC-P1-01-task-breakdown.md`` §5.2's frozen-clock rule and make
replay non-deterministic. The audit timestamp belongs on the
:class:`~labcairn.evidence.record.VerificationRecord` the caller appends, which
does take an injected clock. That record is the durable audit row; a verdict is
the in-memory answer that produced it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, Protocol, Self, runtime_checkable

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import (
    IMPLEMENTED_CHECKS,
    CheckKind,
    CheckOutcome,
    NormalizationProfile,
)
from labcairn.sources.primitives import ContentHash, NonEmptyText, require_schema_version
from labcairn.sources.source import SourceAnchor

__all__ = [
    "C4_CHECKER_ID",
    "C4_DETAIL",
    "CITE_SUPPORT_SCHEMA_VERSION",
    "IMPLEMENTED_CHECKS",
    "CheckKind",
    "CheckOutcome",
    "CiteSupportNotImplementedError",
    "LocatedContent",
    "LocationResolution",
    "NormalizationProfile",
    "NotCheckedVerdict",
    "SourceIndex",
    "Verdict",
    "check_numeric_consistency",
    "check_quotation_support",
    "check_scientific_interpretation",
    "check_source_exists",
]

#: The verdict schema version this build reads.
CITE_SUPPORT_SCHEMA_VERSION: int = 1

#: The checker identity ADR-0004 fixes for C4, pinned on
#: :class:`NotCheckedVerdict` so a C4 verdict cannot claim a different checker.
#:
#: Annotated ``Final`` with **no** type so ``mypy`` infers a literal type: writing
#: ``Final[str]`` widens it, and a widened name is not usable where a literal is
#: wanted. It is still referenced from the model only through the after-validator,
#: because ``mypy`` rejects a *name* inside ``Literal[...]`` — only literal
#: expressions are legal parameters there. See :class:`NotCheckedVerdict`.
C4_CHECKER_ID: Final = "c4.not_implemented"

#: ADR-0004 Contract 3's C4 detail text, verbatim, and pinned on
#: :class:`NotCheckedVerdict` for the same reason. It is the sentence a user
#: reads in place of a scientific endorsement, so it cannot be reworded into
#: something a reader might mistake for a passed check.
C4_DETAIL: Final = (
    "Scientific interpretation is not machine-verifiable in Phase 1. "
    "Do not present this record as scientifically established."
)


def _verdict_version(value: int) -> int:
    return require_schema_version(value, expected=CITE_SUPPORT_SCHEMA_VERSION, schema="Verdict")


class Verdict(BaseModel):
    """What one check concluded about one record.

    ``outcome`` is a member of the closed
    :class:`~labcairn.evidence.states.CheckOutcome` enumeration, never a bool.
    ADR-0004 Contract 3: *"`indeterminate` and `not_checked` are never equal to
    `pass`."* As four members of one closed enum, ``outcome == PASS`` cannot be
    satisfied by a check that declined to answer — and ``outcome != FAIL``
    cannot be mistaken for one that confirmed.

    Frozen, so a verdict cannot be edited into a better result between the
    check and the log entry it produces.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_verdict_version)] = CITE_SUPPORT_SCHEMA_VERSION
    check: CheckKind
    outcome: CheckOutcome
    #: The registered rule id (or C4's fixed id). Never empty: a verdict that
    #: says "pass" without naming who passed it is not an audit record.
    checker_id: NonEmptyText
    #: The machine-readable reason. Rendered to the user, so it must say what
    #: happened rather than what the verdict symbol means.
    detail: NonEmptyText


class NotCheckedVerdict(Verdict):
    """The only kind of verdict C4 can produce.

    ``outcome`` is a ``Literal`` type rather than a plain field with a default,
    so Pydantic rejects ``NotCheckedVerdict(outcome=CheckOutcome.PASS)`` before
    any validator runs. The value is **unrepresentable**, not merely discouraged.

    ``checker_id`` and ``detail`` are pinned to ADR-0004's exact values by
    :meth:`_is_the_c4_verdict` rather than by ``Literal``, because ``mypy``
    rejects a name inside ``Literal[...]`` — only literal expressions are legal
    parameters there, and these two are constants that have to stay readable as
    prose. The guarantee is the same: construction with any other value raises,
    so no code path produces a C4 verdict that claims another checker or another
    explanation.

    This is the call-side half of ADR-0004 I2; the record-side half is
    :meth:`~labcairn.evidence.record.VerificationRecord._c4_is_never_anything_but_not_checked`.
    """

    outcome: Literal[CheckOutcome.NOT_CHECKED] = CheckOutcome.NOT_CHECKED
    checker_id: str = C4_CHECKER_ID
    detail: str = C4_DETAIL

    @model_validator(mode="after")
    def _is_the_c4_verdict(self) -> Self:
        """Pin all three fields. A C4 verdict is one fixed statement, not a family."""
        if self.outcome is not CheckOutcome.NOT_CHECKED:  # pragma: no cover - unreachable
            raise ValueError(
                "a NotCheckedVerdict may only carry outcome='not_checked'. Phase 1 "
                "cannot verify scientific interpretation; implementing C4 requires a "
                "superseding ADR with its own evidence standard."
            )
        if self.checker_id != C4_CHECKER_ID:
            raise ValueError(
                f"a NotCheckedVerdict may only carry checker_id={C4_CHECKER_ID!r}. "
                f"ADR-0004 fixes C4's checker identity so that a report cannot "
                f"attribute 'not checked' to something that might have checked."
            )
        if self.detail != C4_DETAIL:
            raise ValueError(
                "a NotCheckedVerdict may only carry the C4 detail text verbatim. "
                "This sentence is what a user reads in place of a scientific "
                "endorsement; rewriting it is how it stops meaning that."
            )
        return self


class LocationResolution(StrEnum):
    """How far resolving an anchor got.

    Three members, not two, because ADR-0004 A1 and A7 need "we could not look"
    to be distinguishable from "we looked and the address is not there". PaperSpine
    makes the same split (``no_hit`` vs ``provider_failure``) and the reasoning
    transfers: conflating them lets a failure discharge an evidence requirement.
    """

    #: The locator resolved against addressable material.
    RESOLVED = "resolved"
    #: The anchor is known but the address does not exist — page 99 of a 3-page
    #: PDF. C1 returns ``fail``. Nothing is cited in its place.
    UNRESOLVABLE = "unresolvable"
    #: The material is present but in a format LabCairn cannot address (a
    #: scanned PDF with no OCR). C1 returns ``indeterminate``.
    UNADDRESSABLE = "unaddressable"


class LocatedContent(BaseModel):
    """What an index reports about one anchor.

    The distinction between ``None`` and a :class:`LocatedContent` returned from
    :meth:`SourceIndex.locate` is load-bearing: ``None`` means *the anchor id is
    unknown to the ledger*, while a ``LocatedContent`` means the anchor exists and
    this is what is at it. Same reason as ADR-0004 A12 — a fabricated source id
    has to fail differently from a real one whose content changed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_id: NonEmptyText
    resolution: LocationResolution
    #: Verbatim text at the located span. ``None`` unless ``RESOLVED`` **and**
    #: the material carries text — a figure has an address and no text.
    text: str | None = None
    #: The numeric content at the located cell, for C3. ``None`` when the
    #: segment is not numeric; C3 returns ``indeterminate`` in that case rather
    #: than coercing the text.
    numeric_value: float | None = None
    #: The source's content hash as the index currently sees it. C1 compares it
    #: against the anchor's ``bound_source_sha256``; a mismatch is A2's hash drift.
    observed_content_sha256: ContentHash | None = None

    @model_validator(mode="after")
    def _nothing_is_claimed_without_a_resolution(self) -> Self:
        if self.resolution is not LocationResolution.RESOLVED:
            if self.text is not None or self.numeric_value is not None:
                raise ValueError(
                    f"resolution={self.resolution.value!r} carries no content. Text or a "
                    f"number alongside 'we could not read this' is a value from "
                    f"nowhere; C1 and C2 answer from the resolution, not from here."
                )
            return self
        if self.text is None and self.numeric_value is None:
            raise ValueError(
                "resolution='resolved' with neither text nor numeric_value. A "
                "resolved address that yielded nothing should be UNRESOLVABLE — "
                "'we found it and there is nothing there' is not a resolution."
            )
        return self


@runtime_checkable
class SourceIndex(Protocol):
    """The seam C1-C3 are handed. Implemented by LC-P1-09's FTS5 index.

    Three members, and the third exists because of a gap this Protocol had for
    months. ADR-0004 Contract 3 requires C1 to "fail if an anchor id is
    unknown", and an :class:`~labcairn.evidence.record.EvidenceRecord` carries
    ``anchor_ids`` as bare strings. ``locate`` and ``content_hash`` between them
    accept no id -- one wants a whole anchor, the other a source id -- so C1 had
    no path from what it was handed to the thing it must check. ADR-0004 does
    not fix this Protocol's members; the Protocol exists only in this module. So
    :meth:`load_anchor` is the seam the ADR's requirement was missing, not an
    amendment to the ADR.

    The two it already had are split because C1 has two jobs ADR-0004 states
    separately: *resolve every anchor_id against the ingested material* and
    *re-verify the recorded content hash*. Keeping them apart is what stops the
    hash check being folded into the lookup and forgotten.

    It is also what lets ``locate``'s ``None`` mean something. An unknown
    anchor id is detected by :meth:`load_anchor`, before there is an anchor to
    hand over, so "the ledger has never heard of this" cannot be confused with
    "the address was empty".

    A Protocol nobody implements yet is the point here, not a gap. ADR-0002's
    lesson about a faked capability probe returning "looks fine" is exactly why
    C1-C3 raise rather than accept an index and answer from it.
    """

    def load_anchor(self, anchor_id: str) -> SourceAnchor | None:
        """The anchor with this id, or ``None`` if the ledger has never heard of it.

        ``None`` is a real answer and not a zero: it is ADR-0004 A12's
        fabricated source, and it has to stay distinguishable from an anchor
        that resolved to the wrong place.
        """
        ...

    def locate(self, anchor: SourceAnchor) -> LocatedContent | None:
        """Resolve one anchor. ``None`` if the anchor id is unknown to the ledger."""
        ...

    def content_hash(self, source_id: str) -> ContentHash | None:
        """The source's current content hash. ``None`` if the source id is unknown."""
        ...


class CiteSupportNotImplementedError(NotImplementedError):
    """Raised by C1, C2 and C3 in Phase 1.

    Subclasses :class:`NotImplementedError` so a caller that genuinely wants to
    probe for the implementation can catch the standard type, and carries the
    :attr:`check` that was asked for so the message names which one.

    The choice to raise rather than return a placeholder verdict is the honest
    one. A check that returns ``indeterminate`` because it is unimplemented is
    indistinguishable, downstream and forever, from a check that declined to
    answer for a real reason — and the first would let a record sit at
    ``extracted`` looking, to a report, like a record a system had looked at.
    """

    def __init__(self, check: CheckKind) -> None:
        super().__init__(
            f"{check.value} is a declared cite-support contract with no Phase 1 "
            f"implementation. C1-C3 land with LC-P1-09's index; only "
            f"{sorted(c.value for c in IMPLEMENTED_CHECKS)} can answer today. "
            f"Callers must handle the unimplemented case rather than treat the "
            f"absence of a verdict as agreement."
        )
        self.check = check


# ---------------------------------------------------------------------------
# C1 — source existence
# ---------------------------------------------------------------------------
def check_source_exists(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Does the source exist, and does the locator resolve?

    ADR-0004 Contract 3:

        Resolve every anchor_id against the ingested material; re-verify the
        recorded content hash. Returns ``pass`` if all anchors resolve and hashes
        match, ``fail`` if an anchor id is unknown or the locator does not
        resolve, and ``indeterminate`` if the material is present but is a format
        LabCairn cannot address (e.g. a scanned PDF with no OCR).

    Phase 1: not implemented. See :class:`CiteSupportNotImplementedError`.

    Note what this must never do, per ADR-0004 A1: when an anchor does not
    resolve, the answer is ``fail`` and the report cites **nothing**. There is no
    nearest-page fallback, because :class:`~labcairn.sources.source.SourceAnchor`
    has no free-text label to trim.
    """
    raise CiteSupportNotImplementedError(CheckKind.C1)


# ---------------------------------------------------------------------------
# C2 — quotation match
# ---------------------------------------------------------------------------
def check_quotation_support(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Is the quoted text actually there, verbatim?

    ADR-0004 Contract 3:

        Match ``record.extracted_span`` against the text at each anchor's located
        span, under a declared normalization profile. ``pass`` = exact match
        after normalization. ``fail`` = the located span was resolved and does
        not contain it. ``indeterminate`` = resolved but normalization made the
        comparison unreliable. Never fuzzy-matches into a ``pass``.

    The **declared** profile is
    :attr:`~labcairn.evidence.record.VerificationRecord.normalization_profile` on
    the C2 log entry this run produces — a field this module does not take as an
    argument, because ADR-0004's signature fixes the two parameters and the
    auditable fact is what the check actually used. A run with no prior C2 entry
    declares nothing, and declaring nothing is ``indeterminate``, not ``pass``.

    Phase 1: not implemented.
    """
    raise CiteSupportNotImplementedError(CheckKind.C2)


# ---------------------------------------------------------------------------
# C3 — numerical consistency
# ---------------------------------------------------------------------------
def check_numeric_consistency(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Does the number agree with the anchored data?

    ADR-0004 Contract 3:

        Re-read the anchored cell/segment and compare to ``record.value`` under
        the declared unit and tolerance. ``fail`` on unit mismatch or on a
        difference exceeding tolerance. ``indeterminate`` when the segment is
        non-numeric or the declared tolerance is absent — an undeclared
        tolerance is never 0.

    That last clause is why :attr:`~labcairn.evidence.record.EvidenceRecord.tolerance`
    defaults to ``None`` rather than ``0.0``: a default of zero would be a
    default exact-match requirement, and "exactly equal" is a claim about a
    number nobody has compared yet.

    Phase 1: not implemented.
    """
    raise CiteSupportNotImplementedError(CheckKind.C3)


# ---------------------------------------------------------------------------
# C4 — scientific interpretation. NEVER CHECKED IN PHASE 1.
# ---------------------------------------------------------------------------
def check_scientific_interpretation(record: EvidenceRecord) -> NotCheckedVerdict:
    """Phase 1: this function has a body and always returns ``not_checked``.

    ADR-0004 Contract 3, verbatim:

        It exists so that every call site is forced to handle the
        unverified-interpretation case. It must never return pass, and must not
        be deleted — removing it would let callers silently stop handling C4.
        Extending it is a separate ADR with its own evidence standard.

    Why the answer is "no" rather than "not yet", in one paragraph: deciding
    whether an inference is warranted needs an evidence standard for scientific
    reasoning, and Phase 1 has none. The two precedents agree — PaperSpine makes
    interpretation a warning while making link-existence a hard finding, and
    ``docs/ARCHITECTURE.md`` forbids ``verified_by_rule`` from implying a
    hypothesis is established. A Phase 1 C4 that returned anything but
    ``not_checked`` would be a check whose verdict no one could audit.

    ``record`` is deliberately unused: the answer does not depend on what the
    record says, only on which Phase 1 this is. Keeping the parameter is the
    point — callers must pass the record they are about to render, which is what
    forces them to consider the record at all.

    Return type is :class:`NotCheckedVerdict`, not :class:`Verdict`, so a
    reimplementation that tried to return a pass would fail ``mypy`` before it
    reached a test. The absence of a clock parameter is likewise ADR's, and the
    audit timestamp belongs on the
    :class:`~labcairn.evidence.record.VerificationRecord` the caller appends.
    """
    return NotCheckedVerdict(check=CheckKind.C4)
