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

from collections.abc import Mapping
from enum import StrEnum

from labcairn.material.intake import IntakeRefusal
from labcairn.papers.versions import PaperRefusal
from labcairn.security.permissions import ConsentRefusal


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
    #: The source exists, and the task does not hold it. A claim rested on
    #: material the task does not carry would be an anchor the report builder
    #: refuses, so the write is refused where the mistake is made.
    SOURCE_NOT_BOUND = "source_not_bound"
    #: The ledger holds no text at the address named, in the bytes the source
    #: currently holds.
    ADDRESS_NOT_FOUND = "address_not_found"
    #: The task's ledger already holds a record whose extracted span hashes to
    #: the same value. ``uq_evidence_task_span`` permits one record per span
    #: per task, so the second write is refused by name rather than by a
    #: constraint error out of the middle of the transaction.
    CLAIM_ALREADY_RECORDED = "claim_already_recorded"
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
    # -- the reasons the analysis run path says, carried through the layer ----- #
    #
    # **Why these are the layer's own, and not one ``analysis_refused`.** The
    # layer's argument is that a surface branches on a *reason* rather than
    # reading a message. The run path already has a fifteen-member vocabulary of
    # why it said no; flattening it to one reason at the layer's boundary would
    # throw away the difference between "no such operator" and "the units in that
    # column contradict its header", which are different remedies for different
    # people. ``tests/test_analysis_service.py`` closes the two vocabularies
    # against each other, so a refusal in the run path cannot arrive at a surface
    # unmapped.
    #: The catalogue holds no operator with that id.
    OPERATOR_NOT_REGISTERED = "operator_not_registered"
    #: The material is not ``readable``. ADR-0004 A7: unreadable material is
    #: neither analysed nor cited, and unreadable is not the same as empty.
    SOURCE_UNREADABLE = "source_unreadable"
    #: The file's bytes are not the bytes the source was ingested from.
    SOURCE_DRIFTED = "source_drifted"
    #: The material has more than one sheet, so a row and a header do not name
    #: one address.
    SOURCE_AMBIGUOUS = "source_ambiguous"
    #: The selection names a different source, or different bytes, than the run
    #: was asked about.
    SELECTION_MISMATCH = "selection_mismatch"
    #: The operator's own run was refused, whatever raised it. The message names
    #: the column and the contradiction; the reason says only that the operator
    #: refused.
    OPERATOR_REFUSED = "operator_refused"
    #: The reproducibility manifest could not be built, so nothing was recorded.
    MANIFEST_REFUSED = "manifest_refused"
    #: The chart recipe the figure is to be drawn from is not there to be read.
    RECIPE_UNREADABLE = "recipe_unreadable"
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
    # -- LC-P2-06: the consent machinery ------------------------------- #
    #: No grant covers this use. **The permission is denied by the absence of
    #: a row**, so the remedy is a grant and not an exemption -- ADR-0015 D2.
    CONSENT_NO_GRANT = "consent_no_grant"
    #: A grant covers the permission but not the purpose. The remedy is a
    #: grant for this purpose.
    CONSENT_PURPOSE_NOT_GRANTED = "consent_purpose_not_granted"
    #: A grant covers the permission and the purpose but names another
    #: destination. **A grant naming provider A does not authorise provider
    #: B** -- ADR-0015 D3.
    CONSENT_DESTINATION_NOT_GRANTED = "consent_destination_not_granted"
    #: The grant that would have covered this use was withdrawn. **This is not
    #: the same as never having been permitted**, and only the first is a
    #: question about a person.
    CONSENT_GRANT_WITHDRAWN = "consent_grant_withdrawn"
    #: The grant existed and has run out.
    CONSENT_GRANT_EXPIRED = "consent_grant_expired"
    #: The grant is recorded but its window has not opened.
    CONSENT_GRANT_NOT_YET_ACTIVE = "consent_grant_not_yet_active"
    #: A grant exists for this subject, permission and purpose, but its scope
    #: does not reach this material.
    CONSENT_SCOPE_NOT_COVERED = "consent_scope_not_covered"
    #: No grant covers this material. **The file is not opened, not listed
    #: and not measured**, because reading it is what the grant is about, and
    #: a refusal that has already read the file has done the thing the grant
    #: forbade.
    INTAKE_NO_GRANT = "intake_no_grant"
    #: An archive declares a compression ratio beyond the declared ceiling.
    #: **The bomb is refused by its declaration**, so the check never expands
    #: the archive.
    INTAKE_ZIP_BOMB = "intake_zip_bomb"
    #: An archive entry's path escapes the extraction root.
    INTAKE_PATH_TRAVERSAL = "intake_path_traversal"
    #: A macro-enabled document. **The macro is not executed, and the file is
    #: not cleaned**: a refusal is honest where a partial acceptance is not.
    INTAKE_MACRO_NOT_EXECUTED = "intake_macro_not_executed"
    #: An archive is larger than the declared ceiling.
    INTAKE_ARCHIVE_TOO_LARGE = "intake_archive_too_large"
    #: The bytes are not an archive this reader can open. It is inventoried
    #: and hashed, and nothing is taken from it.
    INTAKE_NOT_AN_ARCHIVE = "intake_not_an_archive"
    # -- LC-P2-09: the version graph -------------------------------------- #
    #
    #: **The paper project's own refusals, and they are named apart from the
    #: ledger's.** A version that names a file the ledger does not hold is the
    #: ledger's refusal and says so; a version the *graph* does not hold is
    #: the graph's, and the two are different questions — one is about a file,
    #: the other about a node.
    #: The store holds no paper project with that id.
    PAPER_PROJECT_NOT_FOUND = "paper_project_not_found"
    #: The store holds no version with that id.
    PAPER_VERSION_NOT_FOUND = "paper_version_not_found"
    #: The store holds no edge with that id.
    PAPER_EDGE_NOT_FOUND = "paper_edge_not_found"
    #: **The frozen contract refused the row.** The three facts that stay
    #: apart, the forbidden self-parent and the confirmation's own rules are
    #: the contracts' rules, and the store asks them rather than restating
    #: them. The message names which rule refused, because a reason nobody
    #: can act on is the same as no reason.
    PAPER_CONTRACT_REFUSED = "paper_contract_refused"
    #: The edge's parent or child belongs to another manuscript. **A claim
    #: about a lineage that does not exist**, and a CHECK constraint cannot
    #: see it, because it is a fact about three rows.
    PAPER_CROSS_PROJECT = "paper_cross_project"
    #: The id is already recorded. An id is minted once, and a second write
    #: with it would be a second row wearing one name.
    PAPER_ALREADY_RECORDED = "paper_already_recorded"


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


#: Every refusal the consent machinery can make, and the layer's name for it.
#:
#: **Closed, and checked closed**, for the reason
#: :data:`labcairn.application.analysis.ANALYSIS_REFUSALS` records: a member of
#: :class:`~labcairn.security.permissions.ConsentRefusal` with no row here
#: would reach a surface as an unmapped reason, and the layer would have to
#: invent a label for somebody else's refusal at the moment somebody needed
#: to read it.
CONSENT_REFUSALS: Mapping[ConsentRefusal, ApplicationRefusal] = {
    ConsentRefusal.NO_GRANT: ApplicationRefusal.CONSENT_NO_GRANT,
    ConsentRefusal.PURPOSE_NOT_GRANTED: ApplicationRefusal.CONSENT_PURPOSE_NOT_GRANTED,
    ConsentRefusal.DESTINATION_NOT_GRANTED: ApplicationRefusal.CONSENT_DESTINATION_NOT_GRANTED,
    ConsentRefusal.GRANT_WITHDRAWN: ApplicationRefusal.CONSENT_GRANT_WITHDRAWN,
    ConsentRefusal.GRANT_EXPIRED: ApplicationRefusal.CONSENT_GRANT_EXPIRED,
    ConsentRefusal.GRANT_NOT_YET_ACTIVE: ApplicationRefusal.CONSENT_GRANT_NOT_YET_ACTIVE,
    ConsentRefusal.SCOPE_NOT_COVERED: ApplicationRefusal.CONSENT_SCOPE_NOT_COVERED,
}

#: Every refusal the intake guards can make, and the layer's name for it.
#:
#: **The same closure, over the intake's own vocabulary.** The guards refuse
#: before they open, and their reasons are the ones a person needs to read:
#: *no grant*, *too large*, *the path escapes*, *the macro is not
#: executed*. A reason the layer cannot name is a reason a surface cannot
#: render.
INTAKE_REFUSALS: Mapping[IntakeRefusal, ApplicationRefusal] = {
    IntakeRefusal.NO_GRANT: ApplicationRefusal.INTAKE_NO_GRANT,
    IntakeRefusal.ZIP_BOMB: ApplicationRefusal.INTAKE_ZIP_BOMB,
    IntakeRefusal.PATH_TRAVERSAL: ApplicationRefusal.INTAKE_PATH_TRAVERSAL,
    IntakeRefusal.MACRO_NOT_EXECUTED: ApplicationRefusal.INTAKE_MACRO_NOT_EXECUTED,
    IntakeRefusal.ARCHIVE_TOO_LARGE: ApplicationRefusal.INTAKE_ARCHIVE_TOO_LARGE,
    IntakeRefusal.NOT_AN_ARCHIVE: ApplicationRefusal.INTAKE_NOT_AN_ARCHIVE,
}


def consent_refusal_name(reason: ConsentRefusal) -> ApplicationRefusal:
    """The layer's name for a refusal of the consent machinery.

    **Looked up, not defaulted.** A reason with no row above is a bug in
    that table, and it must arrive as one rather than wearing somebody
    else's label.
    """
    return CONSENT_REFUSALS[reason]


def intake_refusal_name(reason: IntakeRefusal) -> ApplicationRefusal:
    """The layer's name for a refusal of the intake guards.

    **Looked up, not defaulted**, for the reason
    :func:`consent_refusal_name` records.
    """
    return INTAKE_REFUSALS[reason]


#: Every refusal the version graph can make, and the layer's name for it.
#:
#: **The same closure, over the version graph's own vocabulary.** The store
#: refuses a row for six reasons, and each of them says something a surface
#: has to be able to render: *no such project*, *no such version*, *no such
#: edge*, *the contract refused it*, *it crosses a project*, *the id is
#: taken*. They are different situations with different remedies, and a reason
#: the layer cannot name is a reason a surface cannot render.
PAPER_REFUSALS: Mapping[PaperRefusal, ApplicationRefusal] = {
    PaperRefusal.PROJECT_NOT_FOUND: ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
    PaperRefusal.VERSION_NOT_FOUND: ApplicationRefusal.PAPER_VERSION_NOT_FOUND,
    PaperRefusal.EDGE_NOT_FOUND: ApplicationRefusal.PAPER_EDGE_NOT_FOUND,
    PaperRefusal.CONTRACT_REFUSED: ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    PaperRefusal.CROSS_PROJECT: ApplicationRefusal.PAPER_CROSS_PROJECT,
    PaperRefusal.ALREADY_RECORDED: ApplicationRefusal.PAPER_ALREADY_RECORDED,
}


def paper_refusal_name(reason: PaperRefusal) -> ApplicationRefusal:
    """The layer's name for a refusal of the version graph.

    **Looked up, not defaulted**, for the reason
    :func:`consent_refusal_name` records.
    """
    return PAPER_REFUSALS[reason]


__all__ = [
    "CONSENT_REFUSALS",
    "INTAKE_REFUSALS",
    "PAPER_REFUSALS",
    "ApplicationRefusal",
    "ApplicationRefusedError",
    "consent_refusal_name",
    "intake_refusal_name",
    "paper_refusal_name",
]
