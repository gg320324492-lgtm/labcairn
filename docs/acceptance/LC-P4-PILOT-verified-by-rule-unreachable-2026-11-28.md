# LC-P4-PILOT — no surface can move a record to `verified_by_rule`

**Ticket:** LC-P4-PILOT (the gap the owner named on 2026-11-28: the store's
`advance` has no caller).
**Date:** 2026-11-28.
**Tree:** `9ee806f9f32c4cf912d8f26ef3fb2480d3687371` (`main`'s tip as the
batch started, carried on the worktree branch
`claude/adoring-bardeen-ff1f33`). The measurement below was taken at that
commit; the record and the witness it names are the only files this work adds.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13 (the project's own
`.venv`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge, and **no change to any file under `src/`** — this window measures and
records; it does not change the product's behaviour.
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
