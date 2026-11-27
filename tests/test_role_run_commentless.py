"""The mentor loop over a document that carries no advisor's comment.

**What is under test.** LC-P4 pilot, first round §4.1: *"The suggestion
loop — the copy has no comments."* The chain's refusal
``role_comment_not_in_the_chain`` sat at the only route to a model the CLI
had, so a manuscript the advisor had not written in was a dead end: the
loop refused, and the refusal was the same refusal the loop gave for a
request about a comment it did hold.

This file watches the difference between those two cases, and the four
properties that came with it.

======================================================  =========================
     acceptance                                         witness
======================================================  =========================
a document with no comment takes part in the chain       the run over a chain
                                                          that holds no comment
                                                          at all returns a
                                                          result, and every role
                                                          the request named is
                                                          in it
a role that has nothing to read says what it cannot      the result's
                                                          ``abstentions`` names
                                                          each role and what it
                                                          lacked -- an abstention
                                                          is a role that ran
the refusal for a missing key still stands               a chain that holds
                                                          comments but none
                                                          under the key is still
                                                          refused by name
the consent gate still runs before the spend             a comment-less run
                                                          spends nothing: no
                                                          wire, no approval asked
                                                          for, no exchange in the
                                                          log
the record says what happened                             the event log holds an
                                                          abstention annotation
                                                          naming the project, the
                                                          roles and what each
                                                          lacked, and a reader
                                                          can tell a comment-less
                                                          run from a commented one
======================================================  =========================

**And the refusal's own shape did not change.** A chain that holds
comments but not under the key the request named is still
``role_comment_not_in_the_chain``; that refusal has its own witnesses
(``tests/test_roles_run.py``) and they are not weakened here. **What moved
is the branch the loop takes, not the refusal it gives.**

**Nothing here calls a model.** The comment-less run reaches no wire by
construction, and the fake provider the project's other witnesses use is
what the commented case would use -- so a green run here costs nothing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from feedback_chain_fixtures import MOMENT, ChainEnv, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.events import read_events
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.roles_run import (
    ModelCallPlan,
    RoleRunRequest,
    TrajectoryJudgement,
    request_role_run,
    run_role_run,
    the_role_run_run,
)
from labcairn.db.repository import list_approvals
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.runtime.event import EventType
from labcairn.security.capabilities import CapabilityId

pytestmark = pytest.mark.integration

env = _shared_env

EXPIRES = MOMENT.replace(year=2027)

#: The key the request names. **No comment is filed under it**, and in the
#: comment-less chain there is no comment anywhere.
KEY = "iss-nowhere"

#: The advisor's own words, as the commented chain holds them. **The quote
#: role A works from is a verbatim substring of this**, and the role checks
#: it.
COMMENT = "Define the parameter."

DESTINATION = "api.model-provider.example"

#: The workspace-relative path of the material, as the chain holds it.
MATERIAL_PATH = "materials/manuscript.docx"
MATERIAL_KEY = "manuscript.docx"
MATERIAL_ROOT = "source:0"

OBJECTIVES: dict[str, str] = {
    "trajectory": "Align the advisor's comments with the edits actually made.",
    "guidance": "Turn a confirmed case into a card a student can act on.",
    "critique": "Review a card independently and retrieve the counter-evidence.",
}


def _the_child_environment() -> dict[str, str]:
    """The environment the command runs under, and why it is this one.

    **The width is set, because a pipe is not a terminal.** Rich asks the
    terminal how wide it is and wraps its output to fit, so a child whose
    stdout is a pipe renders at eighty columns unless it is told otherwise
    -- and a wrap that falls *inside* a phrase truncates it, so an
    assertion about that phrase would fail for a reason that has nothing
    to do with the property under test. ``COLUMNS`` is the same width the
    project's other CLI witnesses use.

    **The encoding is set** because the child's output encoding is
    otherwise the machine's locale encoding, and a path with a non-ASCII
    character in it would make the test fail for a reason that has nothing
    to do with the CLI.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return environment


@pytest.fixture()
def bare(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain whose manuscripts carry no comment at all.

    **The advisor wrote nothing in the margins.** The fixture plants the
    versions, the edge and the two manuscripts, and the comments it does not
    plant are the point: there are none.

    **And the roles' contracts are planted too**, because a role with no
    contract is refused by name before it can abstain -- and a refusal
    about the contract would say nothing about the comment.

    **And the workspace carries the files a surface command reads.** The
    chain fixture binds a task to the directory, but the CLI's own command
    reads the workspace's ``workspace.json``, its policy and its database by
    name; those are written here, so ``roles run`` -- which runs in its own
    process against this workspace -- finds what a workspace the product
    initialised would hold. The database is the fixture's own file, named
    in the configuration; the policy allows everything, because what is
    under test is the wiring, not the policy.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    chain = build_chain(env.store(), workspace_root)
    for role_id in ("trajectory", "guidance", "critique"):
        _spec(chain.context, role_id)
    _write_the_workspace(chain)
    return chain


def _write_the_workspace(chain: ChainEnv) -> None:
    """The workspace's own files, so the CLI's command can reach the run.

    **The command runs in its own process**, and it finds the workspace by
    name: the configuration file, the policy, and the database the
    configuration names. A fixture that wrote only the rows would leave the
    command looking at a directory that is not a workspace at all.
    """
    from labcairn.cli.workspace import (
        CONFIG_SCHEMA_VERSION,
        DEFAULT_POLICY_RULES,
        WorkspaceConfig,
        WorkspaceLocation,
        write_config,
        write_policy,
    )
    from labcairn.security.policy import Permission, Rule

    location = WorkspaceLocation(root=chain.context.workspace.selected_root)
    write_policy(
        location,
        (
            *DEFAULT_POLICY_RULES,
            Rule(effect=Permission.ALLOW, pattern="**"),
        ),
    )
    write_config(
        location,
        WorkspaceConfig(
            schema_version=CONFIG_SCHEMA_VERSION,
            database="../labcairn.db",
            source_dirs=("materials",),
            current_task=str(chain.context.task_id),
        ),
    )
    assert location.config_path.is_file(), "the workspace carries its configuration"


def _spec(context: ApplicationContext, role_id: str) -> AgentRoleSpec:
    """One role's contract, with the capability the run exercises."""
    return define_role_spec(
        context,
        role_id=role_id,
        role_version=1,
        objective=OBJECTIVES[role_id],
        input_schema="Input",
        output_schema="Output",
        allowed_capabilities=(CapabilityId.MODEL_REQUEST,),
        forbidden_actions=FORBIDDEN_ACTIONS,
        allowed_data_purposes=("guidance_review",),
        provider_routing_policy="single-provider-per-call",
        cost_budget=None,
        token_budget=4000,
        timeout_seconds=120,
        retry_policy="no-retry",
        fallback_policy="abstain",
        abstain_conditions=("material_under_two_comments",),
        escalation_conditions=("a_conflict_between_two_rules",),
        prompt_template_version=f"{role_id}-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )


def _commented_chain(env: StoreEnv, tmp_path: Path, *, key: str) -> ChainEnv:
    """A chain whose first manuscript carries one comment, keyed *key*.

    **The advisor wrote one remark, and it is filed under *key*.** The
    second manuscript carries none -- so the chain holds a comment and the
    question is whether the request names the right one.
    """
    from feedback_chain_fixtures import a_comment

    from labcairn.papers.feedback import record_feedback, set_issue_key

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    chain = build_chain(env.store(), workspace_root, comments=(a_comment("201"),))
    for role_id in ("trajectory", "guidance", "critique"):
        _spec(chain.context, role_id)
    (event,) = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
    return chain


def _request(
    chain: ChainEnv,
    *,
    roles: tuple[str, ...],
    trajectory: TrajectoryJudgement | None = None,
) -> RoleRunRequest:
    """A request for the roles named, on the chain the fixture planted."""
    return RoleRunRequest(
        roles=roles,
        project_id=chain.project_id,
        issue_key=KEY,
        version_ids=(chain.version_id, chain.second_version_id),
        trajectory=trajectory,
    )


def _trajectory_judgement() -> TrajectoryJudgement:
    """The judgement role A works from, supplied outright.

    **The quote is the advisor's own words**, verbatim -- the role checks
    it against the comment the chain holds, and a paraphrase offered as a
    quotation is refused by name.
    """
    return TrajectoryJudgement(
        issue_type="method_and_hypothesis",
        alignment="partial",
        advisor_quote=COMMENT,
        note="the change answered the wording, not the missing quantity.",
        edit_action_id=None,
    )


def _plan() -> ModelCallPlan:
    """What the model call would need, declaring the chain's material.

    **The declaration is the chain's own address.** The loop checks it
    against what it reads, so a comment-less run is refused by name when
    the caller declares a material the chain does not hold.
    """
    return ModelCallPlan(
        provider="fake",
        model="scripted",
        root_id=MATERIAL_ROOT,
        resource_key=MATERIAL_KEY,
        material_ref=MATERIAL_PATH,
        purpose="guidance_review",
        destination=DESTINATION,
        subject_ref="proj-1",
    )


def _refusal_reason(call: object) -> object:
    """The refusal an expected error carries, so the test fails on the
    wrong refusal rather than on any error at all."""
    with pytest.raises(ApplicationRefusedError) as caught:
        call()  # type: ignore[operator]
    return caught.value.reason


def _role_refusal_reason(call: object) -> RoleRefusal:
    """The role's refusal an expected error carries.

    **The application layer maps the role's vocabulary into its own**, so
    the reason that reaches the caller is the application's. The mapping
    is a bijection over the reasons the roles raise, so the role's own
    name is recovered from it -- and the assertion that the name is a role
    refusal at all is what fails loudly when the loop refuses for some
    other reason.
    """
    reason = _refusal_reason(call)
    assert isinstance(reason, ApplicationRefusal), (
        f"expected an application refusal, saw {reason!r}"
    )
    assert reason.value.startswith("role_"), f"expected a role refusal, saw {reason.value!r}"
    return RoleRefusal(reason.value.removeprefix("role_"))


# --------------------------------------------------------------------------- #
# a document with no comment takes part in the chain
# --------------------------------------------------------------------------- #


def test_a_chain_that_holds_no_comment_at_all_is_not_a_dead_end(bare: ChainEnv) -> None:
    """The run answers, and the roles it names are in the answer.

    **This is the whole of the gap.** The chain's own promise is that a
    manuscript holding hundreds of changes and no comment at all is a shape
    the chain can report and does not explain away -- so the loop reports
    it, and the roles that ran are named in the result.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    assert result.roles == ("trajectory", "guidance"), (
        "the roles the request named are the roles that ran"
    )
    assert result.exchange_event_id is None, "no model was called, so no exchange"
    assert result.answer is None, "no model was asked, so there is no answer"


def test_each_role_says_what_it_could_not_answer(bare: ChainEnv) -> None:
    """An abstention is a role that ran, and it names what was missing.

    **A run that quietly did less than it reported is the failure this
    whole shape exists to prevent.** So the abstention is a first-class
    output: every role the request named is in the mapping, and the mapping
    says what that role lacked.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance", "critique")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    assert set(result.abstentions) == {"trajectory", "guidance", "critique"}, (
        "every role that ran abstained, and every abstention is named"
    )
    for role_id, what_is_missing in result.abstentions.items():
        assert what_is_missing.strip(), (
            f"the abstention of {role_id!r} names no missing thing, and an"
            " abstention that cannot say what it lacks is a shrug"
        )
    assert "comment" in result.abstentions["trajectory"], (
        "role A lacked a comment to align, and says so in those words"
    )


def test_role_as_abstention_is_the_roles_own_output(bare: ChainEnv) -> None:
    """Role A's abstention is carried the way its candidate would be.

    **A role that abstained is a role that ran**, so its output is the
    role's own type and not a string in a mapping. And the abstention
    carries **no advisor's quote** -- because there were no advisor's words
    to carry, and a shape with an empty quote would be one in which a role
    could say *"I judged the advisor's comment"* while having quoted
    nothing.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    assert result.candidate is None, "there was no mark to align, so no candidate"
    assert result.abstention is not None, (
        "role A ran, so its output is the abstention and not nothing"
    )
    assert result.abstention.role_id == "trajectory"
    assert result.abstention.issue_key == KEY
    assert result.abstention.what_is_missing.strip(), "the abstention names what was missing"
    assert not hasattr(result.abstention, "advisor_quote"), (
        "the abstention carries no quote field at all -- an empty one would be a"
        " shape in which a role could claim to have judged a comment it never read"
    )


def test_the_wire_carries_role_as_abstention(bare: ChainEnv) -> None:
    """The abstention reaches the wire as the role's own shape.

    **One conversion, one place** -- so the wire cannot drop what the
    layer carried.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)
    wire = the_role_run_run(result)

    assert wire.abstention is not None, "the wire carries the abstention"
    assert wire.abstention.role_id == "trajectory"
    assert result.abstention is not None
    assert wire.abstention.what_is_missing == result.abstention.what_is_missing


def test_role_c_says_it_cannot_assess(bare: ChainEnv) -> None:
    """The critique's honest answer to evidence it cannot reach.

    **``cannot_assess`` is a verdict in the closed vocabulary**, and it is
    what the review gives when there is nothing to review. The run must not
    manufacture a judgement the material does not support.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("guidance", "critique")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    assert result.verdict is not None, "the critique ran, so it has a verdict"
    assert result.verdict.verdict == "cannot_assess", (
        "the review of a card that is itself an abstention cannot assess"
    )
    assert result.verdict.handover_reason is not None, (
        "a verdict that cannot assess says who has to act next"
    )


def test_the_result_carries_the_documents_shape(bare: ChainEnv) -> None:
    """The result says what the document was, in counts and ids.

    **The counts are the log's own currency**, and they are what lets a
    reader tell this run from a commented one without reading the
    material's text.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    assert result.shape is not None, "every run carries the shape"
    assert result.shape.comment_count == 0, (
        "the chain holds no comment, and the shape says so as a count"
    )
    assert result.shape.project_id == bare.project_id
    assert result.shape.version_ids == (bare.version_id, bare.second_version_id), (
        "the versions are in the accepted edges' order"
    )


def test_the_comment_count_is_the_projects_and_not_one_versions(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The count and the read have to agree about the same fact.

    **The chain reads a comment by key, and a key names a comment wherever
    it was written.** So the shape's count is the project's count. A count
    narrowed to the versions the caller named would say *"no comment"* about
    a project that holds one -- while the read under the same key found it,
    and the run would abstain over a chain that holds the advisor's words.
    """
    from labcairn.application import chain as chain_layer

    chain = _commented_chain(env, tmp_path, key=KEY)

    whole = chain_layer.read_document_shape(chain.context, project_id=chain.project_id)
    assert whole.comment_count == 1, "the project holds the advisor's one remark"

    narrowed = chain_layer.read_document_shape(
        chain.context,
        project_id=chain.project_id,
        version_ids=(chain.second_version_id,),
    )
    assert narrowed.comment_count == 1, (
        "the comment was written on the first round, and the count is the"
        " project's -- the read under the key finds it whatever version the"
        " caller named"
    )
    held = chain_layer.read_comments(chain.context, issue_keys=(KEY,))
    assert len(held) == 1, "and the read under the key agrees"


def test_the_wire_carries_the_abstentions_and_the_shape(bare: ChainEnv) -> None:
    """The API's body and the CLI's ``--json`` say the same thing.

    **One conversion, one place** -- so the wire cannot drop what the
    layer carried. A wire that dropped the abstentions would report a run
    that did less than it did.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)
    wire = the_role_run_run(result)

    assert set(wire.abstentions) == {"trajectory", "guidance"}
    assert wire.shape is not None
    assert wire.shape.comment_count == 0
    assert wire.shape.project_id == bare.project_id


# --------------------------------------------------------------------------- #
# the refusal for a missing key still stands
# --------------------------------------------------------------------------- #


def test_a_chain_that_holds_comments_but_not_this_one_is_still_refused(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A mistake about a comment is still a mistake, and is refused by name.

    **The comment-less case did not swallow this one.** A chain that holds
    a comment under some other key is a chain that holds comments, so the
    request's key is still wrong, and the refusal is the one it always was.
    """
    chain = _commented_chain(env, tmp_path, key="iss-other")

    refused = _role_refusal_reason(
        lambda: request_role_run(
            chain.context,
            _request(chain, roles=("trajectory",)),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused is RoleRefusal.COMMENT_NOT_IN_THE_CHAIN, (
        "the chain holds a comment but not under the key, and that is the"
        " refusal it has always been"
    )


def test_the_refusal_is_the_applications_own_reason(env: StoreEnv, tmp_path: Path) -> None:
    """The refusal the loop raises is the one the vocabulary names.

    **``role_comment_not_in_the_chain`` is the reason a caller sees.** The
    chain layer answers it in the role's vocabulary, and the application
    layer maps that to its own -- so the reason on the wire is the
    application's, not a spelling of it.
    """
    chain = _commented_chain(env, tmp_path, key="iss-other")

    with pytest.raises(ApplicationRefusedError) as caught:
        request_role_run(
            chain.context,
            _request(chain, roles=("trajectory",)),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN, (
        "the refusal is the application's own reason"
    )


# --------------------------------------------------------------------------- #
# the consent gate still runs before the spend
# --------------------------------------------------------------------------- #


def test_a_comment_less_run_spends_nothing(bare: ChainEnv) -> None:
    """No wire, no approval asked for, and no approval consumed.

    **The gate-before-the-spend property is not weakened by the new
    branch.** A comment-less run does not reach the gate at all, because
    there is no spend to gate -- and so it cannot have found a way around
    it either.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance", "critique")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is None, "the run asks no one's consent for a call it will not make"

    result = run_role_run(bare.context, ticket, grants=(), at=MOMENT)
    assert result.exchange_event_id is None, "no model was called"

    page = read_events(bare.context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "the run reached no wire"
    )
    assert not list_approvals(bare.context.store.session, bare.context.task_id), (
        "no approval was asked for, so none was spent"
    )


def test_a_comment_less_run_asks_no_approval_and_the_ask_writes_no_exchange(
    bare: ChainEnv,
) -> None:
    """The ask itself spends nothing, and writes nothing to the wire.

    **The ask is the step that spends the owner's consent**, so a run over
    a document with no comment must leave it as it found it: a question
    written down, and no exchange.
    """
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    page = read_events(bare.context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "asking reached no wire"
    )
    assert ticket.approval_id is None


# --------------------------------------------------------------------------- #
# the record says what happened
# --------------------------------------------------------------------------- #


def test_the_log_holds_the_abstention(bare: ChainEnv) -> None:
    """The record names the project, the roles and what each lacked.

    **The record is not evidence, but it is the log.** A reader of the log
    the next morning has to be able to see that the loop ran and what it
    found -- ids and counts, never the material's text.
    """
    request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory", "guidance")),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    page = read_events(bare.context)
    abstentions = [
        event for event in page.events if event.type is EventType.ROLE_ABSTENTION_RECORDED
    ]
    assert len(abstentions) == 1, "the run is recorded once"
    payload = abstentions[0].payload
    assert payload["project_id"] == bare.project_id
    roles = payload["roles"]
    assert isinstance(roles, list), f"the roles are a list, saw {type(roles).__name__}"
    assert list(roles) == ["trajectory", "guidance"], (
        "the roles that ran are named in the order they ran"
    )
    missing = payload["missing"]
    assert isinstance(missing, dict), f"the missing map is a dict, saw {type(missing).__name__}"
    assert set(missing) == {"trajectory", "guidance"}, "what each role lacked is named"


def test_the_abstention_carries_no_run_and_no_operation(bare: ChainEnv) -> None:
    """The annotation is an observation, not an attempt.

    **No model was called and no approval was spent**, so there is no
    operation for the event to belong to and no run for it to be part of.
    An event that carried one would be the trace that could be mistaken
    for work that was attempted.
    """
    request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    ticket = request_role_run(
        bare.context,
        _request(bare, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    run_role_run(bare.context, ticket, grants=(), at=MOMENT)

    page = read_events(bare.context)
    (event,) = [e for e in page.events if e.type is EventType.ROLE_ABSTENTION_RECORDED]
    assert event.run_id is None, "the abstention is not part of a run"
    assert event.operation_id is None, "the abstention is not part of an operation"
    assert event.transition is None, "an abstention changed no state"


def test_a_reader_can_tell_a_comment_less_run_from_a_commented_one(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The two runs leave different records.

    **A reader must be able to tell them apart afterwards.** The
    comment-less run's own annotation says the chain held no comment; a
    commented run leaves no abstention at all.
    """
    commented = _commented_chain(env, tmp_path, key=KEY)

    ticket = request_role_run(
        commented.context,
        # **The judgement is supplied outright**, so the commented run needs
        # no model and no approval -- the two runs are then compared on
        # their records alone, and neither of them reaches a wire.
        _request(commented, roles=("trajectory",), trajectory=_trajectory_judgement()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    run_role_run(commented.context, ticket, grants=(), at=MOMENT)

    page = read_events(commented.context)
    assert not [
        event for event in page.events if event.type is EventType.ROLE_ABSTENTION_RECORDED
    ], "a run over a commented document leaves no abstention"


def test_the_run_state_is_closed_alongside_the_record(bare: ChainEnv) -> None:
    """A run that abstained has done what it was asked to do.

    **The pilot measured the gap**: a run that did its work and stopped
    left its stage ``blocked`` and its run ``running`` although nothing
    was waiting. A run that abstained has finished, and the finish is in
    the same transaction as the record of what it did.
    """
    from labcairn.application.records import ensure_run, record_role_abstention
    from labcairn.core.ids import RunId, new_id

    run_id = RunId(new_id())
    ensure_run(bare.context, run_id, now=MOMENT)
    record_role_abstention(
        bare.context,
        project_id=bare.project_id,
        roles=("trajectory",),
        missing={"trajectory": "the chain holds no comment for this document"},
        run_id=run_id,
        stage_id=None,
        now=MOMENT,
    )

    page = read_events(bare.context)
    assert [event for event in page.events if event.type is EventType.ROLE_ABSTENTION_RECORDED], (
        "the abstention is recorded"
    )
    assert [event for event in page.events if event.type is EventType.RUN_FINISHED], (
        "the run is finished in the same transaction as the record"
    )


# --------------------------------------------------------------------------- #
# the run the loop gives up on is not silently different
# --------------------------------------------------------------------------- #


def test_a_run_over_a_commented_chain_still_asks_and_still_spends(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The new branch did not swallow the old one.

    **A chain that holds a comment under the key the request named is a
    chain that holds comments**, so the run asks for an approval and the
    run spends one -- the behaviour that was there before the comment-less
    case existed.
    """
    chain = _commented_chain(env, tmp_path, key=KEY)

    ticket = request_role_run(
        chain.context,
        _request(chain, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None, (
        "a run that will ask the model asks for the consent first"
    )


# --------------------------------------------------------------------------- #
# the command, which is where the pilot found the gap
# --------------------------------------------------------------------------- #


def test_the_command_runs_a_comment_less_document(bare: ChainEnv) -> None:
    """``roles run`` answers for a document with no comment.

    **The command is where the gap was found**, so the command is what has
    to answer now. And it answers with the run -- not with a pending
    approval, because there is no call to consent to.
    """
    import json as _json
    import subprocess

    from test_cli_support import _console_script

    from labcairn.cli.workspace import application_context  # noqa: F401

    # **The command runs in its own process**, so this process's transaction
    # has to be committed before it starts -- otherwise the command waits on
    # a write lock this process holds.
    bare.context.store.session.commit()

    completed = subprocess.run(
        [
            str(_console_script()),
            "--workspace",
            str(bare.context.workspace.selected_root),
            "roles",
            "run",
            "--json",
            "--role",
            "trajectory",
            "--role",
            "guidance",
            "--project",
            bare.project_id,
            "--issue-key",
            KEY,
            "--version",
            bare.version_id,
            "--version",
            bare.second_version_id,
            "--provider",
            "fake",
            "--model",
            "scripted",
            "--root",
            MATERIAL_ROOT,
            "--resource-key",
            MATERIAL_KEY,
            "--material-ref",
            MATERIAL_PATH,
            "--purpose",
            "guidance_review",
            "--destination",
            DESTINATION,
            "--subject-ref",
            bare.project_id,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=_the_child_environment(),
    )
    assert completed.returncode == 0, f"the command refused: {completed.stderr}"
    run = _json.loads(completed.stdout)

    assert run["roles"] == ["trajectory", "guidance"], (
        "the roles the command named are the roles that ran"
    )
    assert run["abstentions"], "the command says what each role could not answer"
    assert run["shape"]["comment_count"] == 0, "and the shape says the document holds no comment"
    assert run["answer"] is None, "no model was asked, so there is no answer"
    assert run["exchange_event_id"] is None, "no model was called, so there is no exchange"
