"""LC-P2-10's gold corpus: four synthetic manuscripts, and the rows that read them.

**What this is.** The material the annotations are made against. Four ``.docx``
manuscripts, two projects, two partitions, ten comments, and the manifest
rows that name them.

**Why they are synthetic.** A real advisor's manuscript tells us what happened;
it does not tell us what *should* have happened, and a reader that agrees with
a real document is not thereby correct. Every manuscript here can carry an
exact case, because the corpus is written rather than found.

**Why they are generated rather than committed.** The same two arguments
``tests/fixtures/README.md`` makes for LC-P2-07's corpus, and for the same
reasons: a checked-in binary is a binary the repository has to carry and a
reviewer cannot read, and a ``.docx`` is a ZIP whose entries carry timestamps
unless the writer pins them. ``tests/docx_fixtures.py`` pins every entry to
the ZIP epoch, so **the bytes are reproducible** and the manifest's ``sha256``
is a binding rather than a timestamp — a corpus whose bytes move between runs
would make every hash-based check meaningless.
:func:`assert_corpus_is_reproducible` is what says the bytes do not move.

**What the corpus is for.** LC-P2-10 T06 is a person's work: two annotators
read these manuscripts and label each comment, and an arbiter resolves the
disagreements. **So the manifest's ``annotations`` are empty and every
``resolution`` is null.** A manifest that carries labels nobody wrote is
worse than an empty one, and the empty one is a structure
``labcairn.papers.gold_manifest.validate_manifest`` already reads.

**The cases the corpus carries** are named in each fixture's ``purpose`` and
``expectations``, and the mapping from a comment to the case it carries is in
``tests/fixtures/papers-gold/README.md``. The issue kinds the comments were
*built* to carry are named there too — **those are the corpus's intentions,
not the gold set's labels.** A reader may disagree with them, and that
disagreement is the thing the exercise is for.

**The two addresses are read out of the file, not recomputed here.** The
comment element's own address (``comment_locator``) and the body-side address
(``paragraph``, ``start``, ``end``) are what
``labcairn.material.ooxml.read_document`` reports for the written bytes.
**That is the point.** A gold set is scored against systems that read the
same manuscript, so its addresses have to be in the reader's coordinate
system; an address spelled a second way here would be a second vocabulary
for the same rows, and it would drift the first time the reader changed.

**And the split is by project, never by event.** Both versions of project A
are in ``train`` and both versions of project B are in ``test``, because two
versions of one paper are two observations of one thing, and a system that
memorised version 1 would score on version 2 without having generalised.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from docx_fixtures import Comment, Fixture, Revision, comment_range, write_fixture

from labcairn.material.ooxml import RevisionDocument, read_document
from labcairn.papers.gold_manifest import validate_manifest
from labcairn.sources.locators import DocxLocator

#: The manifest in the tree.
_MANIFEST_PATH: Final[Path] = Path("docs") / "papers" / "gold-set-manifest.json"

#: The manifest's schema version.
MANIFEST_VERSION: Final[str] = "1"

#: The generator recorded against every corpus entry.
#:
#: **Named, so a reader can find the thing that produced the bytes.** The
#: bytes themselves are written by ``tests/docx_fixtures.py``'s
#: :func:`~tests.docx_fixtures.write_fixture`, which pins every ZIP entry to
#: the ZIP epoch.
GENERATOR: Final[str] = "tests/gold_set_fixtures.py:gold_fixtures"

#: The two partitions, and the project in each.
#:
#: **One project per partition, and a project in exactly one.** The split is
#: by ``PaperProject``: two versions of one paper are two observations of one
#: thing, so a split by row would put version 1 in one partition and version 2
#: in the other. ``labcairn.papers.gold_manifest.validate_manifest`` refuses a
#: project that appears in two partitions, and names it when it does.
PARTITIONS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "train": ("proj-gold-a",),
        "test": ("proj-gold-b",),
    }
)

#: The issue key the two rounds of project A share.
#:
#: **A recurrence is a relation, and it is recorded rather than inferred.**
#: ADR-0017 D6: the same wording is not the same issue, and the same issue is
#: not the same wording, so a person gives the key. The comment in version 1
#: and the comment in version 2 that share it are the corpus's one recurring
#: issue, and they are in the same project and in different rounds — which is
#: exactly what the chain's recurrence query is over.
RECURRING_ISSUE_KEY: Final[str] = "iss-gold-a-significance"


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """One manuscript: the fixture, the project it belongs to, and its place.

    **The metadata lives here and not in the fixture.** ``tests/docx_fixtures.py``
    is a contract this work order does not own: it knows how to write a Word
    document, and it knows nothing about paper projects, partitions or issue
    keys.
    """

    fixture: Fixture
    #: The paper project this version belongs to. **Every version of one
    #: project is in one partition.**
    project_id: str
    #: The manuscript version the comments were written against.
    version_id: str
    #: The partition the project is in.
    partition: str
    #: The person-given issue key, by comment id, for the comments that carry
    #: one. A comment with no key is uncategorised, and it is not guessed at.
    issue_keys: Mapping[str, str] = field(default_factory=dict)


#: The corpus.
#:
#: **Four manuscripts, two projects, and the cases they carry.** Ordered by
#: project and then by version, so the order is the reading order: version 1
#: of a paper is read before version 2 of it.
_ENTRIES: Final[tuple[CorpusEntry, ...]] = (
    CorpusEntry(
        fixture=Fixture(
            name="gold-a-v1",
            paragraphs=(
                "We train the classifier on the 2019 release of the corpus and "
                "evaluate on the 2021 release.",
                "The method improves over the baseline by 4.2 points on the held-out "
                "split. Every number below is the mean over three random seeds.",
                "We hypothesise that the normalisation step is what produces the gain "
                "under distribution shift.",
                "Table 1 lists the per-dataset scores and Figure 1 shows the learning curves.",
            ),
            revisions=(
                Revision(
                    kind="ins",
                    text=" The appendix lists the hyper-parameters.",
                    author="R. Alvarez",
                    date="2026-04-01T16:05:00Z",
                    element_id="401",
                    paragraph=3,
                    after_text="Figure 1 shows the learning curves.",
                    note="A tracked change in a paragraph no comment is anchored on.",
                ),
            ),
            comments=(
                Comment(
                    comment_id="c301",
                    author="Prof. Lin",
                    date="2026-04-02T09:20:00Z",
                    text=(
                        "The two releases use different labelling guidelines. Say how "
                        "the labels were harmonised, and say who checked it."
                    ),
                    paragraph=0,
                    anchor_text="the 2019 release of the corpus",
                ),
                Comment(
                    comment_id="c302",
                    author="Prof. Lin",
                    date="2026-04-02T09:35:00Z",
                    text=(
                        "Three seeds cannot support the significance claim you make "
                        "here. Report the spread, name the test, and say what would "
                        "falsify the claim."
                    ),
                    paragraph=1,
                    # **The subject crosses a sentence boundary.** A reader that
                    # takes one sentence at a time cannot find it, and that is
                    # the case the corpus carries.
                    anchor_text="4.2 points on the held-out split. Every number below",
                ),
                Comment(
                    comment_id="c303",
                    # **No author.** The attribute is present but empty, which is
                    # the writer's only way of saying the author is absent; an
                    # author is not inferred from the document or the file name.
                    author="",
                    date="2026-04-02T09:50:00Z",
                    text=(
                        "State this as a falsifiable hypothesis, and say what result "
                        "would refute it."
                    ),
                    paragraph=2,
                    anchor_text="the normalisation step is what produces the gain",
                ),
            ),
            purpose=(
                "The advisor's first round on the paper that becomes project A: a "
                "data-quality problem, a statistical claim the seeds cannot carry, "
                "and a hypothesis that is not yet falsifiable."
            ),
            expectations=(
                "Three comments, each attached to the paragraph it was written about.",
                "c301 asks how two releases' labels were harmonised, which is a "
                "data-quality problem.",
                "c302 asks for the spread, the test and the falsifier, which is a "
                "statistical-conclusion problem, and the sentence it is attached to "
                "spans two sentences.",
                "c303 asks for a falsifiable hypothesis, which is a "
                "method-and-hypothesis problem, and it carries no author.",
                "One tracked insertion, in a paragraph no comment is attached to.",
            ),
        ),
        project_id="proj-gold-a",
        version_id="ver-gold-a1",
        partition="train",
        issue_keys=MappingProxyType({"c302": RECURRING_ISSUE_KEY}),
    ),
    CorpusEntry(
        fixture=Fixture(
            name="gold-a-v2",
            paragraphs=(
                "We train the classifier on the 2019 release of the corpus and "
                "evaluate on the 2021 release, with the labels harmonised by two "
                "annotators who checked every disagreement.",
                "The method improves over the baseline by 4.2 points on the held-out "
                "split. Every number below is the mean over ten random seeds, and the "
                "standard deviation is given in Table 2.",
                "We hypothesise that the normalisation step is what produces the gain "
                "under distribution shift, and the analysis plan was pre-registered.",
                "Table 2 gives the per-seed numbers, and Figure 1 shows the learning "
                "curves for the baseline.",
            ),
            revisions=(
                Revision(
                    kind="del",
                    text=" for the baseline",
                    author="R. Alvarez",
                    date="2026-05-05T11:20:00Z",
                    element_id="402",
                    paragraph=3,
                    anchor_text=" for the baseline",
                    note="A tracked deletion, in a paragraph no comment is attached to.",
                ),
            ),
            comments=(
                Comment(
                    comment_id="c401",
                    author="Prof. Lin",
                    date="2026-05-06T10:05:00Z",
                    text=(
                        "Ten seeds is better, but the claim still needs a test and a "
                        "p-value. Name the test and say what happens if the normality "
                        "assumption fails."
                    ),
                    paragraph=1,
                    anchor_text="the mean over ten random seeds",
                ),
                Comment(
                    comment_id="c402",
                    author="Dr. Chen",
                    date="2026-05-06T10:20:00Z",
                    text=(
                        "The experiment was renamed in round one and the old name is "
                        "still used in places. Pick the new name and use it throughout."
                    ),
                    paragraph=0,
                    # **The comment carries no range markers at all.** The writer
                    # writes the comment into word/comments.xml and no anchor into
                    # the body, so the reader reports the comment and reports that
                    # it has no anchor: there is no paragraph and no character
                    # range to read. The body-side address is empty, which is what
                    # the annotation guide's case one is about — its three labels
                    # are `unknown` because the reading ran out of evidence, and
                    # the comment's own address still gets real labels.
                    anchor_text="",
                    after_text="",
                    anchor="none",
                ),
            ),
            purpose=(
                "The advisor's second round on project A: the same statistical "
                "problem raised again, and a general remark whose anchor was never "
                "placed."
            ),
            expectations=(
                "Two comments, one of them with no anchor at all.",
                "c401 asks for the test and the p-value, which is a "
                "statistical-conclusion problem, and it carries the same issue key "
                "as c302 in version 1 — the corpus's one recurring issue.",
                "c402 is about a name that is used two ways, which is a "
                "language-and-format problem at the comment's own address; its "
                "body-side address is empty, because the file carries no range "
                "markers for it. The fixture's own record names the paragraph the "
                "comment was written against; the file does not, and neither does "
                "the manifest, and the guide says all three of its body-side "
                "labels are `unknown`.",
                "One tracked deletion, in a paragraph no comment is attached to.",
            ),
        ),
        project_id="proj-gold-a",
        version_id="ver-gold-a2",
        partition="train",
        issue_keys=MappingProxyType({"c401": RECURRING_ISSUE_KEY}),
    ),
    CorpusEntry(
        fixture=Fixture(
            name="gold-b-v1",
            paragraphs=(
                "We evaluate on a held-out set of 240 documents, all drawn from a "
                "single collection.",
                "This paper presents a method for adapting a pretrained encoder to a "
                "new corpus, and evaluates it on three benchmarks.",
                "The evaluation uses the three corpora described in Appendix A.",
            ),
            revisions=(
                Revision(
                    kind="ins",
                    text=" Two of them are new to this release.",
                    author="K. Nakamura",
                    date="2026-04-08T11:40:00Z",
                    element_id="403",
                    paragraph=2,
                    after_text="described in Appendix A.",
                    note="A tracked change in a paragraph no comment is attached to.",
                ),
            ),
            comments=(
                Comment(
                    comment_id="c501",
                    author="Dr. Osei",
                    date="2026-04-11T08:40:00Z",
                    text=(
                        "Add a control experiment: with the augmentation on and the "
                        "normalisation off, a reader cannot tell which of the two "
                        "produces the gain. Report a variant with neither as a "
                        "baseline, and report it on the same held-out set."
                    ),
                    paragraph=0,
                    # **The comment and its anchor are about different problems.**
                    # The comment asks for a comparison that is missing, which is a
                    # controls-and-ablation problem; the sentence it is attached to
                    # reports the evaluation set, which is a data-quality problem.
                    # One label per comment would have had to pick one of them, and
                    # this is the case that makes the two addresses observably
                    # different rather than a slogan.
                    anchor_text="a held-out set of 240 documents",
                ),
                Comment(
                    comment_id="c502",
                    author="Dr. Osei",
                    date="2026-04-11T09:05:00Z",
                    text=(
                        "The paper opens with the method, so a reader meets the method "
                        "before the claim. Say in the first paragraph what this paper "
                        "contributes, and in what order the rest of it should be read."
                    ),
                    paragraph=1,
                    anchor_text="This paper presents a method for adapting a pretrained encoder",
                ),
            ),
            purpose=(
                "A second paper, in the test partition: a comment that asks for a "
                "control and is anchored on the sentence that reports the "
                "evaluation set, and a paper that opens with its method."
            ),
            expectations=(
                "Two comments.",
                "c501 asks for a control experiment and a baseline variant, which is "
                "a controls-and-ablation problem at the comment's own address, and "
                "it is anchored on the sentence that reports the evaluation set, "
                "which is a data-quality problem at the body-side address. The two "
                "addresses are not the same label, and they are not supposed to be.",
                "c502 asks where the contribution sits and in what order the paper "
                "should be read, which is an introduction-and-storyline problem at "
                "both addresses.",
                "One tracked insertion, in a paragraph no comment is attached to.",
            ),
        ),
        project_id="proj-gold-b",
        version_id="ver-gold-b1",
        partition="test",
    ),
    CorpusEntry(
        fixture=Fixture(
            name="gold-b-v2",
            paragraphs=(
                "We add a control variant with neither the augmentation nor the "
                "normalisation, and report it on the same held-out set.",
                "This paper presents a method for adapting a pretrained encoder to a "
                "new corpus, and evaluates it on three benchmarks and one synthetic "
                "set.",
                "The March batch was collected after the label guideline changed, and "
                "412 rows are affected.",
                "We answered Reviewer 1 by adding the ablation in Section 4.",
                "The word 'significant' appears in three senses in this section, and "
                "'robust' in two.",
            ),
            comments=(
                Comment(
                    comment_id="c601",
                    author="Dr. Osei",
                    # **No date.** The attribute is present but empty, which is the
                    # writer's only way of saying the date is absent; the file's
                    # modification time is not a substitute.
                    date="",
                    text=(
                        "What did you do with the 412 rows? Say whether they were "
                        "relabelled or dropped, and say who checked the decision."
                    ),
                    paragraph=2,
                    anchor_text="412 rows are affected",
                ),
                Comment(
                    comment_id="c602",
                    author="Dr. Osei",
                    date="2026-05-18T11:30:00Z",
                    text=(
                        "In R1 you promised a significance test next to the ablation. "
                        "Section 4 has the ablation and still has no test. Keep the "
                        "promise in R2 or withdraw the claim."
                    ),
                    paragraph=3,
                    anchor_text="adding the ablation in Section 4",
                ),
                Comment(
                    comment_id="c603",
                    author="Dr. Osei",
                    date="2026-05-18T11:45:00Z",
                    text=(
                        "'Significant' and 'robust' are each used in more than one sense "
                        "in this section, and a reader cannot tell which is meant. Pick "
                        "one meaning for each and use it throughout."
                    ),
                    paragraph=4,
                    anchor_text="'significant' appears in three senses",
                ),
            ),
            purpose=(
                "The second round on project B: the control that was asked for, a "
                "comment with no date, a promise to a reviewer that the manuscript "
                "has not kept, and a word that means three things."
            ),
            expectations=(
                "Three comments, one of them with no date.",
                "The first paragraph is the control that c501 in version 1 asked "
                "for, and it is reported on the same held-out set; the evaluation "
                "set's own problem is never mentioned again, so the two addresses of "
                "c501 do not get the same response state.",
                "The second paragraph still opens with the method and does not say "
                "what the paper contributes, which is what c502 in version 1 asked "
                "for.",
                "c601 asks what was done with the affected rows, which is a "
                "data-quality problem, and it carries no date.",
                "c602 asks about a promise made to a reviewer, which is a review-response problem.",
                "c603 asks for one meaning for each of two words, which is a "
                "language-and-format problem.",
            ),
        ),
        project_id="proj-gold-b",
        version_id="ver-gold-b2",
        partition="test",
    ),
)


# ---------------------------------------------------------------------------
# The corpus on disk
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    """The SHA-256 of *data*, as lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def gold_fixtures() -> tuple[Fixture, ...]:
    """The corpus's manuscripts, in a stable order.

    **The order is project, then version.** Version 1 of a paper is read
    before version 2 of it, and the two versions of project A are read before
    either version of project B — which is the order an annotator works in
    and the order the manifest's items come out in.
    """
    return tuple(entry.fixture for entry in _ENTRIES)


def write_corpus(directory: Path) -> dict[str, Path]:
    """Write every manuscript into *directory* and say where each landed.

    **Nothing is written at import.** A module that writes files when it is
    imported dirties the checkout during pytest's collection, and the
    collection is not a place where a side effect belongs. The bytes are
    reproducible — every ZIP entry is pinned to the ZIP epoch — so writing the
    corpus twice gives the same bytes twice.
    """
    return {entry.fixture.name: write_fixture(entry.fixture, directory) for entry in _ENTRIES}


def _corpus(directory: Path) -> tuple[dict[str, Path], dict[str, RevisionDocument]]:
    """The corpus written to *directory*, and the same corpus read back.

    **Read back with the project's own reader.** Every address in the manifest
    comes from :func:`labcairn.material.ooxml.read_document`, so the manifest
    and the chain are reading the same file the same way.
    """
    written = write_corpus(directory)
    documents = {name: read_document(path.read_bytes()) for name, path in written.items()}
    return written, documents


@contextmanager
def _temporary_corpus() -> Iterator[Path]:
    """A temporary directory for a corpus nobody asked to keep."""
    with tempfile.TemporaryDirectory(prefix="labcairn-gold-corpus-") as raw:
        yield Path(raw)


# ---------------------------------------------------------------------------
# The manifest's sections
# ---------------------------------------------------------------------------


def corpus_manifest(directory: Path | None = None) -> dict[str, dict[str, object]]:
    """The manifest's ``corpus`` section: one entry per manuscript.

    **The hash is of the bytes that were written**, and it is a binding
    rather than a timestamp: a corpus whose bytes move between runs would
    make every hash-based check meaningless, and this hash is what says the
    manifest and the corpus are the same corpus.

    **With no directory the corpus is written into a temporary one** and
    hashed there, so the section can be computed without a caller naming a
    place. With a directory, the corpus is written there — the writer is
    idempotent and byte-reproducible — and that copy is hashed.
    """
    if directory is None:
        with _temporary_corpus() as raw:
            return corpus_manifest(raw)
    written, _ = _corpus(directory)
    return {
        entry.fixture.name: {
            "project_id": entry.project_id,
            "version_id": entry.version_id,
            "partition": entry.partition,
            "sha256": _sha256(written[entry.fixture.name].read_bytes()),
            "generator": GENERATOR,
        }
        for entry in _ENTRIES
    }


def issue_keys() -> dict[tuple[str, str], str]:
    """The person-given issue keys, by ``(fixture, comment id)``.

    **A recurrence is a relation, and it is recorded rather than inferred.**
    ADR-0017 D6: the same wording is not the same issue, and the same issue is
    not the same wording, so a person gives the key. This corpus has one
    recurring issue — the significance claim that three seeds cannot carry, and
    that ten seeds still cannot carry without a test — and it appears once in
    each of the two versions of project A.
    """
    return {
        (entry.fixture.name, comment_id): key
        for entry in _ENTRIES
        for comment_id, key in entry.issue_keys.items()
    }


def feedback_id(version_id: str, comment_id: str) -> str:
    """The chain's id for the comment *comment_id* in the version *version_id*.

    **The same derivation the chain uses.**
    ``labcairn.papers.feedback._feedback_id`` derives it as
    ``fb-<sha256(version_id + NUL + comment_id)[:16]>``, and this is that
    formula. The version is part of the key because a comment id is only
    unique inside one document, and two rounds of one manuscript hold two
    different comments with the same id.
    """
    digest = hashlib.sha256(f"{version_id}\x00{comment_id}".encode()).hexdigest()
    return f"fb-{digest[:16]}"


def item_id(project_id: str, version_id: str, comment_id: str) -> str:
    """The manifest's id for one item: one comment in one version.

    **Derived, so the same comment is the same row.** The project is part of
    the key as well as the version, because the item is a reading of a
    comment *in a project*, and two projects may each hold a comment with the
    same id.
    """
    digest = hashlib.sha256(f"{project_id}\x00{version_id}\x00{comment_id}".encode()).hexdigest()
    return f"it-{digest[:16]}"


def anchor_range(fixture: Fixture, comment: Comment) -> tuple[int, int]:
    """The characters of *fixture*'s baseline that *comment* is about.

    **The corpus's own record of the subject**, and it is derived rather than
    written down: ``tests/docx_fixtures.py`` computes a comment's range from
    the baseline text it covers and refuses to build a fixture whose anchor
    does not occur in its own baseline.

    **This is not the address the manifest carries.** The file's range markers
    are paragraph-granular, so the reader reports the whole paragraph; see
    :func:`body_address`, which is the address the manifest uses.
    """
    return comment_range(fixture, comment)


def body_address(
    document: RevisionDocument, comment_id: str
) -> tuple[int | None, int | None, int | None]:
    """The body-side address of a comment, as the project's own reader reports it.

    **Which paragraph, and which characters of it** — the chain's
    ``anchor_paragraph``, ``anchor_start`` and ``anchor_end``.

    **An unanchored comment carries neither a paragraph nor offsets.** The
    reader names three ways a comment can fail to have an anchor — a range
    that starts and never ends, a range that ends and never started, and a
    comment with no range at all — and this corpus carries the third: the
    comment is in ``word/comments.xml`` and no range marker points at it, so
    there is nothing to read and the honest answer on the body-side address is
    ``UNKNOWN``. The other two keep the paragraph and leave the offsets
    unknown, which is a different case and a different manifest row.

    :raises KeyError: when the document holds no comment with that id.
    """
    for comment in document.comments:
        if comment.comment_id == comment_id:
            anchor = comment.anchor
            return anchor.paragraph, anchor.start, anchor.end
    raise KeyError(f"the document holds no comment {comment_id!r}")


def comment_locator(document: RevisionDocument, comment_id: str) -> dict[str, Any]:
    """The comment element's own address, as the reader reports it.

    **The comment's address, not the body's.** ``labcairn.papers.feedback``
    keeps the two apart for the same reason this manifest does: the comment
    element in ``word/comments.xml`` is *what was written*, and the body's
    paragraph and offsets are *where it was written about*.

    **Built with the project's own model**, so the address is validated by the
    contract rather than spelled out here: ``DocxLocator`` is closed, and it
    refuses a span with one endpoint.

    :raises KeyError: when the document holds no comment with that id.
    """
    for comment in document.comments:
        if comment.comment_id == comment_id:
            locator: DocxLocator = comment.locator
            return dict(locator.model_dump(mode="json"))
    raise KeyError(f"the document holds no comment {comment_id!r}")


def manifest_items(directory: Path | None = None) -> list[dict[str, Any]]:
    """The manifest's items: one per comment in the corpus.

    **Every item's ``annotations`` is empty and every ``resolution`` is
    null.** A label is a person's work (LC-P2-10 T06), and a manifest that
    carries labels nobody wrote is worse than an empty one. The empty one is
    a structure ``validate_manifest`` already reads — that is the difference
    between a manifest and a finished gold set, and
    ``labcairn.papers.gold_manifest.require_annotated`` is what says whether
    the gold set is finished.

    **Both addresses are read out of the written file**, by the project's own
    reader, so they are the addresses the chain would record for the same
    comment.

    ``issue_key`` is the one field here that the manifest's own reader does
    not read. It is here so that the recurring issue is visible in the
    manifest as well as in the corpus, and it is copied from
    :func:`issue_keys` rather than written by hand.
    """
    if directory is None:
        with _temporary_corpus() as raw:
            return manifest_items(raw)
    _, documents = _corpus(directory)
    return _items(documents)


def manifest_document(directory: Path | None = None) -> dict[str, Any]:
    """The manifest skeleton: every item, and no annotations.

    **The skeleton, not the manifest.** Every item's ``annotations`` is an
    empty list and every item's ``resolution`` is null, because the readings
    are a person's work. This is what the committed
    ``docs/papers/gold-set-manifest.json`` was before the annotators filled it
    in — **so do not write it over a manifest that has been annotated.**

    The corpus's hashes are computed here, which means the skeleton is only
    correct for the corpus as it stands: change a manuscript and the manifest
    has to be regenerated.
    """
    if directory is None:
        with _temporary_corpus() as raw:
            return manifest_document(raw)
    written, documents = _corpus(directory)
    return {
        "version": MANIFEST_VERSION,
        "corpus": {
            entry.fixture.name: {
                "project_id": entry.project_id,
                "version_id": entry.version_id,
                "partition": entry.partition,
                "sha256": _sha256(written[entry.fixture.name].read_bytes()),
                "generator": GENERATOR,
            }
            for entry in _ENTRIES
        },
        "partitions": {name: list(members) for name, members in PARTITIONS.items()},
        "items": _items(documents),
    }


def _items(documents: Mapping[str, RevisionDocument]) -> list[dict[str, Any]]:
    """The manifest's items, from the corpus read back by the reader."""
    keys = issue_keys()
    items: list[dict[str, Any]] = []
    for entry in _ENTRIES:
        document = documents[entry.fixture.name]
        for comment in entry.fixture.comments:
            paragraph, start, end = body_address(document, comment.comment_id)
            items.append(
                {
                    "item_id": item_id(entry.project_id, entry.version_id, comment.comment_id),
                    "project_id": entry.project_id,
                    "version_id": entry.version_id,
                    "feedback_id": feedback_id(entry.version_id, comment.comment_id),
                    "fixture": entry.fixture.name,
                    "comment_id": comment.comment_id,
                    "comment_locator": comment_locator(document, comment.comment_id),
                    "paragraph": paragraph,
                    "start": start,
                    "end": end,
                    "annotations": [],
                    "resolution": None,
                    "issue_key": keys.get((entry.fixture.name, comment.comment_id)),
                }
            )
    return items


# ---------------------------------------------------------------------------
# The self-checks
# ---------------------------------------------------------------------------


def assert_corpus_is_reproducible(directory: Path) -> None:
    """The corpus's bytes do not move: writing it twice gives the same bytes.

    **The property the manifest's hashes depend on.** The manifest binds
    itself to the corpus by ``sha256``, and that binding is worth nothing if
    the corpus's bytes differ from one run to the next. The writer pins every
    ZIP entry to the ZIP epoch for exactly this reason.

    Checked three ways, because each catches a different mistake: two
    directories give the same bytes, writing over a file gives the same bytes
    as the first write, and the hashes the manifest records are the hashes of
    those bytes.
    """
    first = write_corpus(directory / "first")
    second = write_corpus(directory / "second")
    for name, path in first.items():
        other = second[name]
        if path.read_bytes() != other.read_bytes():
            raise AssertionError(
                f"{name} was written twice and the two writes differ. The manifest's "
                "sha256 binds the corpus to the manifest, and a corpus whose bytes "
                "move makes that binding worth nothing."
            )

    rewritten = write_corpus(directory / "first")
    for name, path in first.items():
        if path.read_bytes() != rewritten[name].read_bytes():
            raise AssertionError(
                f"{name} was rewritten over itself and its bytes changed. A corpus "
                "that changes when it is written again cannot be hashed."
            )

    recorded = corpus_manifest(directory / "first")
    for name, entry in recorded.items():
        digest = _sha256(first[name].read_bytes())
        if entry["sha256"] != digest:
            raise AssertionError(
                f"the manifest records {entry['sha256']!r} for {name} and the bytes "
                f"hash to {digest!r}. The record and the measurement disagree, and "
                "the measurement wins."
            )


def assert_manifest_matches_corpus(path: Path | None = None) -> None:
    """The committed manifest agrees with the corpus that is in the tree.

    **Structure only.** The annotators fill in ``annotations`` and
    ``resolution``, so those are not compared — a manifest that has been
    annotated is still a manifest that must match its corpus. Everything that
    names the material is compared: the corpus section and its hashes, the
    partitions, and each item's identity and its two addresses.

    The manifest is also read through
    ``labcairn.papers.gold_manifest.validate_manifest``, so a manifest that
    breaks one of the manifest's own rules is refused by name.
    """
    target = path if path is not None else _MANIFEST_PATH
    if not target.is_file():
        raise FileNotFoundError(
            f"{target} is not there. The manifest is the contract the annotators "
            "fill in, and its absence is the first thing a reader should be told."
        )

    committed = json.loads(target.read_text(encoding="utf-8"))
    validate_manifest(committed)

    expected = manifest_document()
    if committed["version"] != expected["version"]:
        raise AssertionError(
            f"the manifest says version {committed['version']!r} and the generator "
            f"says {expected['version']!r}."
        )
    if committed["corpus"] != expected["corpus"]:
        raise AssertionError(
            "the manifest's corpus section does not match the corpus that is in the "
            "tree. A manuscript changed and the manifest was not regenerated, so the "
            "hashes no longer bind."
        )
    if committed["partitions"] != expected["partitions"]:
        raise AssertionError(
            f"the manifest's partitions are {committed['partitions']!r} and the "
            f"generator's are {expected['partitions']!r}. The split is by project, "
            "and every version of one project is in one partition."
        )

    committed_items = committed["items"]
    expected_items = expected["items"]
    if len(committed_items) != len(expected_items):
        raise AssertionError(
            f"the manifest holds {len(committed_items)} items and the corpus holds "
            f"{len(expected_items)} comments. Every comment in the corpus is one "
            "item."
        )
    fields = (
        "item_id",
        "project_id",
        "version_id",
        "feedback_id",
        "fixture",
        "comment_id",
        "comment_locator",
        "paragraph",
        "start",
        "end",
        "issue_key",
    )
    for position, (actual, wanted) in enumerate(zip(committed_items, expected_items, strict=True)):
        for field_name in fields:
            if actual.get(field_name) != wanted[field_name]:
                raise AssertionError(
                    f"item {position} has {field_name}={actual.get(field_name)!r} and "
                    f"the corpus says {wanted[field_name]!r}. The manifest and the "
                    "corpus are not the same corpus."
                )


def assert_the_feedback_ids_match_the_chain() -> None:
    """The manifest's feedback ids are the ones the chain would mint.

    **The chain's derivation, not a copy of it.** The manifest's
    ``feedback_id`` has to be the id ``labcairn.papers.feedback`` would give
    the same comment in the same version, or a row the manifest names is not
    the row the chain holds. The chain's function is private, so it is
    imported here rather than spelled out a second time — a second spelling
    is a second vocabulary for the same rows.
    """
    from labcairn.papers.feedback import _feedback_id

    for entry in _ENTRIES:
        for comment in entry.fixture.comments:
            mine = feedback_id(entry.version_id, comment.comment_id)
            theirs = _feedback_id(entry.version_id, comment.comment_id)
            if mine != theirs:
                raise AssertionError(
                    f"the manifest would call {mine!r} the feedback id for "
                    f"{comment.comment_id!r} in {entry.version_id!r} and the chain "
                    f"calls it {theirs!r}."
                )


__all__ = [
    "GENERATOR",
    "MANIFEST_VERSION",
    "PARTITIONS",
    "RECURRING_ISSUE_KEY",
    "CorpusEntry",
    "anchor_range",
    "assert_corpus_is_reproducible",
    "assert_manifest_matches_corpus",
    "assert_the_feedback_ids_match_the_chain",
    "body_address",
    "comment_locator",
    "corpus_manifest",
    "feedback_id",
    "gold_fixtures",
    "issue_keys",
    "item_id",
    "manifest_document",
    "manifest_items",
    "write_corpus",
]
