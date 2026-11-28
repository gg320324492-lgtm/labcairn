# The deadline sweep — every wait in the tree, and the bound it now has

**Date:** 2026-11-28.
**Scope:** the repository's tests, scripts, examples and CI tooling.
**Not in scope:** `src/` — the product is not what is being bounded, and
nothing here changes what it does.

## Why this document exists

The drill tests' helper read a killed child's output with `readline()` and
no timeout: it looped until the child's stream *ended*, so a child that
died before printing its marker line left the parent blocked on a read that
would never return. The pytest process then sat at **zero CPU**, which is
how the hang was recognised. It was measured, not guessed: the same file
alone hung on its third attempt at this tree and on its second attempt at
the base revision, with nothing else on the machine.

A window gave that helper a **120-second deadline**, with a witness that
drives a child which never prints its marker and requires the helper to give
up and say what it saw. The two drill files' measured costs fell from
**603.91 s** and **1204.83 s** to **29.03 s** and **24.41 s** — so the hang
was costing the suite a great deal, and not only when it stuck.

**One instance of a class is not the class.** The tree waits on children,
threads, queues and sockets in many places, and a wait with no deadline
turns any hung counterpart into a hung suite — a run that must be killed,
whose "no failures so far" is not a result.

This document says what the sweep found, where it was, what bound each wait
now has, and why that number.

## What was found

The sweep was run over `tests/`, `scripts/`, `examples/`, `.github/` and
`conftest.py` by parsing every `.py` file with `ast` and looking for the
calls that can park the calling thread.

**The method matters, so it is stated.** A first pass over the raw text
found 2,038 "waits", of which 1,269 were `dict.get` and 532 were
`str.join` — neither of which parks. The AST pass that distinguishes them
found **99 unbounded `subprocess.run` calls** across 47 files, plus the
stream reads, the future results and the child-stderr reads described
below.

### The 99 subprocess calls

Every one of them was a `subprocess.run` (98) or `subprocess.check_output`
(1) with no `timeout=`. They fell into three kinds by what the command
*is*, and each kind now goes through a helper whose name says which kind
it is:

| The command | Sites | Helper | Bound |
| --- | --- | --- | --- |
| `git` | 53 | `bounded_git` | 120 s |
| an interpreter or other work | 38 | `bounded_run` | 300 s |
| `mklink`, `taskkill`, `kill` | 13 | `bounded_fast` | 60 s |

**The bound is named at the call site, not repeated as a number.** A reader
of `bounded_git(["git", "log", ...])` can see that it is git, and that git
has its own tighter bound, without reading a constant's value. That is why
there are three helpers rather than one with a `timeout=` argument at every
call site.

### The waits that were not subprocess calls

| The wait | Where | Now |
| --- | --- | --- |
| `Future.result()` with no timeout | `tests/test_api_concurrency.py` (2) | `_result_within(future, 60 s)` |
| `sink.readline()` on a live child's pipe | `tests/test_analysis_render.py` (1) | `read_line_within(sink)` |
| `child.stderr.read()` to end-of-stream | `tests/test_fault_injection_e2e.py` (1) | `read_stream_within(child.stderr)` |
| `child.stderr.read()` to end-of-stream | `tests/test_recovery_crash_matrix.py` (1) | `read_stream_within(child.stderr)` |

**Two of the four were genuine hangs, and one of them was on the failure
path.** `tests/test_recovery_crash_matrix.py`'s `_report_child_failure` is
called from two places: once when the child has *died* (its stderr reaches
its end at once) and once when the child is *alive* and parked inside the
injector's pause, having never reached the injection point at all. The
second call read stderr to its end, which waits for a pause that lasts
minutes — on exactly the path that exists to report a child that is stuck.
That is the same defect as the drill's, in a second place, and it was found
by reading the callers rather than by trusting the call site.

`tests/test_fault_injection_e2e.py`'s `_died` is only reached when
`child.poll() is not None`, so the child is dead and the read returns
immediately. It was bounded anyway: the bound costs nothing and removes the
possibility of a diagnostic that hangs on the path that exists to report a
hung child.

### The two drill files' own waits

`tests/test_drill_interrupted_writes.py` and
`tests/test_drill_rewrite_interrupted.py` were already bounded by the
window that fixed the hang: their `_pump_lines` reads on a thread and the
caller waits on the queue with a deadline, and their `readline()` calls are
inside that pump. **Those two were the instance, not the class**, and this
sweep left their design alone. One `subprocess.run` in each (the
`taskkill` on the failure path) had no bound and now goes through
`bounded_fast`.

## The bounds, and why those numbers

**`COMMAND_TIMEOUT_SECONDS` = 300 s.** A command that is *doing work*: an
interpreter rendering a chart, a build. It is the bound
`tests/test_cli_support.py` already applied to the CLI, so the tree has one
number for "a command that should finish". It is generous because it has to
cover a chart render on a loaded CI runner, and finite because the point of
the module is that it is.

**`GIT_TIMEOUT_SECONDS` = 120 s.** Git is the one command in this tree
that can block on something *outside* the run — a credential helper, a lock
another process holds — and it is called most often, so its bound is the
tighter one.

**`FAST_TIMEOUT_SECONDS` = 60 s.** `mklink`, `taskkill` and `kill` cannot
plausibly take a minute: each either creates one directory entry or ends
one process, and each is on the failure path of a test that has already
gone wrong, so a long wait on one of them is a symptom rather than a cost.

**The stream read's bound is 60 s**, and it is a *diagnostic* bound: the
purpose is to collect a child's error output, not to wait for a child to
finish. A child that has already died has its whole output available
immediately, so a minute is generous and anything longer would be a minute
of a hung run.

**`WRITE_TIMEOUT_SECONDS` = 60 s** on the two futures in
`tests/test_api_concurrency.py`. The requests are real SQLite writes against
a real service on a loaded runner, and the request's own timeout is 8
seconds, so 60 s is three times the request's own bound and generous
against a slow machine.

## What a deadline has to do, or it is half a fix

A wait that gives up has to **say what it saw**. A timeout that raises a
bare `subprocess.TimeoutExpired` sends the reader looking for a timing
problem when the real fault is an import error three lines away.

So `DeadlineExceededError` carries the command that was run, the bound it
was given, the output that had arrived, and whether the process was still
running. `subprocess.run` captures the child's output before raising, so a
command that printed a traceback and then hung still has that traceback, and
the exception carries it. That is the difference between a failure that
names the fault and a failure that names the symptom.

`read_line_within` returns the empty string rather than raising, because its
callers are already reporting a failure when the line does not arrive, and
they report it better than the helper could — they have the child's error
output to attach. The helper's job is to *stop waiting*; the caller's job
is to say what it saw.

## The waits that are deliberately unbounded

These are named rather than quietly bounded, and the reason is given.

**`tests/provider_fakes.py`'s `asyncio.Event().wait()` — a fake provider
that never returns.** This one *is* the subject under test: the fake
hangs so that the adapter's own timeout can be measured against it. Every
caller bounds it — `tests/test_provider_adapter.py`,
`tests/test_drill_provider_faults.py` and
`tests/test_provider_bounded_rehearsal.py` all wrap the call in
`asyncio.wait_for` with a 50 ms budget — so the hang is bounded *by the
thing being measured*. Bounding the fake itself would turn the witness into
a witness of the wrong thing.

**`scripts/checkout_upstreams.py` — the whole file.** The repository's own
plan assigns it to **"nobody — read-only"**
(`docs/plans/LC-P1-01-task-breakdown.md`, the ownership table), and ruff
excludes it for the same reason: it is developer tooling that clones
upstream study repositories, and it carries 22 findings today. Its
`subprocess.check_output` and its `git clone` have no deadline.

**This sweep does not edit it, and the exclusion is watched.** The
witness `tests/test_deadlines.py::test_the_read_only_script_is_the_only_one_excluded`
requires the exclusion list to hold exactly that one file *and* requires
the plan to still mark it read-only — so the exclusion cannot grow, and a
later change to the plan has to be re-read rather than carried forward.
The file's two waits are named here instead: `git clone` of an upstream
study repository, and the `check_output` that reads the clone's output.
Both are network-bound by their nature, which is the case a deadline would
have to be generous about rather than tight.

**`src/`** — the product's own waits are out of scope by the brief, and
this document does not reach them.

## The witnesses

**`tests/test_deadlines.py`** — sixteen tests, in two kinds.

*The deadlines work* (eleven tests). Each helper is driven into the state
that used to hang: a child that prints and then sleeps for ten minutes, a
child that prints nothing at all, a stream that never ends. Each is
required to give up within its bound, and each is required to say what it
saw — the command, the bound, the output that arrived, whether the process
was still running.

*The tree's waits are bounded* (five tests). One reads the tree's own
source and fails if any `subprocess.run` anywhere carries no deadline and
no helper. One requires the tree still to *have* the class of waits the
sweep found (so the sweep cannot pass by the class disappearing). One
requires the helper call count not to fall below the number the sweep
measured. One requires the read-only exclusion list to be exactly the
plan's.

**The measurement that each witness fails without its bound** was made by
mutating each of the five deadline mechanisms in turn and running the
witness file against each mutation:

| The mutation | What the witness did |
| --- | --- |
| `bounded_run` ignores its `timeout` | **hung** — killed at 180 s |
| `bounded_git` given an effectively infinite one | **hung** — killed at 180 s |
| `bounded_fast` given an effectively infinite one | **hung** — killed at 180 s |
| `read_line_within` waits forever | **hung** — killed at 180 s |
| `read_stream_within` waits forever | **hung** — killed at 180 s |

The baseline was **16 passed**, and the tree was **16 passed** again after
the mutations were reverted. **Every mutation was caught, and every one of
them was caught by hanging** — which is the clearest possible demonstration
that the property was held by the deadline and by nothing else. A witness
that fails with an assertion would have shown the deadline was *bypassed*;
a witness that hangs shows the deadline was *gone*, which is the actual
defect.


## What changed in the tree

**`tests/deadline_support.py`** (new) — the helper module. `bounded_run`,
`bounded_git`, `bounded_fast`, `read_line_within`, `read_stream_within`,
`DeadlineExceededError`, and the three bounds. It lives under `tests/`
because that is where the tree's shared test helpers live, and because a
module under `src/` would be shipped in the wheel — and the product is not
what is being bounded here.

**`tests/test_deadlines.py`** (new) — the witnesses.

**46 existing files** — the rewrite. Each unbounded `subprocess.run` became
a helper call, and each file gained the helper's import. The scripts and
examples that need the helper put the repository's `tests/` directory on
`sys.path` first, the way several of them already do for other reasons.

**Three files** gained a bounded wait that was not a subprocess call:
`tests/test_api_concurrency.py` (the two futures), and
`tests/test_analysis_render.py`, `tests/test_fault_injection_e2e.py`,
`tests/test_recovery_crash_matrix.py` (the stream reads).

**Nothing under `src/` changed.** No product behaviour changed. The tree's
own waits are the tree's own.

## What was run, and what it said

Every number below is from a run on this worktree's own virtualenv
(CPython 3.12.10, created with `uv sync --frozen` into the worktree, so its
editable install points at **this worktree's** `src/`), with `TEMP`/`TMP` at
`E:\labcairn-local\tmp` and a `--basetemp` outside the repository.

**The gate:**

| The command | The result |
| --- | --- |
| `ruff check .` | **All checks passed!** |
| `ruff format --check .` | **593 files already formatted** |
| `mypy --strict` | **Success: no issues found in 518 source files** |

**The tests of the changed files**, in the batches they were run in:

| The files | The result |
| --- | --- |
| `test_deadlines`, `test_api_concurrency`, `test_scaffolding`, `test_baseline_document`, `test_record_citations`, `test_release_record`, `test_event_payload_vocabulary`, `test_material_pdf`, `test_paper_fixtures`, `test_parallel_temp_isolation` | **146 passed** |
| `test_status_consistency`, `test_shell_ci`, `test_first_release_record`, `test_chinese_run_classes`, `test_chinese_totals_pin`, `test_ci_shard_coverage`, `test_no_reference_leakage`, `test_workspace_boundaries`, `test_security_paths`, `test_security_listing_canonical` | **897 passed**, 12 skipped, 5 failed (3 are the registration below; 2 were mine and are fixed) |
| `test_cli`, `test_evaluation_harness`, `test_release_workflow`, `test_analysis_dependency`, `test_analysis_report_checks`, `test_analysis_report_model`, `test_analysis_report_render`, `test_application_layer`, `test_feedback_event_stream`, `test_material_ingest`, `test_outsider_path`, `test_pilot_runbook` | **555 passed**, 3 skipped, 1 failed (the registration below) |
| `test_analysis_render`, `test_drill_interrupted_writes`, `test_drill_rewrite_interrupted`, `test_fault_injection_e2e`, `test_recovery_crash_matrix` | **86 passed** |
| `test_evaluation_harness`, `test_quickstart_commands`, `test_readme_accuracy`, `test_repo_root_guard` | **124 passed**, 7 failed (all 7 were mine and are fixed; see below) |
| `test_external_path_references`, `test_pilot_material_registration`, `test_pilot_decisions`, `test_no_reference_leakage`, `test_scaffolding` | **227 passed** (a first run of this batch failed for a reason of my own making — see below — and passes after the fix) |

**The scripts, run standalone** — a script that cannot run is a script whose
deadline protects nothing:

| The script | The result |
| --- | --- |
| `scripts/check_repo_root.py` | prints `OK: repository root is this LabCairn checkout` |
| `scripts/witness_ledger.py HEAD~1 HEAD` | runs, and reports the tree's rename |
| `scripts/release_record.py --help`, `scripts/check_external_paths.py --help`, `scripts/cjk_ceilings.py --help`, `scripts/pilot_material_registration.py --help` | all run |
| `.github/remeasure_shards.py --help` | runs |
| `examples/g1_exit_demo.py` | **36 checks passed** |
| `examples/g2_exit_demo.py` | **14 checks passed** |

### Three failures that were mine, and are fixed

**Two documents cited a line number that moved.** The rewrite changed the
line count of `tests/test_recovery_crash_matrix.py` and
`tests/test_no_reference_leakage.py` by one line each, and
`docs/THREAT-MODEL.md` and `docs/REVIEW-DOSSIER.md` cite lines in those
files by number. The tree's own witness caught it —
`test_every_declared_anchor_carries_the_line_and_the_words_it_cites` — and
the two citations were moved to the lines the text is now on (**210 → 211**
and **508 → 509**).

**Six tests copied a script into a synthetic checkout.** The guard's own
tests copy `scripts/check_repo_root.py` into a checkout they build, and the
guard now waits on git through `tests/deadline_support.py` — which that
checkout did not have, so the guard could not run at all. The same was true
of the shard tool's fixture. **The helper now travels with the tools** in
both fixtures, and the guard's AST witness was updated to recognise the
helper's call as a git invocation — a witness that only recognised the old
spelling would have reported that the guard invokes no git at all, which is
a *pass* by accident on a tree where the guard had stopped checking
anything.

### One failure that was mine, and was not the tree's

`tests/test_external_path_references.py` failed with *"E:/labcairn-local/tmp/mpl
is on disk, and the ledger says it is not there"*. **That was caused by my
own `MPLCONFIGDIR`**, which I had pointed at `E:/labcairn-local/tmp/mpl` —
a directory the tree's external-path ledger requires to be **absent**. The
directory was removed and the test passes (**6 passed**). Nothing in the
tree was changed to accommodate it.

### One failure that pre-existed this sweep

`tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`
fails because the **drill fix** changed two test files after the shard costs
were measured. This was measured, not assumed: the sweep's changes were
stashed and the file was run on the tree as it stood — **1 failed, 47
passed**, the same failure. So it is the drill fix's, and the same
re-measurement that registers this sweep's new file fixes it.

## What was not done, and why

- **`scripts/checkout_upstreams.py`** — read-only by the plan's ownership
  table. Named above, watched by a witness.
- **The provider fake's deliberate hang** — the subject under test, and
  bounded by the adapter timeout it exists to measure.
- **The whole suite** — not run. The brief says to run the tests that
  changed, and the whole-suite run gets the machine to itself. The changed
  files' tests were run; the numbers are above.
- **The shard costs** — see the next section, which carries the measurement
  rather than an assertion about it.
- **`src/`** — the product's own waits are out of scope by the brief, and
  this sweep does not reach them.

## The shard costs: one failure pre-existed this sweep, and two are this sweep's to hand over

`tests/test_ci_shard_coverage.py` is the tree's witness on the CI
partition, and it fails on this branch. **The three failures are not the
same kind of thing**, and the difference was measured rather than assumed.

**One failure pre-existed this sweep.** `test_the_costs_belong_to_the_tree_they_were_measured_on`
fails because `tests/test_drill_rewrite_interrupted.py` and
`tests/test_drill_interrupted_writes.py` changed after the costs were
measured at `b56f9994c1429fafcd37072c0ed8599c8aba474d` — and those files
were changed by the **drill fix**, not by this sweep.

**That was measured, not reasoned.** The sweep's changes were stashed
(`git stash push -u`) and `tests/test_ci_shard_coverage.py` was run on the
tree as it stood: **1 failed, 47 passed**, and the failure was the same
one. So the pre-existing failure is the drill fix's, and this sweep did
not cause it. The same witness's message names the reason itself: *"the
partition is outside the limit by structure (tests/test_drill_rewrite_interrupted.py
alone costs 1209s of a 1209s shard set)"* — the drill fix took that file
from 1204.83 s to 24.41 s, and the shard table still carries the old cost.

**Two failures are this sweep's own, and they are the registration the
brief reserved.** `tests/test_deadlines.py` is in no shard and has no
recorded cost:

```
AssertionError: on ubuntu-latest, these test files are in no shard, so CI
never runs them: ['tests/test_deadlines.py']
```

**The integrating session owns the registration.** The brief says so
directly: it registers new test files in `tests/evaluation/manifest.py` and
in `.github/ci-shards.json`, because other windows in this batch may add
files of their own. **This sweep does not touch either file**, and the
cost entry cannot be written here anyway: `python .github/make_ci_shards.py`
*refuses to guess a cost it has not measured*, and the costs come from a
runner's `--durations=0` log. The re-measurement is
`python .github/remeasure_shards.py <run-id>`, and it has to come from a
runner — a development machine gives a different answer, not only a
different total but a different *order*, which is why the partition is one
per platform.

**What the integrating session has to do, then:**

1. Register `tests/test_deadlines.py` in `tests/evaluation/manifest.py` —
   the class and the clause are in the report below.
2. Register it in `.github/ci-shards.json` with a cost measured on a
   runner, and re-measure the shard costs, because the drill fix changed
   two files whose recorded costs are now stale. **Both are one
   re-measurement**: `python .github/remeasure_shards.py <run-id>` reads
   the per-file seconds out of a CI run's log and rebuilds the partition.
3. Note that the **pre-existing** failure is fixed by that same
   re-measurement, so it is not a second thing to chase.

