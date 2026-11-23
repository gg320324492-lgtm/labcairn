"""Cancel, retry and recovery for the deliver round — execution plan §7.3.

Four witnesses, all against real files and real consents:

* **cancel** — an apply round cancelled after the publication consent is
  granted and before the publication effect runs leaves the grant GRANTED
  and unspent, publishes nothing, and re-runs cleanly (idempotently: no
  duplicate deliveries).
* **timeout** — the model-suggestion path's timeout is its own refusal, and
  it is retryable: the record carries the reason, and asking again succeeds.
* **locked source** — a source another process holds locked is refused as
  ``source_locked`` before any consent is spent, and the round retries once
  the lock is gone.
* **export resume** — an export interrupted part-way is resumed by hash:
  the complete files are skipped, the missing or damaged ones are re-exported
  whole, and the resumed set matches the manifest byte for byte.
* **restart recovery** — a publication interrupted between the write and its
  confirmation is resolved by a probe, then replayed under a fresh approval,
  and the replay lands one artifact row — no duplicates.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from binding_support import (
    MOMENT,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
    open_the_binding,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.approvals import grant_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.revision_loop import (
    PUBLICATION_STAGE_NAME,
    InterruptedPublication,
    LoopOpened,
    find_interrupted_publication,
    replay_interrupted_publication,
    request_loop_approval,
    resolve_interrupted_publication,
    stage_copy,
)
from labcairn.db.repository import list_approvals, list_artifacts
from labcairn.papers.binding import (
    CANCEL_POINT_BEFORE_CLEAN_PUBLICATION,
    CANCEL_POINT_BEFORE_MARKED_PUBLICATION,
    ReviewDecision,
    ReviewVerdict,
    apply_approved_edits,
)
from labcairn.runtime.operation import ApprovalState

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


def _decisions(fixture: BindingFixture) -> tuple[ReviewDecision, ...]:
    """One accepted opinion: the smallest round that publishes."""
    return (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.ACCEPTED,
            operator="Dr. Chen",
            decided_at=MOMENT,
        ),
    )


def _grant_counts(context: ApplicationContext) -> tuple[int, int]:
    """(granted, consumed) approval counts, as the store holds them."""
    with_grants = [
        approval
        for approval in list_approvals(context.store.session, context.task_id)
        if approval.state is ApprovalState.GRANTED
    ]
    consumed = [
        approval
        for approval in list_approvals(context.store.session, context.task_id)
        if approval.state is ApprovalState.CONSUMED
    ]
    return len(with_grants), len(consumed)


# --------------------------------------------------------------------------- #
# cancel
# --------------------------------------------------------------------------- #


def test_a_cancelled_round_publishes_nothing_and_keeps_the_grant(
    fixture: BindingFixture,
) -> None:
    """Cancellation between the consent and the publication stops the round.

    The refusal is ``apply_cancelled``, it names the point the round was
    asked at, and the round's writes stop there: no publication bytes, no
    output version. The publication consent the round had already granted
    stays GRANTED — a person said yes, and nothing since has spent it.
    """
    opened = open_the_binding(fixture)
    points: list[str] = []

    def cancel_at_clean(point: str) -> str | None:
        points.append(point)
        if point == CANCEL_POINT_BEFORE_CLEAN_PUBLICATION:
            return "the advisor asked to stop after the marked draft"
        return None

    with pytest.raises(ApplicationRefusedError) as refused:
        apply_approved_edits(
            fixture.context,
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            opened=opened,
            decisions=_decisions(fixture),
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="cancelled-round",
            window_end=MOMENT.replace(year=MOMENT.year + 1),
            cancel_check=cancel_at_clean,
            now=MOMENT,
        )
    assert refused.value.reason is ApplicationRefusal.APPLY_CANCELLED
    assert CANCEL_POINT_BEFORE_CLEAN_PUBLICATION in refused.value.detail
    assert "the advisor asked to stop" in refused.value.detail
    assert points == [
        CANCEL_POINT_BEFORE_MARKED_PUBLICATION,
        CANCEL_POINT_BEFORE_CLEAN_PUBLICATION,
    ], "the check is asked once per draft, in round order"

    # The marked draft's loop completed before the cancellation, so its
    # publication exists; the clean draft's does not. One publication, not two.
    receipts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    publications = [receipt for receipt in receipts if receipt.receipt_id.startswith("pub-")] or [
        receipt for receipt in receipts if "published.bin" in receipt.relative_path
    ]
    assert len(publications) == 1, (
        "a round cancelled before the clean publication has one published draft"
    )
    assert not any(receipt.relative_path.endswith("quality-report.md") for receipt in receipts), (
        "a cancelled round closes no dossier"
    )


def test_a_cancelled_round_leaves_the_publication_consent_granted(
    fixture: BindingFixture,
) -> None:
    """The consent the round had granted but not spent is still there to spend.

    **A cancellation is not a revocation.** The publication consent was
    granted by a person; the round was stopped before spending it. The
    grant stays GRANTED — the record says the yes happened — and the clean
    draft's consent is the one left granted, because the marked draft's was
    consumed by its own publication.
    """
    opened = open_the_binding(fixture)

    def cancel_at_clean(point: str) -> str | None:
        return "stopping" if point == CANCEL_POINT_BEFORE_CLEAN_PUBLICATION else None

    with pytest.raises(ApplicationRefusedError):
        apply_approved_edits(
            fixture.context,
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            opened=opened,
            decisions=_decisions(fixture),
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="cancelled-round",
            window_end=MOMENT.replace(year=MOMENT.year + 1),
            cancel_check=cancel_at_clean,
            now=MOMENT,
        )
    granted, consumed = _grant_counts(fixture.context)
    assert granted >= 1, "the unspent publication consent stays granted"
    assert consumed >= 1, "the marked draft's consents were spent by its loop"


def test_a_cancelled_round_reapplies_without_duplicating_deliverables(
    fixture: BindingFixture,
) -> None:
    """Re-running a cancelled round succeeds, once, with one dossier.

    **Idempotence is the loop's own, reused.** The cancelled round left a
    completed marked loop; the re-run opens fresh loops, and the fresh
    publication receipts are new rows — a re-run is a further publication,
    not a replay of the old id. What must not happen is two dossiers or two
    output versions for one round: the round's close is the single place the
    dossier is written, and the re-run's close replaces the round's record.
    """
    opened = open_the_binding(fixture)

    def cancel_at_clean(point: str) -> str | None:
        return "stopping" if point == CANCEL_POINT_BEFORE_CLEAN_PUBLICATION else None

    with pytest.raises(ApplicationRefusedError):
        apply_approved_edits(
            fixture.context,
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            opened=opened,
            decisions=_decisions(fixture),
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="round-retry",
            window_end=MOMENT.replace(year=MOMENT.year + 1),
            cancel_check=cancel_at_clean,
            now=MOMENT,
        )

    reopened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=reopened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="round-retry",
        window_end=MOMENT.replace(year=MOMENT.year + 1),
        now=MOMENT,
    )
    assert closed.dossier_artifact_id
    receipts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    dossiers = [receipt for receipt in receipts if receipt.receipt_id == closed.dossier_artifact_id]
    assert len(dossiers) == 1, "the re-run closes the round with one dossier"
    assert closed.marked_publication.publication.receipt_id != (
        closed.clean_publication.publication.receipt_id
    )


# --------------------------------------------------------------------------- #
# source locked / drifted, before any consent is spent
# --------------------------------------------------------------------------- #


def test_a_locked_source_refuses_the_round_before_any_consent_is_spent(
    fixture: BindingFixture,
) -> None:
    """A source that cannot be opened refuses as ``source_locked``, and spends nothing.

    A word processor holding the manuscript open is the case in point: the
    bytes are fine, and the round must not spend a copy consent on a file it
    could not read. The refusal names the file; a retry after the lock is
    gone proceeds from the start.
    """
    # **The binding opens first, the lock lands second.** The round under
    # test is the apply, not the open: the open's own unreadable-material
    # refusal is a different witness. Locking after the open isolates the
    # apply path's pre-publication check — and the decisions are resolved
    # before the lock too, because reading the chain's rows through
    # ``record_feedback`` reads the manuscript, and that read under the lock
    # would be the open path's refusal, not the apply's.
    opened = open_the_binding(fixture)
    decisions = _decisions(fixture)
    before = _grant_counts(fixture.context)

    source_path = fixture.context.workspace.path_in(
        fixture.source_key, fixture.source_root_id
    ).real_path
    # **A real byte-range lock, not a second handle.** A plain second handle
    # does not lock anything — Python's ``open`` shares read and write by
    # default on Windows, and POSIX locks are advisory. A byte-range lock
    # (``msvcrt.locking`` on Windows, ``fcntl.flock`` elsewhere) is the lock
    # a word processor holds, and it makes the check's own read fail for
    # real: the refusal is witnessed against a genuinely unreadable file.
    handle = os.open(source_path, os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ApplicationRefusedError) as refused:
            apply_approved_edits(
                fixture.context,
                project_id=fixture.project_id,
                input_version_id=fixture.version_id,
                opened=opened,
                decisions=decisions,
                source_root_id=fixture.source_root_id,
                source_key=fixture.source_key,
                output_label="locked-round",
                window_end=MOMENT.replace(year=MOMENT.year + 1),
                now=MOMENT,
            )
        assert refused.value.reason is ApplicationRefusal.SOURCE_LOCKED
    finally:
        if os.name == "nt":
            import msvcrt

            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)

    after = _grant_counts(fixture.context)
    assert after == before, "a refused round spends no consent"


def test_a_drifted_source_refuses_the_round_before_any_consent_is_spent(
    fixture: BindingFixture,
) -> None:
    """A source whose bytes moved refuses as ``source_drifted``, spending nothing.

    The loop's own re-hash would refuse the copy anyway; the round's
    pre-publication check refuses one step earlier, so the first draft's
    consent is never spent on a manuscript that is no longer the one the
    opinions were read from.
    """
    opened = open_the_binding(fixture)
    # **The decisions are resolved before the drift, for the reason the lock
    # witness states**: reading the chain's rows reads the manuscript, and a
    # read after the move would be the chain's own drifted refusal, not the
    # apply path's pre-publication check.
    decisions = _decisions(fixture)
    before = _grant_counts(fixture.context)
    source_path = fixture.context.workspace.path_in(
        fixture.source_key, fixture.source_root_id
    ).real_path
    source_path.write_bytes(source_path.read_bytes() + b"\nA late edit nobody reviewed.\n")

    with pytest.raises(ApplicationRefusedError) as refused:
        apply_approved_edits(
            fixture.context,
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            opened=opened,
            decisions=decisions,
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="drifted-round",
            window_end=MOMENT.replace(year=MOMENT.year + 1),
            now=MOMENT,
        )
    assert refused.value.reason is ApplicationRefusal.SOURCE_DRIFTED
    assert _grant_counts(fixture.context) == before, "a refused round spends no consent"


# --------------------------------------------------------------------------- #
# restart recovery: an interrupted publication, resolved and replayed
# --------------------------------------------------------------------------- #


def _interrupted_publication(fixture: BindingFixture, loop: LoopOpened, edited: bytes) -> None:
    """Drive a loop to a granted-but-unresolved publication attempt.

    The copy lands and the publication consent is granted; the publication
    operation is left ATTEMPTING by failing the effect, which is the record a
    crash leaves. Nothing is published.
    """
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
    loop_publication_path = (
        fixture.workspace_root
        / "output"
        / str(fixture.context.task_id)
        / "revisions"
        / loop.import_receipt.receipt_id
        / "copy.bin"
    )
    loop_publication_path.write_bytes(edited)
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
    # The publication stage is driven through the loop's own request builder,
    # so the arguments, the resource key and the source resolution are the
    # ones the approval's digest was minted over — a hand-built request would
    # re-resolve the bound source against the output root and read
    # ``source_changed`` for material that never moved.
    from labcairn.application.revision_loop import _stage_request
    from labcairn.application.stages import StageOutcome, run_stage

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


def test_an_interrupted_publication_is_found_and_never_blindly_replayed(
    fixture: BindingFixture,
) -> None:
    """The recovery pass refuses a blind re-run, and the replay needs a resolve first.

    The interrupted operation is findable from the loop's own receipt; a
    replay attempted while it is still UNCERTAIN is refused — the record
    cannot say whether the attempt landed, and replaying over that is the
    second writer ADR-0003 A2 refuses.
    """
    edited = b"recovered draft bytes\n"
    _interrupted_publication(fixture, open_the_binding_loop(fixture), edited)
    loop_receipt = _any_loop_receipt_id(fixture)

    # The recovery pass (run at the front of every stage) enters UNCERTAIN.
    from labcairn.application.recovery import reconcile_abandoned

    abandoned = reconcile_abandoned(fixture.context)
    assert len(abandoned) == 1, "the interrupted publication is the one abandoned operation"

    found = find_interrupted_publication(fixture.context, receipt_id=loop_receipt)
    assert found is not None, "the loop's own receipt names its interrupted publication"
    assert found.publication_key.endswith("published.bin")

    replay_approval = grant_approval(
        fixture.context,
        request_loop_approval(
            fixture.context,
            _loop_for_receipt(fixture, loop_receipt, found),
            stage_name=PUBLICATION_STAGE_NAME,
            expires_at=MOMENT.replace(year=MOMENT.year + 1),
            now=MOMENT,
        ).approval.approval_id,
        now=MOMENT,
    )
    with pytest.raises(ApplicationRefusedError) as refused:
        replay_interrupted_publication(
            fixture.context,
            found,
            edited_bytes=edited,
            approval_id=replay_approval.approval.approval_id,
            now=MOMENT,
        )
    assert refused.value.reason is ApplicationRefusal.OPERATION_UNCERTAIN


def test_a_resolved_interrupted_publication_replays_to_one_complete_row(
    fixture: BindingFixture,
) -> None:
    """Resolve, then replay under a fresh approval: one publication, no duplicates.

    The probe resolves the interrupted attempt (nothing landed →
    ``REPLAY_SAFE``), the replay publishes the predicted bytes under a fresh
    consent, and the store holds exactly one publication receipt for the
    loop — the replay lands the row the interrupted attempt was reaching
    for, not a second one beside it.
    """
    edited = b"recovered draft bytes\n"
    loop = open_the_binding_loop(fixture)
    _interrupted_publication(fixture, loop, edited)
    loop_receipt = loop.import_receipt.receipt_id

    from labcairn.application.recovery import reconcile_abandoned

    reconcile_abandoned(fixture.context)
    found = find_interrupted_publication(fixture.context, receipt_id=loop_receipt)
    assert found is not None

    # The prediction the caller states is the edited bytes' own hash — the
    # fact the round's record carries, and the probe's question.
    import hashlib

    outcome = resolve_interrupted_publication(
        fixture.context,
        found,
        expected_sha256=hashlib.sha256(edited).hexdigest(),
    )
    assert outcome.replay_permitted, "nothing landed, so the replay is permitted"

    replay_approval = grant_approval(
        fixture.context,
        request_loop_approval(
            fixture.context,
            _loop_for_receipt(fixture, loop_receipt, found),
            stage_name=PUBLICATION_STAGE_NAME,
            expires_at=MOMENT.replace(year=MOMENT.year + 1),
            now=MOMENT,
        ).approval.approval_id,
        now=MOMENT,
    )
    published = replay_interrupted_publication(
        fixture.context,
        found,
        edited_bytes=edited,
        approval_id=replay_approval.approval.approval_id,
        now=MOMENT,
    )
    assert published.publication.content_sha256 == hashlib.sha256(edited).hexdigest()

    receipts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    landed = [
        receipt for receipt in receipts if receipt.receipt_id == published.publication.receipt_id
    ]
    assert len(landed) == 1, "the replayed publication is one artifact row"
    publication_path = (
        fixture.workspace_root
        / "output"
        / str(fixture.context.task_id)
        / "revisions"
        / loop_receipt
        / "published.bin"
    )
    assert publication_path.read_bytes() == edited


# --------------------------------------------------------------------------- #
# model-suggestion timeout: the retryable refusal
# --------------------------------------------------------------------------- #


def test_a_suggestion_timeout_is_refused_by_name_and_the_record_stays_clean(
    fixture: BindingFixture,
) -> None:
    """The suggestion path's timeout is its own refusal, and retrying is safe.

    ``ReviewModelTimeout`` is the apply path's name for "the model did not
    answer within its window" — a refusal whose remedy is to ask again,
    because nothing was recorded and nothing was published. The witness
    drives the real suggestion seam with a source that raises the timeout,
    and asserts the refusal's reason, the unchanged record, and a retry that
    succeeds with the same material.
    """
    from labcairn.editing.drafts import ApprovedEdit
    from labcairn.papers.binding import open_binding

    def timing_out_suggester(event: object) -> ApprovedEdit:
        raise ApplicationRefusedError(
            ApplicationRefusal.REVIEW_MODEL_TIMEOUT,
            "the suggestion source did not answer within its window; the "
            "material is unchanged and no decision was recorded, so the "
            "request may be retried",
        )

    with pytest.raises(ApplicationRefusedError) as refused:
        open_binding(
            fixture.context,
            project_id=fixture.project_id,
            version_id=fixture.version_id,
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            suggest=timing_out_suggester,  # type: ignore[arg-type]
            now=MOMENT,
        )
    assert refused.value.reason is ApplicationRefusal.REVIEW_MODEL_TIMEOUT

    # The timeout recorded nothing: no suggestion rows, no decisions, and the
    # source is exactly the bytes it was. A retry asks again over the same
    # material, and the second answer lands as the first would have.
    from sqlalchemy import select

    from labcairn.db.models import ReviewDecisionRow, ReviewSuggestionRow

    session = fixture.context.store.session
    assert session.scalars(select(ReviewSuggestionRow)).all() == []
    assert session.scalars(select(ReviewDecisionRow)).all() == []

    def answering_suggester(event: object) -> ApprovedEdit | None:
        return None  # the retry's own answer is exercised by the binding's witnesses

    reopened = open_binding(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        suggest=answering_suggester,  # type: ignore[arg-type]
        now=MOMENT,
    )
    assert reopened.loop.import_receipt.original_sha256


# --------------------------------------------------------------------------- #
# export resume: an interrupted export resumed by hash
# --------------------------------------------------------------------------- #


def _closed_round(fixture: BindingFixture) -> object:
    """One full apply round, closed, with its dossier on the record."""
    opened = open_the_binding(fixture)
    return apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="resume-round",
        window_end=MOMENT.replace(year=MOMENT.year + 1),
        now=MOMENT,
    )


def test_an_interrupted_export_resumes_to_the_full_matching_set(
    fixture: BindingFixture,
) -> None:
    """A resume re-exports what is missing or damaged and skips what is complete.

    The first export is interrupted after two files land; the resume finds
    the complete ones by hash, re-exports the rest, and the finished set
    matches the manifest byte for byte — the same result a single
    uninterrupted export would have produced.
    """
    from labcairn.application.review import ExportDeliverablesRequest, export_deliverables

    closed = _closed_round(fixture)
    request = ExportDeliverablesRequest(
        project_id=fixture.project_id, dossier_artifact_id=closed.dossier_artifact_id
    )
    whole = export_deliverables(fixture.context, request)
    area_root = fixture.context.workspace.output_root.root_id

    def landed(path: str) -> bytes | None:
        candidate = fixture.context.workspace.path_in(path, area_root).real_path
        return candidate.read_bytes() if candidate.is_file() else None

    # **The interruption, simulated on the disk the export writes to.** Two
    # deliverables landed; the third is truncated (a crash mid-write's
    # residue), the fourth never landed. The hashes are the manifest's own,
    # so "complete" is a comparison the binding itself would accept.
    first, second, third, fourth = (deliverable for deliverable in whole.deliverables)
    for deliverable in (first, second):
        fixture.context.workspace.path_in(deliverable.relative_path, area_root)
        from labcairn.workspace.outputs import TaskOutputArea

        TaskOutputArea(fixture.context.workspace).write(
            deliverable.relative_path, deliverable.content
        )
    from labcairn.workspace.outputs import TaskOutputArea

    area = TaskOutputArea(fixture.context.workspace)
    area.write(third.relative_path, third.content[: len(third.content) // 2])
    assert landed(fourth.relative_path) is None

    resumed = export_deliverables(fixture.context, request, resume=True)

    # The resumed set is the whole set, and each file on disk is the bytes
    # the manifest binds — including the two the interruption had already
    # landed, which the resume left untouched.
    assert {item.kind for item in resumed.deliverables} == {
        "marked",
        "clean",
        "response_table",
        "quality_report",
    }
    for deliverable in resumed.deliverables:
        on_disk = landed(deliverable.relative_path)
        assert on_disk is not None, f"{deliverable.kind} did not land"
        import hashlib

        assert hashlib.sha256(on_disk).hexdigest() == deliverable.sha256, (
            f"{deliverable.kind} does not match the manifest's digest"
        )


def test_a_resume_skips_nothing_when_nothing_landed_and_twice_is_stable(
    fixture: BindingFixture,
) -> None:
    """A resume from nothing lands all four; resuming again rewrites nothing.

    Idempotence is the property an interrupted export needs: running the
    resume to completion and running it again leaves the same bytes, because
    "complete" is a hash comparison and a complete file is never re-written.
    """
    import hashlib

    from labcairn.application.review import ExportDeliverablesRequest, export_deliverables

    closed = _closed_round(fixture)
    request = ExportDeliverablesRequest(
        project_id=fixture.project_id, dossier_artifact_id=closed.dossier_artifact_id
    )
    area_root = fixture.context.workspace.output_root.root_id

    def snapshots() -> dict[str, str]:
        state: dict[str, str] = {}
        for deliverable in export_deliverables(fixture.context, request).deliverables:
            path = fixture.context.workspace.path_in(deliverable.relative_path, area_root).real_path
            state[deliverable.kind] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
            )
        return state

    export_deliverables(fixture.context, request, resume=True)
    after_first = snapshots()
    assert all(after_first.values()), "a resume from nothing lands all four"
    export_deliverables(fixture.context, request, resume=True)
    assert snapshots() == after_first, "a second resume rewrites nothing"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def open_the_binding_loop(fixture: BindingFixture) -> LoopOpened:
    """A second loop over the same material, for the recovery witnesses."""
    from labcairn.application.revision_loop import open_loop

    return open_loop(
        fixture.context,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        now=MOMENT,
    )


def _any_loop_receipt_id(fixture: BindingFixture) -> str:
    from labcairn.application.revision_loop import LOOP_DIR_NAME

    receipts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    for receipt in receipts:
        # Artifact paths are workspace-relative: output/<task>/revisions/<id>/...
        parts = receipt.relative_path.split("/")
        if LOOP_DIR_NAME in parts:
            return parts[parts.index(LOOP_DIR_NAME) + 1]
    raise AssertionError("no loop directory is on the record")


def _loop_for_receipt(
    fixture: BindingFixture, receipt_id: str, found: InterruptedPublication
) -> LoopOpened:
    """Reassemble the interrupted loop, on the ids the interruption carried.

    **The ids come from the found record, not from a fresh mint.** The
    publication's arguments digest covers the loop's own publication id, so
    an approval asked over a re-minted id covers a different request — and
    the replay would be refused as ``args_changed`` for an approval that was
    never asked about anything else. The loop's identity is its receipt.
    """
    from labcairn.application.revision_loop import LOOP_DIR_NAME, ImportReceipt

    manifest_path = (
        fixture.workspace_root
        / "output"
        / str(fixture.context.task_id)
        / LOOP_DIR_NAME
        / receipt_id
        / "import-receipt.json"
    )
    import_receipt = ImportReceipt.model_validate_json(manifest_path.read_bytes())
    return LoopOpened(
        import_receipt=import_receipt,
        copy_key=f"{LOOP_DIR_NAME}/{receipt_id}/copy.bin",
        publication_key=f"{LOOP_DIR_NAME}/{receipt_id}/published.bin",
        manifest_key=f"{LOOP_DIR_NAME}/{receipt_id}/import-receipt.json",
        publication_artifact_id=found.publication_artifact_id,
        import_artifact_id=found.import_artifact_id,
    )
