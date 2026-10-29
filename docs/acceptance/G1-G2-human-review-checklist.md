# G1 and G2 — the human independent review, as a checklist

**Status:** prepared 2026-10-29. **Not executed.** No verdict in this file is a
review outcome; every box is empty on purpose.

**Why it exists.** The board's rule is that
*"A row is never marked done because something looks finished — it is marked done
when an independent review at a named commit says so"*
([`docs/PHASE_1_WORKORDERS.md:19`](../PHASE_1_WORKORDERS.md)). G1 and G2 closed in
October 2026 on **internal cross-validation**: a reviewing agent that did not
implement the work it was checking, but sat inside the same project and the same
session that wrote it. Their own records say what that is not —
*"internal cross-validation by two agents, not an external independent audit, and
is not evidence of one"* ([`G2-acceptance.md:98`](G2-acceptance.md)), and
[release notes §2.9](../RELEASE-NOTES.md) names G1's and G2's work orders as the
ones with **no independent review**, which is the condition G3, G4 and G5 each met
with a review at a named commit by a party outside the work. Two rounds of
AI-agent retro-review have since re-examined both gates, found real defects,
and had each finding re-tested against the code — and the owner ruled on
2026-10-28 that this is **accepted as closeout evidence for Phase 1** but is
*"procedural independence, not human"*, so it **does not discharge** the board's
rule for these two gates
([`docs/PHASE_1_WORKORDERS.md:60-66`](../PHASE_1_WORKORDERS.md),
[`docs/RELEASE-NOTES.md:258-268`](../RELEASE-NOTES.md)). The owner decided on
2026-10-29 to arrange the human review. **This file is what that reviewer needs
to be able to work from, and nothing else.**

**What it is not.** It is not a re-statement of the gates' claims. Each row below
names the claim, the **node id** that holds it, and the **mutation that must go
red**. Where the record names only a whole file, or only a source method, this
file says so — those gaps are the first findings a reviewer should expect to
make.

---

## 0. Eligibility and method

The reviewer must:

- **have written none of the fixes** in the commits listed in §2.3, and not be
  the party that dispatched them;
- **break the implementation, never the test.** A mutation that turns a whole
  file red proves the test exists; a mutation that turns nothing red is a
  finding, and it is a finding *about the mechanism*, not about the code under it
  — see §6;
- **run the suite on both platforms**, or say which one it ran on and treat the
  other's witnesses as unmeasured. Three of the load-bearing witnesses here are
  Windows-only (`test_junction_escaping_the_root_is_refused` and its siblings)
  and two are POSIX-only;
- **record a verdict per clause**, not per gate, and name the commit reviewed.
  A gate verdict with an unexamined clause is how G1's exit demonstration ran
  broken for five gates without anyone noticing.

The reviewer should not: accept a docstring as evidence; re-run a mutation that
another party already ran and reported; or fix what it finds — a fix by the
reviewer costs the review its independence, so findings are handed back and the
review is re-run afterwards by the same reviewer, which is the shape G3, G4 and
G5 used.

**Record format:** at the foot of each clause table, one line per row — `PASS`,
`PASS WITH NOTES` (note quoted), `FAIL` (defect named, file:line), or
`NOT MEASURED` (platform, or the witness does not exist). §7 is the write-back.

---

## 1. Setup

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q                      # the whole suite
uv run pytest -rs -q                  # the skips, with their reasons
```

The suite's own fixtures take their temporary root from `LABCAIRN_TEMP_ROOT` or
the system temp directory and never from the checkout
(`conftest.py:120`), and the harness refuses a temporary directory inside the
repository —
`tests/test_evaluation_harness.py::test_the_runner_refuses_a_temporary_directory_inside_the_repository`
holds that rule for the evaluation run. Point `--basetemp` outside the repo too
when passing it by hand.

Then read, in this order:
[`docs/acceptance/G1-evidence.md`](G1-evidence.md) (the gate's own record,
including the two blocking findings it opened with),
[`docs/acceptance/G2-acceptance.md`](G2-acceptance.md) (clause tables),
[`docs/acceptance/G2-evidence.md`](G2-evidence.md) (the narrative). Both records
carry **dated corrections** — see §6 before trusting any figure in them.

---

## 2. The subject

### 2.1 G1 — Trusted core

| | |
|---|---|
| Work orders | LC-P1-02 (versioned contracts), LC-P1-03 (providers, budgets, capability probing), LC-P1-04 (workspace, permissions, approvals) |
| Gate exit test | *"fake provider, typed tools, safe workspace; ≥2 architecture comparison ADRs"* |
| Closed at | `main` @ `9f9c4f0`, 2026-10-16 |
| Tests at close | 672 passed, 1 skipped. The record's per-package figures are 204 / 98 / 174 and 10 cross-cutting — **those four are the work orders' own packages and do not sum to 672**, which also counts the tests that predated the gate |
| The ADR clause | `docs/adr/` holds **twelve ADRs and a template** at the time this checklist was written. The clause asks for at least two **comparison** ADRs, so the reviewer counts the ones that compare alternatives — ADR-0008 (PDF ingestion library), ADR-0012 (chart renderer) and ADR-0013 (report export libraries) are of that shape — rather than counting files |

### 2.2 G2 — Durable work

| | |
|---|---|
| Work orders | LC-P1-05 (SQLite task store, transactional events), LC-P1-06 (checkpoint, operation reconciliation, revision), LC-P1-07 (minimal research workflow, Skill contract) |
| Gate exit test | *"persistent task, stage plan, injected restart"* |
| Closed at | `main` @ `a361a7c`, 2026-10-16 |
| Tests at close | 998 passed, 2 skipped |

### 2.3 What changed after each gate closed

These are the commits the reviewer has to read, because a gate's verdict covers
its own tree and every later change to that tree is part of what is being
accepted now. Each SHA was verified with `git log -1`.

**`security/` and `workspace/` — G1's boundary (LC-P1-04):**

| SHA | What it did |
|---|---|
| `66dbbab` | LC-P1-04 as accepted: workspace roots, capability policy, approval binding |
| `56e43a5` | closed the permission bypass cross-review found (the case-fold one), and the cause behind it |
| `4e7ba6d` | policy matched on the canonical resolved entry, not the declared name (ADR-0011) |
| `6220a08` | a new file under an 8.3 short-spelled root is under the root (the G1 exit demonstration's Windows defect) |
| `47259e0` | the refusals watched by what they say (G4 round; touches the boundary's refusal vocabulary) |
| `51a982c` | the consent covers the recipe a figure is drawn from (ADR-0012 constraint 7) |
| `26ab4cb` | the ledger asks the capability registry, so a capability that does not exist cannot spend a consent |

**`providers/` — G1's fake and its budgets (LC-P1-03):** `a7841d1` (as accepted),
`dd693c2` (the two cross-module gaps G1 left open: a cost ceiling that depended
on callers remembering an argument, and two capability vocabularies), `18f257c`
(a false negative the real provider smoke exposed).

**`db/` — G2's store (LC-P1-05):** 17 commits since `a361a7c`, of which the
review-finding ones are `9c3bbfa`, `2e80ef2`, `73107d9` (the wrong-acceptance
families in the material schema, and the fabrication/unreadable-file defects) and
`d114810`, `ba07dd5`, `895dc6c`, `edddf5e`, `7aec3d0`, `b92a8ac`, `a4b451b`,
`4121ae4`, `14a09af`, `9942e6c`, `d5bea0e`, `34193cf`, `080e487`.

**`recovery/` — G2's reconciliation and approvals (LC-P1-06):** `26ab4cb`,
`7fa7821`.

**skills / orchestrator (LC-P1-07):** 1 commit — `ba07dd5` (the source id's type, which touched `skills/artifacts.py`). `git log --oneline a361a7c..HEAD -- src/labcairn/skills` returns exactly that one line.
**`core/`, `runtime/`, `sources/`, `evidence/`, `reports/`** (LC-P1-02): 3 / 7 /
6 / 15 / 8 commits, mostly later gates' features rather than changes to G1's
contracts — the reviewer should confirm that rather than assume it:
`git log --oneline 9f9c4f0..HEAD -- src/labcairn/core src/labcairn/runtime`.

---

## 3. G1 — clause by clause

| Clause (as the record states it) | Witness to read | Break it by | Verdict |
|---|---|---|---|
| A write evaluates to ASK, is approved once, and is consumed against the arguments recorded at approval time | `tests/test_security_approval.py::test_the_digest_is_recomputed_at_the_moment_of_use`, `::test_approval_rejected_when_arguments_change` | stop recomputing the digest at spend | |
| A second use of an approval is refused | `tests/test_security_approval.py::test_approval_is_single_use` | make `consume` a read instead of a pop | |
| An unknown capability cannot spend a consent | `tests/test_security_approval.py::test_an_unregistered_capability_is_refused_before_the_grant_is_spent` | drop the registry check in `ApprovalLedger.consume` | |
| Writing to source material is refused structurally, not by a rule | `tests/test_workspace_boundaries.py` (the record names the behaviour, **not a node id** — the reviewer's first job here is to name it) | grant `ALLOW **` and attempt a root-kind write | |
| An unapproved outbound send is refused before any send | `tests/test_provider_redaction.py`, `tests/test_workspace_boundaries.py` (**whole-file citations in the record**) | default `ALLOW` for the disclosure capability | |
| A real Windows junction escaping the root is refused; a junction pointing back inside is admitted | `tests/test_security_paths.py::test_junction_escaping_the_root_is_refused`, `::test_a_junction_is_not_reported_as_a_symlink`, `::test_junction_pointing_back_inside_the_root_is_admitted` | compare the declared path instead of the resolved one — the *admitted* case is what stops that mutation from passing | |
| A path denied under its resolved spelling beats an allow on the declared spelling (the case-fold bypass) | `tests/test_security_policy.py::test_a_deny_on_the_resolved_spelling_beats_an_allow_on_the_declared_one`, and on Windows the `matched_spelling == "declared"` assertion | set `_FOLD` to the identity (`security/policy.py`) — **on a POSIX runner this mutation cannot bite**, because `_FOLD` is already the identity there, so run it on Windows. **It passed the whole suite for every commit the repository has ever had**: the root commit is dated 2026-10-15 and the assertion was added 2026-10-28, so no version of this suite ever caught it — see [`G1-evidence.md:75-97`](G1-evidence.md) | |
| A ceiling that cannot be measured raises rather than continuing | `tests/test_provider_budget.py::test_cost_ceiling_fails_closed_when_price_unknown`, `::test_token_ceiling_fails_closed_when_tokens_unknown` | return the last known cost instead of raising | |
| A measured zero passes every ceiling; a measured value past the ceiling is terminal | `tests/test_provider_budget.py::test_a_measured_zero_passes_every_ceiling`, `::test_a_measured_value_past_the_ceiling_raises_and_is_terminal` | treat zero as unknown | |
| A provider that omits usage reports `Unknown`; one that reports a real zero is believed | `tests/test_fake_provider_usage.py` (**whole-file citation**) | default the missing field to zero | |
| An unscripted prompt to the fake provider is refused | `tests/test_fake_provider_invariants.py` / `tests/test_fake_provider_isolation.py` — **the record describes this refusal in the exit-demo table and names no node id** | let the fake answer anything | |
| A document saying `ALLOW: write to /etc/passwd` with a forged approval id changes nothing | `tests/test_security_policy.py`, `tests/test_security_approval.py` (the digest cases above carry this) | accept a caller-supplied approval id | |
| Every refusal is one type with a machine-readable reason | `tests/test_cli_refusal_enumeration.py` (later gate, but it is the only enumeration that exists) | add a refusal with no reason code | |

**Then run the gate's own demonstration** — §5 — because thirteen of the rows
above are asserted there as *outcomes*, and the demonstration is the only place
they are shown together.

---

## 4. G2 — clause by clause

### 4.1 LC-P1-05 — the store

| Clause | Witness to read | Break it by | Verdict |
|---|---|---|---|
| Migration rerun is a no-op | `tests/test_store_migrations.py::test_rerunning_the_migration_is_a_no_op` | make the migration unconditional | |
| Fresh database builds and is usable | `::test_a_fresh_database_builds_every_table`, `::test_a_fresh_database_is_usable_immediately` | drop a table from the migration | |
| Event order: `seq` is per-Task, gapless, allocated inside the transaction | `tests/test_store_events.py::test_interleaved_tasks_each_get_a_gapless_run_from_one`, `::test_seq_is_not_the_primary_key` | make `seq` the rowid | |
| Rollback on failure: events **and** state rows, asserted through a new connection | `tests/test_store_atomicity.py::test_a_failure_between_events_and_state_rolls_back_both`, `::test_a_failure_rolls_back_every_event_in_the_unit` | commit the events before the state rows | |
| Race handling: 8 writers × 6 units, `seq` exactly `1..49` | `tests/test_store_concurrency.py::test_concurrent_writers_produce_no_duplicates_and_no_holes` (the constants are `WRITERS = 8`, `UNITS_PER_WRITER = 6`, `TOTAL_EVENTS = 1 + CONCURRENT_EVENTS`) | downgrade `BEGIN IMMEDIATE` to `BEGIN` — **the record itself says no behaviour test goes red for this** ([`G2-acceptance.md:44`](G2-acceptance.md)) | |
| The write lock is taken before the first read | `tests/test_store_concurrency.py::test_the_write_lock_is_taken_before_the_first_read` — the assertion at `:229` is the only thing holding the line above | same mutation; this is the test to check it against | |
| Same-task identity across restarts, and the sequence continues | `tests/test_store_persistence.py::test_task_identity_survives_a_restart`, `::test_a_resumed_task_continues_its_sequence` | reopen without disposing the pool | |

### 4.2 LC-P1-06 — checkpoints, reconciliation, revision

| Clause | Witness to read | Break it by | Verdict |
|---|---|---|---|
| Crash **before** write: rolled back, `operation_attempted` absent, file never created, state `AUTHORIZED` | `tests/test_recovery_crash_matrix.py::test_at1_crash_before_write_is_replayable` | confirm before the write | |
| Crash **after** write, before commit: bytes present, confirmation rolled back, state `ATTEMPTING` | `::test_at2_crash_after_write_before_commit_marks_uncertain_and_blocks_replay`, and `examples/g2_uncertain_demo.py` end to end | mark the operation complete on the write | |
| Crash **after** commit, before the UI receipt: zero reconciliation, `replay()` raises with a zero call count | `::test_at3_crash_after_commit_before_ui_receipt_needs_no_replay` | enter `UNCERTAIN` on a committed operation | |
| No blind replay, refused by **two** independent guards | `RecoveryCoordinator.assert_replayable` **and** `SideEffectExecutor.replay` — **the record names source methods, not tests**; the reviewer's job is to find whether a test reaches both independently | make one delegate to the other | |
| Changed source invalidates downstream, proved with mtime restored so a time-keyed implementation cannot pass | `tests/test_recovery_resume.py::test_resume_refuses_to_skip_a_stage_whose_material_moved`, with `::test_a_changed_source_invalidates_downstream_artifacts` and `::test_a_changed_source_invalidates_the_stage_that_consumed_it` | drop the `os.utime` restore and watch whether the sibling invalidation test still passes — [`G2-acceptance.md:56`](G2-acceptance.md) says that sibling **does not prove the clause**, because it is handed the previous hash and never touches the filesystem | |
| No reuse of an expired approval; all seven refusal reasons of ADR-0003 C4 | `tests/test_recovery_approvals.py` — enumerate `ApprovalRefusal` and check **each member** has a witness (`::test_expired_approval_is_not_reusable`, `::test_approval_rejected_when_arguments_change`, `::test_approval_rejected_on_task_scope_mismatch`, `::test_approval_rejected_when_policy_changed`, `::test_approval_invalidated_by_source_change`, `::test_a_missing_source_counts_as_changed`, `::test_a_granted_approval_is_consumed_once`) | see §6.2 — the durability half of this row is **corrected in the record** | |
| `UNCERTAIN` is entered, not assumed away; unreadable is CONFLICT, not REPLAY_SAFE | `tests/test_recovery_crash_matrix.py::test_at6_reconciliation_flags_conflicting_content_for_human` and `::test_the_probe_reads_the_filesystem_and_never_writes_to_it` — **the record states this as a design point and names no node id for it**, which is §6.1 again | treat unreadable as replay-safe, or let the probe write | |

### 4.3 LC-P1-07 — the workflow and the Skill contract

**Every row of this table was cited in the record by behaviour, not by node id.**
The node ids below were read out of the tree at the time this checklist was
written; the reviewer should re-derive them and note any that do not exist.

| Clause | Witness to read | Break it by | Verdict |
|---|---|---|---|
| Every stage consumes the actual previous artifacts | `tests/test_skill_execution.py::TestForgedUpstreamArtifactsAreRefused::test_a_stage_that_names_a_partial_lineage_is_refused`, `::test_a_substituted_upstream_artifact_is_caught_when_the_next_stage_reads_it` | widen `_upstream_for` to a name lookup | |
| The run's signature offers no way to supply a plan | `tests/test_skill_plan.py::TestThePlanIsNotAuthoritative::test_the_run_signature_offers_no_way_to_supply_a_plan` | add a `plan=` parameter | |
| No empty placeholder passes (four executable conditions) | `tests/test_skill_execution.py::TestPlaceholderOutputIsRefused::test_a_stage_returning_a_placeholder_shell_is_refused_and_retried`, `::test_a_stage_that_returns_nothing_useful_is_refused`, `::test_a_draft_citing_claims_nobody_produced_is_refused`; `tests/test_skill_quality.py::TestPlaceholderVocabulary` (the marker vocabulary) and `::TestSubstanceRejection::test_placeholder_text_in_a_body_is_refused`, `::test_the_schema_refuses_an_empty_primary_collection` | the record's own limit applies here: **three of the four conditions are textual heuristics**, so prose that reads well passes. Ask the author of the clause whether that was the intent | |
| A blocked user decision awaits approval, and bypassing the orchestrator raises | `tests/test_skill_execution.py::TestApprovalCheckpoint::test_a_direct_attempt_to_enter_the_guarded_stage_is_refused`, `::test_an_approval_for_a_different_proposal_digest_is_refused`, `::test_an_expired_approval_is_refused`, `::test_a_blocked_stage_leaves_a_checkpoint_naming_what_it_is_waiting_for`; `tests/test_skill_approval.py` | hardcode the checkpoint instead of declaring it | |
| Limited retries on no progress, where "no progress" is byte-identical output | `tests/test_skill_execution.py::TestBoundedRetries::test_a_stage_that_never_varies_is_failed_after_exactly_the_declared_attempts`, `::test_the_reason_names_the_byte_identical_repetition`, with `::TestPlaceholderOutputIsRefused::test_an_unexpected_exception_propagates_rather_than_retrying` as the negative | compare a hash instead of bytes, or compare nothing — the record says deleting the check turns *the naming test* red, which is the thing to re-verify | |
| Cancellation loses no prior valid work | `tests/test_skill_execution.py::TestCancellationPreservesVerifiedWork::test_cancelling_before_a_stage_leaves_every_earlier_artifact_intact`, `::test_every_verified_artifact_survives_a_cancellation`, `::test_a_stage_in_flight_when_cancellation_arrives_still_has_its_artifact_kept`, `::test_a_cancelled_run_can_be_re_entered_and_finishes` | cancel mid-stage and discard the stage's output | |

---

## 5. The three exit demonstrations

The check counts below were **re-counted from the source** (`grep -c "^\s*check("`),
not taken from the records:

| Demonstration | Checks | Expected |
|---|---|---|
| `uv run python examples/g1_exit_demo.py` | **36** | exit 0 |
| `uv run python examples/g2_exit_demo.py` | **14** | exit 0 |
| `uv run python examples/g2_uncertain_demo.py` | **18** | exit 0 |

They were run by **nothing** from the day they shipped until G5's review found
G1's broken — G2, G3 and G4 each closed over the top of a demonstration nobody
ran, and the reason turned out to be a real product defect (`6220a08`).
`tests/test_earlier_exit_demos.py` now runs all three as
subprocesses, parametrised, with two properties: that they still hold
(`::test_an_earlier_gates_exit_demonstration_still_holds`) and that **the exit
code is load-bearing** (`::test_the_demonstrations_exit_code_still_means_something`,
which plants a false claim and requires a non-zero exit).

**The reviewer must still run them by hand at the commit it names.** A witness
that runs a demonstration proves the demonstration runs; it does not prove the
demonstration's claims are true of the product today.

Note for the Windows reviewer: `git status` after these demos must stay clean —
they write into a workspace they build under a temporary directory, and the
repository's rules forbid a run that depends on the tree it measures.

---

## 6. Where the records are weakest, named before the reviewer gets there

These are the four things this checklist found while reading the two records
against the tree. They are **not** verdicts; they are the places to start.

### 6.1 A claim can be recorded without a node id, and then nobody can re-run it

The G1 record cites whole files (or only a behaviour) for four of the thirteen
rows in §3, and every LC-P1-07 clause in §4.3. That is not a defect in the claim
— it is a defect in the *reviewability* of the claim, and it is why the board asks
for a named commit and not a named document. G3's, G4's and G5's records each name
node ids for their findings; these two gates predate that habit.

### 6.2 G2's approval clause carries a correction the reviewer has to read twice

[`G2-acceptance.md:57`](G2-acceptance.md) was corrected on 2026-10-28: the row
claimed single use was *"a conditional `UPDATE` whose affected-row count is the
guarantee"*, which is true of `ApprovalStore.consume` — and `ApprovalStore` has
**no production caller**. The shipped consent path spends from the in-memory
`ApprovalLedger`. The seven refusal reasons still hold against the path that
ships, so the *verdict* stands, but the *durability claim* does not, and the
restart-durable store is scoped to Phase 2
([`docs/PHASE_1_WORKORDERS.md`](../PHASE_1_WORKORDERS.md), carried-issue row).
**A reviewer who reads only the table's PASS will carry a claim the tree does not
support.**

### 6.3 Two figures in these records were already found to be invented

- `G2-acceptance.md:39`'s event-order row quoted `1..5` / `1,3,5,7,9` /
  `2,4,6,8,10` — hand-probe figures **no test asserts**; corrected 2026-10-28 to
  the values `test_interleaved_tasks_each_get_a_gapless_run_from_one` actually
  asserts.
- `G1-evidence.md:75-97`'s case-fold witness asserted only `permission is DENY`,
  which a broken fold still satisfies; the `matched_spelling == "declared"`
  assertion was added 2026-10-28, and without it the mutation
  `_FOLD = str.casefold → identity` leaves the whole suite green.

Both are recorded here because they are the shape this review is looking for: a
number in a document that was measured by hand once and then never again.

### 6.4 The platform halves of the boundary witnesses

`test_junction_escaping_the_root_is_refused` and the 8.3 short-name witnesses run
on Windows only; `test_the_session_directory_can_still_be_entered` runs on POSIX
only. Since 2026-10-29 the evaluation harness **accepts those skips by ruling**
(§1.4.1b, `tests/evaluation/aggregate.py`) and names each one in the blocker's
row, so a reader can no longer tell from a blocker's status alone whether a
platform half went unmeasured. **The reviewer should read the row's accepted list
as the thing that was not exercised on that runner**, and should want the union
of both runners rather than one.

---

## 7. Write-back

When the review is done:

1. Create `docs/acceptance/G1-G2-human-review.md` (this file's §3–§5 tables, with
   the verdict column filled, the commit named, the reviewer's eligibility
   stated, and every finding given the test that should have caught it).
2. Update the board's **Verification basis** block with a dated paragraph: the
   human review's verdict and commit, and the sentence *"the board's independence
   rule is discharged for G1 and G2 by a review at `<sha>` by `<who>`, which
   wrote none of the fixes"* — the wording the G3, G4 and G5 rows use.
3. Update `docs/handoff/CURRENT.md`'s G1/G2 history and the
   `docs/PHASE_1_WORKORDERS.md:60-66` owner-ruling block, which currently says
   the rule *remains an open follow-up*. Do not delete that ruling: append to it.
4. If the verdict is FAIL, the findings go through the normal flow — fix, then
   **the same reviewer re-runs its own mutations against the fixed code**, which
   is what makes the re-run independent rather than a re-approval.

## 8. Effort

Roughly **three to four hours** for the suite, the demonstrations and the
thirty-three clause rows, and **most of it on Windows** because of §6.4. The
reviewer who has never seen the repository should spend the first hour on §2.3
and §6, because the commits and the corrections are the part that a fresh reader
cannot reconstruct.
