# G2 — Acceptance evidence (LC-P1-05, LC-P1-06, LC-P1-07)

**Status:** implemented and merged; **G2 not proposed as closed** — see "The clause that is not met".
**Merged:** LC-P1-05 `917f844` · LC-P1-06 `3c2269e` · LC-P1-07 `a6c6671` · demo PR open
**Date:** 2026-10-16

## What was built

| Work order | Package | Tests |
|---|---|---|
| LC-P1-05 SQLite task store and transactional events | `db/`, `migrations/` | 75 |
| LC-P1-06 checkpoints, crash recovery, reconciliation | `recovery/` | 108 |
| LC-P1-07 `research-report` Skill contract and stages | `skills/` | 213 |
| exit demonstration | `examples/g2_exit_demo.py` | 14 checks |

**993 passed, 2 skipped.** ruff, ruff format and mypy `--strict` clean across 112 source files. LC-P1-06 and LC-P1-07 were built by two agents that never read each other's work, which is why the integration seam below exists.

## The exit demonstration

`uv run python examples/g2_exit_demo.py` — exit 0, temporary database, no network, no credential.

```
1. Create a task, a run, and a stage; write a result
   [ok] intent is durable before any file is touched — operation_intent committed
   [ok] the file landed and the confirmation committed
   [ok] a stage-boundary checkpoint was recorded — checkpoint_created
   [ok] this task's sequence is contiguous from 1 — seq=[1, 2, 3, 4]

2. Kill the process mid-flight, on a real child
   [ok] the child is still running before the kill
   [ok] the kill succeeded — rc=0
   [ok] the process is gone and ran no cleanup — exit=1

3. Restart against the same database file and resume
   [ok] the task identity survived the restart
   [ok] its event history is intact
   [ok] the artifact is still on disk and unmodified
   [ok] nothing is in doubt, so nothing needs reconciling
   [ok] the confirmed artifact was not redone

4. A pending approval is still pending
   [ok] an unapproved write stays unapproved across the restart — state=awaiting_approval
   [ok] and it wrote nothing
```

The kill is genuine. The child writes a sentinel, prints ready, and sleeps; the parent waits until the sentinel exists **and** the child is still alive before terminating it, so a child that died early cannot be mistaken for one killed in the window. `taskkill /F` is `TerminateProcess`: no `finally`, no `atexit`, no buffer flush — there was no cleanup path a graceful shutdown could have taken.

## The load-bearing decisions

**`seq` is per-Task and is not the rowid.** Verified from outside the suite: two interleaved Tasks each get `seq` 1..5 while their rowids interleave as `1,3,5,7,9` and `2,4,6,8,10`. Those cannot both hold if `seq` were the rowid. After disposing the connection pool and reopening from the file alone, the next event took 6, not 1.

**`UNCERTAIN` is a state recovery enters, not one it assumes away.** Probing is over bytes: absent and a matching SHA256 are decidable; a different hash, a directory, or an unreadable target are not. **Unreadable is deliberately CONFLICT** — it is not evidence that nothing landed, it is evidence that we cannot tell. CONFLICT falls back to `UNCERTAIN` rather than `FAILED`, because `FAILED` would read as retryable to a later round and this one needs a human.

**The third crash costs zero reconciliation.** After commit, before the UI receipt: nothing enters `UNCERTAIN`, no reconciliation events are written, `replay()` raises with a zero call count, the file's mtime and hash are unchanged, and a reconnecting client reads exactly the missed tail by `after_seq`. The evidence that the transaction boundary is what makes it free: **a mutation that pulls the artifact write out of the confirmation transaction turns exactly that test red and nothing else.**

## Findings from the two cross-reviews

**A permission bypass by filename case** (G1, fixed): `evaluate()` returned on the first spelling that matched any rule, so a request hitting `ALLOW **` was granted without the resolved spelling — carrying the deny — ever being evaluated.

**Two capability vocabularies with an empty intersection** (G1, decided): `providers.Capability` and `security.CapabilityId` shared nothing, so no code connected an outbound transmission to `MODEL_REQUEST`. ADR-0006 decides they stay disjoint permanently.

**A cost ceiling that depended on callers remembering an argument** (G1, fixed): `RunLedger(priced=True)` was the default while its own docstring argued every ledger should be unpriced.

**A usage-capture false negative** (found by the real provider smoke): the sniffer read `response.content` at transport level, where httpx has not loaded the body, so `ResponseNotRead` was swallowed and **every** endpoint looked like it reported no usage. Safe-when-broken is still broken — it also made the whole provider layer unusable.

## Defects the gates found, which reading would not have

| Defect | Found by |
|---|---|
| `# type: ignore` needed on Windows, reported *unused* on Ubuntu | CI on the second platform |
| `os.utime` needed to prove source-change detection is not timestamp-based | the agent, writing its own test honestly |
| 75 Alembic `DeprecationWarning`s | running the suite |
| `.gitignore` did not cover `*.db` | the default config leaving files in the tree |
| `ResumeCoordinator` needed a session `TaskStore` did not expose | wiring the exit demonstration |
| A concurrency test that measured nothing | mutation testing: deleting the guard left 32 tests green |

## Cross-line integration seams

Two agents built LC-P1-06 and LC-P1-07 without reading each other. The result:

```text
runtime.Checkpoint     : ... through_seq, material_hashes ...
skills.StageCheckpoint : ... status, attempt, input_digests, output_digests ...
```

**Neither is a superset of the other.** `StageCheckpoint` has no `through_seq`, which ADR-0003 C1 names as the only ordering and which `ResumeCoordinator.plan_resume` works from; `Checkpoint` cannot express a failed or blocked stage. Both exist in the tree and import cleanly, and the conversion between them is not written.

## The clause that is not met

**The demonstration proves recovery after a *confirmed* side effect. It does not prove recovery from an *unresolved* one** — the `UNCERTAIN` path, where the process died between writing and confirming and the system genuinely cannot tell whether the effect landed.

That path is covered by `tests/test_recovery_crash_matrix.py` (AT-2, AT-2b, AT-6, AT-7), which injects faults at `AFTER_WRITE_BEFORE_CONFIRM` and asserts that the operation enters `UNCERTAIN`, that replay is refused, and that a probe resolves it. The suite's coverage is real; the **end-to-end demonstration of it is missing**, because driving it needs a side effect whose probe outcome the demo can control.

I am not proposing G2 closed on the strength of a suite the demonstration does not exercise. Closing it needs either that demonstration or an explicit decision that the fault matrix is sufficient evidence.

## Open items carried forward

| Item | Severity | Note |
|---|---|---|
| `UNCERTAIN` recovery not in the exit demonstration | **blocks close** | Covered by the fault matrix; needs an end-to-end demo or a decision that the suite suffices |
| `StageCheckpoint` cannot convert to `runtime.Checkpoint` | integration | The two lines were built in parallel; conversion is the next piece of work |
| The frozen `Event` has no `payload` field | technical debt | ADR-0003 C1 requires it. Has blocked real work twice: LC-P1-05 stores the whole document as JSON, LC-P1-06 cannot persist `confirmed_by_probe` literally |
| `ArtifactLedger` is in-memory | persistence | LC-P1-07's ledger does not survive a restart; the store does |
| `ApprovalLedger.consume()` does not resolve the capability | defence in depth | Carried from G1 |
| Path-guard tests ran on Windows only | coverage | Carried from G1; one test of this class was already fixed when CI found it on Ubuntu |
| ADR-0006's outbound-consent bridge | deferred | Both modules exist; the bridge is not built |

## What is deliberately not here

Material parsing, retrieval, the evidence ledger, analysis and plots — LC-P1-08 through LC-P1-11. **There is still no research capability of any kind**, no CLI, no server, and no model call that leaves the machine. G2 is a durable, recoverable floor, not a product.
