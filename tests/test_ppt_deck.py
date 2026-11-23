"""The multi-source index: a deck's objects, searchable with their provenance.

**What is under test.** Phase 4 (P4-MS), execution plan §8.3 and §8.5,
second source: a PowerPoint deck's titles, body text, speaker notes,
tables and images. The reader turns the file's bytes into located objects;
the ingest writes them into a searchable index; and a hit points back at
the correct slide and object, which is §8.5's acceptance.

=================================  =======================================
§8.3 / §8.5 acceptance             witness
=================================  =======================================
the four object kinds are          a hand-built deck yields its title,
extracted                          body, notes, table and picture name
every result keeps slide,          each object's locator names its
position and fingerprint           slide, position and kind, and the
                                   fingerprint is stable across re-reads
a hit points at the correct        a search for a table's word returns
page or object                     the table row on the slide that
                                   holds it, not another slide's text
an unparseable object is a         a chart frame is recorded as a
recorded limitation                limitation, and no content is
                                   invented for it
a corrupted deck is a problem,     bytes that are not a deck are one
not a crash                        recorded problem and no objects
unauthorized material is refused   a policy that denies the read
                                   refuses the ingest, and nothing is
                                   written
the API serves the index           ``POST /ppt/ingest`` and
                                   ``GET /ppt/search`` over HTTP
=================================  =======================================

**The fixture is a hand-built deck.** A minimal but real ``.pptx`` — the
package parts a genuine deck carries, assembled as a zip — so every
assertion is against bytes the reader would meet in the wild, not against
a mock of the reader's own output.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.application.material_ingestion import ingest_material
from labcairn.application.ppt_deck import (
    ingest_ppt_deck,
    list_ppt_objects,
    search_ppt_deck,
)
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.tasks import TaskGoal, create_task
from labcairn.db.models import PaperProjectRow
from labcairn.material.pptx import read_deck
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

#: The one moment every write is stamped with. **A fixed instant, not the
#: wall clock**, for the project's reason.
MOMENT = datetime(2026, 4, 5, 9, 0, tzinfo=UTC)

#: The root id ``Workspace.bind`` gives the first source directory, and the
#: key the deck has inside it.
ROOT_ID = "source:0"
DECK_KEY = "deck.pptx"

#: The PresentationML, DrawingML, relationship and package namespaces the
#: fixture's parts are written in. They are the namespaces the reader reads.
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_PKG_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"

#: The words each object carries. **The table's word is the search's
#: probe**: it appears only in the table, so a hit for it names the table
#: row and the slide it sits on, and nothing else.
TITLE_TEXT = "Quarterly yield measurements"
BODY_TEXT = "The treated group yielded more than the control group."
NOTES_TEXT = "Remember to mention the control group's baseline."
TABLE_HEADER = "group | yield"
TABLE_ROW = "treated | 5.101"
PICTURE_NAME = "yield-curve-figure"

#: A second slide's body text, for the test that a hit points at the
#: *correct* slide rather than at any slide that mentions the words.
SECOND_SLIDE_TEXT = "The second slide discusses the assay protocol."

#: A chart frame with no data part: the limitation §8.3 says to record.
CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
TABLE_URI = "http://schemas.openxmlformats.org/drawingml/2006/table"

#: The media part the picture references, and the relationship id.
MEDIA_TARGET = "ppt/media/image1.png"
IMAGE_REL_ID = "rIdImg1"


def _text_shape(name: str, text: str, *, placeholder: str | None = None) -> str:
    """One ``p:sp`` carrying one paragraph of text.

    A placeholder attribute makes the shape a title; without one it is
    body text. That is the distinction the reader reads, so the fixture
    writes it the way a real deck writes it.
    """
    ph = f'<p:ph type="{placeholder}"/>' if placeholder else ""
    return (
        f"<p:sp><p:nvSpPr><p:cNvPr name=\"{name}\"/>{ph}</p:nvSpPr>"
        f"<p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"
    )


def _table_frame() -> str:
    """One ``p:graphicFrame`` holding a two-row table.

    The header row and one data row -- the smallest table that has a word
    to search for and a row to find it in.
    """
    return (
        '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr name="Table 5"/>'
        "</p:nvGraphicFramePr>"
        f'<a:graphic><a:graphicData uri="{TABLE_URI}"><a:tbl>'
        f'<a:tr><a:tc><a:p><a:r><a:t>group</a:t></a:r></a:p></a:tc>'
        f'<a:tc><a:p><a:r><a:t>yield</a:t></a:r></a:p></a:tc></a:tr>'
        f'<a:tr><a:tc><a:p><a:r><a:t>treated</a:t></a:r></a:p></a:tc>'
        f'<a:tc><a:p><a:r><a:t>5.101</a:t></a:r></a:p></a:tc></a:tr>'
        "</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
    )


def _chart_frame() -> str:
    """One ``p:graphicFrame`` whose ``a:graphicData`` names a chart.

    **The frame carries no data part** -- the chart's numbers would live
    in a separate part this reader does not parse, which is exactly the
    case §8.3 says to record as a limitation.
    """
    return (
        '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr name="Chart 9"/>'
        "</p:nvGraphicFramePr>"
        f'<a:graphic><a:graphicData uri="{CHART_URI}"/></a:graphic>'
        "</p:graphicFrame>"
    )


def _picture_shape() -> str:
    """One ``p:pic`` referencing the media part through its relationship."""
    return (
        '<p:pic><p:nvPicPr><p:cNvPr name="' + PICTURE_NAME + '"/></p:nvPicPr>'
        f'<a:blipFill><a:blip r:embed="{IMAGE_REL_ID}"/></a:blipFill>'
        "</p:pic>"
    )


def _slide_xml(shapes: str) -> str:
    return (
        '<?xml version="1.0"?>'
        f'<p:sld xmlns:p="{_P}" xmlns:a="{_A}" xmlns:r="{_R}">'
        f"<p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>"
    )


def build_deck_bytes(*, with_chart: bool = False) -> bytes:
    """A minimal but real ``.pptx``, assembled as a zip.

    Two slides, the first carrying a title, a body text box, a table, a
    picture and (optionally) a chart frame; the second carrying one body
    text box. The first slide's notes slide carries one paragraph. The
    parts are the parts a genuine deck carries, named the way a genuine
    deck names them.
    """
    first_shapes = (
        _text_shape("Title 1", TITLE_TEXT, placeholder="title")
        + _text_shape("Body 2", BODY_TEXT)
        + _table_frame()
        + _picture_shape()
        + (_chart_frame() if with_chart else "")
    )
    second_shapes = _text_shape("Body 3", SECOND_SLIDE_TEXT)

    content_types = (
        '<?xml version="1.0"?>'
        f'<Types xmlns="{_PKG_TYPES}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
        'package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        "</Types>"
    )
    presentation = (
        '<?xml version="1.0"?>'
        f'<p:presentation xmlns:p="{_P}" xmlns:r="{_R}">'
        '<p:sldIdLst><p:sldId id="256" r:id="rId1"/>'
        '<p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>'
    )
    presentation_rels = (
        '<?xml version="1.0"?>'
        f'<Relationships xmlns="{_PKG_REL}">'
        f'<Relationship Id="rId1" Type="{_R}/slide" Target="slides/slide1.xml"/>'
        f'<Relationship Id="rId2" Type="{_R}/slide" Target="slides/slide2.xml"/>'
        "</Relationships>"
    )
    slide1_rels = (
        '<?xml version="1.0"?>'
        f'<Relationships xmlns="{_PKG_REL}">'
        f'<Relationship Id="rId1" Type="{_R}/notesSlide" '
        'Target="../notesSlides/notesSlide1.xml"/>'
        f'<Relationship Id="{IMAGE_REL_ID}" Type="{_R}/image" '
        'Target="../media/image1.png"/>'
        "</Relationships>"
    )
    notes = (
        '<?xml version="1.0"?>'
        f'<p:notes xmlns:p="{_P}" xmlns:a="{_A}">'
        f"<p:cSld><p:txBody><a:p><a:r><a:t>{NOTES_TEXT}</a:t></a:r></a:p>"
        "</p:txBody></p:cSld></p:notes>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slides/slide1.xml", _slide_xml(first_shapes))
        archive.writestr("ppt/slides/slide2.xml", _slide_xml(second_shapes))
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", slide1_rels)
        archive.writestr("ppt/notesSlides/notesSlide1.xml", notes)
        archive.writestr(MEDIA_TARGET, b"\x89PNG\r\n\x1a\nnot-really-a-png")
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# the reader: extraction, addresses, fingerprints, limitations
# --------------------------------------------------------------------------- #


def test_a_deck_yields_every_object_kind() -> None:
    """Title, body, notes, table and picture name all come out, addressed."""
    deck = read_deck(build_deck_bytes())
    kinds = sorted(object.kind for object in deck.objects)
    assert kinds == ["body", "body", "image", "notes", "table", "table", "title"]
    assert deck.problems == ()


def test_every_object_carries_its_slide_position_and_kind() -> None:
    """The locator names the slide, the position within it, and the kind."""
    deck = read_deck(build_deck_bytes())
    by_text = {object.text: object for object in deck.objects}

    title = by_text[TITLE_TEXT]
    assert title.slide == 1
    assert title.locator.slide == 1
    assert title.locator.object_kind == "title"
    assert title.locator.position == 1

    notes = by_text[NOTES_TEXT]
    assert notes.slide == 1
    assert notes.locator.object_kind == "notes"

    second = by_text[SECOND_SLIDE_TEXT]
    assert second.slide == 2
    assert second.locator.object_kind == "body"

    # The picture's text is its name, and the media part it references is
    # resolved through the slide's relationships -- the name says what the
    # picture is, the target says where its bytes are.
    picture = by_text[PICTURE_NAME]
    assert picture.locator.object_kind == "image"
    assert picture.media_target == MEDIA_TARGET

    # And no two objects on one slide share a position: two addresses that
    # resolve to different text must not share a key.
    positions = [(object.slide, object.position) for object in deck.objects]
    assert len(positions) == len(set(positions))


def test_the_fingerprint_is_stable_across_reads_and_names_the_object() -> None:
    """The same object in the same deck fingerprints the same way; two
    different objects of one deck do not share a fingerprint."""
    data = build_deck_bytes()
    first = {o.text: o for o in read_deck(data).objects}
    second = {o.text: o for o in read_deck(data).objects}
    assert (
        first[TITLE_TEXT].fingerprint
        == second[TITLE_TEXT].fingerprint
    )
    assert first[TITLE_TEXT].fingerprint != first[NOTES_TEXT].fingerprint
    assert first[TITLE_TEXT].fingerprint != first[TABLE_ROW].fingerprint

    # The fingerprint folds the object's XML path, so the same words at a
    # different address do not share one -- the second slide's body text
    # and the first slide's body text are different objects.
    assert first[BODY_TEXT].fingerprint != first[SECOND_SLIDE_TEXT].fingerprint


def test_a_chart_is_a_recorded_limitation_and_no_content() -> None:
    """§8.3: a chart this reader cannot parse is a limitation with its
    location, and no object is invented for it."""
    deck = read_deck(build_deck_bytes(with_chart=True))
    codes = [problem.code for problem in deck.problems]
    assert codes == ["pptx_chart_unparsed"]
    assert "slide 1" in deck.problems[0].detail
    assert deck.problems[0].location == "slide:1:shape:5"
    # No object carries chart content: the deck's objects are the same
    # kinds a chartless deck yields.
    assert all(object.kind != "chart" for object in deck.objects)


def test_corrupted_bytes_are_a_problem_not_a_crash() -> None:
    """Bytes that are not a deck are one recorded problem and no objects --
    "we could not look", not "there was nothing there" and not a raise."""
    for payload in (b"not a zip at all", b"", b"PK\x03\x04truncated"):
        deck = read_deck(payload)
        assert deck.objects == ()
        assert len(deck.problems) == 1
        assert deck.problems[0].code in ("pptx_unreadable", "pptx_part_absent")


def test_an_archive_with_no_presentation_part_is_refused_by_name() -> None:
    """A zip that holds no ``ppt/presentation.xml`` says so, by part name."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "not a deck")
    deck = read_deck(buffer.getvalue())
    assert deck.objects == ()
    assert [problem.code for problem in deck.problems] == ["pptx_part_absent"]
    assert "ppt/presentation.xml" in deck.problems[0].detail


# --------------------------------------------------------------------------- #
# the ingest and the search, against a real store and workspace
# --------------------------------------------------------------------------- #


class DeckEnv:
    """A task, a workspace holding one deck, and a project to index it for."""

    def __init__(self, context: ApplicationContext, project_id: str) -> None:
        self.context = context
        self.project_id = project_id


def _build_env(env: StoreEnv, tmp_path: Path, *, policy: PermissionPolicy) -> DeckEnv:
    """A workspace with the deck in a source root, and a project row."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / DECK_KEY).write_bytes(build_deck_bytes())

    store = env.store()
    created = create_task(
        store=store,
        policy=policy,
        workspace_root=workspace_root,
        title="Indexing a deck",
        goal=TaskGoal(
            objective="Index the deck's objects with their provenance.",
            success_criterion="A hit points at the slide and object it came from.",
        ),
        source_dirs=(materials,),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=policy,
        ledger=ApprovalLedger(),
    )
    ingest_material(context, now=MOMENT)
    session = store.session
    session.add(
        PaperProjectRow(
            project_id="proj-deck",
            workspace_id="ws-deck",
            subject_pseudonym="subject-1",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.commit()
    return DeckEnv(context, "proj-deck")


@pytest.fixture()
def deck_env(env: StoreEnv, tmp_path: Path) -> DeckEnv:
    """The environment under an allowing policy."""
    return _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
    )


def test_the_ingest_indexes_every_object_with_its_provenance(deck_env: DeckEnv) -> None:
    """The ingest writes one row per object, each carrying slide, position,
    kind and fingerprint -- and reports the counts honestly."""
    ingested = ingest_ppt_deck(
        deck_env.context,
        project_id=deck_env.project_id,
        root_id=ROOT_ID,
        resource_key=DECK_KEY,
        ingested_at=MOMENT,
    )
    assert ingested.objects_indexed == 7
    assert ingested.title_objects == 1
    assert ingested.body_objects == 2
    assert ingested.notes_objects == 1
    assert ingested.table_objects == 2
    assert ingested.image_objects == 1
    assert ingested.limitations_recorded == 0

    objects = list_ppt_objects(deck_env.context, project_id=deck_env.project_id)
    assert len(objects) == 7
    by_text = {object.text: object for object in objects}
    row = by_text[TABLE_ROW]
    assert row.slide_no == 1
    assert row.object_kind == "table"
    assert row.source_sha256 == ingested.source_sha256
    assert '"slide": 1' in row.locator_json
    assert '"object_kind": "table"' in row.locator_json
    # The fingerprint the reader recorded is the one the row carries.
    deck = read_deck(build_deck_bytes())
    reader_fingerprints = {o.text: o.fingerprint for o in deck.objects}
    assert row.object_fingerprint == reader_fingerprints[TABLE_ROW]


def test_reingesting_the_same_deck_is_the_same_rows(deck_env: DeckEnv) -> None:
    """The ids are derived: a second ingest rewrites the same rows, and the
    index does not grow a second copy of the deck."""
    first = ingest_ppt_deck(
        deck_env.context,
        project_id=deck_env.project_id,
        root_id=ROOT_ID,
        resource_key=DECK_KEY,
        ingested_at=MOMENT,
    )
    second = ingest_ppt_deck(
        deck_env.context,
        project_id=deck_env.project_id,
        root_id=ROOT_ID,
        resource_key=DECK_KEY,
        ingested_at=MOMENT,
    )
    assert first.objects_indexed == second.objects_indexed
    objects = list_ppt_objects(deck_env.context, project_id=deck_env.project_id)
    assert len(objects) == first.objects_indexed
    assert len({object.object_id for object in objects}) == len(objects)


def test_a_search_hit_points_at_the_correct_slide_and_object(deck_env: DeckEnv) -> None:
    """§8.5: the word that appears only in the table's data row returns that
    row, on the slide that holds it, with the provenance to check it."""
    ingest_ppt_deck(
        deck_env.context,
        project_id=deck_env.project_id,
        root_id=ROOT_ID,
        resource_key=DECK_KEY,
        ingested_at=MOMENT,
    )
    hits = search_ppt_deck(deck_env.context, query="5.101")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.object_kind == "table"
    assert hit.slide_no == 1
    assert hit.text == TABLE_ROW
    assert '"slide": 1' in hit.locator_json
    assert len(hit.object_fingerprint) > 0

    # A hit for the notes names the notes, not the slide's body text that
    # also mentions the control group.
    notes_hits = search_ppt_deck(deck_env.context, query="baseline")
    assert len(notes_hits) == 1
    assert notes_hits[0].object_kind == "notes"
    assert notes_hits[0].text == NOTES_TEXT

    # A second slide's word names the second slide.
    second_hits = search_ppt_deck(deck_env.context, query="assay protocol")
    assert len(second_hits) == 1
    assert second_hits[0].slide_no == 2

    # A query with no servable terms is an empty answer, not an error.
    assert search_ppt_deck(deck_env.context, query="is") == ()


def test_a_chart_deck_reports_its_limitation(deck_env: DeckEnv, tmp_path: Path) -> None:
    """A deck whose chart cannot be parsed indexes the rest and records the
    chart as a limitation -- the §8.3 disclosure, not invented content."""
    (tmp_path / "workspace" / "materials" / "chart-deck.pptx").write_bytes(
        build_deck_bytes(with_chart=True)
    )
    ingested = ingest_ppt_deck(
        deck_env.context,
        project_id=deck_env.project_id,
        root_id=ROOT_ID,
        resource_key="chart-deck.pptx",
        ingested_at=MOMENT,
    )
    assert ingested.limitations_recorded == 1
    # The chart contributes no object; everything else is still indexed.
    assert ingested.objects_indexed == 7
    assert not any(
        "chart" in object.object_kind
        for object in list_ppt_objects(
            deck_env.context, project_id=deck_env.project_id
        )
    )


def test_a_denied_deck_is_refused_and_writes_nothing(env: StoreEnv, tmp_path: Path) -> None:
    """A policy that denies the read refuses the ingest by name, and the
    index holds nothing -- a deck the policy denies is not a deck the
    index quietly holds anyway.

    **The denial is scoped to the source material**, not to everything:
    the task's own bookkeeping must still work, or the environment could
    not be built at all -- and a test that denies everything tests
    nothing about the read gate. The policy allows everything else and
    denies the source root; a deny wins over an allow.
    """
    deck_env = _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules(
            [
                Rule(effect=Permission.DENY, pattern="**/deck.pptx"),
                Rule(effect=Permission.ALLOW, pattern="**"),
            ]
        ),
    )
    with pytest.raises(ApplicationRefusedError) as refused:
        ingest_ppt_deck(
            deck_env.context,
            project_id=deck_env.project_id,
            root_id=ROOT_ID,
            resource_key=DECK_KEY,
            ingested_at=MOMENT,
        )
    assert "denied" in str(refused.value).lower()
    assert list_ppt_objects(deck_env.context, project_id=deck_env.project_id) == ()


def test_ingest_refuses_a_project_the_store_does_not_hold(deck_env: DeckEnv) -> None:
    """A deck is indexed for a project; a project nobody holds is a
    refusal, not an index of nothing."""
    with pytest.raises(ApplicationRefusedError):
        ingest_ppt_deck(
            deck_env.context,
            project_id="proj-absent",
            root_id=ROOT_ID,
            resource_key=DECK_KEY,
            ingested_at=MOMENT,
        )


# --------------------------------------------------------------------------- #
# the API surface
# --------------------------------------------------------------------------- #


@pytest.fixture()
def api(deck_env: DeckEnv) -> Iterator[tuple[TestClient, str]]:
    """The service over the deck environment, with its session token."""
    from labcairn.api.events import UnwiredEventSource

    app = create_app(deck_env.context, event_source=UnwiredEventSource())
    with TestClient(app) as wired:
        token = wired.get("/session").json()["token"]
        yield wired, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_the_api_indexes_and_searches_a_deck(deck_env: DeckEnv, api) -> None:
    """``POST /ppt/ingest`` indexes; ``GET /ppt/search`` answers with the
    object's provenance -- the wire serving the layer's own records."""
    client, token = api
    response = client.post(
        "/ppt/ingest",
        json={
            "project_id": deck_env.project_id,
            "root_id": ROOT_ID,
            "resource_key": DECK_KEY,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["objects_indexed"] == 7
    assert body["limitations_recorded"] == 0

    search = client.get(
        "/ppt/search",
        params={"q": "5.101", "project_id": deck_env.project_id},
        headers=_auth(token),
    )
    assert search.status_code == 200, search.text
    hits = search.json()
    assert len(hits) == 1
    assert hits[0]["object_kind"] == "table"
    assert hits[0]["slide_no"] == 1
    assert hits[0]["text"] == TABLE_ROW
    assert hits[0]["object_fingerprint"]


def test_the_api_refuses_an_unauthorized_deck(env: StoreEnv, tmp_path: Path) -> None:
    """A denied read is a refusal on the wire, and the index stays empty."""
    deck_env = _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules(
            [
                Rule(effect=Permission.DENY, pattern="**/deck.pptx"),
                Rule(effect=Permission.ALLOW, pattern="**"),
            ]
        ),
    )
    from labcairn.api.events import UnwiredEventSource

    app = create_app(deck_env.context, event_source=UnwiredEventSource())
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        response = client.post(
            "/ppt/ingest",
            json={
                "project_id": deck_env.project_id,
                "root_id": ROOT_ID,
                "resource_key": DECK_KEY,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text
        assert response.json()["reason"] == "permission_denied"
