"""The partition: which test file witnesses which protocol clause.

**What this table is.** The protocol names five mandatory automated gate
classes and describes each of them in prose — *"model/provider-independent
typed contracts, state transitions, permission resolution, path traversal/
symlinks, dataset locators, numerical extraction and report serialization"*
— and the repository's tests are not filed under those names. So somebody
has to say which file belongs to which class, and the answer has to be
**written down** rather than held in the head of whoever ran the suite.

**Why it is a table and not a marker.** The repository does declare
``unit``, ``integration`` and ``e2e`` markers, but only on 33 of the 102
test files, and the protocol's ``negative`` class has no marker at all. A
partition that read only the markers would leave 69 files unclassified, and
an unclassified file is a file whose tests never enter any denominator — the
hole this whole package exists to close.

**The two rules the partition follows.**

1. **Where a file declares a marker, the marker decides.** 33 files carry
   one of the three runnable markers, and the partition agrees with them;
   ``tests/test_evaluation_harness.py`` watches that it does. That check
   catches the failure this table is exposed to — a file classified into a
   class its own markers contradict.
2. **Where a file declares no marker, the classification is a judgement,
   and it is recorded here** with the protocol clause it checks, so a
   reviewer can argue with a specific entry instead of with the whole run.

**The clause is a second axis, and it is the one the protocol's metrics
use.** A file's *class* says which gate it belongs to; its *clause* says
which property of the protocol it checks. The two are not the same: the
report's revisions file is in the ``integration`` class because the
repository marks it so, and its clause is ``outdated-checkpoint`` because
that is the property it checks. The protocol's metrics are filed under
clauses, which is why the two axes are kept apart.

**What is not in the protocol's five classes.** The ``repository`` class
holds the repository's own gates — the shard list, the README's accuracy,
the reference-exclusion check, the repo-root guard, the status board, the
suite's temp isolation, the packaging smoke. They are real tests and they
are run, and they are reported — but they are **not** one of the protocol's
five mandatory gate classes, and the report says so rather than counting
them into a class the protocol did not name.
"""

from __future__ import annotations

from typing import Final

from .protocol import GateClass

#: The class the repository's own gates live in. It is **not** one of the
#: protocol's five, and the report says so wherever it appears.
REPOSITORY_CLASS: Final = "repository"

#: The class the repository's own gates are reported under.
#:
#: Its definition is the harness's own, and it says what it is: **not** one
#: of the protocol's five mandatory gate classes. The report prints this
#: definition next to the protocol's, so a reader can see which rows the
#: protocol asked for and which the repository asked for on its own.
REPOSITORY_GATE_CLASS: Final = GateClass(
    key=REPOSITORY_CLASS,
    label="Repository gates",
    definition=(
        "the repository's own gates — the shard list, the README's accuracy, "
        "the reference-exclusion check, the repo-root guard, the status board, "
        "the suite's temp isolation and the packaging smoke. They are run and "
        "reported, and they are not one of the protocol's five mandatory "
        "gate classes, so they are counted apart from them."
    ),
    runnable_offline=True,
    offline_reason="",
)

#: The protocol's gate classes, in the protocol's order. The harness reads
#: the labels and the definitions out of ``docs/EVALUATION.md``; this tuple
#: is the set of keys it expects to find there.
PROTOCOL_CLASS_KEYS: Final[tuple[str, ...]] = (
    "unit",
    "integration",
    "negative",
    "e2e",
    "real_model_smoke",
)

#: Every class the harness knows, including the one the protocol does not
#: name.
ALL_CLASS_KEYS: Final[tuple[str, ...]] = (*PROTOCOL_CLASS_KEYS, REPOSITORY_CLASS)

#: The classes the harness runs by default, and the one it does not.
#:
#: The real-model smoke class is **not** run by default, for the reason the
#: protocol itself gives: it needs *"at least one real supported provider
#: under declared model/version/parameters"*, and it spends money. The
#: harness reports it as not run, with the reason, rather than reporting it
#: as a pass.
OFFLINE_CLASSES: Final[dict[str, tuple[bool, str]]] = {
    "unit": (True, ""),
    "integration": (True, ""),
    "negative": (True, ""),
    "e2e": (True, ""),
    "real_model_smoke": (
        False,
        "the protocol requires at least one real supported provider under a "
        "declared model, version and parameter set, and to record its cost; "
        "no real provider credential is configured in this environment, and "
        "the run would spend money. A mock-only success is insufficient "
        "under the protocol, so this class is reported as NOT RUN and is "
        "not counted as a pass.",
    ),
    REPOSITORY_CLASS: (True, ""),
}

#: The protocol's own phrases, used as the clause vocabulary. Each clause
#: names the part of the protocol it comes from.
CLAUSES: Final[dict[str, str]] = {
    # The unit class.
    "typed-contracts": "model/provider-independent typed contracts",
    "state-transitions": "state transitions",
    "permission-resolution": "permission resolution",
    "path-traversal": "path traversal/symlinks",
    "dataset-locators": "dataset locators",
    "numeric-extraction": "numerical extraction",
    "report-serialization": "report serialization",
    # The integration class.
    "migrations": "SQLite migrations",
    "event-append": "transactional event append",
    "restart-recovery": "restart recovery",
    "approvals": "approvals",
    "artifact-hashes": "artifact hashes",
    "api-auth": "local API auth",
    "provider-redaction": "provider redaction",
    # The negative class.
    "fabricated-citation": "fabricated citation",
    "missing-material": "missing material",
    "conflicting-values": "conflicting numeric values/units",
    "insufficient-evidence": "insufficient evidence",
    "outdated-checkpoint": "outdated checkpoint",
    "crash-between-write-and-confirm": (
        "simulated crash between file change and operation confirmation"
    ),
    "untrusted-instructions": "untrusted document instructions",
    # The end-to-end class.
    "fresh-install": "fresh install",
    "cli-task": "CLI task",
    "web-task": "local Web task",
    "resume-and-revise": "resume and revise",
    "export": "Markdown and DOCX/PDF export",
    "source-click-through": "source click-through",
    # The real-model smoke class.
    "real-provider": "at least one real supported provider",
    # The repository's own gates, outside the protocol's five.
    "repository-gate": "the repository's own gates, outside the protocol's five",
}

#: The partition itself: test file name -> (gate class, protocol clause).
#:
#: Every file in ``tests/`` that matches ``test_*.py`` appears here exactly
#: once. ``tests/test_evaluation_harness.py`` watches that it does, so a
#: new test file cannot arrive without being filed — and a file that is not
#: filed is a file whose tests enter no denominator, which is the hole this
#: package exists to close.
FILE_ASSIGNMENTS: Final[dict[str, tuple[str, str]]] = {
    # -- the analysis layer ------------------------------------------------
    "test_analysis_catalog.py": ("unit", "typed-contracts"),
    "test_analysis_demo.py": ("integration", "artifact-hashes"),
    "test_analysis_dependency.py": ("unit", "report-serialization"),
    "test_analysis_descriptive.py": ("unit", "numeric-extraction"),
    "test_analysis_fixtures.py": ("unit", "numeric-extraction"),
    "test_analysis_grouped.py": ("unit", "numeric-extraction"),
    "test_analysis_manifest.py": ("unit", "report-serialization"),
    "test_analysis_operator_contract.py": ("unit", "typed-contracts"),
    "test_analysis_recipe.py": ("unit", "report-serialization"),
    "test_analysis_render.py": ("unit", "report-serialization"),
    "test_analysis_report_build.py": ("unit", "report-serialization"),
    "test_analysis_report_checks.py": ("integration", "conflicting-values"),
    "test_analysis_report_manifest.py": ("unit", "report-serialization"),
    "test_analysis_report_model.py": ("integration", "typed-contracts"),
    "test_analysis_report_render.py": ("integration", "report-serialization"),
    "test_analysis_report_revisions.py": ("integration", "outdated-checkpoint"),
    "test_analysis_selection.py": ("unit", "numeric-extraction"),
    "test_analysis_service.py": ("unit", "artifact-hashes"),
    # -- the application surfaces ----------------------------------------
    "test_capability_namespaces.py": ("unit", "typed-contracts"),
    "test_api.py": ("integration", "api-auth"),
    "test_api_concurrency.py": ("integration", "event-append"),
    "test_application_approvals.py": ("integration", "approvals"),
    "test_application_ingestion.py": ("integration", "dataset-locators"),
    "test_application_layer.py": ("integration", "approvals"),
    "test_cli.py": ("e2e", "cli-task"),
    "test_cli_path_refused_catch.py": ("negative", "path-traversal"),
    "test_cli_refusal_enumeration.py": ("negative", "missing-material"),
    "test_cli_serve_bind_refusal.py": ("negative", "path-traversal"),
    "test_cli_workspace_refusals.py": ("negative", "path-traversal"),
    "test_developer_launch.py": ("integration", "fresh-install"),
    "test_earlier_exit_demos.py": ("integration", "fresh-install"),
    "test_service_launch.py": ("integration", "api-auth"),
    # -- the evidence path -------------------------------------------------
    "test_cite_c1.py": ("negative", "fabricated-citation"),
    "test_cite_c2.py": ("negative", "fabricated-citation"),
    "test_cite_c3.py": ("negative", "conflicting-values"),
    "test_evidence_anchor_registry.py": ("unit", "dataset-locators"),
    "test_evidence_contracts.py": ("unit", "typed-contracts"),
    "test_evidence_gate.py": ("negative", "insufficient-evidence"),
    "test_evidence_index.py": ("integration", "dataset-locators"),
    "test_evidence_normalize.py": ("unit", "dataset-locators"),
    "test_evidence_retrieval.py": ("negative", "insufficient-evidence"),
    "test_evidence_schema.py": ("integration", "migrations"),
    "test_evidence_store.py": ("integration", "event-append"),
    "test_paper_fixtures.py": ("unit", "dataset-locators"),
    "test_retrieval_ground_truth.py": ("negative", "fabricated-citation"),
    # -- the fake provider --------------------------------------------------
    "test_fake_provider_determinism.py": ("unit", "typed-contracts"),
    "test_fake_provider_invariants.py": ("negative", "insufficient-evidence"),
    "test_fake_provider_isolation.py": ("unit", "typed-contracts"),
    "test_fake_provider_usage.py": ("unit", "typed-contracts"),
    "test_fake_provider_usage_transcripts.py": ("unit", "typed-contracts"),
    # -- material -----------------------------------------------------------
    "test_material_adapters.py": ("unit", "typed-contracts"),
    "test_material_addressing.py": ("unit", "dataset-locators"),
    "test_material_indexing.py": ("integration", "dataset-locators"),
    "test_material_ingest.py": ("integration", "dataset-locators"),
    "test_material_pdf.py": ("unit", "dataset-locators"),
    "test_material_regressions.py": ("negative", "conflicting-values"),
    "test_material_schema.py": ("integration", "migrations"),
    "test_material_walk.py": ("unit", "permission-resolution"),
    "test_material_walk_paths.py": ("unit", "dataset-locators"),
    # -- providers ----------------------------------------------------------
    "test_provider_adapter.py": ("unit", "typed-contracts"),
    "test_provider_budget.py": ("unit", "typed-contracts"),
    "test_provider_capabilities.py": ("unit", "typed-contracts"),
    "test_provider_credentials.py": ("unit", "typed-contracts"),
    "test_provider_redaction.py": ("unit", "provider-redaction"),
    # -- recovery -----------------------------------------------------------
    "test_recovery_approvals.py": ("integration", "approvals"),
    "test_recovery_crash_matrix.py": ("negative", "crash-between-write-and-confirm"),
    "test_recovery_resume.py": ("integration", "restart-recovery"),
    "test_recovery_stage_bridge.py": ("unit", "typed-contracts"),
    "test_recovery_support.py": ("integration", "restart-recovery"),
    # -- security -----------------------------------------------------------
    "test_security_approval.py": ("integration", "approvals"),
    "test_security_injection.py": ("negative", "untrusted-instructions"),
    "test_security_listing_canonical.py": ("negative", "untrusted-instructions"),
    "test_security_paths.py": ("negative", "path-traversal"),
    "test_security_policy.py": ("unit", "permission-resolution"),
    "test_workspace_boundaries.py": ("negative", "path-traversal"),
    # -- the skills ---------------------------------------------------------
    "test_skill_approval.py": ("unit", "approvals"),
    "test_skill_contracts.py": ("unit", "typed-contracts"),
    "test_skill_execution.py": ("unit", "state-transitions"),
    "test_skill_ledger.py": ("unit", "artifact-hashes"),
    "test_skill_plan.py": ("unit", "typed-contracts"),
    "test_skill_quality.py": ("unit", "report-serialization"),
    "test_skill_support.py": ("unit", "report-serialization"),
    # -- the runtime and the store ------------------------------------------
    "test_id_aliases_are_nominal.py": ("unit", "typed-contracts"),
    "test_runtime_contracts.py": ("unit", "typed-contracts"),
    "test_source_contracts.py": ("unit", "typed-contracts"),
    "test_source_id_type.py": ("unit", "typed-contracts"),
    "test_store_atomicity.py": ("negative", "crash-between-write-and-confirm"),
    "test_store_concurrency.py": ("integration", "event-append"),
    "test_store_events.py": ("integration", "event-append"),
    "test_store_migrations.py": ("integration", "migrations"),
    "test_store_persistence.py": ("integration", "restart-recovery"),
    "test_store_queries.py": ("integration", "event-append"),
    "test_store_support.py": ("integration", "event-append"),
    # -- the smoke path and the repository's own gates ----------------------
    "test_refusal_witnesses.py": ("negative", "insufficient-evidence"),
    "test_smoke_path.py": ("e2e", "fresh-install"),
    "test_ci_shard_coverage.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_no_reference_leakage.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_parallel_temp_isolation.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_readme_accuracy.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_repo_root_guard.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_scaffolding.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_status_consistency.py": (REPOSITORY_CLASS, "repository-gate"),
    # -- this harness --------------------------------------------------------
    "test_evaluation_harness.py": (REPOSITORY_CLASS, "repository-gate"),
}

#: The witnesses of each protocol metric: the test files that check the
#: property the metric names.
#:
#: A metric's witnesses are **not** the metric's value. They are the
#: evidence that the property is watched at all; the value is what the
#: protocol asks for, and where this run cannot produce it, the report says
#: NOT MEASURED and says why.
METRIC_WITNESSES: Final[dict[str, tuple[str, ...]]] = {
    "end-to-end-task-success": (
        "test_smoke_path.py",
        "test_analysis_demo.py",
        "test_cli.py",
        "test_service_launch.py",
        "test_earlier_exit_demos.py",
    ),
    "evidence-locator-validity": (
        "test_cite_c1.py",
        "test_cite_c2.py",
        "test_cite_c3.py",
        "test_evidence_anchor_registry.py",
    ),
    "numeric-extraction-exactness": (
        "test_analysis_fixtures.py",
        "test_analysis_selection.py",
        "test_analysis_descriptive.py",
        "test_analysis_grouped.py",
        "test_cite_c3.py",
    ),
    "unsupported-claim-detection": (
        "test_evidence_gate.py",
        "test_refusal_witnesses.py",
        "test_skill_quality.py",
        "test_fake_provider_invariants.py",
    ),
    "revision-consistency": (
        "test_analysis_report_revisions.py",
        "test_analysis_report_checks.py",
        "test_analysis_report_manifest.py",
        "test_recovery_resume.py",
    ),
    "recovery-correctness": (
        "test_recovery_crash_matrix.py",
        "test_store_atomicity.py",
        "test_recovery_resume.py",
        "test_recovery_approvals.py",
    ),
    "latency-usage-cost": (
        "test_fake_provider_usage.py",
        "test_fake_provider_usage_transcripts.py",
        "test_provider_budget.py",
    ),
}

#: How each protocol metric's text is recognised. The key is a lowercased
#: prefix of the metric's wording; the longest matching prefix wins.
METRIC_PREFIXES: Final[dict[str, str]] = {
    "end-to-end task success": "end-to-end-task-success",
    "evidence locator validity": "evidence-locator-validity",
    "numeric-cell extraction exactness": "numeric-extraction-exactness",
    "unsupported-claim detection": "unsupported-claim-detection",
    "revision consistency": "revision-consistency",
    "recovery correctness": "recovery-correctness",
    "latency, model usage/cost": "latency-usage-cost",
}

#: The witnesses of each Phase 1 blocker: the test files that check the
#: property the blocker names.
#:
#: **A skip in a witness is a failed blocker**, not a neutral one. The
#: protocol's sixth blocker says the required tests must not be *"skipped,
#: ignored or only pass by mocking the actual behavior under acceptance"*,
#: and a witness that did not run is a witness that did not hold.
BLOCKER_WITNESSES: Final[dict[str, tuple[str, ...]]] = {
    "clean-environment-readme": (
        "test_developer_launch.py",
        "test_smoke_path.py",
        "test_readme_accuracy.py",
        "test_earlier_exit_demos.py",
    ),
    "no-unauthorized-write-or-disclosure": (
        "test_workspace_boundaries.py",
        "test_security_paths.py",
        "test_material_walk.py",
        "test_provider_redaction.py",
    ),
    "no-fake-citation-or-unsupported-number": (
        "test_cite_c1.py",
        "test_cite_c2.py",
        "test_cite_c3.py",
        "test_evidence_gate.py",
    ),
    "no-repeated-side-effect-after-crash": (
        "test_recovery_crash_matrix.py",
        "test_store_atomicity.py",
        "test_recovery_resume.py",
    ),
    "no-verified-claim-from-rendering-checks": (
        "test_analysis_report_checks.py",
        "test_analysis_report_manifest.py",
        "test_evidence_gate.py",
    ),
    "no-skipped-required-tests": (
        "test_ci_shard_coverage.py",
        "test_fake_provider_isolation.py",
        "test_refusal_witnesses.py",
    ),
}

#: How each blocker's text is recognised.
BLOCKER_PREFIXES: Final[dict[str, str]] = {
    "new user cannot complete a task": "clean-environment-readme",
    "any unauthorized file write": "no-unauthorized-write-or-disclosure",
    "fake citation presented as verified": "no-fake-citation-or-unsupported-number",
    "a crash silently repeats unknown file side effects": ("no-repeated-side-effect-after-crash"),
    "report claims a verified scientific result": "no-verified-claim-from-rendering-checks",
    "required ci tests are skipped": "no-skipped-required-tests",
}

#: The file that carries the real-model smoke once it exists. LC-P1-13 T04
#: owns it; until it lands, the class has no witness and the report says
#: that, next to the reason the class was not run.
REAL_MODEL_SMOKE_FILE: Final = "test_real_provider_smoke.py"


def files_for_class(class_key: str) -> tuple[str, ...]:
    """Every test file filed under this class, in name order."""
    return tuple(
        sorted(
            name for name, (assigned, _clause) in FILE_ASSIGNMENTS.items() if assigned == class_key
        )
    )


def paths_for_class(class_key: str) -> tuple[str, ...]:
    """The class's files, as paths pytest can find.

    The shards name paths relative to the repository root rather than bare
    file names, and for the same reason: pytest resolves an argument
    against the working directory, and a bare name is not a path it can
    find. A shard that named bare names would collect nothing and would
    look like it had passed.
    """
    return tuple(f"tests/{name}" for name in files_for_class(class_key))


def clause_for_file(name: str) -> str | None:
    """The protocol clause a file checks, or ``None`` if it is not filed."""
    entry = FILE_ASSIGNMENTS.get(name)
    return None if entry is None else entry[1]


def class_for_file(name: str) -> str | None:
    """The gate class a file is filed under, or ``None`` if it is not."""
    entry = FILE_ASSIGNMENTS.get(name)
    return None if entry is None else entry[0]
