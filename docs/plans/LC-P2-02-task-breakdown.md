# LC-P2-02 — Restart-durable consent: the approval that survives a restart — task breakdown

**Work order:** LC-P2-02 (restart-durable consent) · **Status:** drafted
2026-10-30, **not yet dispatched**. **Priority:** the adjustment of
2026-10-30 (P2-AMD-01) puts this **first among the Phase 2 work orders**,
because it is the operation half of the gate LC-P2-01's model path has to
pass.

## 0. How to read this document

**This is a contract, not a suggestion.** §4 names the acceptance clauses
and, for each, the test that carries it; a work order that ships without
those tests has not met the contract, whatever the suite says.

**And this one reopens something a gate already accepted.** G2 closed
LC-P1-05 with a verdict, and the consent internals it accepted are
**reworked here**. That is not a new feature and not a criticism of G2: the
ledger was accepted as the mechanism *for one process*, and this work order
makes the mechanism mean the same thing **across a restart**. §1.2 says
what is kept and what changes, and §5 says what this work order must not
touch.

## 1. Goals and boundaries

### 1.1 What LC-P2-02 must produce

**A granted approval that is single-use across a restart**, and a store
that reads the two facts that make a consent mean something **out of the
row** rather than out of an argument:

- the **policy digest** — what the policy said at the moment of the grant;
- the **bound sources** — which material the consent was bound to.

**And the surfaces spend from the DB-backed store.** Today they build an
in-memory `ApprovalLedger` (one construction site,
`src/labcairn/cli/workspace.py:636`, inside the `application_context`
builder at `:609`), so after a restart the ledger is empty and the spend
fails closed with `APPROVAL_MISSING` — **safe, but not what a consent is
for**: a person who was told "approved" should not have to ask again
because the process restarted.

### 1.2 Already done — removed from scope

- **The approval ledger's own semantics.** `src/labcairn/security/approval.py`
  — the in-memory ledger, its eight refusal reasons, its single-use
  guarantee. **The semantics are kept; the durability is what is added.**
- **ADR-0003 C4's eight refusal reasons** (seven at G2's close;
  `capability_unregistered` joined on 2026-10-27 in `26ab4cb`). **They
  are not softened.**
- **The event stream's shape.** `UnitOfWork.emit` and the per-Task gapless
  `seq`. What changes is **who emits what** (§3.2), not the stream.
- **The provider boundary, the budget and the probe** — LC-P2-01's
  material. This work order does not touch them.

### 1.3 Explicitly not in scope

- **The model call itself.** LC-P2-01.
- **The material-purpose grant.** LC-P2-06's `access_grants` and its
  `external_transmit` check, which is **the other gate** and already
  exists. **The two gates are separate permissions and this work order
  touches only the operation one.**
- **A multi-person identity.** ADR-0003 and ADR-0015 D6's conditions are
  open; a restart-durable consent is not an identity model.
- **Turning a spent approval back into a grantable one.** That is the
  failure this work order exists to prevent.

## 2. The decisions that shape it

### 2.1 The two facts are read from the row, not passed in

`ApprovalStore.consume` takes the policy digest and the bound sources
**as arguments**. That is the whole gap: a caller can present a digest
that was never recorded, and the store has nothing to check it against.
**After this work order, the row carries them and the store reads them.**

**And a mismatch is a refusal, not a recomputation.** If the row's digest
does not match the one recomputed at the moment of use, the approval does
not cover this request — and that is one of ADR-0003 C4's existing
refusals, not a new one.

### 2.2 The grant-time digest is not the use-time digest

**A policy that changes between the grant and the spend must not be
satisfied by the old answer.** So the row keeps **both**: the digest the
policy gave **when the approval was granted**, and the one recomputed
**at the moment of use**. The spend is allowed when they agree, and the
row records which one it was.

### 2.3 One row, one owner

**The event stream and the row must not both own the same fact.** Today
`request` / `grant` / `consume` can emit into the append-only event table
**and** write the row, and a reader has to know which one to believe.
**This work order decides: the row owns the state, the event owns the
history**, and the two are reconciled in one place rather than three.

### 2.4 A restart may not make a spent approval spendable

**The failure this work order is measured against is the double spend.**
An approval that was consumed, then the process restarted, then the
approval was granted again — or the row came back as `granted` — is a
consent that means nothing. **The crash matrix case kills the process
between the grant and the consume**, and the second spend is refused
**from the row**.

## 3. The work

### T00 — The migration, and the two columns

**Files:** `migrations/versions/00XX_approval_binding.py` (new),
`src/labcairn/db/models.py` (`ApprovalRow`).

**Add two columns to `approvals`:** the **grant-time policy digest** and
the **bound sources**. Take the next free revision number after the
newest in `migrations/versions/` and say which you took.

**And the migration is direct DDL**, for the reason revision 0007 records:
a frozen revision must not import today's models, or editing that class
would silently rewrite what the revision meant to create. **The parity
test that holds the migration and the ORM together is the one in
`tests/test_store_migrations.py`** — note that the four migrations that
name it point at `tests/test_evidence_schema.py`, which has **no parity
test in it**; that is a record error, not a code one, and the file to
name is `tests/test_store_migrations.py`.

### T01 — The store reads the row

**Files:** `src/labcairn/db/repository.py`, `src/labcairn/application/approvals.py`.

**The spend reads the grant-time digest and the bound sources out of the
row**, compares them with what the policy says **now**, and refuses on a
mismatch. **The row keeps what the policy said at the grant**, so the
comparison is between two recorded facts and not between a row and an
argument.

**And `consume` stops taking the two as arguments.** A caller that could
pass them could pass anything.

### T02 — The event and the row stop both owning the same fact

**Files:** `src/labcairn/application/approvals.py`,
`src/labcairn/application/records.py`.

**One place decides whether a given operation writes the row, the event,
or both.** The rule this work order adopts: **the row owns the state; the
event owns the history**; and a reader who asks "what is the approval's
state" reads the row, while a reader who asks "what happened to it"
reads the stream. **No operation emits twice.**

### T03 — The surfaces spend from the store

**Files:** `src/labcairn/cli/workspace.py` (the construction site at
`:636`), `src/labcairn/api/routes.py` (the forked session at `:614`),
`src/labcairn/application/tasks.py` (the `_unused_ledger()` at `:130`).

**Replace the in-memory ledger with the DB-backed store**, on the
service's **forked session** per the rule `api/routes.py:120` states.

**And the ledger is either gone or a cache that cannot outlive its row.**
A cache that can be read when the row says otherwise is a second source of
truth, and this work order's acceptance is *"the second spend is refused
**from the row**, not from memory"*.

### T04 — The G2 witnesses, reworked

**Files:** `tests/test_application_approvals.py` and whatever else the
change breaks.

**The accepted G2 witnesses stay red under the same mutations that make
them red now.** That is the clause that keeps this from being a rewrite:
the single-use guarantee's existing witnesses are re-expressed against the
store, and **the mutations that broke them before break them again**.

**And the tests that injected `now=` or peeked the ledger are reworked**
rather than deleted — the clock and the ledger were the two ways the old
tests reached past the layer, and the new ones reach past it in the same
places for the same reasons.

### T05 — The crash matrix, and the acceptance record

**Files:** `tests/test_approval_crash_matrix.py` (new),
`docs/acceptance/LC-P2-02-acceptance.md` (new).

**The crash matrix case that kills the process between the grant and the
consume**, and shows the **second** spend refused **from the row**.

**And the shard costs**, by the two-step process the Phase 2 evidence pack
records — the first run apportions, the second measures.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | The approval row carries the grant-time policy digest and the bound sources | `test_the_approval_row_carries_the_grant_time_binding` |
| A2 | The spend reads those two **from the row**, and `consume` no longer takes them as arguments | `test_the_spend_reads_the_binding_from_the_row` |
| A3 | A policy that changed between the grant and the spend does not satisfy the old approval | `test_a_changed_policy_does_not_satisfy_the_old_approval` |
| A4 | One operation writes the row, the event, or both — and never emits twice | `test_no_approval_operation_emits_twice` |
| A5 | The surfaces spend from the DB-backed store, on the forked session | `test_the_surfaces_spend_from_the_store` |
| A6 | A crash between the grant and the consume leaves the **second** spend refused **from the row** | `test_a_crash_between_grant_and_consume_refuses_the_second_spend` |
| A7 | A restart never turns a spent approval back into a grantable one | `test_a_restart_does_not_un_spend_an_approval` |
| A8 | The eight refusal reasons are unchanged, and a restart does not soften any of them | `test_the_eight_refusal_reasons_are_unchanged` |
| A9 | The single-use guarantee's existing witnesses are still red under the same mutations | `test_the_single_use_witnesses_survive_the_rework` |
| A10 | The ledger is gone, or it is a cache that cannot outlive its row | `test_the_ledger_cannot_outlive_its_row` |

**Every one of these needs a witness, and the witness must fail for the
property.** When a test goes red, ask what made it red before believing
that it caught something. **And a mutation that was never applied is
reported by anyone who does not check as a survivor**, which looks exactly
like a success — so check the diff before you believe a green result.

## 5. What this work order cannot deliver, and why

- **It does not make an approval mean something for two people.** An
  approval is bound to a task and a session; a multi-user identity is
  ADR-0003 and ADR-0015 D6's open question.
- **It does not make the material-purpose grant durable.** That is
  LC-P2-06's table, and it is already durable. **The two gates are
  separate permissions**, and this one is about the operation, not the
  material.
- **It does not make a paid call safe to repeat.** It makes a paid call
  **single-use across a restart**, which is what LC-P2-01 needs. What
  happens when a provider answers and the process dies before the answer
  is recorded is LC-P2-01's unknown-state rule, and this work order does
  not reach it.
- **It does not change what an approval authorises.** Only where the
  answer is kept.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `migrations/versions/00XX_approval_binding.py` | `src/labcairn/db/models.py` |
| T01 | — | `src/labcairn/db/repository.py`, `src/labcairn/application/approvals.py` |
| T02 | — | `src/labcairn/application/approvals.py`, `src/labcairn/application/records.py` |
| T03 | — | `src/labcairn/cli/workspace.py`, `src/labcairn/api/routes.py`, `src/labcairn/application/tasks.py` |
| T04 | — | `tests/test_application_approvals.py`, and whatever the change breaks |
| T05 | `tests/test_approval_crash_matrix.py`, `docs/acceptance/LC-P2-02-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**And the two shared files.** `src/labcairn/db/models.py` and
`src/labcairn/db/repository.py` are shared with **every work order that
adds a table or a store method** — and at the time this work order is
dispatched, LC-P2-09's subtasks are landing changes in both. **The two
must not be dispatched at the same time**, or one window's migration
becomes the other's conflict.

## 7. What "done" means

1. The approval row carries the grant-time binding, and the spend reads
   it **from the row**.
2. The ten acceptance clauses above have a named test each, **and the
   tests are named as the table names them**.
3. **The crash between the grant and the consume** is witnessed, and the
   second spend is refused **from the row**.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-02-acceptance.md` names the commit
   every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md).
7. **Every claim in §2 has been mutation-checked**: the property broken,
   the witness red, the tree restored.
