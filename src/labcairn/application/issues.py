"""The pilot's in-system issue record: record, list, and move along.

**What this module is.** Phase 4's real trial (P4-PILOT, execution plan
§9.4) records each problem twice: in the unified feedback form -- the
subjective experience, the description, the improvement suggestion -- and
**in the system**, as a row that names what the problem happened to and
what the user saw. This module is the seam for that system-side record:
the form references an issue id, and the issue row is what a reader of the
form resolves it against.

Three operations, each as small as the record allows:

* :func:`record_issue` -- write one problem, under the two closed
  vocabularies §9.4 spells: severity (``blocker``, ``serious``,
  ``minor``, ``suggestion``) and type (``function``, ``interface``,
  ``performance``, ``model``, ``documentation``). **A tag outside either
  is a tag nobody can group the trial's findings by**, so the check is the
  layer's and not the wire's -- the pilot's feedback-ingest tool records
  past the wire, and it has no request-body validation to lean on.
* :func:`list_issues` -- the project's issues, filtered by what the trial
  team asks for (status, severity). **A filter is a read, not a write**,
  and the listing narrows rather than refuses: an empty answer is a fact
  about the trial, not an error.
* :func:`update_issue_status` -- move the row along the four states:
  ``open`` -> ``confirmed`` -> ``fixed``/``wontfix``. **The states are
  walked, not set.** A caller that set a status outright could record a
  confirmation nobody made, or mark a problem fixed before anyone
  confirmed it was real; the trial's own record of *what happened* is the
  sequence, so the sequence is what the layer enforces. A ``fixed`` row
  names the version that fixed it -- a fix without a version is a claim
  the next regression cannot check.

**The permission posture is the chain's.** An issue belongs to a paper
project and names no path of its own, so the permission that governs what
a writer may record is the permission on the material, asked where the
material is named -- the same posture the review workbench reads under
(ADR-0003 C5). This module asks the project's presence the way
:mod:`labcairn.application.review` does, through the chain's own
refusals, so every surface catches one kind of "no".
"""

from __future__ import annotations

from datetime import UTC, datetime

from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import PaperVersionRow, PilotIssueRow
from labcairn.papers.chain import ChainRefusal, feedback_row, project_row

__all__ = [
    "PILOT_ISSUE_CATEGORIES",
    "PILOT_ISSUE_SEVERITIES",
    "PILOT_ISSUE_STATUSES",
    "PILOT_ISSUE_STATUS_FIXED",
    "PILOT_ISSUE_STATUS_OPEN",
    "IssueData",
    "IssueStatusUpdate",
    "list_issues",
    "record_issue",
    "update_issue_status",
]


#: Severity's closed vocabulary: §9.4's four grades, from the one that
#: stops a wider trial to the one that is a suggestion.
PILOT_ISSUE_SEVERITIES: tuple[str, ...] = ("blocker", "serious", "minor", "suggestion")

#: Type's closed vocabulary: §9.4's five kinds, from what the product does
#: to what the trial writes down about it.
PILOT_ISSUE_CATEGORIES: tuple[str, ...] = (
    "function",
    "interface",
    "performance",
    "model",
    "documentation",
)

#: Status's closed vocabulary, in the order the states are walked.
PILOT_ISSUE_STATUSES: tuple[str, ...] = ("open", "confirmed", "fixed", "wontfix")

PILOT_ISSUE_STATUS_OPEN = "open"
PILOT_ISSUE_STATUS_CONFIRMED = "confirmed"
PILOT_ISSUE_STATUS_FIXED = "fixed"
PILOT_ISSUE_STATUS_WONTFIX = "wontfix"

#: The states each state may move to. ``open`` is confirmed; a confirmed
#: issue is closed one of two ways -- fixed, or not worth fixing. A closed
#: state moves nowhere: reopening a fixed issue is a second record, not an
#: edit of the first.
_ISSUE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    PILOT_ISSUE_STATUS_OPEN: (PILOT_ISSUE_STATUS_CONFIRMED,),
    PILOT_ISSUE_STATUS_CONFIRMED: (PILOT_ISSUE_STATUS_FIXED, PILOT_ISSUE_STATUS_WONTFIX),
    PILOT_ISSUE_STATUS_FIXED: (),
    PILOT_ISSUE_STATUS_WONTFIX: (),
}


class IssueData(Result):
    """One recorded issue, as the surfaces read it.

    The timestamps and the identity are strings because the wire carries
    strings; the layer's own vocabulary for a moment is the ISO-8601 UTC
    spelling every other result here uses.
    """

    issue_id: str
    project_id: str
    task_id: str | None
    version_id: str | None
    feedback_id: str | None
    step: str
    error_text: str
    duration_seconds: float | None
    retry_count: int | None
    severity: str
    category: str
    reported_by: str
    reported_at: str
    status: str
    fix_version: str | None
    regression_note: str | None


class IssueStatusUpdate(Result):
    """The result of moving an issue's status along.

    **The row's new state, whole.** A surface that drew the issue would
    draw the issue, not a bare ``ok``; and the updated row is what the
    caller's next read sees, so the operation returns it rather than
    making the caller read twice.
    """

    issue: IssueData


def _require_project(context: ApplicationContext, project_id: str) -> None:
    if project_row(context.store.session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )


def _require_version(context: ApplicationContext, project_id: str, version_id: str) -> None:
    row = context.store.session.get(PaperVersionRow, version_id)
    if row is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}.",
        )
    if row.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{row.project_id!r}, not to {project_id!r}.",
        )


def _check_vocabulary(
    *,
    severity: str,
    category: str,
) -> None:
    """The two closed vocabularies, checked by name rather than by a
    constraint error out of the middle of the transaction.

    **A tag outside either is refused where the mistake is made.** The
    CHECK constraints are the store's backstop -- a caller that reached
    past this layer would still be refused -- but the record the trial
    reads is written through here, and here is where the vocabulary's
    words are named in the refusal.
    """
    if severity not in PILOT_ISSUE_SEVERITIES:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_SEVERITY_UNKNOWN,
            f"{severity!r} is not one of the four severities "
            f"({', '.join(PILOT_ISSUE_SEVERITIES)}).",
        )
    if category not in PILOT_ISSUE_CATEGORIES:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_CATEGORY_UNKNOWN,
            f"{category!r} is not one of the five issue types "
            f"({', '.join(PILOT_ISSUE_CATEGORIES)}).",
        )


def _issue_data(row: PilotIssueRow) -> IssueData:
    """The row, in the result's own shape. One spelling, so every read
    agrees."""
    return IssueData(
        issue_id=row.issue_id,
        project_id=row.project_id,
        task_id=row.task_id,
        version_id=row.version_id,
        feedback_id=row.feedback_id,
        step=row.step,
        error_text=row.error_text,
        duration_seconds=row.duration_seconds,
        retry_count=row.retry_count,
        severity=row.severity,
        category=row.category,
        reported_by=row.reported_by,
        reported_at=row.reported_at.isoformat(),
        status=row.status,
        fix_version=row.fix_version,
        regression_note=row.regression_note,
    )


def record_issue(
    context: ApplicationContext,
    *,
    issue_id: str,
    project_id: str,
    task_id: str | None = None,
    version_id: str | None = None,
    feedback_id: str | None = None,
    step: str,
    error_text: str,
    duration_seconds: float | None = None,
    retry_count: int | None = None,
    severity: str,
    category: str,
    reported_by: str,
    reported_at: datetime | None = None,
) -> IssueData:
    """Record one problem the trial met, in the system's own record.

    **The record is about something.** A project is required; a version,
    an opinion and a task are named when the trial can name them, and a
    version or an opinion that *is* named must be one the store holds --
    an issue about a version nobody ingested is a report about nothing,
    and the record refuses it rather than carrying a dangling name.

    **The vocabularies are closed at the write.** §9.4's severity and
    type are the two tags the trial groups its findings by, and a word
    outside either is refused here, by name, before the store is asked.
    The wire refuses the same words first with a 422, for a caller that
    sent them as a request body; this refusal is for the caller that
    reached past the wire -- the pilot's feedback-ingest tool -- and it
    is the same rule, applied where the mistake is made.

    :raises ApplicationRefusedError: the project does not exist, the named
        version or opinion does not exist or belongs to another project,
        a severity or type is outside its closed vocabulary, the step or
        the reporter's handle is empty, or a retry count is negative.
    """
    if not step.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "an issue names the operation step it happened at; the step was empty.",
        )
    if not error_text.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "an issue carries what the user saw; the error text was empty.",
        )
    if not reported_by.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "an issue names who saw it; the reporter's handle was empty.",
        )
    if retry_count is not None and retry_count < 0:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"a retry count counts attempts and cannot be negative, not {retry_count}.",
        )
    if duration_seconds is not None and duration_seconds < 0:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a duration is measured from the step's start and cannot be negative, "
            f"not {duration_seconds}.",
        )

    _require_project(context, project_id)
    if version_id is not None:
        _require_version(context, project_id, version_id)
    if feedback_id is not None and feedback_row(context.store.session, feedback_id) is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the chain holds no comment with the id {feedback_id!r}. An issue "
            "names the opinion it concerns, and an issue about an opinion "
            "nobody holds is a report about nothing.",
        )
    _check_vocabulary(severity=severity, category=category)

    now = datetime.now(UTC)
    row = PilotIssueRow(
        issue_id=issue_id,
        project_id=project_id,
        task_id=task_id,
        version_id=version_id,
        feedback_id=feedback_id,
        step=step,
        error_text=error_text,
        duration_seconds=duration_seconds,
        retry_count=retry_count,
        severity=severity,
        category=category,
        reported_by=reported_by,
        reported_at=reported_at if reported_at is not None else now,
        status=PILOT_ISSUE_STATUS_OPEN,
        fix_version=None,
        regression_note=None,
    )
    context.store.session.add(row)
    context.store.session.commit()
    return _issue_data(row)


def list_issues(
    context: ApplicationContext,
    *,
    project_id: str,
    status: str | None = None,
    severity: str | None = None,
) -> tuple[IssueData, ...]:
    """The project's issues, newest first, narrowed by what is asked for.

    **A filter narrows; it does not refuse.** An empty answer is a fact
    about the trial -- "no blocker has been recorded" -- and not an error.
    A status or severity outside the closed vocabulary is a different
    thing: it is a question the record cannot understand, and it is
    refused by name rather than answered with an empty list that would
    read as "none recorded".

    :raises ApplicationRefusedError: the project does not exist, or a
        filter names a word outside its closed vocabulary.
    """
    _require_project(context, project_id)
    if status is not None and status not in PILOT_ISSUE_STATUSES:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_STATUS_MOVE_REFUSED,
            f"{status!r} is not one of the four statuses "
            f"({', '.join(PILOT_ISSUE_STATUSES)}); a filter names a state the "
            "record can hold, or no filter at all.",
        )
    if severity is not None and severity not in PILOT_ISSUE_SEVERITIES:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_SEVERITY_UNKNOWN,
            f"{severity!r} is not one of the four severities "
            f"({', '.join(PILOT_ISSUE_SEVERITIES)}); a filter names a severity "
            "the record can hold, or no filter at all.",
        )

    query = context.store.session.query(PilotIssueRow).filter(
        PilotIssueRow.project_id == project_id
    )
    if status is not None:
        query = query.filter(PilotIssueRow.status == status)
    if severity is not None:
        query = query.filter(PilotIssueRow.severity == severity)
    rows = query.order_by(PilotIssueRow.reported_at.desc(), PilotIssueRow.issue_id).all()
    return tuple(_issue_data(row) for row in rows)


def update_issue_status(
    context: ApplicationContext,
    *,
    project_id: str,
    issue_id: str,
    status: str,
    fix_version: str | None = None,
    regression_note: str | None = None,
) -> IssueStatusUpdate:
    """Move an issue along the four states, refusing a move that skips one.

    **The states are walked, not set.** ``open`` becomes ``confirmed``
    (a second person has seen the problem); ``confirmed`` becomes
    ``fixed`` or ``wontfix`` (the team's word on it). A closed issue moves
    nowhere -- reopening it is a new record about the same problem, and
    editing the first record's history would make the trial's record say
    something nobody said.

    **A fixed issue names the version that fixed it.** The fix version is
    what the trial's regression check reads when it re-opens the
    manuscript; a ``fixed`` row without one is a claim the next round
    cannot verify, so the move is refused. A ``regression_note`` travels
    with the fix: what to watch, in the words the team agreed on.

    :raises ApplicationRefusedError: the project or the issue does not
        exist, the issue belongs to another project, the target status is
        not one of the four, the move skips a state or closes a closed
        issue, or a ``fixed`` move names no fix version.
    """
    _require_project(context, project_id)
    row = context.store.session.get(PilotIssueRow, issue_id)
    if row is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_NOT_FOUND,
            f"the store holds no pilot issue with the id {issue_id!r}.",
        )
    if row.project_id != project_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_NOT_FOUND,
            f"the pilot issue {issue_id!r} belongs to the project "
            f"{row.project_id!r}, not to {project_id!r}.",
        )
    if status not in PILOT_ISSUE_STATUSES:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_STATUS_MOVE_REFUSED,
            f"{status!r} is not one of the four statuses ({', '.join(PILOT_ISSUE_STATUSES)}).",
        )
    allowed = _ISSUE_TRANSITIONS[row.status]
    if status not in allowed:
        raise ApplicationRefusedError(
            ApplicationRefusal.PILOT_ISSUE_STATUS_MOVE_REFUSED,
            f"an issue in state {row.status!r} moves to one of "
            f"({', '.join(allowed) if allowed else 'nothing -- the state is closed'}), "
            f"not to {status!r}. The states are walked, not set.",
        )
    if status == PILOT_ISSUE_STATUS_FIXED and not (fix_version and fix_version.strip()):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a fixed issue names the version that fixed it; the fix version was empty. "
            "A fix without a version is a claim the next regression cannot check.",
        )

    row.status = status
    if status == PILOT_ISSUE_STATUS_FIXED:
        row.fix_version = fix_version
        row.regression_note = regression_note
    elif status == PILOT_ISSUE_STATUS_WONTFIX:
        # A wontfix carries its reason: what the team decided, and why the
        # problem is being left as it is.
        row.regression_note = regression_note
    context.store.session.commit()
    return IssueStatusUpdate(issue=_issue_data(row))
