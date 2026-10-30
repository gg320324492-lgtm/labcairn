# LC-P2-02 — Restart-durable consent: acceptance

**Work order:** LC-P2-02 (restart-durable consent) · **Subtasks:** T00–T05.
**Task breakdown:** [`docs/plans/LC-P2-02-task-breakdown.md`](../plans/LC-P2-02-task-breakdown.md)
**Status of the work order:** **implemented and measured**, and **not independently reviewed** — see §5.
**Measured:** 2026-10-30 on the tree this record was written at, on Windows 11 (AMD64),
Python 3.12.13.

**What this is.** The operation half of the gate LC-P2-01's model path has to pass:
an approval that **survives a restart**, is **single-use across it**, and reads
the two facts ADR-0003 C4 needs — the policy's answer at the grant, and the
source hashes it was bound to — **out of the row** rather than out of an argument.

**What this is not.** It is not an identity model, it does not make the
material-purpose grant durable (LC-P2-06's table already is), and it does not
make a paid call safe to repeat: it makes it single-use, which is what LC-P2-01
needs and where LC-P2-01's unknown-state rule begins.

---

## 1. The gap, and what closed it

**The consent was in memory.** `ApprovalLedger` held the grant in a dict and its
own docstring said so: it was the mechanism *for one process*. Every surface
built a fresh one (`cli/workspace.py:636`), so a restart emptied it and the
spend failed closed with `APPROVAL_MISSING` — safe, and not what a consent is
for: a person told "approved" had to ask again because a process restarted.

**And the row carried none of the two facts that make an approval mean
something.** `consume` took the policy digest **as an argument**, so a caller
could present a digest nobody had recorded and the store had nothing to compare
it with.

**It is closed in two places, and neither is a copy of the other:**

| The fact | Where it lives now |
|---|---|
| The policy's answer at the grant | `approvals.grant_policy_digest`, written by `grant_approval` (`0014_approval_binding.py`) |
| The sources the consent covered | `approvals.bound_sources`, written as JSON; **empty is a fact**, not an absence |
| Who owns the state | the row; the event stream owns the history (§2.3) |
| What a surface hands the layer | `blocked` → `approval_ledger_for(store)`, a `StoredApprovalLedger` on the surface's own session |

**And the spend is one conditional `UPDATE`.** Two processes racing one
approval produce exactly one match; the second finds no row in `GRANTED` and
that is the double spend refused **from the row**.

## 2. The ten acceptance clauses

Every clause in the task breakdown's §4 names a test, and the test exists.

| # | The clause | The test |
|---|---|---|
| A1 | The approval row carries the grant-time policy digest and the bound sources | `test_the_approval_row_carries_the_grant_time_binding` |
| A2 | The spend reads those two **from the row**, and `consume` no longer takes them as arguments | `test_the_spend_reads_the_binding_from_the_row` |
| A3 | A policy that changed between the grant and the spend does not satisfy the old approval | `test_a_changed_policy_does_not_satisfy_the_old_approval` |
| A4 | One operation writes the row, the event, or both — and never emits twice | `test_no_approval_operation_emits_twice` |
| A5 | The surfaces spend from the DB-backed store, on the forked session | `test_the_surfaces_spend_from_the_store` |
| A6 | A crash between the grant and the consume leaves the **second** spend refused **from the row** | `test_a_crash_between_grant_and_consume_refuses_the_second_spend` |
| A7 | A restart never turns a spent approval back into a grantable one | `test_a_grant_outlives_the_process_that_granted_it`, `test_a_restart_does_not_un_spend_an_approval` |
| A8 | The eight refusal reasons are unchanged, and a restart does not soften any of them | `test_the_eight_refusal_reasons_are_unchanged` |
| A9 | The single-use guarantee's existing witnesses are still red under the same mutations | see §4 — **one of them is not** |
| A10 | The ledger is gone, or it is a cache that cannot outlive its row | `test_the_ledger_cannot_outlive_its_row` |

**A6 and A7 are measured across a real process boundary.** Each test starts a
child interpreter that grants (and, in A6, spends) and then calls `os._exit`;
the parent builds a fresh session and a fresh ledger against the same file. That
is what a restart hands a surface, and no in-memory ledger can pass it.

## 3. The surfaces

| Surface | What it hands the layer |
|---|---|
| The CLI (`cli/workspace.py`) | `StoredApprovalLedger(session)` in the one construction site |
| The local API (`api/routes.py`) | `approval_ledger_for(forked)` — **on the request's own forked session** |
| `create_task` (`application/tasks.py`) | `StoredApprovalLedger(store.session)`; it cannot have an approval, and the shape is the same anyway |

**The API may not reach the store directly**, and a test holds that
(`test_no_module_of_the_api_reaches_the_store`). So the ledger is reached
through `labcairn.application.context.approval_ledger_for`, and the import rule
stays intact.

## 4. The mutations, and what each broke

| # | The mutation | What went red |
|---|---|---|
| 1 | `policy_unchanged` is forced to `True` | `test_the_spend_reads_the_binding_from_the_row`, `test_a_changed_policy_does_not_satisfy_the_old_approval` |
| 2 | the conditional `UPDATE` loses its `WHERE state = 'granted'` | **nothing** — see below |

**Mutation 2 survived, and it is reported as a survivor rather than as a
success.** The Python guard (`row.state == CONSUMED` → `NoSuchApprovalError`)
runs before the `UPDATE`, so every witness the suite has is refused by the guard
and never reaches the conditional write. **The conditional `UPDATE` is a second
defence for two processes that both read `GRANTED` before either writes**, and
there is **no witness for that window**: a test that starts two connections and
interleaves their reads and writes does not exist. That is a gap in the
witnesses, stated here rather than covered by a name.

**Mutation 1 is the clean one**, and it is the one that matters: the row's
recorded digest is what decides, and forcing the comparison open turns two
witnesses red at once.

## 5. What was measured

| | |
|---|---|
| **The affected set** | see §5.1 |
| **The crash matrix** | two child interpreters, one database file, `os._exit` rather than a return |
| **Lint and types** | `ruff check .`, `ruff format --check .` and `mypy` are clean |
| **The shard table** | the two new test files are apportioned, because no runner has executed them — the second step is the next CI run's |

### 5.1 The affected set

```
342 passed, 1 skipped, 0 failed, in 9 minutes 8 seconds
```

**The skip is the project's accepted POSIX permission-bit case**, and none of
the files in this set is new to the suite.

**The full suite has not been run on this tree**, and this record says so
rather than presenting a subset as the whole. The first CI run on the branch is
the full-suite measurement, and the line above is the local one.

## 6. Limits, and what is left for the reviewer

- **The review is not independent**, and the board's rule is not discharged.
- **The concurrent-spend window has no witness** (§4, mutation 2).
- **The in-memory `ApprovalLedger` still exists.** It is what the G2 witnesses
  in `tests/test_application_approvals.py` and `tests/test_analysis_service.py`
  build, and those tests pass unchanged. §T04 asks for them to be re-expressed
  against the store; **the two new files carry the store's version of the same
  properties**, and the older files have not been rewritten.
- **The bound sources are always empty in this round**, because no caller binds
  a source to an approval yet. The column and the read exist; the write path
  that fills it is the caller's, and no caller in the tree fills it.
- **Rows granted before `0014` keep a null digest**, and the spend refuses them
  rather than inventing one — a record whose policy answer nobody wrote down is
  not one the store can say still holds.
