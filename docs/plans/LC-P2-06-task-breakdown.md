# LC-P2-06 — Data governance: the grant table and the refusals — task breakdown

**Status:** ready to implement. Detailed decomposition only — nothing here is
implemented, and this document does not authorise starting without the
owner's go-ahead.
**Subject when written:** `main` at `6ab9f3e`
**Date:** 2026-10-29
**Gate:** the second implementation of the mentor-trajectory line.
**Ordered by the owner, 2026-10-29:** LC-P2-06 comes after LC-P2-08,
because its grant table names the paper project LC-P2-08 created.

## 0. How to read this document

Section 1 fixes what is in and out. Section 2 describes the three decisions
that shape it. Section 3 is the work, in dependency order, with a
file-ownership map. Section 4 maps the acceptance clauses onto the subtask
and the test that carries each one. Section 5 records what this work order
cannot deliver, and why.

Every claim about what "cannot" happen is a refusal or a state, never an
absence.

## 1. Goals and boundaries

### 1.1 What LC-P2-06 must produce

From ADR-0015: **four independent permissions, the grant table, and the
refusal paths that enforce them.**

Concretely, by the end:

1. An **`access_grants` table** — one row per grant, naming the subject it
   covers, the **purpose**, the **permission**, the scope, who granted it,
   when, and how it was withdrawn.
2. **A permission check** that answers one question — *"may this material be
   used for this purpose, in this state, by this caller?"* — and answers
   **no** when the answer is not on record.
3. **The two-gate model request path**: an operation approval for
   `model.request` **and** an `external_transmit` grant, and **passing one
   does not imply the other**.
4. **A withdrawal that propagates**, and the propagation is **checkable** —
   a derived copy cannot outlive the grant that produced it.
5. **A refusal vocabulary** that names what is missing and what would
   satisfy it, in the project's existing style.
6. **An intake path** that refuses a file with no grant, and refuses the
   dangerous archives — the zip bomb, the path traversal, the macro.

### 1.2 Already done — removed from scope

- **The paper project and the version graph.** LC-P2-08's, and the grant
  table names its `paper_projects`.
- **The four permissions' vocabulary.** ADR-0015 D1 fixes them:
  `store_read`, `parse_annotate`, `external_transmit`, `train_reuse`. **This
  work order implements them; it does not choose them.**
- **The identity separation.** ADR-0015 D5 says a person's name is kept
  apart from the material; `PaperProject.subject_pseudonym` is where the
  pseudonym lives, and the grant table carries **no name at all** — only a
  pseudonymous subject reference.
- **The multi-user question.** ADR-0015 D6 defers it, with the conditions
  written down.

### 1.3 Explicitly not in scope

- **Any model call.** The two-gate path is built and **tested**, and this
  work order does not spend money. LC-P2-01's path is where a call
  happens.
- **Any real material.** Everything here is synthetic, and the reader has
  never seen a real Word document.
- **The version graph's persistence.** LC-P2-08 owns it.
- **The feedback chain.** LC-P2-09 owns `FeedbackEvent` and `EditAction`.
- **The experience store.** LC-P2-11's rules are built on what this
  work order lets through; it does not build them.

## 2. The three decisions that shape it

### 2.1 Absence is denial, and the table only holds what was granted

**The four permissions are four grant kinds, and each is independently
absent, independently withdrawn.** ADR-0015 D2 says it without hedging:
*"Not 'denied until granted' as a UI default — **denied in the model**.
There is no row, so there is nothing to check, so the path cannot
proceed."*

**So the table holds only grants, and a check that finds no row refuses.**
There is no column that says `permitted = false`, because a column that
can hold `false` can also hold `true` by an update that nobody audited, and
the whole design is that **the answer is a fact on the record rather than a
flag somebody flipped**.

**The consequence for the schema.** A permission's state is the *absence of
a row*, and the schema says so by having nowhere to put a "not permitted"
row: `permission` is a closed vocabulary of the four, and every row is a
grant. There is no row shape that means "denied", which is the point.

### 2.2 A grant names one purpose and one destination

**The purpose and the destination are both on the grant**, and both are
narrower than "the material may be used".

ADR-0015 D3's rule: *"a grant naming provider A does not authorise
provider B"*. So the destination is a field, not an assumption. A grant for
`external_transmit` names **one** destination, and a request to a different
one finds no matching grant and is refused.

**And the purpose is a separate axis.** The design's four purposes are
`read | annotate | retrieve | transmit | train`, and the four permissions
are `store_read | parse_annotate | external_transmit | train_reuse`. **A
grant carries one of each**, and the permission is what the grant *is* while
the purpose is what it is *for* — which is what lets "annotating this for
the lab" and "sending this to a model" be two different grants rather than
one broad one.

### 2.3 A withdrawal propagates, and the propagation is checkable

ADR-0015 D4: *"Withdrawing a grant must invalidate what depended on it:
derived embeddings, index entries built from the material, queued training
runs, cached model transcripts, and any guidance rule distilled from it."*

**And the design says the question is asked precisely**: *"撤回同意后历史
embedding/缓存/训练队列是否失效"* — after consent is withdrawn, do the
historical embeddings, caches and training queues expire?

**So the propagation has to be a fact, not a promise.** The mechanism this
work order builds: **a derived copy records the grant it came from**, and
the check asks whether that grant is still active. A copy whose grant was
withdrawn is **stale by derivation**, and it says so.

**What this cannot do, and says so.** It cannot find copies that were
written before the mechanism existed, and it cannot undo a copy that has
already been used. It makes the *next* use impossible, which is the part
that is enforceable.

## 3. The work

### T00 — The grant table

**Files:** `src/labcairn/db/models.py`,
`migrations/versions/0011_access_grants.py`, `tests/test_store_migrations.py`.

```
access_grants:
  grant_id            caller-minted
  subject_ref         the paper project id, or a body of material
  permission          store_read | parse_annotate | external_transmit | train_reuse
  purpose             read | annotate | retrieve | transmit | train
  scope               what material the grant covers
  destination         where the material may go; NULL for the two
                      permissions that do not leave the machine
  granted_by          a named person
  granted_at
  expires_at          optional
  state               active | withdrawn | expired
  withdrawn_at        optional
  withdrawn_by        optional
  withdrawal_reason   optional
```

**Four constraints the schema holds.**

1. **`permission` is a closed set of four, and `purpose` a closed set of
   five.** A typo like `transmit` instead of `external_transmit` must not
   sail through as a permission nobody holds.
2. **A destination is required for `external_transmit` and forbidden for
   the other three.** A transmit grant with no destination is a grant to
   send anywhere, which is the thing D3 exists to prevent. A read grant
   *with* a destination is a grant that says where the material goes, which
   nothing needs.
3. **A withdrawal names who and when.** `state='withdrawn'` with no
   `withdrawn_by` is a refusal nobody made.
4. **`state` and the withdrawal fields agree**: an active grant has no
   withdrawal fields, a withdrawn one has both, and an expired one has
   neither (it ran out on its own).

**And what is *not* a constraint.** There is **no `permitted` column**, and
no row shape that means "denied". §2.1 says why.

### T01 — The permission check

**Files:** `src/labcairn/security/consent.py` (new),
`tests/test_dataset_consent.py` (new).

**The one question.** `may_use(grant_rows, *, permission, purpose,
subject_ref, destination=None, at=...) -> Decision`.

**The decision has three parts, and the third is the useful one.**

| | |
|---|---|
| `allowed` | whether the use is permitted |
| `grant_id` | **which** grant permitted it — so the answer can be audited |
| `reason` | when refused, **what is missing and what would satisfy it** |

**The refusals, and each names its own missing thing.**

| The refusal | What it says |
|---|---|
| `no_grant` | no grant covers this permission for this subject |
| `purpose_not_granted` | a grant exists for this permission, but not for this purpose |
| `destination_not_granted` | a grant exists for this purpose, but not for this destination |
| `grant_withdrawn` | the grant that would have covered it was withdrawn, by whom and when |
| `grant_expired` | the grant existed and has run out |
| `grant_not_yet_active` | the grant is recorded but its window has not opened |

**And the rule that a refusal is not a permission.** The check returns
`allowed=False` with a reason; it does not raise, because "not permitted"
is a normal answer on this path, not an exception. **A model request with
no transmit grant must be refused with a reason, not crash.**

**And the rule about which refusal is reported.** When several grants
exist and none covers the use, the reason names the **closest** one — the
grant that covers the permission but not the purpose, or the purpose but
not the destination — because "you have a read grant but not a transmit
grant" is an answer a person can act on, and "no grant" is not.

### T02 — The two-gate model request path

**Files:** `src/labcairn/application/consent.py` (new),
`tests/test_consent_two_gates.py` (new).

**ADR-0015 D3: two independent checks, and passing one does not imply the
other.**

1. The **operation approval** for `model.request` — the existing machinery,
   the existing single-use guarantee, unchanged.
2. The **`external_transmit` grant** for the material in the request — the
   new check, and the one that names the destination.

**What is refused, and what is *not* refused.**

- A request with no operation approval is refused by the **existing**
  machinery, and **the approval is not spent** — asking a question is not
  spending. ADR-0015 says this and the existing consent layer already
  holds to it.
- A request whose material has no transmit grant is refused by the **new**
  check, and **the approval is likewise not spent**, because the refusal
  happened before the effect.
- A request whose grant names a **different destination** is refused, and
  the refusal **names the destination** that was asked for and the one that
  was granted.

**The order matters and is stated.** The transmit check runs **before** the
approval is consumed, so a request that is refused for lack of a grant
leaves the approval unspent and the person can fix the grant and try
again.

### T03 — Withdrawal, and the propagation that is checkable

**Files:** `src/labcairn/security/consent.py`,
`tests/test_consent_withdrawal.py` (new).

**Withdrawing a grant** records who, when and why, and moves its state to
`withdrawn`. It does **not** delete the row: **the record of a grant that
was withdrawn is itself a record**, and a permission check that cannot say
"this was withdrawn by the advisor on 2026-03-02" is a check that cannot
answer a question a person will ask.

**And the propagation.** A **derived copy** records the grant it came
from: the index entry built from the material, the queued training run, the
cached transcript. The copy is **stale by derivation** when its grant is
not active, and the check that says so is the one the acceptance clause
names.

**What this work order cannot do, and says so.** It cannot find copies
written before the mechanism existed, and it cannot undo a copy already
used. It makes the **next** use impossible.

### T04 — The intake path

**Files:** `src/labcairn/material/intake.py` (new),
`tests/test_intake_guards.py` (new).

**This is where the design's §7 archive cases live**, and they are not a
version-graph question:

| The case | The refusal |
|---|---|
| a file with no `store_read` grant | `no_grant` — the archive is not readable |
| an archive with a compression ratio beyond a declared ceiling | `zip_bomb` |
| an entry whose path escapes the extraction root | `path_traversal` |
| an entry with a macro-enabled extension | `macro_not_executed` — **the macro is never run, and the file is refused rather than stripped** |
| an entry whose total size exceeds a declared ceiling | `archive_too_large` |

**And the design's own standard applies**: the ceilings are **declared**
values, not guesses buried in the code, and a file that exceeds one is
refused **with the ceiling named**.

**Why refusing rather than stripping.** A `.docm` with its macro removed is
still a document whose provenance is unclear, and the design says the
malicious macro is *not executed* — not that the file is cleaned. **A
refusal is honest; a partial acceptance is not.**

### T05 — The refusal vocabulary

**Files:** `src/labcairn/application/refusal.py`,
`tests/test_cli_refusal_enumeration.py` (the existing witness).

**Every refusal joins the existing enumeration**, which the CLI renders and
the test watches. **A refusal that is not in the enumeration does not
exist**, so a new reason that nobody renders is a reason nobody sees.

### T06 — The end-to-end demonstration

**Files:** `examples/consent_demo.py`, `tests/test_consent_demo.py`.

**The same shape as LC-P2-08's demonstration**: a project with a grant for
reading, a request to transmit that is refused with the reason, a request
that is refused because the destination is not the granted one, a
withdrawal, and a derived copy that is stale because of it. **Every claim
carried by a `check()` that raises**, and a test runs it.

### T07 — What the tables cost, and the acceptance record

**Files:** `docs/acceptance/LC-P2-06-acceptance.md`.

**And the shard costs**, by the two-step process the Phase 2 evidence pack
records: the first run apportions, the second measures. **The number in the
table comes from the runner**, and the first run's number is labelled as
what it is.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The subtask | The test |
|---|---|---|---|
| A1 | Material with no grant is **not readable** for the restricted purpose | T01, T04 | `test_material_with_no_grant_is_not_readable` |
| A2 | The refusal names **what is missing and what would satisfy it** | T01 | `test_a_refusal_names_what_would_satisfy_it` |
| A3 | `external_transmit` and `train_reuse` are **denied by absence** — no row means no permission | T00, T01 | `test_a_permission_with_no_row_is_denied_by_absence` |
| A4 | A grant naming provider A does **not** authorise provider B | T01, T02 | `test_a_grant_for_one_destination_does_not_authorise_another` |
| A5 | A transmit grant with **no destination** is refused by the schema | T00 | `test_a_transmit_grant_with_no_destination_is_refused` |
| A6 | A request with no transmit grant is refused **and the approval is not spent** | T02 | `test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent` |
| A7 | The transmit check runs **before** the approval is consumed | T02 | `test_the_transmit_check_runs_before_the_approval_is_consumed` |
| A8 | Withdrawing a grant **invalidates the copies derived from it** | T03 | `test_a_withdrawn_grant_invalidates_the_copies_derived_from_it` |
| A9 | A withdrawal records **who and when** | T03 | `test_a_withdrawal_records_who_and_when` |
| A10 | `owner_id` authorises **nothing** | T01 | `test_the_owner_scope_authorises_nothing` |
| A11 | No real manuscript's bytes appear in the repository, a CI artefact, or the public evaluation corpus | T04 | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| A12 | The archive guards refuse: zip bomb, path traversal, macro, oversize | T04 | `test_the_archive_guards_refuse_what_the_design_names` |
| A13 | The demo is run by a test | T06 | `test_the_consent_demo_runs` |
| A14 | The refusal reasons are in the enumeration the CLI renders | T05 | the existing enumeration witness |

## 5. What this work order cannot deliver, and why

- **It does not decide who may be granted what.** A grant is issued by a
  person — the advisor, or the administrator — and this work order builds
  the machinery, not the policy. **The pilot's grant-issuing rule is the
  owner's** and is recorded in the Phase 2 evidence pack.
- **It does not undo a copy that was already used.** The propagation makes
  the *next* use impossible; a transcript that was already sent cannot be
  recalled, and saying otherwise would be the kind of claim this project
  does not make.
- **It does not find copies written before the mechanism existed.** The
  mechanism is a fact about a copy's provenance, and a copy with no
  recorded provenance has none to check.
- **It does not spend money and it does not call a model.** The two-gate
  path is built and tested; LC-P2-01's path is where a call happens, and
  **the owner's authorisation is a precondition there.**
- **It does not make the multi-user question go away.** ADR-0015 D6's
  conditions — the identity model, the audit trail, the withdrawal-deletion
  consistency check — are the acceptance list for the moment the pilot
  opens beyond the administrator, and they are written down rather than
  left to be discovered.
- **It does not store the material.** It says who **may** use it; the
  material's own storage is LC-P2-08's and LC-P2-09's.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `migrations/versions/0011_access_grants.py` | `src/labcairn/db/models.py` |
| T01 | `src/labcairn/security/consent.py`, `tests/test_dataset_consent.py` | — |
| T02 | `src/labcairn/application/consent.py`, `tests/test_consent_two_gates.py` | — |
| T03 | `tests/test_consent_withdrawal.py` | `src/labcairn/security/consent.py` (its own) |
| T04 | `src/labcairn/material/intake.py`, `tests/test_intake_guards.py` | — |
| T05 | — | `src/labcairn/application/refusal.py` |
| T06 | `examples/consent_demo.py`, `tests/test_consent_demo.py` | — |
| T07 | `docs/acceptance/LC-P2-06-acceptance.md`, `.github/ci-shards.json` | — |

**The two shared files.** `src/labcairn/db/models.py` is shared because
every table lives in it, and **only T00 writes to it**. The
`src/labcairn/security/consent.py` is shared between T01 and T03, and it is
written by T01 and extended by T03 — so **T03 follows T02**, which is
sequential by construction.

**And the migration number.** `0011` follows `0010` (LC-P2-08's).

## 7. What "done" means

1. The migration and the ORM agree, and a row the schema must refuse is
   refused.
2. The fourteen acceptance clauses above have a named test each.
3. The demonstration runs, and **a test runs it**.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-06-acceptance.md` names the commit
   every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md) —
   the review happens after the merge, so what to break has to be written
   down while the work is being done.
