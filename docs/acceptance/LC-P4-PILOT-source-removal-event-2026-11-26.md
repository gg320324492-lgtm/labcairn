# LC-P4-PILOT — a removal that names the source it took back

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Date:** measured 2026-11-27; this record was written the same day.
**Tree:** `b4e5169f5390df2146d0a452eafd284041b0c17c` (worktree
`relaxed-ardinghelli-e553d2`, branch `claude/relaxed-ardinghelli-e553d2`),
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Workspace for the witnesses:** a temporary workspace under
`E:/labcairn-local/tmp`, built by the tests. The pilot workspace was **not**
written to by this work.
**Predecessor:** [`LC-P4-PILOT-source-removal-2026-11-26.md`](LC-P4-PILOT-source-removal-2026-11-26.md),
whose §7 and §9.1 recorded the gap this record closes.

**What is claimed here.** A removal now writes an event of its own —
`source_removed` — carrying the id of the row that left, its
workspace-relative path, its content digest and the tasks that had to let the
material go. The event is an annotation: no run, no stage, no operation and
no transition. It is written in the same transaction as the deletion, so a
store that cannot take the event does not take the deletion either.

**What is not claimed.** The pilot workspace's own log was not rewritten or
re-measured: a new event type reaches an existing store through migration
0034, and the pilot store is still at the revision it was at. This work did
not run a migration against `E:/labcairn-local/pilot-ws`, and it does not
claim the pilot's §7 counts would now read differently — it claims that the
product, from this tree, writes the naming event.

## 1. The gap this closes

The predecessor record measured
`labcairn sources remove --source src-0738f31ecf1e750b --json` on the pilot
and read the log back: the removal wrote **exactly one** event,
`task_revised`, with `transition: null` and `payload: {}`. The released
task's change was in the log; the row's departure was not. §9.1 kept it as
an observation about the ledger's provenance.

The event vocabulary already had `source_changed`, but that is a different
fact: the material moving under a source that stays. Nothing in the
vocabulary named the row leaving.

## 2. What the product does now

**A new member, in the closed vocabulary.** `EventType.SOURCE_REMOVED =
"source_removed"`, an annotation registered in `ANNOTATION_EVENTS`
(`src/labcairn/runtime/event.py`). It carries no `run_id`, no `stage_id`, no
`operation_id` and no transition, and the event contract refuses each of
those on it — the same rule `refusal_recorded` follows.

**Its payload is a schema, not a bag.** `SourceRemovedPayload` names
`source_id`, `relative_path`, `content_sha256` and `released_task_ids`; a
removal that names no source is unrepresentable, and a payload with an
unexpected key is refused. No material text is in it.

**The event is the removal operation's own.** `remove_source` deletes the
row on the store's session and then hands the commit to
`records.record_source_removed`, whose unit writes the event and commits.
ADR-0003 C3 is the reason: the deletion and the event that describes it
commit together or not at all. The released tasks' `task_revised` events are
still written, one per task, by `bind_sources` — they are a different fact
and they stay.

**A store built before the member existed reaches it through 0034.**
`migrations/versions/0034_source_removed_event.py` rebuilds the `events`
table with the four vocabulary CHECK constraints as the models now derive
them, and its downgrade restores the 0033 shape. Direct DDL, for the reason
revisions 0032 and 0033 record.

**The checked-in TypeScript contract was regenerated.** Running
`python -m labcairn.api.typescript web/src/api/generated.ts` added
`'source_removed'` to the generated `EventType` union; the diff is one line,
and `tests/test_api.py`'s contract witness passes with it.

## 3. Where each number came from

| Number | Where it came from |
| --- | --- |
| 6 witnesses pass | `python -m pytest tests/test_source_removal_event.py -q`, basetemp `E:/labcairn-local/tmp/format-w1`; final confirmation run `…/restored-w1` (6 passed, 25 with the migration file) |
| 19 migration witnesses pass | `python -m pytest tests/test_store_migrations.py -q`, basetemp `E:/labcairn-local/tmp/migrations-w2` |
| 165 pass, 1 fail (vocabulary group) | `tests/test_event_payload_vocabulary.py tests/test_runtime_contracts.py tests/test_store_events.py tests/test_feedback_event_stream.py`, basetemp `E:/labcairn-local/tmp/vocab-w1`; log `E:/labcairn-local/tmp/vocab-w1.log` |
| 139 pass, 1 fail, 1 skip (neighbouring files) | `tests/test_source_removal.py tests/test_application_ingestion.py tests/test_api.py`, basetemp `E:/labcairn-local/tmp/neighbours-w1` |
| 18 pass (CLI parameters) | `tests/test_cli_parameters.py`, basetemp `E:/labcairn-local/tmp/cli-w1` — **read §6 before using this one** |
| 575 files formatted, all checks pass | `ruff check .`, `ruff format --check .` |
| 501 source files, no issues | `mypy --strict` (`files = ["src", "conftest.py", "tests"]`), `MYPYPATH` set to this worktree's `src` |

**How the tests were made to read this tree.** The shared virtualenv's
`_editable_impl_labcairn.pth` names `E:\LabCairn\src`, the main checkout —
so importing `labcairn` without help reads somebody else's code, the defect
`CLAUDE.md` records. Every run above set
`PYTHONPATH=E:/LabCairn/.claude/worktrees/relaxed-ardinghelli-e553d2/src`,
and the first line of the witness file's run proves it: before the setting,
`EventType` had no `SOURCE_REMOVED`; after it, the module resolved from this
worktree.

## 4. The witnesses

`tests/test_source_removal_event.py` — six witnesses, each with a docstring
saying what would make it red:

| Witness | Holds still |
| --- | --- |
| `test_the_log_names_the_source_a_removal_took_back` | the event's payload names **that source id**, its path and its digest — not an event count, and not the survivor |
| `test_the_entry_that_names_the_source_is_not_the_tasks_revision` | the removal's window holds `source_removed` and not `task_revised`; a task revised and a row removed are two facts |
| `test_a_removal_that_released_a_task_says_which_task` | `released_task_ids` names the task, and the task's own revision is still written with an empty payload |
| `test_the_removal_event_is_an_annotation_and_carries_no_attempt` | no run, stage, operation or transition; the seq follows the task's previous event |
| `test_a_removal_whose_event_cannot_be_written_leaves_the_row` | the deletion is rolled back with the event — C3, one direction further than the original gap |
| `test_the_removal_payload_must_name_the_source` | an empty `source_removed` payload is refused by the event contract |

`tests/test_store_migrations.py` — one witness, both directions:
`test_a_store_at_the_previous_head_reaches_the_source_removal_event_after_the_upgrade`.
A raw insert at 0033 must raise on `ck_events_type_is_closed_vocabulary`; the
same insert after the upgrade must land. The insert carries no run, no
operation and no transition, so it also exercises the three "must not" sets.

## 5. The mutations

Each witness was checked to fail under a mutation of the code it watches,
then the code was restored and the witness ran green again (the confirmation
run above).

| Mutation | Red witnesses |
| --- | --- |
| 1. `remove_source` no longer calls `record_source_removed` (and commits the deletion itself) | all five event witnesses (1–5) |
| 2. the payload's `source_id` written as the relative path | witnesses 1 and 2 |
| 3. `session.commit()` inserted between the deletion and the event | witness 5 only — the row stayed deleted although the event was refused |
| 4. `register_payload_schema(SOURCE_REMOVED, …)` commented out | witnesses 1–4 (payload refused as a bag) and 6 (empty payload accepted) |
| 5. `downgrade()` keeps `source_removed` in the vocabulary | migration witness: the insert at 0033 did not raise |
| 6. `upgrade()` leaves `source_removed` out of the vocabulary | migration witness: the insert after the upgrade raised |
| 7. `released_task_ids` passed as `()` | witnesses 1 and 3 |

**What mutation 1 shows about the old witness.** It also leaves
`tests/test_source_removal.py::test_the_removal_is_recorded_in_the_log_as_the_task_s_own_revision`
green, because that witness freezes the old shape — see §6.

## 6. What this work did not exercise, and what it found

**The old removal witness now fails, and this window does not own it.**
`tests/test_source_removal.py` was written by another window
(commit `32d42c4`) and its
`test_the_removal_is_recorded_in_the_log_as_the_task_s_own_revision` asserts
`len(new) == 1` and `new[0].type is EventType.TASK_REVISED`. Its own
docstring says it does not freeze the gap — *"an event that named the
removal would be an improvement rather than a regression"* — but the count
does. With this change the removal writes two events for a bound task: the
release's revision and the removal's own. **The file is outside this
window's ownership map and was not edited.** It needs its assertion changed
to accept both events (the revision, and the naming event), or to scope its
window to the revision's seq. It is the one red the main session must
resolve before the tree is green.

**A counting constant is now one short.**
`tests/test_store_events.py::test_the_vocabulary_constraint_lists_exactly_the_frozen_enum`
asserts the generated CHECks list exactly 32 types, and compares the set with
the enum. With `source_removed` the enum has 33. The set comparison passes;
the count fails. That file is outside this window's ownership map; the
constant and the two docstring sentences that state it need re-measuring to
33. (The project's rule — a value that can change is re-measured, not carried
forward — is exactly what this failure is asking for.)

**The CLI was not measured against this tree.** The installed console script
is a compiled launcher with `E:\LabCairn\src` burned in, so
`tests/test_cli_parameters.py` (18 passed) exercised the **main checkout's**
application layer, and that is a measurement of one tree being read as
another. The CLI itself was not changed by this work; the application layer
and the migration were measured in-process, where `PYTHONPATH` wins. A CLI
end-to-end measurement of the naming event belongs to a tree whose console
script points at it.

**Registration files were not edited.** `tests/evaluation/manifest.py` and
`.github/ci-shards.json` are the main session's to write at merge. The new
file is `tests/test_source_removal_event.py`, whose manifest entry should be
`("integration", "state-transitions")` — the same pair as
`test_source_removal.py`; its shard cost must come from a runner, because
`.github/make_ci_shards.py` refuses to guess one.

**What the event does not say.** The removal command carries no reason
argument, so the payload carries none. `released_task_ids` is the list of
tasks whose binding the removal released; a removal of a source no task
holds carries an empty list, and that is the honest answer rather than a
missing one. The event says nothing about *why* the row was removed — the
operator's intent is not in the command — and nothing about the material's
text, which never belonged in the log.

## 7. Where the material lives

Nothing from the pilot is in this record or in the tests. Every witness
above writes its own bytes into a temporary workspace under
`E:/labcairn-local/tmp` and its own rows into a temporary database there.
The pilot's real material stays under `E:/labcairn-local/pilot-ws`; the only
pilot identifiers named here are the ones the predecessor record already
published (a source id, a path, a digest), and this record does not add a
sentence of the material.

## 8. Evidence

- The code commit this record describes:
  `b4e5169f5390df2146d0a452eafd284041b0c17c`.
- The witnesses: `tests/test_source_removal_event.py`,
  `tests/test_store_migrations.py` (the 0034 witness).
- The vocabulary: `src/labcairn/runtime/event.py` (`SOURCE_REMOVED`,
  `SourceRemovedPayload`).
- The write path: `src/labcairn/application/records.py`
  (`record_source_removed`) and
  `src/labcairn/application/material_ingestion.py` (`remove_source`).
- The revision: `migrations/versions/0034_source_removed_event.py`.
- The contract: `web/src/api/generated.ts` (`'source_removed'`).

## 9. What this record is not

It is not a claim that the pilot's log now holds the event: the pilot store
is where it was, and no migration was run on it. It is not a claim that the
removal is the only way a row can leave, nor that the vocabulary is now
complete for every future departure — it claims one fact, that a removal
written by this tree says which source it took back, and that the claim has
a witness that goes red when it is broken.