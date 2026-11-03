"""Reading a Word document's revision history without damaging it.

This is LC-P2-07's deliverable. A `.docx` with tracked changes holds the
original and the edited text **at the same time**, in one file, and the
whole of the mentor-trajectory line rests on being able to tell them apart
and to say who changed what.

**Why this is written here and not taken from a library.** The upstream
study records what three libraries do with the same file
(``docs/research/upstream-study/``):

* ``python-docx`` — the project's own dependency — reads ``w:t`` only, so a
  deleted run reads as empty and **the text the advisor deleted never
  reaches the output**;
* Docling drops the same runs for the same reason, and anchors comments at
  paragraph granularity;
* ``docx2python`` reads comments, and **loses every comment in the document**
  when the number of range markers and the number of comment elements
  differ.

The measurement in ``docs/acceptance/LC-P2-07-fidelity-baseline.md`` puts
numbers on all three: no text arm reports a revision as an event, none
recovers a deletion, and one loses eight of fourteen comments. The reader
here is written against ECMA-376 / ISO-IEC 29500 and is held to that
measurement.

**What it refuses to do.**

* **It never writes.** The bytes are opened, read and closed. There is no
  "accept all revisions" operation, because that is a destructive
  transformation that produces a different document — ADR-0014 D6 forbids
  it, and the first-party ``docx`` skill's ``accept_changes.py`` is exactly
  the thing that rule is about.
* **It never guesses.** A revision with no ``w:author`` has an unknown
  author, not an empty one; a revision with no ``w:date`` has an unknown
  date, not the file's mtime. A comment whose range does not pair is
  reported with its body and an **unknown anchor**, with the reason named.
  The design's rule is the project's own: *"we could not look" is not
  "there was nothing there"*.
* **It never expands entities.** A part that declares a DTD is refused, and
  the refusal is recorded. Entity expansion is a denial-of-service vector,
  and the standard library's XML parser is not the place to trust.

**The two views.** A Word document reads two ways, and ADR-0014 D4 names
them: *accepted* is the text as if every revision were accepted, *rejected*
is the text as if every revision were rejected. The reader produces both,
and a :class:`~labcairn.sources.locators.DocxLocator` names which one a
character range is in — because the same range means different characters in
each, and an address that could mean either is not an address.

**Where the deleted text goes.** It is not in the accepted view, and it is
not nowhere: a ``w:del`` element's text in the rejected view is the deleted
text, and it is a first-class event with its own locator, its own author and
date, and its own hash. For a project whose thesis is *"the deletion is the
signal"*, losing it is losing the thesis.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from types import ModuleType
from typing import Final, Literal
from xml.etree import ElementTree

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import DocxLocator
from labcairn.sources.source import SourceKind

__all__ = [
    "CommentEvent",
    "DocxAdapter",
    "RevisionDocument",
    "RevisionEvent",
    "read_document",
]

#: The WordprocessingML namespace.
W: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: The namespace-qualified names this module reads.
_TAG: Final[dict[str, str]] = {
    "paragraph": f"{{{W}}}p",
    "insertion": f"{{{W}}}ins",
    "deletion": f"{{{W}}}del",
    "move_from": f"{{{W}}}moveFrom",
    "move_to": f"{{{W}}}moveTo",
    "text": f"{{{W}}}t",
    "deleted_text": f"{{{W}}}delText",
    "tab": f"{{{W}}}tab",
    "break": f"{{{W}}}br",
    "carriage_return": f"{{{W}}}cr",
    "comment_start": f"{{{W}}}commentRangeStart",
    "comment_end": f"{{{W}}}commentRangeEnd",
    "comment_reference": f"{{{W}}}commentReference",
    "comment": f"{{{W}}}comment",
}

#: The two views ADR-0014 D4 names. A Word document reads two ways, and an
#: address must say which one -- see :class:`~labcairn.sources.locators.DocxLocator`.
DocxView = Literal["accepted", "rejected"]

#: The four tracked-change kinds, and the view each contributes to.
#:
#: An insertion and a move destination are in the **accepted** view; a
#: deletion and a move source are in the **rejected** view. That is what
#: "accepting" and "rejecting" mean, and it is the whole of the distinction
#: between the two texts.
_ACCEPTED_KINDS: Final[frozenset[str]] = frozenset({"ins", "moveTo"})
_REJECTED_KINDS: Final[frozenset[str]] = frozenset({"del", "moveFrom"})

#: The package parts this reader looks in.
_DOCUMENT_PART: Final[str] = "word/document.xml"
_COMMENTS_PART: Final[str] = "word/comments.xml"


# --------------------------------------------------------------------------- #
# the model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RevisionEvent:
    """One tracked change, as the file records it.

    **The author and the date are optional, and their absence is the
    answer.** Word permits a ``w:ins`` with no ``w:author`` and no
    ``w:date``, and Phase 1's ``SourceReadability`` already separates "we
    could not look" from "there was nothing there"; this is the same
    distinction one level down, and it is the design's rule that a missing
    author is ``UNKNOWN`` rather than a guess.
    """

    #: ``ins``, ``del``, ``moveFrom`` or ``moveTo``.
    kind: str
    #: The changed text: what was inserted, or what was deleted.
    text: str
    #: The revision's author, or ``None`` when the file records none.
    author: str | None
    #: The revision's timestamp, or ``None`` when the file records none.
    date: datetime | None
    #: Word's ``w:id`` for the revision, or ``None`` when the file records
    #: none. It pairs a move's source with its destination.
    element_id: str | None
    #: The locator that addresses this revision, and resolves to ``text``.
    locator: DocxLocator
    #: The index of the paragraph the revision sits in, or ``None`` when no
    #: paragraph holds it. A table row's mark (``w:trPr/w:ins``, ``w:trPr/w:del``)
    #: is such a case: Word writes it on the row's properties, outside every
    #: paragraph, and an index invented for it would name a place the file
    #: does not give it.
    paragraph: int | None
    #: The revision's place in the paragraph's **rejected** (baseline) text.
    #: A deletion covers the text it removed; an insertion is a *point*,
    #: because an insertion contributes nothing to the baseline. Both are
    #: ``None`` together with :attr:`paragraph` when the revision sits
    #: outside every paragraph -- there is then no baseline text for it to
    #: have a place in, and a coordinate that names no text is a coordinate
    #: nobody can check.
    baseline_start: int | None
    baseline_end: int | None
    #: Whether this revision is nested inside another one. Word permits it
    #: and a reader that flattens it cannot tell "inserted then deleted"
    #: from "inserted".
    nested: bool
    #: The hash of ``text`` at the time it was read, so a later read can
    #: tell whether the same address still holds the same text.
    text_sha256: str


@dataclass(frozen=True)
class CommentAnchor:
    """Where a comment is anchored, or why it is not.

    The five failure modes are named rather than lumped: a range that
    starts and never ends, a range that ends and never started, a
    comment with no range at all, a range that starts in one
    paragraph and ends in another, and a range that closes where it
    opens. They are different facts and a
    reader that reports them as one loses the distinction between a
    document that is damaged and a document that is merely unusual.
    """

    #: ``"resolved"`` or ``"unknown"``.
    status: str
    #: Why the anchor is unknown, or ``None`` when it resolved.
    reason: str | None
    #: The paragraph the anchor is in, or ``None`` when it is not known.
    paragraph: int | None
    #: The anchored range in the paragraph's rejected (baseline) text.
    start: int | None
    end: int | None
    #: The text the comment covers, in the baseline.
    #:
    #: **Carried, and not inferred from elsewhere.** This is the text the
    #: offsets above name: ``baseline_paragraphs[paragraph][start:end]``, cut
    #: from the same baseline the offsets are into, so the two agree by
    #: construction and a reader can check that they do. It is the first link
    #: of LC-P2-09's feedback chain, and an empty one is a chain that cannot
    #: be traversed.
    #:
    #: **Empty whenever the anchor is unknown, and each unknown is a fact
    #: rather than a failure.** There is no range to name text and the
    #: reason says which of the five shapes it was; a range that starts in
    #: one paragraph and ends in another has two offsets into two different
    #: texts, so no single slice is the text the comment covers; and a
    #: range that closes where it opens covers a position, not a passage —
    #: reported as unknown rather than as a passage nobody wrote.
    text: str


@dataclass(frozen=True)
class CommentEvent:
    """One comment, as the file records it.

    **A comment with an unusable anchor is still a comment.** Its body,
    author and date are in the file, and dropping them because the anchor
    did not pair is the failure the upstream study found in a library and
    this reader exists to avoid.
    """

    comment_id: str
    author: str | None
    date: datetime | None
    text: str
    #: The locator that addresses the comment element in the comments part,
    #: and resolves to ``text``.
    locator: DocxLocator
    anchor: CommentAnchor
    text_sha256: str


@dataclass(frozen=True)
class RevisionDocument:
    """Everything the reader found in one document.

    ``problems`` is not an afterthought: an adapter that can only report
    success is indistinguishable from one that silently dropped a comment,
    and the difference between those two is the whole point of the type.
    """

    revisions: tuple[RevisionEvent, ...] = ()
    comments: tuple[CommentEvent, ...] = ()
    #: The document's text with every revision accepted.
    accepted_text: str = ""
    #: The document's text with every revision rejected — the original.
    rejected_text: str = ""
    #: The accepted text of each paragraph, in document order.
    paragraphs: tuple[str, ...] = ()
    #: The rejected text of each paragraph, in document order.
    baseline_paragraphs: tuple[str, ...] = ()
    problems: tuple[ExtractionProblem, ...] = ()


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _local_name(tag: str) -> str:
    """The tag's name without its namespace."""
    return tag.rsplit("}", 1)[-1]


def _element_path(element: ElementTree.Element, root: ElementTree.Element) -> str:
    """A re-derivable path to ``element`` within ``root``.

    Each step is ``tag[n]``, where ``n`` is the 1-based index among the
    siblings that share that tag. The path names **structure** rather than
    content, so it survives a re-parse of the same tree and does not move
    when the text inside an element changes.
    """
    steps: list[str] = []
    current = element
    while current is not root:
        parent = _parent_of(current, root)
        if parent is None:
            break
        tag = _local_name(current.tag)
        index = 0
        for sibling in parent:
            if sibling.tag == current.tag:
                index += 1
                if sibling is current:
                    break
        steps.append(f"{tag}[{index}]")
        current = parent
    steps.append(f"{_local_name(root.tag)}[1]")
    steps.reverse()
    return "/" + "/".join(steps)


def _parent_of(
    element: ElementTree.Element, root: ElementTree.Element
) -> ElementTree.Element | None:
    """``element``'s parent, or ``None`` when it is the root.

    ``ElementTree`` has no parent pointer, so the tree is walked. That is
    O(n) per lookup and the walk is over one document's paragraphs, which
    is not a cost this module needs to hide.
    """
    for candidate in root.iter():
        for child in candidate:
            if child is element:
                return candidate
    return None


def _text_in(element: ElementTree.Element, view: str) -> str:
    """The text ``element`` contributes in ``view``.

    One rule, and it covers every element:

    - an insertion or a move destination contributes its text in the
      **accepted** view and nothing in the rejected one;
    - a deletion or a move source contributes its text in the **rejected**
      view and nothing in the accepted one;
    - ``w:t`` contributes in the accepted view, ``w:delText`` in the
      rejected one.

    A nested revision is decided by its **outermost** enclosing revision:
    text inside an insertion is gone when the insertion is rejected, and
    text inside a deletion is gone when the deletion is accepted. That is
    what "accept" and "reject" mean, and it is why the rule needs no
    special case for nesting.
    """
    parts: list[str] = []
    for child in element:
        tag = child.tag
        if tag in (_TAG["insertion"], _TAG["move_to"]):
            if view == "accepted":
                parts.append(_text_in(child, view))
            continue
        if tag in (_TAG["deletion"], _TAG["move_from"]):
            if view == "rejected":
                parts.append(_text_in(child, view))
            continue
        if tag == _TAG["text"]:
            parts.append(child.text or "")
            continue
        if tag == _TAG["deleted_text"]:
            if view == "rejected":
                parts.append(child.text or "")
            continue
        if tag == _TAG["tab"]:
            parts.append("\t")
            continue
        if tag in (_TAG["break"], _TAG["carriage_return"]):
            parts.append("\n")
            continue
        parts.append(_text_in(child, view))
    return "".join(parts)


def _parse_part(name: str, data: bytes) -> ElementTree.Element | None:
    """Parse one XML part, or return ``None`` after refusing it.

    **A part that declares a DTD is refused.** Entity expansion is a
    denial-of-service vector, and the standard library's parser is not the
    place to decide that a document's entities are safe. The refusal names
    the part, so the reader's problem list says which part and why.
    """
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head:
        raise _RefusedPartError(
            f"{name} declares a DTD, which is refused: entity expansion is a "
            f"denial-of-service vector and this reader does not expand entities."
        )
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise _RefusedPartError(f"{name} is not well-formed XML: {exc}") from exc


class _RefusedPartError(Exception):
    """A part this reader will not read, and why."""


def _parse_date(value: str | None) -> datetime | None:
    """A revision's timestamp, or ``None``.

    Word writes ISO-8601 with a ``Z``. A value this reader cannot parse is
    reported as **unknown**, not as the file's mtime and not as now: an
    unreadable date is not a date.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _revision_kind(tag: str) -> str | None:
    """The tracked-change kind of a tag, or ``None``."""
    for name, needle in (
        ("ins", _TAG["insertion"]),
        ("del", _TAG["deletion"]),
        ("moveFrom", _TAG["move_from"]),
        ("moveTo", _TAG["move_to"]),
    ):
        if tag == needle:
            return name
    return None


def _scan_paragraph(
    paragraph: ElementTree.Element,
) -> tuple[
    list[tuple[ElementTree.Element, str, int, int, bool]],
    list[tuple[str, str, str, int]],
]:
    """The revisions and the comment markers of a paragraph, with their places.

    The first list holds ``(element, kind, baseline_start, baseline_end,
    nested)``; the second holds ``(kind, comment_id, element_path,
    baseline_offset)`` for the three marker kinds.

    **One walk, so the two cannot drift apart.** A revision's place and a
    comment marker's place are the same coordinate system, and a reader
    that computed them separately would let a revision claim it removed a
    passage that a comment says it never covered.

    **And the offset advances by exactly what the element contributes to
    the rejected view** — the same rule :func:`_text_in` applies:

    - a deletion contributes the text it removed;
    - an insertion contributes nothing, because an insertion is not in the
      original;
    - the text inside a revision is counted **once**, by the revision. The
      walk inside it looks for a revision nested within and adds nothing.

    Counting a revision's text twice would put every revision after the
    first at the wrong place in the baseline, and every comment marker
    after it at the wrong place too. **A coordinate that names the wrong
    place is a coordinate nobody can check** — and a comment's anchored
    text, cut at the wrong offsets, is text nobody wrote.

    **A revision nested inside another has no separate place.** Its text
    is the enclosing revision's own text, so it is reported at the
    enclosing revision's place.

    **And a revision is reported by the nearest paragraph that contains
    it** -- and by :func:`_scan_outside_paragraphs` when no paragraph
    contains it, which is the case a table row's mark belongs to. A
    run's content is not limited to text: it can carry a drawing, and a
    drawing carries a text box, and a text box holds paragraphs of its
    own -- real material holds exactly that, inside a
    ``mc:AlternateContent`` whose ``Choice`` and ``Fallback`` each carry
    one. Those inner paragraphs are paragraphs (``iter`` finds them and
    :func:`read_document` scans each one), so the outer paragraph's walk
    reports them a second time if it crosses into them. This walk does
    not: from the first nested ``w:p`` downward it still advances the
    offset -- the outer paragraph's text counts the box's text either
    way, and the two coordinate systems must agree -- but it reports no
    revision and no comment marker there. One tracked change, one
    event, and the reporter is the nearest paragraph.
    """
    revisions: list[tuple[ElementTree.Element, str, int, int, bool]] = []
    markers: list[tuple[str, str, str, int]] = []

    def walk(
        element: ElementTree.Element,
        offset: int,
        depth: int,
        enclosing: tuple[int, int] | None,
        reports: bool,
        counting: bool = False,
    ) -> int:
        """Walk ``element``'s children, returning the new baseline offset.

        ``enclosing`` is the baseline place of the revision this element
        sits inside, or ``None`` at the top level. ``reports`` is False
        once the walk has crossed into a nested paragraph: the offsets
        are still this paragraph's, but the revision and the comment
        marker belong to the nested paragraph's own scan.

        ``counting`` is True once the walk is inside a revision that
        contributes to the baseline. **The deleted words are baseline
        words** -- the rejected view is the manuscript as it read before
        the change -- so the walk keeps advancing through them, and a
        comment marker inside the deletion is recorded at the place its
        words actually sit. An insertion contributes nothing to the
        baseline, so its subtree never counts: every marker inside one
        collapses to the insertion point, which is the honest coordinate
        for a comment on text the baseline does not hold.
        """
        for child in element:
            child_reports = reports and child.tag != _TAG["paragraph"]
            kind = _revision_kind(child.tag)
            if kind is not None:
                if enclosing is None:
                    width = len(_text_in(child, "rejected")) if kind in _REJECTED_KINDS else 0
                    start = offset
                    offset += width
                    if child_reports:
                        revisions.append((child, kind, start, offset, depth > 0))
                    walk(
                        child,
                        start,
                        depth + 1,
                        (start, offset),
                        child_reports,
                        counting=kind in _REJECTED_KINDS,
                    )
                else:
                    if child_reports:
                        revisions.append((child, kind, enclosing[0], enclosing[1], depth > 0))
                    walk(
                        child,
                        offset,
                        depth + 1,
                        enclosing,
                        child_reports,
                        counting=counting and kind in _REJECTED_KINDS,
                    )
                continue
            if child_reports and child.tag == _TAG["comment_start"]:
                markers.append(
                    ("start", child.get(f"{{{W}}}id", ""), _element_path(child, paragraph), offset)
                )
                continue
            if child_reports and child.tag == _TAG["comment_end"]:
                markers.append(
                    ("end", child.get(f"{{{W}}}id", ""), _element_path(child, paragraph), offset)
                )
                continue
            if child_reports and child.tag == _TAG["comment_reference"]:
                markers.append(
                    (
                        "reference",
                        child.get(f"{{{W}}}id", ""),
                        _element_path(child, paragraph),
                        offset,
                    )
                )
                continue
            if not counting and enclosing is not None:
                # The text inside a revision is already counted by it.
                walk(child, offset, depth, enclosing, child_reports)
                continue
            if child.tag in (_TAG["text"], _TAG["deleted_text"]):
                offset += len(child.text or "")
                continue
            if child.tag == _TAG["tab"]:
                offset += 1
                continue
            if child.tag in (_TAG["break"], _TAG["carriage_return"]):
                offset += 1
                continue
            offset = walk(child, offset, depth, enclosing, child_reports, counting)
        return offset

    walk(paragraph, 0, 0, None, True)
    return revisions, markers


def _scan_outside_paragraphs(
    root: ElementTree.Element,
) -> list[tuple[ElementTree.Element, str, bool]]:
    """The revision elements no paragraph holds, in document order.

    Returns ``(element, kind, nested)``. **These are the changes a scan of
    paragraphs cannot see.** :func:`_scan_paragraph` reports a revision to
    the nearest paragraph that contains it, and a tracked change on a
    *table row* is written on the row's properties -- ``w:trPr/w:ins``,
    ``w:trPr/w:del`` -- where no paragraph contains it. Word also writes
    such a marker with no children at all, so it carries no text; the event
    the reader builds from it says *this row was inserted by this author at
    this time* and quotes nothing, which is what the file records.

    **The walk stops descending to report at a paragraph, and never starts
    reporting inside one.** Every revision element under some ``w:p`` is
    that paragraph's to report, and the paragraph loop already reports it;
    the two scans therefore split the part's revision elements on the
    question "does a paragraph contain it", which is what keeps
    :func:`read_document` reporting each element **exactly once**. A walk
    that reported here as well as in the paragraph scan would double the
    element; a walk that reported neither would lose it, and a lost revision
    is the failure no caller can see.

    Descent continues through a paragraph's subtree (a nested paragraph is
    still a paragraph, and the loop scans it) and through a revision
    element's subtree, where a further revision outside every paragraph is
    marked ``nested`` -- the same disclosure :func:`_scan_paragraph` gives
    inside a paragraph.
    """
    found: list[tuple[ElementTree.Element, str, bool]] = []
    # An explicit stack rather than recursion: a document's tree is shallow,
    # but a stack keeps the walk's cost on the tree and not on the interpreter.
    stack: list[tuple[ElementTree.Element, bool, bool]] = [(root, False, False)]
    while stack:
        element, in_paragraph, in_revision = stack.pop()
        kind = None if in_paragraph else _revision_kind(element.tag)
        if kind is not None:
            found.append((element, kind, in_revision))
            in_revision = True
        # A paragraph owns everything under it, down to a nested paragraph,
        # which the paragraph loop picks up as a paragraph of its own.
        child_in_paragraph = in_paragraph or element.tag == _TAG["paragraph"]
        children = list(element)
        for child in reversed(children):
            stack.append((child, child_in_paragraph, in_revision))
    return found


def _comment_body(comment: ElementTree.Element) -> str:
    """A comment's text, paragraph by paragraph."""
    paragraphs: list[str] = []
    for paragraph in comment.iter(_TAG["paragraph"]):
        paragraphs.append(_text_in(paragraph, "accepted"))
    return "\n\n".join(paragraphs)


def read_document(data: bytes) -> RevisionDocument:
    """Read a Word document's revisions and comments.

    **The bytes are never modified.** They are opened, read and closed; the
    caller keeps the original and this function keeps nothing of it.
    """
    problems: list[ExtractionProblem] = []

    try:
        archive = zipfile.ZipFile(_BytesReader(data))
    except (zipfile.BadZipFile, OSError) as exc:
        return RevisionDocument(
            problems=(
                ExtractionProblem(
                    code="docx_unreadable",
                    detail=(
                        f"the bytes are not a Word document this reader can open: "
                        f"{type(exc).__name__}: {exc}. It is inventoried and hashed; "
                        f"no revision history is extracted, because a history we could "
                        f"not read is not an empty history."
                    ),
                ),
            )
        )

    with archive:
        names = set(archive.namelist())
        if _DOCUMENT_PART not in names:
            return RevisionDocument(
                problems=(
                    ExtractionProblem(
                        code="docx_part_absent",
                        detail=(
                            f"the archive has no {_DOCUMENT_PART}; it is not a Word "
                            f"document this reader can read. It is inventoried and "
                            f"hashed, and nothing is extracted from it."
                        ),
                    ),
                )
            )

        try:
            document_root = _parse_part(_DOCUMENT_PART, archive.read(_DOCUMENT_PART))
        except _RefusedPartError as exc:
            return RevisionDocument(
                problems=(ExtractionProblem(code="docx_part_refused", detail=str(exc)),)
            )
        assert document_root is not None

        comments_root: ElementTree.Element | None = None
        if _COMMENTS_PART in names:
            try:
                comments_root = _parse_part(_COMMENTS_PART, archive.read(_COMMENTS_PART))
            except _RefusedPartError as exc:
                problems.append(ExtractionProblem(code="docx_part_refused", detail=str(exc)))

    revisions: list[RevisionEvent] = []
    comments: list[CommentEvent] = []
    accepted_paragraphs: list[str] = []
    baseline_paragraphs: list[str] = []
    markers_by_comment: dict[str, list[tuple[str, int, int, str]]] = {}

    paragraphs = list(document_root.iter(_TAG["paragraph"]))
    for index, paragraph in enumerate(paragraphs):
        accepted = _text_in(paragraph, "accepted")
        baseline = _text_in(paragraph, "rejected")
        accepted_paragraphs.append(accepted)
        baseline_paragraphs.append(baseline)

        found_revisions, found_markers = _scan_paragraph(paragraph)
        for kind, comment_id, path, offset in found_markers:
            markers_by_comment.setdefault(comment_id, []).append((kind, index, offset, path))

        for element, kind, start, end, nested in found_revisions:
            view: DocxView = "accepted" if kind in _ACCEPTED_KINDS else "rejected"
            text = _text_in(element, view)
            element_path = _element_path(element, document_root)
            revisions.append(
                RevisionEvent(
                    kind=kind,
                    text=text,
                    author=element.get(f"{{{W}}}author"),
                    date=_parse_date(element.get(f"{{{W}}}date")),
                    element_id=element.get(f"{{{W}}}id"),
                    locator=DocxLocator(
                        part=_DOCUMENT_PART,
                        element_path=element_path,
                        view=view,
                        char_start=0,
                        char_end=len(text),
                    ),
                    paragraph=index,
                    baseline_start=start,
                    baseline_end=end,
                    nested=nested,
                    text_sha256=_sha256(text),
                )
            )

    # **And the changes no paragraph holds.** A table row's mark is written on
    # the row's properties, outside every paragraph, so the loop above never
    # reaches it. They come last: the paragraph pass finishes first, then the
    # document scan reports its elements in document order among themselves.
    # So ``revisions`` is paragraph-ordered and then row-ordered, not one
    # merged document sequence -- the file gives a row's mark no paragraph to
    # be counted against, and pretending otherwise would put it inside a
    # paragraph it is not in. Nothing in this reader, or in the chain's writer,
    # keys an identity on that order: the derived id is the address plus the
    # count of changes already seen *at that address*, and a row's mark is the
    # first and only change at its own. Each such event carries no paragraph and
    # no baseline place -- the two ``None``s are the file's own fact, not a gap
    # in this reader.
    for element, kind, nested in _scan_outside_paragraphs(document_root):
        marker_view: DocxView = "accepted" if kind in _ACCEPTED_KINDS else "rejected"
        text = _text_in(element, marker_view)
        revisions.append(
            RevisionEvent(
                kind=kind,
                text=text,
                author=element.get(f"{{{W}}}author"),
                date=_parse_date(element.get(f"{{{W}}}date")),
                element_id=element.get(f"{{{W}}}id"),
                locator=DocxLocator(
                    part=_DOCUMENT_PART,
                    element_path=_element_path(element, document_root),
                    view=marker_view,
                    char_start=0,
                    char_end=len(text),
                ),
                paragraph=None,
                baseline_start=None,
                baseline_end=None,
                nested=nested,
                text_sha256=_sha256(text),
            )
        )

    comments, comment_problems = _collect_comments(
        comments_root, markers_by_comment, document_root, baseline_paragraphs
    )
    problems.extend(comment_problems)

    if any(revision.nested for revision in revisions):
        problems.append(
            ExtractionProblem(
                code="docx_nested_revision",
                detail=(
                    "the document holds a revision inside another revision. The "
                    "inner one is reported separately with its own path and text; "
                    "the outer one decides what the two views contain, which is "
                    "what accepting and rejecting mean."
                ),
            )
        )

    return RevisionDocument(
        revisions=tuple(revisions),
        comments=tuple(comments),
        accepted_text="\n".join(accepted_paragraphs),
        rejected_text="\n".join(baseline_paragraphs),
        paragraphs=tuple(accepted_paragraphs),
        baseline_paragraphs=tuple(baseline_paragraphs),
        problems=tuple(problems),
    )


class _BytesReader:
    """A file-like object over a bytes buffer, for :mod:`zipfile`.

    ``zipfile`` accepts a file-like object, and the bytes are already in
    memory, so a reader that hands them over is both simpler and safer
    than writing the archive to disk to read it back.
    """

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._position = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._position
        chunk = self._data[self._position : self._position + size]
        self._position += len(chunk)
        return chunk

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._position = offset
        elif whence == 1:
            self._position += offset
        else:
            self._position = len(self._data) + offset
        return self._position

    def tell(self) -> int:
        return self._position

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True


def _collect_comments(
    comments_root: ElementTree.Element | None,
    markers: dict[str, list[tuple[str, int, int, str]]],
    document_root: ElementTree.Element,
    baseline_paragraphs: list[str],
) -> tuple[list[CommentEvent], list[ExtractionProblem]]:
    """The comments, with their anchors or the reason there is none."""
    problems: list[ExtractionProblem] = []
    events: list[CommentEvent] = []

    if comments_root is None:
        if markers:
            problems.append(
                ExtractionProblem(
                    code="docx_comments_part_absent",
                    detail=(
                        "the document's body refers to comments but the archive has no "
                        "word/comments.xml. The references are reported as unknown "
                        "comments rather than as a document with no comments."
                    ),
                )
            )
        return events, problems

    for comment in comments_root.iter(_TAG["comment"]):
        comment_id = comment.get(f"{{{W}}}id", "")
        text = _comment_body(comment)
        element_path = _element_path(comment, comments_root)
        locator = DocxLocator(
            part=_COMMENTS_PART,
            element_path=element_path,
            view="accepted",
            char_start=0,
            char_end=len(text),
        )
        anchor, anchor_problems = _anchor_for(
            comment_id, markers, document_root, text, baseline_paragraphs
        )
        problems.extend(anchor_problems)
        events.append(
            CommentEvent(
                comment_id=comment_id,
                author=comment.get(f"{{{W}}}author"),
                date=_parse_date(comment.get(f"{{{W}}}date")),
                text=text,
                locator=locator,
                anchor=anchor,
                text_sha256=_sha256(text),
            )
        )

    # A reference to a comment that does not exist is a defect in the file
    # and is reported, not ignored: the reference is real and it points at
    # nothing.
    known = {event.comment_id for event in events}
    for comment_id in markers:
        if comment_id not in known:
            problems.append(
                ExtractionProblem(
                    code="docx_comment_reference_unknown",
                    detail=(
                        f"the body refers to comment {comment_id!r} and the archive "
                        f"holds no such comment. The reference is reported and the "
                        f"comment is not invented."
                    ),
                    location=f"comment {comment_id}",
                )
            )
    return events, problems


def _anchored_text(
    baseline_paragraphs: list[str],
    paragraph: int | None,
    start: int | None,
    end: int | None,
) -> str:
    """The baseline text a comment's range covers.

    **Cut from the same baseline the offsets are into**, so the offset and
    the text agree by construction and a reader can check that they do.

    **Empty when there is no single paragraph the offsets name.** A range
    that starts in one paragraph and ends in another has two offsets into
    two different texts, and no slice is the text the comment covers. The
    reader reports that case as an unknown anchor with its reason named,
    and does not call this with the borrowed end offset at all.
    """
    if paragraph is None or start is None or end is None:
        return ""
    if paragraph < 0 or paragraph >= len(baseline_paragraphs):
        return ""
    baseline = baseline_paragraphs[paragraph]
    if start < 0 or end < start or end > len(baseline):
        return ""
    return baseline[start:end]


def _anchor_for(
    comment_id: str,
    markers: dict[str, list[tuple[str, int, int, str]]],
    document_root: ElementTree.Element,
    comment_text: str,
    baseline_paragraphs: list[str],
) -> tuple[CommentAnchor, list[ExtractionProblem]]:
    """A comment's anchor, or the reason it does not have one.

    **Five ways a comment can fail to have a nameable anchor, and each is
    named.** A range that carries no markers, a range that ends without
    starting, a range that starts without ending, a range whose two
    markers sit in different paragraphs, and a range that closes where it
    opens. They are five different facts, and a reader that reports them
    as one has thrown away the difference between a damaged document and
    an unusual one.

    **An address that names no text is not a text.** The fourth case is the
    one that looks resolvable and is not: Word writes a comment covering
    several paragraphs with its start marker in the first and its end marker
    in the last, and **each marker carries an offset within its own
    paragraph**. The two offsets are therefore offsets into two different
    texts, and the pair names no range that exists. Reporting the start
    offset with the end offset borrowed from the other paragraph would
    store an address that resolves to text nobody wrote — so the anchor is
    reported as unknown, with the reason named, and the paragraph the range
    starts in is kept.

    **And the fifth is the claim nothing backs.** A range that closes
    where it opens covers a *position* — a reviewer commenting on the
    place, not on words. Reporting it as ``resolved`` would store the
    empty string as the text the comment covers and hash that emptiness
    into an integrity value any check reading only "is there a digest"
    accepts, so the anchor is reported as unknown with its reason named,
    the way the four genuinely damaged shapes above are.
    """
    problems: list[ExtractionProblem] = []
    entries = markers.get(comment_id, [])
    starts = [e for e in entries if e[0] == "start"]
    ends = [e for e in entries if e[0] == "end"]

    if not starts and not ends:
        problems.append(
            ExtractionProblem(
                code="docx_comment_unanchored",
                detail=(
                    f"comment {comment_id!r} has no range markers, so the text it "
                    f"covers cannot be located. The comment's body, author and date "
                    f"are reported; the anchor is reported as unknown rather than "
                    f"guessed at the paragraph."
                ),
                location=f"comment {comment_id}",
            )
        )
        return (
            CommentAnchor(
                status="unknown",
                reason="the comment carries no range markers",
                paragraph=None,
                start=None,
                end=None,
                text="",
            ),
            problems,
        )

    if not starts:
        problems.append(
            ExtractionProblem(
                code="docx_comment_range_unopened",
                detail=(
                    f"comment {comment_id!r} has a range that ends but never starts. "
                    f"The comment is reported with its body and an unknown anchor."
                ),
                location=f"comment {comment_id}",
            )
        )
        return (
            CommentAnchor(
                status="unknown",
                reason="the comment's range ends but never starts",
                paragraph=ends[0][1],
                start=None,
                end=None,
                text="",
            ),
            problems,
        )

    if not ends:
        problems.append(
            ExtractionProblem(
                code="docx_comment_range_unclosed",
                detail=(
                    f"comment {comment_id!r} has a range that starts but never ends. "
                    f"The comment is reported with its body and an unknown anchor."
                ),
                location=f"comment {comment_id}",
            )
        )
        return (
            CommentAnchor(
                status="unknown",
                reason="the comment's range starts but never ends",
                paragraph=starts[0][1],
                start=None,
                end=None,
                text="",
            ),
            problems,
        )

    start_entry = starts[0]
    end_entry = ends[0]
    if start_entry[1] != end_entry[1]:
        # **The range spans two paragraphs.** The end offset belongs to the
        # paragraph the range ends in, so pairing it with the start
        # paragraph's offset names a range that cannot exist. The anchor is
        # reported as unknown, and the paragraph the range *starts* in is
        # kept, because that much is a fact about the file.
        problems.append(
            ExtractionProblem(
                code="docx_comment_range_spans_paragraphs",
                detail=(
                    f"comment {comment_id!r} has a range that starts in one paragraph "
                    f"and ends in another. The anchor is reported against the "
                    f"paragraph it starts in, and the reason is named."
                ),
                location=f"comment {comment_id}",
            )
        )
        return (
            CommentAnchor(
                status="unknown",
                reason="the comment's range spans two paragraphs",
                paragraph=start_entry[1],
                start=None,
                end=None,
                text="",
            ),
            problems,
        )

    if start_entry[2] == end_entry[2]:
        # **A range that closes where it opens is a position, not a
        # passage.** Word writes this when a reviewer comments on *the
        # place* rather than on words — an insertion point, a spot between
        # runs. The paragraph is a fact the file records and is kept, but
        # ``resolved`` would claim a passage was found and no passage
        # exists: the stored slice would be the empty string, hashed into
        # an integrity value that any check reading only "is there a
        # digest" accepts. A comment on a place is still a comment, so it
        # is reported with its body and the reason it holds no words.
        problems.append(
            ExtractionProblem(
                code="docx_comment_position_anchor",
                detail=(
                    f"comment {comment_id!r} covers a position, not a passage: its "
                    f"range closes where it opens. The paragraph the comment sits "
                    f"in is reported, and the anchor carries no text because the "
                    f"file records no words there."
                ),
                location=f"comment {comment_id}",
            )
        )
        return (
            CommentAnchor(
                status="unknown",
                reason="the comment's range is a position, not a passage of text",
                paragraph=start_entry[1],
                start=None,
                end=None,
                text="",
            ),
            problems,
        )

    return (
        CommentAnchor(
            status="resolved",
            reason=None,
            paragraph=start_entry[1],
            start=start_entry[2],
            end=end_entry[2],
            # **The text is cut only when one paragraph holds both ends.**
            # A range that spans paragraphs has two offsets into two
            # different texts, and no single slice is the text the comment
            # covers — so such a range is not a resolved anchor at all, and
            # it is reported above with its reason.
            text=_anchored_text(
                baseline_paragraphs,
                start_entry[1],
                start_entry[2],
                end_entry[2],
            ),
        ),
        problems,
    )


@register
class DocxAdapter:
    """One unit per paragraph, one per revision, one per comment.

    **The revisions and the comments are units, not a side-channel.** They
    are citable text: the deleted text and the advisor's remark are both
    statements the evidence ledger must be able to check against. A reader
    that reports them without giving them an address would make them
    unreferenceable, which is the same defect as not reporting them.
    """

    kind = SourceKind.DOCX

    def extract(self, data: bytes) -> ExtractionResult:
        document = read_document(data)
        units: list[ExtractedUnit] = []

        for index, paragraph in enumerate(document.paragraphs):
            locator = DocxLocator(
                part=_DOCUMENT_PART,
                element_path=_paragraph_path(index, document),
                view="accepted",
                char_start=0,
                char_end=len(paragraph),
            )
            units.append(ExtractedUnit(locator=locator, text=paragraph))

        for revision in document.revisions:
            units.append(ExtractedUnit(locator=revision.locator, text=revision.text))

        for comment in document.comments:
            units.append(ExtractedUnit(locator=comment.locator, text=comment.text))

        return ExtractionResult(units=tuple(units), problems=document.problems)

    def libraries(self) -> dict[str, str]:
        """No dependency beyond the standard library.

        The reader uses :mod:`zipfile` and :mod:`xml.etree`, both of which
        ship with Python. **Adding a DOCX library would add exactly the
        behaviour this reader exists to avoid**: one that reads ``w:t``
        only, and therefore cannot see a deletion.
        """
        return {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        return (sys.modules[__name__],)


def _paragraph_path(index: int, document: RevisionDocument) -> str:
    """The path of a paragraph, derived from the document's own numbering.

    The reader does not keep the paragraph elements around, so the path is
    rebuilt from the index. That is sound because the paragraphs are
    numbered in document order and the path's step for a paragraph is its
    index among the body's paragraphs.
    """
    return f"/w:document/w:body/w:p[{index + 1}]"
