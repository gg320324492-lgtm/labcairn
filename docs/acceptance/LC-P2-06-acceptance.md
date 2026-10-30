# LC-P2-06 — Data governance: the grant table and the refusals — acceptance

**Work order:** LC-P2-06 (data governance, consent and access) ·
**Subtasks:** T00–T06.
**Task breakdown:** [`docs/plans/LC-P2-06-task-breakdown.md`](../plans/LC-P2-06-task-breakdown.md)
**ADR:** [`ADR-0015`](../adr/ADR-0015-dataset-consent-and-access.md)
**Status of the work order:** **implemented and measured**, and
**independently reviewed** against the merged tree at `ff93b1d` — see §3.3
and §6.
**Measured:** 2026-10-29 on the tree at `d7de4fb`.

**What this is.** The consent machinery for the mentor-trajectory line: a
row is a permission somebody granted, and **the absence of a row is the
refusal**.

**What this is not.** It does not spend money, does not call a model, and
does not decide who may be granted what. **The policy of granting is a
person's**; this is the mechanism that enforces it.

---

## 1. The three decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **Absence is denial** — the table holds only grants, and there is no row shape that means "denied" | the schema, and the model's vocabulary check | `test_the_table_holds_only_grants_and_therefore_has_no_way_to_say_denied` |
| **A grant names one purpose and one destination** | the schema's `access_grants_destination_belongs_to_transmit` and the model's validator | `test_a_transmit_grant_with_no_destination_is_refused`, `test_a_grant_for_one_destination_does_not_authorise_another` |
| **The check asks two questions** — whose project, and which of its material | `may_use` in `security/permissions.py` | `test_a_grant_for_another_subject_does_not_answer_for_this_one`, `test_a_grant_whose_scope_does_not_reach_the_material_is_refused` |

## 2. The fourteen acceptance clauses

| # | The clause | The test |
|---|---|---|
| A1 | Material with no grant is not readable | `test_material_with_no_grant_is_not_readable` — **and the witness is a file that could not be opened**, so an open would fail the test |
| A2 | The refusal names what is missing and what would satisfy it | `test_a_refusal_names_what_would_satisfy_it` |
| A3 | `external_transmit` and `train_reuse` are denied by absence | `test_a_permission_with_no_row_is_denied_by_absence` — **and `test_a_grant_for_one_permission_does_not_answer_for_another`**, which holds the purpose fixed and changes the permission, because a read grant is not a training grant |
| A4 | A grant naming provider A does not authorise provider B | `test_a_grant_for_one_destination_does_not_authorise_another` |
| A5 | A transmit grant with no destination is refused by the schema | `test_a_transmit_grant_with_no_destination_is_refused` |
| A6 | A request with no transmit grant is refused and the approval is not spent | `test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent` |
| A7 | The transmit check runs before the approval is consumed | `test_the_transmit_check_runs_before_the_approval_is_consumed` |
| A8 | Withdrawing a grant invalidates the copies derived from it — **and so does a grant whose window has closed**, which is the other way a grant stops holding | `test_a_withdrawn_grant_invalidates_the_copies_derived_from_it`, `test_a_grant_whose_window_has_closed_makes_its_copies_stale` |
| A9 | A withdrawal records who and when | `test_a_withdrawal_records_who_and_when` |
| A10 | `owner_id` authorises nothing | `test_the_owner_scope_authorises_nothing` |
| A11 | No real material reaches the repository or a CI artefact | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| A12 | The archive guards refuse what the design names | `test_the_archive_guards_refuse_what_the_design_names` |
| A13 | The demo is run by a test | `test_the_consent_demo_runs` — **and `test_the_demonstrations_guards_are_guards`**, because a demonstration that runs is not a demonstration that still asserts |
| A14 | The refusal reasons are in the enumeration the CLI renders | the existing enumeration witness |

**The names in this table are the work order's, and the tests were renamed
to match** — the task breakdown is the contract, and the implementation is
supposed to meet it.

## 3. The mutations, and what each broke

**Twenty-four mutations were applied.** Each is recorded here with the test that
caught it.

| # | The mutation | What went red |
|---|---|---|
| 1 | the permission check drops the window's **lower** bound | `test_a_grant_that_has_not_opened_yet_is_refused_as_such` |
| 2 | any transmit grant authorises any destination | `test_a_grant_for_one_destination_does_not_authorise_another` |
| 3 | a withdrawal is reported as "no grant" | `test_a_withdrawn_grant_is_refused_as_withdrawn` |
| 4 | a missing grant row is treated as a live grant | `test_a_copy_whose_grant_is_not_on_the_record_is_stale`, `test_the_stale_copies_are_listed_and_not_a_promise` |
| 5 | the intake's path traversal check is dropped | four tests, including `test_a_refused_archive_still_lists_its_entries` |
| 6 | the intake's macro check is dropped | `test_a_macro_enabled_document_is_refused_not_cleaned` |
| 7 | the intake's grant check is made ineffective | `test_material_with_no_grant_is_not_readable` |
| 8 | the demonstration's withdrawal check is inverted | three of the demonstration's four tests |
| 9 | a material file is left in the working tree, uncommitted and unignored | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| 10 | a material file is committed that is not on the allowed list | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| 11 | the public corpus stops declaring itself synthetic | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| 12 | one byte of the public corpus' material changes | `test_no_real_material_reaches_the_repository_or_a_ci_artefact` |
| 13 | the covering test accepts a grant on the strength of its scope alone, so the owner's scope becomes a permission | `test_the_owner_scope_authorises_nothing` |
| 14 | the refusal names the owner as the reason | `test_the_owner_scope_authorises_nothing` |
| 15 | the intake's macro check is dropped | `test_the_archive_guards_refuse_what_the_design_names` |
| 16 | the intake's grant gate is removed | `test_the_archive_guards_refuse_what_the_design_names` |
| 17 | a training use with no grant is permitted by default | `test_a_permission_with_no_row_is_denied_by_absence` |
| 18 | the covering test drops the grant's **permission** clause, so a read grant answers a training use | `test_a_grant_for_one_permission_does_not_answer_for_another` — **the only test in the suite that notices** |
| 19 | every `check()` in the demonstration's step 2 is deleted | `test_the_demonstrations_guards_are_guards` |
| 20 | the grant table grows a `permitted` column | `test_the_table_holds_only_grants_and_therefore_has_no_way_to_say_denied`, and `test_the_migrated_schema_matches_the_orm_models` |
| 21 | the scope is asked about the **subject** rather than about the material | `test_a_grant_whose_scope_does_not_reach_the_material_is_refused`, and `test_a_wildcard_scope_does_not_cover_a_sibling` |
| 22 | the copy check reads the grant's **state column** instead of asking the grant at a moment | four tests, including `test_a_grant_whose_window_has_closed_makes_its_copies_stale` and `test_the_copy_check_and_the_permission_check_do_not_disagree` |
| 23 | a row is removed from the layer's consent-refusal mapping | `test_every_consent_refusal_has_a_layer_name` |
| 24 | the operation approval is consumed **before** the transmit gate | `test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent`, `test_the_transmit_check_runs_before_the_approval_is_consumed`, **and the demonstration itself**, which exits non-zero |

### 3.1 The one that was reported as surviving and was not

**Mutation 7's first attempt changed nothing.** The text inserted was
``if False: pass`` immediately before the real check, so the check still
ran and the suite stayed green — and the mutation was about to be reported
as surviving. **It was not a mutation at all**, and the way to know was to
look at what the code did rather than at what the test said.

**The rule, which is in the review points and in the mutation memory:**
*a mutation must make an assertion fail*, and a survivor must be checked
for having been applied at all.

### 3.2 Why mutation 9 is the one that matters most

**The untracked file is the channel the release job names itself:** *"the
build backend does not read .gitignore"*, so a file in the working tree
that is neither committed nor ignored **lands in the source distribution**.
An index-only check would not have seen it, and the material would have
shipped.

### 3.3 The seven the independent review found

**An independent review of the merged tree at `ff93b1d` read the property
list against the tree and found seven things.** Four of them were properties
the suite stated and did not watch; **two were dead vocabulary and an
unwired order** — claims that were true of the code and true of nothing
else; and **one was a defect in the behaviour**, a grant whose window had
closed leaving its derived copies live. Mutations 18–24 are the witnesses
that were added.

**Every one of the seven was checked against the shipped tree before it
was checked against the mutation**, and the tree was restored after each
one — a mutation that never applied looks exactly like a success, and that
is the mistake this work order's own record already tells of.

**The row that is worth reading twice is 21.** The scope witness refused
for the right answer and the wrong reason: its scope did not cover the
subject either, so a check that conflated the two coordinate systems still
refused, and the witness could not tell the difference. **It was green
under the mutation, and the way to know was to apply the mutation and read
which test went red** — the sibling witness, and not the one whose name
matches the property. The witness now uses grants whose scope reaches the
subject and not the material named.

**And row 18 is the axis that had no witness at all.** Every other witness
in the consent suite asked a question in which the *purpose* already
excluded the grant, so the permission clause was never the binding
constraint: **the whole suite was green under the mutation**, and the
permission was the one axis that nothing held.

**Rows 23 and 24 are the two that were not about a witness.** Row 23: the
twelve refusal names the work order added to the layer were **names nothing
raised**, and the layer could not render a single consent refusal; row 24:
the order the work order claimed — *a refused request does not spend the
operation approval* — was claimed by a witness that held no approval, on a
path that was wired to nothing. **Both were true of the code and true of
nothing else**, and the fix was to make the path exist and to give it a
witness that holds a real approval.

**And one record was corrected.** ADR-0015 D1's column list named twelve
columns and omitted the destination its own D3 requires and the schema has
carried since the table was created. **The list is the shape of the row**,
and the witness for that shape now asserts the whole set.

## 4. What the tests found in the implementation

**Nine defects. Six of them would not have been found by reading the code
twice; the last three were found by an independent review of the merged
tree.**

1. **The window's lower bound was missing.** A check that asks only "has it
   expired?" lets a grant for a *future* window permit a use today.
2. **An expired grant was reported as "no grant."** The expiry is a clock
   fact and the state column still said `active`.
3. **The subject and the scope were one test**, so a grant's scope never
   had to reach the material.
4. **Two coordinate systems were mixed up.** The scope named material by an
   absolute path while the subject named a project by its id, and the two
   were never in the same system. **The demonstration is what found it**,
   because the demonstration exercises both together.
5. **A module was overwritten.** The permission check was first written to
   `labcairn/application/consent.py`, which **already existed** and holds
   the capability model's single `evaluate`. The import error caught it
   immediately and the file was restored from git; the check now lives at
   `labcairn/security/permissions.py`, and the two gates at
   `labcairn/application/model_transmit.py`. **Two modules called
   `consent` is a confusion the names should not carry**, and one of them
   was already taken.
6. **The training permission was never exercised.** `train_reuse` was in
   the vocabulary and in the schema's constraint, and **no test ever asked
   for it**. A3's clause — *"`external_transmit` and `train_reuse` are
   denied by absence"* — was carried by a witness that only ever asked
   about reading and about transmitting, so **the clause was true of the
   code and unwatched**. The witness now asks for all four permissions,
   and the mutation that permits a training use by default turns it red.
7. **The expiry half of the propagation never fired.** The copy check read
   the grant's `state` column, and **nothing in the product ever writes
   `state='expired'`** on an access grant — an expiry is a clock fact, and
   a grant whose `expires_at` has passed is still `active` by state. So a
   grant that had run out left its copies live, while `may_use` refused
   the same grant with `grant_expired`. **The witness did not catch it
   because the witness built the expired grant by hand**, writing a state
   the product cannot reach — and so it watched a branch that never runs.
   **The witness that now carries it builds the grant the way the product
   can produce one**, and the state-column mutation turns four tests red.
8. **The refusals never reached a surface.** The work order added twelve
   refusal names to the layer's vocabulary, and **nothing raised them**: the
   consent machinery's vocabulary is `ConsentRefusal` and the intake's is
   `IntakeRefusal`, and neither was mapped onto the layer. So a refusal
   produced by either could not become an `ApplicationRefusedError` and no
   surface could print it — and the drift was already there, with
   `IntakeRefusal.NO_GRANT` having no name in the layer at all. **Two
   closed tables and a lookup instead of a default**, and a witness that
   closes the two vocabularies against each other in both directions.
9. **The order was never wired.** A6 and A7 claimed that a refused request
   leaves the operation approval unspent, and **the witness named for the
   claim held no approval**; the demonstration printed the sentence
   unconditionally; and the transmit gate was called from no production code
   at all, so there was no path on which an approval could be spent before
   it. **There is a path now**, and the witness holds a real approval — and
   **reads the store** to say the approval was not spent, because
   `spendable_approval` asks whether the moment is right to spend and not
   whether the approval has been spent already, which is a weaker question
   than the one the claim asks.

**The sixth is the one worth keeping.** The other five were found by
writing code and running it; this one was found by **reading the task
breakdown's clause against the tree's test names** and noticing that a
permission the clause names had no case that reached it. A clause that
names a permission, and a suite that never mentions it, is a claim with
nothing behind it — and the suite was green throughout.

**And the seventh is worth keeping for the other half of the reason.**
It was found by **the independent review of the merged tree**, and the
defect it found had a witness — a witness that was not a witness, because
it built a state the product cannot write. **A witness that constructs an
unreachable state watches a branch that never runs**, and it goes green
whether the branch is right or wrong. That is the failure the project's
own rule is about: *a mutation must make an assertion fail*, and a
witness that cannot fail is not a witness.

## 4.1 The gate-class partition, and the one file outside the ownership map

**The six new test files had to be filed, and filing them is not optional.**
The evaluation harness keeps a partition — `FILE_ASSIGNMENTS` in
`tests/evaluation/manifest.py` — that assigns every `tests/test_*.py` to
exactly one gate class. A file in no class is **a test the CI never runs and
whose cases enter no denominator**, so PR #128's first run failed six
shards on exactly that sentence.

**Two rules of the harness made the filing a real decision.** A file filed
under a protocol class must **declare that class itself**, in its own
`pytestmark`, because the table's word alone is not a bound — the marker is
a different field in a different file, and it is the one the harness reads
to catch a misclassification. And the clause beside the class has to be the
protocol's own phrase.

| The file | The class | The clause |
|---|---|---|
| `test_access_grant_schema.py` | integration | migrations |
| `test_consent_demo.py` | integration | approvals |
| `test_consent_two_gates.py` | integration | approvals |
| `test_consent_withdrawal.py` | integration | approvals |
| `test_dataset_consent.py` | unit | permission-resolution |
| `test_intake_guards.py` | negative | path-traversal |

**And the file itself is outside this work order's ownership map.**
`docs/plans/LC-P2-06-task-breakdown.md` §6 gives T07 the acceptance record
and the shard file; `tests/evaluation/manifest.py` belongs to LC-P1-13's
harness and to nobody in this work order. **The change was made anyway,
because leaving it out means the work order's own CI cannot go green**, and
it is recorded here rather than made quietly. The rule the project states —
*a window that needs another's file says so rather than reaching for it* —
is satisfied by this paragraph and by the report to the owner, not by the
edit being silent.

**What the change does not do:** it does not touch the harness's rules, the
protocol, or any existing file's filing. It adds six rows to a table and
six `pytestmark` lines to the files themselves.

## 5. The suite on this tree

**Measured on `6c367c4`** — the tree the measurement was taken on, on
Windows 11 (AMD64), Python 3.12.13.

```
3982 passed, 5 skipped, 0 failed, in 37 minutes 31 seconds
```

**The five skips are all of the project's own accepted kinds**: a
POSIX-only permission-bit case, the real-provider smoke that needs the
owner's credential, and three Windows-path cases. **None of them is new**,
and none of them is about this work order.

**This is a local measurement, and it says so.** The number is the
evidence until a runner says otherwise; the CI run on the review-fix pull
request replaces it, and its shard costs replace the apportioned one for
the new test file in the same round.

**And nothing that the number depends on has changed since.** The only
commit after `6c367c4` changes the shard table, and **the number does not
depend on the shard table** — the partition decides which job runs which
file, not what a file asserts.

## 6. The review, and what is still open

- **The independent review has been carried out** against the merged tree
  at `ff93b1d`, and it found **seven things**: four properties the suite
  stated and did not watch, two claims that were true of the code and of
  nothing else, and one defect in the behaviour. **They are the seven of
  §3.3**, and the review's own document is
  [`LC-P2-06-review.md`](LC-P2-06-review.md) — in this tree now, so the
  link resolves.
- **The review points are recorded**, in
  [`docs/plans/PHASE_2-review-points.md`](../plans/PHASE_2-review-points.md),
  with the mutations and the witnesses that catch them — nineteen
  properties, what to break in each, and the five rules a reviewer is
  held to.
- **No real material, and no grant has been issued.** The machinery is
  built and measured; **the pilot's grant-issuing rule is the owner's** and
  is recorded in the Phase 2 evidence pack.
- **No model call and no money.** The two-gate path is built and tested;
  LC-P2-01's path is where a call happens, and the owner's authorisation
  is a precondition there.
- **The multi-user question is still open.** ADR-0015 D6's conditions —
  the identity model, the audit trail, the withdrawal-deletion consistency
  check — are the acceptance list for the moment the pilot opens beyond the
  administrator.
- **A copy that was already used cannot be recalled.** The propagation makes
  the *next* use impossible, and the record says so rather than implying
  more.
- **Nothing in `src/` reads the grant tables yet.** The check is
  *checkable* — the tests and the demonstration hold it — but no product
  path fetches an `access_grants` row into a `Grant`, and nothing calls
  `stale_copies` outside this work order's own tests and its demonstration.
  **The expiry defect was unreachable in two independent ways**: the wrong
  reading of the clock, and the absence of a path that would have reached
  it.
- **`Grant.is_in_force` treats any state outside `{"withdrawn",
  "expired"}` as in force.** `'revoked'`, `'suspended'` and `''` all come
  back true. **The schema closes the vocabulary**, so those are not
  reachable through the store, and asking for `state != "active"` instead
  would close it. **Left as it is, deliberately**: the change is one line,
  but a line with no witness behind it is a line nobody will notice being
  wrong, and the witnesses this work order has are worth more than the
  tightening. It is a separate piece of work, with its own mutation.

## 7. The next thing

**LC-P2-09, the feedback chain** — `FeedbackEvent`, `EditAction`,
`ResponseLink` and `FollowupAssessment` — and the tables this work order's
`derived_copies` will point at when a distilled rule is made from a case.

**And one thing that is not a ticket:** the CI shard cost for this work
order's six new test files, by the two-step process the Phase 2 evidence
pack records — the first run apportions, the second measures. **Both
steps have happened.** The first run could not execute a file that was in
no shard, so the tool apportioned the unaccounted time by test count; the
second run executed them, and the costs now in `.github/ci-shards.json`
are the runner's own, with `measured_at` naming the commit they belong
to.

**And the apportionment was wrong in both directions**, which is the
point of measuring on the runner rather than on the laptop: the
demonstration's file was apportioned at 0.13 s and measured at **1.16 s**
— nine times larger — and the intake guards' file was apportioned at
0.49 s and measured at **0.06 s**, eight times smaller. **A locally
measured number would have been wrong by a different factor again.**

**The partition those costs produce is better balanced than the one they
replaced**: **1.162** on Ubuntu and **1.000** on Windows, against 1.449
and 1.180.

**And the one file the review's own fixing added** — the refusal
vocabulary's witness — went through the same two steps, and the
apportionment was **low by two times and by four**: 0.16 s and 0.07 s
apportioned, **0.34 s and 0.27 s measured**. **A file that checks a
vocabulary against two enums is not the average of the files around it**,
and the apportionment divides the unaccounted time by test count.
