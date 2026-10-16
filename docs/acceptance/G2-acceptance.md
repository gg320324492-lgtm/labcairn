# G2 — Formal acceptance

**Gate:** G2 (Durable work)
**Work orders:** LC-P1-05, LC-P1-06, LC-P1-07
**Subject:** `main` @ `a361a7c` — 186 tracked files
**Date:** 2026-10-16
**Scope of this document:** the checklist the work orders specify, with the evidence for each line. The narrative record is [G2-evidence.md](G2-evidence.md).

## Gate exit test

> persistent task, stage plan, injected restart

```
uv run python examples/g2_exit_demo.py     → exit 0, 14 checks
uv run python examples/g2_uncertain_demo.py → exit 0, 18 checks
```

## Verification actually run at this commit

| Check | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 122 files already formatted |
| `uv run mypy` | no issues, 114 source files |
| `uv run pytest` | **998 passed, 2 skipped** |
| `examples/g2_exit_demo.py` | exit 0 |
| `examples/g2_uncertain_demo.py` | exit 0 |

The two skips are declared, not silent: one is the real-provider smoke needing a credential the project owner supplies, the other is a Windows-drive-form test that is meaningless on POSIX.

## LC-P1-05 — SQLite task store and transactional events

**Build:** SQLAlchemy/Alembic migrations; tables for task, run, stage, event, operation, approval, checkpoint, artifact; unique event sequence; transactionally coupled event/state transitions; snapshots; user identity and future multiuser scope explicit.

| Acceptance clause | Verdict | Evidence |
|---|---|---|
| Migration rerun | **PASS** | `tests/test_store_migrations.py` — rerun at 0001 and 0002 leaves the revision and the data untouched, asserted rather than assumed |
| Fresh database | **PASS** | `test_store_migrations.py`, and both exit demonstrations build one from nothing |
| Event order | **PASS** | `seq` is per-Task, gapless, allocated inside the transaction. Verified from outside the suite: two interleaved Tasks each get 1..5 while their rowids interleave `1,3,5,7,9` / `2,4,6,8,10` — impossible if `seq` were the rowid |
| Rollback on failure | **PASS** | Failure injected between the events and the state rows rolls back **both**, asserted through a new connection so a partially committed state cannot pass. A mutation that commits events alone turns exactly that test red |
| Race handling | **PASS** | 8 threads × 6 units, one session each, producing `seq` 1..49 with no duplicate and no gap |
| Same-task identity across restarts | **PASS** | Connection pool disposed, reopened from the file alone; the next event takes `seq` 4, not 1 (`test_a_resumed_task_continues_its_sequence` asserts the whole run `[1, 2, 3, 4]`) |

**Recorded limitation.** Downgrading `BEGIN IMMEDIATE` to `BEGIN` leaves every concurrency *behaviour* test green, because this implementation's first statement is a write and no lock upgrade is needed. The assertion on the emitted SQL is what holds that line. This is stated because a reader should know which of the two is load-bearing.

## LC-P1-06 — Checkpoint, operation reconciliation and revision

**Build:** stage-boundary checkpoints, material hashes, artifact hashes, task revision ID, run attempts, uncertainty states on crashed side effects; reconcile before replay, resume from the last verified stage; scoped pause/stop/resume.

| Acceptance clause | Verdict | Evidence |
|---|---|---|
| Crash **before** write | **PASS** | `AT-1`: transaction rolled back, `operation_attempted` absent, file never created, state `AUTHORIZED` |
| Crash **after** write, before commit | **PASS** | `AT-2` and `examples/g2_uncertain_demo.py` end to end: file present with the intended bytes, confirmation rolled back, state `ATTEMPTING` |
| Crash **after** commit, before UI receipt | **PASS** | `AT-3`: zero reconciliation — nothing enters `UNCERTAIN`, no reconciliation events, `replay()` raises with a zero call count, mtime and hash unchanged. `AT-3b`: a reconnecting client reads exactly the missed tail by `after_seq` |
| No blind replay | **PASS** | Refused by `RecoveryCoordinator.assert_replayable` **and** by `SideEffectExecutor.replay` independently, while the outcome is unresolved |
| Changed source invalidates downstream | **PASS** | The material is rewritten **and its mtime restored with `os.utime`**, so an implementation keyed on modification time cannot pass: `plan_resume` re-snapshots through `MaterialResolver.snapshot` (`test_resume_refuses_to_skip_a_stage_whose_material_moved`). Its sibling `invalidate_on_source_change` test does **not** prove this — that one is handed the previous hash by the caller and never touches the filesystem. Invalidation follows `derived_from` |
| No reuse of an expired approval | **PASS** | All seven refusal reasons from ADR-0003 C4, each reached by real input; single use is a conditional `UPDATE` whose affected-row count is the guarantee |

**Design point worth naming.** `UNCERTAIN` is a state recovery *enters*, not one it assumes away. Probing is over bytes: absent and a matching SHA256 are decidable; a different hash, a directory, or an unreadable target are not. **Unreadable is deliberately CONFLICT, not REPLAY_SAFE** — it is not evidence that nothing landed, it is evidence that we cannot tell. CONFLICT falls back to `UNCERTAIN` rather than `FAILED`, because `FAILED` would read as retryable to a later round and this one needs a human.

## LC-P1-07 — Minimal research workflow and Skill contract

**Build:** one declared `research-report` Skill with stages `intake → inventory → retrieve → evidence → propose → [user approval] → draft → validate → deliver`; typed inputs/outputs/dependencies; the approval checkpoint between `propose` and `draft`; a plan that is a task artifact, not a new authoritative store; budget and graceful blocking semantics.

| Acceptance clause | Verdict | Evidence |
|---|---|---|
| Every stage consumes actual previous artifacts | **PASS** | Not a non-null check. One path to an input (`_upstream_for`), and `run()`'s signature is locked by `inspect.signature`. A forged inventory with the wrong lineage, one whose materials `intake` never declared, and a ledger slot swapped after the fact each fail |
| No empty placeholder passes | **PASS** | Four executable conditions. Coverage found a real hole while being written: five fields were unclassified, so a stage could hide a shell in any of them |
| Blocked user decision awaits approval | **PASS** | The gate is declared, not hardcoded; bypassing the orchestrator raises `StaleApprovalError` |
| Limited retries on no progress | **PASS** | "No progress" is byte-identical output. Deleting the check turns the naming test red |
| User cancels without losing prior valid work | **PASS** | Cancellation is observed at stage boundaries, so a stage in flight finishes and its verified output is kept |

**Honest limits.** Three of the four placeholder conditions are textual heuristics: prose that reads well can still pass. Reference closure is the one carrying weight and is verified separately. The run-wide execution cap is unreachable in a clean run; the test demonstrates the real path where an earlier stage has already spent the allowance.

## Cross-line integration

Two agents built LC-P1-06 and LC-P1-07 without reading each other. Three seams resulted, all closed:

| Seam | Resolution |
|---|---|
| `StageCheckpoint` and `runtime.Checkpoint` were not supersets — no `through_seq`, no failure status | `recovery/stages.py` bridges by looking the stage name up in the store. `through_seq` is a **parameter**, because only the transaction that wrote the events can say how far the log got |
| The frozen `Event` had no `payload`, though ADR-0003 C1 requires one | [ADR-0007](../adr/ADR-0007-event-payload.md). The store's old `payload` column held the whole event and was renamed `document`; a real one was added beside it |
| Provider capability and permission capability share nothing (ADR-0006) | Carried, unchanged. The outbound-consent bridge is still not built |

## Defects found and fixed during G2

| Defect | How it surfaced |
|---|---|
| `# type: ignore` needed on Windows, reported **unused** on Ubuntu | CI on the second platform |
| Migration 0002 reported success and changed nothing — twice, once with `recreate="always"` | Running it, then checking whether the column moved |
| `.gitignore` did not cover `*.db` | The default Alembic URL leaving files in the tree |
| The head-revision test hardcoded `0001` after its own docstring said that would fail for the wrong reason | Reading the test against its claim |
| `test_at7_crash_matrix_subprocess` flaked at two runs in five | Chased to `TerminateProcess` outliving the child's SQLite shared-memory teardown on Windows; the fix discards the orphaned sidecars |
| My own first two flake diagnoses were wrong — basetemp reuse, then pragma order | The second was disproved by the failure rate not moving, which is why it is recorded |

## Independent cross-review

A reviewer who did not implement any of this ran this document against the code. **This is internal cross-validation by two agents, not an external independent audit**, and is not evidence of one.

It worked from `a361a7c`, re-ran all four gates itself, and mutated code in a scratch copy rather than in the tree.

- **All 17 clauses CONFIRMED.** No clause's named test was found to pass vacuously, and no PASS row was contradicted by the code.
- **All three disclosures above verified TRUE** — two of them by applying the mutation and re-running the suite.
- **No implementation defect and no test defect was found.** Six issues were raised and all six were in documentation.
- One of the six could not be fixed because it is not a defect: on Windows pytest exits 0 while an `atexit` cleanup callback prints a `PermissionError`.

Five were corrected in this document's branch: two misattributed citations (the `seq` figure and which test actually constrains timestamp-keyed invalidation), a stale test count in `G2-evidence.md` that contradicted this file, an unreproducible "32 tests green" figure replaced with the mutation a reader can run in one command, and a demonstration that told the reader a capability was absent from the very next file.

**The reviewer's own summary was wrong once, and that was caught by re-measuring.** It reported that all seven tests in `test_store_concurrency.py` pass with `BEGIN IMMEDIATE` downgraded. Six do; the seventh — `test_the_write_lock_is_taken_before_the_first_read` — is the SQL assertion the disclosure says is load-bearing, and it fails, as it must. Its own docstring anticipates exactly this: *"If this assertion ever fails, the concurrency tests above are passing for a reason that has nothing to do with the design."* A review is evidence only after someone has checked it, which is the same standard applied to the work it reviews.

## Gate verdict

**G2: PASS WITH NOTES.**

All six LC-P1-06 acceptance clauses, all five LC-P1-07 clauses and all six LC-P1-05 clauses have executable evidence at `a361a7c`, and both demonstrations run green. The notes are the three recorded limitations above (the concurrency assertion's true load-bearing element, the placeholder heuristics, the unreachable run cap) plus the open items below, none of which is a Phase 1 blocker.

**Not proposed as closed silently:** the items below are carried, not deleted.

## Open items carried beyond G2

| Item | Owner | Note |
|---|---|---|
| `ArtifactLedger` is in-memory | G3 or later | LC-P1-07's ledger does not survive a restart; the store does |
| `ApprovalLedger.consume()` does not resolve the capability against the registry | an ADR | Carried from G1. Only `policy.evaluate()` turns an unknown id into DENY, and nothing enforces that a caller evaluates first |
| Path-guard tests ran on Windows only | G3 | POSIX ADS and case semantics unverified. One test of this class was already fixed when CI found it on Ubuntu |
| ADR-0006's outbound-consent bridge | G3 | Both modules exist; the bridge is not built |
| Structured-output capability unmeasured | G3 | Both probes fail in pydantic-ai's client layer before a request is sent |
| **PyMuPDF is AGPL/commercial dual-licensed** | **G3, before LC-P1-08** | Named by LC-P1-08 and constraining a future MIT release. Needs a decision, not a workaround |
