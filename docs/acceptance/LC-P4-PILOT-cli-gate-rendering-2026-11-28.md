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
one attested record (`E:/labcairn-local/tmp/probe_cli_gate.py`, outside the
repository):

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
- The whole suite: **measured separately** — see below.
- `ruff check` and `ruff format --check` over the three changed files: clean.
- `mypy --strict` over the three changed files: `Success: no issues found in 3
  source files`.

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
- **The new test file is in no shard.** `tests/test_cli_report_gate_rendering.py`
  is not registered in `.github/ci-shards.json` and not in
  `tests/evaluation/manifest.py`, as this window was told. **A file in no
  shard is a test CI never runs**, and every other check would stay green
  while it went — so the integrating session must register it and re-measure
  the shard costs.
- **The shard costs were not re-measured.** The shard file records the commit
  its costs were measured at, and this change touches `src/`, so
  `tests/test_ci_shard_coverage.py` will fail until
  `python .github/remeasure_shards.py <run-id>` runs on a runner's numbers.
  Not this window's step.
- **The API was not re-witnessed by this window.** The API's exposure of both
  fields is carried by the contract and by
  `tests/test_report_evidence_gate.py`; this work did not change the API's
  return shape, and the whole-suite run is what says the API's own tests
  still pass.
- **No real model request was made,** and no credential was read, printed or
  written into any file.
