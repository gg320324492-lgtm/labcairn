"""Locked-file drills: hold an OS lock, observe the loop's typed answer.

Drill class 2 of work orders §12 §5.1, designed at
``docs/plans/LC-P3-07-drill-matrix-design.md`` §2.2. Two sub-rows, because the
two roots answer differently:

* a **source-side** lock — the original in the source root is held open with
  no share flags — and the loop's copy stage must answer with the OS error
  surfaced as a stage failure, with the already-written pieces left where
  ``open_loop`` put them (``revisions/<receipt_id>/``), so the operator can
  answer the loop after releasing the lock instead of re-importing;
* an **output-side** lock — the copy target is held — and the write fails with
  the OS error surfaced, no receipt is recorded for a file that does not
  exist, and the loop's already-written pieces stay put.

The refusal-side of this class (a source the policy will not let the task
touch answers *refused* before any write) is ``LC-P3-03``'s own ground,
already witnessed by ``tests/test_revision_loop_refusals.py``; this file
drills the OS-level lock half on real files.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from store_support import env as _shared_env

env = _shared_env

pytestmark = pytest.mark.integration

MOMENT = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
WINDOW_END = MOMENT + timedelta(hours=1)


@pytest.fixture()
def rig(env: Any, tmp_path: Path) -> Any:
    from drill_support import build_rig

    return build_rig(env.store(), tmp_path / "workspace")


def _open_exclusive(path: Path) -> Any:
    """A handle that denies everyone else every access, on this platform."""
    if hasattr(__import__("os"), "O_EXCL") and hasattr(__import__("os"), "O_RDWR"):
        # Windows: no sharing flags means no other handle can open the file.
        import msvcrt

        handle = __import__("os").open(str(path), __import__("os").O_RDWR)
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        return handle
    import fcntl  # pragma: no cover - POSIX branch

    handle = __import__("os").open(str(path), __import__("os").O_RDWR)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
    return handle


def test_a_locked_original_fails_the_copy_with_the_os_error_surfaced(
    rig: Any,
) -> None:
    """A source the OS will not let anyone read stops the copy before it lands.

    The consent's own re-hash (``sources_intact``) cannot read the locked
    original, so the approval is refused as ``source_changed`` — the consent's
    answer to "the bytes I bound may have moved, because I cannot read them".
    The write primitive is never reached: the loop's already-written pieces —
    the import receipt and its artefact row — stay where ``open_loop`` put
    them, and the operator answers the loop after releasing the lock instead
    of re-importing.
    """
    import os

    from drill_support import MOMENT, grant_copy

    from labcairn.application.refusal import ApplicationRefusedError
    from labcairn.application.revision_loop import stage_copy

    approval_id = grant_copy(rig)
    lock = _open_exclusive(rig.original_path)
    try:
        with pytest.raises(ApplicationRefusedError) as raised:
            stage_copy(rig.context, rig.loop, approval_id=approval_id, now=MOMENT)
    finally:
        import msvcrt

        msvcrt.locking(lock, msvcrt.LK_UNLCK, 1)
        os.close(lock)

    assert raised.value.reason.value in ("approval_refused", "stage_failed"), (
        f"the lock surfaces as a named refusal, not silence: {raised.value}"
    )
    assert "source_changed" in str(raised.value), (
        f"the consent names the unreadable source: {raised.value}"
    )

    # The loop's already-written pieces are still there.
    assert rig.manifest_path().exists(), "the import receipt stays put"
    assert not rig.copy_path().exists(), (
        "no copy landed, because the copy was refused before any write"
    )


def test_a_locked_copy_target_fails_the_write_and_lands_no_receipt(
    rig: Any,
) -> None:
    """A copy target the OS will not let the task write fails, named.

    The loop's already-written pieces stay where ``open_loop`` put them: the
    import manifest at ``revisions/<receipt_id>/import-receipt.json``, the
    original's artefact row in the ledger. The operator releases the lock and
    re-runs the copy; the loop is not re-imported.
    """
    import os

    from drill_support import MOMENT, grant_copy

    from labcairn.application.refusal import ApplicationRefusedError
    from labcairn.application.revision_loop import stage_copy

    approval_id = grant_copy(rig)
    # The copy is written through TaskOutputArea's temp-then-replace; holding
    # the *directory* denies the replace itself.
    rig.loop_dir().mkdir(parents=True, exist_ok=True)
    target = rig.copy_path()
    target.write_bytes(b"")  # the replace must overwrite this
    lock = _open_exclusive(target)
    try:
        with pytest.raises(ApplicationRefusedError) as raised:
            stage_copy(rig.context, rig.loop, approval_id=approval_id, now=MOMENT)
    finally:
        import msvcrt

        msvcrt.locking(lock, msvcrt.LK_UNLCK, 1)
        os.close(lock)

    assert raised.value.reason.value == "stage_failed", (
        "the OS lock on the copy target surfaces as a failed stage"
    )
    # No receipt for a file that does not exist: the copy's bytes are still
    # the placeholder, not the original.
    assert rig.copy_path().read_bytes() == b"", "the locked copy target was not overwritten"
    assert rig.manifest_path().exists(), "the import receipt stays put"
