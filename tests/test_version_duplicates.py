"""The duplicate and missing-round checks, and what they refuse to decide.

**What is under test.** LC-P2-08 T04: the two checks that are about **not
lying** about an archive.

**The two halves of one question, with opposite answers.**

- **The same name, different bytes: two versions.** The system cannot tell
  a copy from two drafts that happen to share a name, so it records both
  and reports the relationship as **unresolved**.
- **The same bytes, different names: one version.** Identical bytes are
  identical documents, whatever they are called — and this is the one
  thing here that **is** decided by evidence rather than by a person.

**The missing round.** A project with v1, v2 and v4 has a gap. The system
**reports it and renumbers nothing**, because a renumbering would destroy
the very gap it was reporting — and with it the information that a version
may have been lost.

**What these checks refuse.** They do not merge, do not renumber, and do
not choose. Every one of those is a decision, and the design puts the
decision with a person.
"""

from __future__ import annotations

from labcairn.papers.duplicates import (
    VersionSummary,
    check_duplicates,
    check_missing_rounds,
)


def _version(
    version_id: str,
    label: str,
    digest: str,
) -> VersionSummary:
    return VersionSummary(version_id=version_id, content_sha256=digest, version_label_raw=label)


# --------------------------------------------------------------------------- #
# the duplicates
# --------------------------------------------------------------------------- #


def test_the_same_name_with_different_bytes_is_two_versions() -> None:
    """**The design's case: 同名不同字节.**

    Two files called ``draft.docx`` with different content are two
    versions, and the system **cannot tell** a copy from two drafts that
    happen to share a name.

    **What breaks it:** merging them because the name matches, or keeping
    only one. Either would lose a document from the archive, and the
    archive's job is to hold what it was given.
    """
    versions = [
        _version("v1", "draft.docx", "a" * 64),
        _version("v2", "draft.docx", "b" * 64),
    ]

    report = check_duplicates(versions)

    assert report.same_label_different_bytes == (("v1", "v2"),)
    assert report.has_duplicates is True


def test_the_same_bytes_with_different_names_is_one_version() -> None:
    """**The design's other case: 哈希一致不同名.**

    Two names, one set of bytes: the same document saved twice. **The
    content hash decides this**, and it is the one thing here that is
    decided by evidence rather than by a person — because identical bytes
    are identical documents whatever they are called.

    **What breaks it:** treating the different names as different
    versions, which would put the same document in the archive twice.
    """
    versions = [
        _version("v1", "draft.docx", "a" * 64),
        _version("v2", "final.docx", "a" * 64),
    ]

    report = check_duplicates(versions)

    assert report.same_bytes_different_labels == (("v1", "v2"),)
    # And it is **not** reported as a name collision, because the bytes
    # agree: there is no unresolved question here.
    assert report.same_label_different_bytes == ()


def test_a_clean_archive_reports_no_duplicates() -> None:
    """Three versions with three names and three sets of bytes: nothing to
    report.

    **What breaks it:** a check that reports everything, which would make
    the report noise and the reader stop reading it.
    """
    versions = [
        _version("v1", "draft.docx", "a" * 64),
        _version("v2", "revised.docx", "b" * 64),
        _version("v3", "submitted.docx", "c" * 64),
    ]

    report = check_duplicates(versions)

    assert report.has_duplicates is False
    assert report.same_label_different_bytes == ()
    assert report.same_bytes_different_labels == ()


def test_a_label_with_no_round_is_reported_as_unlabelled() -> None:
    """A name that carries no round is a version whose round is unknown.

    **It is not a version in round zero.** A name with no number says
    nothing about where the version sits, and giving it a number would put
    it in a place the archive has no evidence for.
    """
    versions = [
        _version("v1", "draft.docx", "a" * 64),
        _version("v2", "revision.docx", "b" * 64),
    ]

    report = check_duplicates(versions)

    assert set(report.unlabelled) == {"v1", "v2"}


# --------------------------------------------------------------------------- #
# the missing rounds
# --------------------------------------------------------------------------- #


def test_a_missing_round_is_reported() -> None:
    """v1, v2 and v4 has a missing v3, and the report says so.

    **What breaks it:** renumbering, or reporting the rounds as 1, 2, 3. A
    renumbering would **destroy the very gap it was reporting**, and with
    it the information that a version may have been lost.
    """
    versions = [
        _version("v1", "v1.docx", "a" * 64),
        _version("v2", "v2.docx", "b" * 64),
        _version("v4", "v4.docx", "d" * 64),
    ]

    report = check_missing_rounds(versions)

    assert report.has_gap is True
    assert report.present == (1, 2, 4)
    assert report.missing == (3,)


def test_a_contiguous_sequence_reports_no_gap() -> None:
    """v1, v2, v3 has no gap.

    **What breaks it:** a check that always reports a gap, which would
    make the report noise and the reader stop reading it.
    """
    versions = [
        _version("v1", "v1.docx", "a" * 64),
        _version("v2", "v2.docx", "b" * 64),
        _version("v3", "v3.docx", "c" * 64),
    ]

    report = check_missing_rounds(versions)

    assert report.has_gap is False
    assert report.missing == ()


def test_a_gap_at_the_start_is_not_reported_as_a_gap() -> None:
    """The report names the rounds between the first and the last.

    **What breaks it:** reporting every round below the first as missing.
    An archive that starts at v2 has no evidence that a v1 existed, and
    claiming one is missing would be the same invention the whole check
    exists to avoid.
    """
    versions = [
        _version("v2", "v2.docx", "b" * 64),
        _version("v3", "v3.docx", "c" * 64),
    ]

    report = check_missing_rounds(versions)

    assert report.has_gap is False
    assert report.present == (2, 3)
    assert report.missing == ()


def test_a_version_whose_label_carries_no_round_is_unplaced_not_missing() -> None:
    """A version with no round in its name is **unplaced**, not missing.

    **The difference matters.** A *missing* round says "something was here
    and is not now"; an *unplaced* version says "this one does not say
    where it goes". They are different facts and the report keeps them
    apart.
    """
    versions = [
        _version("v1", "v1.docx", "a" * 64),
        _version("v2", "v2.docx", "b" * 64),
        _version("unknown", "final copy.docx", "c" * 64),
    ]

    report = check_missing_rounds(versions)

    assert report.missing == ()
    assert report.unplaced == ("unknown",)


def test_the_duplicate_and_gap_checks_are_independent() -> None:
    """The two checks answer two different questions.

    **What breaks it:** merging them into one "problems" list. The same
    name with different bytes is an **unresolved relationship**, and a
    missing round is a **gap in the sequence** — and a reader who saw
    them as one thing would not know which one they were looking at.
    """
    versions = [
        _version("v1", "v1.docx", "a" * 64),
        _version("v2", "v2.docx", "b" * 64),
        _version("v4", "v4.docx", "d" * 64),
        _version("v2-again", "v2.docx", "e" * 64),
    ]

    duplicates = check_duplicates(versions)
    rounds = check_missing_rounds(versions)

    assert duplicates.same_label_different_bytes == (("v2", "v2-again"),)
    assert rounds.missing == (3,)
    # And the name collision does not become a round gap, because the
    # rounds come from the numbers the labels carry.
    assert rounds.present == (1, 2, 4)


def test_an_empty_archive_is_handled() -> None:
    """No versions means no duplicates and no gap, and no exception.

    **What breaks it:** an index error on an empty list. An empty project is
    a project that has nothing in it, and it comes back as that.
    """
    duplicates = check_duplicates([])
    rounds = check_missing_rounds([])

    assert duplicates.has_duplicates is False
    assert rounds.has_gap is False
    assert rounds.present == ()
