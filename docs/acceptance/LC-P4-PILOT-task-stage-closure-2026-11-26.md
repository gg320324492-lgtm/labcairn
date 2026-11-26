# LC-P4-PILOT — the two bookkeeping gaps, closed and witnessed

**Ticket:** LC-P4-PILOT (pilot preparation, the first round's §6 findings)
**Date:** 2026-11-26 (the change and its witnesses), recorded 2026-11-26.
**Tree:** `ddfee5ff262641d6647551de3621daf9bdbb5ebe`, branch
`claude/task-stage-closure`, based on `main` @
`e6822fc15daa5eb63379c1690bcabf22030d8769`. Windows 11 Pro (10.0.26300
x64, AMD64), Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Origin record:** [`LC-P4-PILOT-first-round-2026-11-26.md`](LC-P4-PILOT-first-round-2026-11-26.md)
§6, items 1 and 2 — the two gaps this record closes.
**Material:** **none was read.** The witnesses build a synthetic chain under
the test's own temporary directory; nothing under `E:/labcairn-local/` is
opened by this work, and no document text, digest of a document or key
appears in this record.

**What is claimed here.** Two things about the product's own bookkeeping,
both measured on this tree:

1. **A refusal on a task path now writes an event.** The ask
   (`request_role_run`), the spend (`run_role_run`) and the service's own
   no-backend refusal (`run_role_run_service`) record the refusal's
   reason, its message and the ask before raising it. The event is
   Task-level: it names no run, stage, operation or transition.
2. **An answered request closes what asked for it.** When the approval a
   stage was parked on has been consumed and its request answered, the
   operation is confirmed, the stage completed and the run finished in one
   transaction, with `operation_confirmed`, `stage_completed` and
   `run_finished` written in that order.

**What is not claimed.** No live pilot round was re-run against this tree:
the two origin findings were **reproduced as test fixtures**, not replayed
on `E:/labcairn-local/pilot-ws`, and this record does not stand in for a
pilot record. No CI run was made (the owner starts the batch's one run),
so every number below is a **local** reading and says so in §6. The other
paths that share the same class of gap are named in §7 and were **not**
changed.

**The boundary this record obeys.** Ids, keys, counts, paths and commits.
No sentence of any material, no advisor mark, no credential and no digest
of a document's bytes. The evidence is the commit and the tests; there is
no external artefact to point at.

## 1. What was read, before anything changed

The origin record's §6 was read first, then the code the two findings name:

- `src/labcairn/runtime/event.py` — the closed `EventType` vocabulary,
  the four scope rules (`run_id` required for the five Run-scoped
  families; annotations carry neither run nor operation context; a
  transition is required exactly of the names that begin `run_`, `stage_`,
  `operation_`, `approval_`), and `EVENT_PAYLOAD_SCHEMAS`, whose rule is
  that a type with no registered schema must carry an empty payload.
- `src/labcairn/application/records.py` — the module's write rules. The
  bullet that said "nothing is written on a refusal — except a policy
  denial" was the rule the first finding broke, and it has been rewritten
  in §3.1's terms rather than left beside the new event.
- `src/labcairn/application/roles_run.py` — the ask and the spend, and
  the refusal the origin record measured: `_the_chain` raises
  `ROLE_COMMENT_NOT_IN_THE_CHAIN` when the chain holds no comment under
  the key, and nothing wrote it down.
- `src/labcairn/application/approvals.py` — `request_approval` plans the
  operation, parks the stage as `blocked` and asks; `consume_approval`
  spends the row and moves the operation to `authorized` with
  `operation_intent`. Neither closes the stage.
- `migrations/versions/0032_denied_operation_events.py` — the vocabulary
  rebuild and the reason the four sets are written out in the migration
  instead of imported from the live package.
- `tests/test_store_migrations.py` — the 0032 witness's shape, used as
  the pattern for 0033's.
- `tests/test_store_events.py` — the DDL-versus-enum witness, which held
  the vocabulary count as a literal.

## 2. What the tree said, and what it did not

The origin record measured both findings on the pilot copy; this section
says what the same questions read on this tree before the change.

**The refusal.** `run_role_run` and `request_role_run` raised
`ApplicationRefusedError` with no write of any kind. A surface caught it,
rendered the reason and the message, and the event log was unchanged. The
origin record's measurement stands as the reading: the task's events for
that day ran `seq 57 … 73` — seventeen events — with no entry for the
refusal.

**The stage and the run.** `request_approval` wrote `run_started`,
`stage_entered`, `operation_awaiting_approval`, `approval_requested` and
`stage_blocked`; `consume_approval` wrote `approval_consumed` and
`operation_intent`; `request_model` wrote `model_exchanged` after the
wire. Nothing wrote `stage_completed` or `run_finished`, so the stage row
stayed `blocked` and the run row stayed `running` after the request had
been answered. `complete_operation` was the only writer of
`stage_completed`, and the roles-run path never reached it.

## 3. What was built

### 3.1 The refusal event

`EventType.REFUSAL_RECORDED` (`refusal_recorded`) is a Task-level
annotation. It is in `ANNOTATION_EVENTS`, and the vocabulary's own rules
then force its shape: `run_id` must be `None`, `operation_id` must be
`None`, and it must carry no transition. That is not a convenience — a
refused request may have been refused before any Run existed, and
inventing a Run for it would be a trace that could be mistaken for a
partial success.

Its payload (`RefusalRecordedPayload`) carries three fields:

| field | what it is |
| --- | --- |
| `reason` | the layer's closed code, e.g. `role_comment_not_in_the_chain` — the word a machine branches on |
| `message` | the message the person was shown, naming the instance rather than the class |
| `asked_for` | the request, as a flat mapping: the operation, the roles, the project, the issue key, versions, rule and approval id — ids, keys and counts, never material text |

`records.record_refusal` writes it in its own unit of work. The three
public operations record before they raise: the ask, the spend, and the
service's own backend refusal (which never reaches the spend's wrapper).
The exception the caller receives is unchanged.

### 3.2 The closure

`records.complete_consumed_approval(context, approval_id=…, now=…)` reads
the approval back, checks that it is `CONSUMED`, finds the operation it
names, and requires that operation to be `AUTHORIZED`. It then calls
`complete_operation(..., run_to_finish=run)`, which writes, in one
transaction and in this order:

1. `operation_confirmed` (`authorized → confirmed`),
2. `stage_completed` (`blocked → completed`, clearing `blocked_reason`),
3. `run_finished` (`running → finished`, setting `finished_at`).

The rows are put in the same unit, so an event and the state it describes
cannot come apart. A retry that finds the closure already written returns
the rows and writes nothing; any other combination of states is refused
rather than guessed at.

A clock that has moved backwards between the ask and the spend cannot
make a run finish before it started: `finished_at` is the later of the
caller's moment and the run's `started_at`. The event's `occurred_at`
still records the moment the closure ran, which is the informational use
that field has always had.

`run_role_run` calls the closure immediately after `request_model`
returns — the approval is spent and the request is answered — and before
the roles do their own work. A role that then refuses writes a refusal
event; it does not unstate the call that happened.

### 3.3 The migration

The vocabulary is four `CHECK` constraints on the `events` table.
`migrations/versions/0033_refusal_events.py` rebuilds the table with the
set that includes `refusal_recorded`, using the direct-DDL rebuild
revision 0032 established (batch mode reflects the live schema, and
revision 0002 found that reflection silently does nothing on this table).

The downgrade rebuilds the table with the four sets as they stood at
0032. The 0033 sets were compared, programmatically, against both
revision 0032's frozen tuples and the live `EventType` derivation; all
seven sets agree in both directions.

## 4. The witnesses

| # | file | what it asserts | red when |
| --- | --- | --- | --- |
| W1 | `tests/test_task_stage_closure.py` | an ask refused for a key the chain does not hold leaves exactly one `refusal_recorded` event, task-level, carrying the code, the message and the ask | the ask's record is removed |
| W2 | same | a spend refused for want of a provider invocation leaves the same shape, with the ticket's approval id in the ask | the spend's record is removed |
| W3 | same | the service's no-backend refusal, which never reaches the spend, is recorded too | the service's record is removed |
| W4 | same | after an answered request: the approval is `consumed`, the operation `confirmed`, the stage `completed` with no blocked reason, the run `finished` at the recorded moment; the log's tail is `operation_confirmed → stage_completed → run_finished`, after `model_exchanged`, with the transitions `blocked → completed` and `running → finished` | the closure after `request_model` is removed |
| W5 | `tests/test_store_migrations.py` | a store downgraded to 0032 refuses `refusal_recorded`; after the upgrade it accepts a row that carries no run, stage, operation or transition | the upgrade builds the old vocabulary |

W4 asserts facts, not the absence of an error: the four row states are
read back from the store and the three transitions are read from the
committed events.

## 5. The mutations

Each witness was checked against a mutation of the code it watches; the
mutation was applied, the witness observed red, the file restored, and
the witness observed green again. The restored files are the ones in the
commit named above, so the green reading is reproducible from the tree.

| mutation | witness | observed |
| --- | --- | --- |
| ask's `record_refusal` removed | W1 | red: the log held no new event (`assert [] == [REFUSAL_RECORDED]`) |
| spend's `record_refusal` removed | W2 | red: the log held no new event |
| service's `record_refusal` removed | W3 | red: the log held no new event |
| closure call removed | W4 | red: the operation read `AUTHORIZED`, not `CONFIRMED` |
| 0033 `upgrade()` built the 0032 vocabulary | W5 | red: the insert after the upgrade raised `CHECK constraint failed: ck_events_type_is_closed_vocabulary` |
| watch: the TypeScript contract | `test_api.py`'s checked-in-TS witness | red before regeneration, green after — a generated-artefact change, not a vocabulary defect |

## 6. Where each number came from

Every number in this record is a local reading on this tree at the commit
named above, unless a row says otherwise. The runs used `COLUMNS=200`,
`TEMP` and `TMP` under `E:/labcairn-local/tmp*`, and a `--basetemp`
outside the repository; no two runs shared a base temp directory.

| number | where it is used | how it was read |
| --- | --- | --- |
| `32` event types | §3.1, §3.3 | `python -c "from labcairn.runtime.event import EventType; print(len(EventType))"` → `32`; the membership check printed `True` for `refusal_recorded` |
| `31` before | §3.1 | the value `tests/test_store_events.py` asserted at `e6822fc`; it is re-measured there as `32` |
| `0033` / `0032` | §3.3 | `alembic.script.ScriptDirectory.from_config(...).get_heads()` → `['0033']`; 0032 is 0033's `down_revision` |
| `8` files, `+1,291 / −28` | the change | `git show --stat --format="" ddfee5f` |
| `4` witnesses in W1–W4 | §4 | `pytest tests/test_task_stage_closure.py -q` → `4 passed` |
| `1` migration witness | §4 W5 | `pytest tests/test_store_migrations.py::test_a_store_at_the_previous_head_reaches_the_refusal_event_after_the_upgrade -q` → `1 passed` |
| `17` events, `seq 57 … 73` | §2 | **not re-measured here**; read from the origin record §6 item 1, which measured it on the pilot copy |
| `28` | §8 | `pytest tests/test_roles_run.py -q` → `28 passed` |
| `34` | §8 | `pytest tests/test_role_run_entry.py tests/test_task_stage_closure.py -q` → `34 passed` |
| `18` | §8 | `pytest tests/test_store_migrations.py -q` → `18 passed` |
| `155` | §8 | `pytest tests/test_runtime_contracts.py tests/test_store_events.py tests/test_feedback_event_stream.py -q` → `155 passed` |
| `18` | §8 | `pytest tests/test_application_approvals.py tests/test_approval_binding.py -q` → `18 passed` |
| `25` | §8 | `pytest tests/test_recovery_stage_bridge.py tests/test_apply_cancel_recover.py tests/test_approval_crash_matrix.py tests/test_cancel_entry.py -q` → `25 passed` |
| `67` | §8 | `pytest tests/test_event_payload_vocabulary.py tests/test_diagnostics_package.py tests/test_operation_states.py tests/test_store_persistence.py tests/test_store_concurrency.py tests/test_recovery_crash_matrix.py -q` → `67 passed` |
| `212` passed, `1` skipped | §8 | `pytest tests/test_api.py tests/test_application_layer.py -q`; the one failure in that run was the checked-in-TypeScript witness, which passed alone after regeneration |
| `128` / `342` / `480` | the change | `git show --numstat --format="" ddfee5f`: insertions in `roles_run.py`, lines in the new migration, lines in the new test file |

## 7. What the work did not exercise, and what looked wrong

**It did not exercise the pilot copy.** The two findings are reproduced as
fixtures: a synthetic chain, a scripted model answer, a fixed moment. No
real request was made, no provider was reached, and nothing under
`E:/labcairn-local/` was read. The pilot's own numbers (the seventeen
events, seq 57 to 73) are the origin record's reading, not this work's.

**It did not run CI.** The owner starts the batch's one run. Locally, the
changes under `src/` and `tests/` move the shard costs' measured commit,
so `tests/test_ci_shard_coverage.py` is expected red until the runner
re-measures; and the new test file has no cost entry, which is the same
red. The main session registers `tests/test_task_stage_closure.py` in
`tests/evaluation/manifest.py` as `("integration", "state-transitions")`
and re-measures the shards from the next run.

**The same gaps remain on other paths.** These were reported, not
widened:

- **Every normal `run_stage` completion leaves its run `running`.** The
  ordinary path writes `stage_completed` and never `run_finished`; only
  the approval path gained the finish here. The same class as origin
  finding 2.
- **`extract_claim` (`src/labcairn/application/extraction.py`)** spends
  an approval through `request_model` and never confirms the operation or
  completes the stage; its approval stage stays `blocked` after an
  answered request. The same class as origin finding 2.
- **No `operation_attempted` in the roles-run path.** `consume_approval`
  moves `awaiting_approval → authorized`; the call happens; the closure
  writes `authorized → confirmed`. The operation never enters
  `ATTEMPTING`, so a crash during the wire call is invisible to recovery:
  the operation is still `AUTHORIZED` and the approval `CONSUMED`.
- **The exchange and the closure are two transactions.** A crash between
  them leaves the origin chain exactly — the call recorded, no
  completion; nothing retries a role run.
- **The clock clamp hides a caller error.** An `at` earlier than the
  run's `started_at` now records `finished_at = started_at` rather than
  failing after a paid call. `tests/test_role_run_entry.py` mixes a
  wall-clock ask with `at=MOMENT`, which is how the case surfaced.

**One check was not available on this machine.** `test_api.py` skips one
POSIX-permission-bits case on Windows; the suite reports it as skipped,
not passed.

## 8. Where the evidence is

- The commit: `ddfee5ff262641d6647551de3621daf9bdbb5ebe` on branch
  `claude/task-stage-closure`, based on `e6822fc`. Its diff is the
  evidence for every claim about the code.
- The witnesses: `tests/test_task_stage_closure.py` (W1–W4) and the 0033
  witness in `tests/test_store_migrations.py` (W5).
- The mutation table in §5 is the evidence for the witnesses' power; the
  restored tree is the commit.
- The local runs in §6 are the evidence for the numbers; each command is
  written beside its number so a reader can repeat it.
- The origin reading for the pilot's seventeen events is the first-round
  record, §6; this record did not re-measure it.

## 9. What this record is not

It is not a pilot round: it touched no real material and made no request.
It is not a CI reading: it is local, and the shard costs are owed a
runner. It is not a claim that the product's bookkeeping is complete: §7
lists the paths where the same class of gap remains, and §3.2's closure
was applied to one path because that is the path the pilot measured. And
it is not an acceptance of the origin findings as fixed everywhere — it
is the record of the two that were, and the measurement that says so.