"""The diagnostics package's de-identification witness.

**What is under test.** Work orders §12 §5.6 deliverable 2: the de-identified
diagnostics *"with a witness asserting what is collected and what is proven
absent from the package"*, as designed by
``docs/plans/LC-P3-07-diagnostics-design.md``.

Three rings, each named in the design's §4:

1. **The schema is the allowlist** — the package holds exactly the fields the
   design's §2.1 table names, and the JSON form carries exactly their names.
   A field that is not on the list has no representation.
2. **What is collected** — build identity, task id only, operation states,
   typed failures, counts, probe verdicts, credential *fingerprints*, output-
   area file facts, and event names with UTC moments.
3. **What is proven absent** — no material text (run-length checked against
   the caller's renderings), no credential value, no absolute path into a
   source root, no long Han run. A package whose verification fails is not
   produced at all.
"""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from store_support import env as _shared_env

env = _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.diagnostics import (
    DiagnosticsPackage,
    DiagnosticsRefusedError,
    collect_diagnostics,
    to_json_dict,
)
from labcairn.providers.deidentify import DeidentificationPipeline, SampleClass
from labcairn.providers.errors import FailureKind, ProviderFailure
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

MOMENT = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

#: Synthetic material. Its *renderings* are what the verification is run
#: against; the text itself must never appear in a package field.
MATERIAL = (
    "The green algae inhibition assay was repeated three times under identical "
    "lighting conditions and the results disagreed with the earlier published "
    "curve at every measured concentration point without exception."
)
SECRET = "sk-super-secret-diagnostics-key-0192837465"


@pytest.fixture()
def context(env: Any, tmp_path: Path) -> ApplicationContext:
    """A task under an allowing policy, with one material file bound."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    (materials / "manuscript.txt").write_text(MATERIAL, encoding="utf-8")
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="Diagnostics witness task",
        goal=TaskGoal(objective="Prove the package.", success_criterion="A clean package."),
        source_dirs=(materials,),
        now=MOMENT,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        ledger=ApprovalLedger(),
    )


# --- ring 1: the schema is the allowlist ------------------------------------


def test_the_package_holds_exactly_the_allowlisted_fields() -> None:
    """The dataclass's fields are the allowlist, spelled out.

    Adding a field is a deliberate act that edits this witness with it — the
    same closed-shape property ``RunRecord``'s frozen counts have.
    """
    names = {f.name for f in dataclass_fields(DiagnosticsPackage)}
    assert names == {
        "format_version",
        "created_at",
        "product_version",
        "schema_revision",
        "platform_name",
        "task_id",
        "operations",
        "failures",
        "refusals",
        "run_counts",
        "capability_verdicts",
        "credential_fingerprints",
        "files",
        "events",
    }


def test_the_json_form_carries_exactly_the_allowlisted_names(
    context: ApplicationContext,
) -> None:
    """The wire form's keys are the allowlist's names, and nothing else."""
    package = collect_diagnostics(context, material_texts=(MATERIAL,))
    rendered = to_json_dict(package)
    assert set(rendered) == {
        "format_version",
        "created_at",
        "product_version",
        "schema_revision",
        "platform",
        "task_id",
        "operations",
        "failures",
        "refusals",
        "run_counts",
        "capability_verdicts",
        "credential_fingerprints",
        "files",
        "events",
    }
    # Round-trips as JSON without loss of the field set.
    reparsed = json.loads(json.dumps(rendered))
    assert set(reparsed) == set(rendered)


# --- ring 2: what is collected ----------------------------------------------


def test_the_build_identity_and_task_id_are_collected(
    context: ApplicationContext,
) -> None:
    """Rows 1 and 2: build identity, and the task id only."""
    from labcairn import __version__

    package = collect_diagnostics(context, material_texts=(MATERIAL,), now=MOMENT)
    assert package.product_version == __version__
    assert package.task_id == str(context.task_id)
    assert package.format_version == 1
    assert package.created_at == MOMENT.isoformat()
    assert package.schema_revision is not None, (
        "the store is migrated, so the package names the revision it read"
    )
    # The task's *title* and *goal* are content; the package carries neither.
    rendered = json.dumps(to_json_dict(package))
    assert "Diagnostics witness task" not in rendered
    assert "Prove the package." not in rendered


def test_operations_and_events_are_collected_as_states_and_moments(
    context: ApplicationContext,
) -> None:
    """Rows 3 and 10: operation states and event names, never payloads."""
    package = collect_diagnostics(context, material_texts=(MATERIAL,))
    types = [event.type for event in package.events]
    assert "task_created" in types
    created = next(event for event in package.events if event.type == "task_created")
    assert created.seq >= 1
    assert created.occurred_at.endswith("+00:00")
    rendered = json.dumps(to_json_dict(package))
    # The material never rides along in an event or operation row.
    assert "algae" not in rendered


def test_provider_failures_embed_to_wire_unchanged(context: ApplicationContext) -> None:
    """Row 4: the package embeds ``ProviderFailure.to_wire``'s exact output."""
    failure = ProviderFailure.of(FailureKind.TIMEOUT, detail_digest="deadbeef")
    package = collect_diagnostics(
        context,
        material_texts=(MATERIAL,),
        failures=(failure,),
    )
    assert len(package.failures) == 1
    fact = package.failures[0]
    wire = failure.to_wire()
    assert fact.kind == wire["kind"]
    assert fact.retryable == wire["retryable"]
    assert fact.user_action == wire["user_action"]
    assert fact.detail_digest == wire["detail_digest"]
    assert fact.message == wire["message"]


def test_credential_fingerprints_are_collected_and_values_are_not(
    context: ApplicationContext,
) -> None:
    """Row 7: the fingerprint identifies the credential; the value is absent."""
    from labcairn.providers.credentials import Credential

    credential = Credential.of(SECRET, source="TEST_CREDENTIAL")
    package = collect_diagnostics(
        context,
        material_texts=(MATERIAL,),
        secrets=(SECRET,),
        credential_fingerprints=(credential.fingerprint,),
    )
    assert package.credential_fingerprints == (credential.fingerprint,)
    rendered = json.dumps(to_json_dict(package))
    assert SECRET not in rendered


# --- ring 3: what is proven absent ------------------------------------------


def test_a_refusal_message_carrying_a_material_run_is_refused(
    context: ApplicationContext,
) -> None:
    """A diagnosis text that quotes the paper inside an allowed field is
    refused at mint time — not blanked out, not shipped."""
    quoting = f"the operator saw: {MATERIAL[:120]}"
    with pytest.raises(DiagnosticsRefusedError) as raised:
        collect_diagnostics(
            context,
            material_texts=(MATERIAL,),
            refusals=(("path_refused", quoting),),
        )
    assert "8-word run" in str(raised.value)


def test_a_refusal_message_carrying_a_named_secret_is_refused(
    context: ApplicationContext,
) -> None:
    """The secret check runs over every rendered field."""
    with pytest.raises(DiagnosticsRefusedError) as raised:
        collect_diagnostics(
            context,
            material_texts=(MATERIAL,),
            secrets=(SECRET,),
            refusals=(("provider_auth", f"auth failed for {SECRET}"),),
        )
    assert "registered secret" in str(raised.value)


def test_a_long_han_run_in_any_field_is_refused(context: ApplicationContext) -> None:
    """The Han-run ceiling applies to the package's own fields too."""
    han_run = "实验结果与文献曲线不一致" * 3
    with pytest.raises(DiagnosticsRefusedError) as raised:
        collect_diagnostics(
            context,
            material_texts=(MATERIAL,),
            refusals=(("provider_transient", f"上游返回：{han_run}"),),
        )
    assert "Han run" in str(raised.value)


def test_material_text_appears_nowhere_in_a_clean_package(
    context: ApplicationContext,
) -> None:
    """The absence claim, verified against the caller's own rendering.

    The verification needs the material to prove its absence; the package it
    mints carries none of it, and this test re-checks the minted form
    independently of the mint-time refusal.
    """
    pipeline = DeidentificationPipeline()
    case = pipeline.redact_case(
        case_id="diagnostics-check",
        source_digest="0" * 64,
        material_text=MATERIAL,
        excerpts=(),
        rendered_prompt="Assay results diverged from a reference trace.",
        rendered_excerpts=(),
        sample_class=SampleClass.PUBLIC_SYNTHETIC,
    )
    package = collect_diagnostics(
        context,
        material_texts=(MATERIAL,),
        refusals=(("source_drifted", "the original moved after the grant"),),
    )
    rendered = json.dumps(to_json_dict(package))
    for word in MATERIAL.lower().split():
        if word in ("the", "and", "was", "at", "of", "a", "in", "to", "under"):
            continue  # function words are not the material's identity
        assert word not in rendered, f"the material's word {word!r} reached the package"
    # The de-identified rendering is allowed to echo (it is what the pipeline
    # minted), but the package carries no case text at all unless the caller
    # put it in a field.
    assert case.safe_prompt not in rendered


def test_file_facts_are_output_area_relative(env: Any, tmp_path: Path) -> None:
    """Row 9: no absolute path and no drive letter ever appears.

    The file facts are the ledger's artifact receipts, so the fixture runs a
    real loop to publication — a bare ``TaskOutputArea.write`` lands bytes but
    no receipt, and a receipt-less write is not a file fact.
    """
    from drill_support import build_rig, run_loop_to_publication

    rig = build_rig(env.store(), tmp_path / "workspace")
    run_loop_to_publication(rig)
    package = collect_diagnostics(rig.context, material_texts=(MATERIAL,))
    paths = [fact.relative_path for fact in package.files]
    assert len(paths) >= 1
    for path in paths:
        assert not Path(path).is_absolute()
        assert ":" not in path
    rendered = json.dumps(to_json_dict(package))
    assert str(rig.workspace_root) not in rendered
    assert rig.loop.import_receipt.receipt_id in " ".join(paths)


def test_run_counts_are_counts_only(context: ApplicationContext) -> None:
    """Row 5: the bounded-run record arrives as counts, never text."""
    from labcairn.providers.bounded_run import RunRecord, StopLossVerdict

    record = RunRecord(
        started_at=MOMENT,
        finished_at=MOMENT + timedelta(seconds=3),
        requests_made=2,
        requests_refused=1,
        requests_failed=0,
        cases_submitted=1,
        cases_completed=1,
        stop_loss=StopLossVerdict.HOLD,
    )
    package = collect_diagnostics(
        context, material_texts=(MATERIAL,), run_record=record
    )
    assert package.run_counts == {
        "requests_made": 2,
        "requests_refused": 1,
        "requests_failed": 0,
        "cases_submitted": 1,
        "cases_completed": 1,
    }
