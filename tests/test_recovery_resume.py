"""Checkpoints, resume, scoped pause/stop, and downstream invalidation.

The claim under test throughout is the one in
:class:`~labcairn.runtime.lifecycle.Stage`: *"Changed input invalidates
downstream" is enforced by comparing hashes, not by timestamps, because a file
can change without its mtime moving.*

That is why the invalidation tests here rewrite a file **without** touching its
mtime. A test that used a normal edit would also pass against an implementation
comparing timestamps — which would make it evidence for a rule the code does not
actually implement. Restoring the original mtime after the rewrite is the step
that makes the comparison honest, and it is called out at each site rather than
buried in a helper.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select
from test_recovery_support import SCENARIO_NOW, Scenario, build_scenario
from test_store_support import env as _shared_env

from labcairn.core.ids import RunId, StageId, new_id
from labcairn.db.models import EventRow
from labcairn.recovery import (
    STALE_REASON,
    InvalidationReport,
    ResumePlan,
    hash_bytes,
)
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus

pytestmark = pytest.mark.integration

env = _shared_env


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _material(scenario: Scenario, key: str, body: bytes) -> Path:
    """Write a source material and return its path."""
    path = scenario.root.joinpath(*key.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _rewrite_preserving_mtime(path: Path, body: bytes) -> None:
    """Replace the bytes and put the mtime back where it was.

    This is the load-bearing trick of the invalidation tests. Without it a
    timestamp-based implementation would also pass, and the test would be
    evidence for a rule the code does not enforce.
    """
    original = path.stat().st_mtime_ns
    path.write_bytes(body)
    os.utime(path, ns=(original, original))
    assert path.stat().st_mtime_ns == original, "the mtime must look untouched"


def _record_artifact(
    scenario: Scenario,
    *,
    receipt_id: str,
    derived_from: tuple[DerivationRef, ...],
    path: str = "outputs/report.md",
) -> ArtifactReceipt:
    receipt = ArtifactReceipt(
        receipt_id=receipt_id,
        task_id=str(scenario.task_id),
        kind=ArtifactKind.REPORT,
        relative_path=path,
        content_sha256=hash_bytes(f"bytes for {receipt_id}".encode()),
        size_bytes=42,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        derived_from=derived_from,
        created_at=SCENARIO_NOW,
    )
    with scenario.store().unit(scenario.task_id) as work:
        work.emit(EventType.ARTIFACT_RECORDED)
        work.put_artifact(receipt, run_id=scenario.run_id)
    return receipt


def _stage(scenario: Scenario, name: str, *, input_hashes: tuple[str, ...] = ()) -> Stage:
    stage = Stage(
        stage_id=StageId(new_id()),
        task_id=scenario.task_id,
        run_id=scenario.run_id,
        name=name,
        status=StageStatus.COMPLETED,
        input_hashes=input_hashes,
    )
    with scenario.store().unit(scenario.task_id) as work:
        work.put_stage(stage)
        work.emit(
            EventType.STAGE_COMPLETED,
            run_id=scenario.run_id,
            stage_id=stage.stage_id,
            transition=EventTransition(
                from_state=StageStatus.ENTERED.value, to_state=StageStatus.COMPLETED.value
            ),
        )
    return stage


# --------------------------------------------------------------------------- #
# checkpoints and resume
# --------------------------------------------------------------------------- #


def test_a_checkpoint_records_the_seq_it_includes_not_the_one_it_emits(env, tmp_path):  # type: ignore[no-untyped-def]
    """A client resuming from the checkpoint must not skip its own announcement.

    ``through_seq`` is read before ``checkpoint_created`` allocates the next one,
    so the checkpoint names the last event it *contains*.
    """
    scenario = build_scenario(env, tmp_path)
    stage = _stage(scenario, "draft")
    before = _last_seq(scenario)

    checkpoint = scenario.resume().record_checkpoint(
        scenario.task_id, stage.stage_id, material_hashes=(hash_bytes(b"material"),)
    )

    assert checkpoint.through_seq == before, (
        "through_seq must be the counter as it stood before this checkpoint's own "
        "event was allocated"
    )
    assert _last_seq(scenario) == before + 1
    assert checkpoint.material_hashes == (hash_bytes(b"material"),)


def test_resume_from_the_last_verified_stage(env, tmp_path):  # type: ignore[no-untyped-def]
    """Nothing changed: the plan resumes after the last checkpoint."""
    scenario = build_scenario(env, tmp_path)
    material_hash = hash_bytes(b"the source, unchanged")
    _material(scenario, "materials/input.txt", b"the source, unchanged")

    first = _stage(scenario, "draft")
    scenario.resume().record_checkpoint(
        scenario.task_id, first.stage_id, material_hashes=(material_hash,)
    )
    second = _stage(scenario, "validate")
    scenario.resume().record_checkpoint(
        scenario.task_id, second.stage_id, material_hashes=(material_hash,)
    )

    snapshot = scenario.materials().snapshot(["materials/input.txt"])
    plan = scenario.resume().plan_resume(scenario.task_id, now=snapshot)

    assert plan.stopped_reason is None, plan.stopped_reason
    assert plan.must_redo is False
    assert plan.from_stage is None, "nothing follows the newest verified checkpoint"


def test_a_changed_source_invalidates_downstream_artifacts(env, tmp_path):  # type: ignore[no-untyped-def]
    """The core acceptance: change a source, and everything derived from it is stale."""
    scenario = build_scenario(env, tmp_path)
    material = _material(scenario, "materials/input.txt", b"the original source")
    original_hash = hash_bytes(b"the original source")

    derived = DerivationRef(
        target_kind=DerivationTargetKind.MATERIAL_FILE,
        target_id="materials/input.txt",
        content_sha256=original_hash,
    )
    receipt = _record_artifact(scenario, receipt_id="artifact-report", derived_from=(derived,))

    # Unrelated artifact, derived from something else entirely.
    other = _record_artifact(
        scenario,
        receipt_id="artifact-figure",
        path="outputs/figure.md",
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.MATERIAL_FILE,
                target_id="materials/other.txt",
                content_sha256=hash_bytes(b"something else"),
            ),
        ),
    )

    _rewrite_preserving_mtime(material, b"an edited source")

    report: InvalidationReport = scenario.resume().invalidate_on_source_change(
        scenario.task_id, [original_hash]
    )

    assert report.stale_artifact_ids == (receipt.receipt_id,)
    assert other.receipt_id not in report.stale_artifact_ids, (
        "an artifact not derived from the changed source must be left alone; "
        "blanket invalidation is not the requirement"
    )
    assert report.changed_hashes == (original_hash,)

    stale = scenario.resume().stale_artifacts(scenario.task_id)
    assert [r.receipt_id for r in stale] == [receipt.receipt_id]
    assert stale[0].staleness is ArtifactStaleness.STALE
    assert stale[0].staleness_reason == STALE_REASON, (
        "ADR-0004 I4: a stale mark nobody can act on is decoration. The receipt "
        "model's paired-field validator enforces the reason is present; this "
        "asserts it is the one a reader can act on."
    )
    _assert_has_event(scenario, "source_changed")


def test_a_changed_source_invalidates_the_stage_that_consumed_it(env, tmp_path):  # type: ignore[no-untyped-def]
    """Stages are named too, so a caller knows what must re-run."""
    scenario = build_scenario(env, tmp_path)
    source_hash = hash_bytes(b"source v1")
    consumed = _stage(scenario, "draft", input_hashes=(source_hash,))
    untouched = _stage(scenario, "triage", input_hashes=(hash_bytes(b"unrelated"),))

    report = scenario.resume().invalidate_on_source_change(scenario.task_id, [source_hash])

    assert report.invalidated_stages == (consumed.stage_id,)
    assert untouched.stage_id not in report.invalidated_stages


def test_resume_refuses_to_skip_a_stage_whose_material_moved(env, tmp_path):  # type: ignore[no-untyped-def]
    """The newest checkpoint fails, so the boundary after it is the resume point.

    And the checkpoints after it are discarded as targets even though their own
    inputs look fine — they were produced *from* the thing that changed.
    """
    scenario = build_scenario(env, tmp_path)
    _material(scenario, "materials/input.txt", b"source v1")
    first_hash = hash_bytes(b"source v1")

    first = _stage(scenario, "draft")
    scenario.resume().record_checkpoint(
        scenario.task_id, first.stage_id, material_hashes=(first_hash,)
    )
    second = _stage(scenario, "validate")
    scenario.resume().record_checkpoint(
        scenario.task_id, second.stage_id, material_hashes=(hash_bytes(b"source v1 too"),)
    )

    material = scenario.root / "materials" / "input.txt"
    _rewrite_preserving_mtime(material, b"source v2, edited in place")

    plan = scenario.resume().plan_resume(
        scenario.task_id,
        now=scenario.materials().snapshot(["materials/input.txt"]),
    )

    assert plan.must_redo
    assert plan.from_stage == first.stage_id, (
        "the stage whose input moved is the one to redo, not the stage after it"
    )
    assert plan.stopped_reason is not None
    assert "no longer match any source" in plan.stopped_reason


def test_a_deleted_source_fails_the_verification(env, tmp_path):  # type: ignore[no-untyped-def]
    """Unverifiable is not verified.

    A material that is gone is absent from the snapshot, which the comparison
    treats as changed. A resume that treated "cannot check" as "fine" would skip
    work whose input had vanished.
    """
    scenario = build_scenario(env, tmp_path)
    _material(scenario, "materials/gone.txt", b"here for now")
    stage = _stage(scenario, "draft")
    scenario.resume().record_checkpoint(
        scenario.task_id,
        stage.stage_id,
        material_hashes=(hash_bytes(b"here for now"),),
    )

    (scenario.root / "materials" / "gone.txt").unlink()

    plan = scenario.resume().plan_resume(
        scenario.task_id, now=scenario.materials().snapshot(["materials/gone.txt"])
    )
    assert plan.must_redo
    assert plan.from_stage == stage.stage_id


def test_a_task_with_no_checkpoint_reports_nothing_verified(env, tmp_path):  # type: ignore[no-untyped-def]
    scenario = build_scenario(env, tmp_path)
    plan: ResumePlan = scenario.resume().plan_resume(scenario.task_id, now={})
    assert plan.must_redo
    assert plan.through_seq == 0
    assert plan.stopped_reason is not None and "no checkpoint" in plan.stopped_reason


def test_the_next_run_carries_an_incrementing_attempt(env, tmp_path):  # type: ignore[no-untyped-def]
    """A resume is a new Run against the same Task — never a new Task."""
    scenario = build_scenario(env, tmp_path)
    stage = _stage(scenario, "draft")

    resume = scenario.resume()
    resume.record_checkpoint(scenario.task_id, stage.stage_id, material_hashes=(hash_bytes(b"m"),))

    # A second Run takes over the same Task, and a checkpoint on it proves the
    # attempt number is read from the history rather than counted.
    second_run = Run(run_id=RunId(new_id()), task_id=scenario.task_id, attempt=2)
    second_stage = Stage(
        stage_id=StageId(new_id()),
        task_id=scenario.task_id,
        run_id=second_run.run_id,
        name="draft-again",
        status=StageStatus.COMPLETED,
    )
    with scenario.store().unit(scenario.task_id) as work:
        work.put_run(second_run)
        work.put_stage(second_stage)
    resume.record_checkpoint(
        scenario.task_id, second_stage.stage_id, material_hashes=(hash_bytes(b"m"),)
    )

    plan = resume.plan_resume(scenario.task_id, now={"anything": hash_bytes(b"m")})
    assert plan.task_id == scenario.task_id, "resuming must not mint a new Task"
    assert plan.next_attempt == 3, "the attempt number must exceed the highest one on record"


# --------------------------------------------------------------------------- #
# scoped pause / stop
# --------------------------------------------------------------------------- #


def test_pause_carries_its_scope_on_the_event(env, tmp_path):  # type: ignore[no-untyped-def]
    """A stage-level pause and a run-level pause must be distinguishable after the fact."""
    scenario = build_scenario(env, tmp_path)
    resume = scenario.resume()

    resume.pause(scenario.task_id, scenario.run_id, stage_id=scenario.stage_id)
    scoped = _last_event(scenario, "run_paused")
    assert scoped.stage_id == str(scenario.stage_id)

    resume.resume_run(scenario.task_id, scenario.run_id)
    resume.pause(scenario.task_id, scenario.run_id)
    whole = _last_event(scenario, "run_paused")
    assert whole.stage_id is None, "an absent stage_id is what means 'the whole run'"


def test_pause_then_resume_returns_the_run_to_running(env, tmp_path):  # type: ignore[no-untyped-def]
    scenario = build_scenario(env, tmp_path)
    resume = scenario.resume()

    paused = resume.pause(scenario.task_id, scenario.run_id)
    assert paused.status is RunStatus.PAUSED

    resumed = resume.resume_run(scenario.task_id, scenario.run_id)
    assert resumed.status is RunStatus.RUNNING
    assert _last_event(scenario, "run_resumed") is not None


def test_resuming_a_run_that_is_not_paused_is_refused(env, tmp_path):  # type: ignore[no-untyped-def]
    scenario = build_scenario(env, tmp_path)
    with pytest.raises(ValueError, match="not paused"):
        scenario.resume().resume_run(scenario.task_id, scenario.run_id)


def test_stop_is_terminal_and_a_resume_makes_a_new_run(env, tmp_path):  # type: ignore[no-untyped-def]
    """A stopped Run is never resumed; a new Run against the same Task is.

    This is the rule that keeps a Task's history intact across an abandonment —
    the identity that survives is the Task's, not the Run's.
    """
    scenario = build_scenario(env, tmp_path)
    stopped = scenario.resume().stop(scenario.task_id, scenario.run_id)
    assert stopped.status is RunStatus.ABANDONED
    assert stopped.finished_at == SCENARIO_NOW
    with pytest.raises(ValueError, match="not paused"):
        scenario.resume().resume_run(scenario.task_id, scenario.run_id)

    successor = scenario.resume().start_run(
        scenario.task_id, Run(run_id=RunId(new_id()), task_id=scenario.task_id, attempt=2)
    )
    assert successor.task_id == scenario.task_id
    assert successor.status is RunStatus.RUNNING


def test_a_run_cannot_be_paused_through_another_task(env, tmp_path):  # type: ignore[no-untyped-def]
    """Run control is scoped by task, and the scope check is explicit."""
    from test_store_support import make_task

    scenario = build_scenario(env, tmp_path)
    other = make_task(title="Not this one", now=SCENARIO_NOW)
    scenario.store().create_task(other)

    with pytest.raises(ValueError, match="belongs to task"):
        scenario.resume().pause(other.task_id, scenario.run_id)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _last_seq(scenario: Scenario) -> int:
    found: int = scenario.session.execute(
        select(EventRow.seq).order_by(EventRow.seq.desc()).limit(1)
    ).scalar_one()
    return found


def _last_event(scenario: Scenario, type_value: str) -> EventRow:
    row: EventRow = scenario.session.execute(
        select(EventRow).where(EventRow.type == type_value).order_by(EventRow.seq.desc()).limit(1)
    ).scalar_one()
    return row


def _assert_has_event(scenario: Scenario, type_value: str) -> None:
    found = (
        scenario.session.execute(select(EventRow.type).where(EventRow.type == type_value))
        .scalars()
        .all()
    )
    assert found, f"expected a {type_value} event"
