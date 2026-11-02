# LC-P1-06 — The artifact ledger made durable

**Work order:** LC-P1-06 (checkpoint, operation reconciliation and revision) —
the debt G2's acceptance recorded, not one of the work order's own clauses
**Gate:** G2
**Subject:** this branch over `c19a83d`
**Date:** 2026-11-02
**Verdict:** the debt is paid locally; one measurement is outstanding (the CI
shard cost for the new test file, which must come from a runner)

## The debt and where it was recorded

`ArtifactLedger` has enforced two properties since LC-P1-07: provenance at write
time (an artifact is only recorded with a lineage matching the digests the
orchestrator handed over) and integrity at read time (the canonical digest is
recomputed on every `load`). Both are real, and both lived in a list in the
process that made them. A restart lost the record; a second reader in another
process saw nothing.

G2's acceptance carried the gap rather than dropping it. It is stated, in the
same words, in five places:

- `docs/acceptance/G2-acceptance.md:123` — open item, owner "G3 or later";
- `docs/handoff/CURRENT.md:1509` — carried item;
- `docs/RELEASE-NOTES.md:303` — §2.12 limitation;
- `docs/THREAT-MODEL.md:779` — §6.12 limitation;
- `docs/PHASE_1_WORKORDERS.md:42` — G2's carried notes.

Those five statements now say the item is closed, and point here.

## What now exists

| Piece | Where |
|---|---|
| The table | `artifact_ledger_entries`, migration `0022_artifact_ledger.py` |
| The store | `SqliteArtifactLedgerStore` in `src/labcairn/db/ledger.py` |
| The seam | `ArtifactLedger(store=...)`, `ArtifactLedgerStore` protocol, `InMemoryLedgerStore` in `src/labcairn/skills/ledger.py` |
| The refusal | `LedgerAlgorithmError` in `src/labcairn/skills/errors.py` |
| Orchestrator wiring | `Orchestrator(..., ledger=...)` in `src/labcairn/skills/execution.py` |

### Design choices

**A facade over a store, not a second ledger class.** `ArtifactLedger`
delegates storage to an `ArtifactLedgerStore` (append, entries, current) and
keeps the type check, the lineage read, the digest computation and the
read-time comparison in one place. A `StoreBackedArtifactLedger` that copied
those checks would have been two implementations of the property, and the
second one would drift. `ArtifactLedger()` still constructs
`InMemoryLedgerStore`, so every existing caller behaves exactly as before.

**The store does no verification.** It writes and reads bytes. The digest
comparison stays in `load` and `verify_all`, which run against whatever the
store returned. A store that repaired a mismatch would be a second authority
over the property the ledger exists to hold.

**The stored payload is the canonical JSON the digest is over.** `append`
writes `artifact.json_canonical()`; `entries` parses that payload back into the
declared model and the ledger re-hashes the model. For an untampered row those
bytes are identical, so "recompute and compare" is a comparison of stored
bytes, not of two serialisers' opinions. No second digest algorithm was
introduced.

**`digest_algorithm` is stored, and a foreign algorithm is refused.** A
durable row outlives a release. Comparing an old algorithm's digest to today's
would produce a mismatch and call it tampering; the honest answer is that the
check cannot be performed, so `LedgerAlgorithmError` says that.

**`ledger_id` scopes the table.** The orchestrator's contract is one ledger per
run; the table's `ledger_id` is what keeps two runs in one database from
reading each other's history. The default id is for a caller with one ledger
per database — the arrangement every witness here uses.

**No `UNIQUE(stage)`, by design.** A re-run is a fact to keep, not a conflict
to refuse. History is every row; `by_stage` is the latest row per stage in
insertion order. There is no second table that could disagree with the first.

### Which callers changed, and which did not

- `Orchestrator.__init__` gained an optional `ledger` parameter. Omitted means
  `ArtifactLedger()` — the previous behaviour, unchanged.
- `ArtifactLedger` changed from a dataclass with two public list/dict fields to
  a class whose `history` and `by_stage` are properties over the store. The
  in-memory store returns its lists live, so the existing substitution
  witnesses in `tests/test_skill_ledger.py` (which replace an entry in
  `by_stage`) still exercise the same attack. No constructor call in `src/` or
  `tests/` passed `history=` or `by_stage=`; none does now.
- No production code constructs an `Orchestrator` in this tree. When one is
  added, the durable path is
  `ArtifactLedger(SqliteArtifactLedgerStore(factory, ledger_id=str(run_id)))`
  passed as `ledger=`. Nothing silently opts in.

## Witnesses

`tests/test_artifact_ledger_persistence.py`, seven tests. Each reads through a
*second* ledger instance or a reopened engine, so a ledger answering from a
process-local cache would not pass.

| # | Test | Property |
|---|---|---|
| 1 | `test_a_new_instance_on_the_same_database_loads_the_same_entry` | record in one instance, load in another: same artifact, same digest |
| 2 | `test_history_and_by_stage_survive_a_restart` | engine disposed, a new engine on the same file: history, `by_stage` and `completed_stages` are there, and the reloaded artifact re-hashes |
| 3 | `test_verify_all_reports_a_payload_changed_in_the_table` | the payload column is edited behind the ledger's back; `verify_all` names the stage and `load` raises `ArtifactSubstitutedError` |
| 4 | `test_a_second_record_for_a_stage_appends_and_moves_by_stage` | two records for one stage: history has both, `by_stage` is the latest |
| 5 | `test_the_stored_payload_is_the_canonical_json_the_digest_is_over` | the stored payload equals `json_canonical()` (non-ASCII included) and the digest is `artifact_digest`'s |
| 6 | `test_an_entry_written_under_another_algorithm_is_refused` | a row whose algorithm is not this build's is refused, not compared |
| 7 | `test_two_ledgers_on_one_database_do_not_see_each_other` | `ledger_id` is the scope of a ledger |

### Mutation checks

Each mutation was applied to the product code, the test file was run, and the
file was restored. A mutation that leaves the suite green is not evidence.

| Mutation | Result |
|---|---|
| `append` does not add the row | 7 failed |
| `verify_all` returns no mismatches | test 3 failed |
| `append` stores `model_dump_json()` instead of `json_canonical()` | test 5 failed |
| the stored `digest_algorithm` is not consulted | test 6 failed |
| `entries` ignores `ledger_id` | test 7 failed |
| `append` deletes the stage's existing rows first | test 4 failed |

## What was actually run

Commands were run from the worktree with `PYTHONPATH` pointing at the
worktree's `src` (the editable install otherwise imports the main checkout),
and `TEMP`/`TMP` under `E:\labcairn-local\tmp`.

| Check | Result |
|---|---|
| the new file, alone | 7 passed |
| `test_artifact_ledger_persistence`, `test_skill_ledger`, `test_store_migrations` | 41 passed |
| the skills, store and identifier neighbourhoods | 286 passed |
| the whole suite (`pytest tests`) | 4593 passed, 5 skipped, 13 failed, 8 errors — classified below |
| `ruff check .` / `ruff format --check .` | clean, 417 files |
| full `mypy` with the repository's configured file set | clean, 378 source files |
| `test_ci_shard_coverage.py`, `test_evaluation_harness.py` | **1 failed, 86 passed** — the failure is the expected missing shard cost, below |

The 13 failures and 8 errors in the whole-suite run are none of them about the
ledger:

- **2 were this branch's own**, and were fixed before the branch was committed:
  `test_application_layer.py` needed `labcairn.db.ledger` recorded as a store
  module, and `test_status_consistency.py` caught a relative link in
  `CURRENT.md` that pointed one directory too shallow. Both pass on re-run.
- **1 is the expected shard-cost failure** (`test_the_recorded_costs_cover_every_test_file`).
- **2 were a harness mistake in this session, not the tree**:
  `test_evidence_retrieval.py` ran with `TEMP` pointing at a subdirectory that
  did not exist, and SQLite reported `unable to open database file`; both pass
  when `TEMP` names an existing directory.
- **8 errors and 8 failures are this machine's network and clone witnesses**:
  `test_no_reference_leakage.py` (8 errors, `uv build` cannot reach PyPI),
  `test_outsider_path.py` (6) and `test_readme_accuracy.py` (2) — the same
  environmental set the repository's own records describe for a worktree with
  no working PyPI route. They fail identically for reasons unrelated to this
  branch.

The mutation runs were six separate invocations of the new file; each is
recorded above by its failing count.

## What is not done

**The shard cost for the new test file is not measured.**
`tests/test_ci_shard_coverage.py::test_the_recorded_costs_cover_every_test_file`
is red, naming `test_artifact_ledger_persistence.py`, because a cost may only
come from a runner and this session did not start one (the repository's rule:
no push to start CI, no pull request from a session). The file is registered in
both platform partitions of `.github/ci-shards.json`; the next runner run's
log is the input to `python .github/remeasure_shards.py <run-id>`, which will
write the cost and rebalance. No local number was guessed.

**The default ledger is still in memory.** That is deliberate: the brief for
this work was to make durability possible without silently changing existing
callers, and there is no production `Orchestrator` caller to switch. The
durable path is a parameter, documented on `Orchestrator`.

**A payload that no longer parses is not a `LedgerMismatch`.** If the stored
bytes stop being valid JSON for the declared kind, the store's parse fails with
the model's validation error. `verify_all` reports digest mismatches, not parse
failures; both are failures, but only the digest case is reported in the
`LedgerMismatch` shape. This is stated rather than smoothed over.

**Concurrent tampering is witnessed only across reads, not during one.** Each
`entries()` call opens and closes its own session, so a committed change is
seen at the next read by construction; no test drives two processes editing the
same row while a ledger instance is open.

## Registrations

Three, as the repository requires for a new test file:

- `pytestmark = pytest.mark.integration` in the file;
- both platform partitions of `.github/ci-shards.json` (shard 4 on each);
- `tests/evaluation/manifest.py`, gate class `integration`, clause
  `artifact-hashes` — the same clause as `test_skill_ledger.py`, because it is
  the same property against a durable store.
