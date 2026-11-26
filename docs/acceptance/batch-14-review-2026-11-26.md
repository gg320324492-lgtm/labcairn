# Batch 14 review — the two bookkeeping gaps, and the floor nobody was watching

**Date:** 2026-11-26
**Range reviewed:** `f060ede..94ee182` on `main` — one window's work,
merged; the shard costs re-measured from a runner; the registration that
follows a new test file; and one witness this review added.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.**

| Piece | Commit | What it is |
|---|---|---|
| the window's work | `ddfee5f` | a refusal writes an event; an answered request closes the operation, the stage and the run; migration `0033`; six witnesses |
| the window's record | `29bb400` | [`LC-P4-PILOT-task-stage-closure-2026-11-26.md`](LC-P4-PILOT-task-stage-closure-2026-11-26.md) |
| the re-measurement | `f35c52b` | the shard costs read out of the seventh round's runner log, and the three documents that print costs |
| the registration | `193f244` | the new test file in the manifest and in a shard |
| this review's witness | `94ee182` | the floor the narration names, checked against the table |

## R1. No witness depends on a build artifact the runner does not have

**Pass.** The six new witnesses build their own chain in the test's own
temporary directory: the record says so in its own header — *"The material
is a fixture, not the pilot's... nothing under `E:/labcairn-local/` is
read"* — and the file agrees, holding no path outside the checkout. The
migration witnesses build a store in a temp directory and migrate it.

**One thing worth naming.** `web/src/api/generated.ts` changed with the
new event type, and it is a checked-in generated file. **That is not a
dependency on a build artifact**: it is a contract that lives in the
repository and has to match the Python side's OpenAPI. The window
regenerated it rather than leaving the two apart, and `tests/test_api.py`
compares them — which is the witness that would have been red otherwise.

## R2. No witness hard-codes one platform's facts

**Pass.** The new test file holds no `os.name`, no `sys.platform`, no
drive letter and no backslash path. The record names the machine it was
taken on, which is a fact about a reading and not a fact the code assumes.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass, and this batch added one.** The window added no new guard, so
there was no guard of a guard to witness; the new test file contains no
`skip`, no `skipif` and no `xfail`, so **no arm of it can pass by not
running**.

**The guard that did not have a guard.** The shard coverage file checked
the cost figures the workflow's narration prints — and that check printed
the cost of `tests/test_cli.py`, **the floor of an earlier tree**. The
narration's own sentence about the floor named a different file and was
never compared with the table. That gap was live for eleven days (see
R6), and `94ee182` closes it: the file the sentence names must be the
heaviest the table records, the figure it prints must be that file's
measured cost, and the Windows figures beside it must be the partition the
table produces. **Two mutations were checked to turn it red** — naming the
wrong file, and moving the cost by a tenth of a second.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** The record states the stronger thing: **no material was read at
all**. The two origin findings were reproduced as fixtures, not replayed
on the pilot workspace, and the record says so rather than implying the
pilot's copy was involved. No document text, no document digest and no
key appears in it.

## R5. A documented rule and its implementation say the same thing, and both sides are witnessed

**Pass.** The event vocabulary gained `refusal_recorded`, and the refusal
the pilot hit — an exit code and a line on stderr that lived and died with
the process — is now something the log holds. The rule is stated in the
event's own schema and in the record, and the implementation writes it on
three paths: the ask, the spend and the service's own no-backend refusal.

The event is **task-level and names no run, stage, operation or
transition**, so a refusal cannot be read as an attempt. That is a
property with a witness, not a convention.

The migration is a new revision on the single head (`0033` over `0032`),
its downgrade restores the `0032` shape, and `tests/test_store_migrations.py`
carries a witness for each direction — a store built before the new
event type reaches it after the upgrade, and a store downgraded to `0032`.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, and this is where the batch's real work was.** The shard costs
were re-measured from the **seventh round's runner log**, read by
`.github/remeasure_shards.py` — not from this machine, because a
development machine gives a different answer and not only a different
total but a different *order*. The anchor moved to `e6822fc`, the new
files carry measured costs instead of `0.0`, and the partition was rebuilt
from them.

**And the re-measurement caught a lie that had been standing for eleven
days.** The workflow's narration said the Ubuntu floor was
`test_drill_interrupted_writes.py` at 604.0 s against 306.7 s for the
other shards, a max/min of 1.969. **The table says otherwise**: the floor
moved to `test_drill_rewrite_interrupted.py` on 2026-11-15, when the
six-shard arrangement was put in place, and it has been the longest file
ever since — 1204.9 s under the old measurement, 1205.8 s under this one.
The sentence named a file that was never the floor and a ratio the
partition has not had since November.

**Why nothing was red.** The witness that checks the printed figures
looked for the cost of `test_cli.py`, which is the floor of an earlier
tree. The floor sentence names a different file, so the two never met.
**A record that is not watched is not held**, and this one was not.

The three documents that print costs were corrected with the table:
`python.yml`'s narration, `.github/CI.md`'s offline-run cost and the
evaluation plan's table — the last of which moved from 3509.7 s to
3820.4 s on Ubuntu, and from 8572.6 s to 9389.1 s on Windows.

**Still owed.** `tests/test_task_stage_closure.py` carries `0.0` in the
cost table: it has never been on a runner, and the next round is what
will supply its number.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The chain the witnesses build is the **premise** — a workspace
with a task and a stage — and what they watch is the **product's output**:
the events the product wrote, and the state the product left behind. No
witness writes the refusal event or the closure itself and then checks
its own work.

The same question was asked of the record, and it answers it: it says the
two origin findings were **reproduced as fixtures rather than replayed on
the pilot workspace**, and it names what it did not exercise.

## The second reader

**A reader who has not seen the pilot can check every claim.** The
window's record needs no material and no workspace; the re-measurement
needs a runner log and the tool that reads it; and the new witness needs
only the repository. The migration's witnesses build their own store. **The
one claim in this batch that cannot be checked by a reader is the
statement that the pilot's own two gaps are now closed** — that is a
statement about the product's behaviour, and the witnesses are about the
product's behaviour too, so it holds; but it has **not** been replayed on
`E:/labcairn-local/pilot-ws`, and the record says so.

## What this review did not cover

- **The pilot workspace was not touched.** The two origin findings were
  reproduced as fixtures. **The pilot's own event log still shows the
  refusal that left no event**, and it will until a round is run against
  this tree.
- **The record's own numbers** were not re-measured; they are the
  window's local readings, and the record says which they are.
- **The suggestion loop** — untouched by this batch, and still not
  exercisable on a copy without comments.
- **The other gaps the round found** — the stage that stayed `blocked`,
  the read that wrote an event, the orphan source row — are closed by this
  batch only for the stage, and the other two are recorded and untouched.
- **The cost of the new test file**, which is `0.0` until a runner says
  otherwise.

## Where each finding went

| Finding | Where it went |
|---|---|
| The floor the narration named was not the floor, for eleven days | `94ee182` — a witness that reads the sentence against the table |
| The three documents printing costs carried the old figures | `f35c52b` — carried with the table they belong to |
| The new test file was in no shard and in no manifest | `193f244` — registered, with its cost owed to the runner |
| `src/labcairn/core/` has no task, stage or event service to change | the next batch's briefs name the real places: `runtime/event.py`, `application/records.py`, `application/roles_run.py` |
| The checked-in TypeScript contract drifts with the Python OpenAPI | already watched by `tests/test_api.py`; the window regenerated it |
