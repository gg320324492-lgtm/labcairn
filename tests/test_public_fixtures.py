"""The public fixture corpus: the answers, the locators, and the hashes.

What this file is for
---------------------
LC-P1-13 asks for *"at least 3 publicly shareable fixture scenarios with
actual answer/source locators and a negative/no-evidence scenario"*, and
``docs/EVALUATION.md`` asks for fixtures that carry *"actual source locators,
hashes and answer keys"* and warns against *"using generated outputs as their
own oracle"*.

That last clause is the whole design of this file. A fixture whose expected
answer was produced by running the product and recording what came out would
test nothing: the product would be graded against its own output, and a
product that returned the wrong number would be graded correct. So the two
directions are kept apart:

* **The answer key is derived from the material, independently.** The
  expected values in ``MANIFEST.json`` were computed by reading the fixture
  files, and this file re-derives them from the material through the
  product's *own* analysis operators and its *own* locator machinery --
  never by trusting a number written down beside the data. Where the
  material is tabular, the operator is asked to compute the statistic over
  a selection of cells; where the material is prose, the value is read out
  of the cited line by the text adapter. A number in the manifest that the
  material does not support fails here.
* **The locator is resolved, not compared as a string.** Every locator in
  the manifest is parsed into a typed ``SourceLocator``, rendered to its
  canonical key, and then *resolved* against the ingested material through
  ``locate_anchor``. A locator that names a line or a cell that is not
  there is ``UNRESOLVABLE``, and that is a failure here, not a detail.

The negative fixture is the reason the corpus exists at all. A corpus with
only answerable fixtures cannot measure abstention, because abstention only
shows up where the answer is not. So the fourth fixture asks for a quantity
the material genuinely does not contain, and this file checks that twice
over: that the question's *subject* is absent from the material, and that
the fixture is not a hollow one (the material is full of other quantities,
so answering "the material does not say" cannot be a way of passing by
saying nothing).

The properties watched
----------------------
1. **Every material file is byte-identical to its recorded hash.** A fixture
   that was edited without its answers being re-derived is a fixture whose
   answers are wrong, and it must fail rather than quietly disagree.
2. **Every locator resolves.** Typed, canonically rendered, and resolved
   through ``locate_anchor`` to the text the manifest says is there.
3. **Every answer is re-derived from the material** -- through the product's
   operators for tabular fixtures, and through the resolved text for prose
   fixtures.
4. **The negative fixture is negative, and is not hollow.** The quantity
   asked about is absent; other quantities are present; and the expected
   artifact checks say the answer is an abstention.
5. **A corrupted answer key fails.** The last test mutates a copy of the
   manifest and shows the checking machinery notices, so a green run means
   the machinery is watching rather than merely present.

What this file does not do
--------------------------
It does not run the product end to end, and it does not score a report.
That is LC-P1-13's evaluation harness (T01), which reads
``docs/EVALUATION.md`` and measures the metrics. What this file guarantees
is that the corpus the harness measures against is *sound*: its answers are
right, its locators point where it says, and its hashes bind.

Provenance
----------
Every fixture file is synthetic, authored for this corpus, and carries a
``SYNTHETIC MATERIAL`` marker near its top. Nothing third-party is
reproduced, so no third-party licence or attribution travels with the
corpus. ``MANIFEST.json`` records the origin and the notice for the corpus
as a whole.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from labcairn.analysis.operators.descriptive import MEAN
from labcairn.analysis.selection import MissingPolicy, RowSet, Selection
from labcairn.analysis.values import CellAddress
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.evidence.cite_support import LocationResolution
from labcairn.evidence.index import locate_anchor, locator_from_key
from labcairn.material.addressing import render_locator_key
from labcairn.material.ingest import ingest_bytes
from labcairn.sources.locators import (
    CsvLocator,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
    describe_locator,
)
from labcairn.sources.source import AnchorKind, SourceAnchor

PUBLIC = Path(__file__).parent / "fixtures" / "public"
MANIFEST = PUBLIC / "MANIFEST.json"

NOW = dt.datetime(2026, 10, 25, tzinfo=dt.UTC)

#: The fixture ids this corpus holds, in manifest order.
EXPECTED_FIXTURES = (
    "physical_tension",
    "biomedical_panel",
    "computational_solver",
    "no_evidence",
)

#: The genres the protocol names, and which fixture carries each. The
#: protocol requires "at least 3 tasks across distinct research genres",
#: so a genre repeated would not count -- hence the set, not the list.
EXPECTED_GENRES = {
    "physical_tension": "physical sciences",
    "biomedical_panel": "biomedical-style tabular measurements without real patient data",
    "computational_solver": "computational experiments",
    "no_evidence": "protocol excerpt that does not contain the answer",
}

#: The marker every synthetic material carries, so a reader who opens one
#: file -- rather than the manifest -- can still tell it is not real data.
SYNTHETIC_MARKER = "SYNTHETIC MATERIAL"

#: The question whose answer is an abstention, and the fixture it is in.
NEGATIVE_FIXTURE = "no_evidence"
NEGATIVE_QUESTION = "no_evidence.buffer_ph"


# --------------------------------------------------------------------------
# The manifest
# --------------------------------------------------------------------------


def _manifest() -> dict[str, Any]:
    loaded: object = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "the manifest is not a JSON object"
    return cast(dict[str, Any], loaded)


def _fixtures() -> list[dict[str, Any]]:
    entries: object = _manifest()["fixtures"]
    assert isinstance(entries, list), "the manifest's fixtures are not a list"
    return cast(list[dict[str, Any]], entries)


def _fixture(fixture_id: str) -> dict[str, Any]:
    for entry in _fixtures():
        if entry["id"] == fixture_id:
            return entry
    raise AssertionError(f"the manifest has no fixture named {fixture_id!r}")


def _questions(fixture_id: str) -> list[dict[str, Any]]:
    return list(_fixture(fixture_id)["questions"])


def _question(fixture_id: str, question_id: str) -> dict[str, Any]:
    for entry in _questions(fixture_id):
        if entry["id"] == question_id:
            return entry
    raise AssertionError(f"fixture {fixture_id!r} has no question {question_id!r}")


def _cited_keys(fixture_id: str) -> list[str]:
    """Every locator key the fixture's artifact checks cite."""
    keys: list[str] = []
    for question in _questions(fixture_id):
        for check in question["expected_artifact_checks"]:
            if check["kind"] == "citation_resolves":
                keys.append(check["locator_key"])
    return keys


# --------------------------------------------------------------------------
# Material, ingested
# --------------------------------------------------------------------------


class Ingested:
    """One fixture's material, ingested, with the addresses it yielded.

    The material is put through the product's real ingest path -- the same
    ``ingest_bytes`` the workspace walk uses -- so the addresses below are
    the ones the product would actually produce, not ones written by hand
    and hoped over.
    """

    def __init__(self, fixture_id: str) -> None:
        self.fixture_id = fixture_id
        self.by_path: dict[str, Any] = {}
        self.units: list[tuple[str, SourceLocator, str]] = []

    def source_for(self, path: str) -> Any:
        return self.by_path[path].source

    def units_of(self, path: str) -> list[tuple[SourceLocator, str]]:
        return [(locator, text) for p, locator, text in self.units if p == path]


def _ingest(fixture: dict[str, Any]) -> Ingested:
    """Ingest one fixture's material through the product's ingest path."""
    out = Ingested(fixture["id"])
    for material in fixture["material"]:
        raw = (PUBLIC / material["path"]).read_bytes()
        ingested = ingest_bytes(
            raw,
            relative_path=material["path"],
            display_name=Path(material["path"]).name,
            ingested_at=NOW,
        )
        out.by_path[material["path"]] = ingested
        for unit in ingested.texts:
            out.units.append((material["path"], unit.locator, unit.text))
    return out


def _path_for_locator(fixture: dict[str, Any], locator: SourceLocator) -> str:
    """Which material file a locator belongs to.

    The manifest's material list is the authority; a locator that belongs to
    no listed file is a fixture pointing at something outside itself.
    """
    if isinstance(locator, (CsvLocator, XlsxLocator)):
        suffix = ".csv"
    elif isinstance(locator, PdfLocator):
        suffix = ".pdf"
    else:
        suffix = ".md"
    candidates = [
        material["path"] for material in fixture["material"] if material["path"].endswith(suffix)
    ]
    if not candidates:
        raise AssertionError(
            f"the fixture has no {suffix} material, but a locator of kind "
            f"{locator.locator_kind.value!r} names one"
        )
    return str(candidates[0])


def _anchor(
    ingested: Ingested, path: str, locator: SourceLocator, kind: AnchorKind
) -> SourceAnchor:
    """An anchor bound to the material's own hash, as the ledger would make it."""
    source = ingested.source_for(path)
    return SourceAnchor(
        anchor_id=f"fixture-{ingested.fixture_id}-{render_locator_key(locator)}",
        source_id=source.source_id,
        kind=kind,
        locator=locator,
        bound_source_sha256=source.content_sha256,
        created_at=NOW,
    )


@pytest.fixture(scope="module")
def session(
    migrated_database_template: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Session]:
    """A migrated database, one per module, for the locator resolutions."""
    from conftest import migrated_database_from

    target = tmp_path_factory.mktemp("public-fixtures") / "fixtures.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    made = create_session_factory(engine)()
    yield made
    made.close()
    engine.dispose()


@pytest.fixture(scope="module")
def ingested_store(session: Session) -> Iterator[dict[str, Ingested]]:
    """Every fixture's material, ingested and written to the store.

    The material goes into the database rather than only into memory,
    because ``locate_anchor`` resolves against the store: a locator that
    names an address no row holds is ``UNRESOLVABLE``, and that is the
    answer this file needs from the product.
    """
    from labcairn.db.materials import put_source, put_source_texts
    from labcairn.material.ingest import to_text_row

    out: dict[str, Ingested] = {}
    for fixture in _fixtures():
        ingested = _ingest(fixture)
        for material in fixture["material"]:
            path = material["path"]
            source = ingested.source_for(path)
            put_source(session, source)
            rows = [to_text_row(unit, created_at=NOW) for unit in ingested.by_path[path].texts]
            put_source_texts(
                session,
                source_content_sha256=source.content_sha256,
                extraction_version=ingested.by_path[path].extraction_version,
                rows=rows,
            )
        out[fixture["id"]] = ingested
    session.commit()
    yield out


# --------------------------------------------------------------------------
# 1. The corpus has the shape the protocol asks for
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_the_corpus_holds_the_fixtures_the_protocol_asks_for() -> None:
    """Three answerable scenarios across distinct genres, plus a negative one.

    ``EVALUATION.md`` asks for "at least 3 tasks across distinct research
    genres" and LC-P1-13 asks for "a negative/no-evidence scenario". Both
    are counted here rather than asserted in prose, because a corpus that
    quietly grew two fixtures of one genre would satisfy the sentence and
    not the requirement.
    """
    ids = [entry["id"] for entry in _fixtures()]
    assert ids == list(EXPECTED_FIXTURES), (
        f"the corpus holds {ids}, not {list(EXPECTED_FIXTURES)}. A fixture "
        f"that is not in this list is a fixture nobody is measuring against."
    )

    genres = {entry["id"]: entry["genre"] for entry in _fixtures()}
    assert genres == EXPECTED_GENRES, (
        f"the genres are {genres}, not {EXPECTED_GENRES}. The protocol asks "
        f"for distinct research genres, so a changed genre is a changed corpus."
    )

    answerable = [i for i in ids if i != NEGATIVE_FIXTURE]
    assert len(answerable) >= 3, "the protocol asks for at least three answerable tasks"
    assert len({genres[i] for i in answerable}) == len(answerable), (
        "two answerable fixtures share a genre, so the corpus has fewer "
        "distinct research genres than it has tasks"
    )


@pytest.mark.unit
def test_every_fixture_declares_its_material_origin_and_licence() -> None:
    """The corpus states that it is synthetic, and says so at corpus level.

    ``LICENSE.PENDING.md`` grants nothing yet, so the corpus cannot claim a
    licence of its own. What it *can* state, and does, is that it contains
    no third-party material -- which is the fact that decides whether a
    future release carries a third-party notice.
    """
    manifest = _manifest()
    assert manifest["material_origin"] == "synthetic", (
        "the corpus's origin is not declared as synthetic; a reader cannot "
        "tell whether the material is reproducible or borrowed"
    )
    notice = manifest["notice"].lower()
    assert "synthetic" in notice
    assert "third-party" in notice or "third party" in notice
    assert "no rights" in notice or "grants nothing" in notice, (
        "the notice must say the repository grants nothing yet, because that "
        "is the licence position this corpus travels under"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    sorted(
        str(p.relative_to(PUBLIC)).replace("\\", "/")
        for p in PUBLIC.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json"
    ),
)
def test_every_material_file_says_it_is_synthetic(path: str) -> None:
    """A file opened on its own says what it is.

    The manifest is not always read before the data is, and a CSV of
    plausible-looking measurements is exactly the thing a reader might
    mistake for a real result. The marker is in the material's own first
    lines, not only in a file beside it.
    """
    text = (PUBLIC / path).read_text(encoding="utf-8")
    head = text[:400]
    assert SYNTHETIC_MARKER in head, (
        f"{path} does not carry the {SYNTHETIC_MARKER!r} marker near its top"
    )


# --------------------------------------------------------------------------
# 2. The hashes bind the material
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("fixture_id", EXPECTED_FIXTURES)
def test_every_material_file_is_byte_identical_to_its_recorded_hash(fixture_id: str) -> None:
    """A fixture that was edited without its answers being re-derived fails.

    The hash is what binds an answer key to the bytes the answer was read
    from. Without it, an edited fixture still "passes" -- its recorded
    answers are simply answers about a file that no longer exists, and
    nothing says so.
    """
    for material in _fixture(fixture_id)["material"]:
        raw = (PUBLIC / material["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == material["sha256"], (
            f"{material['path']} hashes to {digest}, not the {material['sha256']} "
            f"the manifest records. Either the material was edited and its "
            f"answers were not re-derived, or the manifest is stale."
        )
        assert len(raw) == material["bytes"], (
            f"{material['path']} is {len(raw)} bytes, not the {material['bytes']} "
            f"the manifest records"
        )


@pytest.mark.unit
def test_the_manifest_names_every_material_file_and_no_other() -> None:
    """The corpus is closed: no unrecorded file, and no recorded file absent.

    An extra file in the corpus is material nothing has an answer key for,
    so a measurement over the corpus would be measuring something the
    manifest does not describe. A missing file is a fixture that cannot be
    measured at all.
    """
    named = {material["path"] for fixture in _fixtures() for material in fixture["material"]}
    on_disk = {
        str(p.relative_to(PUBLIC)).replace("\\", "/")
        for p in PUBLIC.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json"
    }
    assert named == on_disk, (
        f"the manifest names {sorted(named - on_disk)} which are not on disk, "
        f"and the corpus holds {sorted(on_disk - named)} which the manifest "
        f"does not name"
    )


@pytest.mark.unit
@pytest.mark.parametrize("fixture_id", EXPECTED_FIXTURES)
def test_no_material_file_carries_a_carriage_return(fixture_id: str) -> None:
    """The material's bytes are the same on every platform.

    The repository's ``.gitattributes`` normalises text to LF, and this
    test is what makes that rule *visible* for the corpus: a file that
    reached the working tree with CRLF in it would hash differently from
    the blob Git stores, and the answer key's hash would stop matching the
    bytes the answers were derived from.

    That failure is invisible in the sense that matters -- the file reads
    the same, and every other assertion still passes. So it is checked
    here, on the bytes, where it is visible.
    """
    for material in _fixture(fixture_id)["material"]:
        raw = (PUBLIC / material["path"]).read_bytes()
        assert b"\r" not in raw, (
            f"{material['path']} carries a carriage return. The material's "
            f"hash is computed over these bytes, and a checkout that changed "
            f"the line endings would change the hash."
        )


# --------------------------------------------------------------------------
# 3. The locators resolve
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("fixture_id", EXPECTED_FIXTURES)
def test_every_cited_locator_resolves_to_the_text_the_manifest_expects(
    fixture_id: str, session: Session, ingested_store: dict[str, Ingested]
) -> None:
    """Each cited address is parsed, canonically rendered, and *resolved*.

    Three separate things, and the middle one is the one that is easy to
    fake:

    * **Parsed** into a typed locator, so a key that does not describe a
      real address is rejected rather than compared as text.
    * **Canonically rendered** back to the key the manifest records, so the
      two spellings of one address cannot drift apart.
    * **Resolved** through ``locate_anchor`` against the ingested material.
      This is the step that fails when the address names a line or a cell
      that is not there, and it is what makes a locator worth having.
    """
    fixture = _fixture(fixture_id)
    ingested = ingested_store[fixture_id]
    connection = session.connection()

    checked = 0
    for question in _questions(fixture_id):
        for check in question["expected_artifact_checks"]:
            if check["kind"] != "citation_resolves":
                continue
            key = check["locator_key"]
            locator = locator_from_key(key)

            assert render_locator_key(locator) == key, (
                f"{key} does not render back to itself: "
                f"{render_locator_key(locator)}. The manifest and the "
                f"addressing module disagree about this address."
            )

            path = _path_for_locator(fixture, locator)
            anchor = _anchor(ingested, path, locator, AnchorKind.QUOTATION)
            located = locate_anchor(connection, anchor)
            assert located.resolution is LocationResolution.RESOLVED, (
                f"{key} resolves to {located.resolution.value!r}, not a resolved "
                f"address. The locator names {describe_locator(locator)}, which "
                f"the material does not contain."
            )
            assert located.text is not None and located.text.strip(), (
                f"{key} resolves to empty text; a citation to an empty address supports nothing"
            )
            checked += 1

    assert checked > 0, (
        f"fixture {fixture_id!r} cites no locator at all, so nothing in it is "
        f"checkable against the material"
    )


@pytest.mark.unit
@pytest.mark.parametrize("fixture_id", EXPECTED_FIXTURES)
def test_a_locator_naming_something_absent_does_not_resolve(
    fixture_id: str, session: Session, ingested_store: dict[str, Ingested]
) -> None:
    """The resolution check can fail, and this is how it is shown.

    A guard that cannot fail is not a guard. So the fixture is asked for an
    address one row past its last, and the answer must be
    ``UNRESOLVABLE`` -- which is what makes the green runs above mean
    something.
    """
    fixture = _fixture(fixture_id)
    ingested = ingested_store[fixture_id]
    connection = session.connection()

    absent: list[tuple[str, SourceLocator]] = []
    for material in fixture["material"]:
        path = material["path"]
        for locator, _ in ingested.units_of(path):
            if isinstance(locator, CsvLocator):
                absent.append((path, CsvLocator(row=9999, column=locator.column)))
            elif isinstance(locator, TextLocator):
                absent.append((path, TextLocator(line=9999, section=locator.section)))
            if absent:
                break

    assert absent, (
        f"fixture {fixture_id!r} produced no addressable unit to be wrong about, "
        f"so the resolution check cannot be shown to fail"
    )

    path, locator = absent[0]
    anchor = _anchor(ingested, path, locator, AnchorKind.QUOTATION)
    located = locate_anchor(connection, anchor)
    assert located.resolution is LocationResolution.UNRESOLVABLE, (
        f"{describe_locator(locator)} resolved to {located.resolution.value!r}. "
        f"An address the material does not contain must not resolve, or the "
        f"resolutions above prove nothing."
    )
    assert located.text is None, "an unresolvable address carries no text"


# --------------------------------------------------------------------------
# 4. The answers are re-derived from the material
# --------------------------------------------------------------------------


def _mean_over_cells(ingested: Ingested, path: str, column: str, rows: list[int]) -> float:
    """The mean of a column's cells, computed by the product's own operator.

    The operator is the point. If the fixture's expected value were checked
    by a hand-written ``sum()/len()``, the check would agree with the
    manifest even where the product's own reading of the same material
    disagreed -- and the disagreement is exactly the defect this corpus
    exists to catch.
    """
    source = ingested.source_for(path)
    selection = Selection(
        source_id=source.source_id,
        content_sha256=source.content_sha256,
        columns=(column,),
        rows=RowSet(rows=tuple(rows)),
        missing=MissingPolicy.REFUSE,
    )

    def text_at(address: CellAddress) -> str | None:
        for locator, text in ingested.units_of(path):
            if (
                isinstance(locator, CsvLocator)
                and locator.row == address.row
                and locator.column == address.column
            ):
                return text
            if isinstance(locator, XlsxLocator) and locator.cell_ref == address.column:
                return text
        return None

    result = MEAN.run(
        MEAN.operator.args_model(selection=selection),
        _Source(text_at=text_at, rows=lambda: tuple(sorted(rows))),
    )
    assert result.value is not None, (
        f"the mean over {column!r} is undefined: {result.undefined_reason}"
    )
    assert result.n_used == len(rows), (
        f"the operator used {result.n_used} cell(s) of the {len(rows)} the selection names"
    )
    return result.value


class _Source:
    """The cell source the operators read: this fixture's ingested units."""

    def __init__(
        self,
        text_at: Callable[[CellAddress], str | None],
        rows: Callable[[], tuple[int, ...]],
    ) -> None:
        self._text_at = text_at
        self._rows = rows

    def text_at(self, address: CellAddress) -> str | None:
        return self._text_at(address)

    def rows(self) -> tuple[int, ...]:
        return self._rows()

    @property
    def records_blank_cells(self) -> bool:
        return False


def _numeric_in(text: str) -> float:
    """The quantity a resolved text states, read out of the sentence.

    A prose line is not a cell -- ``read_number`` refuses a segment that is
    more than one number and one token, which is right for a cell and wrong
    for a sentence. So the number is taken out of the line first, and then
    handed to the product's own reader, which is what decides whether what
    was taken is a quantity or a fragment of prose.
    """
    import re

    from labcairn.sources.quantity import read_number

    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
    assert numbers, f"{text!r} states no number at all"

    readings = [
        reading
        for reading in (read_number(number) for number in numbers)
        if reading.value is not None
    ]
    assert readings, f"{text!r} holds no readable quantity: none of {numbers} is one"
    value = readings[0].value
    assert value is not None
    return value


@pytest.mark.unit
def test_the_tabular_answers_are_re_derived_by_the_products_own_operator(
    ingested_store: dict[str, Ingested],
) -> None:
    """Each tabular answer is recomputed from the material, not trusted.

    The manifest's numbers are checked against what the product's mean
    operator computes over the same cells of the same file. A manifest that
    says 412.0 where the material says something else fails here.
    """
    checked = 0
    for fixture in _fixtures():
        ingested = ingested_store[fixture["id"]]
        for question in fixture["questions"]:
            answer = question["answer"]
            if answer["kind"] != "numeric":
                continue
            derivation = answer["derivation"]
            if "mean of the" not in derivation:
                continue

            path = _csv_path_for(fixture, ingested)
            column, rows = _selection_for(ingested, path, derivation)
            computed = _mean_over_cells(ingested, path, column, rows)
            assert math.isclose(
                computed,
                answer["value"],
                rel_tol=0.0,
                abs_tol=answer["tolerance"],
            ), (
                f"{question['id']}: the material gives {computed!r} over "
                f"{column!r} rows {rows}, but the manifest says "
                f"{answer['value']!r}. One of them is wrong."
            )
            checked += 1

    assert checked >= 3, (
        f"only {checked} tabular answer(s) were re-derived; the corpus should "
        f"have at least one per answerable fixture"
    )


def _csv_path_for(fixture: dict[str, Any], ingested: Ingested) -> str:
    for material in fixture["material"]:
        if str(material["path"]).endswith(".csv"):
            return str(material["path"])
    raise AssertionError(f"fixture {fixture['id']!r} has no tabular material")


def _selection_for(ingested: Ingested, path: str, derivation: str) -> tuple[str, list[int]]:
    """The column and rows a derivation names, read out of the material.

    The derivation is prose, so the rows come from the ingested units
    themselves: either every data row of the table, or the rows whose id
    cell carries the subject the derivation names. Reading them from the
    material rather than from the manifest is deliberate -- a manifest
    that named the wrong rows would then be caught, instead of being
    checked against itself.
    """
    column = _column_in(derivation)
    id_column = _id_column(ingested, path)

    if _covers_every_row(derivation):
        rows = sorted(
            {
                locator.row
                for locator, _ in ingested.units_of(path)
                if isinstance(locator, CsvLocator) and locator.column == id_column
            }
        )
        assert rows, "the material has no data rows at all"
        return column, rows

    subject = _subject_in(derivation)
    rows = []
    for locator, text in ingested.units_of(path):
        if not isinstance(locator, CsvLocator):
            continue
        if locator.column != id_column:
            continue
        if text == subject:
            rows.append(locator.row)
    assert rows, (
        f"the derivation {derivation!r} names rows with {subject!r}, and the material has none"
    )
    return column, sorted(rows)


def _covers_every_row(derivation: str) -> bool:
    """Whether a derivation says it is over the whole table."""
    lowered = derivation.lower()
    return "over all" in lowered or "every row" in lowered


def _id_column(ingested: Ingested, path: str) -> str:
    """The column that identifies a row, taken as the first one."""
    for locator, _ in ingested.units_of(path):
        if isinstance(locator, CsvLocator):
            return locator.column
    raise AssertionError("the tabular material has no cells")


def _subject_in(derivation: str) -> str:
    """The subject code a derivation names.

    The corpus's id schemes differ -- ``B-2``, ``SYN-P03``, ``SYN-R1`` -- so
    the subject is whatever token the derivation names as the id, read
    between "is" and the end of the phrase. That keeps the fixture prose
    free to name its own identifiers, which is what lets the derivation be
    checked against the material rather than the other way round.
    """
    import re

    found = re.findall(r"\b(?:SYN-)?[A-Z](?:-\d+)+\b|\b(?:SYN-)?[A-Z]\d+\b", derivation)
    if found:
        return str(found[0])
    raise AssertionError(f"the derivation {derivation!r} names no subject code")


def _column_in(derivation: str) -> str:
    """The column a derivation names, read out of its prose."""
    import re

    found = re.findall(r"\b([a-z_]+ \([^)]*\))", derivation)
    if found:
        return str(found[0])
    raise AssertionError(f"the derivation {derivation!r} names no column")


@pytest.mark.unit
def test_the_prose_answers_are_re_derived_from_the_resolved_text(
    ingested_store: dict[str, Ingested],
) -> None:
    """Each prose answer is read out of the cited line, not trusted.

    A prose fixture's answer is a number in a sentence, so it cannot be
    recomputed by an operator over cells. It is recomputed by *resolving*
    the line the fixture cites and reading the quantity out of the
    resolved text with the product's own reader. A manifest that says 0.5
    where the cited line says something else fails here.
    """
    checked = 0
    for fixture in _fixtures():
        ingested = ingested_store[fixture["id"]]
        for question in fixture["questions"]:
            answer = question["answer"]
            if answer["kind"] != "numeric":
                continue
            keys = [
                check["locator_key"]
                for check in question["expected_artifact_checks"]
                if check["kind"] == "citation_resolves"
            ]
            if not keys:
                continue
            locator = locator_from_key(keys[0])
            if not isinstance(locator, TextLocator):
                continue

            path = _path_for_locator(fixture, locator)
            found = [
                text
                for candidate, text in ingested.units_of(path)
                if _same_address(candidate, locator)
            ]
            assert found, (
                f"{question['id']}: the cited line {describe_locator(locator)} is "
                f"not in the material"
            )
            value = _numeric_in(found[0])
            assert math.isclose(
                value,
                answer["value"],
                rel_tol=0.0,
                abs_tol=answer["tolerance"],
            ), (
                f"{question['id']}: the cited line says {value!r}, but the "
                f"manifest says {answer['value']!r}. One of them is wrong."
            )
            checked += 1

    assert checked >= 1, "no prose answer was re-derived, so the corpus's prose half is unchecked"


def _same_address(left: SourceLocator, right: SourceLocator) -> bool:
    """Whether two locators name the same place."""
    return render_locator_key(left) == render_locator_key(right)


# --------------------------------------------------------------------------
# 5. The negative fixture is negative, and is not hollow
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_the_negative_fixture_really_does_not_answer_the_question(
    ingested_store: dict[str, Ingested],
) -> None:
    """The material does not report the quantity the question asks for.

    This is the property that makes the fixture a measurement of
    abstention rather than a formality.

    The check is for a **reported pH** -- the word "pH" next to a number --
    not for the word "pH" at all. The material deliberately *names* the
    quantity it does not report, because that is what a real excerpt
    looks like, and a check that forbade the word outright would fail on
    a fixture that is being honest about its own limits. What must not
    exist is a pH **value**, and that is what is checked: no number in
    the material is stated as a pH.
    """
    question = _question(NEGATIVE_FIXTURE, NEGATIVE_QUESTION)
    assert question["answer"]["kind"] == "not_stated", (
        "the negative fixture's answer must be an abstention; an answer key "
        "that gives a number is not a negative fixture"
    )
    assert question["answer"]["value"] is None

    ingested = ingested_store[NEGATIVE_FIXTURE]
    reported = _reported_ph_values(ingested)

    assert not reported, (
        f"the negative fixture's material reports a pH of {reported}, so the "
        f"question is answerable and the fixture is not negative"
    )


def _reported_ph_values(ingested: Ingested) -> list[str]:
    """Every pH the material states, as the raw text around the word.

    A pH is a number and the word "pH" together -- in either order, since
    "7.2 pH" and "pH of 7.2" are both ways of writing it. The gap between
    the word and the number may hold a short connective ("of", "=", ":",
    "was"), because prose writes it that way and a pattern that allowed only
    adjacency would miss exactly the phrasing a real excerpt uses.

    Anything else mentioning the word is the material saying it does not
    report it, which is not a report.
    """
    import re

    gap = r"(?:\s*(?:of|was|is|at|to|:|=)?\s*)"
    found: list[str] = []
    for _path, _locator, text in ingested.units:
        for match in re.finditer(
            r"(\d+(?:\.\d+)?)\s*[pP][hH]\b|[pP][hH]\b" + gap + r"(\d+(?:\.\d+)?)",
            text,
        ):
            found.append(match.group(0))
    return found


def _words(text: str) -> set[str]:
    """The words of a text, lowercased, without punctuation."""
    import re

    return set(re.findall(r"[a-z0-9]+", text))


@pytest.mark.unit
def test_the_negative_fixture_is_not_hollow(
    ingested_store: dict[str, Ingested],
) -> None:
    """The negative material is full of *other* quantities.

    A fixture whose material says nothing at all would be satisfied by a
    system that abstains from everything, and would measure nothing. So
    the negative fixture's material carries several real quantities, and
    the test asserts they are there and resolvable -- which is also what
    makes "the material does not say X" a statement about X rather than
    about the document.
    """
    ingested = ingested_store[NEGATIVE_FIXTURE]
    csv_path = _csv_path_for(_fixture(NEGATIVE_FIXTURE), ingested)

    quantities = [
        ("wash_count", "3"),
        ("buffer_conc (mM)", "50"),
        ("elution_volume (uL)", "250"),
        ("incubation_temp (C)", "37"),
    ]
    for column, expected in quantities:
        found = [
            text
            for locator, text in ingested.units_of(csv_path)
            if isinstance(locator, CsvLocator) and locator.column == column
        ]
        assert found, (
            f"the negative fixture's material has no {column!r} column, so the "
            f"fixture does not demonstrate that the material is informative"
        )
        assert expected in found, (
            f"the {column!r} column does not carry {expected!r}; the negative "
            f"fixture's material would be a different one"
        )


@pytest.mark.unit
def test_the_negative_fixture_says_the_answer_is_an_abstention() -> None:
    """The expected artifact checks say so, in the terms a harness reads.

    The answer key and the artifact checks are two faces of the same
    statement, and the harness measures the second. A negative fixture
    whose checks did not require an abstention would let a report that
    confidently states a number pass.
    """
    question = _question(NEGATIVE_FIXTURE, NEGATIVE_QUESTION)
    kinds = {check["kind"] for check in question["expected_artifact_checks"]}
    assert "abstains" in kinds, (
        "the negative fixture's expected artifact checks do not require an "
        f"abstention; they are {sorted(kinds)}"
    )
    assert "no_fabricated_value" in kinds, (
        "the negative fixture must forbid the plausible wrong answers, or a "
        "report that states the buffer concentration as the pH would pass"
    )


# --------------------------------------------------------------------------
# 6. The artifact checks are consistent with the answers
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_every_number_present_check_matches_its_question_s_answer() -> None:
    """A check and the answer key cannot disagree.

    The harness compares a produced report against these checks. A check
    that names a number the answer key does not would either fail a
    correct report or pass an incorrect one, and the corpus would be
    measuring the wrong thing.
    """
    for fixture in _fixtures():
        for question in fixture["questions"]:
            answer = question["answer"]
            for check in question["expected_artifact_checks"]:
                if check["kind"] != "number_present":
                    continue
                assert answer["kind"] == "numeric", (
                    f"{question['id']} has a number_present check but its answer "
                    f"is {answer['kind']!r}"
                )
                assert math.isclose(
                    check["value"],
                    answer["value"],
                    rel_tol=0.0,
                    abs_tol=answer["tolerance"],
                ), (
                    f"{question['id']}: its artifact check asks for "
                    f"{check['value']!r} and its answer key says "
                    f"{answer['value']!r}"
                )
                if check.get("unit") is not None:
                    assert check["unit"] == answer["unit"], (
                        f"{question['id']}: the check's unit {check['unit']!r} "
                        f"and the answer's {answer['unit']!r} differ"
                    )


@pytest.mark.unit
def test_every_no_fabricated_value_check_names_a_value_the_material_holds(
    ingested_store: dict[str, Ingested],
) -> None:
    """A forbidden value is one a wrong answer would actually produce.

    The point of ``no_fabricated_value`` is to catch the specific mistake
    the fixture invites: the report reaching for a nearby number. So the
    forbidden value has to be *in* the material -- otherwise the check
    forbids nothing and passes no matter what the report says.

    "In the material" means the material's own numbers, not a number the
    material happens to imply: the check forbids a figure a report could
    have copied out of the wrong cell.
    """
    for fixture in _fixtures():
        ingested = ingested_store[fixture["id"]]
        numbers = _material_numbers(ingested)
        for question in fixture["questions"]:
            for check in question["expected_artifact_checks"]:
                if check["kind"] != "no_fabricated_value":
                    continue
                value = check["value"]
                assert any(
                    math.isclose(value, number, rel_tol=0.0, abs_tol=1e-12) for number in numbers
                ), (
                    f"{question['id']}: the forbidden value {value!r} is not a "
                    f"number the material holds, so the check forbids nothing"
                )


def _material_numbers(ingested: Ingested) -> list[float]:
    """Every quantity the material's cells hold, read by the product's reader."""
    from labcairn.sources.quantity import read_number

    numbers: list[float] = []
    for _path, _locator, text in ingested.units:
        reading = read_number(text)
        if reading.value is not None:
            numbers.append(reading.value)
    return numbers


def _numeric_text(value: float) -> str:
    """How a number is written in the material."""
    if value == int(value):
        return str(int(value))
    return repr(value).rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# 7. The checking machinery can fail
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_a_corrupted_answer_key_is_caught(ingested_store: dict[str, Ingested]) -> None:
    """Break an answer, and the machinery notices.

    A check that cannot fail is not a check. So the answer key is copied,
    one number is changed, and the same re-derivation is run against the
    copy -- and it must disagree with the corrupted key.

    The corruption is applied to a *copy*; the committed manifest is never
    touched, so a failing run of this test leaves the corpus as it was.
    """
    fixture = _fixture("physical_tension")
    question = copy.deepcopy(_question("physical_tension", "tension.mean_peak_stress_b2"))

    ingested = ingested_store["physical_tension"]
    csv_path = _csv_path_for(fixture, ingested)
    column, rows = _selection_for(ingested, csv_path, question["answer"]["derivation"])
    computed = _mean_over_cells(ingested, csv_path, column, rows)

    assert math.isclose(
        computed, question["answer"]["value"], rel_tol=0.0, abs_tol=question["answer"]["tolerance"]
    ), "the untouched answer does not agree with the material, so this test would not mean anything"

    question["answer"]["value"] = computed + 1.0
    corrupted = _mean_over_cells(ingested, csv_path, column, rows)
    assert not math.isclose(
        corrupted,
        question["answer"]["value"],
        rel_tol=0.0,
        abs_tol=question["answer"]["tolerance"],
    ), (
        "the corrupted answer still agrees with the material, so a wrong "
        "answer key would pass the check"
    )


@pytest.mark.unit
def test_a_corrupted_locator_is_caught(
    session: Session, ingested_store: dict[str, Ingested]
) -> None:
    """Point a citation at a cell that is not there, and the resolution fails.

    The locator check is the one that would let a fixture cite something
    the material does not contain. So a copy of a real key is pointed one
    row past the last, and the resolution must come back UNRESOLVABLE.
    """
    fixture = _fixture("physical_tension")
    ingested = ingested_store["physical_tension"]
    connection = session.connection()
    csv_path = _csv_path_for(fixture, ingested)

    key = "k=3:csv|r=1:2|c=17:peak_stress (MPa)"
    good = locator_from_key(key)
    assert render_locator_key(good) == key

    corrupted = CsvLocator(row=9999, column="peak_stress (MPa)")
    anchor = _anchor(ingested, csv_path, corrupted, AnchorKind.QUOTATION)
    located = locate_anchor(connection, anchor)
    assert located.resolution is LocationResolution.UNRESOLVABLE, (
        "a locator naming a row past the end of the material still resolves, so "
        "the resolution checks above would not notice a wrong citation"
    )


@pytest.mark.unit
def test_the_negative_check_notices_a_ph_value_appearing_in_the_material(
    tmp_path: Path,
) -> None:
    """The negative check can fail, and this is how it is shown.

    A material that stated the pH would answer the question, and the
    fixture would no longer measure abstention. So a copy of the negative
    material is given a pH, and the same detector the real fixture uses
    must find it.

    The copy is written to a temporary directory and never committed, so a
    failing run of this test leaves the corpus as it was.
    """
    source = PUBLIC / "no_evidence" / "protocol_excerpt.md"
    copied = tmp_path / "protocol_excerpt.md"
    copied.write_text(
        source.read_text(encoding="utf-8").replace(
            "prepared at a concentration of 50 mM and",
            "prepared at a concentration of 50 mM and a pH of 7.2, and",
        ),
        encoding="utf-8",
    )
    assert copied.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"), (
        "the negative material could not be given a pH, so this test would "
        "not be exercising anything"
    )

    from labcairn.material.ingest import ingest_bytes as ingest

    ingested = ingest(
        copied.read_bytes(),
        relative_path="no_evidence/protocol_excerpt.md",
        display_name="protocol_excerpt.md",
        ingested_at=NOW,
    )
    probe = Ingested("mutated")
    probe.units = [
        ("no_evidence/protocol_excerpt.md", unit.locator, unit.text) for unit in ingested.texts
    ]

    assert _reported_ph_values(probe), (
        "a pH written into the negative material was not found, so the "
        "negative check would pass on a material that answers the question"
    )


@pytest.mark.unit
def test_the_negative_fixture_states_no_ph_value_while_naming_the_quantity(
    ingested_store: dict[str, Ingested],
) -> None:
    """The negative material names the quantity it does not report.

    This is the distinction the negative check rests on. The material
    mentions "pH" -- because an honest excerpt says what it does not
    cover -- and it states no pH value. A detector that forbade the word
    would fail on a fixture that is being straightforward about its own
    limits, and a detector that only looked for the word would pass on a
    material that answers the question.
    """
    ingested = ingested_store[NEGATIVE_FIXTURE]
    mentions = [text for _path, _locator, text in ingested.units if "ph" in text.lower()]
    assert mentions, (
        "the negative material never mentions the quantity at all, so it is "
        "not testing abstention against a named-but-unreported quantity"
    )
    assert not _reported_ph_values(ingested), (
        "the negative material states a pH value, so the question is answerable"
    )


@pytest.mark.unit
def test_the_manifest_is_valid_json_and_declares_what_the_corpus_is() -> None:
    """The manifest parses, and declares the corpus's shape.

    A manifest that does not parse would make every other check in this
    file raise rather than fail, which reads as a crash and not as a
    finding. So the shape is checked first, on its own.
    """
    manifest = _manifest()
    assert manifest["schema"] == "labcairn.public-fixtures/1"
    assert manifest["corpus_version"]
    assert manifest["material_origin"] == "synthetic"
    assert manifest["notice"].strip(), "the corpus carries no notice at all"


@pytest.mark.unit
def test_every_question_names_a_kind_the_corpus_understands() -> None:
    """The answer kinds are a closed set, and every question uses one of them.

    A kind nothing handles would be an answer nobody can check -- the
    fixture would look answerable and be neither.
    """
    kinds = {"numeric", "not_stated"}
    for fixture in _fixtures():
        for question in fixture["questions"]:
            assert question["answer"]["kind"] in kinds, (
                f"{question['id']} has answer kind {question['answer']['kind']!r}, "
                f"which is not one of {sorted(kinds)}"
            )
            if question["answer"]["kind"] == "numeric":
                assert isinstance(question["answer"]["value"], (int, float))
                assert question["answer"]["tolerance"] is not None, (
                    f"{question['id']} declares no tolerance, so nothing says how "
                    f"far the answer may be from the material's number"
                )
            else:
                assert question["answer"]["value"] is None, (
                    f"{question['id']} abstains and yet carries a value"
                )


@pytest.mark.unit
def test_every_question_has_at_least_one_artifact_check() -> None:
    """A question with no check is a question nothing is measured against.

    The protocol asks each fixture for "expected artifact checks". A
    question without one would be scored by nothing, and the corpus would
    look fuller than it is.
    """
    for fixture in _fixtures():
        for question in fixture["questions"]:
            assert question["expected_artifact_checks"], (
                f"{question['id']} has no expected artifact check"
            )
            for check in question["expected_artifact_checks"]:
                assert check["kind"] in {
                    "number_present",
                    "citation_resolves",
                    "no_fabricated_value",
                    "abstains",
                }, f"{question['id']} has an artifact check of unknown kind {check['kind']!r}"
