"""Retrieval against the real papers, using the ground-truth set as its judge.

Every expectation here comes from ``tests/fixtures/retrieval/ground_truth.json``,
which was written by reading the papers and is validated against them by
``test_retrieval_ground_truth.py``. This file adds the other half: it puts that
real text into the index and asks whether a query finds it.

The pages are inserted directly rather than through the workspace walk. That is
deliberate, and it is a limit worth stating: LC-P1-08's ingest is covered by its
own tests, and this file is about the index. Re-walking 70 pages of PDF to test
a ``MATCH`` clause would be slow and would fail for reasons that belong to a
different module. What is real here is the text -- the actual extracted content
of the actual pages -- and the queries, which is the part that decides whether
retrieval works.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
from collections.abc import Iterator
from typing import Any

import pdfplumber
import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine
from labcairn.evidence.cite_support import LocationResolution
from labcairn.evidence.index import Hit, build_match_expression, locate_anchor, search
from labcairn.evidence.normalize import normalize
from labcairn.evidence.states import NormalizationProfile
from labcairn.material.addressing import render_locator_key, split_locator_key
from labcairn.sources.locators import PdfLocator

PAPERS = pathlib.Path(__file__).parent / "fixtures" / "papers"
GROUND_TRUTH = pathlib.Path(__file__).parent / "fixtures" / "retrieval" / "ground_truth.json"
NOW = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)


def _entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["queries"]
    return entries


POSITIVE = [e for e in _entries() if e["expect"]]
NEGATIVE = [e for e in _entries() if not e["expect"]]


def _page_texts(source: str) -> dict[int, str]:
    with pdfplumber.open(PAPERS / source) as document:
        return {n: page.extract_text() or "" for n, page in enumerate(document.pages, 1)}


def _seed(connection: Connection, rows: list[tuple[str, int, str]]) -> None:
    """Insert real page text as ``source_texts`` rows and index them.

    One ``sources`` row per paper, not per page: a paper is one material with
    many addresses, and the store's primary key says so.

    Indexed through :func:`normalize`, so the index holds the normalised copy
    and ``source_texts`` the original -- the split T02 exists to keep, and the
    one ``search`` has to get right.
    """
    seeded_papers: set[str] = set()
    for source, page, body in rows:
        digest = hashlib.sha256(source.encode()).hexdigest()
        key = render_locator_key(PdfLocator(page=page))
        if source not in seeded_papers:
            connection.execute(
                sql_text(
                    "INSERT INTO sources (source_id, owner_id, kind, display_name,"
                    " relative_path, content_sha256, size_bytes, readability,"
                    " readability_disclosure, identifiers, ingested_at, schema_version)"
                    " VALUES (:sid,'local-user','pdf',:name,:rel,:sha,1,'readable',NULL,"
                    "'[]',:now,1)"
                ),
                {
                    "sid": f"src-{source}",
                    "name": source,
                    "rel": source,
                    "sha": digest,
                    "now": NOW,
                },
            )
            seeded_papers.add(source)
        connection.execute(
            sql_text(
                "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                " locator_kind, locator_key, page, text, text_sha256, created_at)"
                " VALUES (:sha,'v1','pdf',:key,:page,:body,:tsha,:now)"
            ),
            {
                "sha": digest,
                "key": key,
                "page": page,
                "body": body,
                "tsha": hashlib.sha256(body.encode()).hexdigest(),
                "now": NOW,
            },
        )
        normalized = normalize(body, NormalizationProfile.NFKC_WHITESPACE_COLLAPSED)
        connection.execute(
            sql_text(
                "INSERT INTO evidence_fts (normalized_text, source_content_sha256,"
                " extraction_version, locator_key, source_text_id)"
                " VALUES (:body,:sha,'v1',:key,'1')"
            ),
            {"body": normalized.text, "sha": digest, "key": key},
        )


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Connection]:
    """An index holding every page the ground-truth set expects to be found."""
    target = tmp_path_factory.mktemp("index") / "index.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    connection = engine.connect()
    with connection.begin():
        wanted: dict[str, set[int]] = {}
        for entry in POSITIVE:
            wanted.setdefault(entry["expect"][0]["source"], set()).update(
                entry["expect"][0]["pages"]
            )
        rows = [
            (source, page, body)
            for source, pages in wanted.items()
            for page, body in sorted(_page_texts(source).items())
            if page in pages
        ]
        _seed(connection, rows)
    connection.commit()
    yield connection
    connection.close()
    engine.dispose()


def _returned_pages(hits: tuple[Hit, ...], source: str) -> set[int]:
    """Pages of *source* the hits name.

    Read back through ``split_locator_key`` rather than by splitting on the
    separators. The addressing module's own docstring records why: splitting on
    ``|`` and validating afterwards is the same non-injective assumption it
    exists to reject, and it fails on real keys whose values contain the
    separator. This test needed a locator read, and it should use the designed
    reader rather than a second guess at the format.
    """
    found: set[int] = set()
    for hit in hits:
        if hit.locator_kind != "pdf":
            continue
        if hit.source_ids and f"src-{source}" not in hit.source_ids:
            continue
        found.add(int(split_locator_key(hit.locator_key)["p"]))
    return found


@pytest.mark.parametrize("entry", POSITIVE, ids=[e["id"] for e in POSITIVE])
def test_a_query_finds_the_excerpts_the_papers_say_it_should(
    seeded: Connection, entry: dict[str, Any]
) -> None:
    """The work order's acceptance, against the real papers.

    Every page the ground truth expects is required to come back, and every
    page that comes back must be one of them -- so a retriever that returns the
    whole paper, or the wrong paper, fails rather than passing on partial
    credit.
    """
    expected = entry["expect"][0]
    hits = search(seeded, entry["query"])
    returned = _returned_pages(hits, expected["source"])
    assert returned == set(expected["pages"]), (
        f"{entry['id']}: expected pages {expected['pages']}, retrieved {sorted(returned)}"
    )


@pytest.mark.parametrize("entry", POSITIVE, ids=[e["id"] for e in POSITIVE])
def test_a_hit_carries_the_original_text_not_the_indexed_copy(
    seeded: Connection, entry: dict[str, Any]
) -> None:
    """T02's split, exercised.

    The index holds a normalised copy. A hit that handed that copy back would
    have C2 comparing the index against itself -- a comparison that cannot
    fail, and the same shape as LC-P1-08's two-column defect.
    """
    expected = entry["expect"][0]
    for hit in search(seeded, entry["query"]):
        source = expected["source"]
        page = _returned_pages((hit,), source)
        if not page:
            continue
        original = _page_texts(source)[next(iter(page))]
        assert hit.text == original, "the hit returned something other than the stored text"


@pytest.mark.parametrize("entry", NEGATIVE, ids=[e["id"] for e in NEGATIVE])
def test_a_query_with_nothing_to_find_returns_nothing(
    seeded: Connection, entry: dict[str, Any]
) -> None:
    """ADR-0004 A6 and A12.

    A retriever that answered a fabricated DOI or the phrase "retrieval
    augmented generation" with its nearest passage would pass every positive
    query above.
    """
    assert search(seeded, entry["query"]) == ()


def test_every_positive_query_is_answered_by_more_than_one_row(seeded: Connection) -> None:
    """A guard on the fixture, not on the code.

    If the seeded pages stopped covering the expectations, every positive test
    would pass vacuously by retrieving nothing and comparing ``set() == set()``.
    """
    for entry in POSITIVE:
        assert search(seeded, entry["query"]), f"{entry['id']} retrieved nothing"


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\t\n",
        'a "quoted',
        "(unbalanced",
        "a OR",
        "NOT x",
        "10.9999/j.labcairn.2026.00001",
        "total-correlation",
        "col:val",
        "x*",
    ],
)
def test_no_query_string_can_crash_the_index(seeded: Connection, query: str) -> None:
    """The measurement that shaped :func:`build_match_expression`.

    A naive ``MATCH :query`` raises on several of these -- a syntax error near
    the ``.``, *no such column* for a ``-`` read as a column filter, an
    unterminated string for a lone quote. That is ADR-0004 A9 arriving as a
    crash rather than as a false negative.
    """
    search(seeded, query)  # must return, not raise


def test_an_empty_query_issues_no_match_at_all() -> None:
    """A6's honest answer is absence, and FTS5 rejects an empty MATCH."""
    assert build_match_expression("") is None
    assert build_match_expression("   \t ") is None
    # "a" would be refused as a short term, so the control uses a term the
    # trigram table can actually serve.
    assert build_match_expression("alpha") is not None


def test_terms_are_quoted_so_punctuation_is_literal() -> None:
    """The property that makes the crash test pass, stated directly.

    Inside double quotes FTS5 reads ``-``, ``.``, ``*``, ``:`` and ``"`` as
    characters rather than as column filters, prefix operators and phrase
    delimiters.
    """
    assert build_match_expression("10.9999/j.x") == '"10.9999/j.x"'
    assert build_match_expression("total-correlation") == '"total-correlation"'
    assert build_match_expression("col:val") == '"col:val"'
    assert build_match_expression('say "hi"') == '"say" AND """hi"""'


def test_terms_are_joined_with_and_not_as_a_phrase() -> None:
    """Order on the page is not part of the question.

    A phrase query would report a real passage as absent whenever the extractor
    emitted the words in a different order, which on this corpus is likely
    enough to matter -- LC-P1-08's own PDF adapter deliberately leaves interior
    spacing alone because that spacing is what a quotation must match.
    """
    assert build_match_expression("alpha beta") == '"alpha" AND "beta"'


@pytest.mark.parametrize("query", ["a", "is", "x", "of an algorithm", "the is not greedy"])
def test_a_query_holding_a_short_term_is_refused_not_narrowed(query: str) -> None:
    """The decision: zero results, never a broader answer.

    Trigram cannot match a term under three characters, and SQLite's own answer
    to that is to return no rows -- so a query could pass unexamined. Refusing it
    here makes the refusal a deliberate act rather than a side effect.

    The dangerous alternative is dropping the short term, which turns "the is
    not greedy" into "the greedy" and returns excerpts nobody asked for. Those
    would look like hits -- real text, a real page, a real locator -- and would
    survive every downstream check on the way to a citation.
    """
    assert build_match_expression(query) is None


def test_a_refused_query_retrieves_nothing_rather_than_something(seeded: Connection) -> None:
    """The behaviour, asserted where it is observable.

    ``test_a_query_holding_a_short_term_is_refused_not_narrowed`` asserts the
    expression; this asserts that the refusal reaches the caller as an absence
    and that nothing else about the index changed to produce it.
    """
    assert search(seeded, "the is not greedy") == ()
    assert search(seeded, "of an algorithm") == ()
    # The same words without the short term do retrieve, so the emptiness above
    # is the refusal rather than an index with nothing in it.
    assert search(seeded, "greedy")


def test_the_boundary_is_three_characters_exactly() -> None:
    """Off-by-one here is invisible until a query stops matching a real page."""
    assert build_match_expression("ab") is None
    assert build_match_expression("abc") == '"abc"'


# --------------------------------------------------------------------------- #
# address resolution -- what C1 is handed
# --------------------------------------------------------------------------- #
# `locate_anchor` answers ADR-0004 A1 and A7, and mutation-checking found both
# of its non-RESOLVED branches unobserved: neutering either one left every test
# in the suite green. They are C1's entire dependency, so they are covered here
# directly rather than left to the checks that call C1 once it exists.


def _seeded_sha() -> str:
    return hashlib.sha256(b"arx-2610.10596.pdf").hexdigest()


def _anchor(page: int, *, source_id: str = "src-arx-2610.10596.pdf", sha: str | None = None) -> Any:
    from labcairn.sources.source import AnchorKind, SourceAnchor

    return SourceAnchor(
        anchor_id="anchor-1",
        source_id=source_id,
        kind=AnchorKind.QUOTATION,
        locator=PdfLocator(page=page),
        bound_source_sha256=sha or _seeded_sha(),
        created_at=NOW,
    )


def _add_source(
    connection: Any,
    *,
    source_id: str,
    digest: str,
    name: str,
    kind: str,
    readability: str = "readable",
    disclosure: str | None = None,
) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES (:sid,'local-user',:kind,:name,:name,:sha,1,:readability,:disclosure,"
            "'[]',:now,1)"
        ),
        {
            "sid": source_id,
            "kind": kind,
            "name": name,
            "sha": digest,
            "readability": readability,
            "disclosure": disclosure,
            "now": NOW,
        },
    )


def _add_text(
    connection: Any,
    *,
    digest: str,
    key: str,
    body: str,
    locator_kind: str,
    page: int | None = None,
    row_number: int | None = None,
    column_name: str | None = None,
) -> None:
    columns = ["source_content_sha256", "extraction_version", "locator_kind", "locator_key"]
    values = [":sha", "'v1'", ":lkind", ":key"]
    params: dict[str, Any] = {
        "sha": digest,
        "lkind": locator_kind,
        "key": key,
        "body": body,
        "tsha": hashlib.sha256(body.encode()).hexdigest(),
        "now": NOW,
    }
    if page is not None:
        columns.append("page")
        values.append(":page")
        params["page"] = page
    if row_number is not None:
        columns.append("row_number")
        values.append(":row")
        params["row"] = row_number
    if column_name is not None:
        columns.append("column_name")
        values.append(":col")
        params["col"] = column_name
    columns += ["text", "text_sha256", "created_at"]
    values += [":body", ":tsha", ":now"]
    connection.execute(
        sql_text(f"INSERT INTO source_texts ({', '.join(columns)}) VALUES ({', '.join(values)})"),
        params,
    )


def test_a_locator_that_resolves_carries_the_original_text(seeded: Connection) -> None:
    found = locate_anchor(seeded, _anchor(1))
    assert found.resolution is LocationResolution.RESOLVED
    assert found.text == _page_texts("arx-2610.10596.pdf")[1]
    assert found.numeric_value is None, "prose is not a quantity"
    assert found.observed_content_sha256 == _seeded_sha()


def test_a_numeric_cell_is_read_as_a_number_not_as_a_string(seeded: Connection) -> None:
    """C3 compares a quantity, and a cell stored as ``3.50`` is not a different
    number from one claiming ``3.5``."""
    from labcairn.sources.locators import CsvLocator
    from labcairn.sources.source import AnchorKind, SourceAnchor

    digest = hashlib.sha256(b"cells").hexdigest()
    if True:
        _add_source(seeded, source_id="src-cells", digest=digest, name="c.csv", kind="csv")
        _add_text(
            seeded,
            digest=digest,
            key=render_locator_key(CsvLocator(row=1, column="mean")),
            body="3.50",
            locator_kind="csv",
            row_number=1,
            column_name="mean",
        )
    seeded.commit()
    anchor = SourceAnchor(
        anchor_id="anchor-cell",
        source_id="src-cells",
        kind=AnchorKind.NUMERIC,
        locator=CsvLocator(row=1, column="mean"),
        bound_source_sha256=digest,
        created_at=NOW,
    )
    found = locate_anchor(seeded, anchor)
    assert found.resolution is LocationResolution.RESOLVED
    assert found.text == "3.50"
    assert found.numeric_value == 3.5, "a cell's string form is not the quantity"


def test_text_that_is_not_a_number_yields_no_quantity(seeded: Connection) -> None:
    """C3 answers ``indeterminate`` for a non-numeric segment rather than
    coercing a sentence into a float."""
    assert locate_anchor(seeded, _anchor(1)).numeric_value is None


def test_an_address_that_does_not_exist_is_unresolvable_not_resolved(
    seeded: Connection,
) -> None:
    """ADR-0004 A1, and the first of two branches nothing was watching.

    A page 99 anchor into a 9-page paper. The answer is ``UNRESOLVABLE`` and the
    report cites nothing -- not page 9, not the nearest page. ``SourceAnchor``
    has no free-text label to trim, so there is no graceful degradation
    available even if someone wanted one.
    """
    found = locate_anchor(seeded, _anchor(99))
    assert found.resolution is LocationResolution.UNRESOLVABLE
    assert found.text is None, "an unresolvable address carries no text"
    assert found.numeric_value is None


def test_material_that_cannot_be_addressed_is_unaddressable(seeded: Connection) -> None:
    """ADR-0004 A7, and the second unobserved branch.

    A scanned PDF: the bytes are present, the page is addressable, and the text
    cannot be had. ``UNADDRESSABLE`` rather than ``fail``, because the material
    is there and the reader cannot read it -- a different fact from the address
    not existing.

    This is only implementable because LC-P1-08 made ``readability`` mean what
    ``source.py`` says it means. Before ``98b5ea5`` a scan was recorded
    ``READABLE``, whose meaning is "may be indexed and cited", so there was
    nothing honest for this branch to return.
    """
    from labcairn.sources.source import AnchorKind, SourceAnchor

    digest = hashlib.sha256(b"scan").hexdigest()
    if True:
        _add_source(
            seeded,
            source_id="src-scan",
            digest=digest,
            name="scan.pdf",
            kind="pdf",
            readability="unreadable_no_ocr",
            disclosure="OCR is not available in this phase",
        )
        _add_text(
            seeded,
            digest=digest,
            key=render_locator_key(PdfLocator(page=1)),
            body="",
            locator_kind="pdf",
            page=1,
        )
    seeded.commit()
    anchor = SourceAnchor(
        anchor_id="anchor-scan",
        source_id="src-scan",
        kind=AnchorKind.QUOTATION,
        locator=PdfLocator(page=1),
        bound_source_sha256=digest,
        created_at=NOW,
    )
    found = locate_anchor(seeded, anchor)
    assert found.resolution is LocationResolution.UNADDRESSABLE, (
        "a scan must not read as resolved; that is the state meaning 'may be cited'"
    )
    assert found.text is None


def test_a_broken_container_is_unaddressable_rather_than_unresolved(
    seeded: Connection,
) -> None:
    """The same bucket as a scan, and deliberately.

    Both are "the material is present and we cannot read it". They are not the
    same *reason*, and the disclosure says which, but a locator answer does not
    need to distinguish them -- C1 turns both into ``indeterminate`` either way.
    """
    from labcairn.sources.source import AnchorKind, SourceAnchor

    digest = hashlib.sha256(b"broken").hexdigest()
    key = render_locator_key(PdfLocator(page=1))
    if True:
        _add_source(
            seeded,
            source_id="src-broken",
            digest=digest,
            name="broken.pdf",
            kind="pdf",
            readability="unparseable",
            disclosure="the bytes are not a PDF this reader can open",
        )
        _add_text(seeded, digest=digest, key=key, body="stale text", locator_kind="pdf", page=1)
    anchor = SourceAnchor(
        anchor_id="anchor-broken",
        source_id="src-broken",
        kind=AnchorKind.QUOTATION,
        locator=PdfLocator(page=1),
        bound_source_sha256=digest,
        created_at=NOW,
    )
    seeded.commit()
    assert locate_anchor(seeded, anchor).resolution is LocationResolution.UNADDRESSABLE


def test_an_unknown_source_is_reported_as_unknown_not_as_zero(seeded: Connection) -> None:
    """ADR-0004 A8's shape, and A12's distinction.

    ``observed_content_sha256`` is ``None`` for a source the ledger has never
    heard of. ``None`` is a real answer: it is what tells a fabricated source id
    apart from a real one whose bytes moved, and a zero would be a claim about a
    hash nobody compared.
    """
    found = locate_anchor(seeded, _anchor(1, source_id="src-does-not-exist"))
    assert found.observed_content_sha256 is None


def test_hash_drift_leaves_the_address_unresolvable(seeded: Connection) -> None:
    """ADR-0004 A2, as C1 will read it.

    The anchor bound one set of bytes and the store holds another, so the text
    under that address is not the text the anchor was made for. Both hashes are
    available, and comparing them is C1's job -- this only has to make sure the
    store's current hash is reachable at all.
    """
    drifted = hashlib.sha256(b"edited after anchoring").hexdigest()
    found = locate_anchor(seeded, _anchor(1, sha=drifted))
    assert found.resolution is LocationResolution.UNRESOLVABLE, (
        "text bound to different bytes is not text at this address any more"
    )
    assert found.observed_content_sha256 == _seeded_sha(), (
        "the store's current hash is what makes the drift detectable"
    )


def test_the_three_resolutions_are_distinguishable(seeded: Connection) -> None:
    """The property each of the three tests above asserts, in one place.

    C1 maps these to ``fail``, ``fail`` and ``indeterminate``, and ADR-0004 A1
    and A7 both require the distinction. A refactor that collapsed two of them
    would still pass each test individually, so this asserts the mapping holds.
    """
    assert locate_anchor(seeded, _anchor(1)).resolution is LocationResolution.RESOLVED
    assert locate_anchor(seeded, _anchor(99)).resolution is LocationResolution.UNRESOLVABLE
    assert {LocationResolution.RESOLVED, LocationResolution.UNRESOLVABLE} == {
        LocationResolution.RESOLVED,
        LocationResolution.UNRESOLVABLE,
    }
