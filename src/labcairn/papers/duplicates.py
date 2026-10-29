"""Duplicates and missing rounds: what the archive reports rather than
resolves.

**What this module is.** LC-P2-08 T04: the two checks that are about **not
lying** about an archive.

**The duplicates.** The design's §7 names the cases: *"同名不同字节"* —
the same name with different bytes — and *"哈希一致不同名"* — the same
bytes under different names. They are the two halves of one question, and
they have **opposite answers**:

- **The same name, different bytes: two versions.** They are different
  documents, and the system cannot tell whether one is a copy of the other
  or whether they are two drafts that happen to share a name. So it
  **records both and reports the relationship as unresolved**. Deciding
  would be a decision by a name.
- **The same bytes, different names: one version.** The content hash
  decides this, and it is the one thing here that **is** decided by
  evidence rather than by a person — because identical bytes are identical
  documents, whatever they are called.

**The missing rounds.** A project whose versions are v1, v2 and v4 has a
**gap**. The system does not invent a v3 and does not renumber: **a missing
round is information the owner needs**, because a version may have been
lost, or it may never have existed. A renumbering would destroy the very
gap it was reporting.

**What this module refuses.** It does not merge, does not renumber, and
does not choose. Every one of those is a decision, and the design puts the
decision with a person.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DuplicateReport",
    "GapReport",
    "VersionSummary",
    "check_duplicates",
    "check_missing_rounds",
]


@dataclass(frozen=True)
class VersionSummary:
    """What the checks need to know about one version.

    **The content hash and the label, and nothing else.** The label is the
    author's file name, and it is here because the duplicate question is
    about names — but it decides nothing.
    """

    version_id: str
    #: The content hash of the file this version came from.
    content_sha256: str
    #: The label the author's file name gave. **Not evidence of order.**
    version_label_raw: str
    #: The round the version's label suggests, if it suggests one at all.
    #: ``None`` means the label carried no round.
    declared_round: int | None = None


@dataclass(frozen=True)
class DuplicateReport:
    """What the duplicate check found.

    **Two kinds, and they are reported separately** because they have
    different answers: a *name* collision is unresolved, and a *content*
    collision is resolved.
    """

    #: Versions that share a label but not their bytes. **Unresolved**: the
    #: system cannot tell a copy from two drafts that share a name.
    same_label_different_bytes: tuple[tuple[str, ...], ...] = ()
    #: Versions that share their bytes under different labels. **One
    #: version**, and the extra labels are duplicates of it.
    same_bytes_different_labels: tuple[tuple[str, ...], ...] = ()
    #: The labels that carry no round at all.
    unlabelled: tuple[str, ...] = ()

    @property
    def has_duplicates(self) -> bool:
        return bool(self.same_label_different_bytes or self.same_bytes_different_labels)


@dataclass(frozen=True)
class GapReport:
    """A gap in the sequence of rounds.

    **The gap is reported, and nothing is renumbered.** The rounds that
    exist are named, the rounds that are missing are named, and the
    versions keep the labels they came with.
    """

    #: The rounds that exist, in order.
    present: tuple[int, ...] = ()
    #: The rounds that are missing between the first and the last.
    missing: tuple[int, ...] = ()
    #: The versions whose declared round is in a gap. Empty when the label
    #: carried no round.
    unplaced: tuple[str, ...] = ()

    @property
    def has_gap(self) -> bool:
        return bool(self.missing)


def _round_from_label(label: str) -> int | None:
    """The round a label suggests, or ``None``.

    **This reads a label, and it decides nothing.** It answers one narrow
    question — *"does this name carry a round number?"* — so that a gap in
    the sequence can be **reported**. The order of the versions still comes
    from the edges, and a label that carries no round is a version whose
    round is unknown rather than a version in round zero.

    **And a label that suggests a round does not become one.** The design
    says the order is never taken from a file name; a name that carries a
    number is a *hint about what a person called the file*, and the hint is
    reported, never obeyed.
    """
    import re

    for match in re.finditer(r"(?<!\d)(\d{1,3})(?!\d)", label):
        number = int(match.group(1))
        if 0 < number < 1000:
            return number
    return None


def check_duplicates(versions: list[VersionSummary]) -> DuplicateReport:
    """Report the two kinds of duplicate.

    **The same label with different bytes is unresolved**, and the two
    versions are both reported. **The same bytes with different labels is
    one version**, and the labels are reported as duplicates of it.

    **What this refuses.** It does not choose which of two same-named
    files is the original, and it does not delete the second copy of a
    duplicated file. Both would be decisions, and the decisions belong to a
    person.
    """
    by_label: dict[str, list[VersionSummary]] = {}
    by_hash: dict[str, list[VersionSummary]] = {}
    unlabelled: list[str] = []

    for version in versions:
        by_label.setdefault(version.version_label_raw, []).append(version)
        by_hash.setdefault(version.content_sha256, []).append(version)
        if _round_from_label(version.version_label_raw) is None:
            unlabelled.append(version.version_id)

    same_label: list[tuple[str, ...]] = []
    for _label, group in sorted(by_label.items()):
        if len(group) < 2:
            continue
        hashes = {version.content_sha256 for version in group}
        if len(hashes) > 1:
            # The same name and different bytes: **two versions**, and the
            # relationship between them is unresolved.
            same_label.append(tuple(sorted(version.version_id for version in group)))

    same_bytes: list[tuple[str, ...]] = []
    for _hash, group in sorted(by_hash.items()):
        labels = {version.version_label_raw for version in group}
        if len(labels) > 1:
            # The same bytes under different names: **one version**, and the
            # other names are copies of it.
            same_bytes.append(tuple(sorted(version.version_id for version in group)))

    return DuplicateReport(
        same_label_different_bytes=tuple(same_label),
        same_bytes_different_labels=tuple(same_bytes),
        unlabelled=tuple(sorted(unlabelled)),
    )


def check_missing_rounds(versions: list[VersionSummary]) -> GapReport:
    """Report a gap in the sequence of rounds.

    **The gap is named, and nothing is renumbered.** A project whose
    versions are v1, v2 and v4 has a missing v3, and **a system that
    renumbered would destroy the very gap it was reporting** — and with it
    the information that a version may have been lost.
    """
    rounds: dict[int, list[str]] = {}
    unplaced: list[str] = []
    for version in versions:
        declared = _round_from_label(version.version_label_raw)
        if declared is None:
            unplaced.append(version.version_id)
            continue
        rounds.setdefault(declared, []).append(version.version_id)

    if not rounds:
        return GapReport(present=(), missing=(), unplaced=tuple(sorted(unplaced)))

    present = tuple(sorted(rounds))
    missing = tuple(number for number in range(present[0], present[-1] + 1) if number not in rounds)
    return GapReport(present=present, missing=missing, unplaced=tuple(sorted(unplaced)))
