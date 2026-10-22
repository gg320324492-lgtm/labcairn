"""The four renderers — the rules they obey, and the ways they could break them.

LC-P1-11's acceptance clause says *"exports are openable"*, and the task
breakdown's §4.1 turns that into a test with a specific shape: each of the
four forms is parsed back **by something that is not the writer**, and what
comes back is the model's content. That is a much stronger claim than "the
file was written", and it is what this file is about.

Four readers, four writers, and no overlap:

============  ==========================  ==========================
Form          written by                  read back by
============  ==========================  ==========================
Markdown      this repository             ``markdown-it-py``
HTML          this repository             the standard library's parser
DOCX          ``python-docx``             ``zipfile`` and ``ElementTree``
PDF           ``reportlab``               ``pdfplumber``
============  ==========================  ==========================

``markdown-it-py`` is used here as a **test-time** reader and is not a
runtime dependency: it is already in the tree, through ``rich``, at no
marginal install cost — which is the fact ADR-0013 records when it
rejects the library as a *writer*. A Markdown writer needs model →
Markdown, and this is a parser; the direction is the whole argument, and
it holds for the test as much as for the product.

Every property below is stated as something that could be broken, and the
test says how. The mutation checks are in the delivery report: each
property was broken on purpose, one at a time, and the named test is the
one that caught it.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Final
from xml.etree import ElementTree

import pdfplumber
import pytest
from markdown_it import MarkdownIt

from labcairn.analysis.chart import INTERPRETATION_MARKER as FIGURE_INTERPRETATION_MARKER
from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
)
from labcairn.evidence.states import EvidenceKind, VerificationStatus
from labcairn.reports.model import (
    ClaimBlock,
    FigureBlock,
    InterpretationBlock,
    LedgerRecordView,
    LedgerSnapshot,
    NarrativeBlock,
    ProvenanceFootnote,
    ReportClaim,
    ReportDocument,
    ReportFigure,
    ReportSection,
    ReportTable,
    TableBlock,
    UnresolvedBlock,
    UnresolvedRecord,
)
from labcairn.reports.render import (
    FIRST_PASS_NOTICE,
    INTERPRETATION_MARKER,
    REPRODUCIBILITY_NOTICE,
    PdfTextRefusedError,
    ReportRenderError,
    escape_markdown,
    render_docx,
    render_html,
    render_markdown,
    render_pdf,
    resolve,
)
from labcairn.reports.render.markdown import MARKDOWN_ESCAPE_TABLE
from labcairn.sources.locators import ComputationLocator, PdfLocator, describe_locator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

#: The bytes the report's material had when it was read.
SOURCE_HASH: str = "b" * 64
#: The bytes of the figure artefact.
FIGURE_HASH: str = "a" * 64
#: The bytes of the table artefact.
TABLE_HASH: str = "c" * 64
#: The bytes of the recipe the figure was made with.
RECIPE_HASH: str = "d" * 64

#: The number the ledger holds, at a precision a rounding step would lose.
LEDGER_VALUE: float = 4.253
#: The number the conflicted record holds, so that the two are not alike.
CONFLICT_VALUE: float = 4.9

#: The text a retrieved source can genuinely contain, and must never become
#: structure. Every part of it is a way the export could break if it were
#: written unescaped: a script tag, an ampersand, a quote, a Markdown
#: emphasis marker, a link, a heading, a bullet and an ordered list.
HOSTILE_CAPTION: str = '<script>alert("xss")</script> & "quotes" \'apos\''
HOSTILE_NARRATIVE: str = "*em* _under_ `code` [l](javascript:alert(1))"
HOSTILE_HEADING: str = "# heading & - bullet"
HOSTILE_TITLE: str = "A <b>title</b> & more"
HOSTILE_STATEMENT: str = "1. not a list"

#: The hostile values that carry a character the **HTML** must escape.
#:
#: A value with no ``<``, ``>``, ``&`` or quote in it has nothing for the
#: HTML writer to escape, and asserting that such a value is absent from
#: the file would be asserting that the report throws its own words away.
HTML_HOSTILE: tuple[str, ...] = (HOSTILE_CAPTION, HOSTILE_HEADING, HOSTILE_TITLE)

#: The hostile values that carry a character the **Markdown** must escape.
MARKDOWN_HOSTILE: tuple[str, ...] = (
    HOSTILE_CAPTION,
    HOSTILE_NARRATIVE,
    HOSTILE_HEADING,
    HOSTILE_STATEMENT,
)

#: A character outside the PDF faces' encoding, and outside the console's.
#:
#: Cyrillic is outside cp1252 — the encoding reportlab's Type 1 faces use
#: — and inside the code page this machine's console writes, so a failure
#: message that quotes it can still be read.
UNENCODABLE: str = "Ж"

#: The ways a text value can try to open an indented code block.
#:
#: A code block is opened by four spaces or a tab at the start of a line,
#: and only where a **blank line** comes before it: an indented line that
#: follows a paragraph is a continuation of that paragraph and cannot open
#: anything. So the attack is a blank line and then an indent, and the
#: indent is measured from the start of the *file* — which is why a claim,
#: written as a bullet, needs two more spaces than a paragraph does.
#:
#: The first entry is the shape the review found: a caption that carries a
#: blank line and four spaces. The rest are the same attack in the other
#: places a text value reaches the file, and with the other indent the
#: writer produces.
CODE_BLOCK_ATTACKS: Final[tuple[tuple[str, str], ...]] = (
    ("caption", "Mean yield across the five measured runs.\n\n    indented by four spaces"),
    ("caption", "Mean yield across the five measured runs.\n\n\tindented by a tab"),
    ("interpretation", "The catalyst therefore improves yield.\n\n    indented by four spaces"),
    ("interpretation", "The catalyst therefore improves yield.\n\n\tindented by a tab"),
    ("statement", "The material reports a yield of 4.253%.\n\n    indented by four spaces"),
    ("statement", "The material reports a yield of 4.253%.\n\n      indented by six spaces"),
    ("narrative", "The dataset contained 120 rows.\n\n    indented by four spaces"),
    ("title", "A first-pass report\n\n    indented by four spaces"),
    ("heading", "Findings\n\n    indented by four spaces"),
)

#: What each escapable character could open, if it were not escaped.
#:
#: One entry per character in :data:`MARKDOWN_ESCAPE_TABLE`, and the
#: strings in which that character opens something. The keys of this table
#: and the keys of the escape table are asserted to be the same set, so a
#: character removed from the escape table is caught here: a test that
#: only *walked* the escape table would walk it without the removed
#: character and see nothing wrong.
ATTACKS: dict[str, tuple[str, ...]] = {
    # A backslash before a sign is the one case where the escape
    # character itself is observable: the writer does not escape a sign
    # that belongs to a number, so a raw backslash in front of it would
    # be read as an escape and the reader would lose the backslash.
    "\\": ("a\\-4",),
    "`": ("`code`",),
    "*": ("*emphasis*",),
    "_": ("_emphasis_",),
    "[": ("[text](url)",),
    "]": ("[text](url)",),
    "!": ("![image](url)",),
    "(": ("[text](url)",),
    ")": ("[text](url)",),
    "<": ("<b>bold</b>",),
    ">": ("> quote",),
    "&": ("&amp;",),
    "#": ("# heading",),
    "+": ("+ bullet",),
    "-": ("- bullet",),
    "=": ("text\n===",),
    ".": ("1. item",),
    # A fence is what CommonMark opens with a tilde. The strikethrough
    # that GitHub's flavour opens with it is not in CommonMark, and the
    # parser this file uses does not have it — so the fence is the
    # attack a CommonMark reader can be shown opening.
    "~": ("~~~",),
}

#: The HTML elements that would mean a text value had opened something.
_STRUCTURAL_PATTERN: Final = re.compile(
    r"<(em|code|a|img|b|blockquote|ul|ol|h[1-6]|hr|pre|table|s|del)\b"
)


def _manifest() -> ReproducibilityManifest:
    """A valid reproducibility manifest for one figure."""
    output: dict[str, Any] = {"mean": LEDGER_VALUE, "n_used": 5}
    selection: dict[str, Any] = {
        "source_id": "src-1",
        "content_sha256": SOURCE_HASH,
        "columns": ["yield"],
        "rows": {"kind": "range", "start": 1, "end": 5},
        "missing": "exclude",
    }
    return ReproducibilityManifest(
        input_file=FileRef(relative_path="material/exp1.csv", content_sha256=SOURCE_HASH),
        operator="labcairn.analysis.mean@1.0.0",
        locator=ComputationLocator(
            operator_id="labcairn.analysis.mean",
            operator_version="1.0.0",
            parameters={"selection": selection, "column": "yield"},
            input_hashes=(SOURCE_HASH,),
        ),
        recipe=FileRef(relative_path="recipes/mean.py", content_sha256=RECIPE_HASH),
        output=output,
        output_sha256=canonical_digest(output),
        environment=RenderEnvironment(
            matplotlib_version="3.11.2",
            svg_hashsalt="labcairn",
            font_families=("sans-serif",),
            platform="TestOS-1.0",
        ),
    )


def _numeric_record(
    *,
    record_id: str,
    value: float,
    status: VerificationStatus,
) -> LedgerRecordView:
    """A numeric record view: a number and its declared unit, and no text."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.NUMERIC,
        value=value,
        unit="%",
        status=status,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )


def _text_record(
    *,
    record_id: str,
    text: str,
    kind: EvidenceKind = EvidenceKind.CLAIM,
    status: VerificationStatus = VerificationStatus.USER_ATTESTED,
) -> LedgerRecordView:
    """A claim record view: text, and no number."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=kind,
        text=text,
        status=status,
        anchor_ids=("anc-2",),
        source_content_hash=SOURCE_HASH,
    )


def _document(
    *,
    as_of: datetime,
    title: str = "A first-pass report",
    heading: str = "Findings",
    caption: str = "Mean yield across the five measured runs.",
    narrative: str = "The dataset contained 120 rows.",
    interpretation: str = "The catalyst therefore improves yield.",
    statement: str = "The material reports a yield of 4.253%.",
    status: VerificationStatus = VerificationStatus.VERIFIED_BY_RULE,
) -> ReportDocument:
    """A report with one of everything, so that no kind goes untested."""
    numeric = _numeric_record(record_id="rec-1", value=LEDGER_VALUE, status=status)
    textual = _text_record(record_id="rec-2", text=statement)
    conflict = _numeric_record(
        record_id="rec-9", value=CONFLICT_VALUE, status=VerificationStatus.CONFLICTED
    )
    return ReportDocument(
        title=title,
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1", "rec-2", "rec-9")),
        sections=(
            ReportSection(
                section_id="sec-1",
                heading=heading,
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    ClaimBlock(claim_id="clm-2"),
                    NarrativeBlock(text=narrative),
                    InterpretationBlock(text=interpretation),
                    FigureBlock(figure_id="fig-1"),
                    TableBlock(table_id="tab-1"),
                    UnresolvedBlock(record_id="rec-9"),
                ),
            ),
        ),
        claims=(
            ReportClaim(claim_id="clm-1", record=numeric, footnote_ids=("fn-1",)),
            ReportClaim(claim_id="clm-2", record=textual, footnote_ids=("fn-1",)),
        ),
        figures=(
            ReportFigure(
                figure_id="fig-1",
                relative_path="outputs/figures/fig-1.svg",
                content_sha256=FIGURE_HASH,
                caption=caption,
                manifest=_manifest(),
            ),
        ),
        tables=(
            ReportTable(
                table_id="tab-1",
                relative_path="outputs/tables/tab-1.csv",
                content_sha256=TABLE_HASH,
            ),
        ),
        footnotes=(
            ProvenanceFootnote(
                footnote_id="fn-1",
                source_id="src-1",
                locator=PdfLocator(page=3),
                content_sha256=SOURCE_HASH,
            ),
        ),
        unresolved_records=(
            UnresolvedRecord(
                record=conflict,
                reason="Two readings of the same cell disagree beyond the tolerance.",
            ),
        ),
    )


@pytest.fixture
def document(frozen_now: datetime) -> ReportDocument:
    """A report with one of every kind of block."""
    return _document(as_of=frozen_now)


def _a_document_with_more_than_one_of_everything(as_of: datetime) -> ReportDocument:
    """A report with more than one of every kind of thing it can carry.

    The usual fixture holds one of each, and a comparison that reads one
    of each cannot tell a form that carries the first from a form that
    carries them all: a form that dropped the second citation, or the
    second section, would still hold the first, and every comparison would
    pass. So this one holds two of each — two sections, two findings, two
    figures, two tables, two disclosures and two citations — and one
    figure and one table that no section places, because a comparison that
    never sees an unplaced artefact never sees the branch that carries it.
    """
    numeric = _numeric_record(
        record_id="rec-1", value=LEDGER_VALUE, status=VerificationStatus.VERIFIED_BY_RULE
    )
    textual = _text_record(record_id="rec-2", text="The material reports a yield of 4.253%.")
    conflict = _numeric_record(
        record_id="rec-3", value=CONFLICT_VALUE, status=VerificationStatus.CONFLICTED
    )
    unsupported = _text_record(
        record_id="rec-4",
        text="The second reading of the same cell.",
        status=VerificationStatus.UNSUPPORTED,
    )
    return ReportDocument(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1", "rec-2", "rec-3", "rec-4")),
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    NarrativeBlock(text="The dataset contained 120 rows."),
                    FigureBlock(figure_id="fig-1"),
                    TableBlock(table_id="tab-1"),
                    UnresolvedBlock(record_id="rec-3"),
                ),
            ),
            ReportSection(
                section_id="sec-2",
                heading="Discussion",
                blocks=(
                    ClaimBlock(claim_id="clm-2"),
                    InterpretationBlock(text="The catalyst therefore improves yield."),
                    FigureBlock(figure_id="fig-2"),
                    TableBlock(table_id="tab-2"),
                    UnresolvedBlock(record_id="rec-4"),
                ),
            ),
        ),
        claims=(
            ReportClaim(claim_id="clm-1", record=numeric, footnote_ids=("fn-1",)),
            ReportClaim(claim_id="clm-2", record=textual, footnote_ids=("fn-2",)),
        ),
        figures=(
            ReportFigure(
                figure_id="fig-1",
                relative_path="outputs/figures/fig-1.svg",
                content_sha256=FIGURE_HASH,
                caption="Mean yield across the five measured runs.",
                manifest=_manifest(),
            ),
            ReportFigure(
                figure_id="fig-2",
                relative_path="outputs/figures/fig-2.svg",
                content_sha256=FIGURE_HASH,
                caption="Yield in the second run.",
                manifest=_manifest(),
            ),
            ReportFigure(
                figure_id="fig-3",
                relative_path="outputs/figures/fig-3.svg",
                content_sha256=FIGURE_HASH,
                caption="A figure no section places.",
                manifest=_manifest(),
            ),
        ),
        tables=(
            ReportTable(
                table_id="tab-1",
                relative_path="outputs/tables/tab-1.csv",
                content_sha256=TABLE_HASH,
            ),
            ReportTable(
                table_id="tab-2",
                relative_path="outputs/tables/tab-2.csv",
                content_sha256=TABLE_HASH,
            ),
            ReportTable(
                table_id="tab-3",
                relative_path="outputs/tables/tab-3.csv",
                content_sha256=TABLE_HASH,
            ),
        ),
        footnotes=(
            ProvenanceFootnote(
                footnote_id="fn-1",
                source_id="src-1",
                locator=PdfLocator(page=3),
                content_sha256=SOURCE_HASH,
            ),
            ProvenanceFootnote(
                footnote_id="fn-2",
                source_id="src-2",
                locator=PdfLocator(page=7),
                content_sha256=SOURCE_HASH,
            ),
        ),
        unresolved_records=(
            UnresolvedRecord(
                record=conflict,
                reason="Two readings of the same cell disagree beyond the tolerance.",
            ),
            UnresolvedRecord(
                record=unsupported,
                reason="No record supports the second reading.",
            ),
        ),
    )


def _document_with_hostile_ids(as_of: datetime) -> ReportDocument:
    """A report whose ids carry characters that must be escaped.

    The ids are free text in the model, so a claim id, a record id, a
    citation id and a source id can each carry a character that opens
    something. A fixture whose ids are ``rec-1`` and ``fn-1`` cannot show
    that the writer escapes them, because there is nothing to escape.
    """
    record = _numeric_record(
        record_id="rec-1&2", value=LEDGER_VALUE, status=VerificationStatus.VERIFIED_BY_RULE
    )
    return ReportDocument(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1&2",)),
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(ClaimBlock(claim_id="clm-1*"),),
            ),
        ),
        claims=(ReportClaim(claim_id="clm-1*", record=record, footnote_ids=("fn-1#",)),),
        figures=(),
        tables=(),
        footnotes=(
            ProvenanceFootnote(
                footnote_id="fn-1#",
                source_id="src<1>",
                locator=PdfLocator(page=3),
                content_sha256=SOURCE_HASH,
            ),
        ),
        unresolved_records=(),
    )


@pytest.fixture
def hostile_document(frozen_now: datetime) -> ReportDocument:
    """A report whose every text value tries to become structure."""
    return _document(
        as_of=frozen_now,
        title=HOSTILE_TITLE,
        heading=HOSTILE_HEADING,
        caption=HOSTILE_CAPTION,
        narrative=HOSTILE_NARRATIVE,
        statement=HOSTILE_STATEMENT,
    )


# ---------------------------------------------------------------------------
# Readers: each form parsed back by something that is not the writer
# ---------------------------------------------------------------------------

#: The WordprocessingML namespace, for the DOCX reader.
_WML = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: The Dublin Core namespace, for the DOCX's core properties.
#:
#: ``docProps/core.xml`` holds the document's metadata, and the names in it
#: are Dublin Core's: ``dc:title``, ``dc:creator`` and ``dc:description``.
_DC = "{http://purl.org/dc/elements/1.1/}"


class _TextReader(HTMLParser):
    """The text of an HTML document, without its tags or its style sheet.

    The standard library's own parser, which is the point: the HTML form
    is read back by something that did not write it. The style sheet is
    skipped because it is the report's furniture and not its content.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._in_style = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._in_style += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self._in_style:
            self._in_style -= 1

    def handle_data(self, data: str) -> None:
        if not self._in_style:
            self._parts.append(data)

    @property
    def text(self) -> str:
        """Everything the document says, in reading order."""
        return " ".join(self._parts)


def _read_html(blob: bytes) -> str:
    """The text of an HTML file, read by the standard library's parser."""
    reader = _TextReader()
    reader.feed(blob.decode("utf-8"))
    reader.close()
    return reader.text


class _BodyReader(_TextReader):
    """The text of an HTML document's **body**, and not of its head.

    The ``<head>`` holds the document's metadata — its ``<title>`` and its
    style sheet — and the body is what a reader reads. The title is not
    lost by the skip: the body's own ``<h1>`` carries it as well, and
    :func:`_the_html_title` reads the element itself.
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_head = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag == "head":
            self._in_head += 1

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        if tag == "head" and self._in_head:
            self._in_head -= 1

    def handle_data(self, data: str) -> None:
        if not self._in_head:
            super().handle_data(data)


def _read_html_body(blob: bytes) -> str:
    """The text of an HTML file's body, read by the standard library's parser."""
    reader = _BodyReader()
    reader.feed(blob.decode("utf-8"))
    reader.close()
    return reader.text


def _the_html_title(blob: bytes) -> str:
    """The text of an HTML file's ``<title>`` element.

    Read out of the file by the same parser, because the element is the
    document's own name and the report says it twice: once in the head,
    for the reader's tab, and once in the body, for the reader's page.
    """
    titles: list[str] = []

    class _TitleReader(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self._in_title = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "title":
                self._in_title = True

        def handle_endtag(self, tag: str) -> None:
            if tag == "title":
                self._in_title = False

        def handle_data(self, data: str) -> None:
            if self._in_title:
                titles.append(data)

    reader = _TitleReader()
    reader.feed(blob.decode("utf-8"))
    reader.close()
    return " ".join(titles)


def _read_markdown(blob: bytes) -> str:
    """The text of a Markdown file, read by a Markdown parser.

    The raw file is not the report's text: the writer escapes the model's
    punctuation, so the file says ``4\\.25`` where the model says
    ``4.25``. The **rendered** file is the report, and that is what a
    reader gets.

    The parser is the **default** preset rather than the CommonMark one,
    because the default is the stricter of the two: it recognises raw
    HTML, strikethrough and tables, so a text value that opened one of
    them would be visible here rather than silently escaped by the
    parser. It is also the preset GitHub uses, which is the most likely
    reader of a Markdown report.
    """
    reader = _TextReader()
    reader.feed(MarkdownIt().render(blob.decode("utf-8")))
    reader.close()
    return reader.text


def _the_markdown_list_items(blob: bytes) -> int:
    """The number of list items the Markdown draws.

    The Markdown's list marker is the ``- `` at the head of a line, and it
    is counted by the **reader** — the parser this file already reads the
    Markdown form with — because a list item is what the reader calls it.

    A text value cannot open one: the escape table turns a leading ``-``
    into ``\\-``, so a list item in the parsed file is one the writer drew
    as a bullet, and never a line of the report's own prose.
    """
    tokens = MarkdownIt().parse(blob.decode("utf-8"))
    return sum(1 for token in tokens if token.type == "list_item_open")


def _rendered_markdown(document: ReportDocument) -> str:
    """The Markdown, rendered — the document a reader actually sees."""
    rendered: str = MarkdownIt().render(render_markdown(document).decode("utf-8"))
    return rendered


def _markdown_token_types(document: ReportDocument) -> list[str]:
    """The parser's own tokens, so that a block is seen as a block.

    The rendered HTML is what a reader sees, and a code block shows up
    there as a ``<pre>``; the tokens say the same thing in the parser's
    own words, and they say it before anything is rendered.
    """
    markdown = render_markdown(document).decode("utf-8")
    return [token.type for token in MarkdownIt().parse(markdown)]


def _an_unresolved_document(
    *,
    as_of: datetime,
    sections: tuple[ReportSection, ...],
    claims: tuple[ReportClaim, ...] = (),
    figures: tuple[ReportFigure, ...] = (),
    tables: tuple[ReportTable, ...] = (),
    footnotes: tuple[ProvenanceFootnote, ...] = (),
    unresolved_records: tuple[UnresolvedRecord, ...] = (),
) -> ReportDocument:
    """A document assembled **without** the model's own checks.

    The model resolves every id when the document is built, so a document
    that places something it does not carry cannot be made the usual
    way — and the renderer's own refusals are for exactly that
    document. ``model_construct`` is what makes one: it fills the
    fields and skips the validators, which is the point.

    A renderer that drew such a document would draw an empty space where
    a finding should be, and nothing in the tree would notice, because
    the export would be perfectly well formed. So the renderer refuses
    it **by name** instead, and these tests are how that is watched.
    """
    return ReportDocument.model_construct(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=()),
        sections=sections,
        claims=claims,
        figures=figures,
        tables=tables,
        footnotes=footnotes,
        unresolved_records=unresolved_records,
    )


def _structural_tags(html: str) -> list[str]:
    """The structural elements an HTML document carries."""
    return _STRUCTURAL_PATTERN.findall(html)


def _read_docx(blob: bytes) -> str:
    """The text of a DOCX file, read out of the package by the standard library.

    ``zipfile`` and ``ElementTree``, not ``python-docx``: the reader must
    not be the writer. A ``<w:br/>`` is a line break, and it is read as
    the whitespace it is.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    parts: list[str] = []
    for node in root.iter():
        if node.tag == f"{_WML}t":
            parts.append(node.text or "")
        elif node.tag in (f"{_WML}br", f"{_WML}tab"):
            parts.append(" ")
    return " ".join(parts)


def _the_docx_core_property(blob: bytes, name: str) -> str:
    """One of the DOCX's own core properties, read out of the package.

    ``docProps/core.xml`` is the part of an OOXML package that carries the
    document's metadata — its title, its author, its description — and it
    is what a reader's word processor shows in its title bar and in its
    properties panel. The package is read with ``zipfile`` and
    ``ElementTree``, because the reader must not be the writer.

    :param blob: the DOCX's bytes.
    :param name: the property's own name — ``title``, ``creator`` or
        ``description`` — which is how OOXML spells it.
    :returns: the property's value, or the empty string when the package
        carries the property and leaves it empty.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        core = archive.read("docProps/core.xml")
    element = ElementTree.fromstring(core).find(f"{_DC}{name}")
    assert element is not None, f"the DOCX carries no dc:{name} in its core properties"
    return element.text or ""


def _the_docx_list_items(blob: bytes) -> int:
    """The number of paragraphs the DOCX draws as entries in a list.

    A paragraph is in a list when it carries numbering itself, or when the
    style it names does: a list style carries its numbering in the style's
    own definition, so a paragraph that names one of them is in a list
    without saying so itself.

    The counting is **structural** rather than by the name of a style,
    because the shape is the renderer's business — a renderer that drew the
    findings as another kind of list would still be drawing them as a
    list, and only a renderer that drew them as prose would be caught.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        document_xml = archive.read("word/document.xml")
        styles_xml = archive.read("word/styles.xml")

    numbered = _the_numbered_style_ids(styles_xml)
    root = ElementTree.fromstring(document_xml)
    items = 0
    for paragraph in root.iter(f"{_WML}p"):
        properties = paragraph.find(f"{_WML}pPr")
        if properties is None:
            continue
        if properties.find(f"{_WML}numPr") is not None:
            items += 1
            continue
        style = properties.find(f"{_WML}pStyle")
        if style is not None and style.get(f"{_WML}val") in numbered:
            items += 1
    return items


def _the_numbered_style_ids(styles_xml: bytes) -> set[str]:
    """The ids of the styles that carry numbering of their own."""
    root = ElementTree.fromstring(styles_xml)
    numbered: set[str] = set()
    for style in root.iter(f"{_WML}style"):
        identifier = style.get(f"{_WML}styleId")
        if identifier is None:
            continue
        if style.find(f".//{_WML}numPr") is not None:
            numbered.add(identifier)
    return numbered


def _read_pdf(blob: bytes) -> str:
    """The text of a PDF file, read by a reader that did not write it."""
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


#: The marker a PDF reader prints in place of a glyph it cannot name.
_UNNAMED_GLYPH: Final = re.compile(r"\(cid:\d+\)")


def _read_pdf_body(blob: bytes) -> tuple[str, int]:
    """The text of a PDF file, and the number of list markers in it.

    reportlab draws a bullet before each of the report's list items, and
    pdfminer cannot map the bullet's glyph, so it prints ``(cid:127)``
    where the bullet is. The marker is the PDF's **list marker** — the
    role the Markdown's ``- `` and the HTML's ``<li>`` play — and those
    readers drop theirs, so this one is dropped as well.

    The number of markers is returned as well, because a dropped marker is
    a hole in the comparison: a renderer that added a glyph the reader
    cannot name would have it dropped too, and the count is what says how
    many were dropped.
    """
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return _UNNAMED_GLYPH.sub("", text), len(_UNNAMED_GLYPH.findall(text))


def _the_pdf_information(blob: bytes, name: str) -> str:
    """One entry of the PDF's document information dictionary.

    The dictionary is the part of a PDF that says what the document is —
    its title, its author, its subject — and it is what a reader's viewer
    shows in its title bar and in its properties panel. It is read with
    ``pdfplumber``, which did not write it.

    :param blob: the PDF's bytes.
    :param name: the entry's own name — ``Title``, ``Author`` or
        ``Subject`` — which is how a PDF spells it.
    :returns: the entry's value.
    """
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        information = pdf.metadata or {}
    assert name in information, f"the PDF carries no {name} in its information dictionary"
    return information[name] or ""


def _docx_entry_times(blob: bytes) -> dict[str, tuple[int, ...]]:
    """The timestamp every entry of a DOCX's ZIP carries."""
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return {info.filename: info.date_time for info in archive.infolist()}


def _pdf_creation_date(blob: bytes) -> bytes:
    """The ``/CreationDate`` a PDF carries."""
    match = re.search(rb"/CreationDate\s*\(([^)]*)\)", blob)
    assert match is not None, "the PDF carries no creation date"
    return match.group(1)


def _normalise(text: str) -> str:
    """The text with every run of whitespace collapsed to one space.

    The PDF wraps a long line, and a wrap is a newline in the extracted
    text. Comparing the report's lines against a reader's output without
    this would fail on a line that is merely long, and the failure would
    say nothing about the renderer. A wrap is at a space, so collapsing
    the whitespace puts the line back together.
    """
    return re.sub(r"\s+", " ", text).strip()


def _texts(document: ReportDocument) -> dict[str, str]:
    """The four forms, each read back by a reader that did not write it."""
    return {
        "markdown": _normalise(_read_markdown(render_markdown(document))),
        "html": _normalise(_read_html(render_html(document))),
        "docx": _normalise(_read_docx(render_docx(document))),
        "pdf": _normalise(_read_pdf(render_pdf(document))),
    }


def _the_snapshot_a_form_states(text: str) -> tuple[set[datetime], set[str]]:
    """What a form says the report is a view of: a moment, and a set of records.

    The **snapshot** is the model's statement of when the report is a view of,
    and the **records** are its statement of which records that view is made
    of. Every form draws both, and they are read the way a reader reads them
    — the text after the word the form writes — rather than taken from the
    writer, so that the comparison says what the file says and not what the
    code meant.

    The text is collapsed first, because a reader's line break is not a
    character of the report: the PDF wraps a long line, and the DOCX has no
    line breaks at all.

    The moment is read as a **moment** and not as a spelling. A form states
    it in the spelling its writer chose, and two spellings can be the same
    moment, so the comparison is about the moment the report is a view of. A
    moment that does not read back as one is named rather than raised as a
    parsing error, so that a broken form says what is wrong with it.

    :param text: the form's text, as a reader read it.
    :returns: the moments the form states, and the record ids it names.
    """
    collapsed = re.sub(r"\s+", " ", text)
    moments: set[datetime] = set()
    for stated in re.findall(r"Snapshot: (\S+)", collapsed):
        try:
            moments.add(datetime.fromisoformat(stated))
        except ValueError as error:
            raise AssertionError(
                f"the form states {stated!r} as its moment, and that does not read back as a moment"
            ) from error
    records: set[str] = set()
    for clause in re.findall(r"Records: ([^ ,]+(?:, [^ ,]+)*)", collapsed):
        records.update(part.strip() for part in clause.split(","))
    return moments, records


def _record_statements(record: LedgerRecordView) -> list[str]:
    """What the report states about a record: its quantity, or its sentence.

    A numeric record's statement is its number, drawn with ``repr`` — the
    same spelling the report draws it with — and a claim or result
    record's statement is its text.
    """
    if record.value is not None:
        return [repr(record.value)]
    if record.text is not None:
        return [record.text]
    return []


def _model_numbers(document: ReportDocument) -> set[str]:
    """The numbers the document's own content holds.

    The acceptance clause says *"numeric values agree with ledger"*, and the
    numbers a report states are the ledger's: the quantities its records
    hold, and the numbers that appear in the prose the model carries. This
    is what an export is measured against, and it is read out of the
    **document**, so that the expectation says "the model's numbers" and
    not "the numbers the renderer happened to print".

    Two things are deliberately not in here. The **figure's reproducibility
    manifest**, because it is the figure's own account of how it was made
    and an export names the artefact by path and hash rather than printing
    the manifest — a manifest that carries ``matplotlib_version:
    "3.11.2"`` would otherwise put numbers in the expectation that no
    export carries. And the **hashes**, because a content hash is hex and a
    hex digest has no decimal point in it.
    """
    texts: list[str] = [document.title]
    for section in document.sections:
        texts.append(section.heading)
        for block in section.blocks:
            if isinstance(block, (NarrativeBlock, InterpretationBlock)):
                texts.append(block.text)
    for claim in document.claims:
        texts.append(claim.claim_id)
        texts.extend(_record_statements(claim.record))
    for figure in document.figures:
        texts.extend((figure.figure_id, figure.caption, figure.relative_path))
    for table in document.tables:
        texts.extend((table.table_id, table.relative_path))
    for unresolved in document.unresolved_records:
        texts.append(unresolved.record.record_id)
        texts.extend(_record_statements(unresolved.record))
        texts.append(unresolved.reason)
    for footnote in document.footnotes:
        texts.extend((footnote.footnote_id, footnote.source_id, describe_locator(footnote.locator)))
    numbers: set[str] = set()
    for text in texts:
        numbers.update(re.findall(r"\d+\.\d+", text))
    return numbers


# ---------------------------------------------------------------------------
# What the report must say
# ---------------------------------------------------------------------------

#: The lines the report must contain, spelled out here rather than derived
#: from the renderers: a test that took its expectations from the code it
#: is checking would prove nothing.
EXPECTED_LINES: tuple[str, ...] = (
    "clm-1 — 4.253 % (verified_by_rule) [fn-1]",
    "clm-2 — The material reports a yield of 4.253%. (user_attested) [fn-1]",
    "The dataset contained 120 rows.",
    "The catalyst therefore improves yield.",
    "Figure fig-1. Mean yield across the five measured runs.",
    f"Artefact: outputs/figures/fig-1.svg (sha256 {FIGURE_HASH})",
    "Table tab-1",
    f"Artefact: outputs/tables/tab-1.csv (sha256 {TABLE_HASH})",
    f"rec-9 — {CONFLICT_VALUE!r} % — conflicted — Two readings of the same cell "
    "disagree beyond the tolerance.",
    f"fn-1 — source src-1 — pdf: page 3 — sha256 {SOURCE_HASH}",
)


# ---------------------------------------------------------------------------
# The four forms exist, and they are the four forms
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_four_forms_are_produced(document: ReportDocument) -> None:
    """Each renderer produces bytes, and produces some."""
    for rendered in (
        render_markdown(document),
        render_html(document),
        render_docx(document),
        render_pdf(document),
    ):
        assert isinstance(rendered, bytes)
        assert rendered


@pytest.mark.unit
def test_the_markdown_and_the_html_are_not_the_same_bytes(document: ReportDocument) -> None:
    """They are two forms, not one form written twice.

    A renderer that returned the Markdown's bytes for the HTML would pass
    every test that only looked for the report's content, and the reader
    would be handed a file with the wrong extension.
    """
    assert render_markdown(document) != render_html(document)


# ---------------------------------------------------------------------------
# Rule 3 — untrusted text is data
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_html_escapes_a_script_tag(hostile_document: ReportDocument) -> None:
    """A caption with a script tag in it reaches the file as text.

    The report renders retrieved text, and retrieved text is data and
    never instructions. The subject of this test is a script tag, because
    a test whose subject is escaping and whose subject is pure ASCII
    proves nothing about escaping.
    """
    html = render_html(hostile_document).decode("utf-8")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert HOSTILE_CAPTION in _normalise(_read_html(html.encode("utf-8")))


@pytest.mark.unit
def test_the_html_escapes_an_ampersand_and_a_quote(hostile_document: ReportDocument) -> None:
    """The ampersand and the quotes are escaped too.

    An unescaped ampersand is a broken entity, and an unescaped quote in
    an attribute is an attribute that ends early. Both are the failure
    the escaping exists to prevent, and neither is visible in a caption
    that is pure ASCII.
    """
    html = render_html(hostile_document).decode("utf-8")

    assert "&amp;" in html
    assert "&quot;" in html
    assert "&#x27;" in html
    assert HOSTILE_CAPTION in _normalise(_read_html(html.encode("utf-8")))


@pytest.mark.unit
def test_the_html_escapes_every_text_value_it_renders(hostile_document: ReportDocument) -> None:
    """Every place a text value can reach the file, not just the caption.

    The report has a title, headings, a narrative, a figure's caption, a
    record's statement and a disclosure's reason, and each of them is
    text that came from outside. A writer that escaped the caption and
    not the title would pass a test that only looked at the caption.
    """
    html = render_html(hostile_document).decode("utf-8")
    text = _normalise(_read_html(html.encode("utf-8")))

    for hostile in HTML_HOSTILE:
        assert hostile not in html, f"the raw text {hostile!r} reached the file"
        assert hostile in text
    for hostile in (HOSTILE_NARRATIVE, HOSTILE_STATEMENT):
        assert hostile in text


@pytest.mark.unit
def test_the_html_gives_the_text_no_elements(hostile_document: ReportDocument) -> None:
    """The text becomes text and not markup.

    A caption that said ``<b>`` must not make a bold run in the report,
    and a title that said ``<b>`` must not either. The test counts the
    elements rather than looking for one string, so a writer that escaped
    the caption and not the title is still caught.
    """
    html = render_html(hostile_document).decode("utf-8")

    assert "<b>" not in html
    assert "<i>" not in html
    assert "<a " not in html
    assert "<h3>" not in html


@pytest.mark.unit
def test_the_html_is_one_self_contained_file(document: ReportDocument) -> None:
    """No external asset, no script, and nothing that reaches the network.

    A local-first tool whose preview fetches something is not a local-first
    preview, and a reader who opens the report offline must get the whole
    of it.
    """
    html = render_html(document).decode("utf-8")

    assert "<script" not in html
    assert "src=" not in html
    assert "href=" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert "url(" not in html
    assert "@import" not in html


@pytest.mark.unit
def test_the_markdown_escapes_its_text(hostile_document: ReportDocument) -> None:
    """A caption cannot become a heading, a link or an emphasis.

    The Markdown's escape set is one table, and this is the test that
    keeps it honest: the text is one that would break the document if it
    were written raw.
    """
    markdown = render_markdown(hostile_document).decode("utf-8")

    assert "\\*em\\*" in markdown
    assert "\\_under\\_" in markdown
    assert "\\`code\\`" in markdown
    assert "\\[l\\]" in markdown
    assert "\\# heading" in markdown
    assert "1\\. not a list" in markdown


@pytest.mark.unit
def test_the_markdown_gives_the_text_no_structure(hostile_document: ReportDocument) -> None:
    """The parsed Markdown has the report's structure and no more.

    The check is on the **parsed** document, because that is what a
    reader sees: the report has headings of its own, and the hostile text
    has not opened one, and it has not become an emphasis, a link or a
    code span either.
    """
    rendered = _rendered_markdown(hostile_document)

    headings = re.findall(r"<h[1-6]>.*?</h[1-6]>", rendered, re.DOTALL)
    assert headings, "the report has no headings at all"
    assert not [heading for heading in headings if HOSTILE_HEADING in heading]
    assert "<em>" not in rendered
    assert "<a " not in rendered
    assert "<code>" not in rendered
    assert "<b>" not in rendered


@pytest.mark.unit
def test_the_markdown_escapes_the_title(hostile_document: ReportDocument) -> None:
    """The title is a text value too, and it is escaped.

    A title that reached the file raw would carry a ``<b>`` into every
    Markdown reader that allows raw HTML, and the report's own first
    heading is the last place to look for an unescaped tag.
    """
    markdown = render_markdown(hostile_document).decode("utf-8")

    assert "A \\<b\\>title\\</b\\> \\& more" in markdown
    assert HOSTILE_TITLE not in markdown


@pytest.mark.unit
def test_the_markdown_escapes_the_ids_it_carries(frozen_now: datetime) -> None:
    """The ids are text values too.

    A claim id, a record id, a citation id and a source id are free text
    in the model, and a fixture whose ids are ``rec-1`` and ``fn-1``
    cannot show that the writer escapes them — there is nothing in them
    to escape.
    """
    document = _document_with_hostile_ids(frozen_now)
    markdown = render_markdown(document).decode("utf-8")

    assert "clm-1\\*" in markdown
    assert "rec-1\\&2" in markdown
    assert "fn-1\\#" in markdown
    assert "src\\<1\\>" in markdown

    text = _normalise(_read_markdown(markdown.encode("utf-8")))
    assert "clm-1*" in text
    assert "rec-1&2" in text
    assert "fn-1#" in text
    assert "src<1>" in text


@pytest.mark.unit
def test_the_html_escapes_the_ids_it_carries(frozen_now: datetime) -> None:
    """And the HTML escapes them too."""
    document = _document_with_hostile_ids(frozen_now)
    html = render_html(document).decode("utf-8")

    assert "rec-1&amp;2" in html
    assert "src&lt;1&gt;" in html
    assert "rec-1&2" not in html


@pytest.mark.unit
def test_the_markdown_carries_the_text_back_when_it_is_parsed(
    hostile_document: ReportDocument,
) -> None:
    """The escaping is invisible to the reader.

    The text is escaped so that it cannot become structure, and the
    reader must get the text back exactly: the escaping is a fact about
    the file's bytes, not about the report.
    """
    text = _normalise(_read_markdown(render_markdown(hostile_document)))

    for hostile in MARKDOWN_HOSTILE:
        assert hostile in text


@pytest.mark.unit
def test_the_markdown_escape_table_escapes_every_character_in_it() -> None:
    """The table is the rule, and the rule covers the whole table.

    A character added to the table and not to the writer would be a
    character the writer does not escape, and the test walks the table
    rather than a list of examples.
    """
    for character in MARKDOWN_ESCAPE_TABLE:
        assert escape_markdown(character) == "\\" + character, (
            f"{character!r} is in the escape table and is not escaped"
        )


@pytest.mark.unit
def test_the_escape_table_and_the_attacks_agree() -> None:
    """The table's **set** is pinned, not only its behaviour.

    A test that walks the escape table cannot catch a character *removed*
    from it: the removed character is simply not walked, and nothing
    fails. The attacks table names every character the escape table is
    supposed to hold, and the two sets are asserted to be the same — so
    ``~``, ``!``, ``=`` and ``\\`` are each pinned, and so is any
    character a future change adds.
    """
    assert set(ATTACKS) == set(MARKDOWN_ESCAPE_TABLE)


@pytest.mark.integration
def test_no_escaped_character_can_open_structure(frozen_now: datetime) -> None:
    """Each character in the table is shown to open nothing.

    The table says which characters can open a span or a block; this
    test says it, one character at a time, by putting the character into
    a narrative — the one place the writer does not prefix — and checking
    that the parsed Markdown has no emphasis, no code span, no link, no
    image, no heading, no quote, no list and no rule where the
    baseline has none.

    The text must also come back **verbatim**: a character that was
    swallowed rather than escaped is a character the reader never saw.

    A character whose attack needs a partner — the image's ``!`` needs
    the link's ``[`` — cannot be shown opening anything on its own,
    because the escaping is layered and the partner is still escaped.
    Those are pinned by the key-set test above rather than by this one.
    """
    baseline = _structural_tags(_rendered_markdown(_document(as_of=frozen_now)))
    for character, attacks in ATTACKS.items():
        for attack in attacks:
            document = _document(as_of=frozen_now, narrative=attack)
            rendered = _rendered_markdown(document)
            assert _structural_tags(rendered) == baseline, (
                f"{character!r} opened structure with {attack!r}"
            )
            assert _normalise(attack) in _normalise(_read_markdown(rendered.encode("utf-8"))), (
                f"{character!r} swallowed {attack!r} instead of escaping it"
            )


@pytest.mark.unit
def test_a_narrative_that_starts_with_four_spaces_is_not_a_code_block(
    frozen_now: datetime,
) -> None:
    """The prose stays prose.

    CommonMark opens an indented code block with four spaces at the start
    of a line, and a narrative is written at the start of a line. The
    leading indent is written as a character reference, so the reader
    sees the same spaces and the paragraph stays a paragraph — the
    export's structure is a function of the model and not of where the
    text happens to begin.
    """
    document = _document(as_of=frozen_now, narrative="    four spaces then prose")
    markdown = render_markdown(document).decode("utf-8")
    rendered = _rendered_markdown(document)

    assert "&#32;&#32;&#32;&#32;four spaces then prose" in markdown
    assert "code_block" not in rendered
    assert "<pre>" not in rendered
    assert "four spaces then prose" in _normalise(_read_markdown(markdown.encode("utf-8")))


@pytest.mark.integration
def test_no_text_value_can_open_an_indented_code_block(frozen_now: datetime) -> None:
    """No text value, in any of the places the writer puts one.

    The escape table covers the punctuation that can open a span or a
    block, and **whitespace is not punctuation**: CommonMark opens an
    indented code block with four spaces or a tab at the start of a line,
    and only where a blank line comes before it. A text value that carries
    a line break therefore carries a line of its own into the file, and
    the writer's prefix — "Figure 1. ", "- " — protects only the **first**
    line of the value, not the ones after it.

    So the attack is a blank line and then an indent, and it is tried in
    every place a text value reaches the file: the caption, the
    interpretation, the claim's own words, the narrative, the title and
    the heading. The claim is written as a bullet, so its indent is
    measured from the bullet and two more spaces are needed; the attack
    carries six.

    The property is the **reader's**: the Markdown is parsed back, and the
    parsed document holds no code block. A writer that escaped the
    punctuation and left the whitespace alone would pass a test that only
    looked at the table.
    """
    baseline = _structural_tags(_rendered_markdown(_document(as_of=frozen_now)))

    for field, attack in CODE_BLOCK_ATTACKS:
        overrides: dict[str, Any] = {field: attack}
        document = _document(as_of=frozen_now, **overrides)
        rendered = _rendered_markdown(document)

        assert "code_block" not in _markdown_token_types(document), (
            f"the {field} opened a code block"
        )
        assert "<pre>" not in rendered, f"the {field} opened a code block"
        assert _structural_tags(rendered) == baseline, (
            f"the {field} opened structure the report does not otherwise hold"
        )


@pytest.mark.unit
def test_a_caption_with_a_blank_line_and_an_indent_is_not_a_code_block(
    frozen_now: datetime,
) -> None:
    """The caption is a caption, and its own line break does not change that.

    A caption is the author's words, and the writer prefixes the **first**
    line of it with "Figure 1. ". A caption that carries a blank line and
    four spaces therefore puts four spaces at the start of a line of the
    file, with a blank line before it — which is exactly what CommonMark
    reads as a code block. The reader would be shown the caption as code.

    The indent is written as a character reference instead, so the reader
    sees the same spaces and the caption stays a caption.
    """
    document = _document(
        as_of=frozen_now,
        caption="Mean yield across the five measured runs.\n\n    indented by four spaces",
    )
    markdown = render_markdown(document).decode("utf-8")

    assert "&#32;&#32;&#32;&#32;indented by four spaces" in markdown
    assert "code_block" not in _markdown_token_types(document)
    assert "<pre>" not in _rendered_markdown(document)
    assert "indented by four spaces" in _normalise(_read_markdown(markdown.encode("utf-8")))


@pytest.mark.unit
def test_an_interpretation_with_a_blank_line_and_an_indent_is_not_a_code_block(
    frozen_now: datetime,
) -> None:
    """And the interpretation is an interpretation.

    An interpretation is written at the start of a line, and its leading
    indent was protected — but only the **leading** one. An interpretation
    that carries a blank line and an indent puts an indented line at the
    start of a later line of the file, and the reader would be shown the
    reading as code.
    """
    document = _document(
        as_of=frozen_now,
        interpretation="The catalyst therefore improves yield.\n\n    indented by four spaces",
    )
    markdown = render_markdown(document).decode("utf-8")

    assert "&#32;&#32;&#32;&#32;indented by four spaces" in markdown
    assert "code_block" not in _markdown_token_types(document)
    assert "<pre>" not in _rendered_markdown(document)
    assert "indented by four spaces" in _normalise(_read_markdown(markdown.encode("utf-8")))


@pytest.mark.unit
def test_the_markdown_does_not_escape_a_number() -> None:
    """The number is the ledger's, spelled the ledger's way.

    ``4.253`` is a number a rounding step would turn into ``4.25``, which
    is a different claim about the same cell. The escape table's two
    exceptions exist for exactly this: a full stop between two digits is a
    decimal point, and a sign before a digit is a sign, and neither can be
    a list marker.
    """
    assert escape_markdown("4.253") == "4.253"
    assert escape_markdown("-4.25 %") == "-4.25 %"
    assert escape_markdown("+4.25 %") == "+4.25 %"
    assert escape_markdown("4.25 %.") == "4.25 %\\."


@pytest.mark.unit
def test_the_markdown_escapes_a_dot_that_is_not_a_decimal_point() -> None:
    """The exception is narrow, and the narrowness is the point.

    A full stop that is not between two digits is escaped, so that a
    paragraph cannot open an ordered list, and a sign that is not before a
    digit is escaped, so that a paragraph cannot open a bullet.
    """
    assert escape_markdown("1. a list") == "1\\. a list"
    assert escape_markdown("- a bullet") == "\\- a bullet"
    assert escape_markdown("1) a list") == "1\\) a list"
    assert escape_markdown(".") == "\\."
    assert escape_markdown("+") == "\\+"


# ---------------------------------------------------------------------------
# Rule 4 — the interpretation is marked, and only the interpretation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_interpretation_carries_the_marker(document: ReportDocument) -> None:
    """The report's own inference says that it is one."""
    text = _normalise(_read_markdown(render_markdown(document)))

    assert f"The catalyst therefore improves yield. {INTERPRETATION_MARKER}" in text


@pytest.mark.unit
def test_a_narrative_carries_no_marker(document: ReportDocument) -> None:
    """A description is not an inference, and marking it would be a lie."""
    text = _normalise(_read_markdown(render_markdown(document)))

    assert f"The dataset contained 120 rows. {INTERPRETATION_MARKER}" not in text
    assert text.count(INTERPRETATION_MARKER) == 2  # the block and the claim


@pytest.mark.unit
def test_a_claim_on_a_claim_record_carries_the_marker(document: ReportDocument) -> None:
    """A claim resting on a claim record is an interpretation too.

    The record's kind says so, and the model's
    :attr:`LedgerRecordView.is_interpretation` is the one spelling of that
    rule. A renderer that marked only the narrative blocks would leave
    this one unmarked.
    """
    text = _normalise(_read_markdown(render_markdown(document)))

    assert (
        f"clm-2 — The material reports a yield of 4.253%. (user_attested) [fn-1] "
        f"{INTERPRETATION_MARKER}"
    ) in text


@pytest.mark.unit
def test_the_marker_is_the_figure_renderers_marker() -> None:
    """One spelling of the marker in the tree, and it is the figure's.

    The figure's renderer has said "this is an interpretation" in one
    wording since LC-P1-10. A report that spelled the marker differently
    would make a reader wonder whether the two were the same claim.
    """
    assert INTERPRETATION_MARKER is FIGURE_INTERPRETATION_MARKER
    assert INTERPRETATION_MARKER == "[interpretation not machine-verified]"


@pytest.mark.unit
def test_every_form_marks_the_interpretation_the_same_way(document: ReportDocument) -> None:
    """The four forms mark it identically.

    A renderer that dropped the marker, or spelled it differently, would
    leave the reader of one export believing the report's inference was
    checked.
    """
    for form, text in _texts(document).items():
        assert text.count(INTERPRETATION_MARKER) == 2, f"the {form} form marks it wrongly"


# ---------------------------------------------------------------------------
# Rule 5 — every export says what the report is
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_every_form_carries_the_notice(document: ReportDocument) -> None:
    """The limit is on the face of every export.

    The work order requires the report to say that it is a first pass and
    not journal-ready, and a report that does not say it is claiming a
    standard it has not met.
    """
    for form, text in _texts(document).items():
        assert FIRST_PASS_NOTICE in text, f"the {form} form does not carry the notice"


@pytest.mark.unit
def test_every_form_says_which_forms_are_reproducible(document: ReportDocument) -> None:
    """The report states which of its four forms can be compared by hash.

    Two of them cannot: a DOCX is a ZIP whose entries carry timestamps,
    and a PDF carries a creation date. A report that stayed silent would
    let a reader hash two exports and read agreement into a difference
    that is only the clock.
    """
    for form, text in _texts(document).items():
        assert REPRODUCIBILITY_NOTICE in text, f"the {form} form does not say"


@pytest.mark.unit
def test_the_notice_says_the_report_is_not_journal_ready() -> None:
    """The notice says the thing the work order asks for."""
    assert "not journal-ready" in FIRST_PASS_NOTICE
    assert "first-pass" in FIRST_PASS_NOTICE


# ---------------------------------------------------------------------------
# Rule 7 — the two writable forms are byte-reproducible
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_markdown_is_byte_reproducible(document: ReportDocument) -> None:
    """Two renders of one model are the same bytes."""
    assert render_markdown(document) == render_markdown(document)


@pytest.mark.unit
def test_the_html_is_byte_reproducible(document: ReportDocument) -> None:
    """And so are the HTML's.

    The writer reads the document and writes text, and nothing in it
    depends on the clock, the environment, or the order the document was
    built in.
    """
    assert render_html(document) == render_html(document)


@pytest.mark.unit
def test_two_documents_of_the_same_content_have_the_same_bytes(
    frozen_now: datetime,
) -> None:
    """The bytes are a function of the content, and of nothing else.

    Two documents are built from the same facts, and the manifest's
    parameters are assembled in a different order in each — a dictionary's
    insertion order is a fact about how the builder ran, not about what
    the report says, and it must not reach the bytes.
    """
    first = _document(as_of=frozen_now)
    second = _document(as_of=frozen_now)

    assert first.canonical_bytes() == second.canonical_bytes()
    assert render_markdown(first) == render_markdown(second)
    assert render_html(first) == render_html(second)


# ---------------------------------------------------------------------------
# The two container forms are not reproducible, and the reasons are named
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_two_container_forms_are_not_byte_reproducible(
    document: ReportDocument,
) -> None:
    """The DOCX and the PDF differ between two renders, and here is why.

    A DOCX is a ZIP and every one of its entries carries the time it was
    written; a PDF carries a creation date and a document id. Both are
    measured here rather than asserted, and the reason is named so that
    nobody later reads the difference as a bug in the renderer.

    The gap between the two renders is a little over two seconds because
    a ZIP entry's timestamp has two seconds' resolution: two renders
    inside one window would agree, and an agreement measured inside one
    window is not a measurement.
    """
    first_docx = render_docx(document)
    first_pdf = render_pdf(document)
    time.sleep(2.2)
    second_docx = render_docx(document)
    second_pdf = render_pdf(document)

    assert first_docx != second_docx, "the DOCX is byte-reproducible, which it must not be"
    assert first_pdf != second_pdf, "the PDF is byte-reproducible, which it must not be"

    assert _docx_entry_times(first_docx) != _docx_entry_times(second_docx)
    assert _pdf_creation_date(first_pdf) != _pdf_creation_date(second_pdf)


@pytest.mark.unit
def test_the_docx_does_not_claim_python_docx_wrote_it(document: ReportDocument) -> None:
    """The artefact's author is LabCairn, and its description is the report's.

    python-docx's template says its author is ``python-docx`` and that its
    description is ``generated by python-docx``. Leaving the library's
    name in the artefact's author field is a false statement about who
    produced the report.
    """
    with zipfile.ZipFile(io.BytesIO(render_docx(document))) as archive:
        core = archive.read("docProps/core.xml").decode("utf-8")

    assert "<dc:creator>LabCairn</dc:creator>" in core
    assert "python-docx" not in core


@pytest.mark.unit
def test_the_docx_records_the_moment_the_report_is_a_view_of_in_utc(
    frozen_now: datetime,
) -> None:
    """The dates are the moment, and they are in UTC.

    python-docx writes the creation and modification dates with
    ``strftime('%Y-%m-%dT%H:%M:%SZ')`` — the wall-clock time of whatever
    datetime it is given, with a ``Z`` bolted on. The offset is *dropped*,
    not applied, so a moment that is aware and not in UTC would be written
    as its **local** time and would be hours wrong: ``12:00+08:00`` would
    be recorded as ``12:00Z``, which is eight hours after the fact.

    The moment is therefore converted to UTC before it is written, and the
    ``Z`` is then true. The moment used here is deliberately **not** in
    UTC, so that a writer that did not convert could not pass: the local
    time and the UTC time are eight hours apart, and only one of them is
    the right answer.

    The package is read back with the standard library — ``zipfile`` and
    ``ElementTree`` — because the reader must not be the writer.
    """
    moment = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    document = _document(as_of=moment)

    with zipfile.ZipFile(io.BytesIO(render_docx(document))) as archive:
        core = archive.read("docProps/core.xml").decode("utf-8")

    root = ElementTree.fromstring(core)
    created = root.find("{http://purl.org/dc/terms/}created")
    modified = root.find("{http://purl.org/dc/terms/}modified")
    assert created is not None
    assert modified is not None

    assert created.text == "2026-01-01T04:00:00Z", (
        "the creation date is the moment in UTC: 12:00+08:00 is 04:00Z, and "
        "writing the local time under a Z would be eight hours wrong"
    )
    assert modified.text == "2026-01-01T04:00:00Z"
    assert "2026-01-01T12:00:00Z" not in core


@pytest.mark.unit
def test_the_pdf_embeds_no_font(document: ReportDocument) -> None:
    """No font file is carried out of reportlab and into the artefact.

    The core Type 1 faces are *referenced*, not embedded, and a
    registered TrueType font would be embedded — which would carry its
    licence into the artefact.
    """
    assert render_pdf(document).count(b"/FontFile") == 0


@pytest.mark.unit
def test_the_pdf_exporter_does_not_open_the_network(document: ReportDocument) -> None:
    """reportlab's URL reader stays default-deny.

    reportlab ships a reader that can pull a figure over HTTP. A
    local-first tool that fetches a figure from the network is not
    local-first, so the trusted-hosts list is left as the library ships
    it.
    """
    from reportlab import rl_config

    render_pdf(document)

    assert rl_config.trustedHosts is None


# ---------------------------------------------------------------------------
# Acceptance: the exports are openable
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_markdown_is_parsed_back_by_a_parser(document: ReportDocument) -> None:
    """A Markdown parser reads it, and what it reads is the report."""
    text = _normalise(_read_markdown(render_markdown(document)))

    assert "A first-pass report" in text
    for line in EXPECTED_LINES:
        assert line in text, f"the parsed Markdown does not carry {line!r}"


@pytest.mark.integration
def test_the_html_is_parsed_back_by_a_parser(document: ReportDocument) -> None:
    """The standard library's parser reads it."""
    text = _normalise(_read_html(render_html(document)))

    assert "A first-pass report" in text
    for line in EXPECTED_LINES:
        assert line in text, f"the parsed HTML does not carry {line!r}"


@pytest.mark.integration
def test_the_docx_is_read_back_by_a_reader(document: ReportDocument) -> None:
    """The package is read out of the ZIP by the standard library."""
    text = _normalise(_read_docx(render_docx(document)))

    assert "A first-pass report" in text
    for line in EXPECTED_LINES:
        assert line in text, f"the DOCX does not carry {line!r}"


@pytest.mark.integration
def test_the_pdf_is_read_back_by_a_reader(document: ReportDocument) -> None:
    """A PDF reader reads it, and the text comes back out of it."""
    text = _normalise(_read_pdf(render_pdf(document)))

    assert "A first-pass report" in text
    for line in EXPECTED_LINES:
        assert line in text, f"the PDF does not carry {line!r}"


@pytest.mark.integration
def test_the_four_forms_say_the_same_words(document: ReportDocument) -> None:
    """Four drawings of one model, and the words are the same in all four.

    This is the property the whole package exists for. The four forms are
    not compared by a human reading them side by side; they are compared
    by a test that reads each of them back and asks whether the model's
    content is in it.
    """
    for form, text in _texts(document).items():
        for line in EXPECTED_LINES:
            assert line in text, f"the {form} form does not carry {line!r}"


@pytest.mark.integration
def test_every_form_reads_back_the_hosts_text(hostile_document: ReportDocument) -> None:
    """All four forms, read back, show the text and not an escape sequence.

    The hostile document is rendered to **every** form here, not only to
    the HTML and the Markdown: a form that was never rendered from it
    cannot be observed to mangle it, and the DOCX and the PDF are exactly
    the two forms that had never seen it.

    What the reader sees is the model's text. A form that escaped its
    text twice would show the reader ``&amp;`` where the model says
    ``&``, and comparing the forms' *bytes* would not have noticed.
    """
    for form, text in _texts(hostile_document).items():
        for hostile in HTML_HOSTILE:
            assert hostile in text, f"the {form} form does not read back {hostile!r}"


@pytest.mark.integration
def test_the_pdf_does_not_print_the_escape_sequence(hostile_document: ReportDocument) -> None:
    """The PDF is the fixed form, and it must not print the escaping.

    reportlab's paragraph markup is escaped once, at the call site. A
    paragraph that escaped its own text as well would escape it twice,
    and the reader would be shown ``&amp;`` where the model says ``&``.
    """
    text = _read_pdf(render_pdf(hostile_document))

    assert "&amp;" not in text
    assert "&lt;" not in text
    assert "&gt;" not in text
    assert "&amp;amp;" not in text


# ---------------------------------------------------------------------------
# Rule 1 — a renderer draws; it does not decide
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_status_printed_is_the_model_status_whatever_it_is(
    frozen_now: datetime,
) -> None:
    """The renderer prints the model's status and does not judge it.

    The ledger's status is the ceiling on what a report may say about a
    record, and the check that enforces the ceiling is the content
    check's, not the renderer's. What the renderer must not do is
    *assume* a status: a record the ledger has only extracted is
    printed as extracted, and the export does not strengthen it.
    """
    document = _document(as_of=frozen_now, status=VerificationStatus.EXTRACTED)

    for form, text in _texts(document).items():
        assert "(extracted)" in text, f"the {form} form does not carry the model's status"
        assert "verified_by_rule" not in text, f"the {form} form strengthens the status"


@pytest.mark.unit
def test_the_number_in_the_export_is_the_ledger_number(document: ReportDocument) -> None:
    """The number is the ledger's, at the ledger's precision.

    A renderer that had to compute a number to draw it would be a
    renderer that could disagree with the ledger, and the acceptance
    clause compares the numbers. ``4.253`` is a number a rounding step
    would turn into ``4.25``, which is a different claim about the same
    cell.
    """
    text = _normalise(_read_pdf(render_pdf(document)))

    assert "4.253" in text
    assert not re.search(r"\b4\.25\b", text)


@pytest.mark.unit
def test_the_markdown_carries_the_ledger_number_unescaped(document: ReportDocument) -> None:
    """And the Markdown's raw bytes carry it too.

    The escape table's two exceptions exist for this: a full stop between
    two digits is a decimal point, and a check that reads the report's
    numbers out of the file must find them.
    """
    markdown = render_markdown(document).decode("utf-8")

    assert "4.253" in markdown
    assert not re.search(r"\b4\.25\b", markdown)


@pytest.mark.unit
def test_no_number_appears_that_the_model_does_not_hold(document: ReportDocument) -> None:
    """Every number in an export is a number the model holds.

    The report's own quantities are the ledger's, copied into the model
    at build time. A renderer that computed a total, or a percentage
    derived from two values, would put a number in the report that no
    record holds — and the check that compares numbers with the ledger
    would then be comparing against a number the ledger never said.

    **All four forms are watched, not one.** The check that agrees the
    numbers with the ledger runs on the *document*, before any form is
    rendered, so it discharges the clause for the document and says
    nothing about what a renderer then does with it. A renderer that added
    a number of its own would produce an export that no check ever looks
    at again, and the clause would hold for the document and not for the
    file a reader opens.
    """
    expected = _model_numbers(document)

    for form, text in _texts(document).items():
        numbers = set(re.findall(r"\d+\.\d+", text))
        assert numbers == expected, (
            f"the {form} form carries {sorted(numbers)}, and the model holds {sorted(expected)}"
        )


@pytest.mark.unit
def test_every_form_carries_the_moment_and_the_records_the_document_holds(
    document: ReportDocument,
) -> None:
    """Every form says which moment it is a view of, and which records it is a view of.

    The **snapshot** is the model's statement of when the report is a view of,
    and the **records** are its statement of which records that view is made
    of. They are claims the report makes about itself, and they were the two
    claims no comparison read: they are not in :data:`EXPECTED_LINES`, so the
    comparison that read every other line of all four forms passed over these
    two, and a form could carry another document's moment, or name another
    document's records, or name none at all, and nothing would have noticed.

    **The expectation is read out of the document.** A literal is what let the
    gap hide — the two lines are missing from the constant the other
    comparison reads — and a literal would hide it again the moment the
    document changed.

    **All four forms are watched**, and each is read by the reader its own
    test reads it with: the Markdown by a parser, the HTML by a parser, the
    DOCX out of its package, the PDF by a reader that did not write it.
    """
    expected_moment = document.snapshot.as_of
    expected_records = frozenset(document.snapshot.record_ids)

    for form, text in _texts(document).items():
        moments, records = _the_snapshot_a_form_states(text)

        assert moments == {expected_moment}, (
            f"the {form} form is a view of {sorted(moments)}, and the document is a "
            f"view of {expected_moment}"
        )
        assert records == expected_records, (
            f"the {form} form names {sorted(records)}, and the document is a view "
            f"of {sorted(expected_records)}"
        )


# ---------------------------------------------------------------------------
# Rule 1 — a form carries the document, and nothing else
# ---------------------------------------------------------------------------
#
# Every comparison above asks whether the document's content is **in** a
# form. None of them asks whether a form says something the document does
# not, and that is the half that was missing: a renderer that composed a
# sentence of its own would produce a form that carried every one of the
# document's claims and one more, and every comparison would pass.
#
# The comparison below is an **equality**, so it fails in both directions —
# a form that leaves a claim out and a form that adds one. And the
# expectation is read out of the **document**, not out of the renderer,
# which is the point the comment above :data:`EXPECTED_LINES` makes: *a
# test that took its expectations from the code it is checking would prove
# nothing*. A resolver that changed the heading it draws would be invisible
# to a comparison built on the resolver, and the form would carry a
# heading the document does not have.

#: The label the four forms write before the moment the report is a view of.
SNAPSHOT_LABEL: Final = "Snapshot: "

#: The label the four forms write before the records the report is a view of.
RECORDS_LABEL: Final = "Records: "

#: The heading the four forms give the citations.
PROVENANCE_HEADING: Final = "Provenance"

#: The heading the four forms give the artefacts no section places.
UNPLACED_HEADING: Final = "Artefacts not placed in a section"


def _the_record_says(record: LedgerRecordView) -> str:
    """What a record holds, in the record's own words.

    A numeric record's statement is its number — drawn with ``repr``,
    which is the shortest spelling that reads back as the same float — and
    its declared unit; a claim or result record's statement is its text.
    """
    if record.text is not None:
        return record.text
    if record.value is None or record.unit is None:
        raise AssertionError(
            f"the record {record.record_id!r} carries neither a statement nor a "
            "quantity, so the model should have refused to build it"
        )
    return f"{record.value!r} {record.unit}"


def _the_claim_says(claim: ReportClaim) -> str:
    """What a finding reads, in the model's own words.

    The label, the statement, how far the record was checked and the
    citations it names, in that order — and the interpretation marker on
    the end, because a finding that rests on a claim or result record is
    an interpretation and the marker says so.
    """
    line = f"{claim.claim_id} — {_the_record_says(claim.record)} ({claim.record.status.value})"
    if claim.footnote_ids:
        line = f"{line} [{', '.join(claim.footnote_ids)}]"
    if claim.record.is_interpretation:
        line = f"{line} {INTERPRETATION_MARKER}"
    return line


def _the_disclosure_says(disclosure: UnresolvedRecord) -> str:
    """What a disclosure reads, in the model's own words.

    The record, what it holds, why it is not a finding, and why it could
    not be resolved — a reader who is shown a conflict has to be shown
    what it was about.
    """
    return (
        f"{disclosure.record.record_id} — {_the_record_says(disclosure.record)}"
        f" — {disclosure.record.status.value} — {disclosure.reason}"
    )


def _the_figure_says(figure: ReportFigure) -> tuple[str, ...]:
    """What a figure reads, in the model's own words.

    The caption, and then the artefact it names: the path and the hash of
    the bytes. The bytes themselves are not in the model, so the report
    names the artefact and the artefact manifest carries it.
    """
    return (
        f"Figure {figure.figure_id}. {figure.caption}",
        f"Artefact: {figure.relative_path} (sha256 {figure.content_sha256})",
    )


def _the_table_says(table: ReportTable) -> tuple[str, ...]:
    """What a table reads, in the model's own words."""
    return (
        f"Table {table.table_id}",
        f"Artefact: {table.relative_path} (sha256 {table.content_sha256})",
    )


def _the_document_says(document: ReportDocument) -> tuple[str, ...]:
    """Every line the report makes, in the order the four forms draw them.

    Read out of the **document**. Every value in it is the model's own —
    the title, the headings, the prose, the findings, the captions, the
    addresses, the moment and the records — so a document that grew a
    claim grew this expectation with it, and a form that left the new
    claim out no longer matches.

    The wording is stated here rather than taken from the renderer, and
    the reason is the one the comment above :data:`EXPECTED_LINES` gives:
    a test that took its expectations from the code it is checking would
    prove nothing. The four labels below are the renderers' own — the
    words they write around the document's content — and the notices are
    the product's.
    """
    claims = {claim.claim_id: claim for claim in document.claims}
    figures = {figure.figure_id: figure for figure in document.figures}
    tables = {table.table_id: table for table in document.tables}
    disclosures = {item.record.record_id: item for item in document.unresolved_records}

    lines: list[str] = [
        document.title,
        FIRST_PASS_NOTICE,
        REPRODUCIBILITY_NOTICE,
        f"{SNAPSHOT_LABEL}{document.snapshot.as_of.isoformat()}",
    ]
    if document.snapshot.record_ids:
        lines.append(f"{RECORDS_LABEL}{', '.join(document.snapshot.record_ids)}")

    placed_figures: set[str] = set()
    placed_tables: set[str] = set()
    for section in document.sections:
        lines.append(section.heading)
        for block in section.blocks:
            if isinstance(block, NarrativeBlock):
                lines.append(block.text)
            elif isinstance(block, InterpretationBlock):
                lines.append(f"{block.text} {INTERPRETATION_MARKER}")
            elif isinstance(block, ClaimBlock):
                lines.append(_the_claim_says(claims[block.claim_id]))
            elif isinstance(block, FigureBlock):
                placed_figures.add(block.figure_id)
                lines.extend(_the_figure_says(figures[block.figure_id]))
            elif isinstance(block, TableBlock):
                placed_tables.add(block.table_id)
                lines.extend(_the_table_says(tables[block.table_id]))
            elif isinstance(block, UnresolvedBlock):
                lines.append(_the_disclosure_says(disclosures[block.record_id]))

    unplaced_figures = [f for f in document.figures if f.figure_id not in placed_figures]
    unplaced_tables = [t for t in document.tables if t.table_id not in placed_tables]
    if unplaced_figures or unplaced_tables:
        lines.append(UNPLACED_HEADING)
        for figure in unplaced_figures:
            lines.extend(_the_figure_says(figure))
        for table in unplaced_tables:
            lines.extend(_the_table_says(table))

    lines.append(PROVENANCE_HEADING)
    for footnote in document.footnotes:
        lines.append(
            f"{footnote.footnote_id} — source {footnote.source_id}"
            f" — {describe_locator(footnote.locator)} — sha256 {footnote.content_sha256}"
        )
    return tuple(lines)


def _what_the_document_says(document: ReportDocument) -> str:
    """What the document says, as one line of text.

    The lines are joined with a space and the whitespace is collapsed,
    because the readers collapse it too: the PDF wraps a long line, the
    DOCX has no line breaks at all, and a comparison that did not collapse
    the whitespace would fail on a line that is merely long.
    """
    return _normalise(" ".join(_the_document_says(document)))


def _the_forms_say(document: ReportDocument) -> dict[str, str]:
    """The four forms, each read back by a reader that did not write it.

    The DOCX and the PDF are **not** byte-reproducible, so a claim about
    them is measured by reading them back and not by comparing bytes: the
    DOCX out of its package, the PDF by a reader that did not write it,
    the HTML by a parser, and the Markdown by a Markdown parser.
    """
    pdf_text, _ = _read_pdf_body(render_pdf(document))
    return {
        "markdown": _normalise(_read_markdown(render_markdown(document))),
        "html": _normalise(_read_html_body(render_html(document))),
        "docx": _normalise(_read_docx(render_docx(document))),
        "pdf": _normalise(pdf_text),
    }


def _the_difference(expected: str, actual: str) -> str:
    """The words two texts disagree about, in the order they disagree.

    A form that does not say what the document says can differ by one
    word or by a whole sentence, and a failure message that named only
    the two texts would leave the reader to find the difference. This
    names it.
    """
    expected_words = expected.split(" ")
    actual_words = actual.split(" ")
    lines: list[str] = []
    for index, (left, right) in enumerate(zip(expected_words, actual_words, strict=False)):
        if left != right:
            lines.append(
                f"at word {index + 1}: the document says {left!r}, the form says {right!r}"
            )
            break
    if len(expected_words) != len(actual_words):
        lines.append(
            f"the document says {len(expected_words)} words and the form says {len(actual_words)}"
        )
    return "; ".join(lines)


@pytest.mark.integration
def test_every_form_carries_the_document_and_nothing_else(
    document: ReportDocument,
) -> None:
    """Every form says what the document says, and says nothing else.

    This is the comparison the rest of this file is made of, said in
    both directions at once. A form that **omits** one of the document's
    claims and a form that **adds** a claim of its own are the same
    failure — a form that is not a drawing of this document — and an
    equality catches both, where a containment catches only the first.

    **All four forms are watched**, and each is read by the reader its
    own test reads it with. The DOCX and the PDF are read back rather
    than compared byte for byte, because neither of them is
    byte-reproducible: a DOCX is a ZIP whose entries carry the time the
    file was written, and a PDF carries a creation date.

    **The expectation is read out of the document**, so a document that
    changed moves the expectation with it, and a renderer that changed
    does not.

    The comparison is on the text with the whitespace collapsed, because
    the readers collapse it: the PDF wraps a long line and the DOCX has no
    line breaks at all, and a difference in the whitespace would say
    nothing about the renderer.
    """
    expected = _what_the_document_says(document)

    for form, text in _the_forms_say(document).items():
        assert text == expected, (
            f"the {form} form does not say what the document says — "
            f"{_the_difference(expected, text)}"
        )


@pytest.mark.integration
def test_every_form_carries_the_document_that_was_escaped(
    hostile_document: ReportDocument,
) -> None:
    """The same comparison, on a document whose every value fights back.

    The comparison above is an equality of texts, and an equality is
    exact: a form that escaped a value twice, or dropped a character
    while escaping it, would read back as a different text and the
    comparison would say so. The hostile document is the one that tries
    every way of doing that, and the four readers are four ways of
    undoing it, so the comparison is worth making on this document and
    not only on the well-behaved one.
    """
    expected = _what_the_document_says(hostile_document)

    for form, text in _the_forms_say(hostile_document).items():
        assert text == expected, (
            f"the {form} form does not read back what the document says — "
            f"{_the_difference(expected, text)}"
        )


@pytest.mark.integration
def test_every_form_carries_every_claim_a_document_with_more_of_them_holds(
    frozen_now: datetime,
) -> None:
    """A document with more than one of everything, and four forms that carry it all.

    The usual fixture holds one of each kind of thing, and a comparison
    that reads one of each cannot tell a form that carries the first from a
    form that carries them all: a form that dropped the second citation, or
    the second section, would still hold the first, and every comparison
    would pass. The expectation here is read out of the document, so the
    comparison grows with the document, and this test grows the document
    to show that it does.

    It is also the test that a claim nobody thought of is watched. A form
    that dropped the second of two citations is a form that says less than
    the document says, and nothing in the suite said anything about it
    before, because the usual document has only one citation to drop.
    """
    document = _a_document_with_more_than_one_of_everything(frozen_now)
    expected = _what_the_document_says(document)

    for form, text in _the_forms_say(document).items():
        assert text == expected, (
            f"the {form} form does not carry every claim the document holds — "
            f"{_the_difference(expected, text)}"
        )


@pytest.mark.unit
def test_the_html_carries_the_title_in_its_own_title_element(
    document: ReportDocument,
) -> None:
    """The HTML names the report in the head as well as in the body.

    The comparison of the forms reads the body, because the head is the
    document's metadata — its title and its style sheet — and the body is
    what a reader reads. The ``<title>`` is the report's own name all the
    same, and it is the name a reader's tab shows, so it is checked on
    its own: a title element that named another report would give a
    reader a tab that lied about what was in it.
    """
    title = _the_html_title(render_html(document))

    assert title == document.title


@pytest.mark.unit
def test_the_pdf_marks_one_list_item_for_each_of_the_report_s_list_items(
    document: ReportDocument,
) -> None:
    """The PDF's list marker is drawn once for each of the report's list items.

    The PDF's reader cannot name the bullet reportlab draws, and drops
    the marker in its place — which is right, because the marker is the
    PDF's list marker and the other three forms' readers drop theirs as
    well. But a dropped marker is a hole in the comparison of the forms,
    because a renderer that added a glyph the reader cannot name would
    have it dropped too.

    So the number of markers is checked against the number of list items
    the report carries: a finding, a disclosure and a citation are list
    items, and a narrative, an interpretation, a figure and a table are
    not.
    """
    _, markers = _read_pdf_body(render_pdf(document))
    list_items = len(document.claims) + len(document.unresolved_records) + len(document.footnotes)

    assert markers == list_items


# ---------------------------------------------------------------------------
# The carriers: what a form says about the report outside its text
# ---------------------------------------------------------------------------
#
# A form says things about the report in places other than its text: a
# document's own title property, a PDF's information dictionary, a
# paragraph's style. Each of those is a carrier the reader sees, and a
# carrier that named another report — or dropped the report's own limit —
# would be the same lie as a body that said the wrong thing, in a place
# the comparison of the forms never looks at.
#
# Each witness below reads its carrier **with the reader its own form is
# read by**, and compares it with the document's own value: the model for
# the title, the report's list items for the markers, and the product's one
# spelling of the limit for the descriptions.


@pytest.mark.unit
def test_the_docx_carries_the_title_in_its_own_title_property(
    document: ReportDocument,
) -> None:
    """The DOCX names the report in its own properties, as well as in its body.

    The comparison of the forms reads the body, because the core
    properties are the document's metadata and the body is what a reader
    reads. The title property is the report's own name all the same, and
    it is the name a reader's word processor shows in its title bar, so it
    is checked on its own: a title property that named another report
    would give a reader a title bar that lied about what was in the file.
    """
    title = _the_docx_core_property(render_docx(document), "title")

    assert title == document.title


@pytest.mark.unit
def test_the_pdf_carries_the_title_in_its_own_title(
    document: ReportDocument,
) -> None:
    """The PDF names the report in its own information dictionary.

    The same lie in the same kind of carrier as the HTML's title element
    and the DOCX's title property: a reader's viewer shows this name in
    its title bar, and a name that belonged to another report would lie
    about what was in the file.
    """
    title = _the_pdf_information(render_pdf(document), "Title")

    assert title == document.title


@pytest.mark.unit
def test_the_docx_carries_the_limit_in_its_own_description(
    document: ReportDocument,
) -> None:
    """The DOCX's description is the limit the report states on its own face.

    python-docx's template says its description is ``generated by
    python-docx``, which is a false statement about the report, and the
    exporter replaces it with the limit the report states on its own face.
    A reader who opens the file in a word processor sees the description
    in its properties panel, so a description that did not carry the limit
    would let a reader believe a standard the report has not met.
    """
    description = _the_docx_core_property(render_docx(document), "description")

    assert description == FIRST_PASS_NOTICE, (
        "the DOCX's description is the limit the report states on its own face"
    )
    assert description in _read_docx(render_docx(document)), (
        "the DOCX's description is a sentence the document itself carries"
    )


@pytest.mark.unit
def test_the_pdf_carries_the_limit_in_its_own_subject(
    document: ReportDocument,
) -> None:
    """The PDF's subject is the limit the report states on its own face.

    The same limit, in the same kind of carrier, in the other container
    form: a reader's viewer shows the subject in its properties panel, and
    a report whose metadata says nothing about its own limit lets a
    reader believe a standard it has not met. The two container forms are
    two renderings of one document, and what they must not do is say four
    different things.
    """
    subject = _the_pdf_information(render_pdf(document), "Subject")

    assert subject == FIRST_PASS_NOTICE, (
        "the PDF's subject is the limit the report states on its own face"
    )
    assert subject in _read_pdf(render_pdf(document)), (
        "the PDF's subject is a sentence the document itself carries"
    )


@pytest.mark.unit
def test_the_pdf_names_the_producer_the_docx_names(
    document: ReportDocument,
) -> None:
    """The two container forms name the same producer.

    The PDF's ``/Author`` is the **producer's** name and not the report's
    author: the report has no author, and the name is there so that a
    reader can see who made the file. The DOCX's ``dc:creator`` is that
    same producer's name, and the two container forms are two renderings
    of one document — so a PDF that named a different producer from the
    DOCX of the same report would be a file that disagrees with itself.

    The producer's name itself is pinned on the DOCX's side by
    :func:`test_the_docx_does_not_claim_python_docx_wrote_it`, which is
    the test that says the name is the producer's and not the library's.
    """
    author = _the_pdf_information(render_pdf(document), "Author")
    creator = _the_docx_core_property(render_docx(document), "creator")

    assert author == creator, "the PDF and the DOCX of one report name two different producers"


@pytest.mark.unit
def test_the_markdown_draws_a_finding_as_a_list_item(
    document: ReportDocument,
) -> None:
    """The Markdown draws each of the report's list items as a list item.

    A finding, a disclosure and a citation are list items, and a
    narrative, an interpretation, a figure and a table are not. The
    Markdown's list marker is the ``- `` at the head of a line, and the
    number of them is compared with the number of list items the model
    holds — so a renderer that drew a finding as a paragraph would be
    caught by the count and not only by the words.
    """
    items = _the_markdown_list_items(render_markdown(document))
    list_items = len(document.claims) + len(document.unresolved_records) + len(document.footnotes)

    assert items == list_items, (
        f"the Markdown draws {items} list items and the document holds {list_items}"
    )


@pytest.mark.unit
def test_the_docx_draws_a_finding_as_a_list_item(
    document: ReportDocument,
) -> None:
    """The DOCX draws each of the report's list items as a list item.

    The same rule as the Markdown's and the PDF's, in the DOCX's own
    carrier: a paragraph in a list. The count is the number of paragraphs
    the package draws in a list, and it is compared with the number of
    list items the model holds, so a renderer that drew a finding as a
    plain paragraph would be caught by the count and not only by the words.
    """
    items = _the_docx_list_items(render_docx(document))
    list_items = len(document.claims) + len(document.unresolved_records) + len(document.footnotes)

    assert items == list_items, (
        f"the DOCX draws {items} list items and the document holds {list_items}"
    )


# ---------------------------------------------------------------------------
# Nothing is dropped, and nothing is claimed that is not there
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_an_artefact_no_section_places_is_not_dropped(frozen_now: datetime) -> None:
    """A figure the document carries but no section places is still drawn.

    The model requires every claim and every disclosure to be placed, but
    not every figure or table. A renderer that drew only the placed ones
    would lose it silently, and "the export is openable" would not notice.
    """
    document = _document(as_of=frozen_now)
    extra = ReportFigure(
        figure_id="fig-2",
        relative_path="outputs/figures/fig-2.svg",
        content_sha256=FIGURE_HASH,
        caption="A figure no section places.",
        manifest=_manifest(),
    )
    document = ReportDocument(
        title=document.title,
        snapshot=document.snapshot,
        sections=document.sections,
        claims=document.claims,
        figures=(*document.figures, extra),
        tables=document.tables,
        footnotes=document.footnotes,
        unresolved_records=document.unresolved_records,
    )

    text = _normalise(_read_markdown(render_markdown(document)))

    assert "A figure no section places." in text
    assert "outputs/figures/fig-2.svg" in text


@pytest.mark.unit
def test_the_export_carries_no_external_identifier(document: ReportDocument) -> None:
    """A citation is a locator, and there is no identifier in the export.

    The owner decided on 2026-10-20 that a report cites locators only:
    an identifier in the source model is a slot ingestion never fills and
    nothing in the tree resolves, so an identifier printed as a citation
    would be the material's claim and not the report's.
    """
    for form, text in _texts(document).items():
        lowered = text.lower()
        assert "doi" not in lowered, f"the {form} form carries an identifier"
        assert "arxiv" not in lowered
        assert "isbn" not in lowered


# ---------------------------------------------------------------------------
# The dependencies are lazy, and the PDF refuses what it cannot draw
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_rendering_markdown_does_not_load_the_container_libraries() -> None:
    """A report exported only as Markdown must not pay for lxml or reportlab.

    ADR-0013's constraint 2. The check is in a subprocess because the
    libraries may already be loaded in this one, and what matters is what
    a fresh interpreter loads.
    """
    code = """
import sys
from datetime import UTC, datetime
from labcairn.reports.model import LedgerSnapshot, NarrativeBlock, ReportDocument, ReportSection
from labcairn.reports.render import render_html, render_markdown

document = ReportDocument(
    title="t",
    snapshot=LedgerSnapshot(as_of=datetime(2026, 1, 1, tzinfo=UTC), record_ids=()),
    sections=(
        ReportSection(
            section_id="sec-1", heading="h", blocks=(NarrativeBlock(text="n"),)
        ),
    ),
)
render_markdown(document)
render_html(document)
assert "docx" not in sys.modules, "the DOCX library was loaded"
assert "reportlab" not in sys.modules, "the PDF library was loaded"
print("ok")
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_the_pdf_refuses_a_character_it_cannot_draw(frozen_now: datetime) -> None:
    """A character outside the faces' encoding is refused, not mangled.

    reportlab draws such a character as a placeholder, silently. A report
    that says one thing and prints another is worse than a report that
    refuses to be printed, so the exporter refuses and names the
    character.
    """
    document = _document(as_of=frozen_now, caption=f"A caption with {UNENCODABLE} in it.")

    with pytest.raises(PdfTextRefusedError) as caught:
        render_pdf(document)

    assert UNENCODABLE in str(caught.value)


@pytest.mark.unit
def test_the_markdown_and_the_html_carry_a_character_the_pdf_cannot(
    frozen_now: datetime,
) -> None:
    """The two writable forms are not limited the way the PDF is.

    The PDF's faces are WinAnsi-encoded and the Markdown and the HTML are
    UTF-8, so the PDF is the one form that cannot carry a character
    outside Latin-1. The limit is the format's, and it is refused rather
    than hidden.
    """
    document = _document(as_of=frozen_now, caption=f"A caption with {UNENCODABLE} in it.")

    assert UNENCODABLE in render_markdown(document).decode("utf-8")
    assert UNENCODABLE in _normalise(_read_html(render_html(document)))


# ---------------------------------------------------------------------------
# The package's own surface
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_render_package_exports_one_spelling_of_each_word() -> None:
    """There is one marker and one notice in the tree, and the package says so."""
    from labcairn.reports import render

    assert render.INTERPRETATION_MARKER is INTERPRETATION_MARKER
    assert render.FIRST_PASS_NOTICE is FIRST_PASS_NOTICE
    assert render.REPRODUCIBILITY_NOTICE is REPRODUCIBILITY_NOTICE


# ---------------------------------------------------------------------------
# The renderer's own refusals
# ---------------------------------------------------------------------------
#
# The model resolves every id when it is built, so a document that places
# something it does not carry cannot be made the usual way. The renderer
# refuses such a document by name anyway, and these are the tests that
# watch it: a renderer that drew one would draw an empty space where a
# finding should be, and nothing would notice, because the export would
# be perfectly well formed.


@pytest.mark.unit
@pytest.mark.parametrize(
    "block",
    [
        ClaimBlock(claim_id="clm-missing"),
        FigureBlock(figure_id="fig-missing"),
        TableBlock(table_id="tab-missing"),
        UnresolvedBlock(record_id="rec-missing"),
    ],
)
def test_the_renderer_refuses_a_block_the_report_does_not_carry(
    frozen_now: datetime, block: Any
) -> None:
    """A block that names something the report does not carry is refused.

    Each kind of block names its thing by id, and the ids are resolved
    by the model when the document is built. A document that slipped
    past that would leave the renderer with nothing to draw, and a
    renderer that drew an empty space would be indistinguishable from a
    renderer that had nothing to say.
    """
    document = _an_unresolved_document(
        as_of=frozen_now,
        sections=(ReportSection(section_id="sec-1", heading="Findings", blocks=(block,)),),
    )

    with pytest.raises(ReportRenderError, match="the report does not carry"):
        resolve(document)


@pytest.mark.unit
def test_the_renderer_refuses_a_citation_the_report_does_not_carry(
    frozen_now: datetime,
) -> None:
    """A claim that cites a citation the report does not carry is refused.

    A claim's citation ids are resolved by the model as well. A claim
    that survived without one would be drawn with no address, and a
    reader would be shown a finding they could not check.
    """
    record = LedgerRecordView(
        record_id="rec-1",
        record_kind=EvidenceKind.NUMERIC,
        value=LEDGER_VALUE,
        unit="%",
        status=VerificationStatus.VERIFIED_BY_RULE,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )
    document = _an_unresolved_document(
        as_of=frozen_now,
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(ClaimBlock(claim_id="clm-1"),),
            ),
        ),
        claims=(
            ReportClaim(
                claim_id="clm-1",
                record=record,
                footnote_ids=("fn-missing",),
            ),
        ),
    )

    with pytest.raises(ReportRenderError, match="cites the footnote"):
        resolve(document)


@pytest.mark.unit
def test_the_renderer_refuses_a_block_of_an_unknown_kind(frozen_now: datetime) -> None:
    """A block the model does not declare is refused, not drawn.

    The model declares the kinds of block there are, and the renderer
    dispatches on the block's class. A block of a kind the model does
    not declare is a document this tree's model did not build.
    """
    section = ReportSection.model_construct(
        section_id="sec-1",
        heading="Findings",
        blocks=("not a block at all",),
    )
    document = _an_unresolved_document(as_of=frozen_now, sections=(section,))

    with pytest.raises(ReportRenderError, match="unknown kind"):
        resolve(document)


@pytest.mark.unit
def test_the_renderer_refuses_a_record_with_nothing_to_draw(frozen_now: datetime) -> None:
    """A record with neither a statement nor a quantity is refused.

    A numeric record carries a value and a declared unit, and a claim
    record carries a sentence. One with neither is a record with nothing
    in it, and there is nothing to draw.
    """
    record = LedgerRecordView.model_construct(
        record_id="rec-1",
        record_kind=EvidenceKind.NUMERIC,
        text=None,
        value=None,
        unit=None,
        status=VerificationStatus.VERIFIED_BY_RULE,
    )
    document = _an_unresolved_document(
        as_of=frozen_now,
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(ClaimBlock(claim_id="clm-1"),),
            ),
        ),
        claims=(
            ReportClaim.model_construct(
                claim_id="clm-1",
                record=record,
                footnote_ids=(),
            ),
        ),
    )

    with pytest.raises(ReportRenderError, match="neither a statement nor a quantity"):
        render_markdown(document)


@pytest.mark.unit
def test_the_docx_exporter_refuses_clearly_when_python_docx_is_missing(
    monkeypatch: pytest.MonkeyPatch, document: ReportDocument
) -> None:
    """A missing dependency is a named refusal, not an ImportError.

    The dependency is declared, so this is not a state the product should
    ever be in — but a writer that lets a raw ``ImportError`` out is a
    writer that answers a different question than the one the caller
    asked, and the caller would have to know which of the two it got.
    """
    monkeypatch.setitem(sys.modules, "docx", None)

    with pytest.raises(RuntimeError, match="python-docx is required"):
        render_docx(document)


@pytest.mark.unit
def test_the_pdf_exporter_refuses_clearly_when_reportlab_is_missing(
    monkeypatch: pytest.MonkeyPatch, document: ReportDocument
) -> None:
    """And the same for the PDF form.

    The library is imported lazily so that a report exported only as
    Markdown does not pay for it, which means the import is inside the
    function — and so means the refusal has to be there too.
    """
    monkeypatch.setitem(sys.modules, "reportlab.lib.styles", None)

    with pytest.raises(RuntimeError, match="reportlab is required"):
        render_pdf(document)
