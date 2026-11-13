# LC-P3-07 — fault-drill matrix (design)

> **DESIGN — not a deliverable until run on the installed build.**
> `LC-P3-07` stays `BLOCKED` on `LC-P3-05`'s installed build (work orders
> §12 decision 2, 2026-11-10: *"Only substitute-first design work — the drill
> matrix, the manual skeleton … — may start now, and each such piece is
> labelled design, not a deliverable until run"*). A dev-build rehearsal is
> not authorised. Nothing in this file was run on an installed build; every
> "expected" below names the claim and its existing substitute-run witness,
> and every installed-build observation is a placeholder until a drill record
> says otherwise. Where a number appears here it is a constant in the code or
> a value from a named substitute-run record, anchored to that record — never
> a drill measurement.

Companion designs in the same batch:
[diagnostics](LC-P3-07-diagnostics-design.md),
[backup/rollback](LC-P3-07-backup-rollback-design.md),
[manual skeleton](LC-P3-07-manual-skeleton.md).
The work order is [PHASE_3-work-orders.md](PHASE_3-work-orders.md) §12; the
rows being drilled are quoted there from
[PHASE_3-execution-plan.md](PHASE_3-execution-plan.md) §4.

## 1. What a drill is, and what it is not

Work orders §12 §5.2: `LC-P3-07` *"proves behaviour that already exists under
fault injection, on the build that will be handed to the trial. It adds no
refusal semantics and repairs nothing — a drill that exposes a defect files the
defect; the fix goes to its owning ticket or batch."* Consequences this matrix
holds:

- Every drill row names an **existing** seam in `src/labcairn/` and the
  witness that already proves the property on a substitute. The drill's new
  work is the *installed-build execution and record*, not a new guarantee.
- A drill row that fails because the product misbehaviour differs from the
  substitute-run claim is a **defect report**, filed against the owning ticket
  (`LC-P3-03` for loop semantics, `LC-P3-06` for the provider half,
  `LC-P3-05` for the shell), not patched inside 07.
- The drill record format is §12 §5.6 deliverable 1: *each fault class, its
  injection method, the observed behaviour, the evidence address* — one dated
  record under `docs/acceptance/` (deliverable 5's measured-gap list collects
  what the run could not cover).

## 2. The matrix

Five fault classes, as §12 §5.1 names them. Each row: the injection seam, the
expected observable (the claim under drill), the machinery already carrying
that claim, and the counter-mutation family design.

### 2.1 Interrupted writes

| Field | Content |
|---|---|
| Injection seam | Kill the installed process inside the publication and copy windows of `labcairn.application.revision_loop` — `stage_copy` and `publish_revision` — between the temp-file write and `os.replace` in `labcairn.workspace.outputs.TaskOutputArea.write`. The substitute-run precedent for the injection *technique* is `Crash` in `tests/test_fault_injection_e2e.py`: a child process killed only after it announces (by sentinel file) that it genuinely reached the window under test — the drill reuses the announce-then-kill pattern, not a sleep guess. |
| Expected observable | Either the old file or the new one is present afterwards — never a half-written destination and never another writer's temp name — because `TaskOutputArea.write` canonicalises the target *before* any temporary exists, writes to a temp in the destination's own directory, flushes and `fsync`s before `os.replace`, and cleans up only the temp its own call created (that sequence and its reasoning are the docstring of `TaskOutputArea.write`). The ledger afterwards is `ATTEMPTING`/`UNCERTAIN` for the operation whose outcome the crash left open (the state the recovery half reads — §4.4 below) — never a confirmed completion the disk cannot show. |
| Existing machinery carrying the claim | `tests/test_revision_loop.py` runs a *real recovery drill* through `reconcile_abandoned` / `resolve_abandoned` (its own import line); `tests/revision_loop_support.py::WriteSpy` counts writes by patching `builtins.open` and `os.replace` — a drill that claimed "nothing was written" without such a spy would be restating, not observing. `tests/test_fault_injection_e2e.py` already witnesses crash-after-`os.replace` semantics at process level: *"a crash before the attempt is durable does not repeat the operation"*, *"a crash during the ingestion does not duplicate the material"*. |
| Counter-mutation family | At least one. Design candidate (same shape as `LC-P3-03`'s record §4): make `TaskOutputArea.write`'s cleanup path delete a temp file its call did **not** create (the docstring says a crashed write leaves *"the old file or the new one, not another writer's name"*) — the interruption witness must go red. Validated as effective or discarded with the reason recorded, exactly as `LC-P3-03`'s record §4 does with its two ineffective attempts. |

### 2.2 Locked files

| Field | Content |
|---|---|
| Injection seam | Hold an OS-level lock (a second open handle) on the import source in the source root, and separately on the copy target and publication key in the task output area, while the installed build runs the loop. Two distinct sub-rows because the two roots answer differently: a source the policy will not let the task touch answers *refused*, an output-area file the OS will not let it write answers *failed with a cause*. |
| Expected observable | Source-side: a refusal from the read-only door — `labcairn.workspace.readonly.SourceMaterial.read_permitted` raising `SourceAccessDeniedError` / `SourceIsReadOnlyError` — or the approval-bound path refusing before any write primitive, in the names `refusal.py` already carries (`path_refused` on an escape attempt into a non-permitted root; `cross_project_access` on another task's output area; `approval_refused` on a stale binding). Output-side: the write fails with the OS error surfaced, no receipt is recorded for a file that does not exist, and the loop's already-written pieces stay where `open_loop` put them — `LOOP_DIR_NAME` (`"revisions"`) under the task output area, the import manifest at `revisions/<receipt_id>/import-receipt.json`, the copy at `…/copy.bin`, the publication at `…/published.bin` — so the operator can answer the loop after releasing the lock instead of re-importing it. |
| Existing machinery carrying the claim | `tests/test_revision_loop_refusals.py` (8 negative witnesses) proves every refusal lands **before any write primitive is reached**, asserted through `WriteSpy`; `tests/revision_loop_support.py::refusal_of` is the helper that names the refusal. `labcairn.workspace.outputs.OutputRefusedError` is the write door's own refusal. |
| Counter-mutation family | At least one: widen a refusal classification the witness asserts on (the `LC-P3-03` precedent names this mutation literally — *"name the other-project refusal `path_refused` instead of `cross_project_access`"*, and the witness went red). |

### 2.3 Network loss

| Field | Content |
|---|---|
| Injection seam | Cut the route to the model endpoint mid-run against the **substitute endpoint** — `FakeEndpoint` and `sync_runner` in `tests/provider_fakes.py`, the endpoint the landed rehearsal witnesses drive (`tests/test_provider_bounded_rehearsal.py` passes `runner=sync_runner`) — a transport whose connect or read fails; a provider call issued by `labcairn.providers.bounded_run.BoundedRun.submit_case` is the unit being interrupted. |
| Expected observable | The failure arrives typed: a `labcairn.providers.errors.ProviderError` whose `FailureKind` is a *post-wire* kind (`PROVIDER_TRANSIENT` at transport level), classified retryable by `errors.py`'s own `_CLASSIFICATION` table — and it counts toward the stop-loss's **failure** arm, not its refusal arm, because `PRE_WIRE_KINDS` (`CAPABILITY_UNAVAILABLE`, `BUDGET_EXHAUSTED`, `BUDGET_ENFORCEMENT_UNAVAILABLE`, `OUTBOUND_REFUSED`, `CANCELLED`) is what bounded_run counts as refused-before-the-wire and everything else as failed. The local ledger's `RunRecord` records digests and counts, never text (its docstring), so a lost network leaves a countable record, not a hole. No local effect that already landed is undone: an already-confirmed publication stays published. |
| Existing machinery carrying the claim | `tests/test_provider_bounded_rehearsal.py` (20 integration witnesses) walks the four-rung ladder — budget preflight fail-closed, probe-record gate, consent bridge, capability refusal — and proves the recording upstream shows zero calls when a rung refuses; `tests/test_provider_deidentification.py` (13) covers the case the run carries. |
| Counter-mutation family | At least one: move a post-wire kind into `PRE_WIRE_KINDS` (so a real failure is miscounted as a refusal) — the bounded-run witness that counts failure against the compound stop-loss must go red. |
| Installed-build note | The installed build's shell half (Electron, ADR-0023 — [../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md](../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md)) decides what "network loss" is *observable* to the operator (a served origin unreachable from the window). **[placeholder — the installed build's behaviour here is unmeasured; the drill record fills it.]** |

### 2.4 Model timeout

| Field | Content |
|---|---|
| Injection seam | A substitute provider whose reply arrives after `BoundedRun`'s `timeout_s`, or that never arrives. The classification exists: `FailureKind.TIMEOUT` is pre-wire-listed *as a failure* (it is not in `PRE_WIRE_KINDS`) and `errors.py` classifies it retryable with the retry action — *"The provider did not answer within the configured timeout."* |
| Expected observable | The request is recorded as a failure, the compound stop-loss counts it toward its consecutive-failure arm (`CONSECUTIVE_FAILURE_LIMIT = 3`), and three such failures end the run with `StopLossTriggeredError` rather than spending further budget. Nothing is published from a timed-out suggestion. |
| Real-model status | **real-model drill, unlocked only by the owner after `LC-P3-06`.** §12 §5.3: the drill matrix's model-timeout row runs against the substitute first, and *"a real-model row is an owner addition, not scope smuggled in"*; §12 decision 5 (2026-11-10) keeps §14 item 7 verbatim — the real-model row remains a named gap at the exit decision. `LC-P3-06`'s real half has since been run under its own seven-field authorisation ([../acceptance/LC-P3-06-real-half-2026-11-10.md](../acceptance/LC-P3-06-real-half-2026-11-10.md), one 47.0 s slow completion measured against the 60 s timeout) — which changes what the gap names, not the ruling. This design adds no real-model row on its own authority. |
| Existing machinery carrying the claim | Same as §2.3. The timeout knob itself is `BoundedRun.__init__`'s `timeout_s`, passed through to the provider the harness wires. |
| Counter-mutation family | At least one: raise the consecutive-failure limit the stop-loss compares against (or bypass `CompoundStopLoss.record_failure`) — the run's own stop-loss witness must go red before any further request is issued. |

### 2.5 Known errors

| Field | Content |
|---|---|
| Injection seam | Drive each named refusal and each typed provider error through the installed build's own surfaces, one at a time: the loop's refusals (`cross_project_access`, `path_refused`, `approval_refused` with ADR-0003's `source_changed`, `approval_missing`, `loop_already_published`, `source_drifted` from `verify_original`) and the provider layer's classified errors (`errors.py`'s `_CLASSIFICATION`). A known error is *expected and named*; the drill's claim is that the operator can tell which one happened from what the build shows. |
| Expected observable | Each refusal surfaces with its name and, where the design says a remedy must be stated, the remedy — the precedent is `describe_abandoned`'s message, which names the operations *and* the one command that can answer them (*"a refusal whose remedy is not stated is a dead end rather than a decision"*). `RunRequestRefusedError`/`StopLossVerdict` name the bounded-run refusals. No refusal class is new: §12 §5.3. |
| Existing machinery carrying the claim | `LC-P3-03`'s four counter-mutations (12…4 classes × witnesses, record §4), `LC-P3-06`'s twelve counter-mutations (12/12 RED, record §5's rung-by-rung table), both under [../acceptance/LC-P3-03-revision-loop-2026-11-10.md](../acceptance/LC-P3-03-revision-loop-2026-11-10.md) and [../acceptance/LC-P3-06-substitute-first-2026-11-10.md](../acceptance/LC-P3-06-substitute-first-2026-11-10.md). |
| Counter-mutation family | At least one: suppress a refusal's message remedy (the "dead end" mutation) — the witness asserting the named remedy must go red. |

## 3. Counter-mutation policy for the drill family

The three landed batches set the precedent this matrix copies: `LC-P3-03`
four counter-mutations all RED with two ineffective attempts *discarded and
recorded* (record §4), `LC-P3-06` twelve counter-mutations 12/12 RED (record
§5). The drill batch's policy, one rule per family:

1. **At least one counter-mutation per fault family** — the drill harness for
   a family whose witness survives a mutation aimed at it is not a drill.
2. **A mutation is semantic, applied to the product module, one witness run,
   restored from `HEAD`** — a mutation that leaves its witness green tested
   nothing, and a mutation that reddens the witness for an unrelated reason
   (lint, encoding, line length) is not a witness of the property. A
   *deletion* of the check is not the mutation: the project's own precedent is
   that removing the assertion can stay invisible to the exit code.
3. **Ineffective mutations are recorded as discarded**, with why — the
   `LC-P3-03` record's habit is load-bearing: *"a red run is not by itself
   evidence that the mutation was effective."*
4. Mutation scripts live **outside** the repository (the 03/06 precedent:
   `run_mutations.py` under `E:\labcairn-local\tmp\`), because they restore
   from `HEAD` and must not dirty the tree they measure.

## 4. Reusable machinery, verified against source

Checked 2026-11-10 by reading the modules, not from memory:

| Cited | Where it actually lives |
|---|---|
| `open_loop`, `request_loop_approval`, `verify_original`, `stage_copy`, `publish_revision` | `src/labcairn/application/revision_loop.py` |
| `CROSS_PROJECT_ACCESS`, `PATH_REFUSED`, `APPROVAL_MISSING`, `APPROVAL_REFUSED`, `SOURCE_DRIFTED`, `LOOP_ALREADY_PUBLISHED` | `src/labcairn/application/refusal.py` |
| `describe_abandoned`, `reconcile_abandoned`, `resolve_abandoned` (CLI: `labcairn task reconcile <operation_id> --expected-sha256 <hash>`) | `src/labcairn/application/recovery.py` |
| `TaskOutputArea.write` (temp + `fsync` + `os.replace`, own-temp-only cleanup), `OutputRefusedError`, `WriteReceipt`, `CountingWriteObserver` | `src/labcairn/workspace/outputs.py` |
| `SourceMaterial.read_permitted`, `SourceAccessDeniedError`, `SourceIsReadOnlyError` | `src/labcairn/workspace/readonly.py` |
| `RecoveryCoordinator.reconcile`, `mark_uncertain`, `FileSystemProbe`, `ATTEMPTING`/`UNCERTAIN` states | `src/labcairn/recovery/reconciliation.py`, `src/labcairn/recovery/probes.py` |
| `BoundedRun`, `CompoundStopLoss`, `StopLossTriggeredError`, `RunNotAuthorisedError`, `RunRequestRefusedError`, `RunRecord.to_counts`, `PRE_WIRE_KINDS`, `REHEARSAL_MAX_REQUESTS`, `REHEARSAL_MAX_TOTAL_TOKENS`, `CONSECUTIVE_FAILURE_LIMIT`, `PROPOSAL_REFUSAL_RATE_LIMIT` | `src/labcairn/providers/bounded_run.py` |
| `FailureKind` (incl. `TIMEOUT`, `PROVIDER_TRANSIENT`), `_CLASSIFICATION` | `src/labcairn/providers/errors.py` |
| `WriteSpy`, `refusal_of`, `LoopFixture` | `tests/revision_loop_support.py` |
| `Crash` (announce-then-kill injector) | `tests/test_fault_injection_e2e.py` |

## 5. What the implementation will have to register (design note, not implemented)

When the drill harness eventually lands on the installed build, each new test
file registers in three places — `pytestmark` gate classes,
`.github/ci-shards.json`, and the gate table in `tests/evaluation/manifest.py`
— per the landed precedent (the 03/06 handovers list exactly these three;
`tests/test_ci_shard_coverage.py` is what says a file in no shard is a test CI
never runs). This design batch adds no test file and changes no registration,
so the shard costs stay measured where they were measured.

## 6. Open placeholders for the drill record

- **[placeholder]** The installed build's copy/publication windows and how the
  drill injects into *that* process (the Electron shell's served origin may
  change who holds the file handles — ADR-0023).
- **[placeholder]** Locked-file behaviour on the installed build's real paths
  (installer-owned directories may carry permissions a dev checkout does not).
- **[placeholder]** What the shell *shows* the operator for each refused class
  (§2.5's observability claim is a shell claim once the shell exists).
- **[placeholder]** Whether the owner adds the real-model timeout row
  (§2.4). Until an owner decision, the substitute row is the whole row.
