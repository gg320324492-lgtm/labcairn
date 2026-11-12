# The CI, and what each job is for

This record belongs to `.github/workflows/python.yml`,
`.github/workflows/shell.yml` and `.github/ci-shards.json`. It says what runs,
why the jobs are arranged this way, and — where a number is a runner
measurement — which run it came from.

## The shape of a run

Four kinds of job:

| job | workflow | runner | what it runs |
| --- | --- | --- | --- |
| `lint` | `python.yml` | `ubuntu-latest`, one runner, no matrix | `ruff check .`, `ruff format --check .`, `mypy --strict` |
| `python-quality (${{ matrix.os }}, shard N)` | `python.yml` | 2 platforms × 5 shards = 10 jobs | `pytest` on that shard's files only |
| `evaluation` | `python.yml` | `ubuntu-latest`, one runner, no matrix, **schedule event only** | `python -m tests.evaluation --classes unit,integration,negative,e2e,repository` |
| `shell-test (${{ matrix.os }})` | `shell.yml` | 2 platforms = 2 jobs | `node --test 'test/*.test.mjs'` in `shell/` |

The shard partition and its measured per-file costs live in
`.github/ci-shards.json`; `tests/test_ci_shard_coverage.py` watches that
every test file is in exactly one shard on every platform and that the shard
count matches the workflow's matrix. **That file also watches the names branch
protection identifies — across every workflow file, and on the names GitHub
actually renders**, one per matrix leg, not on the name templates as written.
The distinction is what `release-dependency-licences (matrix.os)` needed (see
2026-11-11 below): as a template it looked distinct from everything.

## 2026-11-11 — the required-check set, measured

Branch protection lives outside the repository, so the repository can only keep a
**dated reading** of it — and a dated reading is what lets a later one be compared
with it. Measured 2026-11-11 at `6b3211ae631c7c9548ca160615f88daa6da7d5dd`:

```
gh api repos/gg320324492-lgtm/labcairn/branches/main/protection \
  --jq '.required_status_checks.contexts | length'   # -> 15
```

The 15 contexts, printed one per line by the same call with
`--jq '.required_status_checks.contexts[]'`:

<!-- required-status-checks:begin — measured 2026-11-11 at 6b3211ae631c7c9548ca160615f88daa6da7d5dd -->
- `web-quality`
- `reference-exclusion`
- `secret-scan`
- `lockfile-consistency`
- `python-quality (ubuntu-latest, shard 0)`
- `python-quality (ubuntu-latest, shard 1)`
- `python-quality (ubuntu-latest, shard 2)`
- `python-quality (ubuntu-latest, shard 3)`
- `python-quality (ubuntu-latest, shard 4)`
- `python-quality (windows-latest, shard 0)`
- `python-quality (windows-latest, shard 1)`
- `python-quality (windows-latest, shard 2)`
- `python-quality (windows-latest, shard 3)`
- `python-quality (windows-latest, shard 4)`
- `lint`
<!-- required-status-checks:end -->

**`lint` is in that list.** The 2026-11-02 record that introduced the job said it
"reports without blocking" until the owner added it; the owner has since added it,
and the sentences in `CLAUDE.md` and `docs/handoff/CURRENT.md` that said otherwise
are corrected to this measurement. **When it was added is not recorded anywhere in
this repository** — only that the 2026-11-02 sentence was true when written and is
not true now. **What the workflows cannot do is make it so**: no file here can add
or remove a required check.

**The rest of the setting — same call, same date, exit 0:**

```
gh api repos/gg320324492-lgtm/labcairn/branches/main/protection \
  --jq '{reviews: .required_pull_request_reviews,
         strict: .required_status_checks.strict,
         admins: .enforce_admins}'
# -> {"admins":{"enabled":true,…},"reviews":null,"strict":true}
```

- **`reviews: null`** — GitHub requires no review of a pull request into `main`.
  The review this project treats as the gate is the one the repository arranges,
  not one the setting enforces. **The owner decided on 2026-11-11 that no
  required review is added**, so this stays `null`; nothing here changes it.
- **`strict: true`** — the required checks must be re-passed on the branch's tip
  before a merge, so a merge cannot carry a green set measured on an older commit.
- **`admins: {"enabled": true}`** (`enforce_admins`) — the fifteen checks bind
  administrators as well.

**Seven names the tree offers are not in the list:** `evaluation` and
`real-model smoke` (schedule-only, so branch protection cannot see them at all),
`release-contents` and both `release-dependency-licences (…)` legs (tag-triggered;
they run on pull requests but are not required), and both
`shell-test (…)` legs. `tests/test_ci_shard_coverage.py` watches the direction
that can actually break a merge — **every name in the list must be a name some job
in `.github/workflows/` reports**, because a required check naming a name no job
reports is a check GitHub waits for forever. It does not watch the seven, and it
must not: which of them become required is the owner's decision, recorded below.

**The owner's decision, taken 2026-11-11.** `shell-test
(windows-latest)` and `shell-test (ubuntu-latest)` run on every pull request
and **are not required**, and the owner decided on 2026-11-11 that they stay
that way. Making them required is the owner's call and this repository only
offers the two names; the decision was to keep the measured set as it stands.
The same day the owner decided that **no required review is added**: the
review this project treats as the gate stays the one the repository arranges
(two layers, an implementer and a reader that did not write the code), not one
GitHub enforces.

## 2026-11-11 — the shell's Node witnesses get a job, and two name defects close

**What changed.** Three things, one change-set.

1. **`shell.yml` runs the shell's tests.** One job, `shell-test (${{ matrix.os }})`,
   on `windows-latest` and `ubuntu-latest`, `fail-fast: false`, on `push` to `main`
   and unfiltered `pull_request`. It installs **no** pnpm package and downloads **no**
   Electron binary: the twelve files under `shell/test/` import only `node:*` built-ins
   plus paths into `shell/` or `.github/`, and the two lockfile-facing witnesses read
   `pnpm-lock.yaml` and `NOTICE` as text rather than resolving an installed package.
   What the job does install is the
   Python CLI (`uv sync --frozen`), because `drain-witness.test.mjs` — the one
   integration file — spawns the `labcairn` console script, and
   `shell/scripts/lib/shell-paths.mjs` derives it from the checkout's own `.venv`.
   `LABCAIRN_SHELL_TEST_TMP: ${{ runner.temp }}/shell-test-tmp` is load-bearing: the
   file's scratch default is `E:\labcairn-local\shell-test-tmp`, and a GitHub runner has
   no E: volume.
2. **`release-dependency-licences` is renamed to `release-dependency-licences (${{ matrix.os }})`.**
   The name held the literal text `matrix.os` inside parentheses, not an expression, so
   the job's two platform legs reported **one** check name — the shape the job's own
   comment at `release.yml:398-400` forbids. A required check of that name was satisfied
   by whichever platform reported first.
3. **The job-name witness now reads every workflow, and renders names.** It read
   `python.yml` alone and compared name *templates*, which is why (2) survived every
   earlier check. It enumerates `.github/workflows/*.y*ml` and compares the names GitHub
   renders, one per matrix leg. The rendering lives in `tests/workflow_job_names.py`,
   shared with `tests/test_shell_ci.py`.

**Why the job is needed at all.** `pyproject.toml`'s `norecursedirs` names `shell` —
"Electron tree; its Node witnesses are not pytest files" — so no shard, no gate class and
no witness-ledger entry sees the Node cases. Before this change, deleting
`shell/test/window-security.test.mjs` left every pytest test green.

**The witness.** `tests/test_shell_ci.py`: **17 test functions**, counted
2026-11-11 with `grep -c "^def test_" tests/test_shell_ci.py`. The 14 this entry
carried was the count at `6b3211ae631c7c9548ca160615f88daa6da7d5dd`; the CI
declaration fixes below add three — a name with no matrix, the
`include`/`exclude` refusal, and the tree-side half of that scope. Its cases: every
`shell/test/*.test.mjs` is a file the CI command actually runs; the step carries
`working-directory: shell`, the runner temp env and `uv sync --frozen` — and must
**not** run `pnpm install`; the name carries `matrix.os`; both legs exist with
`fail-fast: false`; the name is unique across every workflow; each recorded file
still declares at least its Node cases, anchored at the revision the floors name
(5/3/5/8/5/6/7/8/9/7/7/4 = 74 across twelve files); and no shell test file exists without a
recorded floor. Several witnesses feed the file's own readers synthetic trees — a
command naming three of twelve files, a glob that does not cross a directory, a matrix
axis the matrix does not declare, and the literal `(matrix.os)` shape — so "the check
exists" is not offered as "the check can fail".

**Mutation checks run, all four reddened and then restored:** reverting the release name
reddened the shard witness; deleting `window-security.test.mjs` from a copy reddened the
floors; a matrix expression naming an undeclared axis is refused rather than compared; and
the coverage reader reports a three-of-twelve command as running three. Deleting a shell file
leaves the coverage check green **by design** — the glob still covers what remains — which
is why the floors and the recorded-floor check exist.

**Not yet runner-measured, intentionally exempt.** The job's duration is unrecorded, as
`lint`'s once was; the first runner run is the measurement. A development-machine run of
the same command shape measured 74/74 on Node v24.16.0. Neither is a recorded cost; the
`0.0` shard-cost placeholders for `test_shell_ci.py` are carried under the balance
witness's slack rule until the first runner run re-measures them. No CI run is owed for
this batch.

**The owner's step, taken 2026-11-11.** `shell-test (windows-latest)` and
`shell-test (ubuntu-latest)` do **not** join branch protection — the owner
decided on 2026-11-11 to keep the measured set as it stands, and the same day
decided that no required review is added. A workflow file cannot make a check
required. `tests/test_no_reference_leakage.py::test_no_workflow_filters_pull_request_at_all` is what
keeps `shell.yml`'s `pull_request` trigger unfiltered if it becomes required.

## 2026-11-03 — the evaluation harness on a schedule

**What changed.** `python.yml` gained a `schedule` trigger and an
`evaluation` job. On the schedule event `lint` and `python-quality` are
skipped, so the run spends one job, not the **eleven** a pull-request event
spends. **Eleven, counted from the workflow:** three job templates,
`python-quality`'s matrix expanding to 2 platforms × 5 shards = 10, and `lint`
as the eleventh; `evaluation` is gated to the schedule and is not among them.
**The workflow names twelve jobs in total** — the eleven above plus `evaluation`
— which is what `tests/test_ci_shard_coverage.py`'s name-uniqueness check sees
(`workflow_job_names.rendered_job_names` returns twelve for this file), and
**eleven** is what a single pull-request run spends. What this sentence printed
until 2026-11-12 was **thirteen**, and thirteen was not the count at any
revision: the matrix has been `[0, 1, 2, 3, 4]` since `5a4d8e9` (2026-10-25),
the six-shard matrix `d8f5788` (2026-10-24) tried reported **12** shard jobs
with no `lint` job (`lint` was split out on 2026-11-02, a day before this
section was written), and with five shards and `lint` the count is **11** — at
`6cdd89d` (2026-11-03, the commit that wrote this section) as it is today.
`python.yml`'s `lint` comment and `docs/plans/LC-P1-13-evaluation-ci.md` §5
carry the same sentence and are corrected with it.

**Why not on pull requests.** The harness runs the same test files the ten
shard jobs already run, and its measured cost on an Ubuntu runner is
1622.3 s (about 27 minutes) over the five offline classes — the per-file
costs in `.github/ci-shards.json`, anchored at
`46e2c21918286a723f9d07d5409d0e52e7551a85`. On a pull request it would add
about twelve minutes to the wall clock and become the new bottleneck. A
schedule produces the report without touching that clock.

**Why exactly five classes.** A Phase 1 blocker is held only when every one
of its witnesses was collected and passed, and the witnesses span all five
offline classes. `--classes unit` passed 1789/1789 and still exited 1,
because five of the six blockers became `NOT_EVALUATED`. That was measured
on 2026-11-03, and it is why the job does not shorten the list. The fifth
protocol class, `real_model_smoke`, is `NOT SELECTED` in the report; the
owner's 2026-10-28 ruling gives it `provider-smoke.yml`.

**Not a required check, and not `continue-on-error`.** The job is not in
branch protection, and a schedule-only job cannot satisfy a pull-request
required check. If the harness exits 1 the job is red and the report is in
the log; hiding that would be the "green row that measured nothing" shape in
reverse.

**The witness.** `tests/test_ci_shard_coverage.py` gains
`test_the_evaluation_job_runs_the_offline_classes_on_a_schedule`. It
computes the class list from `tests.evaluation.manifest.OFFLINE_CLASSES`,
asserts the fifth class is not named, watches the trigger and the two
guards, and checks the artifact path is the runner's temp. Five mutations
were applied and all five were caught (job renamed; `real_model_smoke`
added; schedule removed; lint guard removed; artifact path moved over the
checkout).

**Not measured on a runner.** No run was pushed. GitHub fires a schedule
only from the default branch, so the job first runs after this workflow
reaches `main`; that run is the measurement. The local harness runs are in
`docs/plans/LC-P1-13-evaluation-ci.md` §2.

## 2026-11-02 — lint split out of the shard jobs

**What changed.** The three static checks moved out of the ten `python-quality`
jobs and into one `lint` job. The shard jobs now run `pytest` only.

**Why.** The same three commands ran in every shard job, so one lint error
turned all ten checks red, and the work was paid for ten times. A separate
`lint` job is one check to read, one place to fix, and one run of each
command.

**The witness.** `tests/test_ci_shard_coverage.py` now also asserts that
`lint` exists, is named exactly `lint`, has no matrix, runs all three
commands, that no shard job runs any of them, and that no two jobs share a
check name. It cannot assert that GitHub *requires* `lint` — that is not in
the repository.

**Wall-clock expectation, and what is not verified.** The split does not
shorten the wait. The shard jobs' wall clock is set by the slowest shard, and
`lint` finishes well before them (its work is seconds-to-a-minute against a
shard's minutes). What it removes is ten duplicate lint runs and nine red
checks to read. **The numbers are not measured on a runner yet**: this change
has only been checked locally (YAML parse, the witness, and the three
commands run from this checkout). The first pull request after it lands is
the measurement.

**Branch protection is the owner's step.** `lint` is a check the workflow
reports; it is **not a required status check**. Only the owner can add it in
GitHub's branch-protection settings. Until that is done, a failing `lint` is
visible but does not block a merge. No file in this repository can make it
required.

> **Dated snapshot — true when written, superseded since.** The two sentences
> above are the state as of 2026-11-02, the date of this section, and they are
> left as written. `lint` **is** a required status check now: it is one of the
> fifteen required contexts read from GitHub on 2026-11-11 at
> `6b3211ae631c7c9548ca160615f88daa6da7d5dd` and listed in "The required-check
> set, measured" above, and re-read live on 2026-11-12 at
> `0655bb8b22506dd851e1eff6f29a455465535a1a` (`gh api
> repos/gg320324492-lgtm/labcairn/branches/main/protection --jq
> '.required_status_checks.contexts | length'` → 15, `lint` among them). When
> the owner added it is not recorded anywhere in this repository.

**C-6, stated plainly.** C-6 says *"Python lint/type/test CI on Ubuntu and
Windows"*. Lint and type checking now run on Ubuntu only. The test suite
still runs on both platforms, and the CLI is still exercised as a real
subprocess on Windows. What is lost is `mypy`'s judgement of Windows-only
branches on a Windows interpreter. If C-6 is to be kept literally, `lint`
needs a two-platform matrix instead of one runner; that is an owner's
decision, and it trades the duplicate-work saving for the second platform.

## The Ubuntu slow file: `tests/test_cli.py`

**Measured 2026-11-02.** The figures below are that measurement; re-measure
them from a runner log before treating them as current.

**What it is.** On Ubuntu, shard 0 is one file: `tests/test_cli.py`. The
partition is not broken — the other four shards are balanced at 264.7s each
against the file's 325.8s (the costs `ci-shards.json` recorded at `e5472f8`,
the commit that wrote this section, whose own `measured_at` is `cf081e4`),
**a balance factor of 1.2308** inside the 1.6 limit. The file is simply the
floor: no arrangement of the remaining files makes the shard that holds it any
shorter.

**The anchor is the cost table's, not a partition's, and the two readings
differ.** `cf081e4` is the revision those *costs* were measured at. The
partition printed above belongs to `e5472f8`. A reader who opens the shard file
**at `cf081e4` itself** finds a different table and a different partition —
Ubuntu 422.8s against 248.6s, `max / min` **1.7010**, a negative slack — because
that tree had not been re-partitioned yet. Re-measure both from the table named
in the row you are reading, not from the anchor's own tree.

**What this paragraph printed before 2026-11-12, and why that was wrong.** It
printed **1.176**. That figure is not what this project's balance check
computes. `tests/test_ci_shard_coverage.py` measures the partition against the
1.6 limit through `min(loads) × 1.6 − max(loads)` — the slack a new file may
add — which is the same ratio `.github/make_ci_shards.py` prints as
`max(loads) / min(loads)`, and on the recorded costs above (325.81 against
264.72) that ratio is **1.2308**. The 1.176 is the floor against the **mean**
(325.81 / 276.92 = 1.1765): derivable from the same five costs, but through a
formula nothing in the repository computes or watches. One quantity, two
denominators, and the record named the one no witness reads.

**The same quantity today, re-measured rather than carried.** At the costs
`ci-shards.json` records at
`46e2c21918286a723f9d07d5409d0e52e7551a85`, Ubuntu's shards are 391.8s against
307.6s — `max / min` **1.2735**, floor against mean 1.2075 — and Windows is
895.7s against 895.7s, **1.0000**. `tests/test_cli.py` is the Ubuntu floor there
as well, and the 1.6 limit is unchanged.

**Why it is slow.** It is an end-to-end subprocess file, on purpose: every
test starts a real console-script process and reads its exit code and two
streams (the module docstring says why — an in-process `CliRunner` would not
exercise option parsing, exit codes, or the bytes that reach a terminal). The
file collects 95 tests and calls `run_cli()` at 105 sites; the `workspace`
and `task_id` fixtures each start another process (`init` and `task create`)
per test that uses them. There are no sleeps in the file; `timeout=300` is
an upper bound, not a wait.

**Measured locally, to see the shape, not to predict the runner.** On this
Windows development machine, `python -m pytest tests/test_cli.py
--durations=0` is 95 passed in 655.4s. The duration report splits it:
**setup 352.5s (53.9%) across the 79 tests that use a fixture**, and call
302.0s (46.1%) across 90 tests; the mean setup is 4.46s per test. The most
expensive single test is 16.2s. A bare `labcairn --help` costs 0.58–0.82s
here (five runs), almost all interpreter start and imports, so the fixture's
`init` and `task create` processes cost more than a bare start — they also
create the workspace and write the store. **More than half the file's time
is rebuilding the same workspace and task per test**, which is the shape the
fixture-sharing option below addresses. The absolute number is a dev-machine
number and is not comparable to the runner's; only the split is the finding.

**It is not the wall-clock bottleneck.** The same commit measures
`tests/test_cli.py` at 690.0s on Windows, and each Windows shard costs 844s
against Ubuntu's 325.8s. Windows sets the wait. Splitting or speeding up the
Ubuntu file improves the Ubuntu balance and does not shorten the run.

**Directions, with risks — for the owner to choose.**

1. **Split the file by command group** into several `test_cli_*.py` files.
   Low risk: the tests and what they exercise do not change, and the shard
   list can spread the pieces. It needs `python .github/make_ci_shards.py`
   (with runner-measured costs from the next run, per the project's rule)
   and gives an Ubuntu-only gain; the Windows wall clock stays.
2. **Share one CLI-made workspace and copy it per test** instead of running
   `init` and `task create` for every test. Saves roughly two process
   starts per test, but changes what the fixture proves: today the workspace
   is made by the CLI in that test. It needs a witness that a copied
   workspace is byte-for-byte usable by every test, and a check that no test
   mutates shared state.
3. **Make the CLI's imports cheaper** (lazy-load the heavy subcommands).
   Changes product code, not tests; the file already has a test that
   `labcairn --help` is cheap, so the change would have to keep it cheap.
4. **Run the CLI in-process.** Not an option: it changes the property the
   file exists to test (a real process's exit code and streams). Listed here
   only so it is not proposed again.

**What was not done.** No change was made to `tests/test_cli.py` in this
piece. Every direction above either changes a measured property or needs a
runner measurement first, and the owner decides.
