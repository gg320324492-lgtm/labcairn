"""The ID aliases must be *nominal* types, not aliases.

ids.py claimed the type checker rejects a TaskId used as a RunId. With PEP 695
``type TaskId = RawId`` that claim was false — mypy accepted the misuse without
comment. The fix was ``NewType``, and this test is what holds it there: the
checker half of the claim cannot be asserted from Python, so it is asserted by
running mypy over a probe file.

The previous version of this assertion was ``new_id() == new_id().__class__ or
True``, which is true for every value at every time and asserted nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROBE = textwrap.dedent(
    """
    from labcairn.core.ids import RunId, TaskId

    def misuse(task: TaskId) -> RunId:
        return task
    """
)


def _mypy_rejects(source: str, tmp_path: Path) -> tuple[int, str]:
    probe = tmp_path / "probe.py"
    probe.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", "--strict", str(probe)],
        capture_output=True,
        text=True,
        # Both halves of the pipe are stated, and they agree. mypy is a
        # Python program, so its output encoding is otherwise the machine's
        # locale encoding, and it echoes the path of the file it was given,
        # which can carry characters the locale cannot read. Pinning only
        # the parent would be the same failure with the arrow turned round:
        # mypy would still write the locale's bytes and the parent would
        # read them as UTF-8.
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        timeout=300,
    )
    return result.returncode, result.stdout + result.stderr


def test_task_id_is_not_assignable_to_run_id(tmp_path: Path) -> None:
    code, output = _mypy_rejects(PROBE, tmp_path)
    assert code != 0, "mypy accepted a TaskId returned as a RunId:\n" + output
    assert "RunId" in output and "TaskId" in output, output


def test_an_unrelated_type_error_is_not_what_is_being_measured(tmp_path: Path) -> None:
    """A probe that fails for the wrong reason would pass the test above.

    The same probe annotated entirely as RunId must type-check cleanly, proving
    the failure above is about nominality and not a broken environment.
    """
    code, output = _mypy_rejects(PROBE.replace("TaskId", "RunId"), tmp_path)
    assert code == 0, "mypy failed on a control probe; the result would be meaningless:\n" + output


@pytest.mark.parametrize("alias", ["TaskId", "RunId", "StageId", "SourceId", "EvidenceId"])
def test_every_alias_exists_and_is_constructible(alias: str) -> None:
    module = __import__("labcairn.core.ids", fromlist=[alias])
    assert hasattr(module, alias)
