# LC-P4-PILOT — no surface can move a record to `verified_by_rule`

**Ticket:** LC-P4-PILOT (the gap the owner named on 2026-11-28: the store's
`advance` has no caller).
**Date:** 2026-11-28.
**Tree:** `58486d2180613aace95168d876c036221fd189af` (`main`'s tip as the
batch started, carried on the worktree branch
`claude/adoring-bardeen-ff1f33`). The measurement below was taken at that
commit; the record and the witness it names are the only files this work adds.
**That hash moved once.** The delivery-line rewrite re-hashed the commit the
batch started from, and the batch was measured at the tree it had before the
rewrite — the same tree, under the name it has now. The tree's witness for
the citations the records make (`tests/test_record_citations.py`) is what
found the old name still written here.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13 (the project's own
`.venv`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. **The measuring window changed nothing under `src/`** — it measured
and recorded. **A second window then closed the gap** (the owner chose
option A by starting it), and changed the product: the closing section at the
end of this record says what was wired, what it cost and what was measured.
Read the measurement below as the state at the commit named above, and the
closing section as what is true after it.
**Material:** **none of the pilot's was read.** The measurement is a read of
this repository's own source at the commit named above, plus greps over
`tests/` and `web/src/`. No document text, digest of a document, or key of
the pilot appears in this record. No model request was made.

## The claim, and how it was measured

**`labcairn.evidence.store.advance` is the only path in the tree that can
move a record to `verified_by_rule`, and nothing in `src/` calls it.** The
measures:

1. `git grep -n "advance(" -- src/` returns one line, the definition
   (`src/labcairn/evidence/store.py:466`).
2. The two SQL writes of the status column in `src/` are
   `UPDATE evidence_records SET status = :status` at `store.py:517` (inside
   `advance`) and `store.py:620` (inside `attest`). `attest` writes
   `USER_ATTESTED` unconditionally and refuses everything else at
   `_require_transition` before the write; so the `verified_by_rule` value
   can reach the column only through line 517.
3. No other writer exists: `append_record` inserts the status the record
   model carries, and the application layer builds every record with
   `status=PLANNED` (model proposals, `application/evidence.py:361`) or
   `status=EXTRACTED` (person's claims, line 312; accepted proposals,
   line 670). `supersede_record` writes a replacement through `append_record`
   and only stamps `superseded_by` on the old row. The migrations insert
   nothing (revision 0005 creates the tables and their CHECKs).
4. `attest` also refuses records whose `created_by` is not `user`, so a
   model-written record cannot be attested out of the way.

**Why `advance` is the only path.** The store's transition table
(`ALLOWED_TRANSITIONS`, `store.py:102`) permits `extracted → verified_by_rule`
and nothing else does. The record model refuses a record *constructed* with
the status and no passing C1–C3 log entry, and the store's
`_require_catalog_backed` (at the `append_record` boundary) refuses one
*inserted* with the status whose passing entry does not name a registered
rule — so the status cannot be smuggled in at write time through a
record built elsewhere. The only remaining route is the transition
`advance` performs, and `advance` has no caller.

## The surfaces, and what each can write

Every surface a person can reach, at the commit named above:

| Surface | What it writes | Status it produces |
| --- | --- | --- |
| CLI `labcairn task claim` (`cli/commands.py:1473`) | person's claim via `record_claim` | `extracted` |
| CLI `labcairn task claim-attest` (`cli/commands.py:1576`) | attestation via `attest_claim` | `user_attested` |
| CLI `labcairn task proposal-confirm` (`cli/commands.py:1633`) | acceptance via `confirm_proposal` | `user_attested` |
| API `POST /claims` (`api/routes.py:454`) | same as `task claim` | `extracted` |
| API `POST /claims/extract` (`api/routes.py:500`) | model proposal via `extract_claim` → `record_model_proposal` | `planned` |
| API `POST /records/{id}/accept` (`api/routes.py:544`) | same as `proposal-confirm` | `user_attested` |

One CLI command asks a model and writes nothing into the ledger:
`labcairn task suggest` puts the answer in the task's output area
(`suggestions/{approval_id}.md`) and returns it — its docstring says so in
its own voice (*"it is nobody's evidence"*). The proposal-writing path is
the API's extraction route alone.

The application layer offers no other writer: `record_claim`,
`record_model_proposal`, `attest_claim` and `confirm_proposal` are the whole
list, and none of them imports `advance`
(`application/evidence.py:107-116` imports `append_record`, `attest`,
`supersede_record` and the readers — not `advance`). The CLI and the API
render the same four operations; neither has a verify route.

**So no record can ever hold `verified_by_rule` through any surface.** And
the same measurement narrows the rest of the vocabulary: every transition
*between* states — the endpoints' retreat to `extracted`, and the moves to
`conflicted` and `unsupported` that the table also allows from `extracted` —
is performed by `advance` and only by `advance` (`attest` moves to
`user_attested` and nothing else; no product module calls `advance`).
`detect_conflicts` finds disagreements and `gate` reports them, but neither
writes a status. **The reachable state machine is three states wide**:
`planned` and `extracted` at write time, `extracted → user_attested` through
the attestation door. The other three statuses — `verified_by_rule`,
`conflicted`, `unsupported` — and every retreat are states no surface can
reach.

## What is therefore unreachable, machinery by machinery

Half the evidence machinery describes a state the product cannot reach. At
the commit named above:

- **`CITABLE_STATUSES`** (`evidence/states.py:87`) holds
  `{verified_by_rule, user_attested}`. Only its `user_attested` half is
  reachable. The set is consumed by the store (`_require_supported_identifiers`
  at the door to any citable state), by the report's
  **evidence gate** — `_judge_status` refuses a record the document states as
  established unless its status is in the set — and by
  `_the_source_still_supports`, which runs C1 at the door for every citable
  record. All of that machinery's `verified_by_rule` half never fires.
- **The store's `advance` preconditions** (`_require_precondition`'s
  `VERIFIED_BY_RULE` branch, `store.py:715-735`): the passing-entry rule and
  the catalog rule, re-judged at transition time. Unreachable in the product.
- **`UPGRADING_CHECKS`** (`store.py:137`): the set `{C1, C2, C3}` whose pass
  may upgrade a record — consulted by `advance` and by the model's status
  validator, which no product path can satisfy for this status.
- **The checks C2 and C3 as *gate re-verifications*** (`gate._reverify`
  re-runs whatever the log records and compares): a log can only hold C1–C3
  entries if `advance` appended them — the sole `append_verification` call
  sites in `src/` are inside `advance` and `attest`, and `attest` writes C4
  only. `attest`'s dangling-source door
  (`_require_source_still_supports`) *runs* C1 but does not log it: it
  returns on a pass and refuses on a fail, and the verdict is never appended.
  So in the product every reachable log holds C4 entries at most. C2 and C3
  re-verification in the gate is dead code on any record the product wrote.
- **`FINDING_STATUSES`** (`reports/model.py:155`) holds
  `{extracted, verified_by_rule, user_attested}`. The middle member is
  unreachable; a report can state findings in `extracted` and
  `user_attested` only.
- **The web workbench** renders the full six-state vocabulary from the
  generated client (`web/src/api/generated.ts:1279`), and its local fake API
  (`web/src/test/fakeApi.ts:690`) even serves a record in the state — the
  one place in the tree a reader *can* meet a `verified_by_rule` record is
  the frontend's test double.
- **The schema CHECKs** (revision 0005) that constrain C2/C4 log entries and
  the status column are live but half-idle: a constraint that refuses a
  state nobody can write is not wrong, but it is not doing work either.

One consequence was already measured and closed in the previous batch: the
gate's "stale passing C1 entry" case — a `verified_by_rule` record whose
logged C1 pass no longer holds — is unreachable for the same reason (the
batch-20 review record and `attested-source-drift-2026-11-28` cover it; that
window's fix added `_the_source_still_supports`, which *is* live for
`user_attested` records).

## What was not measured

- **Behaviour under a writer outside the product.** A SQL client or a
  future code path could insert a `verified_by_rule` row directly; the
  model, the store boundary and the schema each hold one of the three
  refusals, but this window did not build such a writer and drive it. The
  witnesses at `tests/test_evidence_store.py` cover the store's own refusals;
  what is not covered is that no *surface* reaches them.

  **Closed by the writer window, and the answer is not the one the item
  assumed.** The writer was built and driven, and each of the three refusals
  held against it — but they do not add up to a closed door, and the
  measurement found a path the item did not anticipate. The full account,
  the attempt-by-attempt verdicts and the mutation check are in **"The
  writer outside the product"** at the end of this record. The short version:
  **a writer that lands a located row *and* a forged passing log entry
  produces a record the product reads, the store never saw, and the report's
  evidence gate accepts with no finding at all.**
- **The analysis pipeline.** `labcairn.analysis` registers operators and
  renders charts, and its manifests bind a run's inputs and outputs — but it
  appends nothing to any evidence record's log. The option the owner may
  weigh — "verification happens only inside the analysis pipeline" —
  presumes a coupling this tree does not yet have; the measurement here is
  that the coupling does not exist, not that the pipeline could not carry it.
- **The evaluation harness's arms.** Whether the harness's blind-run arms
  ever construct the state through the store directly (the tests do —
  `tests/test_evidence_store.py` calls `advance` fifteen times — the
  harness's own arms were not inspected).

  **Closed by the closing window, and the answer is no.** A read of
  `tests/evaluation/` (every module, not only `arms.py`) for `advance`,
  `append_record`, `VERIFIED_BY_RULE` and `VerificationStatus` returns no
  occurrence: the harness's arms describe which *faces* of evidence an arm
  sees and build no evidence rows of their own. The only test code that
  constructs the state through the store is the store's own
  (`tests/test_evidence_store.py`), as this section said.

## The options, with their costs

The owner decides; the record's job is to make the decision a real one. Each
option names what it would do, what it would cost, and what it would not do.
No option in this table is recommended by the record; the measurement is
neutral about which the owner should want.

**Option A — wire a verify surface** (for example
`labcairn task claim-verify --check c1|c2|c3` and/or
`POST /records/{id}/verify`), calling the existing `advance` with the
matching `CheckKind`. What it would do: make the machinery live, give the
tree a second citable status, let a rule's pass stand beside a person's
attestation in the report's gate. Cost: a new application operation and
surface files (CLI and/or API), the TypeScript client regenerated, witnesses
for the new door, a shard re-measure (`python .github/remeasure_shards.py
<run-id>` — the numbers must come from a runner), and one CI run in the
end-of-batch PR. It would **not** decide *which* claims deserve a rule's
pass — that is a second decision the surface only makes possible.

**Option B — record the decision that verification lives only inside the
analysis pipeline**, and state what the unreachable machinery then is. Two
sub-shapes the owner would choose between: keep it as a **contract** (the
catalog, the preconditions and `CITABLE_STATUSES` are the API a future
pipeline wires into; the record says so, the docstrings say so, and the
witness below keeps the surfaces honest), or **remove** it (delete the
`advance` preconditions' dead half, the `VERIFIED_BY_RULE` members, and let
the state machine carry five states — the larger cut, with its own witness
cost: every test that constructs the state through `advance` today, thirty-one
call sites across six files, would be rewritten). The removal sub-shape has
a wider version worth naming: the same measurement that hides
`verified_by_rule` also leaves `conflicted` and `unsupported` without a
writer, and a removal that wanted the state machine to match what the
product can reach would cut those members too. What this option would
cost: an ADR or a decision record, and for the removal sub-shape a large
migration of the test tree. It would **not** make the pipeline actually
verify anything: the coupling does not exist today (see "What was not
measured").

**Option C — nothing now, the gap named and watched.** The record exists
(this document); the witness below makes the gap a failing test the moment
someone adds a surface, instead of a fact a reader cannot see. Cost: one
test file and the attention a red test demands when it goes red. It would
**not** resolve the question — the machinery stays half-idle, and the next
reader asks it again.

The options are not mutually exclusive in time: A can follow C, and B can be
recorded now and acted on later. What cannot be done by any option alone is
make the tree's claims and its behaviour agree — that is what the next
decision buys.

## The witness

`tests/test_surface_status_reach.py` — one file, two tests, `unit`-marked.
It reads the product's source as data: an `ast` scan over
`src/labcairn/`, so what matches is what the interpreter would load — an
import statement or a call expression — and a docstring that mentions
`advance`, a comment, or the name inside another identifier does not. It
asserts:

1. **no module in `src/labcairn/` imports `store.advance` or calls it** —
   any binding depth, any alias, and the three call shapes
   (`advance(...)`, `store.advance(...)`,
   `labcairn.evidence.store.advance(...)`). The record's central fact is
   watched: the moment a surface wires the writer, this test goes red and
   the integrator reads this record again. Its docstring says what it is
   watching and what will make it red, and that a red is **expected** at
   that moment, not a regression — the record names the decision that
   follows.
2. **no surface package names the unreachable status** —
   `VerificationStatus.VERIFIED_BY_RULE` (as an attribute access or an
   import) appearing anywhere under `application/`, `cli/` or `api/` is the
   act of a surface about to write it. The evidence and reports packages
   are deliberately not scanned: describing the status is the machinery's
   own job, and the scan would go red on the code that keeps the state
   machine honest.

`tests/` is not scanned either: the suite constructs the state through
`advance` on purpose — thirty-one call sites across six files at the
measured commit — because the machinery's own witnesses need a record in
the state.

**The scan's one blind spot, said plainly.** A writer reached through
dynamic indirection — `getattr` off a stringly-typed name, a dispatch
table of callables — does not read as an import or a call to `ast`, and
this scan cannot see it. The store's own refusals (the model validator,
`_require_catalog_backed`, the transition table) remain the second line
behind the witness: even a path this scan missed could not write the
status without a passing entry from a registered rule already in the log.

The witness was mutation-checked, and the checks are part of the evidence:
three wiring shapes (a function-level import and call, a package-level
`from labcairn.evidence import store` and call, an aliased
`import ... as` and call) each turned it red; a surface naming the status
member turned it red; and two controls stayed green — prose mentioning
`advance` in a docstring, and the tests' own legitimate use of the writer.
If a witness of this shape is judged misleading — a test that says "the
product cannot" about a state the owner may choose to enable next batch —
its own docstring is the answer: it names the decision point, and the
record carries the options. A brittle witness would be one that greps the
*tests*; this one does not.

<!-- Each branch of the tree the owner may cut is named above with what it
     would cost; the record recommends none of them. -->

## The gap closed — the verify door (option A)

**The owner chose option A by starting the window that wired it**, the same
day this record was written. This section is that window's account: what was
wired, what it cost, what was measured, and what the witness now says. It is
written because the witness above was designed to go red at exactly this
moment — it did, and it was inverted rather than silenced.

**The tree the closing was measured at:** `f39b96b36bebbf20852ec570b393c9433fb0f01b`
(the worktree's branch tip before the closing changes) plus the closing
changes themselves, which land in the commit this section is committed with.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13 (the project's own
`.venv`). **The venv's editable install names the main checkout**, so every
test run below was launched with `PYTHONPATH` pointing at the worktree's
`src`; the console script was checked to be loading that tree (the new
`task claim-verify --help` exists only there), which is the check the
repository's own rules ask for when a tree is not the installed one.

### What was wired

The store is still the only writer of the status, and the three layers are
unchanged in their division of labour:

| Layer | What it holds |
| --- | --- |
| store (`evidence/store.py`) | `advance`, unchanged — the only writer of the status column, and the only place the rule catalog, the transition table and the identifier rule are enforced |
| application (`application/evidence.py`) | `verify_claim(context, evidence_id, check=...)` — the operation, and the only caller of `advance` in `src/` |
| CLI (`cli/commands.py`) | `labcairn task claim-verify <id> --check c1\|c2\|c3` — calls the operation |
| API (`api/routes.py`, `api/contracts.py`) | `POST /records/{evidence_id}/verify` with `{"check": "c1"\|"c2"\|"c3"}` — calls the operation; `ClaimVerified` is the response model |

The operation's rules, each a deliberate one:

* **The rule is run, not asserted.** `verify_claim` calls `advance` with the
  named `CheckKind`; the store evaluates it against the ledger's anchors,
  appends the verdict, and moves the status only on a pass. The status a
  report cites is the residue of a check that ran.
* **A check that does not pass does not move the record.** The store appends
  the verdict before judging the move; the operation commits it (it is
  evidence, and it says what the rule found) and raises
  `ApplicationRefusedError` with reason `verification_refused`, whose message
  carries the outcome and the detail. This is why the refusal is not a
  rollback: the record's log keeps the failing verdict, and the status stays
  `extracted`.
* **Only C1, C2 and C3 can verify.** C4's only outcome is `not_checked`; the
  operation refuses it with `arguments_invalid` before any check runs, rather
  than sending it into a move whose precondition could not hold.
* **A record the context's task does not hold is refused as not found.** One
  refusal for "no such record" and "another task's record", so a context
  cannot probe another task's ledger.
* **No capability is asked.** The checks read the ledger's own rows, not the
  material's bytes again — the posture `attest_claim` takes for the same kind
  of act. The write that admitted those rows was the ingestion's
  `source.inventory` question.

The store's file is in the table and **was not changed**: the record's option A
called the existing `advance`, and the existing `advance` already refuses
everything the new door must refuse. The closing window verified that by
driving it, not by assuming it (the refusals are in the mutation table below).

### What it cost

| Change | Size |
| --- | --- |
| `application/evidence.py` | `ClaimVerified`, `verify_claim`, module docstring (the operation and its refusals) |
| `application/refusal.py` | one reason, `verification_refused` |
| `application/__init__.py` | the export and the capability table's row |
| `cli/commands.py` | `task claim-verify`, one command |
| `api/routes.py`, `api/contracts.py` | the route and `RecordVerificationBody` |
| `web/src/api/generated.ts` | regenerated; +9 lines (`ClaimVerified`, `RecordVerificationBody`) |
| `tests/test_surface_status_reach.py` | inverted from "nothing wires it" to "the door is wired and is the only way in" |
| `tests/test_evidence_verify_door.py` | new; nine tests (six `integration`, three `e2e`) |
| `tests/test_api.py` | the mutating-surface set gains `POST /records/{evidence_id}/verify`; one docstring sentence now says three evidence acts instead of two |
| `tests/test_status_consistency.py` | the anchored-pointer witness's own probe destination is **read from `routes.py`** instead of hard-coded at 373 — a hard-coded line is a value that changes the day a route joins above it, and the witness's comment now says the verify route moved it |
| 7 documents (`docs/RELEASE-NOTES.md`, `docs/REVIEW-DOSSIER.md`, `docs/THREAT-MODEL.md`, two plans, one work-orders draft, `web/README.md`) | **citations re-pointed only** — the routes and CLI command added lines above pointers those documents carry, and the pointer witness names the destination; no words changed |

**The shard costs are stale, by the tree's own rule.** The work changes files
under `src/` and adds a test file, so `.github/ci-shards.json`'s witness will
fail until `python .github/remeasure_shards.py <run-id>` runs against a CI
run's log. The numbers must come from a runner; this window did not run CI
and did not guess. The batch's one pull request and one run supply the
run id. **The new test file must be registered** — the shard list and the
evaluation manifest are the integrating session's files, because other
windows in the batch add files too.

### What was measured

All commands run in the worktree, with `TEMP`/`TMP` at
`E:\labcairn-local\tmp` and distinct `--basetemp` per run:

| Command | Result |
| --- | --- |
| `ruff check` over the changed files | clean |
| `ruff format --check` over the changed files | clean, 9 files |
| `mypy --strict` (the project's full configuration) | clean, 515 source files |
| `pytest tests/test_evidence_verify_door.py -m integration` | 6 passed, 6.53s |
| `pytest tests/test_evidence_verify_door.py -m e2e` | 3 passed, 25.06s |
| `pytest tests/test_surface_status_reach.py` | 4 passed, 1.63s |
| `pytest tests/test_application_evidence.py` | 20 passed |
| `pytest tests/test_evidence_store.py` | 28 passed |
| `pytest tests/test_api.py` (the five contract and mutating-surface tests) | 5 passed |
| `pytest tests/test_status_consistency.py` | 597 passed, 16.82s |
| `pytest tests/test_record_citations.py tests/test_cli_evidence_writer.py tests/test_cli_confirmation_guidance.py` | 46 passed, 201.81s |

**One fact about this table's provenance.** The worktree the work was first
measured in was **removed by the host while the changes were uncommitted**;
the changes were rebuilt from this session's own operation log (every write
and edit recorded as it happened), and every run above was re-measured on the
rebuilt tree before the branch was committed. The branch's commit is the
durable copy; the numbers are the rebuilt tree's, not the lost one's. Nothing
about the product's behaviour depends on this, but a reader comparing a
number here with a missing worktree deserves to know which one was measured.

**The witnesses were mutation-checked, and each mutation is red for its own
property, not for lint or an import error.** Twelve cases, twelve reds; the
source was restored byte-for-byte after each:

1. the operation asks `advance` for `extracted` instead of the status — the
   pass witness fails;
2. the operation runs no check before judging the move — the failing-check
   witness fails (no verdict in the log, no outcome in the message);
3. the C4 guard is removed — the C4 witness fails (the wrong reason, and a
   log entry it said would not exist);
4. the transition table allows `planned -> verified_by_rule` — the proposal
   witness fails;
5. the operation stops checking the record's task — the cross-task witness
   fails;
6. `verified_by_rule` is removed from `CITABLE_STATUSES` — the gate witness
   fails;
7. the CLI sends `c1` whatever the operator typed — the console witness
   fails;
8. the CLI lets an unknown `--check` escape as a traceback — the CLI refusal
   witness fails;
9. the API route sends `c1` whatever the body said — the route witness
   fails;
10. the CLI calls the store's writer itself — the static witness fails;
11. the operation stops calling the writer — the static witness fails;
12. a surface holds the status column's SQL — the SQL-boundary witness
    fails.

The limits of these measurements: no runner measured them (no CI run, by the
batch's rule), so the shard costs above are stale rather than re-measured;
the CLI's end-to-end witnesses drive the console script from the worktree via
`PYTHONPATH`, not from a fresh install; and the API witness uses the
service's own `create_app` with the test's event-source adapter, as the two
other API test files do.

### What the witness now says

`tests/test_surface_status_reach.py` keeps its path and its subject; its
direction is inverted. It now asserts:

1. **the verify operation is the one caller of `store.advance`** under
   `src/` — a tree with no caller would be the old gap back, and a tree with
   a second caller would be a surface that skipped the layer;
2. **the call asks for `VerificationStatus.VERIFIED_BY_RULE`** — a wired
   writer asked for another status would leave the state unreachable;
3. **CLI and API import `verify_claim` and never call the writer or name the
   status member outside the operation**;
4. **the status column's SQL lives only in `evidence/store.py`.**

The record's old claims that are now **false for this tree**, and the
measurement above is the one that is superseded:

* *"no record can ever hold `verified_by_rule` through any surface"* — one
  can, through `task claim-verify` and `POST /records/{id}/verify`;
* *"the reachable state machine is three states wide"* — it is four wide
  now: `extracted -> verified_by_rule` is reachable from a person's act;
* *"C2 and C3 re-verification in the gate is dead code on any record the
  product wrote"* — it is live on rule-verified records, and the gate
  re-runs the logged checks before the report cites them;
* *the middle member of `FINDING_STATUSES`* — a report can now state a
  finding in `verified_by_rule`.

Still true, and now by construction rather than by absence: the store
remains the only writer, and the surfaces reach it only through the layer's
operation.

### What the closing did not decide

* **Which claims deserve a rule's pass.** The surface runs the check the
  operator names; nothing in it chooses a check for a claim. The record's
  option A said this is a second decision, and it is still open.
* **Option B's question** — whether verification should live only inside the
  analysis pipeline — is untouched: the pipeline still appends nothing to a
  record's log, and the new door does not make it do so. **A later window
  has since measured the pipeline's capacity** (see the options section and
  "What was not measured" above), and its finding is that the pipeline
  **could not** carry the ledger's rules as they stand — a computed number
  cannot be anchored, so C1, C2 and C3 have nothing to read. **The question
  itself remains the owner's**, and the record does not choose.
* **Behaviour under a writer outside the product** is no longer unmeasured —
  the writer window measured it, and what it found is the section below. The
  new door does not close that line, and does not pretend to.

## The writer outside the product

**This section closes the last open item of "What was not measured" above.**
It is a third window's account, written after the closing window that wired
the verify door. It changed nothing under `src/`: the product is not what was
measured here.

**The tree the measurement was taken at:** `7bcfe53952e969ee1736af3623a656927d550d62`
(this worktree's branch tip, `claude/zealous-noyce-54abd1`) plus this
window's two files, which land in the commit this section is committed with.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13 (the project's own
`.venv`).

**A measurement note that is part of the evidence.** The `.venv`'s editable
install names the **main checkout** (`E:\LabCairn\src`), not this worktree.
A bare `pytest` run therefore imports and migrates the main checkout's tree.
The first mutation check this window ran was therefore **measuring the wrong
tree**: it mutated this worktree's `src/` and `migrations/`, and every
mutation came back green, because the tests never loaded the files that
were changed. That is the failure mode the repository's own rules warn
about — *"a copied virtualenv is not a virtualenv of its own"*, and the
check that settles it is *"apply a mutation that only the console script can
reach, and see whether the witness fails"*. Every run this window reports
sets `PYTHONPATH` to this worktree's `src`, and the mutation script guards
it: it prints the module path the tests load and refuses to mutate
anything unless that path is inside this worktree.

### The writer

`tests/test_evidence_outside_writer.py` holds it, as `OutsideWriter`. Every
method is a `connection.execute` of a SQL string. It never imports
`EvidenceRecord`, never calls `append_record`, and never touches the
application layer — it holds the database the way `psql` holds it, and it
commits, because a refusal that only holds until the next transaction is not
a refusal.

It writes into a database that is otherwise indistinguishable from one the
product wrote: the same migrated schema (at head), the same source, the
same page of text, the same anchor. The fixture is the store's own, copied
from `tests/test_evidence_store.py`.

### The three attempts, and what each refusal actually did

**Attempt 1 — the model.** The writer landed a row whose status is
`verified_by_rule`, with a span, a span hash, a source hash and a non-empty
anchor key — so every schema CHECK was satisfied — and **no log entry at
all**.

*The write succeeded.* The row is in the database; the schema accepted it.
The refusal came when the *product* read the row back:
`load_record` raised `pydantic.ValidationError`, and the model's own message
is the one the record's model validator carries:

> verified_by_rule requires a verification_log entry with check in {c1, c2,
> c3} and outcome 'pass' (ADR-0004 Contract 2). Status without a log entry
> is a schema violation (I3).

**The model's refusal held.** It held at *read*, not at write — the model is
not in the write path of a writer that does not use it, so a forged row sits
in the database until something reads it.

**Attempt 2 — the store boundary.** The writer's one way through the store
is `append_record`, and it handed it a record whose status is
`verified_by_rule` and whose log names `a.person` — a checker id no build
implements. The store refused with its own `LedgerError`:

> Contract 2: a verified_by_rule record needs a passing entry from a
> checker_id in the registered rule catalog, and 'a.person' is not one.

**The store's refusal held, and it was demonstrably the store's.** The
record in that attempt is *constructed successfully* before `append_record`
is called — the model was asked and said yes. So the refusal that follows
can only be the store's, which is the division of labour the store's
docstring claims, measured rather than asserted. The append also left no
row behind.

**Attempt 3 — the schema.** The writer landed a row whose status is
`verified_by_rule` with no span, no span hash, no source hash and an empty
anchor key. The database refused the write outright, and named the
constraint:

> CHECK constraint failed: ck_evidence_records_evidence_records_located_past_planned

**The schema's refusal held**, and it held at the earliest possible moment —
inside SQLite, on the write, before any product code runs. A second schema
refusal was measured on the same writer: a status outside the vocabulary
(`verified_by_ruel`) is refused by
`ck_evidence_records_evidence_records_status_vocabulary`.

**A third refusal the item did not name.** The migrated schema has **no
triggers** — revision 0005's own comment says why ("triggers would keep the
index in step with writes by the application, and silently miss every write
by anything else"). So there is no fourth layer waiting to catch a writer
that bypasses the three.

### What the three refusals do not add up to

This is the finding, and it is not what the open item anticipated.

**The three refusals each held, and together they leave a path open.** The
writer landed **two** rows and no product code:

1. a located row whose status is `verified_by_rule` (satisfying every CHECK
   the schema has), and
2. a `verification_records` row claiming C1 concluded `pass`, with
   `checker_id` `c1.source_exists` — an id that **is** in the registered rule
   catalog, because the writer copied it from a real check.

What happened, in order:

- **The schema accepted both rows.** Every CHECK was satisfied.
- **The store never saw the write.** It was not in the store's path.
- **The model accepted the row back.** `load_record` returned a record in
  `verified_by_rule` carrying one log entry.
- **The report's evidence gate accepted it too.** The gate — the last thing
  that runs before a report says something — judged the forged record and
  reported `passed` with **no findings at all**.

**Why each of the three refusals did not stop it.**

- The **model** requires *a* passing entry. It does not require the entry
  to be *true*, and it cannot: a `VerificationRecord` is a statement about
  the past, and the model has nothing to compare it against.
- The **store boundary** holds the registered-rule rule — but the writer
  used a *registered* id, so there was nothing to refuse. The store's rule
  is about *which* rules may vouch, not about whether the vouch happened.
- The **schema** holds the location rule — and the writer satisfied it,
  because a located row is easy to write.

**The narrow finding this does *not* make.** The gate does have a power the
three refusals do not: it re-runs the checks the log records, so a forgery
it can *disprove* is caught as a drift finding. A forged **C2** pass is
caught (re-running C2 says `fail`, because the record's text is not the
source's text). A forged **C1** pass whose anchor resolves *nowhere* is
caught (re-running C1 says `fail`). But a forged **C1** pass whose anchor
*does* resolve is **not** caught — because re-running C1 confirms it. That
is the narrow case, and it is the case the gate's own power cannot reach.

**Two further costs of a forged row, measured.**

- A forged **status alone** — a bare `UPDATE` of a legitimate located
  record's status, with no log entry — leaves the record **unreadable**
  rather than falsely verified. The model's I3 refusal fires on the read.
  A forged status *breaks* the record; a forged status *plus* a forged log
  entry *disguises* it.
- A forged row makes the **whole task** unreadable, not just the row:
  `load_task_records` loads and validates every record the task holds, so
  one forged row without a log entry takes the task with it.

### The witness, and the mutation check

`tests/test_evidence_outside_writer.py` — one file, eight tests, all
`negative`-marked. The claim is watched rather than asserted:

| Test | What it holds |
| --- | --- |
| `test_the_model_refuses_a_verified_row_the_writer_landed` | the model's I3 refusal fires on the row the writer landed |
| `test_the_store_boundary_refuses_a_verified_row_from_an_unregistered_rule` | the store's catalog refusal fires, and is the store's and not the model's |
| `test_the_schema_refuses_a_verified_row_with_no_location` | the schema's location CHECK fires, by name |
| `test_the_schema_refuses_a_status_outside_its_vocabulary` | the schema's vocabulary CHECK fires, by name |
| `test_the_three_refusals_do_not_add_up_to_a_closed_door` | **the open door**: the forgery is read, and the gate passes it with no finding |
| `test_the_gate_catches_a_forged_entry_that_re_running_would_refuse` | the gate's own power catches what it can disprove |
| `test_a_forged_status_alone_leaves_the_record_unreadable` | a forged status breaks the record rather than verifying it |
| `test_a_forged_row_breaks_the_task_that_holds_it` | a forged row takes the task with it |

**The witness is not satisfied by the store's own refusals**, which is what
the open item said was already covered: four of the eight tests drive the
writer's raw SQL, and the two that call `append_record` do so to show that
*the store's* refusal is the store's.

**The registration this file needs.** It is `negative`-marked, so the
integrating session files it in `tests/evaluation/manifest.py` under the
`negative` class — its own marker rules out the others — with the clause
`fabricated-citation`: the outside writer fabricates a verification the
product never performed. It also needs a shard entry in
`.github/ci-shards.json` with a measured cost, and the shard file's cost
witness will be red until the costs are re-measured on a runner.

**The mutation check, and what it measured.** Each witness was made red by
breaking the property it watches, with the tree restored after each one, and
the guard in place that proves the tests load this worktree:

| Mutation | The witness | Result |
| --- | --- | --- |
| the model stops refusing a status with no passing log entry | the model's refusal | **red** — `DID NOT RAISE ValidationError` |
| the store stops consulting the registered rule catalog | the store's refusal | **red** |
| the schema's `located_past_planned` CHECK is neutered | the schema's location refusal | **red** — `DID NOT RAISE IntegrityError` |
| the schema's `status_vocabulary` CHECK is neutered | the schema's vocabulary refusal | **red** — `DID NOT RAISE IntegrityError` |
| the gate stops re-running the checks the log records | the gate's drift finding | **red** — `passed=True` |
| the gate starts refusing a `verified_by_rule` record | the open door | **red** — the gate found the forgery |

**The sixth mutation is the one worth reading twice.** The open-door witness
is red when the door *closes*: a tree that refuses a forged
`verified_by_rule` record at the gate would fail that test. It is a
**floor, not a ceiling** — it says the door is open *now*, and a tree that
closes it must update this test and this record together. That is the
correct direction for a witness of an open door, and it is why the test
asserts that the forgery *succeeds*.

### What is left open

- **The door itself.** The three refusals hold, and a writer outside the
  product can still land a record the report's gate accepts with no
  finding. Nothing under `src/` changed here, so this is not a regression
  — it is a property of the tree as measured, and it was not named anywhere
  before this section.
- **What to do about it.** That is the owner's call, and the record's job is
  to make the decision a real one. The measurement says what the cost of
  each shape would be: a gate that refuses a `verified_by_rule` record whose
  log cannot be re-confirmed (a check, a trigger, or a signature over the
  log) would close the narrow case this section found; a rule that the
  *store* holds — rather than the model — would not, because the writer
  used a registered id.
- **The `verified_by_rule` half of `CITABLE_STATUSES`** remains live for
  the product's own records and is now also reachable by a writer outside
  it.
