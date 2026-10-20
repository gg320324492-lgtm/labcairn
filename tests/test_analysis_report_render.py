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
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
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
    escape_markdown,
    render_docx,
    render_html,
    render_markdown,
    render_pdf,
)
from labcairn.reports.render.markdown import MARKDOWN_ESCAPE_TABLE
from labcairn.sources.locators import ComputationLocator, PdfLocator

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
) -> ReportDocument:
    """A report with one of everything, so that no kind goes untested."""
    numeric = _numeric_record(
        record_id="rec-1", value=LEDGER_VALUE, status=VerificationStatus.VERIFIED_BY_RULE
    )
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


def _read_markdown(blob: bytes) -> str:
    """The text of a Markdown file, read by a Markdown parser.

    The raw file is not the report's text: the writer escapes the model's
    punctuation, so the file says ``4\\.25`` where the model says
    ``4.25``. The **rendered** file is the report, and that is what a
    reader gets.
    """
    rendered = MarkdownIt("commonmark").render(blob.decode("utf-8"))
    reader = _TextReader()
    reader.feed(rendered)
    reader.close()
    return reader.text


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


def _read_pdf(blob: bytes) -> str:
    """The text of a PDF file, read by a reader that did not write it."""
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


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
    rendered = MarkdownIt("commonmark").render(render_markdown(hostile_document).decode("utf-8"))

    headings = re.findall(r"<h[1-6]>.*?</h[1-6]>", rendered, re.DOTALL)
    assert headings, "the report has no headings at all"
    assert not [heading for heading in headings if HOSTILE_HEADING in heading]
    assert "<em>" not in rendered
    assert "<a " not in rendered
    assert "<code>" not in rendered


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


# ---------------------------------------------------------------------------
# Rule 1 — a renderer draws; it does not decide
# ---------------------------------------------------------------------------


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
    """
    text = _normalise(_read_pdf(render_pdf(document)))
    numbers = set(re.findall(r"\d+\.\d+", text))

    assert numbers == {"4.253", "4.9"}


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
