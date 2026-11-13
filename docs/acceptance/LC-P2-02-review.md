# LC-P2-02 — independent review of the acceptance record
**Line numbers.** The `file:line` pointers in this record name the lines as they stood when it was written; the tree has moved since. Follow the sentence, not the number.  
**Record reviewed:** `docs/acceptance/LC-P2-02-acceptance.md` (restart-durable
consent), as it stands in this branch.
**The tree reviewed:** `e10359e` (*citation identity: a record can carry an
identifier, and a claim may not rest on one nothing resolved*), the branch tip
this review worked in.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreter:** the repository's shared virtualenv at `E:\LabCairn\.venv`
(CPython 3.12), with `PYTHONPATH` pointed at this worktree's `src/` so that
`import labcairn` resolved to `E:\LabCairn\.claude\worktrees\awesome-hopper-3a1b23\src\labcairn\__init__.py`
— verified before any run, because the venv's own editable install names the
main checkout's `src/` and a run without the override measures a different tree.
Each run had its own `--basetemp` under `E:\labcairn-local\tmp`, outside the
repository.

**Method.** The record's mutation table (§4) was re-applied one mutation at a
time against this worktree; every mutation's diff was read before the witness
ran, and the file was restored with `git checkout -- <file>` afterwards, with
`git status` checked clean. Verdicts below are results of runs, not readings.

## 1. What was re-applied, and what happened

**Baseline.** `tests/test_approval_binding.py` — 8 passed;
`tests/test_approval_crash_matrix.py` together with it — 10 passed.
`ruff check` on the affected files: clean.

| # | The mutation, as the record states it | Where it was applied | Witness run | Result |
|---|---|---|---|---|
| 1 | `policy_unchanged` forced to `True` | `src/labcairn/db/repository.py:1745` (the comparison with `row.grant_policy_digest`) | `test_the_spend_reads_the_binding_from_the_row`, `test_a_changed_policy_does_not_satisfy_the_old_approval` | **Both red** — the second with `DID NOT RAISE ApplicationRefusedError`, exactly the spend going through that the row's digest should have refused. Matches the record. |
| 2 | the conditional `UPDATE` loses its `WHERE state = 'granted'` | `src/labcairn/db/repository.py:1775` (`.where(ApprovalRow.state == ApprovalState.GRANTED.value)` deleted) | all of `tests/test_approval_binding.py` + `tests/test_approval_crash_matrix.py` | **Survived** — 10 passed. Matches the record, which reports this survivor rather than hiding it. |

The record's stated reason for mutation 2's survival was verified against the
code: the Python guard at `src/labcairn/db/repository.py:1741` (`row.state == CONSUMED` →
`NoSuchApprovalError`) runs before the write, so every witness the suite has
is refused before the conditional write is reached. The record's further claim
— that **no witness covers the two-connection interleaving window** — was
checked and still holds in this tree: every test in the crash matrix builds
one session (`tests/test_approval_crash_matrix.py:98,141,176`); no test starts
two connections and interleaves their reads and writes. The gap is real and
still open, and the record says so.

## 2. What was checked against the store, not against the tests

- **The migration exists and is what the record names.**
  `migrations/versions/0014_approval_binding.py` adds `grant_policy_digest`
  (`String(64)`, nullable — a pre-revision row has no digest, and the spend
  refuses it) and `bound_sources` (JSON, `NOT NULL`,
  `server_default '[]'`). `src/labcairn/db/models.py:456,459` carries both.
- **`NULL` `bound_sources` is refused by the schema, not by an adapter.** A raw
  `INSERT` into a database migrated to head wrote the illegal row and the
  schema refused it: `NOT NULL constraint failed: approvals.bound_sources`.
  This is the project's own rule that a constraint claim is asserted against
  the schema itself.
- **The empty list is a fact, not an absence.** The raw-`INSERT` check for the
  empty list was blocked by the store's own foreign-key chain
  (`approvals → operations → stages → runs`), which a hand-built row would
  have to satisfy whole; rather than rebuild four tables' worth of parents,
  the product path is the witness: `tests/test_approval_binding.py:146`
  asserts `row.bound_sources == []` after a grant with no sources, and that
  test passes on this tree — the empty list is written, read back, and is
  therefore a stored fact.

## 3. What was checked as claims about the code

- **`consume` reads the binding from the row.** The method takes
  `current_policy_digest` as a *recomputation input* (it is the digest of the
  policy **as the arguments are right now**), and compares it with
  `row.grant_policy_digest` — the row's own value decides, which is what A2
  claims and what mutation 1 proved.
- **The surfaces spend from the DB-backed store.** `cli/workspace.py` builds
  `ApplicationContext` with `ledger=StoredApprovalLedger(session)` on the
  session-scoped context; `test_the_surfaces_spend_from_the_store` passes.
- **A8, the eight refusal reasons.** `test_the_eight_refusal_reasons_are_unchanged`
  passes; the reasons live in `src/labcairn/application/refusal.py`.

## 4. What could not be checked, and why

- **§5.1's "342 passed, 1 skipped" affected set.** The record does not list
  which files make up that set, so the number cannot be re-run on this tree
  — and this tree is several commits past the one the record was measured
  on. The claim is an honest local measurement of a tree this review does
  not have; it is not evidence about this tree, and the record does not
  pretend it is (it says the first CI run is the full-suite measurement).
- **The crash matrix's child-interpreter mechanics** (`os._exit`, two child
  interpreters, one database file) were run, not re-derived: the two crash
  tests pass on this tree, which is what the record needs.

## 5. Findings

1. **(Note) The record's §1 line reference `src/labcairn/cli/workspace.py:636` has drifted.**
   In this tree that line is inside the context builder that now yields
   `StoredApprovalLedger(session)` — the *fixed* state, not the in-memory
   ledger the sentence describes. The sentence describes the gap as it was,
   and the row the fact now lives in is the fix; no claim depends on the
   number, but a record that cites line numbers ages faster than one that
   cites names.
2. **(Note, accepted by the record itself) The double-spend window between the
   Python guard and the conditional `UPDATE` has no witness.** The record
   states this as a gap rather than covering it with a name, which is the
   honest form; this review confirms the gap still exists on this tree.
   Mutation 2 surviving is the direct measurement of it.
3. No claim was found with nothing behind it. Every clause in §2 named a test
   that exists under that name and passes on this tree.

## 6. Verdict

**Holds.** Both mutations re-applied with the outcomes the record states —
one red on the witnesses it names, one a survivor the record reports as a
survivor. The schema claim was verified against the schema itself. The one
witness gap (the interleaving window) is stated in the record and confirmed
open.
