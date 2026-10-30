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

from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.material.intake import IntakeRefusal
from labcairn.papers.chain import ChainRefusal
from labcairn.papers.versions import PaperRefusal
from labcairn.roles.refusals import RoleRefusal
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
    # -- LC-P2-09: the feedback chain ------------------------------------- #
    #: The store holds no paper project with that id. A chain about a
    #: manuscript nobody holds is a chain about nothing.
    CHAIN_PROJECT_NOT_FOUND = "chain_project_not_found"
    #: The store holds no manuscript version with that id.
    CHAIN_VERSION_NOT_FOUND = "chain_version_not_found"
    #: The store holds no feedback event with that id.
    CHAIN_FEEDBACK_NOT_FOUND = "chain_feedback_not_found"
    #: The store holds no edit action with that id.
    CHAIN_EDIT_NOT_FOUND = "chain_edit_not_found"
    #: The version names material the ledger does not hold.
    CHAIN_SOURCE_NOT_FOUND = "chain_source_not_found"
    #: The material is there and could not be read. **Unreadable is not the
    #: same as empty**, and a comment in a file nobody can open is not a
    #: comment the chain can claim to have found.
    CHAIN_MATERIAL_UNREADABLE = "chain_material_unreadable"
    #: The file's bytes are not the bytes the version was made from. The
    #: version names a manuscript, and a manuscript that has changed under
    #: the name is not the one the coordinates would name.
    CHAIN_MATERIAL_DRIFTED = "chain_material_drifted"
    #: The anchored text no longer hashes to what was recorded. The
    #: manuscript's bytes changed under the anchor, so it is **stale** --
    #: reported as stale rather than silently re-pointed.
    CHAIN_ANCHOR_STALE = "chain_anchor_stale"
    #: A model may not write a comment. **The row that holds a locator is
    #: the row the reader wrote**, and a model may not cause the system to
    #: claim the advisor said something -- ADR-0016's third promotion path.
    CHAIN_MODEL_MAY_NOT_WRITE_A_COMMENT = "chain_model_may_not_write_a_comment"
    #: A response state other than ``pending`` was asked for with no
    #: evidence behind it. **A status anybody can set is not a status.**
    CHAIN_RESPONSE_NEEDS_EVIDENCE = "chain_response_needs_evidence"
    #: A model may put a link forward, but it may not decide one. Only a
    #: rule or a person settles whether a change answered a comment.
    CHAIN_RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL = "chain_response_may_not_be_decided_by_a_model"
    #: An assessment was asked for with no evidence of its own.
    CHAIN_ASSESSMENT_NEEDS_EVIDENCE = "chain_assessment_needs_evidence"
    #: The assessment rests on something that is not evidence of the
    #: advice's correctness. **"The change was accepted" is one of those
    #: things** -- acceptance is a fact about the process, and the
    #: correctness of the advice is a claim about the science.
    CHAIN_ASSESSMENT_BASIS_REFUSED = "chain_assessment_basis_refused"
    #: An issue key was asked to be derived rather than given. The same
    #: wording is not the same issue, and a recurrence is recorded rather
    #: than inferred.
    CHAIN_ISSUE_KEY_MAY_NOT_BE_INFERRED = "chain_issue_key_may_not_be_inferred"
    # -- the reasons the guidance memory says no ---------------------------- #
    #
    # **Why these are the memory's own, and not one ``rule_refused``.** The
    # same argument the run path's vocabulary makes: a surface branches on a
    # *reason*, and "the problem is outside the vocabulary" and "the proposer
    # cannot confirm their own rule" are different remedies for different
    # people — one is a wording fix, the other is a person the record needs.
    #: The rule's problem is not one of the closed vocabulary's labels.
    GUIDANCE_PROBLEM_OUTSIDE_VOCABULARY = "guidance_problem_outside_vocabulary"
    #: A required field of the rule is missing or empty.
    GUIDANCE_RULE_FIELD_EMPTY = "guidance_rule_field_empty"
    #: The rule names no chain material, and a rule without a source is not
    #: a rule.
    GUIDANCE_RULE_WITHOUT_SOURCE = "guidance_rule_without_source"
    #: No rule carries that id, at any version.
    GUIDANCE_RULE_NOT_FOUND = "guidance_rule_not_found"
    #: The proposer cannot be the one who confirms the rule.
    GUIDANCE_CONFIRMER_IS_PROPOSER = "guidance_confirmer_is_proposer"
    #: The state transition asked for is not one the machine has.
    GUIDANCE_TRANSITION_NOT_POSSIBLE = "guidance_transition_not_possible"
    #: A dispute or a retraction without a reason is a shrug.
    GUIDANCE_RESOLUTION_WITHOUT_REASON = "guidance_resolution_without_reason"
    #: A counterexample with no case in it challenges nothing.
    GUIDANCE_COUNTEREXAMPLE_EMPTY = "guidance_counterexample_empty"
    # -- the reasons the role contract says no ------------------------------ #
    #
    # **Why these are the contract's own.** The boundary exists to refuse a
    # call a contract does not allow, and a refusal a surface cannot branch
    # on is a refusal a caller can only read. "The capability is not listed"
    # and "the action is forbidden" have different remedies — one is a
    # contract amendment, the other is the operation stopping — so they are
    # different reasons, and the machine reads them without a message.
    #: A required field of the spec is missing or empty.
    ROLE_SPEC_FIELD_EMPTY = "role_spec_field_empty"
    #: The spec names a capability the security layer has not registered.
    ROLE_SPEC_CAPABILITY_UNKNOWN = "role_spec_capability_unknown"
    #: The spec names a forbidden action outside the closed five.
    ROLE_SPEC_FORBIDDEN_ACTION_UNKNOWN = "role_spec_forbidden_action_unknown"
    #: The spec declares no purpose for which it may read material.
    ROLE_SPEC_PURPOSE_EMPTY = "role_spec_purpose_empty"
    #: The operation asked to exercise a capability the spec does not list.
    ROLE_SPEC_CAPABILITY_NOT_LISTED = "role_spec_capability_not_listed"
    #: The operation asked to perform an action the spec forbids.
    ROLE_SPEC_FORBIDDEN_ACTION_REQUESTED = "role_spec_forbidden_action_requested"
    #: No spec carries that role id, at any version.
    ROLE_SPEC_NOT_FOUND = "role_spec_not_found"
    #: A spec at that role id and version is already defined.
    ROLE_SPEC_ALREADY_DEFINED = "role_spec_already_defined"
    #: The chain holds no comment under the issue key named.
    ROLE_COMMENT_NOT_IN_THE_CHAIN = "role_comment_not_in_the_chain"
    #: The candidate quotes words the advisor did not write.
    ROLE_QUOTE_NOT_IN_THE_CHAIN = "role_quote_not_in_the_chain"
    #: The alignment named is outside the four the vocabulary closes.
    ROLE_ALIGNMENT_STATE_UNKNOWN = "role_alignment_state_unknown"
    #: The candidate's issue type is outside the closed vocabulary.
    ROLE_CANDIDATE_ISSUE_TYPE_UNKNOWN = "role_candidate_issue_type_unknown"
    #: The edit named does not answer the comment named.
    ROLE_EDIT_DOES_NOT_ANSWER_THE_COMMENT = "role_edit_does_not_answer_the_comment"
    #: A version the trajectory was asked to order is not in the graph.
    ROLE_VERSION_OUTSIDE_THE_GRAPH = "role_version_outside_the_graph"
    #: The accepted edges leave the order ambiguous.
    ROLE_VERSION_ORDER_AMBIGUOUS = "role_version_order_ambiguous"
    #: A required field of the card is empty.
    ROLE_CARD_FIELD_EMPTY = "role_card_field_empty"
    #: The card's evidence list is empty.
    ROLE_CARD_WITHOUT_EVIDENCE = "role_card_without_evidence"
    #: The severity named is outside the vocabulary.
    ROLE_SEVERITY_UNKNOWN = "role_severity_unknown"
    #: A claim's kind is outside the vocabulary.
    ROLE_CLAIM_KIND_UNKNOWN = "role_claim_kind_unknown"
    #: A claim cites evidence the card does not declare.
    ROLE_CLAIM_WITHOUT_EVIDENCE = "role_claim_without_evidence"
    #: An advisor claim's quote is not the advisor's words in the chain.
    ROLE_ADVICE_NOT_IN_THE_CHAIN = "role_advice_not_in_the_chain"
    #: The uncertainty named is outside the vocabulary.
    ROLE_UNCERTAINTY_KIND_UNKNOWN = "role_uncertainty_kind_unknown"
    #: An abstention that cannot say what it lacks.
    ROLE_ABSTENTION_WITHOUT_A_MISSING = "role_abstention_without_a_missing"
    #: The memory holds no rule under the id a card tries to cite.
    ROLE_RULE_NOT_IN_THE_MEMORY = "role_rule_not_in_the_memory"
    #: The verdict named is outside the four the vocabulary closes.
    ROLE_VERDICT_UNKNOWN = "role_verdict_unknown"
    #: The review accepted evidence it cannot check.
    ROLE_UNVERIFIABLE_EVIDENCE_ACCEPTED = "role_unverifiable_evidence_accepted"
    #: A chain reference names a key the chain does not hold.
    ROLE_EVIDENCE_NOT_IN_THE_CHAIN = "role_evidence_not_in_the_chain"
    #: A refusing verdict carries no reason for the hand-over.
    ROLE_HANDOVER_WITHOUT_A_REASON = "role_handover_without_a_reason"


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

#: Every refusal the feedback chain can make, and the layer's name for it.
#:
#: **The same closure, over the chain's own vocabulary.** The chain knows
#: things the layer does not — that an anchor is stale, that a model may
#: not write a comment, that an assessment rests on something that is not
#: evidence — and a reason the layer cannot name is a reason a surface
#: cannot render.
#:
#: The chain's vocabulary lives in :mod:`labcairn.papers.chain`, **below**
#: this module, because the chain's operations raise this module's refusal
#: and this table imports the vocabulary: putting the vocabulary in the
#: chain's operation module would make the import run in a circle.
CHAIN_REFUSALS: Mapping[ChainRefusal, ApplicationRefusal] = {
    ChainRefusal.PROJECT_NOT_FOUND: ApplicationRefusal.CHAIN_PROJECT_NOT_FOUND,
    ChainRefusal.VERSION_NOT_FOUND: ApplicationRefusal.CHAIN_VERSION_NOT_FOUND,
    ChainRefusal.FEEDBACK_NOT_FOUND: ApplicationRefusal.CHAIN_FEEDBACK_NOT_FOUND,
    ChainRefusal.EDIT_NOT_FOUND: ApplicationRefusal.CHAIN_EDIT_NOT_FOUND,
    ChainRefusal.SOURCE_NOT_FOUND: ApplicationRefusal.CHAIN_SOURCE_NOT_FOUND,
    ChainRefusal.MATERIAL_UNREADABLE: ApplicationRefusal.CHAIN_MATERIAL_UNREADABLE,
    ChainRefusal.MATERIAL_DRIFTED: ApplicationRefusal.CHAIN_MATERIAL_DRIFTED,
    ChainRefusal.ANCHOR_STALE: ApplicationRefusal.CHAIN_ANCHOR_STALE,
    ChainRefusal.MODEL_MAY_NOT_WRITE_A_COMMENT: (
        ApplicationRefusal.CHAIN_MODEL_MAY_NOT_WRITE_A_COMMENT
    ),
    ChainRefusal.RESPONSE_NEEDS_EVIDENCE: ApplicationRefusal.CHAIN_RESPONSE_NEEDS_EVIDENCE,
    ChainRefusal.RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL: (
        ApplicationRefusal.CHAIN_RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL
    ),
    ChainRefusal.ASSESSMENT_NEEDS_EVIDENCE: ApplicationRefusal.CHAIN_ASSESSMENT_NEEDS_EVIDENCE,
    ChainRefusal.ASSESSMENT_BASIS_REFUSED: ApplicationRefusal.CHAIN_ASSESSMENT_BASIS_REFUSED,
    ChainRefusal.ISSUE_KEY_MAY_NOT_BE_INFERRED: (
        ApplicationRefusal.CHAIN_ISSUE_KEY_MAY_NOT_BE_INFERRED
    ),
}

GUIDANCE_REFUSALS: Mapping[GuidanceRefusal, ApplicationRefusal] = {
    GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY: (
        ApplicationRefusal.GUIDANCE_PROBLEM_OUTSIDE_VOCABULARY
    ),
    GuidanceRefusal.RULE_FIELD_EMPTY: ApplicationRefusal.GUIDANCE_RULE_FIELD_EMPTY,
    GuidanceRefusal.RULE_WITHOUT_SOURCE: ApplicationRefusal.GUIDANCE_RULE_WITHOUT_SOURCE,
    GuidanceRefusal.RULE_NOT_FOUND: ApplicationRefusal.GUIDANCE_RULE_NOT_FOUND,
    GuidanceRefusal.CONFIRMER_IS_PROPOSER: (
        ApplicationRefusal.GUIDANCE_CONFIRMER_IS_PROPOSER
    ),
    GuidanceRefusal.TRANSITION_NOT_POSSIBLE: (
        ApplicationRefusal.GUIDANCE_TRANSITION_NOT_POSSIBLE
    ),
    GuidanceRefusal.RESOLUTION_WITHOUT_REASON: (
        ApplicationRefusal.GUIDANCE_RESOLUTION_WITHOUT_REASON
    ),
    GuidanceRefusal.COUNTEREXAMPLE_EMPTY: (
        ApplicationRefusal.GUIDANCE_COUNTEREXAMPLE_EMPTY
    ),
}

ROLE_REFUSALS: Mapping[RoleRefusal, ApplicationRefusal] = {
    RoleRefusal.SPEC_FIELD_EMPTY: ApplicationRefusal.ROLE_SPEC_FIELD_EMPTY,
    RoleRefusal.SPEC_CAPABILITY_UNKNOWN: ApplicationRefusal.ROLE_SPEC_CAPABILITY_UNKNOWN,
    RoleRefusal.SPEC_FORBIDDEN_ACTION_UNKNOWN: (
        ApplicationRefusal.ROLE_SPEC_FORBIDDEN_ACTION_UNKNOWN
    ),
    RoleRefusal.SPEC_PURPOSE_EMPTY: ApplicationRefusal.ROLE_SPEC_PURPOSE_EMPTY,
    RoleRefusal.SPEC_CAPABILITY_NOT_LISTED: (
        ApplicationRefusal.ROLE_SPEC_CAPABILITY_NOT_LISTED
    ),
    RoleRefusal.SPEC_FORBIDDEN_ACTION_REQUESTED: (
        ApplicationRefusal.ROLE_SPEC_FORBIDDEN_ACTION_REQUESTED
    ),
    RoleRefusal.SPEC_NOT_FOUND: ApplicationRefusal.ROLE_SPEC_NOT_FOUND,
    RoleRefusal.SPEC_ALREADY_DEFINED: ApplicationRefusal.ROLE_SPEC_ALREADY_DEFINED,
    RoleRefusal.COMMENT_NOT_IN_THE_CHAIN: (
        ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN
    ),
    RoleRefusal.QUOTE_NOT_IN_THE_CHAIN: ApplicationRefusal.ROLE_QUOTE_NOT_IN_THE_CHAIN,
    RoleRefusal.ALIGNMENT_STATE_UNKNOWN: (
        ApplicationRefusal.ROLE_ALIGNMENT_STATE_UNKNOWN
    ),
    RoleRefusal.CANDIDATE_ISSUE_TYPE_UNKNOWN: (
        ApplicationRefusal.ROLE_CANDIDATE_ISSUE_TYPE_UNKNOWN
    ),
    RoleRefusal.EDIT_DOES_NOT_ANSWER_THE_COMMENT: (
        ApplicationRefusal.ROLE_EDIT_DOES_NOT_ANSWER_THE_COMMENT
    ),
    RoleRefusal.VERSION_OUTSIDE_THE_GRAPH: (
        ApplicationRefusal.ROLE_VERSION_OUTSIDE_THE_GRAPH
    ),
    RoleRefusal.VERSION_ORDER_AMBIGUOUS: (
        ApplicationRefusal.ROLE_VERSION_ORDER_AMBIGUOUS
    ),
    RoleRefusal.CARD_FIELD_EMPTY: ApplicationRefusal.ROLE_CARD_FIELD_EMPTY,
    RoleRefusal.CARD_WITHOUT_EVIDENCE: ApplicationRefusal.ROLE_CARD_WITHOUT_EVIDENCE,
    RoleRefusal.SEVERITY_UNKNOWN: ApplicationRefusal.ROLE_SEVERITY_UNKNOWN,
    RoleRefusal.CLAIM_KIND_UNKNOWN: ApplicationRefusal.ROLE_CLAIM_KIND_UNKNOWN,
    RoleRefusal.CLAIM_WITHOUT_EVIDENCE: (
        ApplicationRefusal.ROLE_CLAIM_WITHOUT_EVIDENCE
    ),
    RoleRefusal.ADVICE_NOT_IN_THE_CHAIN: (
        ApplicationRefusal.ROLE_ADVICE_NOT_IN_THE_CHAIN
    ),
    RoleRefusal.UNCERTAINTY_KIND_UNKNOWN: (
        ApplicationRefusal.ROLE_UNCERTAINTY_KIND_UNKNOWN
    ),
    RoleRefusal.ABSTENTION_WITHOUT_A_MISSING: (
        ApplicationRefusal.ROLE_ABSTENTION_WITHOUT_A_MISSING
    ),
    RoleRefusal.RULE_NOT_IN_THE_MEMORY: (
        ApplicationRefusal.ROLE_RULE_NOT_IN_THE_MEMORY
    ),
    RoleRefusal.VERDICT_UNKNOWN: ApplicationRefusal.ROLE_VERDICT_UNKNOWN,
    RoleRefusal.UNVERIFIABLE_EVIDENCE_ACCEPTED: (
        ApplicationRefusal.ROLE_UNVERIFIABLE_EVIDENCE_ACCEPTED
    ),
    RoleRefusal.EVIDENCE_NOT_IN_THE_CHAIN: (
        ApplicationRefusal.ROLE_EVIDENCE_NOT_IN_THE_CHAIN
    ),
    RoleRefusal.HANDOVER_WITHOUT_A_REASON: (
        ApplicationRefusal.ROLE_HANDOVER_WITHOUT_A_REASON
    ),
}


def role_refused(reason: RoleRefusal, detail: str) -> ApplicationRefusedError:
    """The refusal of the role machinery, carrying its own reason.

    :class:`labcairn.roles.refusals.RoleRefusal` enumerates the reasons the
    contract says no, and this table gives each one the application layer's
    name. The mapping is looked up, not defaulted, for the reason
    :func:`consent_refusal_name` records.
    """
    return ApplicationRefusedError(ROLE_REFUSALS[reason], detail)


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


def chain_refusal_name(reason: ChainRefusal) -> ApplicationRefusal:
    """The layer's name for a refusal of the feedback chain.

    **Looked up, not defaulted**, for the reason
    :func:`consent_refusal_name` records.
    """
    return CHAIN_REFUSALS[reason]


def chain_refused(reason: ChainRefusal, detail: str) -> ApplicationRefusedError:
    """The refusal of a chain operation, named in the layer's vocabulary.

    **One spelling, so a surface catches one thing.** A chain operation
    that raised its own exception type would give a surface two exception
    types to catch for the same problem, and a surface that has to catch
    four to draw one error eventually misses one.
    """
    return ApplicationRefusedError(chain_refusal_name(reason), detail)


def guidance_refused(reason: GuidanceRefusal, detail: str) -> ApplicationRefusedError:
    """The refusal of a rule-memory operation, named in the layer's vocabulary.

    **One spelling, so a surface catches one thing** — the same argument
    :func:`chain_refused` records, and the same lookup rather than a
    default.
    """
    return ApplicationRefusedError(GUIDANCE_REFUSALS[reason], detail)


__all__ = [
    "CHAIN_REFUSALS",
    "CONSENT_REFUSALS",
    "GUIDANCE_REFUSALS",
    "INTAKE_REFUSALS",
    "PAPER_REFUSALS",
    "ROLE_REFUSALS",
    "ApplicationRefusal",
    "ApplicationRefusedError",
    "chain_refusal_name",
    "chain_refused",
    "consent_refusal_name",
    "guidance_refused",
    "intake_refusal_name",
    "paper_refusal_name",
    "role_refused",
]
