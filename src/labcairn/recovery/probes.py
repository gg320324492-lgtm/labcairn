"""The probe: a read-only question of the filesystem.

Its entire job is to answer "are the bytes this operation predicted at the path
this operation named?" — and to answer it *without touching anything*. A probe
that repaired as it went would be a second writer on the exact path where a
second writer is most expensive.

The four verdicts come straight from ADR-0003 C2's reconcile branch:

============================  ==========================================
probe found                   resolution
============================  ==========================================
file absent                   ``REPLAY_SAFE`` — provably did not land
file present, hash matches    ``CONFIRMED``  — it landed
file present, hash differs    ``CONFLICT``   — a human must decide
file unreadable / is a dir     ``CONFLICT``   — fail closed
============================  ==========================================

The last row is the one that is easy to get wrong. An unreadable target is not
evidence that the write did not happen; it is evidence that we cannot tell, and
"we cannot tell" is what ``UNCERTAIN`` means. Mapping an unreadable path onto
``REPLAY_SAFE`` would reopen the exact blind spot this ticket exists to close.
"""

from __future__ import annotations

from pathlib import Path

from labcairn.recovery.contracts import (
    ContentHash,
    ProbeVerdict,
    ReconciliationResolution,
    resource_path,
)
from labcairn.security.approval import content_hash


class FileSystemProbe:
    """Ask the filesystem what is at a canonical resource key."""

    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    def inspect(self, resource_key: str, expected_sha256: ContentHash) -> ProbeVerdict:
        """Read-only. Never creates, writes, truncates or removes anything.

        The absence check uses :meth:`Path.exists`, which follows symlinks. A
        dangling symlink at the target is therefore reported as *absent* — and
        that is right, because a dangling symlink cannot hold the bytes the
        operation predicted, so the effect demonstrably did not land there.
        """
        target = resource_path(self._root, resource_key)

        try:
            present = target.exists()
        except OSError as exc:  # pragma: no cover - stat() failing on a real path
            return self._conflict(
                resource_key,
                expected_sha256,
                None,
                f"cannot stat the target: {exc}",
            )

        if not present:
            return ProbeVerdict(
                resolution=ReconciliationResolution.REPLAY_SAFE,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=None,
                detail="no file at the canonical path; the effect provably did not land",
            )

        if target.is_dir():
            return self._conflict(
                resource_key,
                expected_sha256,
                None,
                "a directory sits at the canonical path",
            )

        try:
            observed = content_hash(target)
        except OSError as exc:
            return self._conflict(
                resource_key,
                expected_sha256,
                None,
                f"the target exists but cannot be read: {exc}",
            )

        if observed == expected_sha256:
            return ProbeVerdict(
                resolution=ReconciliationResolution.CONFIRMED,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=observed,
                detail="the predicted bytes are on disk; the effect landed",
            )

        return ProbeVerdict(
            resolution=ReconciliationResolution.CONFLICT,
            resource_key=resource_key,
            expected_sha256=expected_sha256,
            observed_sha256=observed,
            detail=(
                "a file exists at the canonical path but its content is not what this "
                "operation predicted. It may be a partial write, an earlier revision, "
                "or something else entirely. No automatic action: overwriting could "
                "destroy work this operation did not produce."
            ),
        )

    @staticmethod
    def _conflict(
        resource_key: str,
        expected_sha256: ContentHash,
        observed: ContentHash | None,
        detail: str,
    ) -> ProbeVerdict:
        return ProbeVerdict(
            resolution=ReconciliationResolution.CONFLICT,
            resource_key=resource_key,
            expected_sha256=expected_sha256,
            observed_sha256=observed,
            detail=detail,
        )


__all__ = ["FileSystemProbe"]
