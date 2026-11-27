"""The mentor loop over a document with no comment, when the request names a rule.

**What is under test.** The comment-less run's record said, under *what is
still open*, that a run over a document with no comment **and a rule the card
would cite** was not exercised, and that *"the rule the request names is not
fetched"*. The measurement says the opposite: the question is built before
the comment-less branch is reached, so the rule **is** read -- and a rule the
memory does not serve refuses the whole request.

**So the path has two directions, and they are one experiment.** The same
document, the same request and the same plan, differing in one value: the
rule's id. A rule the memory serves is read, cited on the ticket, and the run
abstains over the document's missing comment. A rule the memory does not hold
is refused by name, before any consent is asked.

**And the answer is the one the product's promises support.** The refusals are
the roles' own, and ``cite_rule`` is the guidance role's read of the memory; a
loop that skipped it whenever the chain holds no comment would decide, on the
chain's state, a question the memory answers -- and a rule id that names
nothing would become indistinguishable from one the memory serves. The
comment-less promise is about the **chain's** state (*no comment at all* is a
shape of the material), and the rule's presence is the **memory's** state. The
two are facts about different stores, and they have different remedies: the
document cannot gain a comment from this request, while the rule's id can be
corrected or dropped.

**And the abstaining result carries no citation.** The product's citation is
*"a rule the card cites"*, minted for a card; a run over a document with no
comment produces no card, so it carries no citation. A result that carried one
would state a citation that no card makes. **The information is not lost**: the
ticket's question carries the citation, so the ask step already says which rule
was read and what its counterexamples are.

======================================================  =========================
     acceptance                                         witness
======================================================  =========================
the fixture's rule is one the memory serves             the memory cites the
                                                          rule the revision
                                                          case built
a served rule does not stop the comment-less answer     the run returns, and
                                                          every role named is in
                                                          it and abstains over
                                                          the missing comment
the ticket says which rule was read                     the question's
                                                          ``rule_citation``
                                                          names the rule and
                                                          carries its
                                                          counterexamples
an abstaining run carries no card that cites the rule   the result's card is
                                                          the role's abstention,
                                                          with no rule refs
a rule the memory does not hold refuses the request     the same request naming
                                                          a missing rule is
                                                          refused by name, and
                                                          the message names the
                                                          id
consent holds in both directions                        the served-rule run asks
                                                          no approval, reaches
                                                          no wire and writes no
                                                          exchange; the
                                                          missing-rule request
                                                          is refused before an
                                                          approval exists
the command answers both ways                           the command runs the
                                                          document with the
                                                          served rule, and
                                                          refuses the missing
                                                          one by name
======================================================  =========================

**What this does not test.** No model is asked: the comment-less run reaches no
wire by construction, and the fixture's rule is built from a tracked change, not
from a real call. The document's material is the project's own fixture, never
the pilot's.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from docx_fixtures import Revision
from feedback_chain_fixtures import MOMENT, ChainEnv, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.model_request import ModelInvocation
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.roles_run import (
    ModelCallPlan,
    RoleRunRequest,
    request_role_run,
    run_role_run,
)
from labcairn.db.repository import list_approvals
from labcairn.guidance.rules import confirm_rule, propose_rule
from labcairn.papers.revisions import record_revision_events
from labcairn.roles.guidance import cite_rule
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, define_role_spec
from labcairn.runtime.event import EventType
from labcairn.security.capabilities import CapabilityId

#: This file is the product's own rule path over the role chain, so it says
#: so: the same class as the file it sits beside, and the harness's check
#: reads this marker rather than the partition table.
pytestmark = pytest.mark.integration

env = _shared_env

#: The document's one paragraph. The revision inserts one word into it.
PARAGRAPH = "The method estimates the parameter roughly from a single observation."

#: The id the tracked change's author is recorded under. **A role label, not a
#: person's name** -- the file records a string a person typed, and this
#: fixture does not need any person.
REVIEWER = "reviewer-a"

#: **One tracked change and no comment at all** -- the third pilot's shape,
#: and the shape the comment-less run exists for.
REVISIONS = (
    Revision(
        kind="ins",
        text="carefully",
        author=REVIEWER,
        date="2026-03-02T09:30:00Z",
        element_id="101",
        paragraph=0,
        after_text="estimates",
    ),
)

#: The issue key the request names. **The chain holds no comment under it**,
#: and the chain holds no comment under any key.
KEY = "iss-bare"

#: The rule's id when the request names one the memory does not hold.
MISSING_RULE = "rule-nowhere"

EXPIRES = MOMENT.replace(year=2027)

DESTINATION = "api.model-provider.example"
MATERIAL_PATH = "materials/manuscript.docx"
MATERIAL_KEY = "manuscript.docx"
MATERIAL_ROOT = "source:0"

OBJECTIVES: dict[str, str] = {
    "trajectory": "Align the advisor's mark with the change that answered it.",
    "guidance": "Diagnose the comment and state the next action.",
    "critique": "Review the card against the evidence it was built from.",
}


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _spec(context: ApplicationContext, role_id: str) -> None:
    """One role's contract, with the capability the run exercises.

    **Written through the layer's own operation**, so the contract the loop
    reads is one a product wrote, not a row a test inserted.
    """
    define_role_spec(
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


@pytest.fixture()
def named(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A document with **one tracked change and no comment**, and a served rule.

    **The rule is learned from the document's own change.** A rule the memory
    serves must stand on material the chain holds: a revision source lives by
    the change's existence, and a comment source lives by a judgement that
    something answered it. The document has no comment to judge, so the
    source is the change -- the shape the distillation reads, and the shape
    the third pilot had.

    **And the workspace carries the files a surface command reads**, because
    the command runs in its own process and finds the workspace by name.

    The fixture returns the chain; :func:`_the_rule_id` is how a test gets
    the rule, so no test has to guess the id the product minted.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    chain = build_chain(
        env.store(),
        workspace_root,
        comments=(),
        paragraphs=(PARAGRAPH,),
        revisions=REVISIONS,
    )
    for role_id in ("trajectory", "guidance", "critique"):
        _spec(chain.context, role_id)
    _write_the_workspace(chain)
    _the_rule[0] = _build_the_rule(chain)
    return chain


#: The rule the fixture built, held here because the fixture writes it and a
#: test reads it. **A list, so the fixture fills it**; the tests never write
#: it.
_the_rule: list[str] = [""]


def _the_rule_id() -> str:
    """The id of the rule the fixture built and confirmed."""
    assert _the_rule[0], "the fixture built no rule"
    return _the_rule[0]


def _build_the_rule(chain: ChainEnv) -> str:
    """A rule learned from the document's tracked change, confirmed.

    **The source is the revision event's own id.** :func:`revision_source_key`
    says the key is the event's id -- the product mints it, and the chain
    holds the event under it -- so a rule naming that id names material the
    chain can show.

    **Two readers, as the memory requires.** ``propose_rule`` writes a
    candidate and ``confirm_rule`` is the second reader's act; a rule one
    person proposed and confirmed is not a rule the memory serves.
    """
    (recorded,) = record_revision_events(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )
    assert recorded.author == REVIEWER, "the fixture's change is the one the rule is learned from"
    rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement="Name how carefully the estimate was made where the wording hides it.",
        rule_context="A methods sentence that hides how careful the estimate was.",
        scope="Empirical papers in this group's field.",
        example="The reviewer's own insertion, on the methods paragraph.",
        sources=(recorded.revision_event_id,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    confirmed = confirm_rule(
        chain.context,
        rule_id=rule.rule_id,
        confirmed_by="the-advisor",
        now=MOMENT,
    )
    assert confirmed.state == "confirmed", "the second reader's act confirmed the rule"
    return rule.rule_id


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


def _request(chain: ChainEnv, *, roles: tuple[str, ...], rule_id: str | None) -> RoleRunRequest:
    """A request for the roles named, on the chain the fixture planted."""
    return RoleRunRequest(
        roles=roles,
        project_id=chain.project_id,
        issue_key=KEY,
        version_ids=(chain.version_id, chain.second_version_id),
        rule_id=rule_id,
    )


def _plan() -> ModelCallPlan:
    """What the model call would need, declaring the chain's material."""
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


def _the_child_environment() -> dict[str, str]:
    """The environment the command runs under, and why it is this one.

    **The width is set, because a pipe is not a terminal.** Rich asks the
    terminal how wide it is and wraps its output to fit, so a child whose
    stdout is a pipe renders at eighty columns unless it is told otherwise
    -- and a wrap that falls *inside* a phrase truncates it. ``COLUMNS`` is
    the same width the project's other CLI witnesses use.

    **The encoding is set** because the child's output encoding is otherwise
    the machine's locale encoding.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return environment


def _role_refusal_reason(call: object) -> RoleRefusal:
    """The role's refusal an expected error carries.

    **The application layer maps the role's vocabulary into its own**, so
    the reason that reaches the caller is the application's. The mapping is a
    bijection over the reasons the roles raise, so the role's own name is
    recovered from it -- and the assertion that the name is a role refusal at
    all is what fails loudly when the loop refuses for some other reason.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        call()  # type: ignore[operator]
    reason = caught.value.reason
    assert isinstance(reason, ApplicationRefusal), (
        f"expected an application refusal, saw {reason!r}"
    )
    assert reason.value.startswith("role_"), f"expected a role refusal, saw {reason.value!r}"
    return RoleRefusal(reason.value.removeprefix("role_"))


# --------------------------------------------------------------------------- #
# the premise: the memory serves the rule the document built
# --------------------------------------------------------------------------- #


def test_the_rule_the_document_built_is_one_the_memory_serves(named: ChainEnv) -> None:
    """The fixture's rule is a rule the product would cite, and it stands on
    the document's own change.

    **A test that failed because the fixture's rule was not served would not
    be a witness of the run's answer.** So the premise is measured first: the
    memory's own read returns the citation, with the counterexamples it
    carries.
    """
    citation = cite_rule(named.context, rule_id=_the_rule_id())

    assert citation.rule_id == _the_rule_id()
    assert citation.statement, "a citation carries the rule's statement"
    assert citation.counterexamples == (), (
        "the fixture recorded no counterexample for this rule, and the"
        " citation carries exactly the cases the memory holds"
    )


# --------------------------------------------------------------------------- #
# a served rule does not stop the comment-less answer
# --------------------------------------------------------------------------- #


def test_a_comment_less_run_that_names_a_served_rule_abstains(named: ChainEnv) -> None:
    """The same document, the same request, the same plan -- only the rule differs.

    **The comment-less run's promise is about the chain's state.** A document
    whose advisor wrote nothing is a shape the chain reports, and a rule the
    memory serves does not change that shape: every role the request named
    runs and abstains over the comment that is not there.
    """
    ticket = request_role_run(
        named.context,
        _request(named, roles=("trajectory", "guidance"), rule_id=_the_rule_id()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(named.context, ticket, grants=(), at=MOMENT)

    assert result.roles == ("trajectory", "guidance"), (
        "the roles the request named are the roles that ran"
    )
    assert set(result.abstentions) == {"trajectory", "guidance"}, (
        "every role that ran abstained, and every abstention is named"
    )
    assert result.shape is not None and result.shape.comment_count == 0, (
        "the document holds no comment, and the run says so as a count"
    )
    assert result.answer is None, "no model was asked, so there is no answer"


def test_the_abstention_names_the_comment_and_not_the_rule(named: ChainEnv) -> None:
    """The abstention says what the document lacks, not what the request left unused.

    **A role abstains about its material.** The material here is the comment
    the advisor did not write; the rule is not the role's material, and an
    abstention that named it would tell the reader the role lacked a rule --
    a different fact, and a false one.
    """
    ticket = request_role_run(
        named.context,
        _request(named, roles=("trajectory", "guidance"), rule_id=_the_rule_id()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(named.context, ticket, grants=(), at=MOMENT)

    assert "comment" in result.abstentions["trajectory"], (
        "role A's abstention names the comment it lacks"
    )
    for role_id, what_is_missing in result.abstentions.items():
        assert what_is_missing.strip(), f"the abstention of {role_id!r} names what it lacks"
        assert _the_rule_id() not in what_is_missing, (
            f"the abstention of {role_id!r} is about the document, not about the rule"
        )


# --------------------------------------------------------------------------- #
# the rule is read: the ticket says which one
# --------------------------------------------------------------------------- #


def test_the_ticket_names_the_rule_it_read(named: ChainEnv) -> None:
    """The rule is fetched, and the ask step already carries the citation.

    **This is the measurement the record's sentence got wrong.** The question
    is built before the run consults the chain's comment count, so a
    comment-less request that names a served rule is a ticket whose
    ``rule_citation`` names that rule -- with the counterexamples the memory
    holds. The run that follows says no card cites it; the ticket says the
    rule was read.
    """
    ticket = request_role_run(
        named.context,
        _request(named, roles=("trajectory",), rule_id=_the_rule_id()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )

    citation = ticket.question.rule_citation
    assert citation is not None, "the rule the request names was fetched"
    assert citation.rule_id == _the_rule_id()
    assert citation.statement, "the citation carries the rule's own statement"


def test_an_abstaining_run_carries_no_card_that_cites_the_rule(named: ChainEnv) -> None:
    """The citation belongs to a card, and this run's card is an abstention.

    **The product's citation is *a rule the card cites*.** A run over a
    document with no comment produces role B's abstaining card -- the card
    the role makes when it cannot answer -- and no citation is attached to a
    card that cites nothing. **A result that carried the citation anyway
    would state a citation no card makes.**
    """
    ticket = request_role_run(
        named.context,
        _request(named, roles=("trajectory", "guidance"), rule_id=_the_rule_id()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(named.context, ticket, grants=(), at=MOMENT)

    assert result.card is not None, "role B ran, and its output is the abstention"
    assert result.card.rule_refs == (), "the abstaining card cites no rule"
    assert result.candidate is None, "role A judged no comment, so there is no candidate"
    assert result.abstention is not None, "role A's abstention is its output"


# --------------------------------------------------------------------------- #
# a rule the memory does not hold refuses the request
# --------------------------------------------------------------------------- #


def test_a_rule_the_memory_does_not_hold_refuses_the_request(named: ChainEnv) -> None:
    """The same document and request, naming a rule that is not there.

    **The memory's answer about a rule does not depend on the chain's comment
    count.** The request names a rule nobody wrote; the product says so by
    name, at the ask step, and the caller can correct the id or drop it. The
    document is not a dead end: with a rule the memory serves, the same
    request abstains.
    """
    refused = _role_refusal_reason(
        lambda: request_role_run(
            named.context,
            _request(named, roles=("trajectory",), rule_id=MISSING_RULE),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )

    assert refused is RoleRefusal.RULE_NOT_IN_THE_MEMORY, (
        "a rule the memory does not hold is refused by the role's own reason"
    )


def test_the_refusal_names_the_rule_and_not_the_provider(named: ChainEnv) -> None:
    """The refusal is the rule's, and the id is in the message.

    **The caller learns which clause of the request was wrong.** A refusal
    for want of a provider would be a different fact -- and it is the refusal
    the comment-less run exists to avoid, so the test names the reason it
    must not be.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        request_role_run(
            named.context,
            _request(named, roles=("trajectory",), rule_id=MISSING_RULE),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ROLE_RULE_NOT_IN_THE_MEMORY
    assert caught.value.reason.value != ApplicationRefusal.ROLE_RUN_NO_PROVIDER_INVOCATION.value, (
        "the request was not refused for want of a provider"
    )
    assert MISSING_RULE in caught.value.detail, (
        "the message names the rule the memory does not hold"
    )


# --------------------------------------------------------------------------- #
# consent holds in both directions
# --------------------------------------------------------------------------- #


def test_a_served_rule_run_asks_no_approval_and_reaches_no_wire(named: ChainEnv) -> None:
    """A run that abstains spends nothing, rule or no rule.

    **The comment-less branch is reached before the provider is consulted**,
    so neither a provider's absence nor its presence changes the answer: the
    run returns with no approval, no call and no exchange.
    """
    sent: list[str] = []

    def the_send(prompt: str) -> ModelInvocation:
        sent.append(prompt)
        raise AssertionError("a comment-less run must not reach the wire")

    ticket = request_role_run(
        named.context,
        _request(named, roles=("trajectory", "guidance"), rule_id=_the_rule_id()),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is None, "there is no call to consent to, so no approval is asked for"
    assert list_approvals(named.context.store.session, named.context.task_id) == (), (
        "the store holds no approval for a run that will never spend one"
    )

    result = run_role_run(named.context, ticket, grants=(), at=MOMENT, send=the_send)

    assert sent == [], "no prompt left the run"
    assert result.exchange_event_id is None, "no exchange was recorded"
    assert result.abstentions, "the run abstained rather than refusing"


def test_a_missing_rule_refuses_before_any_consent_exists(named: ChainEnv) -> None:
    """The refusal comes at the ask step, so there is nothing to spend.

    **A refusal before the consent is asked leaves no approval behind** --
    there is no pending question a person has to answer about a run that
    cannot start, and no approval to consume.
    """
    with pytest.raises(ApplicationRefusedError):
        request_role_run(
            named.context,
            _request(named, roles=("trajectory",), rule_id=MISSING_RULE),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )

    assert list_approvals(named.context.store.session, named.context.task_id) == (), (
        "the refused request minted no approval"
    )


def test_the_refusal_is_recorded_in_the_log(named: ChainEnv) -> None:
    """A refusal the caller sees is a refusal the log holds.

    **The pilot measured this gap once already**: a refusal that reached only
    the exit code and the message left no trace, so the log could not say
    that anything was asked for. The request step records it before raising.
    """
    from labcairn.application.events import read_events

    with pytest.raises(ApplicationRefusedError):
        request_role_run(
            named.context,
            _request(named, roles=("trajectory",), rule_id=MISSING_RULE),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )

    page = read_events(named.context)
    recorded = [event for event in page.events if event.type is EventType.REFUSAL_RECORDED]
    assert recorded, "the refusal is in the task's log"
    assert any(MISSING_RULE in str(event.payload.get("message") or "") for event in recorded), (
        "the log names the rule the memory does not hold"
    )


# --------------------------------------------------------------------------- #
# the command, which is where the pilot found the gap
# --------------------------------------------------------------------------- #


def _run_the_command(chain: ChainEnv, *, rule_id: str) -> subprocess.CompletedProcess[str]:
    """``roles run`` over the fixture's document, naming one rule.

    **The command runs in its own process**, so this process's transaction
    has to be committed before it starts -- otherwise the command waits on a
    write lock this process holds.
    """
    from test_cli_support import _console_script

    chain.context.store.session.commit()

    return subprocess.run(
        [
            str(_console_script()),
            "--workspace",
            str(chain.context.workspace.selected_root),
            "roles",
            "run",
            "--json",
            "--role",
            "trajectory",
            "--role",
            "guidance",
            "--project",
            chain.project_id,
            "--issue-key",
            KEY,
            "--version",
            chain.version_id,
            "--version",
            chain.second_version_id,
            "--rule",
            rule_id,
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
            chain.project_id,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=_the_child_environment(),
    )


def test_the_command_runs_a_comment_less_document_that_names_a_served_rule(
    named: ChainEnv,
) -> None:
    """The command answers with the run, and the run carries the abstentions.

    **This is the pilot's route**: the operator's command over a document the
    advisor never wrote in, with the rule the workbench offered. It must
    answer with the run, not with a pending approval.
    """
    completed = _run_the_command(named, rule_id=_the_rule_id())
    assert completed.returncode == 0, f"the command refused: {completed.stderr}"
    run = json.loads(completed.stdout)

    assert run["roles"] == ["trajectory", "guidance"]
    assert run["abstentions"], "the command says what each role could not answer"
    assert run["shape"]["comment_count"] == 0
    assert run["answer"] is None
    assert run["exchange_event_id"] is None


def test_the_command_refuses_a_missing_rule_by_name(named: ChainEnv) -> None:
    """The operator sees the refusal, with the reason a script branches on.

    **A reason, not a phrase**: the JSON carries the layer's own reason, and
    the message names the rule the memory does not hold.
    """
    from labcairn.cli.commands import EXIT_REFUSED

    completed = _run_the_command(named, rule_id=MISSING_RULE)

    assert completed.returncode == EXIT_REFUSED, f"a refusal, not a crash: {completed.stderr}"
    refused = json.loads(completed.stdout)
    assert refused["reason"] == ApplicationRefusal.ROLE_RULE_NOT_IN_THE_MEMORY.value
    assert MISSING_RULE in refused["message"]
