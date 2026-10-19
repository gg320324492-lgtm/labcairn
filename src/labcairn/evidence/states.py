"""The closed vocabularies of the evidence model, and one structural lock on C4.

Every enumeration here is **closed**. An unrecognised value is rejected, never
coerced, for the reason ADR-0003 §C1 gives for the event vocabulary: a coercion
rule turns a typo in a persisted row into a value that looks valid and reads
false. ``"verified_by_Rule"`` is not a verification state; it is a bug, and the
only safe behaviour is to refuse the payload.

Three of these enums carry the weight ADR-0004 puts on them:

:class:`VerificationStatus`
    Exactly six members. ADR-0004 I2: *"There is **no state meaning
    'scientifically established.'** The enumeration must not grow a seventh
    member in Phase 1."* :data:`VERIFICATION_STATES` freezes that list as data
    so the SQLite check constraint and the report layer read the same set the
    tests assert against — and so "did anyone add a seventh?" has one answer.

:class:`CheckOutcome`
    Four members, and the rule from ADR-0004 Contract 3 is the point of the
    type: **``indeterminate`` and ``not_checked`` are never equal to ``pass``**.
    They are distinct members of one closed enum precisely so that
    ``outcome == PASS`` cannot be satisfied by a check that did not run.

:class:`CheckKind`
    Exactly C1-C4. :data:`IMPLEMENTED_CHECKS` says which of them have an
    implementation; after LC-P1-09 T05-T07 all four do, and what still separates
    them is :data:`UPGRADING_CHECKS` — the subset whose ``pass`` may move a
    record out of ``extracted``. C4 has a body and can never return anything but
    ``not_checked``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

#: ADR-0004 Contract 2, I2. Do not add a member without a superseding ADR.
VERIFICATION_STATES: Final[frozenset[str]] = frozenset(
    {
        "planned",
        "extracted",
        "verified_by_rule",
        "user_attested",
        "conflicted",
        "unsupported",
    }
)


class VerificationStatus(StrEnum):
    """How far a record has been through the six-state machine.

    The three negative states are the ones the machine exists for. ADR-0004 A3
    ("a paraphrase presented as a quote does not reach ``verified_by_rule``")
    and A5 ("neither wins by recency; the conflict is displayed") are about what
    these states make *possible*, and a design with only ``planned`` and
    ``verified`` cannot express either.
    """

    #: Declared, not yet located. The only state that may carry no anchor.
    PLANNED = "planned"
    #: Located and copied out; the span and its hash are on the record.
    EXTRACTED = "extracted"
    #: A rule confirmed a **number or a structure**. It never confirms a
    #: scientific hypothesis — ``docs/ARCHITECTURE.md`: *"`verified_by_rule` can
    #: mean numeric/structural verification; it must not imply a scientific
    #: hypothesis is established."*
    VERIFIED_BY_RULE = "verified_by_rule"
    #: A named human said so, and the record says who.
    USER_ATTESTED = "user_attested"
    #: Two readings of the same quantity disagree beyond tolerance. A state to
    #: surface, not a terminal failure.
    CONFLICTED = "conflicted"
    #: Cannot be located, or does not support the record.
    UNSUPPORTED = "unsupported"


class EvidenceKind(StrEnum):
    """What sort of statement the record carries.

    The kind decides which fields are meaningful.
    :class:`~labcairn.evidence.record.EvidenceRecord` enforces that pairing in a
    validator, so a ``numeric`` record cannot carry a claim string and a ``claim``
    record cannot carry a value — see the cross-type test in
    ``tests/test_evidence_contracts.py``.
    """

    #: A statement about the world. Text, no value.
    CLAIM = "claim"
    #: A quantity. Value and unit, no text.
    NUMERIC = "numeric"
    #: An outcome of this project's own analysis. Text, no value.
    RESULT = "result"


class EvidenceCreator(StrEnum):
    """Who or what produced the record's *current* state.

    ADR-0002's rule, restated by ADR-0004 Contract 1: a record claiming a final
    state must also name **who or what established it**.
    :class:`~labcairn.evidence.record.EvidenceRecord` pairs this with
    ``created_by_id`` and refuses ``user_attested`` unless the creator is
    ``USER``.
    """

    #: A deterministic, registered check.
    RULE = "rule"
    #: A named human. Phase 1 is local single-user, but the name is still recorded.
    USER = "user"
    #: A model proposed it. **Proposing is not verifying** — a proposal reaches
    #: ``planned`` and no further without a log entry from C1-C3 or a user.
    MODEL_PROPOSAL = "model_proposal"


class CheckKind(StrEnum):
    """The four cite-support checks of ADR-0004 Contract 3.

    Kept distinct because **none can be inferred from another**: a locator that
    resolves proves nothing about the quote at it, and a quote that matches
    proves nothing about whether the inference from it is sound.
    """

    #: Source existence — does the cited source exist and does the locator resolve?
    C1 = "c1"
    #: Quotation match — does the quoted text appear, verbatim, at that locator?
    C2 = "c2"
    #: Numerical consistency — does the number agree with the anchored cell?
    C3 = "c3"
    #: Scientific interpretation — is the author's inference warranted?
    #: **Not implemented in Phase 1 and never returning anything but
    #: ``not_checked``.** See :mod:`labcairn.evidence.cite_support`.
    C4 = "c4"


class NormalizationProfile(StrEnum):
    """The declared text-normalisation profile a C2 quotation check runs under.

    Named and closed rather than a boolean "be lenient": ADR-0004 R2's concern
    is that a comparison whose aggressiveness is invisible produces false
    negatives, and a false negative train users to switch the check off. Naming
    the profile makes the choice auditable — the profile is recorded on the
    :class:`~labcairn.evidence.record.VerificationRecord` the check produced, so
    "how lenient was this pass?" is a question with an answer.

    The *transforms* are LC-P1-09's; this contract fixes the vocabulary so the
    answer is comparable across runs and across records.
    """

    #: Byte-for-byte after the extraction normalisation only. The strict default.
    EXACT = "exact"
    #: Unicode NFKC, then runs of whitespace collapsed to one space, ends
    #: trimmed. The usual choice for text extracted from a PDF, where the only
    #: differences are ones no reader would call a difference.
    NFKC_WHITESPACE_COLLAPSED = "nfkc_whitespace_collapsed"
    #: The above, plus ligature expansion (ﬁ → fi). For scanned-and-OCR'd or
    #: badly-encoded material, where letter *identity* may not be preserved.
    NFKC_WHITESPACE_COLLAPSED_LIGATURES = "nfkc_whitespace_collapsed_ligatures"
    #: NFKC, then **every** whitespace character removed. Added by LC-P1-09 T06
    #: because these PDFs space words by positioning and the extractor
    #: synthesises the space from glyph gaps: on one page "total correlation"
    #: keeps its space while "alignsfusedmodalitysubsetswith" has none of
    #: theirs. Measured on the fixture corpus, 7 of the 21 quotations a human
    #: confirmed on a page are not character-for-character present in the
    #: stored text, and boundary removal recovers all 7 with no false positive
    #: on the corpus's four negative queries.
    #:
    #: A match achieved only under this profile is ADR-0004 A4's ambiguous
    #: case: ``indeterminate``, never ``pass``. It is named here rather than
    #: hidden inside the check so the audit row can say how lenient the
    #: comparison actually was.
    WORD_BOUNDARIES_REMOVED = "word_boundaries_removed"


class CheckOutcome(StrEnum):
    """What a check concluded.

    Four members, and the two middle ones are the entire reason this is a type
    rather than a boolean. ADR-0004 R2: a strict-by-default quotation matcher
    "would train users to disable it", so C2 may decline to answer. ADR-0004 A4:
    ``indeterminate`` "must never be reported as pass". Making them separate
    members of a closed enum means no amount of downstream convenience
    (`outcome != FAIL`, `bool(outcome)`) turns "I don't know" into "yes".
    """

    #: The check ran and the claim held.
    PASS = "pass"
    #: The check ran and the claim did not hold.
    FAIL = "fail"
    #: The check ran and could not decide — normalisation ambiguity, an absent
    #: declared tolerance, a non-numeric segment. Routes to ``user_attested``,
    #: never to automatic failure and never to automatic pass.
    INDETERMINATE = "indeterminate"
    #: The check did not run at all. In Phase 1 this is C4's permanent answer.
    NOT_CHECKED = "not_checked"


#: The checks that have an implementation rather than a stub.
#:
#: All four do now: C1 landed with LC-P1-09 T05, C2 with T06 and C3 with T07.
#: C4's implementation is a body that always returns ``not_checked``, which is
#: still an implementation -- it answers, and the answer is that Phase 1 cannot
#: establish scientific interpretation.
#:
#: This set is now equal to :data:`CHECK_KINDS`, and that is worth saying out
#: loud, because a reader who expects it to be a subset will look for the check
#: that is missing. There is none. The distinction that matters is no longer
#: "implemented or not" but "may report pass": C4 structurally cannot, and
#: :data:`UPGRADING_CHECKS` is where that is enforced.
#:
#: ``CiteSupportNotImplementedError`` is currently raised by nothing. It is kept
#: because it is part of the exported contract surface callers were written
#: against, and deleting an exported symbol mid-work-order is a contract change
#: in its own right. A test asserts that no check raises it, so its
#: unreachability is a fact in the suite rather than a drift nobody noticed.
IMPLEMENTED_CHECKS: Final[frozenset[CheckKind]] = frozenset(CheckKind)

#: Every check the model knows about. Closed, per ADR-0004 I2.
CHECK_KINDS: Final[frozenset[CheckKind]] = frozenset(CheckKind)

#: Every outcome a verdict may carry. ``indeterminate`` and ``not_checked`` are
#: deliberately members: see the class docstring.
CHECK_OUTCOMES: Final[frozenset[CheckOutcome]] = frozenset(CheckOutcome)
