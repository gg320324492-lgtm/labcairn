"""One refusal type, one reason vocabulary, one rendering for every surface.

A layer that raises a different exception per operation cannot be rendered by a
surface that does not know which operation produced it. The CLI's ``task run``
and the API's ``POST /stages`` have no way to learn that "no such task" and "no
such approval" are raised by different code paths, and a surface that has to
catch four exception types to draw one error is a surface that will eventually
miss one.

So there is exactly one refusal type here, and it carries the two things a
surface needs and cannot work out for itself:

* **a machine-readable reason**, so a caller can branch without reading a
  message — ``permission_denied`` and ``approval_missing`` are different
  situations with different remedies, and a UI that draws them the same way
  has thrown away information it was given;
* **a message that names what was wrong**, so a person reading it does not have
  to guess. The reason says which class of failure this is; the detail says
  which one.

The vocabulary is deliberately the run path's. :mod:`labcairn.analysis.service`
already settled on one type, one reason enum and one message shape for the same
problem one level down, and a second vocabulary for the same idea is a second
thing for a reader to learn.

:meth:`ApplicationRefusedError.to_payload` is the rendering. A CLI's ``--json``
and an API's error body are the same two fields, so the two surfaces cannot
disagree about what a refusal said — which is the same property the plan's
acceptance clause asks of the task state.
"""

from __future__ import annotations

from enum import StrEnum


class ApplicationRefusal(StrEnum):
    """Why the application layer said no.

    Enumerated so a caller can branch on the reason without reading a message,
    and so that "the operation was refused" and "the operation was refused *for
    that reason*" are two different facts.
    """

    #: The capability's arguments are not usable, or name something other than
    #: the resource the operation addresses.
    ARGUMENTS_INVALID = "arguments_invalid"
    #: The path could not be admitted, or does not name a bound root.
    PATH_REFUSED = "path_refused"
    #: The policy denied the request.
    PERMISSION_DENIED = "permission_denied"
    #: The policy asked about the request and the operation had no approval to
    #: present. Not a denial: the remedy is an approval, not an exemption.
    POLICY_ASKED = "policy_asked"
    #: No such approval, or it was never issued.
    APPROVAL_MISSING = "approval_missing"
    #: The approval does not cover this request.
    APPROVAL_REFUSED = "approval_refused"
    #: The store holds no task with that id.
    TASK_NOT_FOUND = "task_not_found"
    #: The ledger holds no source with that id.
    SOURCE_NOT_FOUND = "source_not_found"
    #: The store holds no artefact with that id.
    ARTIFACT_NOT_FOUND = "artifact_not_found"
    #: The store holds no operation with that id.
    OPERATION_NOT_FOUND = "operation_not_found"
    #: The stage's work failed. The original failure is kept as the cause.
    STAGE_FAILED = "stage_failed"
    #: The operation would read more than the capability's own bound allows.
    LIMITS_EXCEEDED = "limits_exceeded"
    #: The report's content was refused: the material it names does not
    #: support it, and nothing was written.
    #:
    #: Its own member, and not ``STAGE_FAILED``, because the two are
    #: different situations and a caller that cannot tell them apart cannot
    #: tell what to do. **A stage that failed ran and failed**: there is an
    #: execution to look at, and the work may be worth retrying. **A report
    #: whose content was refused never ran**: the checks read the ledger and
    #: the material, found that the document says something they do not
    #: support, and stopped — so there is nothing to retry and the ledger is
    #: what has to change.
    #:
    #: The message names what refused and why — the check that refused, and
    #: the reason it gave — because a reason nobody can act on is the same as
    #: no reason.
    REPORT_CONTENT_REFUSED = "report_content_refused"
    #: The operation is declared but not implemented yet.
    NOT_IMPLEMENTED = "not_implemented"
    #: A crash left an operation in flight, its outcome is unknown, and the stage
    #: is blocked until a probe answers it. **The remedy is a reconciliation, not
    #: a retry**: replaying would plan a second operation for work that may already
    #: have happened, which is the failure ADR-0003 A2 refuses to assume away.
    OPERATION_UNCERTAIN = "operation_uncertain"
    #: Reconciliation was asked for an operation that is not in ``UNCERTAIN``. A
    #: confirmed one is settled and re-running it would duplicate its effect; an
    #: authorised one has never been attempted and needs no probe.
    OPERATION_NOT_UNCERTAIN = "operation_not_uncertain"
    #: The probe found bytes at the operation's path that this operation did not
    #: predict. Nothing was overwritten — a human decides, because the alternative
    #: is a second writer on the one path where a second writer is expensive.
    OPERATION_CONFLICT = "operation_conflict"


class ApplicationRefusedError(RuntimeError):
    """The application layer refused, and says why.

    One type for every refusal, with a machine-readable reason and a message
    that names what was wrong. The refusals raised by the machinery this layer
    calls — the policy's, the ledger's, the store's — are translated into this
    one rather than swallowed, and the original is kept as the cause, so
    nothing is lost by the translation and a caller has one thing to catch.
    """

    def __init__(self, reason: ApplicationRefusal, detail: str) -> None:
        super().__init__(f"application refused ({reason.value}): {detail}")
        self.reason = reason
        self.detail = detail

    def to_payload(self) -> dict[str, str]:
        """The refusal as data, for a surface to render.

        The same two fields for every surface and every operation: the reason a
        machine branches on, and the message a person reads. A surface that
        wanted to format this differently per operation would need to know
        which operation produced it, which is exactly what this type exists to
        prevent.
        """
        return {"reason": self.reason.value, "message": str(self)}


__all__ = ["ApplicationRefusal", "ApplicationRefusedError"]
