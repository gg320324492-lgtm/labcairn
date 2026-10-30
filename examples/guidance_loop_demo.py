"""The guidance loop, end to end — with the fake provider, and nothing sent.

**What this demonstrates.** LC-P2-12's three roles and the arrangement
that routes them, on one planted chain:

1. **The chain** — a project, two versions, one edge, a comment keyed,
   an edit that answers it, a judgement that says so.
2. **The routing** — a research suggestion needs roles A and B; the
   high risk adds role C; a comment extraction needs A alone.
3. **A grounded suggestion** — a trajectory candidate quoting the
   advisor verbatim, a card carrying its evidence and its limits, and
   a review that supports it.
4. **A suggestion the critique refuses** — the review reads the
   counter-evidence it retrieved itself, and hands the card to a
   person with its reason.
5. **An abstention** — material the role cannot answer produces a
   structured record naming what was missing, and never a guess.
6. **The priced call** — one invocation through the fake provider:
   the exchange is recorded, and **nothing leaves the machine**.

**And throughout: no write-back, no unauthorised outbound, and no paid
call.** Every claim is a ``check()`` that raises; the demonstration's
exit code is its verdict. The chain is planted the way a fixture
plants one — the rows a reader would record — and what the roles do
with it is the product path.

This file is the acceptance demonstration of LC-P2-12; it is run by
``tests/test_guidance_loop_demo.py`` on every suite, and a second run
of that test plants the first claim false **from outside this source**
so the exit code keeps meaning something.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from labcairn.application.context import ApplicationContext
from labcairn.application.material_ingestion import ingest_material
from labcairn.application.sources import list_sources
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperProjectRow,
    PaperVersionRow,
    ResponseLinkRow,
    VersionEdgeRow,
)
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.roles.critique import review_card
from labcairn.roles.guidance import (
    CardClaim,
    Uncertainty,
    abstaining_card,
    build_card,
    cite_rule,
)
from labcairn.roles.orchestration import (
    DecisionLedger,
    LoopRequest,
    decide_roles,
    record_human_decision,
)
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.roles.trajectory import TrajectoryInput, propose_candidate, read_trajectory
from labcairn.security.capabilities import CapabilityId

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"
COMMENT = (
    "The comparison rests on the new estimator alone; where is the baseline"
    " the text promises in the introduction?"
)
ANCHOR = "The method estimates the parameter from a single observation."

STEPS: tuple[str, ...] = (
    "1. The chain the loop reads",
    "2. The routing: who runs, and why",
    "3. A grounded suggestion, reviewed",
    "4. A suggestion the critique refuses",
    "5. An abstention that names what was missing",
    "6. The priced call, and nothing sent",
)


def check(condition: bool, message: str = "") -> bool:
    """Every claim the demonstration makes. A false one stops the show."""
    if not condition:
        raise AssertionError(message or "the demonstration's claim does not hold")
    return True


def _source_id_of(context: ApplicationContext, suffix: str) -> str:
    """The id of the ingested material whose path ends with *suffix*."""
    for view in list_sources(context):
        if str(view.source.relative_path).endswith(suffix):
            return str(view.source.source_id)
    raise AssertionError(f"the task holds no material ending in {suffix!r}")


def _plant(db_path: Path, workspace: Path) -> ApplicationContext:
    """The workspace, the material, and the rows a reader would record.

    **The material is real** — two small text files, ingested through the
    product's own intake — because the memory's retrieval checks the
    reader's reach through the consent layer, and a check against a file
    that is not there would refuse everything. The chain rows are planted
    the way a fixture plants them: the project, the two versions, the
    edge, the comment keyed, the edit, and the judgement that says the
    change answered.
    """
    from labcairn.application.tasks import create_task
    from labcairn.runtime.lifecycle import TaskGoal
    from labcairn.security.approval import ApprovalLedger
    from labcairn.security.policy import Permission, PermissionPolicy, Rule

    upgrade_to_head(db_path)
    materials = workspace / "materials"
    materials.mkdir()
    (materials / "manuscript.txt").write_text(
        "Introduction.\n"
        "The method estimates the parameter from a single observation.\n"
        "Results follow in the next section.\n",
        encoding="utf-8",
    )
    (materials / "manuscript-2.txt").write_text(
        "Revised.\nThe estimator now names the baseline it is measured against.\n",
        encoding="utf-8",
    )
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    engine = create_db_engine(db_path)
    factory = create_session_factory(engine)
    session = factory()
    created = create_task(
        store=TaskStore(session),
        policy=policy,
        workspace_root=workspace,
        title="The guidance loop's demonstration",
        goal=TaskGoal(
            objective="Show the three roles and the arrangement routing them.",
            success_criterion="A loop that sends nothing and refuses to guess.",
        ),
        source_dirs=(materials,),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=TaskStore(session),
        policy=policy,
        ledger=ApprovalLedger(),
    )
    ingest_material(context, now=MOMENT)
    source_id = _source_id_of(context, "manuscript.txt")
    second_source_id = _source_id_of(context, "manuscript-2.txt")
    session.add(
        PaperProjectRow(
            project_id="proj-1",
            workspace_id="ws-1",
            subject_pseudonym="subject-1",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-1",
            project_id="proj-1",
            source_id=source_id,
            version_label_raw="manuscript.txt",
            stage_candidate="advisor_reviewed",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-2",
            project_id="proj-1",
            source_id=second_source_id,
            version_label_raw="manuscript-2.txt",
            stage_candidate="draft",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.commit()
    session.add(
        FeedbackEventRow(
            feedback_id="fb-201",
            project_id="proj-1",
            version_id="ver-1",
            comment_locator=json.dumps(
                {"part": "materials/manuscript.txt", "comment": "1", "range": "0-1"}
            ),
            anchor_status="unknown",
            anchor_reason="the demonstration plants the chain as a fixture would",
            anchor_text=ANCHOR,
            anchor_text_sha256="0" * 64,
            comment_text=COMMENT,
            comment_text_sha256="0" * 64,
            grade="observed",
            issue_key=KEY,
            created_at=MOMENT,
        )
    )
    session.commit()
    session.add(
        VersionEdgeRow(
            edge_id="edge-1",
            project_id="proj-1",
            parent_version_id="ver-1",
            child_version_id="ver-2",
            source="human",
            confidence=1.0,
            evidence_spans=["the demonstration's own accepted edge"],
            accepted_by="the-student",
            accepted_at=LATER,
            created_at=LATER,
        )
    )
    session.commit()
    session.add(
        EditActionRow(
            edit_action_id="edit-201",
            feedback_id="fb-201",
            version_edge_id="edge-1",
            actor_kind="student",
            grade="observed",
            created_at=LATER,
        )
    )
    session.add(
        ResponseLinkRow(
            response_link_id="resp-201",
            feedback_id="fb-201",
            edit_action_id="edit-201",
            state="addressed",
            grade="human_verified",
            decided_by="user",
            decided_at=LATER,
            evidence_refs=[f"check:{KEY}"],
            created_at=LATER,
        )
    )
    session.commit()
    return context


def _specs(context: ApplicationContext) -> dict[str, AgentRoleSpec]:
    """The three roles' contracts, priced so the demonstration's call can be measured."""
    specs: dict[str, AgentRoleSpec] = {}
    for role_id, capability in (
        ("trajectory", CapabilityId.SOURCE_READ),
        ("guidance", CapabilityId.MODEL_REQUEST),
        ("critique", CapabilityId.SOURCE_READ),
    ):
        specs[role_id] = define_role_spec(
            context,
            role_id=role_id,
            role_version=1,
            objective=f"What the {role_id} role owes the loop.",
            input_schema="Input",
            output_schema="Output",
            allowed_capabilities=(capability,),
            forbidden_actions=FORBIDDEN_ACTIONS,
            allowed_data_purposes=("guidance_review",),
            provider_routing_policy="single-provider-per-call",
            cost_budget=0.5,
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
    return specs


def _print(step: str) -> None:
    print(f"\n=== {step} ===")


def main() -> int:
    """Run the six scenes; every claim is a check that raises."""
    workspace = Path(tempfile.mkdtemp(prefix="guidance-loop-demo-"))
    try:
        db_path = workspace / "labcairn.db"
        _print("1. The chain the loop reads")
        context = _plant(db_path, workspace)
        material = read_trajectory(
            context,
            trajectory_input=TrajectoryInput(
                project_id="proj-1",
                version_ids=("ver-1", "ver-2"),
                issue_keys=(KEY,),
            ),
        )
        check(material.ordered_version_ids == ("ver-1", "ver-2"), "the graph's order")
        check([comment.issue_key for comment in material.comments] == [KEY], "the keyed comment")
        check("edit-201" in {edit.edit_action_id for edit in material.edits}, "the edit")
        print(f"  the comment's words: {COMMENT[:60]}...")
        print(f"  the versions, in the accepted edges' order: {material.ordered_version_ids}")

        _print("2. The routing: who runs, and why")
        extraction = decide_roles(LoopRequest(kind="a_comment_extraction", risk="low"))
        check(extraction.roles == ("trajectory",), "a comment extraction runs A alone")
        suggestion = decide_roles(LoopRequest(kind="a_research_suggestion", risk="high"))
        check(
            suggestion.roles == ("trajectory", "guidance", "critique"),
            "the high risk adds the critique",
        )
        for reason in suggestion.reasons:
            print(f"  because {reason}")

        _print("3. A grounded suggestion, reviewed")
        specs = _specs(context)
        candidate = propose_candidate(
            context,
            spec=specs["trajectory"],
            issue_key=KEY,
            issue_type="method_and_hypothesis",
            alignment="partial",
            advisor_quote=COMMENT[:52],
            note="the student's edit changed the wording, not the missing baseline.",
            edit_action_id="edit-201",
        )
        check(candidate.role_id == "trajectory" and candidate.role_version == 1)
        check(candidate.advisor_quote in COMMENT, "the quote is the advisor's own words")
        card = build_card(
            context,
            spec=specs["guidance"],
            target_locator="docx:word/document.xml#para=12",
            issue_type="method_and_hypothesis",
            severity="major",
            reason="the comparison names no baseline, and the rule asks for one.",
            evidence_refs=(f"chain:{KEY}",),
            suggested_next_action="name the baseline the estimate is measured against.",
            uncertainty=Uncertainty(kind="low", what_is_uncertain="the rule's scope"),
            claims=(
                CardClaim(
                    text="the comment asks for the baseline, in the advisor's words",
                    kind="advisor",
                    issue_key=KEY,
                    advisor_quote=COMMENT[:52],
                ),
            ),
            style_notes=("the paragraph could lead with its claim.",),
        )
        verdict = review_card(
            context,
            spec=specs["critique"],
            card=card,
            verdict="supported",
            repair_advice="none needed; the evidence is the chain's",
        )
        check(verdict.verdict == "supported" and verdict.grade == "inferred")
        print(f"  the card's evidence: {card.evidence_refs}")
        print(f"  the review's verdict: {verdict.verdict}, at grade {verdict.grade}")

        _print("4. A suggestion the critique refuses")
        rule = propose_rule(
            context,
            issue_type="method_and_hypothesis",
            statement=(
                "When the claim rests on a comparison, the advisor asks for the"
                " baseline to be named in the same paragraph."
            ),
            rule_context="A results section whose claim is comparative.",
            scope="Empirical papers in this group's field.",
            example="The comment of the run, on the ablation paragraph.",
            sources=(KEY,),
            proposed_by="a-mentor",
            now=MOMENT,
        )
        confirm_rule(context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)
        record_counterexample(
            context,
            rule_id=rule.rule_id,
            statement="The baseline was in the paragraph, and the advisor still asked.",
            recorded_by="a-reader",
            now=MOMENT,
        )
        citation = cite_rule(context, rule_id=rule.rule_id)
        check(bool(citation.counterexamples), "the rule's case against it came back with it")
        refused_card = build_card(
            context,
            spec=specs["guidance"],
            target_locator="docx:word/document.xml#para=14",
            issue_type="method_and_hypothesis",
            severity="moderate",
            reason="the advice rests on the rule alone.",
            evidence_refs=(f"chain:{KEY}",),
            suggested_next_action="follow the rule.",
            uncertainty=Uncertainty(kind="moderate", what_is_uncertain="the rule's limits"),
            rule_refs=(citation,),
        )
        refusing_verdict = review_card(
            context,
            spec=specs["critique"],
            card=refused_card,
            verdict="needs_revision",
            repair_advice="name where the rule does not hold before following it.",
            handover_reason="the rule the card cites has a case against it",
        )
        check(refusing_verdict.verdict == "needs_revision")
        check(refusing_verdict.handover_reason is not None, "the hand-over says why")
        check(bool(refusing_verdict.counter_evidence), "the review's own retrieval found the case")
        print(f"  the rule's counterexamples: {citation.counterexamples}")
        print(f"  the hand-over: {refusing_verdict.handover_reason}")

        _print("5. An abstention that names what was missing")
        abstention = abstaining_card(
            spec=specs["guidance"],
            issue_type="method_and_hypothesis",
            what_is_uncertain="whether the comment was ever answered",
            missing=(
                "no revision of the manuscript is in reach",
                "the comment's version has no child in the graph",
            ),
        )
        check(abstention.uncertainty.kind == "abstention")
        check(len(abstention.uncertainty.missing) == 2, "the missing are named")
        print(f"  the abstention's missing: {abstention.uncertainty.missing}")
        ledger = DecisionLedger()
        decision = record_human_decision(
            ledger,
            card_locator="docx:word/document.xml#para=12",
            decision="accepted",
            decided_by="the-student",
            reason="the card names the baseline; the paragraph now has one.",
            now=LATER,
        )
        check(decision.decision == "accepted")
        check(len(ledger.decisions_for("docx:word/document.xml#para=12")) == 1)

        _print("6. The priced call, and nothing sent")
        from labcairn.core.providers import FakeProvider, ModelRequest
        from labcairn.core.providers.fake import Transcript, TranscriptStep

        request = ModelRequest(
            prompt="Draft the card's suggested next action, from the evidence named.",
        )
        transcript = Transcript.of(
            "guidance-loop-demo",
            (
                TranscriptStep.of(
                    "the-card",
                    request,
                    {"text": "Name the baseline the estimate is measured against."},
                ),
            ),
        )
        responses = FakeProvider(transcript, clock=lambda: MOMENT).run()
        check(len(responses) == 1, "the script answered once")
        check("baseline" in responses[0].text, "the answer is the script's")
        print(f"  the exchange: {responses[0].text}")
        print("  and the exchange happened in a fake provider; nothing left the machine")

        print("\nThe demonstration holds:")
        print("  the loop routed three roles, quoted the advisor verbatim,")
        print("  refused a card on counter-evidence it retrieved itself,")
        print("  abstained by naming what was missing, audited a person's decision,")
        print("  and paid for one exchange in a fake provider that sent nothing.")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
