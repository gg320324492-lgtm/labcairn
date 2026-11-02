# LC-P1-13 — the evaluation harness in CI

**Status:** proposal plus one safe implementation, 2026-11-03. The
implementation is a scheduled job that is **not a required check**; what
remains for the owner is stated in §7.

## 1. The debt

`docs/plans/PHASE_2-work-orders.md` §5 carries it:

> **Nothing in CI runs the evaluation harness** — `python.yml` runs plain
> sharded pytest. The blocker table and the metrics exist only when somebody
> runs them locally. **Wiring them in is a gate decision and it is the
> owner's** — after the Phase 1 ruling the run exits 2 because the fifth gate
> class cannot run offline, so a naive gate would be permanently red.

The harness is `python -m tests.evaluation`. Its exit codes are not a
conventional 0/1 pair, and that is the whole difficulty:

| exit | meaning |
| --- | --- |
| 0 | every **selected** class ran, every case passed, and every Phase 1 blocker held |
| 1 | a case failed, errored or was skipped, or a blocker did not hold |
| 2 | a selected class could not be run |

The default run selects all six classes — the protocol's five plus the
repository's own — and the fifth (`real_model_smoke`) is not runnable
offline. The default run therefore reports it `NOT RUN` and exits 2. That is
the harness doing its job, not a defect: a run that exited 0 there would be
reporting a pass for a class it never ran.

## 2. What the harness actually says — three measurements

All three were run on this machine on 2026-11-03 from the worktree
`E:\LabCairn\.claude\worktrees\quizzical-lewin-094bf1`, at revision
`e13b967db605af173ca698428e4dd949042cd2ce`, with `TEMP`/`TMP`/`TMPDIR`
pointed at a fresh directory under `E:\labcairn-local\tmp`. The report goes
outside the repository.

### 2.1 The default run (all six classes)

Command: `python -m tests.evaluation --out <temp>/report`.

- **Exit code: 2.**
- Duration: **2456.8 s** (40 min 57 s).
- Classes: Unit 1789/1789 passed; Integration 1608/1609 (1 skipped);
  Negative 378/381 (3 skipped); E2E 136/140 (4 failed); Real-model smoke
  **NOT RUN** (no credential); Repository gates 738/739 (1 failed).
- Blockers: **all six HELD** — including `no-skipped-required-tests`,
  because a declared skip's ruling is not this run's to make.

The five failures are all clone-shaped tests in a worktree, not product
defects:

- four in `tests/test_outsider_path.py` — the outsider walk builds a clone
  and runs the README inside it; with `PYTHONPATH` pointing at this
  worktree's `src`, the clone's own package was shadowed;
- one in `tests/test_no_reference_leakage.py::test_wheel_installs_clean_and_imports`
  — the editable install of the working tree shadowed the wheel, which is
  the same failure the project has recorded before.

### 2.2 The control run (E2E + repository, without `PYTHONPATH`)

Command: `python -m tests.evaluation --classes e2e,repository`.

- **Exit code: 1.**
- E2E 134/140 (6 failed); Repository gates 729/739 (2 failed, 8 errored).
- All six blockers **NOT_EVALUATED**, because their witnesses include
  files in classes this run did not select.

The failures are environmental, and they name the two forces this machine
adds:

- the outsider walk's clone cannot `uv sync`: `Failed to build labcairn`
  (the build backend cannot be fetched — PyPI is unreachable here);
- eight `uv build` errors in `test_no_reference_leakage.py`: `hatchling`
  cannot be resolved from PyPI;
- `test_core_resolves_inside_the_source_tree` resolves the **main
  checkout**, not this worktree — the editable install's `.pth` points at
  the main checkout while the test runs in a worktree.

PyPI reachability was measured directly: `curl https://pypi.org/simple/hatchling/`
exits **35** (TLS connect failure) and reports HTTP **000**.

### 2.3 The partial-selection run (`--classes unit`)

Command: `python -m tests.evaluation --classes unit`.

- Unit: **1789/1789 passed**.
- **Exit code: 1**, not 0.
- All six blockers: **NOT_EVALUATED**.

This is the measurement that decides the shape of any CI job. A blocker is
held only when **every** one of its witnesses was collected and passed; a
witness outside the selected classes cannot be evaluated, and a blocker
that could not be evaluated has not held. The witnesses are spread across
the classes:

| blocker | classes its witnesses live in |
| --- | --- |
| `clean-environment-readme` | integration, e2e, repository |
| `no-unauthorized-write-or-disclosure` | negative, unit |
| `no-fake-citation-or-unsupported-number` | negative |
| `no-repeated-side-effect-after-crash` | negative, integration, e2e |
| `no-verified-claim-from-rendering-checks` | integration, unit, negative |
| `no-skipped-required-tests` | repository, unit, negative |

**So the smallest selection that can exit 0 is all five offline classes** —
`unit,integration,negative,e2e,repository`. Selecting fewer can never be
green, however many tests pass. This is a property of the harness, and it
is the reason "just run the fast classes" is not an option.

### 2.4 What a clean runner would say

None of the 2.1/2.2 failures is a product defect: they are the worktree's
editable install and this machine's unreachable PyPI. A CI runner has a
clean checkout and a network, which is exactly the environment the clone
tests are designed for. **This document does not claim the offline job is
green on a runner — that has not been measured, because no run was pushed
(on the owner's standing rule).** The first scheduled run after this lands
on `main` is the measurement.

## 3. What a CI job costs

The per-file costs in `.github/ci-shards.json` are runner measurements,
anchored at `49e81f26c2f0b5efb77e312423d179dde5fe4290`. Summed over the
five offline classes:

| platform | unit | integration | negative | e2e | repository | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ubuntu-latest | 165.0 s | 485.6 s | 156.4 s | 610.0 s | 33.0 s | **1450.0 s ≈ 24.2 min** |
| windows-latest | 388.0 s | 2455.1 s | 283.2 s | 1121.1 s | 59.1 s | **4306.5 s ≈ 71.8 min** |

The current pull-request wall clock is set by the slowest shard: about 844 s
on Windows (14 min); the Ubuntu floor is `test_cli.py` at 325.8 s. A job
that runs all five offline classes **on Ubuntu** would therefore become the
new bottleneck at about 24 minutes — a 10-minute increase on every pull
request, and another full run of the suite on top of the ten shard jobs. On
Windows it would be about 72 minutes, which is not a candidate.

That cost is the reason for the trigger choices below: the job is valuable
as a report, but it is not worth adding ten minutes to every pull request
while the shard jobs already run the same files.

## 4. The options

### A. An informational full run on every pull request

- **Semantics.** Select all six classes. The run reports the fifth class
  `NOT RUN` and exits 2; the job is marked `continue-on-error` (or left
  non-required) so the red is visible but blocks nothing. The report is the
  product.
- **What CI looks like.** One more job per pull request, about 24 minutes on
  Ubuntu, carrying a permanent red X whose cause is a protocol gap the pull
  request did not create.
- **What goes red.** The job, always, by design. A permanent red that is
  expected is a red nobody reads — the exact shape the project's reviews
  keep finding ("a green row that measured nothing" has a red twin).
- **Cost.** +10 minutes of pull-request wall clock and one extra suite run
  per pull request.
- **Owner's decision.** Accept a permanently red non-required check, or
  accept `continue-on-error` hiding it.

### B. The offline classes on every pull request

- **Semantics.** `--classes unit,integration,negative,e2e,repository`; the
  fifth class is `NOT SELECTED` and named in the report. Exit 0/1 then means
  what it says, and all six blockers are evaluable.
- **What CI looks like.** One more job per pull request, about 24 minutes on
  Ubuntu; the report says `NOT SELECTED` for the fifth class.
- **What goes red.** Only real test failures (exit 1). It can be green.
- **Cost.** Same +10 minutes and the same duplicate suite run as A.
- **Owner's decision.** Whether a second full run of the suite per pull
  request is worth a report the shard jobs cannot produce, and whether the
  job should be a required check. **If it is required, "green" would mean
  "the four offline protocol classes held", not "the protocol was
  satisfied"** — the fifth class is still only discharged by
  `provider-smoke.yml`.

### C. A scheduled full run

- **Semantics.** Select all six classes on a schedule; the run exits 2 every
  time because the fifth class cannot run offline. Report uploaded, job red
  or `continue-on-error`.
- **What CI looks like.** No pull-request impact; one run per period.
- **What goes red.** The job, every time, for the same reason as A.
- **Cost.** About 24 minutes of runner time per period, no pull-request
  wall clock.
- **Owner's decision.** Cadence, and whether a report that is always red is
  worth producing.

### D. A scheduled run of the five offline classes — **implemented**

- **Semantics.** `--classes unit,integration,negative,e2e,repository`, on a
  schedule only. Exit 0/1 is meaningful; the fifth class is `NOT
  SELECTED` and named; the report points at `provider-smoke.yml` as the
  owner's ruled shape for that class (G5 acceptance, 2026-10-28). The job
  is **not a required check** and cannot be one: a scheduled job does not
  report on a pull request, so branch protection never sees it.
- **What CI looks like.** `lint` and the ten shard jobs keep their
  pull-request behaviour unchanged; on the schedule event they are skipped
  and only `evaluation` runs. The report is uploaded as an artifact and its
  markdown is printed in the job log, so a failure leaves the blocker table
  and the failure list in the log.
- **What goes red.** Only real failures in the offline classes (exit 1), or
  a harness that cannot run a selected class (exit 2). It can be green, and
  green would mean the four offline protocol classes and the repository
  gates held.
- **Cost.** About 24 minutes of Ubuntu runner time per period; **zero
  pull-request wall clock**.
- **What it gives up.** Nothing is checked before a merge; a regression is
  found on the next schedule, not on the pull request. The report is not a
  merge gate.
- **Owner's decision.** Whether a periodic report is worth the runner time,
  and whether the trigger should instead be `push` on `main` (per merge,
  still no pull-request wall clock) or a pull-request job (option B).

**Why D rather than C.** C's red is guaranteed and therefore uninformative;
D's red is a measurement. **Why D rather than A/B.** A and B spend ten
minutes of pull-request wall clock on a second run of the same files; the
owner's standing rule is that CI is not spent unless necessary, and a
report that is already produced periodically is the cheaper way to keep the
blocker table from existing only on one developer's machine.

## 5. What was implemented

`.github/workflows/python.yml`:

- a `schedule` trigger — `17 3 * * 1` (Mondays, 03:17 UTC; the off-minute
  and the weekly cadence are deliberate);
- `lint` and `python-quality` carry `if: ${{ github.event_name != 'schedule' }}`,
  so the schedule run spends one job, not thirteen;
- a new job `evaluation`, `name: evaluation`, `runs-on: ubuntu-latest`, no
  matrix, gated on `github.event_name == 'schedule'`. It checks out, sets up
  the pinned interpreter and uv, runs `uv sync --frozen`, then:

  ```
  uv run python -m tests.evaluation \
    --classes unit,integration,negative,e2e,repository \
    --out "$RUNNER_TEMP/evaluation-report"
  ```

  followed by two steps that run `if: always()`: print the markdown report
  to the log, and upload `${{ runner.temp }}/evaluation-report` as the
  `evaluation-report` artifact.

**Why the artifact path is narrow.** `tests/test_no_reference_leakage.py`
watches every `upload-artifact` path for reference-path families; the path
here is a single directory under the runner's temp, never the working tree.
The old comment at the end of `python.yml` saying this workflow uploads no
artifact has been replaced, because it is no longer true.

**What is deliberately not done.**

- The job is **not** added to branch protection. That is the owner's step in
  GitHub, and it is also impossible for a schedule-only job to satisfy a
  pull-request required check.
- No `continue-on-error` is used. If the harness exits 1, the job is red and
  the log carries the report; hiding it would be the "green row that
  measured nothing" shape in reverse.
- The fifth class is not selected. It is discharged, by the owner's ruling,
  by `provider-smoke.yml`; the evaluation report says `NOT SELECTED` and
  does not pretend otherwise.

**When it starts.** GitHub fires `schedule` only from the default branch, so
the job first runs after this workflow reaches `main`. A branch run of a
scheduled workflow silently never happens; the first run on `main` is the
first measurement.

## 6. The witnesses

`tests/test_ci_shard_coverage.py` gains
`test_the_evaluation_job_runs_the_offline_classes_on_a_schedule`. It
asserts:

- the workflow has a `schedule` trigger;
- a job named `evaluation` exists, has no matrix, runs on `ubuntu-latest`,
  and is gated on `github.event_name == 'schedule'`;
- the step that runs `python -m tests.evaluation` names exactly the
  offline classes — computed from
  `tests.evaluation.manifest.OFFLINE_CLASSES`, not a second literal — and
  does **not** name `real_model_smoke`;
- the report directory in `--out` is the directory the artifact step
  uploads;
- the artifact path is the runner's temp directory, not the checkout;
- `lint` and `python-quality` are skipped on the schedule event;
- every job's check name is distinct.

The witness is mutation-checked; the mutations and their results are
recorded in §8.

## 7. What the owner decides

1. **The trigger.** Keep the weekly schedule (implemented), move it to
   `push` on `main` so every merge gets a report, or accept option B and
   spend about ten minutes of pull-request wall clock. Only B can ever be a
   required check.
2. **The cadence**, if the schedule stays.
3. **Whether the job's artifact and log are enough**, or the report should
   be published somewhere a human reads it.
4. **Whether the runner cost is acceptable** — about 24 minutes of Ubuntu
   runner time per period, against zero pull-request wall clock.
5. Nothing about the fifth class: that was ruled on 2026-10-28 —
   `provider-smoke.yml` is its shape, and this job reports it as
   `NOT SELECTED`.

## 8. Mutations

Each mutation was applied to the workflow or the witness, the witness was
run, and the file was restored from a copy (not `git checkout`, which has
lost uncommitted work in this repository before).

| mutation | witness result |
| --- | --- |
| `evaluation` renamed | red — no job named `evaluation` |
| `--classes` gains `real_model_smoke` | red — the command names a class that is not offline |
| `schedule` trigger removed | red — no schedule trigger |
| `lint`'s schedule guard removed | red — a schedule would spend the shard jobs |
| artifact path changed to the checkout | red — the path is not the runner temp |
