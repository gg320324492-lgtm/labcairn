"""C1 — source existence.

ADR-0004 Contract 3 states C1 as: *resolve every anchor_id against the
ingested material; re-verify the recorded content hash.* Two jobs, and the
second is not a detail of the first. A locator can resolve perfectly against
a file that has since been edited, and that is ADR-0004 A2's drift: the
address is right and the bytes are not.

The delegation pattern here is not decoration. ``check_source_exists`` is
importable from :mod:`labcairn.evidence.cite_support` because ADR-0004 fixes
the callable's home and its signature; this module is where the decision
lives. Importing this module from ``cite_support`` at module level would make
the package import itself before it had finished defining ``Verdict`` and
``SourceIndex``, which are exactly the types this module needs.

Four things C1 refuses
----------------------
**No nearest-page fallback.** ADR-0004 A1: an unresolvable locator is ``fail``
and the report cites nothing. Structurally there is nothing to fall back to --
:class:`~labcairn.sources.source.SourceAnchor` has no free-text label to trim.
A check that substituted page 3 for page 99 would produce a *real* address for
a *wrong* claim, in the shape of a citation.

**No vacuous pass.** A record citing no anchors has nothing confirmed and
nothing contradicted. Returning ``pass`` for it is the most dangerous answer
available here, because it is the one that lets ``verified_by_rule`` be
reached with no evidence behind it while wearing the appearance of a check
having run. ``indeterminate`` routes the record to a person instead.

**No refresh.** A hash is compared, never updated. ADR-0004 I4 invalidates a
record whose source hash stops matching. An implementation that read the
record's hash and then wrote the current one back could report drift exactly
never.

**No hiding a hard fact behind a soft one.** Every anchor is examined before
the verdict is made. A record with one unreadable anchor and one drifted
anchor is ``fail``, not ``indeterminate`` -- the drift is a fact, and
"we could not tell" would bury it.
"""

from __future__ import annotations

from typing import Final

from labcairn.evidence.cite_support import (
    LocationResolution,
    SourceIndex,
    Verdict,
)
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CheckKind, CheckOutcome
from labcairn.sources.locators import describe_locator
from labcairn.sources.source import SourceAnchor

__all__ = ["C1_CHECKER_ID", "check_source_exists"]

#: The registered rule id. Pinned as a constant so an audit row names which
#: implementation ran, the same way ``C4_CHECKER_ID`` is pinned for C4.
C1_CHECKER_ID: Final = "c1.source_exists"

#: One anchor's answer: what happened, and the sentence that says why.
_Answer = tuple[CheckOutcome, str]


def check_source_exists(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Run C1 over every anchor a record cites.

    ``pass`` only when every anchor resolves against addressable material and
    no recorded hash disagrees with the source as it now stands. ``fail`` for
    an unknown anchor id, an unresolvable locator, a source the ledger has no
    row for, or any hash mismatch. ``indeterminate`` when the material is
    present but cannot be read, or when the record cites nothing.
    """
    if not record.anchor_ids:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            "the record cites no anchors, so there is nothing C1 could confirm "
            "or deny. A record that cites nothing is not thereby supported.",
        )

    answers = [_resolve_one(record, anchor_id, index) for anchor_id in record.anchor_ids]

    failures = [detail for outcome, detail in answers if outcome is CheckOutcome.FAIL]
    if failures:
        return _verdict(
            CheckOutcome.FAIL,
            f"{len(failures)} of {len(record.anchor_ids)} cited anchor(s) do not "
            f"hold: {'; '.join(failures)}",
        )

    unclear = [detail for outcome, detail in answers if outcome is CheckOutcome.INDETERMINATE]
    if unclear:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            f"every cited anchor was located, but {len(unclear)} of them cannot "
            f"be read: {'; '.join(unclear)}",
        )

    return _verdict(
        CheckOutcome.PASS,
        f"all {len(record.anchor_ids)} anchor(s) resolved and every recorded "
        f"content hash still matches the source",
    )


def _resolve_one(record: EvidenceRecord, anchor_id: str, index: SourceIndex) -> _Answer:
    """C1's whole decision for one anchor id."""
    anchor = index.load_anchor(anchor_id)
    if anchor is None:
        # A12. The ledger has never heard of this anchor. Inventing an address
        # to check would make a fabricated source indistinguishable from a real
        # one whose locator broke.
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} is not registered: no anchor with that id "
            f"exists, so the record cites an address that was never made",
        )

    located = index.locate(anchor)
    if located is None:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} is registered but the index cannot resolve it "
            f"at all. A registered anchor with no resolution is a ledger defect, "
            f"not an absent source, and is reported rather than passed over",
        )

    if located.resolution is LocationResolution.UNRESOLVABLE:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} points at {describe_locator(anchor.locator)}, "
            f"which is not in the ingested material. Nothing is cited in its "
            f"place: not the nearest page, not the last page",
        )

    if located.resolution is LocationResolution.UNADDRESSABLE:
        # A7. The material is present and LabCairn cannot read it. Not `fail`:
        # the claim may be true of a document nobody has been able to open.
        return (
            CheckOutcome.INDETERMINATE,
            f"anchor {anchor_id!r} points at {describe_locator(anchor.locator)}, "
            f"whose source carries no text LabCairn can address",
        )

    return _compare_hashes(record, anchor, anchor_id, index)


def _compare_hashes(
    record: EvidenceRecord, anchor: SourceAnchor, anchor_id: str, index: SourceIndex
) -> _Answer:
    """A2 and I4, in the order the contract states them.

    Three hashes are in play and they are not the same thing. ``current`` is
    what the source is now; ``anchor.bound_source_sha256`` is what the anchor
    was made against; ``record.source_content_hash`` is what the record was
    extracted from. The first is a fact and the other two are claims about it.
    Neither claim is refreshed, because refreshing is what makes drift
    unreportable.

    The anchor's hash is checked before the record's because they are
    different failures. An anchor bound to bytes that no longer exist means the
    citation is stale; a record whose own hash disagrees with the source means
    the copy out of it is. A report that said only "a hash does not match"
    would not tell a reader which one to fix.
    """
    current = index.content_hash(anchor.source_id)
    if current is None:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} names source {anchor.source_id!r}, which is "
            f"not in the ledger -- there are no bytes this citation rests on",
        )

    if current != anchor.bound_source_sha256:
        return (
            CheckOutcome.FAIL,
            f"the source behind anchor {anchor_id!r} changed after the anchor was "
            f"made (bound to {anchor.bound_source_sha256}, now {current}). The "
            f"address still resolves, but not at the bytes the record was written "
            f"against; it is invalidated, not refreshed",
        )

    if record.source_content_hash is None:
        # Nothing was recorded, so nothing could be re-verified. This is not a
        # failure -- the anchor is fine -- but it is also not a pass, because
        # ``pass`` asserts "the hashes match" and there is no hash to match.
        # Contract 2 requires the hash for any status past ``planned``, so a
        # record that reaches this branch is one that has not yet been located,
        # and C1's answer tells it so rather than waving it through.
        return (
            CheckOutcome.INDETERMINATE,
            f"anchor {anchor_id!r} resolves, but the record stores no "
            f"source_content_hash, so C1 had nothing to re-verify. A citation "
            f"cannot be confirmed against bytes that were never written down",
        )

    if record.source_content_hash != current:
        return (
            CheckOutcome.FAIL,
            f"the record was extracted from content hashing to "
            f"{record.source_content_hash}, but its source now hashes to "
            f"{current}. Record and source disagree about what was read",
        )

    return (CheckOutcome.PASS, "")


def _verdict(outcome: CheckOutcome, detail: str) -> Verdict:
    return Verdict(
        check=CheckKind.C1,
        outcome=outcome,
        checker_id=C1_CHECKER_ID,
        detail=detail,
    )
