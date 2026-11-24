"""The recovery and quality doors, at the surface, witnessed end to end.

What this file witnesses is the seam between the service and the two
capabilities Phase 4 exposes here: **an interrupted publication is findable,
resolvable by a probe and replayable under a fresh consent, and a closed
round's quality report is readable** — with a real commented DOCX on disk, a
real interrupted operation in the store, and no provider call.

The interrupted publication is built the way the recovery witnesses build
it (``tests/test_apply_cancel_recover.py``): the loop runs to a
granted-but-unresolved publication attempt, and the effect is failed with a
``BaseException`` — the record a hard kill leaves. The API is then asked
what the CLI would ask the layer, and the answers are the layer's own
models, byte for byte.

The refusals are asserted by name, in the two fields every other refusal
uses: an unknown receipt, a short hash, bytes that do not decode, an
approval id that is not a UUID, a replay over an unresolved operation, a
project that is not there, and a dossier that is not there. A route whose
refusals are not its own vocabulary is a route a client cannot branch on.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from binding_support import (
    MOMENT,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
    open_the_binding,
)
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.approvals import grant_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.recovery import reconcile_abandoned
from labcairn.application.revision_loop import (
    PUBLICATION_STAGE_NAME,
    LoopOpened,
    open_loop,
    request_loop_approval,
    stage_copy,
)
from labcairn.core.ids import is_uuid7
from labcairn.papers.binding import ReviewDecision, ReviewVerdict, apply_approved_edits

pytestmark = pytest.mark.integration

env = _shared_env


#: The approvals' expiry — an hour past the **real** clock, taken at the
#: call. The replay runs through the service, whose clock is the wall clock,
#: and a window anchored to the fixture's fixed moment would already be
#: closed by the time the request lands.
def _window() -> datetime:
    """An approval window that outlives this call, from the real clock."""
    return datetime.now(UTC) + timedelta(hours=1)


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


class _NoEvents:
    """An event source that serves nothing: these routes do not stream.

    It satisfies the ``EventSource`` protocol's shape, and it is never
    reached — the recovery and quality witnesses call no stream route.
    """

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("these witnesses read no event stream")


@pytest.fixture
def client(fixture: BindingFixture) -> Iterator[tuple[TestClient, str]]:
    """A client for the service, with the fixture's context behind it."""
    context: ApplicationContext = fixture.context
    app = create_app(context, event_source=_NoEvents())
    with TestClient(app) as wired:
        session = wired.get("/session")
        assert session.status_code == 200
        token = str(session.json()["token"])
        yield wired, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _interrupted_publication(fixture: BindingFixture, loop: LoopOpened, edited: bytes) -> None:
    """Drive a loop to a granted-but-unresolved publication attempt.

    The copy lands and the publication consent is granted; the publication
    operation is left ATTEMPTING by failing the effect, which is the record a
    crash leaves. Nothing is published. The stage is driven through the
    loop's own request builder, so the arguments, the resource key and the
    source resolution are the ones the approval's digest was minted over.
    """
    from labcairn.application.revision_loop import _stage_request
    from labcairn.application.stages import StageOutcome, run_stage

    copy_granted = grant_approval(
        fixture.context,
        request_loop_approval(
            fixture.context,
            loop,
            stage_name="revision-copy",
            expires_at=MOMENT.replace(year=MOMENT.year + 1),
            now=MOMENT,
        ).approval.approval_id,
        now=MOMENT,
    )
    stage_copy(fixture.context, loop, approval_id=copy_granted.approval.approval_id, now=MOMENT)
    loop_copy_path = (
        fixture.workspace_root
        / "output"
        / str(fixture.context.task_id)
        / "revisions"
        / loop.import_receipt.receipt_id
        / "copy.bin"
    )
    loop_copy_path.write_bytes(edited)
    publication_granted = grant_approval(
        fixture.context,
        request_loop_approval(
            fixture.context,
            loop,
            stage_name=PUBLICATION_STAGE_NAME,
            expires_at=MOMENT.replace(year=MOMENT.year + 1),
            now=MOMENT,
        ).approval.approval_id,
        now=MOMENT,
    )
    request = _stage_request(
        loop,
        stage_name=PUBLICATION_STAGE_NAME,
        approval_id=publication_granted.approval.approval_id,
        run_id=None,
    )

    def failing_work(resource: object) -> StageOutcome:
        # **The in-flight kill is simulated, not performed.** ``run_stage``
        # marks ``ATTEMPTING`` before the effect and fails the operation after
        # an exception; a ``BaseException`` (what a hard kill delivers) skips
        # that handler and leaves the operation ATTEMPTING — the record a real
        # crash leaves, because nothing was running to write the failure.
        raise KeyboardInterrupt("the process died here")

    with pytest.raises(KeyboardInterrupt):
        run_stage(
            fixture.context,
            request,
            failing_work,
            now=MOMENT,
            resolve_source=lambda key: (
                fixture.context.workspace.path_in(key, fixture.source_root_id).real_path
            ),
        )


def _interrupted_loop(fixture: BindingFixture, edited: bytes) -> tuple[LoopOpened, str]:
    """An interrupted publication, on the record, with its reassembled loop.

    **The loop is reassembled on the found ids, not the opening's.** The
    publication's approval digest covers the loop's own publication id, so
    an approval asked over a re-minted id covers a different request — the
    same discipline the recovery witnesses apply. The returned string is the
    interrupted publication's resolved publication id.
    """
    from labcairn.application.revision_loop import (
        LOOP_DIR_NAME,
        ImportReceipt,
        find_interrupted_publication,
    )

    loop = open_loop(
        fixture.context,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        now=MOMENT,
    )
    _interrupted_publication(fixture, loop, edited)
    fixture.context.store.session.commit()
    receipt_id = loop.import_receipt.receipt_id
    found = find_interrupted_publication(fixture.context, receipt_id=receipt_id)
    assert found is not None, "the interrupted publication is findable from its receipt"
    reassembled = LoopOpened(
        import_receipt=ImportReceipt.model_validate(
            {
                **found.import_receipt.model_dump(mode="json"),
            }
        ),
        copy_key=f"{LOOP_DIR_NAME}/{receipt_id}/copy.bin",
        publication_key=f"{LOOP_DIR_NAME}/{receipt_id}/published.bin",
        manifest_key=f"{LOOP_DIR_NAME}/{receipt_id}/import-receipt.json",
        publication_artifact_id=found.publication_artifact_id,
        import_artifact_id=found.import_artifact_id,
    )
    return reassembled, receipt_id


def _decisions(fixture: BindingFixture) -> tuple[ReviewDecision, ...]:
    """The reviewer's sitting: one accepted, one flagged for evidence."""
    return (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.ACCEPTED,
            operator="Dr. Chen",
            decided_at=MOMENT,
        ),
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-2"),
            verdict=ReviewVerdict.PENDING,
            operator="Dr. Chen",
            decided_at=MOMENT,
            needs_evidence=True,
        ),
    )


def _closed_round(fixture: BindingFixture) -> str:
    """One healthy round, applied through the binding; its dossier's id."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="quality-round-1",
        window_end=MOMENT.replace(year=MOMENT.year + 1),
        now=MOMENT,
    )
    fixture.context.store.session.commit()
    return closed.dossier_artifact_id


# --------------------------------------------------------------------------- #
# the interrupted publication is readable
# --------------------------------------------------------------------------- #


def test_an_interrupted_publication_is_served_with_what_a_replay_needs(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The read carries the loop's own pieces, and nothing invented.

    **Everything a replay needs is in the answer**: the operation's id, the
    loop's three keys, the two artefact ids and the prediction. The keys are
    the loop's own addresses — the same ones the recovery witnesses resolve
    against — because a replay that re-derived them would be a second
    spelling of the loop.

    **The ids are read from the record, not from the opening.** The import
    row is on the record, so its id is served as the store holds it; the
    publication row never confirmed, so the id the read carries is the
    loop's own derivation of it — the same id a replay reassembles the loop
    under, and the same one the replayed receipt is upserted by.
    """
    edited = b"recovered draft bytes\n"
    loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    response = wired.get(
        "/revision/interrupted",
        params={"receipt_id": receipt_id},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["publication_key"].endswith("published.bin")
    assert body["copy_key"].endswith("copy.bin")
    assert body["manifest_key"].endswith("import-receipt.json")
    assert body["import_receipt"]["receipt_id"] == loop.import_receipt.receipt_id
    served_artifacts = wired.get("/artifacts", headers=_headers(token)).json()
    served_ids = {receipt["receipt"]["receipt_id"] for receipt in served_artifacts}
    assert body["import_artifact_id"] in served_ids, (
        "the import row is on the record, and the read names it as the store holds it"
    )
    assert body["publication_artifact_id"].startswith("pub-"), (
        "the publication row never confirmed; the id is the loop's own derivation of it"
    )
    assert body["operation_id"], "the interrupted operation is named"


def test_an_unknown_receipt_is_refused_by_name(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A receipt the record does not know is a refusal, not a null.

    **An empty answer would say "nothing to do" about a receipt that may not
    exist at all**, and "a quiet loop" and "a mistyped id" are different
    facts. The refusal is the layer's own name, in the same two fields every
    other refusal uses.
    """
    wired, token = client
    response = wired.get(
        "/revision/interrupted", params={"receipt_id": "no-such-receipt"}, headers=_headers(token)
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "identifier_not_found"


def test_the_interruption_read_is_behind_the_session_guard(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A read is free, a mutation is not — and this read asks for its origin.

    The route is a read, so the session guard does not demand the token; the
    origin guard does the work, exactly as it does for every other route. A
    foreign origin is refused before anything is read.
    """
    wired, _token = client
    response = wired.get(
        "/revision/interrupted",
        params={"receipt_id": "whatever"},
        headers={"Origin": "https://someone-else.example"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "origin_refused"


# --------------------------------------------------------------------------- #
# the probe resolution
# --------------------------------------------------------------------------- #


def test_a_probe_resolves_the_interrupted_publication(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Nothing landed, so the probe says a replay is safe.

    The interrupted attempt never wrote the publication file, so the probe
    finds nothing at the publication key — ``replay_safe``, with no observed
    hash — and the operation is resolved out of ``UNCERTAIN``.
    """
    edited = b"recovered draft bytes\n"
    _loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    found = wired.get(
        "/revision/interrupted",
        params={"receipt_id": receipt_id},
        headers=_headers(token),
    ).json()

    response = wired.post(
        f"/revision/interrupted/{receipt_id}/resolve",
        json={"expected_sha256": hashlib.sha256(edited).hexdigest()},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolution"] == "replay_safe"
    assert body["replay_permitted"] is True
    assert body["observed_sha256"] is None
    assert body["expected_sha256"] == hashlib.sha256(edited).hexdigest()
    assert body["operation_id"] == found["operation_id"]
    assert body["resulting_state"] == "authorized"


def test_a_resolution_with_a_short_hash_is_refused_at_the_wire(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The body's own pattern refuses a hash that is not a SHA-256.

    **The prediction is the one fact the probe needs**, and a value that
    cannot be a hash is not a prediction — the wire refuses it with the same
    422 every other closed shape answers with, before the layer is reached.
    """
    edited = b"recovered draft bytes\n"
    _loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    response = wired.post(
        f"/revision/interrupted/{receipt_id}/resolve",
        json={"expected_sha256": "abc123"},
        headers=_headers(token),
    )
    assert response.status_code == 422, response.text


def test_a_resolution_for_an_unknown_receipt_is_refused_by_name(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Resolving nothing is refused, the same name the read refuses."""
    wired, token = client
    response = wired.post(
        "/revision/interrupted/no-such-receipt/resolve",
        json={"expected_sha256": hashlib.sha256(b"whatever").hexdigest()},
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "identifier_not_found"


def test_a_mutation_without_the_token_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The session guard covers the new writes like every other write."""
    wired, _token = client
    response = wired.post(
        "/revision/interrupted/some-receipt/resolve",
        json={"expected_sha256": hashlib.sha256(b"whatever").hexdigest()},
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert response.status_code == 401, response.text
    assert response.json()["reason"] == "session_required"


# --------------------------------------------------------------------------- #
# the replay
# --------------------------------------------------------------------------- #


def test_a_resolved_publication_is_replayed_to_one_artifact_row(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Resolve, then replay under a fresh consent: one publication, one row.

    The probe resolves (nothing landed), the replay publishes the predicted
    bytes under a **fresh** consent — asked and granted over ``/approvals``,
    named in the body — and the response is the loop's own
    ``RevisionPublished``: the receipt, the key, and the bytes' hash. The
    store holds exactly one publication receipt for the loop.
    """
    edited = b"recovered draft bytes\n"
    loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    resolved = wired.post(
        f"/revision/interrupted/{receipt_id}/resolve",
        json={"expected_sha256": hashlib.sha256(edited).hexdigest()},
        headers=_headers(token),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["replay_permitted"] is True

    replay_requested = request_loop_approval(
        fixture.context,
        loop,
        stage_name=PUBLICATION_STAGE_NAME,
        expires_at=_window(),
    )
    replay_granted = grant_approval(fixture.context, replay_requested.approval.approval_id)
    fixture.context.store.session.commit()

    response = wired.post(
        f"/revision/interrupted/{receipt_id}/replay",
        json={
            "edited_base64": base64.b64encode(edited).decode("ascii"),
            "approval_id": str(replay_granted.approval.approval_id),
        },
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    published = response.json()
    assert published["publication_sha256"] == hashlib.sha256(edited).hexdigest()
    assert published["publication_key"].endswith("published.bin")
    assert published["publication"]["receipt_id"] == loop.publication_artifact_id

    artifacts = wired.get("/artifacts", headers=_headers(token)).json()
    landed = [
        receipt
        for receipt in artifacts
        if receipt["receipt"]["receipt_id"] == published["publication"]["receipt_id"]
    ]
    assert len(landed) == 1, "the replayed publication is one artifact row"


def test_a_replay_over_an_unresolved_operation_is_refused_by_name(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Replaying over an unknown outcome is the second writer, and is refused.

    The interruption is entered into doubt (``UNCERTAIN``) and **not**
    resolved; the replay is refused with the layer's own
    ``operation_uncertain``, whose remedy is the resolve door.
    """
    edited = b"recovered draft bytes\n"
    loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    # The approval id has to be a well-formed UUID for the request to reach
    # the layer's own refusal — this witness is about the replay gate, not
    # about the body's shape, so it names one the service could have minted.
    approval = (
        str(loop.import_artifact_id)
        if is_uuid7(str(loop.import_artifact_id))
        else str(uuid.uuid4())
    )
    response = wired.post(
        f"/revision/interrupted/{receipt_id}/replay",
        json={
            "edited_base64": base64.b64encode(edited).decode("ascii"),
            "approval_id": approval,
        },
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "operation_uncertain"


def test_a_replay_with_bytes_that_do_not_decode_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Bytes that are not base64 predict nothing, and are refused by name."""
    edited = b"recovered draft bytes\n"
    loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    response = wired.post(
        f"/revision/interrupted/{receipt_id}/replay",
        json={
            "edited_base64": "not base64 at all!",
            "approval_id": str(loop.publication_artifact_id),
        },
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"


def test_a_replay_with_an_approval_that_is_not_a_uuid_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """An approval id is the store's own mint, and the route says so."""
    edited = b"recovered draft bytes\n"
    _loop, receipt_id = _interrupted_loop(fixture, edited)
    reconcile_abandoned(fixture.context)
    fixture.context.store.session.commit()
    wired, token = client

    response = wired.post(
        f"/revision/interrupted/{receipt_id}/replay",
        json={
            "edited_base64": base64.b64encode(edited).decode("ascii"),
            "approval_id": "approval-1",
        },
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"


# --------------------------------------------------------------------------- #
# the round's quality report
# --------------------------------------------------------------------------- #


def test_a_closed_round_s_quality_report_is_served(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The six checks, in §7.4's own order, for one closed round.

    The round is the binding's whole three-opinion sample, decided the way
    the binding's own witnesses decide it, and the report is the layer's own
    model — the same bytes the CLI's ``--json`` prints, which is the whole
    point of serving the layer's models rather than copies of them.
    """
    dossier_artifact_id = _closed_round(fixture)
    wired, token = client

    response = wired.get(
        "/review/quality",
        params={"project_id": fixture.project_id, "dossier_artifact_id": dossier_artifact_id},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert len(report["checks"]) == 6, "the report carries the six §7.4 checks"
    for outcome in report["checks"]:
        assert outcome["passed"], f"{outcome['check']} failed: {outcome['facts']}"
    assert report["input_version_id"] == fixture.version_id
    assert report["dossier_artifact_id"] == dossier_artifact_id


def test_the_quality_report_refuses_a_project_that_is_not_there(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A round's quality is measured for a project, and nobody's is not one."""
    dossier_artifact_id = _closed_round(fixture)
    wired, token = client

    response = wired.get(
        "/review/quality",
        params={"project_id": "no-such-project", "dossier_artifact_id": dossier_artifact_id},
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "chain_project_not_found"


def test_the_quality_report_refuses_a_dossier_that_is_not_there(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """An artefact the store does not hold is a refusal, in its own name."""
    _closed_round(fixture)
    wired, token = client

    response = wired.get(
        "/review/quality",
        params={"project_id": fixture.project_id, "dossier_artifact_id": "no-such-dossier"},
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "artifact_not_found"


def test_the_quality_report_refuses_an_artefact_that_is_not_a_dossier(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The checks read the binding's own manifest, and another artefact names no round.

    An artefact row that is genuinely in the store but is **not** a manifest
    — here, an ``other`` receipt like a staged draft's — is refused by kind.
    This is the *kind* refusal, not the *missing* one, and the two are
    different facts about the same door.
    """
    import hashlib as _hashlib

    from labcairn.reports.receipt import (
        ArtifactKind,
        ArtifactProducerKind,
        ArtifactReceipt,
    )

    payload = b"not a manifest at all\n"
    staged = fixture.workspace_root / "output" / str(fixture.context.task_id) / "not-a-dossier.bin"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(payload)
    receipt = ArtifactReceipt(
        receipt_id="art-not-a-dossier",
        task_id=str(fixture.context.task_id),
        kind=ArtifactKind.OTHER,
        relative_path=f"output/{fixture.context.task_id}/not-a-dossier.bin",
        content_sha256=_hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="test",
        derived_from=(),
        media_type="application/octet-stream",
        created_at=MOMENT,
    )
    with fixture.context.store.unit(fixture.context.task_id) as work_unit:
        work_unit.put_artifact(receipt)
    fixture.context.store.session.commit()
    wired, token = client

    response = wired.get(
        "/review/quality",
        params={
            "project_id": fixture.project_id,
            "dossier_artifact_id": "art-not-a-dossier",
        },
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"
