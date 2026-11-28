# LC-P4-PILOT — the command line says what the evidence gate judged

**Ticket:** LC-P4-PILOT (the surface gap the review measured on 2026-11-28:
the API returns the gate's verdict and the command line prints neither).
**Date:** 2026-11-28.
**Tree:** `9fff78da38769e6b6e5e0fe09e478926615895e1`, the commit this work sits
on; the change is the commit that carries this record. Worktree
`.claude/worktrees/upbeat-villani-9c12d4`, branch
`claude/upbeat-villani-9c12d4`. Windows 11 Pro (10.0.26300.9711 x64, AMD64),
Python 3.12.10 (a worktree-local `.venv`, created by `uv sync --frozen`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. The new test file is under `tests/`, so the shard-cost witness
(`tests/test_ci_shard_coverage.py`) will need
`python .github/remeasure_shards.py <run-id>` at the integrating session's
next run, and the new file needs registering in the shard list and in
`tests/evaluation/manifest.py` — that is the integrating session's step, and
this window did neither, as it was told.
**Material:** **none of the pilot's was read.** Every shape below is built in a
scratch workspace under the registered temp area (`E:/labcairn-local/tmp/`),
from a synthetic CSV of the tests' own whose cells read `1` and `2`. No
document text, digest of a document, or key of the pilot appears in this
record. No model request was made.

## The gap, as it was measured at the base revision

The task statement measured it, and the measurement is re-run here at
`9fff78d`:

```
git grep -n "evidence_gate\|unjudged" 9fff78d -- \
    src/labcairn/cli/commands.py src/labcairn/cli/render.py
```

returns **nothing** — exit 1. The CLI's two files never mentioned either
field.

The facts already existed. `ReportRendered` carries `evidence_gate` (the
`GateResult`: `passed`, `findings`, `considered`) and `unjudged_records` (the
records the report names and the gate did not judge)
(`src/labcairn/application/reports.py:294` and `:298`), the API returns both
(`src/labcairn/api/routes.py:781`, `response_model=ReportRendered`), and the
checked-in TypeScript contract carries them
(`web/src/api/generated.ts:672` and `:673`). So an API reader saw the gate's
verdict and its extent, and a reader at the command line saw that a report
was written and nothing else.

**Why that is more than a missing paragraph.** `considered` and
`unjudged_records` are **one statement**: they partition the document's
snapshot (`src/labcairn/application/reports.py:880` and `:890` compute them
from the same document), and a reader who sees only one of them cannot tell
what the other holds. A report that carried two records, one judged and one
named without judging, was indistinguishable at the terminal from a report
that carried none.

**The refusal path was not the gap.** A gate that objects refuses the report
before anything is written, and the refusal is rendered on both surfaces with
its reason and every objection
(`src/labcairn/application/reports.py:886`, `src/labcairn/cli/models.py:128`).
That rendering is unchanged by this work, and a witness says so.

## What changed

- `src/labcairn/cli/render.py` — a new `render_report_gate(model:
  ReportRendered) -> RenderableType`: a `Panel` titled `evidence gate` whose
  rows are the verdict (`passed` / `did not pass`, with the count of records
  considered), the ids the gate judged, the ids the report names without
  judging, and the number of findings. **Ids, counts and outcomes — never the
  records' text.** The `ReportRendered` import is new.
- `src/labcairn/cli/commands.py` — `task report` prints that panel after the
  receipt line, on the human path only; the `--json` path is untouched and
  still emits the model's own serialization. The command's docstring gains a
  paragraph saying the gate's verdict is on the human rendering too.
- `tests/test_cli_report_gate_rendering.py` — **NEW**, seven witnesses.
- `docs/acceptance/LC-P4-PILOT-cli-gate-rendering-2026-11-28.md` — this
  record.

**Not changed, deliberately.** The API's return shape, the gate's behaviour,
the result model, the layer's operation, and the refusal rendering. This
window is the command line's rendering of facts that already existed.

## What the command line now prints

Measured on this tree, through the console script, over a workspace holding
one attested record (the probe that drove it lives outside the repository, in
the registered temp area, and is named in the **Material** paragraph above
rather than here — a record may not name a path the ledger does not hold):

```
$ labcairn task report   -> exit 0
output/01a21e90-a42f-7524-9b5c-1f3e4e80cfcd/report/v1/report.json — revision 1, 6fe7b0a4...
3 link(s) in its chain; the four forms are beside it under the task's output area, and `labcairn artifacts list` names them.
┌──────────────────────── evidence gate ─────────────────────────┐
│ evidence gate  passed, over 1 record(s)                        │
│ judged         01a21e90-c348-72ef-90b9-209226f3351e           │
│ unjudged       (none)                                          │
│ findings       0                                               │
└─────────────────────────────────────────────────────────────────┘
```

and the same command with `--json`:

```json
{
  "evidence_gate": {
    "passed": true,
    "findings": [],
    "considered": ["01a21e90-c348-72ef-90b9-209226f3351e"]
  },
  "unjudged_records": []
}
```

The same id in both, and the same verdict. (The box-drawing characters are
the probe's console, not the rendering's.)

## The witnesses, and what would make each red

All seven are end-to-end through the console script, on the project's shared
rig (`run_cli` from `tests/test_cli_support.py`), so `COLUMNS` is two hundred
and the child's encoding is pinned.

**The property is an equivalence, not a text.** The two renderings are not
the same text — one is a picture, the other is the model's own serialization
— so the witness compares them **as facts**. Every fact the human rendering
carries is read back out of the JSON the *same command* printed; a literal
would go stale the moment the layer changed a shape, and would then fail for
a reason that has nothing to do with the property under test.

**Phrases, not lines.** Rich asks the terminal how wide it is, and a pipe is
not a terminal, so a wrap that falls inside a phrase truncates it. Every
assertion is on a phrase or on an id read out of the whole text, never on a
whole line — so a wider or narrower terminal cannot turn this file red for a
reason that has nothing to do with what it witnesses.

- `test_the_command_line_says_the_gate_ran_and_what_it_judged` — the gate ran,
  the rendering says which records it judged, the id is there, the verdict is
  there, and the human rendering's ids equal the JSON's. Red if the rendering
  stops carrying the verdict or the judged ids.
- `test_the_two_lists_partition_what_the_report_carries` — the judged and
  unjudged lists are disjoint, and the rendering's ids are exactly their
  union. Red if the rendering carries only one half.
- `test_the_command_line_names_the_records_the_report_states_without_judging`
  — a claim that is only *extracted* is carried by the report with its status
  printed beside it, so the gate does not judge it; the rendering still names
  it. Red if the unjudged list stops travelling.
- `test_the_command_line_carries_the_records_the_gate_did_not_judge_and_the_ones_it_did`
  — both halves non-empty at once. The partition is only visible when both
  lists are non-empty: with one empty, a rendering that dropped the other
  entirely would still look right.
- `test_a_record_the_report_does_not_carry_is_neither_judged_nor_unjudged` —
  a planned record is in neither list and does not appear at the terminal.
  Naming it as unjudged would be a false statement about the report's extent.
- `test_the_refusal_is_unchanged_and_names_the_objection` — a gate that objects
  refuses the report; the reason is still `report_evidence_refused`, the
  message still names both records, the human form still goes to stderr with
  the reason, the exit code is still 3, and **no gate panel is drawn** — a
  report the gate refused was never written, so there is nothing to draw.
- `test_the_rendering_carries_ids_and_not_the_records_text` — the id is
  present and the record's unit and number are absent. Red if material starts
  travelling in the rendering.

### One detail the witness had to learn

The task id is a UUID too, and it appears in the rendering for a different
reason — the receipt's path names the task the report belongs to. A first
version of the witness compared *every* UUID in the human output with the
JSON's record ids, and failed on the task id: `1 failed, 6 passed`. The
helper now subtracts the task's id explicitly rather than filtering by shape,
**because the shape is the same for both**. This is recorded because the
failure was in the witness, not in the product, and a reader should know it
was measured rather than assumed.

## Mutation checks

The check that settles it: apply a mutation that only the console script can
reach, and see whether the witness fails. If it stays green, the witness is
not watching the property. All three mutations were applied to this tree,
measured, and reverted; `git diff` holds no mutation text.

| # | The mutation | Measured |
|---|---|---|
| 1 | `render_report_gate`'s `unjudged` row always says `(none)` | **2 failed, 5 passed** — `test_the_command_line_names_the_records_the_report_states_without_judging`, `test_the_command_line_carries_the_records_the_gate_did_not_judge_and_the_ones_it_did` |
| 2 | `render_report_gate`'s `judged` row always says `(none)` | **4 failed, 3 passed** |
| 3 | `task report` never calls `render_report_gate` | **5 failed, 2 passed** |

Each mutation is one that only the console script can reach — the JSON path
was untouched by all three — and each was caught by a witness that reads the
**human** rendering.

## Measurements

- The new file at this tree: **7 passed** in 170.20 s.
- The whole suite at this tree: **25 failed, 6392 passed, 39 skipped**. The
  failures were sorted by measurement, not by assumption — see "What the
  failures were" below, which separates this window's three from the nineteen
  that reproduce at the base revision.
- `ruff check` and `ruff format --check` over the three changed files: clean.
- `mypy --strict` over the three changed files: `Success: no issues found in 3
  source files`.

### What the failures were

**Three were this window's**, and are expected: the new file is in no shard,
has no measured cost, and is in no gate class (the table under "What was not
measured"). The integrating session registers it.

**Three more were this window's, by accident, and were fixed here:**

- `tests/test_external_path_references.py::test_every_path_a_record_names_is_in_the_ledger`
  — the record named the probe's own path, and a record may not name a path
  the ledger does not hold. The probe is now described rather than named.
- `tests/test_status_consistency.py` (two failures) — this window's edit to
  `commands.py` shifted it by **eleven lines**, and five anchors in three
  documents cite lines in it. Each was re-pointed with the checker's own
  word-matching, the way commit `49d3659` did for the same reason. **Both
  witnesses pass now (599 passed).**

**Nineteen are not this window's, and the measurement says so.** The same four
test files were run at the base revision `9fff78d`, in a separate worktree with
its own environment: **19 failures there, 19 the same tests**. The
difference between the two sets is exactly the three above and the three
shard/manifest ones.

**Their cause, measured.** `55942a3` — "Ask every citable record about its
source, and the file before the receipt" — merged into `main` as `1d62b95`
*before* this window's base. It made the report render compare every source
its citations name against the ledger's account, and **refuse before writing**
when the file has moved. The exit demonstration and the outsider path both
ingest `tests/fixtures/analysis/groups.csv` into a **clone** and then expect
the report to be written:

```
the ledger holds 1c74e71d72ce676838e78fc4aeb7cd7303e210268430b5fe143e83173226373f,
and the file now hashes to b2da5b9315d506f16052e97451a06b3fb0cc686f97a76d4f8d567baf8b5c1f9f
```

`sha256sum tests/fixtures/analysis/groups.csv` at this tree is the first of
those — so the **clone's** copy is the one that moved, and the door now
refuses where the demonstration expects a report. That is the drift window's
integration gap and not this one's: the door is behaving as it was written to
behave, and the demonstration has not caught up with it.

**This window does not own those files** (`examples/g4_exit_demo.py` and
`scripts/outsider_path.py`, with the witnesses that drive them,
`tests/test_smoke_path.py` and `tests/test_outsider_path.py`), so this window
did not touch them. It is reported here so the integrating session knows the
nineteen are a known, measured, pre-existing failure and not something this
change introduced.

**And the integrating session has closed them.** The cause above is the drift
window's integration gap, and it was closed there rather than here: both
demonstrations now show the refusal — the reason, the source, the bytes the
ledger holds and the bytes the file has, and **nothing written** — with a
control of its own, and a witness reads each demonstration's output for the
refusal's line and the two hashes it names. Measured at the integrating
session's tree: `tests/test_smoke_path.py` **21 passed** and
`tests/test_outsider_path.py` **17 passed**, and the runner's own run on the
delivery head was green.

### A whole-suite run that hung, and what it cost

The first whole-suite run **hung** and was killed at 29% (`[exited with code
0]` after the kill, 1976 bytes of output, no summary). It was not this
window's change: the run was sitting in
`tests/test_drill_interrupted_writes.py` — a test that spawns a child process
and kills it in a window — with the pytest process consuming **zero CPU over
a measured 15-second interval**, blocked on a child that never signalled.

**The cause was measured, and the first answer this record gave was wrong.**
While the whole suite was running, this window also ran **three other pytest
suites** against the same machine (`test_ci_shard_coverage`,
`test_evaluation_harness`, and the two refusal-enumeration files).
`CLAUDE.md` says it: *"Parallel runs each need their own `TEMP`. `MPLCONFIGDIR`
is pinned under the temp directory, so two runs sharing one temp directory
fight over it. **Whole-suite runs go one at a time.**"* All four runs shared
`E:/labcairn-local/tmp`, and the whole-suite run was the one that hung — so
this record first said the concurrency was the cause.

**It is not the cause.** The hang was measured again, twice, and it
reproduces with nothing else on the machine:

- **At this tree**, `tests/test_drill_rewrite_interrupted.py` alone: attempt 1
  passed, attempt 2 passed, **attempt 3 hung** (killed after 600 s).
- **At the base revision `9fff78d`**, in a separate worktree with its own
  environment: attempt 1 passed, **attempt 2 hung** (killed after 400 s).

**So it is a pre-existing flake in that test file, not this window's change.**
The mechanism is visible in the test's own helper: `_wait_for` reads the
child's stdout with `readline()` **and no timeout**, and raises only if the
child's stream *ends*. A child that dies before printing its marker line
leaves the parent blocked on a read that will never return — the pytest
process then sits at **zero CPU**, which is how the hang was recognised.

**Two failures of reasoning, both corrected here.** The first was to attribute
the hang to this window's concurrent runs because that fitted the project's own
rule; the second was to assume a second hang had the same cause. Both were
attributions without a measurement. **The measurement is that the flake is
pre-existing and reproduces at the base revision** — so the honest reading of
the whole suite is the one that *completed*, and the hung runs are a known
flake rather than a signal about this change.

**It is recorded because the number that came out of a hung run is not a
number.** The killed run reported progress to 29% with no failures in the
first 20% except the two expected shard ones, and a reader skimming the log
would take that for a passing run. It is not a passing run: it is a run that
stopped. **A run that was killed has no result, and "no failures before the
hang" is not a result.** The suite was re-run alone, and it completed.

The lesson for the next window: the whole-suite run gets the machine to
itself, and the witnesses that need measuring run **before** it or **after**
it, never beside it.

**It happened again the same day, from the integrating session — and the
cause is the flake above.** The delivery's reviewer-mode walk — the
outsider's path run in full, which runs the whole suite in its clone — was
started at 05:03, with four pytest runs measured beside it, and **produced no
result**: it was killed at fifty minutes with an empty log and no report.
The kill followed a measurement of one interpreter at zero CPU over a
fifteen-second interval, and that reading is **exactly what this window's
flake produces** — a pytest process blocked on a read that will never
return. The window's own measurement says the flake reproduces with nothing
else on the machine and at the base revision, so **the concurrency is not
what caused this one either**.

**The second attempt failed for a different, arithmetic reason.** It ran
with its own `TEMP`, its own work root, and nothing else measured beside
it, and it reached the walk's own timeout: the clone's whole suite costs
**10120 s** on Windows when it runs as one process, against the **5400 s**
the walk gives that command. That ceiling holds with or without the flake.

### The environment, and why it was rebuilt rather than shared

The project's `.venv` at `E:/LabCairn/.venv` is an **editable install** whose
`.pth` names `E:\LabCairn\src` — the **main checkout**, not this worktree.
Running it from here would have measured the main checkout's code: exactly
the trap `CLAUDE.md` records ("a virtualenv copied with hard links shares
that launcher — and shares the `.pth` that names its editable install's
source tree — so every copy runs the same code"). This window's worktree
therefore has its own `.venv`, created by `uv sync --frozen`, and it was
**verified** before use rather than assumed:

```
cat .venv/Lib/site-packages/_editable_impl_labcairn.pth
E:\LabCairn\.claude\worktrees\upbeat-villani-9c12d4\src

.venv/Scripts/python.exe -c "import labcairn; print(labcairn.__file__)"
E:\LabCairn\.claude\worktrees\upbeat-villani-9c12d4\src\labcairn\__init__.py
```

The `--basetemp` and `TEMP`/`TMP` were outside the repository, on the E drive
(`E:/labcairn-local/tmp/`), and no two pytest runs shared one.

## What was not measured

- **No CI run.** Nothing was pushed and no pull request was opened; the
  seventeen required checks have not read this tree. The local run is the
  evidence until a runner says otherwise.
- **The new test file is in no shard and in no gate class.** Three witnesses
  say so, each naming the file, and each was measured at this tree:

  | Witness | What it says |
  |---|---|
  | `tests/test_ci_shard_coverage.py::test_every_test_file_is_in_exactly_one_shard` | the file is in no shard |
  | `tests/test_ci_shard_coverage.py::test_the_recorded_costs_cover_every_test_file` | `on ubuntu-latest, these test files have no measured cost recorded: ['test_cli_report_gate_rendering.py']` |
  | `tests/test_evaluation_harness.py::test_the_partition_files_every_test_file_exactly_once` | `these test files are in no gate class, so their cases enter no denominator: ['test_cli_report_gate_rendering.py']` |

  Measured: **2 failed, 46 passed** in the shard file, and **1 failed, 83
  passed** in the evaluation harness. **A file in no shard is a test CI never
  runs**, and every other check would stay green while it went — so the
  integrating session must register it in `.github/ci-shards.json` and in
  `tests/evaluation/manifest.py`, and re-measure the shard costs.
- **A correction to what this record first said.** It first claimed that the
  shard-cost witness would fail with *"the shard costs were measured at ... and
  these files have changed since"*. **It does not**, and the measurement says
  so: `test_the_costs_belong_to_the_tree_they_were_measured_on` **passed**. That
  witness has **slack** — a changed file only needs re-measurement if its cost
  could unbalance the partition, and this change does not. So a
  re-measurement is still needed, but for the reasons the two failures above
  give (a file with no measured cost, and a file in no shard), **not** for the
  reason this record first named. The fix is
  `python .github/remeasure_shards.py <run-id>` on a runner's numbers, and it
  is the integrating session's step.
- **Two witnesses that also enumerate the test files pass unchanged.**
  `tests/test_cli_refusal_enumeration.py` and
  `tests/test_cli_workspace_refusals.py` were run over the new file:
  **38 passed**. The new file needs nothing from them.
- **The API was not re-witnessed by this window.** The API's exposure of both
  fields is carried by the contract and by
  `tests/test_report_evidence_gate.py`; this work did not change the API's
  return shape, and the whole-suite run is what says the API's own tests
  still pass.
- **No real model request was made,** and no credential was read, printed or
  written into any file.
