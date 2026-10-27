"""Building the index from the store, over the real papers.

Two shapes of test, and the split is deliberate.

**The real corpus** -- three CC-BY papers, 70 pages -- carries the property
that matters most: the whole path runs in about four seconds (measured:
``ingest_workspace`` 3.98s, the readable join instant, 70 index rows 0.02s), so
these tests use it rather than a reduced fixture. It is what proves a rebuild
over real extracted text, with real locators, is idempotent and complete.

**A synthetic unreadable source** carries the property the corpus cannot. Every
one of the 70 rows in the fixtures belongs to a readable source, so A7's
exclusion rule has **no negative case in the real material** -- it has never
been shown to exclude anything. A rule that has not seen the thing it excludes
has not been shown to exclude it, and the difference between "covered" and
"exercised" is what that last sentence means.

Drifted text is the third case, and it is synthetic too: no fixture has been
edited after extraction, which is what drift *is*.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.core.ids import TaskId, new_id
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.evidence.index import search
from labcairn.material.indexing import build_index, index_state
from labcairn.material.walk import ingest_workspace
from labcairn.workspace.readonly import SourceMaterial
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.integration

PAPERS = pathlib.Path(__file__).parent / "fixtures" / "papers"
NOW = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)


def _allowing_policy() -> Any:
    from labcairn.security.capabilities import CapabilityId
    from labcairn.security.policy import Permission, PermissionPolicy, Rule

    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


@pytest.fixture(scope="module")
def ingested(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Connection]:
    """A store holding the three real papers, walked and ingested."""
    root = tmp_path_factory.mktemp("corpus") / "ws"
    sources = root / "sources"
    sources.mkdir(parents=True)
    for pdf in sorted(PAPERS.glob("*.pdf")):
        (sources / pdf.name).write_bytes(pdf.read_bytes())

    target = tmp_path_factory.mktemp("corpus") / "corpus.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    session = create_session_factory(engine)()

    workspace = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    report = ingest_workspace(
        session, SourceMaterial(workspace, _allowing_policy()), ingested_at=NOW
    )
    session.commit()
    assert report.failures == (), [message for _, message in report.failures]
    assert len(report.outcomes) == 3

    connection = engine.connect()
    yield connection
    connection.close()
    session.close()
    engine.dispose()


def _add_source(
    connection: Connection,
    *,
    source_id: str,
    digest: str,
    name: str,
    kind: str,
    readability: str,
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
    connection: Connection, *, digest: str, key: str, body: str, kind: str = "pdf"
) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, page, text, text_sha256, created_at)"
            " VALUES (:sha,'v1',:kind,:key,1,:body,:tsha,:now)"
        ),
        {
            "sha": digest,
            "kind": kind,
            "key": key,
            "body": body,
            "tsha": hashlib.sha256(body.encode()).hexdigest(),
            "now": NOW,
        },
    )


@pytest.fixture
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Connection]:
    """A store with one readable source, one unreadable and one drifted.

    Built by hand because the corpus cannot supply two of the three cases:
    it holds no unreadable material and nothing has been edited after
    extraction.
    """
    target = tmp_path_factory.mktemp("synthetic") / "synthetic.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    connection = engine.connect()
    connection.commit()
    yield connection
    connection.close()
    engine.dispose()


# --------------------------------------------------------------------------- #
# the real corpus
# --------------------------------------------------------------------------- #


def test_a_first_build_indexes_every_readable_page(ingested: Connection) -> None:
    build = build_index(ingested)
    ingested.commit()
    stored: int = ingested.execute(sql_text("SELECT COUNT(*) FROM source_texts")).scalar_one()
    assert build.indexed == stored, "every extracted page of a readable paper belongs in the index"
    assert build.excluded_reasons == {}, "nothing in this corpus is unreadable"


def test_a_rebuild_is_idempotent(ingested: Connection) -> None:
    """The property that makes the index safe to rebuild rather than patch.

    ``evidence_fts`` has no unique constraint, so a second build over the same
    rows would silently double the index and make every hit appear twice --
    with no error anywhere. ADR-0009's key discipline is what prevents that,
    and it only prevents it if the rebuild is actually checked.
    """
    build_index(ingested)
    ingested.commit()
    first: int = ingested.execute(sql_text("SELECT COUNT(*) FROM evidence_fts")).scalar_one()

    build_index(ingested)
    ingested.commit()
    second: int = ingested.execute(sql_text("SELECT COUNT(*) FROM evidence_fts")).scalar_one()

    assert second == first, "a rebuild doubled the index"


def test_rebuilding_reports_nothing_stale(ingested: Connection) -> None:
    """After a rebuild the index cannot disagree with its authority.

    This is the asymmetry that matters: an index carrying a row whose text no
    longer exists has the same shape as a correct hit, so drift has to be
    countable rather than merely unlikely.
    """
    build_index(ingested)
    ingested.commit()
    build = build_index(ingested)
    ingested.commit()
    assert build.removed_stale == 0
    assert index_state(ingested)["complete"] is True


def test_a_search_over_the_built_index_finds_a_real_passage(ingested: Connection) -> None:
    """The whole path, end to end, on real extracted text.

    Walk, ingest, index, retrieve. Every earlier stage is covered elsewhere;
    what this asserts is that the stages compose -- a query that works against
    hand-seeded rows proves nothing about what the walk actually produced.
    """
    build_index(ingested)
    ingested.commit()
    hits = search(ingested, "customary greedy selection rule")
    assert hits, "the walk's own text was not findable through the index"
    assert any(hit.locator_kind == "pdf" for hit in hits)
    assert any("greedy" in hit.text.lower() for hit in hits)


def test_what_the_index_holds_is_the_normalised_copy(synthetic: Connection) -> None:
    """What is **in** the index, which is a different question from what a hit
    returns.

    An earlier version of this test asserted that a hit's text has no doubled
    spaces and called it "the index never holds the normalised copy". It proved
    nothing: a hit re-reads ``source_texts`` regardless of what was written
    into ``evidence_fts``, so writing raw text into the index left it green.
    Mutation-checking the builder is what caught it.

    Synthetic rather than the real corpus, and the reason is measured: across
    all three fixture papers there is **not one line containing doubled
    whitespace**, so whitespace normalisation is a no-op on this material and
    no assertion over it can tell a normalised copy from a raw one. That is a
    property of the corpus, not a gap in the normalisation.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    digest = hashlib.sha256(b"spacing").hexdigest()
    body = "leading  doubled   spacing and a  tab	here"
    _add_source(
        synthetic,
        source_id="src-spacing",
        digest=digest,
        name="s.pdf",
        kind="pdf",
        readability="readable",
    )
    _add_text(synthetic, digest=digest, key=render_locator_key(PdfLocator(page=1)), body=body)
    synthetic.commit()

    build_index(synthetic)
    synthetic.commit()

    held: str = synthetic.execute(sql_text("SELECT normalized_text FROM evidence_fts")).scalar_one()
    assert held == "leading doubled spacing and a tab here", (
        "the index holds the raw text, so a query matches on spacing the "
        f"extracted text does not have: {held!r}"
    )
    assert synthetic.execute(sql_text("SELECT text FROM source_texts")).scalar_one() == body, (
        "normalisation must not reach source_texts; it is an index-side copy"
    )


def test_normalisation_changes_every_row_of_this_corpus(synthetic: Connection) -> None:
    """What normalisation actually does here, measured rather than assumed.

    The obvious guess was whitespace, and it is wrong for this corpus: across
    all three fixture papers there is **not one line containing doubled
    whitespace**, so collapsing it changes nothing. What does change every row
    is NFKC -- the ligatures and compatibility forms ADR-0008 measured, which
    is precisely why T03 needed a trigram tokenizer to find words inside them.

    So this asserts the difference is real and is *not* whitespace, which is
    what stops a reader concluding from the corpus alone that normalisation is
    a no-op here.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    digest = hashlib.sha256(b"nfkc").hexdigest()
    _add_source(
        synthetic,
        source_id="src-nfkc",
        digest=digest,
        name="n.pdf",
        kind="pdf",
        readability="readable",
    )
    _add_text(
        synthetic,
        digest=digest,
        key=render_locator_key(PdfLocator(page=1)),
        body="the ﬁ ligature and a ① circled digit",
    )
    synthetic.commit()

    build_index(synthetic)
    synthetic.commit()

    original: str = synthetic.execute(sql_text("SELECT text FROM source_texts")).scalar_one()
    held: str = synthetic.execute(sql_text("SELECT normalized_text FROM evidence_fts")).scalar_one()
    assert held == "the fi ligature and a 1 circled digit"
    assert original == "the ﬁ ligature and a ① circled digit", (
        "the stored text was rewritten; normalisation is an index-side copy"
    )


def test_the_real_corpus_is_affected_by_normalisation(ingested: Connection) -> None:
    """70 of 70, and the count is the point.

    An earlier version of this test asserted the corpus was *unaffected*,
    reasoning from doubled whitespace. That was wrong: whitespace is a no-op
    here and NFKC is not, so all 70 rows differ. Written down because the
    opposite assumption is the easy one to reach.
    """
    build_index(ingested)
    ingested.commit()
    differing = int(
        ingested.execute(
            sql_text(
                "SELECT COUNT(*) FROM source_texts AS t JOIN evidence_fts AS f"
                "  ON f.source_content_sha256 = t.source_content_sha256"
                " AND f.extraction_version = t.extraction_version"
                " AND f.locator_key = t.locator_key"
                " WHERE f.normalized_text <> t.text"
            )
        ).scalar_one()
    )
    stored = int(ingested.execute(sql_text("SELECT COUNT(*) FROM source_texts")).scalar_one())
    assert differing == stored, (
        f"expected every row of this corpus to change under NFKC, and {differing} of {stored} did"
    )
    doubled = int(
        ingested.execute(
            sql_text("SELECT COUNT(*) FROM evidence_fts WHERE normalized_text LIKE '%  %'")
        ).scalar_one()
    )
    assert doubled == 0, "whitespace collapsing is a no-op here, so none should remain"


# --------------------------------------------------------------------------- #
# A7 -- unreadable material, which the corpus cannot supply
# --------------------------------------------------------------------------- #


def test_unreadable_material_is_excluded_from_the_index(synthetic: Connection) -> None:
    """ADR-0004 A7, over a source the corpus does not contain.

    A scan: the bytes are present, the pages are addressable, and the text
    cannot be had. The exclusion is unconditional and unlike drift -- there is
    no case for indexing it with a caveat, because an unreadable page must be
    neither findable nor citable.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    readable = hashlib.sha256(b"readable").hexdigest()
    scanned = hashlib.sha256(b"scanned").hexdigest()
    key = render_locator_key(PdfLocator(page=1))

    _add_source(
        synthetic,
        source_id="src-ok",
        digest=readable,
        name="ok.pdf",
        kind="pdf",
        readability="readable",
    )
    _add_text(synthetic, digest=readable, key=key, body="a page the project can read")
    _add_source(
        synthetic,
        source_id="src-scan",
        digest=scanned,
        name="scan.pdf",
        kind="pdf",
        readability="unreadable_no_ocr",
        disclosure="OCR is not available in this phase",
    )
    _add_text(synthetic, digest=scanned, key=key, body="text no OCR could recover")
    synthetic.commit()

    build = build_index(synthetic)
    synthetic.commit()

    assert build.excluded_reasons.get("source_unreadable") == 1, (
        "the exclusion was not reported, so an empty search could not be read"
    )
    assert search(synthetic, "project"), "readable material was not indexed"
    assert not search(synthetic, "recover"), (
        "the unreadable page was indexed -- its text says 'no OCR could recover'"
    )


def test_a_broken_container_is_excluded_the_same_way(synthetic: Connection) -> None:
    """Same bucket, different reason, and the disclosure is what distinguishes
    them -- which is why the exclusion is counted rather than assumed."""
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    broken = hashlib.sha256(b"broken").hexdigest()
    _add_source(
        synthetic,
        source_id="src-broken",
        digest=broken,
        name="b.pdf",
        kind="pdf",
        readability="unparseable",
        disclosure="the bytes are not a PDF this reader can open",
    )
    _add_text(
        synthetic,
        digest=broken,
        key=render_locator_key(PdfLocator(page=1)),
        body="stale text from a container that would not open",
    )
    synthetic.commit()

    build = build_index(synthetic)
    synthetic.commit()
    assert build.excluded_reasons.get("source_unreadable") == 1
    assert not search(synthetic, "stale")


# --------------------------------------------------------------------------- #
# drift -- also synthetic, because no fixture has been edited
# --------------------------------------------------------------------------- #


def test_drifted_text_is_indexed_and_marked_as_drifted(synthetic: Connection) -> None:
    """ADR-0004 A2 with the choice made explicit.

    The old rows stay in ``source_texts`` after an edit (ADR-0009), and they
    are indexed here -- because dropping them would make a passage that
    genuinely was written unfindable, surfacing as A6's "the material does not
    say that" when the truth is "it said so and has since changed".

    What must not happen is that it looks current, and that is what
    ``Hit.is_drifted`` is for.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    old = hashlib.sha256(b"version one").hexdigest()
    new = hashlib.sha256(b"version two").hexdigest()
    key = render_locator_key(PdfLocator(page=1))

    _add_source(
        synthetic,
        source_id="src-file",
        digest=new,
        name="f.pdf",
        kind="pdf",
        readability="readable",
    )
    _add_text(synthetic, digest=new, key=key, body="the current version of the passage")
    _add_text(synthetic, digest=old, key=key, body="the superseded version of the passage")
    synthetic.commit()

    build = build_index(synthetic)
    synthetic.commit()
    assert build.excluded_reasons == {}, "drift is not an exclusion; only unreadability is"

    hits = {hit.text: hit for hit in search(synthetic, "version")}
    assert len(hits) == 2, "one of the two versions was dropped"

    current = hits["the current version of the passage"]
    drifted = hits["the superseded version of the passage"]
    assert current.is_drifted is False
    assert drifted.is_drifted is True, (
        "drifted text was indexed without saying so; it carries a real page and "
        "a real locator, so every downstream check would pass and the citation "
        "would read as though the file still said it"
    )
    assert current.source_ids == ("src-file",)
    assert drifted.source_ids == ()


def test_drift_is_visible_without_consulting_source_ids(synthetic: Connection) -> None:
    """The property is named, not inferred.

    An empty ``source_ids`` is the mechanism; a caller reading
    ``if not hit.source_ids`` has to know to look at all.
    """
    assert search is not None  # the module is what provides Hit
    from labcairn.evidence.index import Hit

    assert Hit(
        source_content_sha256="a" * 64,
        extraction_version="v1",
        locator_key="k=3:pdf|p=1:1",
        locator_kind="pdf",
        text="x",
        source_ids=(),
    ).is_drifted
    assert not Hit(
        source_content_sha256="a" * 64,
        extraction_version="v1",
        locator_key="k=3:pdf|p=1:1",
        locator_kind="pdf",
        text="x",
        source_ids=("src-1",),
    ).is_drifted


def test_a_drifted_row_does_not_break_a_rebuild(synthetic: Connection) -> None:
    """Drift is not staleness.

    A row whose source has gone is still a row ``source_texts`` holds, so a
    rebuild keeps it and reports nothing removed. Conflating the two would make
    a changed file look like a corrupt index.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    old = hashlib.sha256(b"gone").hexdigest()
    _add_text(
        synthetic,
        digest=old,
        key=render_locator_key(PdfLocator(page=1)),
        body="text whose source no longer exists",
    )
    synthetic.commit()

    build = build_index(synthetic)
    synthetic.commit()
    assert build.removed_stale == 0, (
        "a drifted row was reported as stale, which is a different and wrong claim"
    )
    assert build.indexed == 1


def test_a_row_the_store_no_longer_holds_is_reported_as_stale(synthetic: Connection) -> None:
    """``removed_stale`` is the only signal that the index and the store have
    parted company, and it needs a case of its own.

    A drifted row is **not** stale -- the store still holds it, and confusing
    the two would make an edited file look like a corrupt index. Stale is the
    other case: an index row whose ``(sha, version, locator_key)`` is in
    neither ``source_texts`` nor any source. That happens when text is removed
    from the store, and nothing else reports it.
    """
    from labcairn.material.addressing import render_locator_key
    from labcairn.sources.locators import PdfLocator

    digest = hashlib.sha256(b"vanishing").hexdigest()
    key = render_locator_key(PdfLocator(page=1))
    _add_source(
        synthetic,
        source_id="src-vanishing",
        digest=digest,
        name="v.pdf",
        kind="pdf",
        readability="readable",
    )
    _add_text(synthetic, digest=digest, key=key, body="text that will be withdrawn")
    synthetic.commit()

    build_index(synthetic)
    synthetic.commit()
    assert build_index(synthetic).removed_stale == 0, "nothing has been withdrawn yet"

    synthetic.execute(
        sql_text("DELETE FROM source_texts WHERE source_content_sha256 = :sha"),
        {"sha": digest},
    )
    synthetic.commit()

    assert build_index(synthetic).removed_stale == 1, (
        "a row the store no longer holds was not reported as stale"
    )
