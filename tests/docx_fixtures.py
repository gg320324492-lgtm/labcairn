"""Synthetic DOCX fixtures with tracked changes and comments, and their gold.

This module builds the test corpus for LC-P2-07 (DOCX revision fidelity). It
exists because there is no public corpus that has what this phase needs: a
Word document carrying *revisions* — insertions, deletions, moves, comments
with anchors, several authors, and the awkward cases where metadata is
missing or an anchor does not pair.

**Why these are generated rather than collected.** Every fixture here is
synthetic, so it can carry an exact expected answer. A real advisor's
manuscript would tell us what happens, but not what *should* happen, and a
parser that agrees with a real document is not thereby correct. The gold
here is written by the same code that writes the XML, so a disagreement
between the two is a disagreement about the fixture, not about the parser.

**Why the XML is written directly.** `python-docx` cannot create a tracked
change: it has no model for `w:ins` or `w:del`, and its `Run.text` reads
`w:t` only — which is exactly why it cannot see a deletion (see
`docs/research/upstream-study/docling.md` for the same effect in Docling).
So the parts are assembled as XML text and zipped, which is also how the
files are read back.

**Why positions are given as text, not as offsets.** A revision names the
baseline text it replaces (``anchor_text``) or the text it follows
(``after_text``), and the character range is *derived* from that. The first
version of this corpus carried hand-written offsets, and they were wrong:
they pointed at a different part of the sentence than the revision's own
text, so the fixture's accepted and rejected views were both nonsense — and
the corpus's own test caught it. A position computed from the thing it
describes cannot drift away from it.

**What is *not* here.** These are not documents produced by Word. They are
documents that are *well-formed enough* to exercise a parser, and they
deliberately include malformed cases (an unpaired comment marker, a
revision with no author, a comment with no range). A real Word corpus would
add the messy parts this cannot reach: run-splitting inside a revision,
`w:moveFrom`/`w:moveTo` pairs with their own name ranges, revision ids that
Word renumbers on save, `w14:paraId` collisions, and comments in parts other
than `word/document.xml`. Those are named in the corpus module's
`KNOWN_GAPS` and are the pilot corpus's job, not this one's.

Every fixture is written to a directory the caller names, and every one is
read-only afterwards: the tests assert the bytes do not change.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The WordprocessingML namespace. Every element below is in it.
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: The relationships namespace. A real Word document declares it on
#: ``w:document``, and a reader that resolves relationships by namespace —
#: docx2python's ``merge_runs`` does, and raises ``KeyError: 'r'`` without
#: it — needs it to be there. The first version of this corpus omitted it
#: and the omission was found by that library failing on the fixture.
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: The parts a `.docx` must carry for Word to open it. The fixture writer
#: emits exactly these, so a missing one is a fixture bug rather than a
#: parser question.
#
#: The content types are assembled from fragments rather than written as one
#: long literal, because the content-type URLs are longer than the line
#: limit and a wrapped URL inside an XML attribute would change the file.
_WML = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    '  <Default Extension="rels" ContentType="'
    "application/vnd.openxmlformats-package.relationships+xml"
    '"/>\n'
    '  <Default Extension="xml" ContentType="application/xml"/>\n'
    f'  <Override PartName="/word/document.xml" ContentType="{_WML}.document.main+xml"/>\n'
    f'  <Override PartName="/word/comments.xml" ContentType="{_WML}.comments+xml"/>\n'
    f'  <Override PartName="/word/styles.xml" ContentType="{_WML}.styles+xml"/>\n'
    "</Types>\n"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    '  <Relationship Id="rId1" Type="'
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    '" Target="word/document.xml"/>\n'
    "</Relationships>\n"
)

_DOCUMENT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    '  <Relationship Id="rId1" Type="'
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    '" Target="styles.xml"/>\n'
    '  <Relationship Id="rId2" Type="'
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    '" Target="comments.xml"/>\n'
    "</Relationships>\n"
)

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
</w:styles>
"""

_XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

#: The timestamp every archive entry carries.
#:
#: A ZIP entry records the moment it was written, so an archive written
#: twice in the same second is reproducible and an archive written twice in
#: different seconds is not. The fixed value is the ZIP epoch (1980-01-01),
#: which is the earliest a ZIP can express — chosen so that the value is
#: obviously a constant rather than a plausible-looking time.
_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _esc(text: str) -> str:
    """Escape text for an XML text node.

    Only the three characters that can break a text node are escaped. A
    ``&`` in a manuscript sentence is common enough that mishandling it
    would make the fixture wrong in a way a parser might "correct", so it
    is escaped here rather than assumed away.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass(frozen=True)
class Revision:
    """One tracked change, as the fixture records it.

    The fields mirror what the XML carries, so the gold and the file cannot
    drift apart by accident: the writer emits ``author`` and ``date`` onto
    the element exactly as given here, including ``None``.

    **The position is computed, not written down.** A revision names the
    baseline text it affects by ``anchor_text`` — the substring it replaces
    — or the text it follows by ``after_text``, and the character range is
    derived from that. The alternative, hand-written offsets, is what the
    first version of this corpus did, and it was wrong: the offsets pointed
    at a different part of the sentence than the revision's own text, so
    the accepted and rejected views of the fixture were both nonsense. The
    corpus's test caught it, which is the reason the derivation is here.
    """

    kind: str  # "ins" | "del" | "moveFrom" | "moveTo"
    text: str
    author: str | None
    date: str | None
    element_id: str
    #: The paragraph this revision lives in, by index into the body's
    #: paragraph list.
    paragraph: int
    #: The baseline substring this revision replaces. Empty for an
    #: insertion, which adds text at a point rather than replacing any.
    anchor_text: str = ""
    #: For an insertion, the baseline text the insertion follows — the
    #: point it is inserted at. Empty when the insertion is at the start
    #: of the paragraph.
    after_text: str = ""
    #: For the deleted text, the fact that it lives in ``w:delText`` rather
    #: than ``w:t``. Word requires this, and a parser that reads only
    #: ``w:t`` therefore loses every deletion.
    note: str = ""


@dataclass(frozen=True)
class Comment:
    """One comment, as the fixture records it.

    Like :class:`Revision`, the range is given as the **text** the comment
    covers rather than as offsets, and the offsets are derived.
    """

    comment_id: str
    author: str
    date: str
    text: str
    paragraph: int
    #: The baseline text the comment's range covers. Empty for a comment
    #: anchored at a point rather than on text.
    anchor_text: str = ""
    #: The baseline text the comment follows, used when the anchor is a
    #: point rather than a range.
    after_text: str = ""
    #: ``"both"`` (the normal case), ``"start_only"``, ``"end_only"`` or
    #: ``"none"``. The last three are the malformed cases, and they exist
    #: because the upstream study found a library that drops the entire
    #: comment set when the counts do not match.
    anchor: str = "both"


@dataclass(frozen=True)
class Fixture:
    """A document, its revisions and comments, and the gold about them."""

    name: str
    paragraphs: tuple[str, ...]
    revisions: tuple[Revision, ...] = ()
    comments: tuple[Comment, ...] = ()
    #: Free-form note about what this fixture is for. Carried into the gold
    #: file so a reader of the corpus knows why a case exists.
    purpose: str = ""
    #: Facts a parser cannot derive from the XML and that the gold must
    #: therefore state rather than imply — for example "this document has a
    #: comment with no anchor, and the correct answer is UNKNOWN".
    expectations: tuple[str, ...] = field(default_factory=tuple)


def _locate(baseline: str, anchor_text: str, after_text: str) -> tuple[int, int]:
    """Find the character range in ``baseline`` that a revision or comment covers.

    The range is the occurrence of ``anchor_text`` — an empty one means the
    range is a **point**, placed after ``after_text``.

    The search is for the **first** occurrence, and the corpus's test
    re-derives every range from the written file, so an ambiguous anchor
    would be caught rather than silently resolved differently in two
    places.
    """
    if anchor_text:
        index = baseline.find(anchor_text)
        if index < 0:
            raise ValueError(
                f"anchor {anchor_text!r} does not occur in the baseline "
                f"{baseline!r}; the fixture's text and its anchor disagree"
            )
        return index, index + len(anchor_text)
    if after_text:
        index = baseline.find(after_text)
        if index < 0:
            raise ValueError(
                f"after-text {after_text!r} does not occur in the baseline "
                f"{baseline!r}; the fixture's text and its anchor disagree"
            )
        return index + len(after_text), index + len(after_text)
    return 0, 0


def revision_range(fixture: Fixture, revision: Revision) -> tuple[int, int]:
    """The character range a revision covers, derived from its text."""
    baseline = fixture.paragraphs[revision.paragraph]
    return _locate(baseline, revision.anchor_text, revision.after_text)


def comment_range(fixture: Fixture, comment: Comment) -> tuple[int, int]:
    """The character range a comment covers, derived from its text."""
    baseline = fixture.paragraphs[comment.paragraph]
    return _locate(baseline, comment.anchor_text, comment.after_text)


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


def _del_run(text: str) -> str:
    """A deleted run.

    The text lives in ``w:delText``. This is the single most consequential
    detail in the whole fixture set: a parser that reads ``w:t`` sees a
    deletion as an empty run, and the text the advisor deleted never
    reaches the output.
    """
    return f'<w:r><w:delText xml:space="preserve">{_esc(text)}</w:delText></w:r>'


def _revision_xml(rev: Revision) -> str:
    """One ``w:ins`` / ``w:del`` / move element.

    ``w:author`` and ``w:date`` are written **only when they are not
    None**. A revision with no author is an element with no ``w:author``
    attribute at all, which is what Word writes — and it is why "missing
    author" and "author with an empty name" are different cases.
    """
    attrs = [f'w:id="{rev.element_id}"']
    if rev.author is not None:
        attrs.append(f'w:author="{_esc(rev.author)}"')
    if rev.date is not None:
        attrs.append(f'w:date="{_esc(rev.date)}"')
    attr_text = " ".join(attrs)
    # A deletion's text lives in w:delText and everything else's in w:t.
    body = _del_run(rev.text) if rev.kind == "del" else _run(rev.text)
    return f"<w:{rev.kind} {attr_text}>{body}</w:{rev.kind}>"


def _comment_xml(comment: Comment) -> str:
    return (
        f'<w:comment w:id="{comment.comment_id}" '
        f'w:author="{_esc(comment.author)}" '
        f'w:date="{_esc(comment.date)}">'
        f'<w:p><w:r><w:t xml:space="preserve">{_esc(comment.text)}</w:t></w:r></w:p>'
        f"</w:comment>"
    )


def _build_document(fixture: Fixture) -> str:
    """Assemble ``word/document.xml``.

    Each paragraph is emitted with its revisions and comment markers woven
    into it.

    **How a revision is placed.** A paragraph has a *baseline* text — the
    text as it would read if every revision were rejected. A revision's
    range is the baseline text it replaces:

    - a ``del`` replaces the baseline's range with the deleted text, so the
      **rejected** view shows the deleted text and the **accepted** view
      shows the baseline without it;
    - an ``ins`` adds its text at a point, so the **accepted** view shows
      the inserted text and the **rejected** view shows the baseline
      without it.

    This is the structure Word writes — the revision elements sit *inside*
    the run sequence at the position they affect, not collected at the front
    of the paragraph — and it is the structure a reader has to cope with.
    Emitting them at the front would produce a file that pandoc's
    ``--track-changes`` modes answer wrongly, which is exactly how this
    corpus found its own first bug.
    """
    revisions_by_para: dict[int, list[Revision]] = {}
    for rev in fixture.revisions:
        revisions_by_para.setdefault(rev.paragraph, []).append(rev)
    comments_by_para: dict[int, list[Comment]] = {}
    for comment in fixture.comments:
        comments_by_para.setdefault(comment.paragraph, []).append(comment)

    body_parts: list[str] = []
    for index, baseline in enumerate(fixture.paragraphs):
        revisions = sorted(
            revisions_by_para.get(index, []), key=lambda r: revision_range(fixture, r)
        )
        comments = comments_by_para.get(index, [])
        ranges = {rev.element_id: revision_range(fixture, rev) for rev in revisions}
        comment_ranges = {c.comment_id: comment_range(fixture, c) for c in comments}

        # Split the baseline at the revision boundaries, so each piece of
        # baseline text is emitted once and the revisions sit between the
        # pieces they affect.
        pieces: list[str] = []
        emitted_up_to = 0
        for rev in revisions:
            start, end = ranges[rev.element_id]
            # The baseline text between the previous revision and this one.
            if start > emitted_up_to:
                pieces.append(_run(baseline[emitted_up_to:start]))
            # Comment markers that begin at this revision open before it.
            for comment in comments:
                c_start, c_end = comment_ranges[comment.comment_id]
                if comment.anchor in ("both", "start_only") and c_start == start:
                    pieces.append(f'<w:commentRangeStart w:id="{comment.comment_id}"/>')
            pieces.append(_revision_xml(rev))
            # Comment markers that end at this revision close after it.
            for comment in comments:
                c_start, c_end = comment_ranges[comment.comment_id]
                if comment.anchor == "both" and c_end == end:
                    pieces.append(f'<w:commentRangeEnd w:id="{comment.comment_id}"/>')
            # A deletion *replaces* the baseline range it covers, so the
            # baseline text is not emitted again. An insertion adds text at
            # a point, and its range is empty, so the same holds.
            emitted_up_to = max(emitted_up_to, end)
        tail_start = emitted_up_to
        if tail_start < len(baseline):
            # A comment anchored on text that carries no revision opens and
            # closes around that text.
            for comment in comments:
                c_start, c_end = comment_ranges[comment.comment_id]
                if comment.anchor in ("both", "start_only") and c_start >= tail_start:
                    pieces.append(f'<w:commentRangeStart w:id="{comment.comment_id}"/>')
            pieces.append(_run(baseline[tail_start:]))
            for comment in comments:
                c_start, c_end = comment_ranges[comment.comment_id]
                if comment.anchor == "both" and c_end >= tail_start:
                    pieces.append(f'<w:commentRangeEnd w:id="{comment.comment_id}"/>')

        for comment in comments:
            if comment.anchor in ("both", "end_only"):
                pieces.append(
                    f'<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
                    f'<w:commentReference w:id="{comment.comment_id}"/></w:r>'
                )
            if comment.anchor == "end_only":
                # A range that ends without ever having started.
                pieces.append(f'<w:commentRangeEnd w:id="{comment.comment_id}"/>')

        body_parts.append(f"<w:p>{''.join(pieces)}</w:p>")

    document = (
        f'{_XML_HEADER}<w:document xmlns:w="{W}" xmlns:r="{_R}">'
        f"<w:body>{''.join(body_parts)}</w:body></w:document>"
    )
    return document


def _build_comments(fixture: Fixture) -> str:
    comments = "".join(_comment_xml(c) for c in fixture.comments)
    return f'{_XML_HEADER}<w:comments xmlns:w="{W}">{comments}</w:comments>'


def write_fixture(fixture: Fixture, directory: Path) -> Path:
    """Write one fixture to ``directory`` and return its path.

    The file is written once and never rewritten. A parser that mutates it
    is caught by the tests, which compare the bytes before and after.

    **The archive is byte-reproducible.** A ZIP entry carries the time it
    was written, so two writes of the same fixture a second apart would
    differ in their bytes — and a fixture whose bytes move between runs
    makes every hash-based check meaningless, exactly as ADR-0009 records
    for extracted text. Every entry therefore carries a fixed timestamp,
    and the entries are written in a fixed order. **The maker's system is
    pinned as well**: ``zipfile`` writes ``create_system = 0`` on Windows
    and ``3`` elsewhere unless it is told otherwise, so the default makes
    the same archive hash differently on each platform — which the gold
    manifest's ``sha256`` binding caught on its first runner run, after
    the local machine had hidden it for as long as only Windows wrote the
    corpus.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{fixture.name}.docx"
    document = _build_document(fixture)
    comments = _build_comments(fixture)
    parts = (
        ("[Content_Types].xml", _CONTENT_TYPES),
        ("_rels/.rels", _RELS),
        ("word/_rels/document.xml.rels", _DOCUMENT_RELS),
        ("word/styles.xml", _STYLES),
        ("word/document.xml", document),
        ("word/comments.xml", comments),
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts:
            info = zipfile.ZipInfo(name, date_time=_FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, content)
    return path


def gold_for(fixture: Fixture) -> dict[str, Any]:
    """The expected answer for one fixture, as data.

    The gold is deliberately *separate* from the XML: it states what a
    correct parser must report, so a parser and the fixture writer cannot
    agree by accident. Where the correct answer is "unknown", the gold says
    ``"UNKNOWN"`` rather than omitting the field — an omitted field and an
    unknown field are different, and only one of them is honest.
    """
    return {
        "name": fixture.name,
        "purpose": fixture.purpose,
        "paragraph_count": len(fixture.paragraphs),
        "paragraph_text": list(fixture.paragraphs),
        "revisions": [
            {
                "kind": rev.kind,
                "text": rev.text,
                "author": rev.author if rev.author is not None else "UNKNOWN",
                "author_present": rev.author is not None,
                "date": rev.date if rev.date is not None else "UNKNOWN",
                "date_present": rev.date is not None,
                "element_id": rev.element_id,
                "paragraph": rev.paragraph,
                "start": revision_range(fixture, rev)[0],
                "end": revision_range(fixture, rev)[1],
                "note": rev.note,
            }
            for rev in fixture.revisions
        ],
        "comments": [
            {
                "id": comment.comment_id,
                "author": comment.author,
                "date": comment.date,
                "text": comment.text,
                "paragraph": comment.paragraph,
                "start": comment_range(fixture, comment)[0],
                "end": comment_range(fixture, comment)[1],
                "anchor": comment.anchor,
                "anchor_status": "resolved" if comment.anchor == "both" else "UNKNOWN",
            }
            for comment in fixture.comments
        ],
        "expectations": list(fixture.expectations),
    }


def write_gold(fixtures: list[Fixture], directory: Path) -> Path:
    """Write the corpus's gold file and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "gold.json"
    payload = {
        "schema_version": 1,
        "note": (
            "Expected parse results for the synthetic DOCX corpus. "
            "'UNKNOWN' means the value is genuinely absent from the file and "
            "a parser must report it as unknown rather than guess."
        ),
        "fixtures": [gold_for(f) for f in fixtures],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
