"""The completed feedback form's walk into the system's issue record.

P4-PILOT §9.4 records each problem twice -- on the unified feedback form
and in the system. ``scripts/pilot_feedback_ingest.py`` is the walk from
the first record to the second, and what this file witnesses is that the
walk is honest in both directions:

* **What the dry run previews is what ``--apply`` writes.** Both read from
  one parsed plan, so a preview cannot promise a record the apply would
  not make.
* **The vocabularies close at the tool's own door.** A severity or type
  word the form does not offer is refused by name before anything is
  written; a word the *record* does not hold cannot be written either,
  because the write goes through the application layer's
  :func:`record_issue`, not around it.
* **Re-ingesting a file does not duplicate rows.** The issue id is the
  record's primary key, so the second pass skips what the first recorded
  -- a problem counted twice would be a finding the trial does not have.

The store is a real migrated database in the test's own temporary
directory; the workspace is bound under it the way the CLI binds one. No
repository data is touched.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from child_encoding import (
    CHILD_OUTPUT_ERRORS,
    PYTHON_OUTPUT_ENCODING,
    python_child_environment,
)
from sqlalchemy import select
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.core.ids import new_id
from labcairn.db.models import PaperProjectRow, PilotIssueRow

env = _shared_env

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "pilot_feedback_ingest.py"

#: The interpreter that runs the script. The subprocess is deliberate: the
#: tool is a console entry point, and its exit status -- the contract a
#: caller's script reads -- is part of what is witnessed.
INTERPRETER = sys.executable


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def task_id() -> str:
    """A task id in the record's own shape: a UUIDv7.

    The record's id types are the application's, and a task id is a UUIDv7
    there -- the API refuses anything else -- so the forms this file sends
    name a task id the record could actually hold.
    """
    return str(new_id())


def _make_workspace(root: Path, task_id: str) -> Path:
    """A minimal LabCairn workspace: its config, its policy, its roots.

    The config names the database the fixture migrated, so ``--apply``
    writes the rows this file's own session reads back. The policy is the
    file shape ``load_policy`` reads; the issue record consults no
    capability, but the file is written anyway so the workspace reads as
    a real one.
    """
    workspace = root / "workspace"
    (workspace / "materials").mkdir(parents=True, exist_ok=True)
    config = {
        "schema_version": 1,
        "database": str(root / "labcairn.db"),
        "source_dirs": ["materials"],
        "current_task": task_id,
    }
    config_dir = workspace / ".labcairn"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "workspace.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (config_dir / "policy.json").write_text(
        json.dumps({"schema_version": 1, "rules": []}, indent=2), encoding="utf-8"
    )
    return workspace


def _seed_project(env: StoreEnv, project_id: str = "proj-1") -> None:
    """One paper project, the way the version graph's scaffolding writes it.

    An issue is about a project, and the layer refuses a project the store
    does not hold -- so the happy path needs one row that is not the
    tool's own concern to create.
    """
    env.session.add(
        PaperProjectRow(
            project_id=project_id,
            workspace_id="ws-1",
            subject_pseudonym="subject-1",
            consent_ref=None,
            created_at=datetime(2026, 11, 24, tzinfo=UTC),
        )
    )
    env.session.commit()


def _write_forms(path: Path, payload: Any) -> Path:
    """The forms file, as an operator would hand it over."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """The tool, as a caller runs it, with this repository's src on the path.

    The src directory goes on ``PYTHONPATH`` ahead of whatever the
    environment already names: an editable install points at the checkout
    it was made in, and a test in a worktree must read the worktree's own
    code, not another tree's.
    """
    script_env = dict(os.environ)
    src = str(SCRIPT.parent.parent / "src")
    existing = script_env.get("PYTHONPATH")
    script_env["PYTHONPATH"] = f"{src}{os.pathsep}{existing}" if existing else src
    # The child's write side is pinned as well as the parent's decode.
    # Pinning one half alone turns the failure around rather than fixing
    # it: a child that writes the machine's code page read as UTF-8 fails
    # the same way. The environment the child is given carries its
    # PYTHONPATH and its own settings, so the encoding variables are added
    # to it rather than replacing it.
    script_env = python_child_environment(script_env)
    return subprocess.run(
        [INTERPRETER, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding=PYTHON_OUTPUT_ENCODING,
        errors=CHILD_OUTPUT_ERRORS,
        env=script_env,
        timeout=120,
    )


def _script_module() -> ModuleType:
    """The tool's module, loaded from its path.

    ``scripts/`` is not a package, so the file is loaded the way a caller
    runs it -- by path -- and its import-time assertions run here too. The
    module is registered under its name before it executes, because the
    dataclasses it defines resolve their own annotations through
    ``sys.modules`` when a test first builds one.
    """
    name = "pilot_feedback_ingest_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def _a_form(task_id: str, **overrides: Any) -> dict[str, Any]:
    """One valid completed form, varied by the test that asks for it."""
    form: dict[str, Any] = {
        "project_id": "proj-1",
        "task_id": task_id,
        "submission_id": "form-2026-11-24-a",
        "submitter_role": "advisor",
        "session_date": "2026-11-24",
        "stages_used": ["import", "review"],
        "issues": [
            {
                "issue_id": "iss-001",
                "title": "suggestion list ignored the language filter",
                "what_happened": "the list showed English suggestions for a Chinese draft",
                "stage": "model-suggestions",
                "severity": "severe",
                "type": "model",
            },
            {
                "issue_id": "iss-002",
                "title": "import stalled on a 40 MB PDF",
                "what_happened": "the progress bar froze for two minutes",
                "steps_to_reproduce": "import the large PDF",
                "expected": "import completes",
                "stage": "import",
                "severity": "blocking",
                "type": "performance",
                "duration_seconds": 120.5,
                "retry_count": 1,
                "frequency": "every time",
                "workaround": "split the PDF by hand",
            },
        ],
    }
    form.update(overrides)
    return {"forms": [form]}


def _rows(env: StoreEnv) -> list[PilotIssueRow]:
    """Every issue row, in id order, as the store holds them."""
    statement = select(PilotIssueRow).order_by(PilotIssueRow.issue_id)
    return list(env.session.scalars(statement).all())


# --------------------------------------------------------------------------- #
# the dry run
# --------------------------------------------------------------------------- #


def test_a_dry_run_previews_the_records_and_writes_nothing(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """The dry run lists what would be recorded, and the store stays empty.

    **The preview is the point of the mode**: an operator checks a stack of
    forms before anything is written, so the report has to name the records
    the apply would make -- with the mapped words, not the form's -- and
    the store has to come out of it untouched.
    """
    forms = _write_forms(tmp_path / "forms.json", _a_form(task_id))

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "2 issue(s) would be created" in finished.stdout
    assert 'severity=serious (from "severe")' in finished.stdout
    assert 'severity=blocker (from "blocking")' in finished.stdout
    assert "dry run: no records were written." in finished.stdout
    assert _rows(env) == []


def test_a_dry_run_rejects_words_outside_the_form_s_vocabularies(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """A severity or type the form does not offer is refused, by name.

    **The refusal names the word and the words.** A submitter who wrote
    ``critical`` needs to see the four words the form offers; a bare
    "invalid value" sends them back to the template to guess. The dry run
    catches it before anything is written, which is the mode's reason to
    exist.
    """
    payload = _a_form(task_id)
    payload["forms"][0]["issues"] = [
        {
            "issue_id": "iss-bad",
            "what_happened": "it broke",
            "stage": "review",
            "severity": "critical",
            "type": "ui",
        }
    ]
    forms = _write_forms(tmp_path / "forms.json", payload)

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert "severity is 'critical'" in finished.stdout
    assert "blocking, severe, normal, suggestion" in finished.stdout
    assert _rows(env) == []


def test_a_dry_run_reports_every_problem_one_item_has(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """An item with several wrong fields is reported with all of them.

    **One pass, not three.** A form with no stage, no type and an unknown
    severity is three corrections; reporting only the first would send the
    operator back twice for the same item.
    """
    payload = _a_form(task_id)
    payload["forms"][0]["issues"] = [
        {
            "issue_id": "iss-bad",
            "what_happened": "it broke",
            "severity": "critical",
        }
    ]
    forms = _write_forms(tmp_path / "forms.json", payload)

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert "3 problem(s)" in finished.stdout
    assert "stage is required" in finished.stdout
    assert "type is required" in finished.stdout
    assert "severity is 'critical'" in finished.stdout


def test_a_dry_run_rejects_a_bad_frequency(tmp_path: Path, env: StoreEnv, task_id: str) -> None:
    """P-14's frequency has three words, and a fourth is named."""
    payload = _a_form(task_id)
    payload["forms"][0]["issues"][0]["frequency"] = "always"
    forms = _write_forms(tmp_path / "forms.json", payload)

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert "frequency is 'always'" in finished.stdout
    assert "once, sometimes, every time" in finished.stdout


def test_a_dry_run_rejects_negative_counts(tmp_path: Path, env: StoreEnv, task_id: str) -> None:
    """A negative duration or retry count is refused before the layer sees it.

    The application layer refuses both too; catching them here means the
    dry run's report is the **complete** truth about the file, not merely
    the truth about the words.
    """
    payload = _a_form(task_id)
    payload["forms"][0]["issues"][0]["duration_seconds"] = -1
    payload["forms"][0]["issues"][0]["retry_count"] = -2
    forms = _write_forms(tmp_path / "forms.json", payload)

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert "duration_seconds cannot be negative" in finished.stdout
    assert "retry_count cannot be negative" in finished.stdout


# --------------------------------------------------------------------------- #
# the unreadable and the malformed
# --------------------------------------------------------------------------- #


def test_a_missing_file_is_an_exit_two(tmp_path: Path) -> None:
    """A file that cannot be read is a different failure from a bad item.

    **The exit status separates the two.** A caller that scripts the ingest
    needs to know whether to fix the path (2) or fix the forms (1); one
    exit code for both would make "nothing was written" the only fact
    either way.
    """
    finished = _run(str(tmp_path / "absent.json"), "--dry-run")

    assert finished.returncode == 2
    assert "could not be read" in finished.stdout


def test_a_file_that_is_not_json_is_an_exit_two(tmp_path: Path) -> None:
    """A file that does not parse is refused with the parse error's place."""
    forms = tmp_path / "forms.json"
    forms.write_text("{not json", encoding="utf-8")

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 2
    assert "not valid JSON" in finished.stdout


def test_a_file_without_a_forms_list_is_rejected(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """A JSON object with no ``forms`` list is refused, not read as empty.

    **An empty answer is a fact; a malformed one is an error.** ``{"forms":
    []}`` means "no forms were collected"; a file that holds something else
    entirely means the wrong file was named, and reading it as empty would
    report success over a mistake.
    """
    forms = _write_forms(tmp_path / "forms.json", {"records": []})

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert '"forms" list' in finished.stdout
    assert _rows(env) == []


def test_a_form_without_items_is_rejected(tmp_path: Path, env: StoreEnv, task_id: str) -> None:
    """A form with an empty ``issues`` list is reported, not silently skipped.

    A session that reported nothing is a fact, but a form that *should*
    hold items and holds none is a form that was not finished -- and a
    silent skip would hide it from the very pass that exists to catch
    unfinished forms.
    """
    payload = _a_form(task_id)
    payload["forms"][0]["issues"] = []
    forms = _write_forms(tmp_path / "forms.json", payload)

    finished = _run(str(forms), "--dry-run")

    assert finished.returncode == 1
    assert 'non-empty "issues" list' in finished.stdout
    assert _rows(env) == []


# --------------------------------------------------------------------------- #
# the apply
# --------------------------------------------------------------------------- #


def test_an_apply_records_every_item_through_the_layer(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """Each item becomes one Issue row, with the record's own words.

    **The mapped words are what lands.** The form said ``severe`` and the
    row must say ``serious`` -- the record's vocabulary, not the form's --
    and the free-text fields are composed into the one ``error_text`` in
    the template's order. The row is read back from the store, so this is
    the record and not the tool's own report of one.
    """
    _seed_project(env)
    forms = _write_forms(tmp_path / "forms.json", _a_form(task_id))
    workspace = _make_workspace(tmp_path, task_id)

    finished = _run(str(forms), "--workspace", str(workspace), "--apply")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "2 created, 0 skipped, 0 failed" in finished.stdout
    rows = {row.issue_id: row for row in _rows(env)}
    assert set(rows) == {"iss-001", "iss-002"}
    first = rows["iss-001"]
    assert first.severity == "serious"
    assert first.category == "model"
    assert first.step == "model-suggestions"
    assert first.status == "open"
    # The submission id is not the chain's ``feedback_id`` (which names an
    # opinion comment), so it travels in the text, where the batch stays
    # traceable without inventing a link the chain does not hold.
    assert first.feedback_id is None
    assert first.error_text.startswith(
        "Form submission: form-2026-11-24-a\n"
        "suggestion list ignored the language filter: "
        "the list showed English suggestions for a Chinese draft"
    )
    second = rows["iss-002"]
    assert second.severity == "blocker"
    assert second.category == "performance"
    assert second.duration_seconds == 120.5
    assert second.retry_count == 1
    assert "Form submission: form-2026-11-24-a" in second.error_text
    assert "Workaround: split the PDF by hand" in second.error_text
    assert "Frequency: every time" in second.error_text


def test_an_apply_is_idempotent_on_the_issue_id(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """Re-ingesting the same file skips the recorded items and adds no rows.

    **A problem counted twice is a finding the trial does not have.** The
    issue id is the record's primary key; the second pass reads the store
    first, reports the row as skipped, and the count of rows is the count
    of problems -- once each.
    """
    _seed_project(env)
    forms = _write_forms(tmp_path / "forms.json", _a_form(task_id))
    workspace = _make_workspace(tmp_path, task_id)

    first = _run(str(forms), "--workspace", str(workspace), "--apply")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "2 created, 0 skipped, 0 failed" in first.stdout

    second = _run(str(forms), "--workspace", str(workspace), "--apply")
    assert second.returncode == 0, second.stdout + second.stderr
    assert "0 created, 2 skipped, 0 failed" in second.stdout
    assert len(_rows(env)) == 2


def test_an_apply_reports_a_failed_item_and_still_records_the_rest(
    tmp_path: Path, env: StoreEnv, task_id: str
) -> None:
    """One item failing does not stop the others from being recorded.

    **A stack of forms is ingested in one sitting.** Stopping at the first
    refusal would make the operator rerun the whole file to discover the
    next refusal; the honest report is per item -- created, skipped, or
    failed with the reason -- and the exit status says whether anything
    failed, so a caller's script sees it without reading the output.
    """
    _seed_project(env)
    payload = _a_form(task_id)
    # The second item names a version the store does not hold: the layer
    # refuses an issue about a version nobody ingested, and this file
    # witnesses that the refusal fails the item -- not the run.
    payload["forms"][0]["issues"][1]["related_version_id"] = "ver-absent"
    forms = _write_forms(tmp_path / "forms.json", payload)
    workspace = _make_workspace(tmp_path, task_id)

    finished = _run(str(forms), "--workspace", str(workspace), "--apply")

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "1 created, 0 skipped, 1 failed" in finished.stdout
    assert "[failed]" in finished.stdout
    assert "[created]" in finished.stdout
    rows = {row.issue_id for row in _rows(env)}
    assert rows == {"iss-001"}


def test_an_apply_names_the_layer_s_refusal(tmp_path: Path, env: StoreEnv, task_id: str) -> None:
    """A refusal comes back with the layer's own words, not a bare failure.

    **The reason is the report.** A failed item that said only "[failed]"
    would send the operator back to guess; the failure line carries the
    application layer's own sentence -- here, the project the store does
    not hold -- so the correction is named, not inferred.
    """
    payload = _a_form(task_id)
    payload["forms"][0]["project_id"] = "proj-absent"
    forms = _write_forms(tmp_path / "forms.json", payload)
    workspace = _make_workspace(tmp_path, task_id)

    finished = _run(str(forms), "--workspace", str(workspace), "--apply")

    assert finished.returncode == 1
    assert "proj-absent" in finished.stdout
    assert _rows(env) == []


# --------------------------------------------------------------------------- #
# the mapping, total by construction
# --------------------------------------------------------------------------- #


def test_the_form_s_vocabularies_map_onto_the_record_s() -> None:
    """Every form word maps to a word the record's vocabulary holds.

    **The mapping is total, and this is what keeps it total.** The two
    vocabularies live in different layers -- the form's in this tool, the
    record's in the application layer and the row's CHECK constraints --
    and a word added to one without the other would be a record nobody
    can group by. The tool asserts the mapping at import time, so a
    vocabulary change upstream fails loudly; this witness re-states the
    assertion as a test, because a claim that is stated and not watched
    is not held.
    """
    module = _script_module()

    from labcairn.application.issues import (
        PILOT_ISSUE_CATEGORIES,
        PILOT_ISSUE_SEVERITIES,
    )

    assert set(module.SEVERITY_MAP) == set(module.FORM_SEVERITIES)
    assert set(module.CATEGORY_MAP) == set(module.FORM_CATEGORIES)
    assert set(module.SEVERITY_MAP.values()) <= set(PILOT_ISSUE_SEVERITIES)
    assert set(module.CATEGORY_MAP.values()) <= set(PILOT_ISSUE_CATEGORIES)
