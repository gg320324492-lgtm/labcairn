"""Ingest completed pilot feedback forms into the issue record.

Phase 4's trial (P4-PILOT, execution plan §9.4) collects each problem on
the unified feedback form -- the template at
``docs/plans/LC-P4-PILOT-feedback-form-template.md`` -- and records it a
second time **in the system**, as an Issue row. This tool walks the
completed forms and writes that second record, so a stack of paper forms
does not have to be re-typed by hand against the API.

The input is one JSON file holding one or more completed forms. A form is
the template's Part 1 (submitter context) plus a list of Part 2 problem
items; each item becomes exactly one Issue record, which is the
template's own mapping rule. The format::

    {
      "forms": [
        {
          "project_id": "proj-...",
          "task_id": "task-...",
          "submission_id": "form-2026-11-24-a",
          "submitter_role": "advisor",
          "session_date": "2026-11-24",
          "stages_used": ["import", "review"],
          "issues": [
            {
              "issue_id": "iss-001",
              "what_happened": "…",          (required; P-2)
              "steps_to_reproduce": "…",     (optional; P-3)
              "expected": "…",               (optional; P-4)
              "stage": "model-suggestions",  (required; P-5)
              "severity": "severe",          (required; P-6, form vocabulary)
              "type": "function",            (required; P-7, form vocabulary)
              "related_version_id": "ver-…", (optional; P-10)
              "related_opinions": "…",       (optional free text; P-8)
              "related_deliverables": "…",   (optional free text; P-9)
              "evidence": "…",               (optional free text; P-11)
              "workaround": "…",             (optional; P-13)
              "frequency": "sometimes",      (optional; P-14)
              "duration_seconds": 12.5,      (optional; system trace)
              "retry_count": 0               (optional; system trace)
            }
          ]
        }
      ]
    }

Two vocabularies are closed, and the form's words are not the record's
words. The template asks the submitter for severity ``blocking | severe |
normal | suggestion`` and type ``function | ui | performance | model |
documentation``; the Issue record's closed vocabularies (G0 §6, enforced
by :func:`labcairn.application.issues.record_issue`) are severity
``blocker | serious | minor | suggestion`` and type ``function |
interface | performance | model | documentation``. The mapping is the
template's own correspondence, applied here once so a form can be read
without the reader re-deriving it. A word outside the form's vocabulary
is an error in that item, reported by name.

Two subcommands:

    python scripts/pilot_feedback_ingest.py forms.json --dry-run
    python scripts/pilot_feedback_ingest.py forms.json --workspace . --apply

``--dry-run`` (the default) parses the file, validates every item, and
prints the Issue records that *would* be created. Nothing is written.
Every bad item is reported, not just the first, so a stack of forms can
be corrected in one pass. ``--apply`` records the items through the
application layer -- the same :func:`record_issue` the API's
``POST /issues`` calls -- reporting each item as created, skipped (its
issue id is already recorded; ingesting the same file twice does not
duplicate rows), or failed with the reason. The tool never edits the
store directly: every write goes through the application layer, and the
workspace it runs against is the operator's own.

Exit status: 0 when every item was created or skipped (or, on a dry run,
when nothing failed validation); 1 when at least one item failed; 2 when
the input could not be read or parsed at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labcairn.application.context import ApplicationContext
from labcairn.application.issues import (
    PILOT_ISSUE_CATEGORIES,
    PILOT_ISSUE_SEVERITIES,
    record_issue,
)
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.cli.workspace import (
    WorkspaceSetupError,
    application_context,
    locate,
    read_config,
)
from labcairn.core.ids import TaskId
from labcairn.db.models import PilotIssueRow

#: The form's severity vocabulary (template P-6), in display order.
FORM_SEVERITIES: tuple[str, ...] = ("blocking", "severe", "normal", "suggestion")

#: The form's type vocabulary (template P-7), in display order.
FORM_CATEGORIES: tuple[str, ...] = (
    "function",
    "ui",
    "performance",
    "model",
    "documentation",
)

#: Form severity -> Issue severity. The template's scale and the record's
#: scale are the same four answers under two names; the mapping is the
#: correspondence the template's §9.4 note asserts. Asserted against the
#: record's vocabulary at import time, so a vocabulary change upstream
#: breaks this module loudly instead of writing a tag nobody can group by.
SEVERITY_MAP: dict[str, str] = {
    "blocking": "blocker",
    "severe": "serious",
    "normal": "minor",
    "suggestion": "suggestion",
}

#: Form type -> Issue type. ``ui`` is the one rename; the rest carry over.
CATEGORY_MAP: dict[str, str] = {
    "function": "function",
    "ui": "interface",
    "performance": "performance",
    "model": "model",
    "documentation": "documentation",
}

#: The Part 1 stage list, which Part 2's P-5 draws from.
STAGES: tuple[str, ...] = (
    "import",
    "parse",
    "model-suggestions",
    "review",
    "preview",
    "apply",
    "publish",
    "deliverables",
    "export",
)

#: The Part 1 submitter roles, and the reporter handle each becomes.
SUBMITTER_ROLES: dict[str, str] = {"advisor": "advisor", "student": "student"}

#: The Part 2 frequency choices (P-14), when the item names one.
FREQUENCIES: tuple[str, ...] = ("once", "sometimes", "every time")

for _form_word, _record_word in SEVERITY_MAP.items():
    assert _form_word in FORM_SEVERITIES, _form_word
    assert _record_word in PILOT_ISSUE_SEVERITIES, _record_word
for _form_word, _record_word in CATEGORY_MAP.items():
    assert _form_word in FORM_CATEGORIES, _form_word
    assert _record_word in PILOT_ISSUE_CATEGORIES, _record_word


@dataclass(frozen=True)
class PlannedIssue:
    """One Part 2 item, mapped onto the record's own words.

    Carried between parsing and writing so that the dry run and the apply
    read from **one** translation: a dry run that computed something
    slightly different from what ``--apply`` would write would be a
    preview of a record that is never made.
    """

    form_index: int
    item_index: int
    issue_id: str
    project_id: str
    task_id: str
    version_id: str | None
    step: str
    error_text: str
    duration_seconds: float | None
    retry_count: int | None
    severity: str
    form_severity: str
    category: str
    form_type: str
    reported_by: str


@dataclass(frozen=True)
class ItemError:
    """Every problem one item has, named so the submitter can fix the form.

    An item that fails validation fails **with all of its reasons**, not
    the first one: a form with three wrong fields corrected one at a time
    is three round trips the pilot does not have.
    """

    form_index: int
    item_index: int
    issue_id: str
    problems: tuple[str, ...]


def _require_text(container: dict[str, Any], key: str, problems: list[str]) -> str:
    """A non-empty string field, or a named problem and an empty string."""
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{key} is required (a non-empty string).")
        return ""
    return value.strip()


def _optional_text(container: dict[str, Any], key: str) -> str | None:
    """An optional string field; absent, null or blank all mean 'not given'."""
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _vocabulary_field(
    container: dict[str, Any],
    key: str,
    vocabulary: Sequence[str],
    problems: list[str],
) -> str:
    """A field whose value must be one of a closed vocabulary, by name.

    The refusal names the word the form used and the words it could have
    used: a submitter who wrote ``critical`` needs to see the four words
    the form offers, not a bare "invalid value".
    """
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{key} is required (one of: {', '.join(vocabulary)}).")
        return ""
    word = value.strip()
    if word not in vocabulary:
        problems.append(f"{key} is {word!r}, which is not one of: {', '.join(vocabulary)}.")
        return ""
    return word


def _optional_float(
    container: dict[str, Any],
    key: str,
    problems: list[str],
) -> float | None:
    """An optional non-negative number of seconds; a negative one is named.

    A duration is measured from the step's start; the application layer
    refuses a negative one, and the dry run names the same refusal before
    anything is written.
    """
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{key} must be a number, not {value!r}.")
        return None
    if value < 0:
        problems.append(f"{key} cannot be negative, not {value!r}.")
        return None
    return float(value)


def _optional_int(container: dict[str, Any], key: str, problems: list[str]) -> int | None:
    """An optional non-negative whole number; anything else is named.

    A retry count counts attempts: a fraction of an attempt is not a thing
    the record can hold, and a negative one is refused by the application
    layer, so both are named here, before anything is written.
    """
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(f"{key} must be a whole number, not {value!r}.")
        return None
    if value < 0:
        problems.append(f"{key} cannot be negative, not {value!r}.")
        return None
    return int(value)


def _compose_error_text(item: dict[str, Any], what_happened: str, submission_id: str | None) -> str:
    """The item's free-text fields, as the one ``error_text`` the record holds.

    The record has one field for what the user saw, and the form spreads
    its account over several (P-2 what happened, P-3 steps, P-4
    expectations, P-8/P-9 pointers, P-11 evidence, P-13 workaround, P-14
    frequency). The account is composed here, in the template's own order,
    so the record reads as the form did instead of losing every field but
    the first.

    The form's ``submission_id`` opens the text. The record's
    ``feedback_id`` names an opinion comment the chain holds, which a
    submission id is not, so the batch's traceability -- the template's
    "the form's own submission id is stored on each Issue" -- is kept in
    the text, where the record can carry it without inventing a link the
    chain does not hold.
    """
    sections: list[str] = []
    if submission_id:
        sections.append(f"Form submission: {submission_id}")
    title = _optional_text(item, "title")
    sections.append(f"{title}: {what_happened}" if title else what_happened)
    for key, label in (
        ("steps_to_reproduce", "Steps to reproduce"),
        ("expected", "What was expected"),
        ("related_opinions", "Related opinions"),
        ("related_deliverables", "Related deliverables"),
        ("evidence", "Evidence"),
        ("workaround", "Workaround"),
    ):
        text = _optional_text(item, key)
        if text:
            sections.append(f"{label}: {text}")
    frequency = _vocabulary_of(item, "frequency", FREQUENCIES)
    if frequency:
        sections.append(f"Frequency: {frequency}")
    return "\n".join(sections)


def _vocabulary_of(container: dict[str, Any], key: str, vocabulary: Sequence[str]) -> str:
    """An optional closed-vocabulary word, or the empty string.

    The composing pass does not report: a frequency outside the three
    choices has already been reported by the validating pass, and the
    composing pass runs only for items that passed it.
    """
    value = container.get(key)
    if isinstance(value, str) and value.strip() in vocabulary:
        return value.strip()
    return ""


def _parse_item(
    form: dict[str, Any],
    form_index: int,
    item: Any,
    item_index: int,
    submission_id: str | None,
) -> tuple[PlannedIssue | None, ItemError | None]:
    """One Part 2 item, validated and mapped, or every reason it fails.

    Returns exactly one of ``(issue, None)`` or ``(None, error)``: an item
    that parsed is planned, and an item that did not carries **all** of
    its problems, so the operator fixes the form in one pass.
    """
    problems: list[str] = []
    if not isinstance(item, dict):
        return None, ItemError(
            form_index, item_index, f"<item {item_index}>", ("an item must be an object.",)
        )
    label = _optional_text(item, "issue_id") or f"<item {item_index}>"

    issue_id = _require_text(item, "issue_id", problems)
    what_happened = _require_text(item, "what_happened", problems)
    stage = _vocabulary_field(item, "stage", STAGES, problems)
    form_severity = _vocabulary_field(item, "severity", FORM_SEVERITIES, problems)
    form_type = _vocabulary_field(item, "type", FORM_CATEGORIES, problems)
    duration = _optional_float(item, "duration_seconds", problems)
    retry_count = _optional_int(item, "retry_count", problems)

    frequency = _optional_text(item, "frequency")
    if frequency is not None and frequency not in FREQUENCIES:
        problems.append(
            f"frequency is {frequency!r}, which is not one of: {', '.join(FREQUENCIES)}."
        )

    project_id = _require_text(form, "project_id", problems)
    task_id = _require_text(form, "task_id", problems)

    role = _vocabulary_field(form, "submitter_role", tuple(SUBMITTER_ROLES), problems)
    reported_by = _optional_text(item, "reported_by") or SUBMITTER_ROLES.get(role, "")

    if problems:
        return None, ItemError(form_index, item_index, label, tuple(problems))

    severity = SEVERITY_MAP[form_severity]
    category = CATEGORY_MAP[form_type]
    return PlannedIssue(
        form_index=form_index,
        item_index=item_index,
        issue_id=issue_id,
        project_id=project_id,
        task_id=task_id,
        version_id=_optional_text(item, "related_version_id"),
        step=stage,
        error_text=_compose_error_text(item, what_happened, submission_id),
        duration_seconds=duration,
        retry_count=retry_count,
        severity=severity,
        form_severity=form_severity,
        category=category,
        form_type=form_type,
        reported_by=reported_by,
    ), None


def parse_forms(data: Any) -> tuple[list[PlannedIssue], list[ItemError]]:
    """Every form's items, mapped and validated.

    The file holds ``{"forms": [...]}``; each form is the template's
    Part 1 context plus a list of Part 2 items. A form with no items is a
    mistake the pilot would want to know about -- a session that reported
    nothing is a fact, but a form that *should* hold items and holds none
    is a form that was not finished -- so it is reported rather than
    silently contributing nothing.
    """
    planned: list[PlannedIssue] = []
    errors: list[ItemError] = []
    if not isinstance(data, dict) or not isinstance(data.get("forms"), list):
        return planned, [
            ItemError(0, 0, "<file>", ('the file must hold a JSON object with a "forms" list.',))
        ]
    for form_index, form in enumerate(data["forms"], start=1):
        if not isinstance(form, dict):
            errors.append(ItemError(form_index, 0, "<form>", ("each form must be a JSON object.",)))
            continue
        items = form.get("issues")
        if not isinstance(items, list) or not items:
            label = _optional_text(form, "project_id") or f"<form {form_index}>"
            errors.append(
                ItemError(
                    form_index,
                    0,
                    label,
                    ('each form must carry a non-empty "issues" list.',),
                )
            )
            continue
        submission_id = _optional_text(form, "submission_id")
        for item_index, item in enumerate(items, start=1):
            issue, error = _parse_item(form, form_index, item, item_index, submission_id)
            if issue is not None:
                planned.append(issue)
            else:
                assert error is not None
                errors.append(error)
    return planned, errors


def _report_errors(errors: Sequence[ItemError]) -> None:
    """Every bad item, with every reason, so one pass fixes the stack."""
    for error in errors:
        print(
            f"form {error.form_index}, item {error.item_index} "
            f"({error.issue_id}): {len(error.problems)} problem(s)"
        )
        for problem in error.problems:
            print(f"  - {problem}")


def _describe(issue: PlannedIssue) -> str:
    """One planned record, as the operator reads it back."""
    parts = [
        f"issue_id={issue.issue_id}",
        f"project={issue.project_id}",
        f"task={issue.task_id}",
        f"step={issue.step}",
        f'severity={issue.severity} (from "{issue.form_severity}")',
        f'type={issue.category} (from "{issue.form_type}")',
        f"reported_by={issue.reported_by}",
    ]
    if issue.version_id:
        parts.append(f"version={issue.version_id}")
    return "  ".join(parts)


def cmd_dry_run(planned: Sequence[PlannedIssue], errors: Sequence[ItemError]) -> int:
    """Report what would be recorded, and write nothing.

    **A dry run that found errors says so in its exit status.** A report
    the caller has to read to notice was a failure would be indistinguishable
    from a green one in a script's output, so a validation failure is
    exit 1 and the records that would have been written are still listed,
    so the operator sees how much of the stack is clean.
    """
    print(f"{len(planned)} issue(s) would be created, {len(errors)} item(s) rejected:")
    for issue in planned:
        print(f"  would record: {_describe(issue)}")
    if errors:
        print()
        _report_errors(errors)
    print()
    print("dry run: no records were written.")
    return 1 if errors else 0


def cmd_apply(planned: Sequence[PlannedIssue], errors: Sequence[ItemError], root: Path) -> int:
    """Record the valid items through the application layer, item by item.

    **One item failing does not stop the others.** A stack of forms is
    ingested in one sitting, and stopping at the first refusal would make
    the operator rerun the whole file to discover the next refusal. Each
    item is reported as created, skipped, or failed, and the exit status
    says whether anything failed.

    **An item already recorded is skipped, not rewritten.** The issue id
    is the record's primary key, so re-ingesting a file is idempotent by
    the record's own identity, and a duplicate row -- a problem counted
    twice in the trial's findings -- cannot happen.
    """
    if errors:
        print("the file has items that failed validation; they are not applied:")
        _report_errors(errors)
        print()

    by_task: dict[str, list[PlannedIssue]] = {}
    for issue in planned:
        by_task.setdefault(issue.task_id, []).append(issue)

    created = 0
    skipped = 0
    failed = len(errors)
    for task_id, issues in by_task.items():
        location = locate(root)
        try:
            config = read_config(location)
        except WorkspaceSetupError as error:
            print(f"the workspace at {root} could not be read: {error}")
            return 2
        try:
            with application_context(location, config, _task_id(task_id)) as context:
                for issue in issues:
                    outcome, detail = _record_one(context, issue)
                    if outcome == "created":
                        created += 1
                    elif outcome == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                    print(f"  [{outcome}] {_describe(issue)}{detail}")
        except WorkspaceSetupError as error:
            # The workspace could not be bound for this task at all; every
            # item in the group failed for that one reason.
            for issue in issues:
                failed += 1
                print(f"  [failed] {_describe(issue)}  ({error})")

    print()
    print(f"summary: {created} created, {skipped} skipped, {failed} failed.")
    return 1 if failed else 0


def _task_id(raw: str) -> TaskId:
    """The form's task id, as the record's own id type.

    A task id is a UUIDv7; the API parses one the same way, and the parse
    is here rather than at the call site so the dry run and the apply can
    both name a malformed id as what it is -- the form's task id -- before
    the workspace is bound at all.
    """
    import uuid

    try:
        parsed = uuid.UUID(raw)
    except ValueError as error:
        raise WorkspaceSetupError(
            f"the form's task id {raw!r} is not a UUIDv7, which is what a task id is."
        ) from error
    if parsed.version != 7:
        raise WorkspaceSetupError(
            f"the form's task id {raw!r} is a UUID version {parsed.version}, "
            "and a task id is a UUIDv7."
        )
    return TaskId(parsed)


def _record_one(context: ApplicationContext, issue: PlannedIssue) -> tuple[str, str]:
    """One item, recorded through the layer. Returns (outcome, detail).

    The write goes through :func:`record_issue` -- the same door the API
    uses -- so the closed vocabularies, the project and version checks and
    the empty-field refusals are the layer's own, applied once. A duplicate
    issue id is read from the store before the write: the record's primary
    key makes re-ingestion idempotent, and "skipped" is the honest report
    for a row that is already there.
    """
    existing = context.store.session.get(PilotIssueRow, issue.issue_id)
    if existing is not None:
        return "skipped", ""
    try:
        record_issue(
            context,
            issue_id=issue.issue_id,
            project_id=issue.project_id,
            task_id=issue.task_id,
            version_id=issue.version_id,
            step=issue.step,
            error_text=issue.error_text,
            duration_seconds=issue.duration_seconds,
            retry_count=issue.retry_count,
            severity=issue.severity,
            category=issue.category,
            reported_by=issue.reported_by,
        )
    except ApplicationRefusedError as error:
        return "failed", f"  ({error})"
    return "created", ""


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the arguments, read the forms, and run the chosen mode."""
    parser = argparse.ArgumentParser(
        description=(
            "Ingest completed pilot feedback forms (JSON) into the system's "
            "issue record. Dry-run by default; pass --apply to write."
        )
    )
    parser.add_argument("forms", type=Path, help="path to the completed forms JSON file")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(),
        help="the LabCairn workspace root (default: the current directory)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="validate and report without writing (the default)",
    )
    mode.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="record the issues through the application layer",
    )
    parser.set_defaults(apply=False)
    args = parser.parse_args(argv)

    try:
        raw = args.forms.read_text(encoding="utf-8")
    except OSError as error:
        print(f"the forms file {args.forms} could not be read: {error}")
        return 2
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"the forms file {args.forms} is not valid JSON: {error}")
        return 2

    planned, errors = parse_forms(data)
    if args.apply:
        return cmd_apply(planned, errors, args.workspace)
    return cmd_dry_run(planned, errors)


if __name__ == "__main__":
    sys.exit(main())
