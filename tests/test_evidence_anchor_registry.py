"""The anchor registry: the round trip from a rendered key back to a locator.

``locator_from_key`` is the one function in LC-P1-09 whose bug produces no
error. Everything else about an address fails loudly if it is wrong -- the
schema refuses a malformed key, Pydantic refuses a zero page, and
``LocatedContent`` refuses a resolution with no content -- but a locator
rebuilt from the wrong component is still a *valid* locator. It resolves, C1
runs, and the mistake surfaces as "C1 read page 5 instead of page 6" rather
than as anything that looks like a defect.

So most of this file is about the round trip being **exact**, over shapes
chosen to break it rather than to exercise it: a CSV column called ``a|b|c``
and a Markdown section called ``# Task | Model`` both put the renderer's own
separator inside a value, which is the case the length-prefixed encoding in
``material.addressing`` exists for and the case a naive reader gets wrong.

The fixtures here are synthetic and written as literals. That is not a
weakness in this file's favour -- the ledger's job is to answer about
arbitrary stored addresses, and an address a test built by calling the
renderer and then asking whether the renderer round-trips would only prove the
renderer is deterministic.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from conftest import migrated_database_from
from labcairn.db.session import create_db_engine
from labcairn.evidence.cite_support import SourceIndex
from labcairn.evidence.index import (
    LabCairnIndex,
    load_anchor,
    locator_from_key,
    read_content_hash,
)
from labcairn.material.addressing import (
    LocatorKeyError,
    render_locator_key,
    split_locator_key,
)
from labcairn.sources.locators import (
    CsvLocator,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
)
from labcairn.sources.source import AnchorKind, SourceAnchor

pytestmark = pytest.mark.unit

NOW = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)
SHA = "a" * 64
OTHER_SHA = "b" * 64


# --------------------------------------------------------------------------- #
# round trip
# --------------------------------------------------------------------------- #

#: Every shape the renderer can produce, including the two adversarial ones.
#: Written as objects and as their keys side by side on purpose: a test that
#: rendered the key from the locator and compared them would be testing the
#: renderer's determinism, which ``test_addressing.py`` already covers.
ROUND_TRIP: tuple[tuple[SourceLocator, str], ...] = (
    (PdfLocator(page=1), "k=3:pdf|p=1:1"),
    (PdfLocator(page=4), "k=3:pdf|p=1:4"),
    (PdfLocator(page=137), "k=3:pdf|p=3:137"),
    (PdfLocator(page=2, char_start=10, char_end=99), "k=3:pdf|p=1:2|c=5:10-99"),
    (TextLocator(line=1), "k=4:text|l=1:1"),
    (TextLocator(line=7), "k=4:text|l=1:7"),
    (TextLocator(line=7, line_end=9), "k=4:text|l=1:7|le=1:9"),
    (TextLocator(line=7, section="Methods"), "k=4:text|l=1:7|s=7:Methods"),
    (
        TextLocator(line=7, line_end=9, section="Methods"),
        "k=4:text|l=1:7|le=1:9|s=7:Methods",
    ),
    (CsvLocator(row=1, column="mean"), "k=3:csv|r=1:1|c=4:mean"),
    (CsvLocator(row=12, column="std dev"), "k=3:csv|r=2:12|c=7:std dev"),
    (XlsxLocator(sheet_name="S1", cell_ref="B2"), "k=4:xlsx|sh=2:S1|c=2:B2"),
    (
        XlsxLocator(sheet_name="Results 2026", cell_ref="AA100"),
        "k=4:xlsx|sh=12:Results 2026|c=5:AA100",
    ),
    # A value carrying the renderer's own separator, and a key component name
    # carrying none. These are the two cases `split_locator_key`'s docstring
    # says a split-first parser got wrong on 12.7% of real keys.
    (CsvLocator(row=1, column="a|b|c"), "k=3:csv|r=1:1|c=5:a|b|c"),
    (TextLocator(line=3, section="# Task | Model"), "k=4:text|l=1:3|s=14:# Task | Model"),
)


@pytest.mark.parametrize(("locator", "locator_key"), ROUND_TRIP, ids=lambda v: str(v)[:28])
def test_a_key_rebuilds_the_locator_it_was_rendered_from(
    locator: SourceLocator, locator_key: str
) -> None:
    """The exact inverse, asserted both ways.

    Equality alone would pass if the reconstruction invented a field the
    original omitted, so the key is re-rendered from the result as well: two
    renderings agreeing is what makes the pair a bijection rather than a
    function with a faithful-looking inverse.
    """
    assert locator_from_key(locator_key) == locator
    assert render_locator_key(locator_from_key(locator_key)) == locator_key


@pytest.mark.parametrize(("locator", "locator_key"), ROUND_TRIP, ids=lambda v: str(v)[:28])
def test_a_component_containing_the_separator_splits_back_whole(
    locator: SourceLocator, locator_key: str
) -> None:
    """The separator is read where the length prefix says, not by splitting.

    A reader that split on ``|`` first would shred ``c=5:a|b|c`` into three
    components and either raise or, worse, bind ``c`` to ``a``.
    """
    rebuilt = locator_from_key(locator_key)
    assert split_locator_key(locator_key)["k"] == rebuilt.locator_kind.value
    assert render_locator_key(rebuilt) == locator_key


# --------------------------------------------------------------------------- #
# refusals
# --------------------------------------------------------------------------- #

MALFORMED: tuple[tuple[str, str], ...] = (
    ("kind is not a member", "k=3:docx|p=1:4"),
    ("kind is a real LocatorKind with no text", "k=2:computation|p=1:4"),
    ("kind is uppercased", "k=3:PDF|p=1:4"),
    ("kind is empty", "k=0:|p=1:4"),
    ("no kind component at all", "p=1:4"),
    ("pdf missing its page", "k=3:pdf|c=5:10-99"),
    ("pdf page is not a number", "k=3:pdf|p=3:four"),
    ("pdf carries a csv row", "k=3:pdf|p=1:4|r=1:1"),
    ("csv is missing its column", "k=3:csv|r=1:1"),
    ("text is missing its line", "k=4:text|s=7:Methods"),
    ("xlsx is missing its sheet", "k=4:xlsx|c=2:B2"),
    (
        # A length prefix that over-declares swallows the rest of the key, so
        # `k` comes back as "pdf|p=1:4" and the kind check refuses it. This is
        # why there is no separate prefix check in the implementation:
        # split_locator_key enforces the prefix by reading it.
        "a length prefix longer than the value swallows the key",
        "k=9:pdf|p=1:4",
    ),
    ("length prefix is not a digit", "k=x:pdf|p=1:4"),
    ("span has two separators", "k=3:pdf|p=1:2|c=7:10-99-4"),
    ("span has no separator", "k=3:pdf|p=1:2|c=4:1099"),
    ("span end is not a number", "k=3:pdf|p=1:2|c=6:10-nine"),
    ("key is empty", ""),
    ("key has no fields", "|"),
    ("component is not length-prefixed", "k=3:pdf|p=1"),
    ("key ends mid-component", "k=3:pdf|p=9:12345678"),
)


@pytest.mark.parametrize(("why", "locator_key"), MALFORMED, ids=lambda v: str(v)[:28])
def test_a_key_the_renderer_could_not_have_written_is_refused(why: str, locator_key: str) -> None:
    """Everything outside the renderer's grammar raises, and names itself.

    ``LocatorKeyError`` rather than ``ValueError`` or a bare ``KeyError``: the
    caller already handles this type from ``split_locator_key``, because
    ``render_locator_key`` raises it for the mirrored defect. A key that does
    not describe a locator is the same failure in both directions, so it should
    be one type in both.
    """
    with pytest.raises(LocatorKeyError):
        locator_from_key(locator_key)


def test_the_locators_own_validators_are_left_to_speak_for_themselves() -> None:
    """A key that parses but describes something impossible is refused too.

    ``k=3:pdf|p=0:4`` is well-formed and has no page 0. Pre-validating here
    would duplicate ``PdfLocator``'s rules, and a second copy of a rule is the
    thing ADR-0009's canonical key exists to prevent -- so the error comes from
    the model, and it is not a ``LocatorKeyError``.
    """
    with pytest.raises(ValueError):
        locator_from_key("k=3:pdf|p=1:0")


# --------------------------------------------------------------------------- #
# load_anchor
# --------------------------------------------------------------------------- #


#: A module-level default rather than a call in the signature: a Pydantic model
#: built in an argument default is one shared instance across every call.
DEFAULT_LOCATOR: SourceLocator = PdfLocator(page=4)


def _insert_anchor(
    connection: Connection,
    *,
    anchor_id: str = "anchor-1",
    locator: SourceLocator = DEFAULT_LOCATOR,
    kind: str = "quotation",
    bound: str = SHA,
) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES (:aid,'src-1',:kind,:key,:bound,:excerpt,:now)"
        ),
        {
            "aid": anchor_id,
            "kind": kind,
            "key": render_locator_key(locator),
            "bound": bound,
            "excerpt": OTHER_SHA,
            "now": NOW,
        },
    )


@pytest.fixture()
def registry(migrated_database_template: Path, tmp_path: Path) -> Iterator[Connection]:
    target = tmp_path / "registry.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    connection = engine.connect()
    with connection.begin():
        yield connection


@pytest.mark.parametrize(("locator", "locator_key"), ROUND_TRIP, ids=lambda v: str(v)[:28])
def test_load_anchor_rebuilds_every_locator_kind(
    registry: Connection, locator: SourceLocator, locator_key: str
) -> None:
    """End to end through the database, not just the pure function.

    The interesting failure this catches is a row whose *stored* key and whose
    rebuilt locator disagree about which kind they are -- which a test that
    inserts the key it already holds cannot see, because it never involves the
    renderer.
    """
    _insert_anchor(registry, anchor_id=f"a-{locator.locator_kind.value}", locator=locator)
    loaded = load_anchor(registry, f"a-{locator.locator_kind.value}")
    assert loaded is not None
    assert loaded.locator == locator
    assert render_locator_key(loaded.locator) == locator_key


def test_load_anchor_carries_every_field_the_anchor_binds(registry: Connection) -> None:
    """An anchor is more than its address, and the rest of it round-trips too.

    ``bound_source_sha256`` in particular: it is the source's hash *as it was
    when the anchor was made*, which is the whole input to ADR-0004 A2's drift
    check. Reading it as the source's hash *now* would make drift detection
    impossible -- the comparison would always agree with itself.
    """
    _insert_anchor(registry, kind="numeric", bound=SHA)
    loaded = load_anchor(registry, "anchor-1")
    assert loaded is not None
    assert loaded == SourceAnchor(
        anchor_id="anchor-1",
        source_id="src-1",
        kind=AnchorKind.NUMERIC,
        locator=PdfLocator(page=4),
        bound_source_sha256=SHA,
        excerpt_sha256=OTHER_SHA,
        created_at=NOW,
    )


def test_the_bound_hash_is_read_from_the_anchor_and_not_from_the_source(
    registry: Connection,
) -> None:
    """The whole point of ``bound_source_sha256``, asserted against a drifted source.

    A ``sources`` row is written holding a *different* hash, so reading the
    source's current hash instead of the anchor's bound one is observable.
    Without that row the two are indistinguishable -- the test would pass
    against an implementation that joined through ``sources``, because there is
    nothing to join to.

    This is what makes ADR-0004 A2's drift check possible at all. If the bound
    hash were refreshed to the source's current hash, C1's comparison would
    always agree with itself and no drift could ever be reported.
    """
    registry.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name,"
            " relative_path, content_sha256, size_bytes, readability,"
            " readability_disclosure, identifiers, ingested_at, schema_version)"
            " VALUES ('src-1','local-user','pdf','a.pdf','a.pdf',:sha,1,'readable',"
            "NULL,'[]',:now,1)"
        ),
        {"sha": OTHER_SHA, "now": NOW},
    )
    _insert_anchor(registry, anchor_id="drifted", bound=SHA)

    loaded = load_anchor(registry, "drifted")
    assert loaded is not None
    assert loaded.bound_source_sha256 == SHA
    assert loaded.bound_source_sha256 != read_content_hash(registry, "src-1")


def test_an_anchor_id_the_ledger_has_never_heard_of_is_none(registry: Connection) -> None:
    """ADR-0004 A12: the fabricated source, and it is a real answer.

    ``None`` and not an exception, and not a locator guessed from the id: an
    id that names nothing must not be turned into an address, because an
    invented address is indistinguishable from a real one everywhere downstream.
    """
    _insert_anchor(registry)
    assert load_anchor(registry, "never-existed") is None
    assert load_anchor(registry, "") is None
    # Near-misses are still misses. A prefix match would be a lookup that
    # invents.
    assert load_anchor(registry, "anchor-") is None
    assert load_anchor(registry, "anchor-12") is None
    assert load_anchor(registry, "ANCHOR-1") is None


def test_a_corrupt_row_is_not_reported_as_an_unknown_id(registry: Connection) -> None:
    """The two failures stay apart, because they are different findings.

    ``None`` says the ledger has never heard of this anchor. A row whose key
    cannot be rebuilt says the ledger has something and it is broken. Both make
    C1 answer ``fail``, but a report that cannot tell them apart will eventually
    call one the other -- and "we never had that source" and "our record of that
    source is damaged" call for different repairs.
    """
    # Written past the schema's CHECK, which is what makes the distinction
    # worth testing: the GLOB vocabulary guard is on the length-prefixed
    # prefix, and this key has a legal prefix with a body it cannot describe.
    registry.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('broken','src-1','quotation','k=3:pdf|c=5:10-99',:bound,NULL,:now)"
        ),
        {"bound": SHA, "now": NOW},
    )
    with pytest.raises(LocatorKeyError):
        load_anchor(registry, "broken")


def test_labcairn_index_satisfies_the_protocol(registry: Connection) -> None:
    """The Protocol is a description until something satisfies it.

    ``runtime_checkable`` checks member *names*, so this cannot prove the
    implementations are right. It can prove the seam exists, which is what
    stops a duck-typed stand-in from reaching C1 unnoticed.
    """
    assert isinstance(LabCairnIndex(registry), SourceIndex)


def test_the_index_routes_to_the_same_functions_the_registry_does(registry: Connection) -> None:
    """One implementation, reached two ways, agreeing.

    A wrapper that re-implemented a query is how ``locate`` and ``load_anchor``
    would end up reading different stores, which no single-member test sees.
    """
    _insert_anchor(registry)
    index = LabCairnIndex(registry)
    assert index.load_anchor("anchor-1") == load_anchor(registry, "anchor-1")
    assert index.load_anchor("never-existed") is None
    assert index.content_hash("src-1") is None
    assert index.content_hash("no-such-source") is None
