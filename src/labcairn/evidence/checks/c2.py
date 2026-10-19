"""C2 — is the quoted text actually there, verbatim?

ADR-0004 Contract 3, verbatim:

    Match ``record.extracted_span`` against the text at each anchor's located
    span, under a declared normalization profile. ``pass`` = exact match after
    normalization. ``fail`` = the located span was resolved and does not contain
    it. ``indeterminate`` = resolved but normalization made the comparison
    unreliable. Never fuzzy-matches into a ``pass``.

The trap this module is built around
------------------------------------
**Quotes are copied out of the store, so comparing a quote to the store verifies
fidelity to storage, not to the author's words.** A record whose
``extracted_span`` was read off page 2 will match page 2 forever. C2's real
value is *drift*: a source edited after the quote was taken, a locator that now
resolves somewhere else. That is why the tests here mutate the store after the
quote was taken rather than starting with a wrong quote, which cannot fail.

Two consequences follow, and both are tested:

* the comparison reads ``source_texts``, never ``evidence_fts``. The index holds
  a normalised copy; comparing a quote against it would be comparing the index
  with itself, a check that cannot fail.
* a match that only holds under a lossy profile is ``indeterminate``, never
  ``pass`` (ADR-0004 A4). ``indeterminate`` is not a softer pass; it routes the
  record to a person.

Why the ladder has four rungs
-----------------------------
Measured on this repository's own papers: of 21 (phrase, page) pairs a human
confirmed, 14 appear character-for-character in the stored text and 7 do not --
"Structured Disambiguation" is stored as "StructuredDisambiguationforText-to-SQL"
because these PDFs space words by positioning and the extractor synthesises the
space from glyph gaps (ADR-0008 constraint 3). Whether a given word pair comes
out with a space is a property of the extractor, not of the document.

Ignoring word boundaries recovers all 7 and admits nothing that is not there:
zero false positives across the corpus's four negative queries, zero for three
paraphrase probes. It is the fourth rung, and a match reached only there is
``indeterminate``.

The profile is a named member of the vocabulary rather than an undocumented step
inside this function because the audit row has to say how lenient the comparison
actually was. That is R2's whole objection.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final

from labcairn.evidence.cite_support import (
    LocationResolution,
    SourceIndex,
    Verdict,
)
from labcairn.evidence.normalize import normalize
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CheckKind, CheckOutcome, NormalizationProfile

__all__ = ["C2_CHECKER_ID", "QuotationMatch", "check_quotation_support", "quotation_match"]

C2_CHECKER_ID: Final = "c2.quotation_match"

#: Strictest first. The order is the contract: a match found at a lower rung
#: never gets to borrow the confidence of a stricter one.
LADDER: Final[tuple[NormalizationProfile, ...]] = (
    NormalizationProfile.EXACT,
    NormalizationProfile.NFKC_WHITESPACE_COLLAPSED,
    NormalizationProfile.NFKC_WHITESPACE_COLLAPSED_LIGATURES,
    NormalizationProfile.WORD_BOUNDARIES_REMOVED,
)


@dataclass(frozen=True)
class QuotationMatch:
    """C2's answer, and the profile that produced it.

    :class:`Verdict` cannot carry the profile -- ADR-0004's signature fixes its
    fields, and the profile is not a fact about the source, it is a fact about
    the comparison. A caller appending the audit row needs it, so this is the
    function the ledger layer should use; :func:`check_quotation_support` is the
    ADR-shaped wrapper over it.
    """

    outcome: CheckOutcome
    profile: NormalizationProfile
    detail: str

    def to_verdict(self) -> Verdict:
        return Verdict(
            check=CheckKind.C2,
            outcome=self.outcome,
            checker_id=C2_CHECKER_ID,
            detail=self.detail,
        )


def check_quotation_support(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Is the quoted text actually there, verbatim?

    ``pass`` only when the span appears character-for-character in a located
    span. ``fail`` when the spans resolved and none contains it, or when the
    record's own span and hash contradict each other. ``indeterminate`` when a
    match required a lossy profile, or when the material cannot be read.
    """
    return quotation_match(record, index=index).to_verdict()


def quotation_match(record: EvidenceRecord, *, index: SourceIndex) -> QuotationMatch:
    """The comparison itself, with the profile it ended up needing."""
    if record.extracted_span is None or record.extracted_span_sha256 is None:
        return QuotationMatch(
            outcome=CheckOutcome.INDETERMINATE,
            profile=NormalizationProfile.EXACT,
            detail="the record carries no quoted text, so C2 has nothing to "
            "compare. A claim with no quotation is not thereby unquoted by the "
            "source; it is unquoted by the record.",
        )

    if hashlib.sha256(record.extracted_span.encode()).hexdigest() != record.extracted_span_sha256:
        # The record contradicts itself before any source is consulted. This is
        # reported as a failure rather than an indeterminacy because there is a
        # definite fact here: the text and its hash do not agree, and any
        # downstream comparison would be comparing a quote to an unknown string.
        return QuotationMatch(
            outcome=CheckOutcome.FAIL,
            profile=NormalizationProfile.EXACT,
            detail=f"the record's extracted_span does not match its own "
            f"extracted_span_sha256 ({record.extracted_span_sha256}). C2 cannot "
            f"confirm a quotation against a record that disagrees with itself",
        )

    if not record.anchor_ids:
        return QuotationMatch(
            outcome=CheckOutcome.INDETERMINATE,
            profile=NormalizationProfile.EXACT,
            detail="the record cites no anchors, so there is no located span to "
            "compare the quotation against. Absence of evidence is not evidence "
            "of absence here: nothing was looked at.",
        )

    located: list[str] = []
    for anchor_id in record.anchor_ids:
        anchor = index.load_anchor(anchor_id)
        if anchor is None:
            return QuotationMatch(
                outcome=CheckOutcome.FAIL,
                profile=NormalizationProfile.EXACT,
                detail=f"anchor {anchor_id!r} is not registered, so C2 has no "
                f"address to read the quotation from",
            )
        content = index.locate(anchor)
        if content is None:
            return QuotationMatch(
                outcome=CheckOutcome.FAIL,
                profile=NormalizationProfile.EXACT,
                detail=f"anchor {anchor_id!r} is registered but yields no content",
            )
        if content.resolution is LocationResolution.UNRESOLVABLE:
            return QuotationMatch(
                outcome=CheckOutcome.FAIL,
                profile=NormalizationProfile.EXACT,
                detail=f"anchor {anchor_id!r} does not resolve, so the quotation "
                f"cannot be located. Nothing is compared in its place",
            )
        if content.resolution is LocationResolution.UNADDRESSABLE:
            return QuotationMatch(
                outcome=CheckOutcome.INDETERMINATE,
                profile=NormalizationProfile.EXACT,
                detail=f"anchor {anchor_id!r} points at material that cannot be "
                f"read, so no comparison was possible. The profile recorded here "
                f"is the strictest one; it names the attempt, not a comparison "
                f"that ran",
            )
        located.append(content.text or "")

    for profile in LADDER:
        quote = normalize(record.extracted_span, profile).text
        if _found(quote, located, profile):
            if profile is NormalizationProfile.EXACT:
                return QuotationMatch(
                    outcome=CheckOutcome.PASS,
                    profile=profile,
                    detail="the quoted span appears character-for-character in the located text",
                )
            return QuotationMatch(
                outcome=CheckOutcome.INDETERMINATE,
                profile=profile,
                detail=f"the quotation matches only after {profile.value} "
                f"normalisation. ADR-0004 A4: a match that required a lossy "
                f"comparison is not confirmation, and it does not promote the "
                f"record",
            )

    return QuotationMatch(
        outcome=CheckOutcome.FAIL,
        profile=LADDER[-1],
        detail=f"the quoted span does not appear in any located span, even under "
        f"the most lenient profile ({LADDER[-1].value}). The located text does "
        f"not contain it",
    )


def _found(quote: str, located: list[str], profile: NormalizationProfile) -> bool:
    """Is *quote* in any located span, or across spans in cited order?

    Both sides of the comparison are normalised. Normalising only the quote is
    the bug this function's shape is designed to make impossible: the located
    text arrives raw from ``source_texts``, so a "lossy" rung of the ladder would
    compare a normalised quote against unnormalised text and match nothing --
    every rung above the first would be unreachable, and the check would report
    the corpus's genuine line-break and boundary cases as failures while still
    passing the trivially exact ones. A test that only ever exercises the exact
    rung cannot see that.

    Concatenating the spans subsumes checking them one at a time, which the
    first draft of this function did not know: for any span s, s is a substring
    of the join, so a per-span test can never succeed where the join fails.
    Mutation-checking found the redundancy by deleting the per-span branch and
    watching nothing go red. What the join adds is the cross-span case -- a
    sentence running from the end of one page into the start of the next is one
    quotation and two stored rows.
    """
    # No guard for an empty quote: EvidenceRecord types extracted_span as
    # NonEmptyText, so an empty quotation is refused at construction and a
    # branch here would be unreachable defensive code.
    return quote in "".join(normalize(text, profile).text for text in located)
