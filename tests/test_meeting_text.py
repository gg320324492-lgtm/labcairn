"""The multi-source index: meeting text, searchable with its provenance.

**What is under test.** Phase 4 (P4-MS), execution plan §8.4 and §8.5,
third source: meeting material that already exists as text -- an SRT or
WebVTT transcript, or organised TXT/Markdown notes. The reader turns the
file's bytes into located records; the ingest writes them into a
searchable index; and a hit points back at the correct entry or
paragraph, which is §8.5's acceptance.

=================================  =======================================
§8.4 / §8.5 acceptance             witness
=================================  =======================================
an SRT transcript is read          a hand-written SRT yields one record
                                   per cue, each with its cue order and
                                   the container's own timestamp
a WebVTT transcript is read        a hand-written VTT yields its cues,
                                   the header and cue ids skipped
organised text is read             a TXT file yields one record per
                                   blank-line-separated paragraph, in
                                   reading order
every record keeps position and    each record's locator names its shape
fingerprint                        and index, the timestamp rides along
                                   for an entry and is absent for a
                                   paragraph, and the fingerprint is
                                   stable across re-reads
a hit points at the correct        a search for one cue's word returns
entry or paragraph                 that cue, not another record's text
re-ingesting the same file is      the ids are derived: a second ingest
the same rows                      rewrites the same rows, and the index
                                   does not grow
unauthorized material is refused   a policy that denies the read refuses
                                   the ingest, and nothing is written
the locator vocabulary is closed   a locator naming a shape nothing
                                   produces is rejected, and the union
                                   has eight members
the API serves the index           ``POST /meeting/ingest`` and
                                   ``GET /meeting/search`` over HTTP
=================================  =======================================

**The fixtures are hand-written files.** Real SRT, WebVTT and TXT bytes
-- the shapes a genuine meeting folder carries -- so every assertion is
against bytes the reader would meet in the wild, not against a mock of
the reader's own output.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.application.meeting_text import (
    ingest_meeting_text,
    list_meeting_records,
    search_meeting_text,
)
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.tasks import create_task
from labcairn.db.models import PaperProjectRow
from labcairn.material.meetingtext import read_meeting_text
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.locators import LOCATOR_MODELS, MeetingTextLocator

pytestmark = pytest.mark.integration

env = _shared_env

#: The one moment everything is stamped with, so a re-ingestion's rows are
#: byte-identical to the first pass's.
MOMENT = datetime(2026, 11, 24, 9, 0, 0, tzinfo=UTC)

ROOT_ID = "source:0"
SRT_KEY = "meeting/session.srt"
VTT_KEY = "meeting/session.vtt"
TXT_KEY = "meeting/notes.txt"

#: The words each record carries. **The second cue's word is the search's
#: probe**: it appears only in that cue, so a hit for it names that entry,
#: and nothing else.
SRT_CUE_ONE = "The meeting opened with the yield results."
SRT_CUE_TWO = "Action item: rerun the assay on Friday."
VTT_CUE_ONE = "WebVTT caption for the discussion."
VTT_CUE_TWO = "Follow up with the collaborators next week."
PARAGRAPH_ONE = "The first paragraph records the agenda."
PARAGRAPH_TWO = "The second paragraph records the decisions."


def srt_bytes() -> bytes:
    """A small but real SRT transcript: two cues, blank-line separated."""
    return (
        "1\n"
        "00:00:01,000 --> 00:00:03,400\n"
        f"{SRT_CUE_ONE}\n"
        "\n"
        "2\n"
        "00:00:05,200 --> 00:00:08,000\n"
        f"{SRT_CUE_TWO}\n"
    ).encode()


def vtt_bytes() -> bytes:
    """A small but real WebVTT transcript: header, two id'd cues."""
    return (
        "WEBVTT\n"
        "\n"
        "cue1\n"
        "00:00:01.000 --> 00:00:03.400\n"
        f"{VTT_CUE_ONE}\n"
        "\n"
        "cue2\n"
        "00:00:05.200 --> 00:00:08.000\n"
        f"{VTT_CUE_TWO}\n"
    ).encode()


def txt_bytes() -> bytes:
    """Organised notes: two paragraphs separated by a blank line."""
    return (f"{PARAGRAPH_ONE}\n\n{PARAGRAPH_TWO}\n").encode()


class MeetingEnv:
    """A task, a workspace holding meeting text, and a project to index it for."""

    def __init__(self, context: ApplicationContext, project_id: str) -> None:
        self.context = context
        self.project_id = project_id


def _build_env(env: StoreEnv, tmp_path: Path, *, policy: PermissionPolicy) -> MeetingEnv:
    """A workspace with the meeting files in a source root, and a project row."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    (materials / "meeting").mkdir(parents=True, exist_ok=True)
    (materials / "meeting" / "session.srt").write_bytes(srt_bytes())
    (materials / "meeting" / "session.vtt").write_bytes(vtt_bytes())
    (materials / "meeting" / "notes.txt").write_bytes(txt_bytes())

    store = env.store()
    created = create_task(
        store=store,
        policy=policy,
        workspace_root=workspace_root,
        title="Indexing meeting text",
        goal=TaskGoal(
            objective="Index the meeting text with its provenance.",
            success_criterion="A hit points at the entry or paragraph it came from.",
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
    from labcairn.application.material_ingestion import ingest_material

    ingest_material(context, now=MOMENT)
    session = store.session
    session.add(
        PaperProjectRow(
            project_id="proj-meeting",
            workspace_id="ws-meeting",
            subject_pseudonym="subject-1",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.commit()
    return MeetingEnv(context, "proj-meeting")


@pytest.fixture()
def meeting_env(env: StoreEnv, tmp_path: Path) -> MeetingEnv:
    """The environment under an allowing policy."""
    return _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
    )


# --------------------------------------------------------------------------- #
# the reader: extraction, addresses, fingerprints, limitations
# --------------------------------------------------------------------------- #


def test_an_srt_transcript_yields_one_timed_entry_per_cue() -> None:
    """Each cue is one record, carrying its cue order and the container's
    own timestamp spelling -- SRT's comma milliseconds stay as they are."""
    meeting = read_meeting_text(srt_bytes(), container="srt")
    assert meeting.problems == ()
    assert [record.text for record in meeting.records] == [SRT_CUE_ONE, SRT_CUE_TWO]
    first, second = meeting.records
    assert first.record_format == "entry"
    assert first.record_index == 1
    assert first.timestamp == "00:00:01,000"
    assert second.record_index == 2
    assert second.timestamp == "00:00:05,200"
    assert all(record.locator.record_format == "entry" for record in meeting.records)
    assert first.locator.timestamp == "00:00:01,000"


def test_a_vtt_transcript_skips_its_furniture_and_times_its_cues() -> None:
    """The WEBVTT header and cue ids are not records; each timed cue is."""
    meeting = read_meeting_text(vtt_bytes(), container="vtt")
    assert meeting.problems == ()
    assert [record.text for record in meeting.records] == [VTT_CUE_ONE, VTT_CUE_TWO]
    first, second = meeting.records
    assert first.timestamp == "00:00:01.000"
    assert second.timestamp == "00:00:05.200"
    assert first.record_index == 1 and second.record_index == 2


def test_organised_text_yields_one_paragraph_per_blank_line_block() -> None:
    """Each blank-line-separated paragraph is one record, in reading order,
    with no timestamp -- a paragraph has no time, and none is invented."""
    meeting = read_meeting_text(txt_bytes(), container="paragraphs")
    assert meeting.problems == ()
    assert [record.text for record in meeting.records] == [PARAGRAPH_ONE, PARAGRAPH_TWO]
    for record in meeting.records:
        assert record.record_format == "paragraph"
        assert record.timestamp is None
        assert record.locator.timestamp is None
    assert [record.record_index for record in meeting.records] == [1, 2]


def test_every_record_carries_its_position_and_a_stable_fingerprint() -> None:
    """The locator names the record's shape and index; the fingerprint is
    stable across re-reads and distinct across records."""
    first = read_meeting_text(srt_bytes(), container="srt")
    second = read_meeting_text(srt_bytes(), container="srt")
    by_text = {record.text: record for record in first.records}
    cue = by_text[SRT_CUE_TWO]
    assert cue.locator.record_format == "entry"
    assert cue.locator.record_index == 2

    # The same record in the same file fingerprints the same way; two
    # different records do not share one.
    assert first.records[0].fingerprint == second.records[0].fingerprint
    assert first.records[0].fingerprint != first.records[1].fingerprint

    # A paragraph of the same words in a different file is a different
    # record: the fingerprint folds the file's content hash.
    organised = read_meeting_text(txt_bytes(), container="paragraphs")
    assert organised.records[0].fingerprint != first.records[0].fingerprint


def test_an_untimed_srt_block_is_a_recorded_problem_and_no_content() -> None:
    """A block with no timing line is not a cue this reader can address:
    it is recorded, and no record is invented for it."""
    data = (
        f"1\n00:00:01,000 --> 00:00:03,400\n{SRT_CUE_ONE}\n\na block with no timing line\n"
    ).encode()
    meeting = read_meeting_text(data, container="srt")
    assert [record.text for record in meeting.records] == [SRT_CUE_ONE]
    codes = [problem.code for problem in meeting.problems]
    assert codes == ["meeting_srt_cue_untimed"]
    assert "timing" in meeting.problems[0].detail


def test_bytes_that_are_not_text_are_one_problem_and_no_records() -> None:
    """Undecodable bytes are recorded, never fabricated: the reader does
    not guess an encoding that would put words in the record."""
    meeting = read_meeting_text(b"\xff\xfe\x00broken", container="srt")
    assert meeting.records == ()
    assert len(meeting.problems) == 1
    assert meeting.problems[0].code == "text_not_decodable"


def test_a_container_the_reader_does_not_name_is_refused() -> None:
    """A container outside the closed set is a refusal, not a guess."""
    with pytest.raises(ValueError, match="no meeting-text reader"):
        read_meeting_text(srt_bytes(), container="mp3")


# --------------------------------------------------------------------------- #
# the ingest: the index, idempotence, refusals
# --------------------------------------------------------------------------- #


def test_the_ingest_indexes_every_record_with_its_provenance(meeting_env: MeetingEnv) -> None:
    """The ingest writes one row per record, each carrying its position,
    timestamp and fingerprint -- and reports the counts honestly."""
    ingested = ingest_meeting_text(
        meeting_env.context,
        project_id=meeting_env.project_id,
        root_id=ROOT_ID,
        resource_key=SRT_KEY,
        ingested_at=MOMENT,
    )
    assert ingested.records_indexed == 2
    assert ingested.entry_records == 2
    assert ingested.paragraph_records == 0
    assert ingested.limitations_recorded == 0

    records = list_meeting_records(meeting_env.context, project_id=meeting_env.project_id)
    assert len(records) == 2
    by_text = {record.text: record for record in records}
    row = by_text[SRT_CUE_TWO]
    assert row.record_format == "entry"
    assert row.record_index == 2
    assert row.timestamp_label == "00:00:05,200"
    assert row.source_sha256 == ingested.source_sha256
    assert '"record_format": "entry"' in row.locator_json
    assert '"record_index": 2' in row.locator_json

    # The fingerprint the reader recorded is the one the row carries.
    meeting = read_meeting_text(srt_bytes(), container="srt")
    reader_fingerprints = {r.text: r.fingerprint for r in meeting.records}
    assert row.record_fingerprint == reader_fingerprints[SRT_CUE_TWO]


def test_the_ingest_reads_organised_text_as_paragraphs(meeting_env: MeetingEnv) -> None:
    """A TXT file's paragraphs are indexed as paragraph records, with no
    timestamp -- the shape the file actually has."""
    ingested = ingest_meeting_text(
        meeting_env.context,
        project_id=meeting_env.project_id,
        root_id=ROOT_ID,
        resource_key=TXT_KEY,
        ingested_at=MOMENT,
    )
    assert ingested.records_indexed == 2
    assert ingested.paragraph_records == 2
    records = list_meeting_records(
        meeting_env.context, project_id=meeting_env.project_id, source_sha256=ingested.source_sha256
    )
    assert all(record.record_format == "paragraph" for record in records)
    assert all(record.timestamp_label is None for record in records)


def test_reingesting_the_same_file_is_the_same_rows(meeting_env: MeetingEnv) -> None:
    """The ids are derived: a second ingest rewrites the same rows, and the
    index does not grow a second copy of the meeting."""
    first = ingest_meeting_text(
        meeting_env.context,
        project_id=meeting_env.project_id,
        root_id=ROOT_ID,
        resource_key=SRT_KEY,
        ingested_at=MOMENT,
    )
    second = ingest_meeting_text(
        meeting_env.context,
        project_id=meeting_env.project_id,
        root_id=ROOT_ID,
        resource_key=SRT_KEY,
        ingested_at=MOMENT,
    )
    assert second.source_sha256 == first.source_sha256
    assert second.records_indexed == first.records_indexed
    again = list_meeting_records(meeting_env.context, project_id=meeting_env.project_id)
    assert len(again) == 2


def test_a_denied_file_is_refused_and_writes_nothing(env: StoreEnv, tmp_path: Path) -> None:
    """A policy that denies the read refuses the ingest by name, and the
    index holds nothing -- a file the policy denies is not a file the
    index quietly holds anyway.

    **The denial is scoped to the source material**, not to everything:
    the task's own bookkeeping must still work, or the environment could
    not be built at all -- and a test that denies everything tests
    nothing about the read gate. The policy allows everything else and
    denies the source root; a deny wins over an allow.
    """
    meeting_env = _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules(
            [
                Rule(effect=Permission.DENY, pattern="**/session.srt"),
                Rule(effect=Permission.ALLOW, pattern="**"),
            ]
        ),
    )
    with pytest.raises(ApplicationRefusedError) as refused:
        ingest_meeting_text(
            meeting_env.context,
            project_id=meeting_env.project_id,
            root_id=ROOT_ID,
            resource_key=SRT_KEY,
            ingested_at=MOMENT,
        )
    assert "denied" in str(refused.value).lower()
    assert list_meeting_records(meeting_env.context, project_id=meeting_env.project_id) == ()


def test_ingest_refuses_a_project_the_store_does_not_hold(meeting_env: MeetingEnv) -> None:
    """A file is indexed for a project; a project nobody holds is a
    refusal, not an index of nothing."""
    with pytest.raises(ApplicationRefusedError):
        ingest_meeting_text(
            meeting_env.context,
            project_id="proj-absent",
            root_id=ROOT_ID,
            resource_key=SRT_KEY,
            ingested_at=MOMENT,
        )


def test_ingest_refuses_an_extension_it_does_not_read(
    meeting_env: MeetingEnv, tmp_path: Path
) -> None:
    """A file whose container is not named is refused rather than guessed
    at -- the refusal names what this ingest reads. **The file exists**;
    the refusal is about the container, not about a missing file."""
    stray = tmp_path / "workspace" / "materials" / "meeting" / "session.mp3"
    stray.write_bytes(srt_bytes())
    with pytest.raises(ApplicationRefusedError, match="reads"):
        ingest_meeting_text(
            meeting_env.context,
            project_id=meeting_env.project_id,
            root_id=ROOT_ID,
            resource_key="meeting/session.mp3",
            ingested_at=MOMENT,
        )


def test_a_search_hit_points_at_the_correct_entry(meeting_env: MeetingEnv) -> None:
    """A search for one cue's word returns that cue -- the record whose
    text carries it -- with the provenance to check it by."""
    ingest_meeting_text(
        meeting_env.context,
        project_id=meeting_env.project_id,
        root_id=ROOT_ID,
        resource_key=SRT_KEY,
        ingested_at=MOMENT,
    )
    hits = search_meeting_text(meeting_env.context, query="Friday")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.text == SRT_CUE_TWO
    assert hit.record_format == "entry"
    assert hit.record_index == 2
    assert hit.timestamp_label == "00:00:05,200"
    assert hit.record_fingerprint


# --------------------------------------------------------------------------- #
# the locator vocabulary
# --------------------------------------------------------------------------- #


def test_the_meeting_locator_vocabulary_is_closed() -> None:
    """A locator naming a record shape nothing produces is rejected, not
    silently accepted -- the vocabulary is two names, and the union has
    eight members."""
    with pytest.raises(ValueError):
        MeetingTextLocator.model_validate(
            {"locator_kind": "meeting", "record_format": "cue", "record_index": 1}
        )
    with pytest.raises(ValueError):
        MeetingTextLocator.model_validate(
            {"locator_kind": "meeting", "record_format": "entry", "record_index": 0}
        )
    # An entry without a timestamp is still a valid address: the timestamp
    # is the container's gift, not the locator's requirement.
    locator = MeetingTextLocator.model_validate(
        {"locator_kind": "meeting", "record_format": "entry", "record_index": 3}
    )
    assert locator.timestamp is None
    assert len(LOCATOR_MODELS) == 8


# --------------------------------------------------------------------------- #
# the API surface
# --------------------------------------------------------------------------- #


@pytest.fixture()
def api(meeting_env: MeetingEnv) -> Iterator[tuple[TestClient, str]]:
    """The service over the meeting environment, with its session token."""
    from labcairn.api.events import UnwiredEventSource

    app = create_app(meeting_env.context, event_source=UnwiredEventSource())
    with TestClient(app) as wired:
        token = wired.get("/session").json()["token"]
        yield wired, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_the_api_indexes_and_searches_meeting_text(
    meeting_env: MeetingEnv, api: tuple[TestClient, str]
) -> None:
    """``POST /meeting/ingest`` indexes; ``GET /meeting/search`` answers
    with the record's provenance -- the wire serving the layer's own
    records."""
    client, token = api
    response = client.post(
        "/meeting/ingest",
        json={
            "project_id": meeting_env.project_id,
            "root_id": ROOT_ID,
            "resource_key": SRT_KEY,
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["records_indexed"] == 2
    assert body["entry_records"] == 2
    assert body["limitations_recorded"] == 0

    search = client.get(
        "/meeting/search",
        params={"q": "Friday", "project_id": meeting_env.project_id},
        headers=_auth(token),
    )
    assert search.status_code == 200, search.text
    hits = search.json()
    assert len(hits) == 1
    assert hits[0]["record_format"] == "entry"
    assert hits[0]["record_index"] == 2
    assert hits[0]["text"] == SRT_CUE_TWO
    assert hits[0]["timestamp_label"] == "00:00:05,200"
    assert hits[0]["record_fingerprint"]


def test_the_api_refuses_an_unauthorized_file(env: StoreEnv, tmp_path: Path) -> None:
    """A denied read is a refusal on the wire, and the index stays empty."""
    meeting_env = _build_env(
        env,
        tmp_path,
        policy=PermissionPolicy.from_rules(
            [
                Rule(effect=Permission.DENY, pattern="**/session.srt"),
                Rule(effect=Permission.ALLOW, pattern="**"),
            ]
        ),
    )
    from labcairn.api.events import UnwiredEventSource

    app = create_app(meeting_env.context, event_source=UnwiredEventSource())
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        response = client.post(
            "/meeting/ingest",
            json={
                "project_id": meeting_env.project_id,
                "root_id": ROOT_ID,
                "resource_key": SRT_KEY,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403, response.text
    assert list_meeting_records(meeting_env.context, project_id=meeting_env.project_id) == ()
