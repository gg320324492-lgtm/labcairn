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
    #: The index of the paragraph the revision sits in.
    paragraph: int
    #: The revision's place in the paragraph's **rejected** (baseline) text.
    #: A deletion covers the text it removed; an insertion is a *point*,
    #: because an insertion contributes nothing to the baseline.
    baseline_start: int
    baseline_end: int
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

    The three failure modes are named rather than lumped: a range that
    starts and never ends, a range that ends and never started, and a
    comment with no range at all. They are different defects and a reader
    that reports them as one loses the distinction between a document that
    is damaged and a document that is merely unusual.
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
    #: The text the comment covers, in the baseline. Empty when unknown.
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


def _walk_paragraph(
    paragraph: ElementTree.Element,
) -> list[tuple[ElementTree.Element, str, int, int, bool]]:
    """The revisions in a paragraph, with their baseline coordinates.

    The returned tuples are ``(element, kind, baseline_start, baseline_end,
    nested)``. The baseline coordinates are the revision's place in the
    paragraph's **rejected** text: a deletion covers the text it removed,
    and an insertion is a point, because an insertion contributes nothing
    to the baseline.
    """
    found: list[tuple[ElementTree.Element, str, int, int, bool]] = []

    def walk(element: ElementTree.Element, offset: int, depth: int) -> int:
        """Walk ``element``'s children, returning the new baseline offset."""
        for child in element:
            kind = _revision_kind(child.tag)
            if kind is not None:
                start = offset
                if kind in _REJECTED_KINDS:
                    offset += len(_text_in(child, "rejected"))
                found.append((child, kind, start, offset, depth > 0))
                # The revision's own children are walked so that a revision
                # nested inside it is found too.
                offset = walk(child, offset, depth + 1)
                continue
            if child.tag == _TAG["deleted_text"]:
                offset += len(child.text or "")
                continue
            if child.tag == _TAG["text"]:
                offset += len(child.text or "")
                continue
            offset = walk(child, offset, depth)
        return offset

    walk(paragraph, 0, 0)
    return found


def _comment_markers(
    paragraph: ElementTree.Element,
) -> list[tuple[str, str, str, int]]:
    """The comment markers in a paragraph, in document order.

    The tuples are ``(kind, comment_id, element_path, baseline_offset)``,
    where ``kind`` is ``"start"``, ``"end"`` or ``"reference"``. The offset
    is the marker's place in the paragraph's rejected text, so a start and
    an end can be told apart from the text between them.
    """
    markers: list[tuple[str, str, str, int]] = []

    def walk(element: ElementTree.Element, offset: int, depth: int) -> int:
        for child in element:
            kind = _revision_kind(child.tag)
            if kind is not None:
                if kind in _REJECTED_KINDS:
                    offset += len(_text_in(child, "rejected"))
                offset = walk(child, offset, depth + 1)
                continue
            if child.tag == _TAG["deleted_text"]:
                offset += len(child.text or "")
                continue
            if child.tag == _TAG["text"]:
                offset += len(child.text or "")
                continue
            if child.tag == _TAG["comment_start"]:
                markers.append(
                    ("start", child.get(f"{{{W}}}id", ""), _element_path(child, paragraph), offset)
                )
                continue
            if child.tag == _TAG["comment_end"]:
                markers.append(
                    ("end", child.get(f"{{{W}}}id", ""), _element_path(child, paragraph), offset)
                )
                continue
            if child.tag == _TAG["comment_reference"]:
                markers.append(
                    (
                        "reference",
                        child.get(f"{{{W}}}id", ""),
                        _element_path(child, paragraph),
                        offset,
                    )
                )
                continue
            offset = walk(child, offset, depth)
        return offset

    walk(paragraph, 0, 0)
    return markers


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

    paragraphs = list(document_root.iter(_TAG["paragraph"]))
    for index, paragraph in enumerate(paragraphs):
        accepted = _text_in(paragraph, "accepted")
        baseline = _text_in(paragraph, "rejected")
        accepted_paragraphs.append(accepted)
        baseline_paragraphs.append(baseline)

        for element, kind, start, end, nested in _walk_paragraph(paragraph):
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

    markers_by_comment = _collect_markers(paragraphs, document_root)
    comments, comment_problems = _collect_comments(comments_root, markers_by_comment, document_root)
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


def _collect_markers(
    paragraphs: list[ElementTree.Element], root: ElementTree.Element
) -> dict[str, list[tuple[str, int, int, str]]]:
    """The comment markers, grouped by comment id.

    Each entry is ``(kind, paragraph, offset, element_path)``. They are
    collected for every paragraph rather than per-paragraph, because a
    comment's range may begin in one paragraph and end in another — Word
    permits it, and a reader that assumed otherwise would report a
    well-formed comment as unpaired.
    """
    grouped: dict[str, list[tuple[str, int, int, str]]] = {}
    for index, paragraph in enumerate(paragraphs):
        for kind, comment_id, path, offset in _comment_markers(paragraph):
            grouped.setdefault(comment_id, []).append((kind, index, offset, path))
    return grouped


def _collect_comments(
    comments_root: ElementTree.Element | None,
    markers: dict[str, list[tuple[str, int, int, str]]],
    document_root: ElementTree.Element,
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
        anchor, anchor_problems = _anchor_for(comment_id, markers, document_root, text)
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


def _anchor_for(
    comment_id: str,
    markers: dict[str, list[tuple[str, int, int, str]]],
    document_root: ElementTree.Element,
    comment_text: str,
) -> tuple[CommentAnchor, list[ExtractionProblem]]:
    """A comment's anchor, or the reason it does not have one."""
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
            status="resolved",
            reason=None,
            paragraph=start_entry[1],
            start=start_entry[2],
            end=end_entry[2],
            text="",
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
