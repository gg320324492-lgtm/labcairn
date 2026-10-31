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
    # LC-P2-02. The two facts the approval row now carries, and the spend
    # that reads them there rather than trusting an argument. Integration,
    # because the property is a row and a conditional UPDATE; the clause is
    # the approval clause, which is the same one the file above carries.
    "test_approval_binding.py": ("integration", "approvals"),
    # LC-P2-02's crash matrix: a child interpreter grants (and spends) and
    # dies, and the parent reads the row. Integration because the witness is
    # two processes and one database file.
    "test_approval_crash_matrix.py": ("integration", "approvals"),
    "test_application_evidence.py": ("integration", "dataset-locators"),
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
    "test_event_payload_vocabulary.py": ("integration", "event-append"),
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
    # LC-P2-06. The consent machinery: the grant table's schema, the
    # permission check that answers whether a use is permitted, the two
    # gates that stand between a request and a transmission, the
    # withdrawal that reaches the copies derived from it, the intake
    # guards that refuse an archive before it is opened, and the exit
    # demonstration that runs all of it.
    "test_access_grant_schema.py": ("integration", "migrations"),
    "test_consent_demo.py": ("integration", "approvals"),
    "test_consent_refusal_vocabulary.py": ("unit", "typed-contracts"),
    "test_consent_two_gates.py": ("integration", "approvals"),
    "test_consent_withdrawal.py": ("integration", "approvals"),
    "test_dataset_consent.py": ("unit", "permission-resolution"),
    "test_intake_guards.py": ("negative", "path-traversal"),
    # LC-P2-07. The OOXML reader's addresses: a package part, an element
    # path, a view and a character range. The protocol's locator clause is
    # the one it exercises.
    "test_ooxml_revisions.py": ("unit", "dataset-locators"),
    # LC-P2-08. The version graph: the schema's refusals, the contracts,
    # the alignment's evidence and its refusal to decide, the human
    # confirmation path, the duplicate and missing-round checks, and the
    # exit demonstration. The clause is the locator clause: these tests
    # are about where a version sits and what addresses it.
    "test_paper_version_graph.py": ("unit", "dataset-locators"),
    "test_paper_version_demo.py": ("unit", "dataset-locators"),
    "test_version_alignment.py": ("unit", "dataset-locators"),
    "test_version_confirmation.py": ("unit", "dataset-locators"),
    "test_version_contracts.py": ("unit", "typed-contracts"),
    "test_version_duplicates.py": ("unit", "dataset-locators"),
    # LC-P2-09. The version graph's *writer*: the store that keeps the
    # projects, versions and edges the contracts describe. The class is
    # integration because the property is exercised against a real database
    # rather than against the models alone, and the clause is the typed
    # contracts because the property is that a stored row round-trips through
    # the frozen models — that a row the contract refuses is neither written
    # nor readable as a valid one. The sibling files above check *where a
    # version sits* in the graph; this one checks that what is stored is the
    # model and not the row.
    "test_version_store.py": ("integration", "typed-contracts"),
    # LC-P2-09. The feedback chain. ``test_feedback_events.py`` carries the
    # row's two addresses and the anchored text -- the locator clause, and
    # the place the DOCX reader's own change is witnessed.
    # ``test_edit_actions.py`` carries the actor kind's closed vocabulary:
    # who made a change is a typed contract, and a model's change is not
    # the advisor's. ``test_response_links.py`` carries the state machine:
    # four states, and the rules about reaching them.
    # ``test_followup_assessments.py`` carries the evidence an assessment
    # needs of its own, and the recurrence an issue key makes visible.
    "test_feedback_events.py": ("integration", "dataset-locators"),
    "test_edit_actions.py": ("integration", "typed-contracts"),
    "test_response_links.py": ("integration", "state-transitions"),
    "test_followup_assessments.py": ("integration", "insufficient-evidence"),
    # LC-P2-09. The feedback chain's four events: they are annotations, they
    # carry a registered payload schema naming the row they are about, and
    # the chain is replayable from the stream alone. The clause is the event
    # append clause: the witnesses write through the unit of work and read
    # back through the store's event reader.
    "test_feedback_event_stream.py": ("integration", "event-append"),
    # LC-P2-09's exit demonstration: the chain run end to end, and the
    # witness that its exit code still carries its claims. It is integration
    # because it writes a real database and a real workspace, and its clause
    # is the event append because the last thing it checks is that the four
    # annotation events are in the stream in the order they were written.
    "test_feedback_demo.py": ("integration", "event-append"),
    # -- LC-P2-10: the annotation gold set --------------------------------
    # The label set: a closed vocabulary that a label outside it cannot
    # enter, and the chain's own words for two of its three axes. Its clause
    # is the typed contracts, because the set is a type and the refusal is
    # part of the type's contract.
    "test_gold_set_labels.py": ("unit", "typed-contracts"),
    # The agreement: a number computed from the manifest over a denominator
    # it names. Its clause is numeric extraction, because the number is
    # taken out of the manifest rather than written into it.
    "test_gold_set_agreement.py": ("unit", "numeric-extraction"),
    # The manifest's own rules: two independent readings and an arbiter's
    # resolution for every item, a resolution that does not overwrite the
    # disagreement, and a split by project. Its clause is insufficient
    # evidence, because an item with one reading, or with no arbiter, is an
    # item whose evidence is short.
    "test_gold_set_manifest.py": ("unit", "insufficient-evidence"),
    # The corpus and the manifest that names it: every item names a comment
    # the corpus has, the corpus section records the bytes that are written,
    # the archives carry no clock, the feedback ids are the chain's own, and
    # the annotations are all or nothing. Its clause is the dataset
    # locators, because the property is that the gold set's rows address the
    # material they name -- and that the two do not drift apart.
    "test_gold_set_corpus.py": ("unit", "dataset-locators"),
    # -- LC-P2-11: the mentor guidance memory --------------------------------
    # The guidance rules: the closed state machine, the second-reader rule,
    # and the schema that refuses what the API refuses. Its clause is the
    # state transitions, because the property is that a rule's state moves
    # only along the machine.
    "test_guidance_rules.py": ("integration", "state-transitions"),
    # The distillation: a scope assembled from the cases, a rule that may
    # not invent one, and a proposal that stays a candidate until a person
    # says so. Its clause is insufficient evidence, because the refusal is
    # about a rule the cases do not support.
    "test_guidance_distillation.py": ("integration", "insufficient-evidence"),
    # The retrieval: a source that stands or falls by its state, the
    # reader's consent, and a hit that carries its source and its
    # conditions. Its clause is the dataset locators, because the property
    # is that a returned rule addresses the material it names.
    "test_guidance_retrieval.py": ("integration", "dataset-locators"),
    # The memory's own demonstration: the rule with its source and its
    # counterexample, the conflict beside it, the source withdrawn from
    # under a rule, and the candidate nobody has confirmed. Its clause is
    # the state transitions, because the claims are the machine's moves.
    "test_guidance_memory_demo.py": ("integration", "state-transitions"),
    # -- LC-P2-12: the three-role guidance loop ------------------------------
    # A role's contract as a versioned row, the five forbidden actions, and
    # the schema that refuses an empty field. Its clause is the typed
    # contracts, because the contract is a type and the refusal is part of
    # that type's contract.
    "test_agent_role_specs.py": ("integration", "typed-contracts"),
    # Role A's candidates: judgements and never facts, the advisor's words
    # verified verbatim, the version order walked over accepted edges. Its
    # clause is the dataset locators, because a candidate must address the
    # chain it claims to speak for.
    "test_role_trajectory.py": ("integration", "dataset-locators"),
    # Role B's card: evidence required, a rule cited with its
    # counter-examples, and an abstention that names what was missing. Its
    # clause is the insufficient evidence, because the card is refused when
    # the evidence is short.
    "test_role_guidance.py": ("integration", "insufficient-evidence"),
    # Role C's critique: every verdict inferred, no store row written, and
    # the counter-evidence retrieved by C itself. Its clause is the
    # insufficient evidence, because the verdict says what the evidence
    # supports and no more.
    "test_role_critique.py": ("integration", "insufficient-evidence"),
    # The routing as data, the cost ceiling that fails closed, and the
    # ledger of human decisions. Its clause is the approvals, because a
    # decision a person made is what the ledger audits.
    "test_role_orchestration.py": ("integration", "approvals"),
    # The loop's own demonstration: the chain, the card, the critique, and
    # the priced call that sends nothing. Its clause is the event append,
    # because the last thing it checks is the events the run wrote.
    "test_guidance_loop_demo.py": ("integration", "event-append"),
    # -- LC-P2-16: the workbench for the guidance line ----------------------
    # The loop, on demand: the roles a request names and only those, the
    # two-step action that asks before it spends, and the roles' own
    # refusals reached through the loop. Its clause is the approvals,
    # because the property at the centre of it is that asking writes the
    # question down and spends nothing, and the run spends once.
    "test_roles_run.py": ("integration", "approvals"),
    # -- LC-P2-01: the model-call path ---------------------------------------
    # The path: the two gates in their order, the budget's preflight, the
    # schema a request is refused without, and the answer that is judged
    # rather than accepted. Its clause is the approvals, because the
    # approval is spent exactly once and only after every gate permitted.
    "test_model_request_path.py": ("integration", "approvals"),
    # The demonstration: consented, budgeted, recorded, and refused before a
    # socket exists. Its clause is the provider redaction, because what it
    # checks about the record is that no key and no text can be in it.
    "test_model_request_demo.py": ("integration", "provider-redaction"),
    # -- providers ----------------------------------------------------------
    "test_provider_adapter.py": ("unit", "typed-contracts"),
    "test_provider_budget.py": ("unit", "typed-contracts"),
    "test_provider_capabilities.py": ("unit", "typed-contracts"),
    "test_provider_credentials.py": ("unit", "typed-contracts"),
    "test_provider_redaction.py": ("unit", "provider-redaction"),
    # The protocol's fifth class. The file also carries the offline witnesses
    # for its own skip predicate, which is how a class that spends money is
    # kept honest on a run that does not: the rules that decide whether it runs
    # are tested by name, in CI, and the live probe next to them skips.
    "test_real_provider_smoke.py": ("real_model_smoke", "real-provider"),
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
    "test_docx_fixture_corpus.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_no_reference_leakage.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_parallel_temp_isolation.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_readme_accuracy.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_repo_root_guard.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_scaffolding.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_status_consistency.py": (REPOSITORY_CLASS, "repository-gate"),
    # -- this harness --------------------------------------------------------
    "test_evaluation_harness.py": (REPOSITORY_CLASS, "repository-gate"),
    # -- G5's own work ------------------------------------------------------
    "test_fault_injection_e2e.py": ("e2e", "cli-task"),
    "test_outsider_path.py": ("e2e", "fresh-install"),
    "test_public_fixtures.py": ("unit", "dataset-locators"),
    "test_review_dossier.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_release_workflow.py": (REPOSITORY_CLASS, "repository-gate"),
    "test_threat_model.py": (REPOSITORY_CLASS, "repository-gate"),
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
        "test_fault_injection_e2e.py",
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
        "test_fault_injection_e2e.py",
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

#: The file that carries the real-model smoke. LC-P1-13 T04 named it and never
#: wrote it, so the class had no witness and the report could only say NOT RUN
#: for a reason that was really "there is nothing to run". The file exists now;
#: the class is still reported as not run offline, because the probe spends
#: money and no CI run of this repository holds a credential.
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
