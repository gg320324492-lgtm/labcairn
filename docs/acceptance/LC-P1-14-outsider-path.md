# LC-P1-14 — The outsider's path

**The claim.** `docs/EVALUATION.md` names six Phase 1 blockers, and the
first one is the only one that is about a **person** rather than about the
product:

> A new user cannot complete a task from a clean environment following README.

**The thing that makes it expressible** is [`scripts/outsider_path.py`](../../scripts/outsider_path.py):
a script that clones the repository into a directory of its own, builds an
environment **inside that clone**, runs the README's commands there for real,
binds a research folder, makes a task, produces a report and a deterministic
figure, revises it, survives a restart, and reads the same task back through
two surfaces. Every step is a check that raises rather than warns, so the exit
code is the assertion.

**This document is the record of one measured run**, not a description of what
the script would do. Every number below came out of the run whose report is
quoted; the run's own command lines, exit codes and seconds are in §4.

---

## 1. What was run, and where

| | |
|---|---|
| The script | `scripts/outsider_path.py` |
| The witness | `tests/test_outsider_path.py` |
| The mode | **`reviewer`** — every command the README shows, as the README writes it (§4) |
| The work root | `E:\labcairn-local\outsider-reviewer` — outside the repository, and outside every other repository |
| The clone | `E:\labcairn-local\outsider-reviewer\clone` |
| The workspace | `E:\labcairn-local\outsider-reviewer\workspace` — **outside** the clone and outside the checkout |
| The machine | Windows 11 Pro 10.0.26200, `uv 0.11.21`, Node v24.16.0, pnpm 9.15.9, Python 3.12.13 |
| The commit cloned | `92cc92025ac6d2a8186805ae808d80da7c6287de` |
| The run | **115 checks, all held**, in **1573.2 s** — of which the whole suite in the clone is 1501.4 s |

To run it yourself:

```bash
python scripts/outsider_path.py --mode reviewer --work-root E:\labcairn-local\outsider
```

`--mode reviewer` runs every README command as the README writes it,
including the whole suite. `--mode witness` reduces the whole-suite command to
a collection; §4 says why, and the report records the reduction against the
command it applies to, so a witness run can never be read as a full-suite run.

**The work root has to be outside the repository**, and the script says so if
it is not. A run inside the checkout proves that the checkout works, which is
not the claim.

**A note on the seconds.** They were measured on a machine that was running
other suites at the same time — four LabCairn worktrees' pytest runs and
some unrelated work — so they are an **upper bound** on what the run costs on
an idle machine. The counts (115 checks, eleven commands, three sources, six
files per revision) are the facts; the seconds are what this machine gave,
and a runner with a quiet machine will give less. The shard file's costs were
measured the same way, which is the safe direction: a file that looks dearer
than it is makes its shard look dearer than it is.

---

## 2. Why the clone, and how the run was kept honest

Four things make "a clean clone" a measurement rather than a description.

1. **The clone is outside the checkout.** The script refuses a work root
   inside the repository, and asserts that the clone it made is outside the
   repository it was cloned from.
2. **The clone's tree is clean and at the same commit.** The script reads
   `git status --porcelain` and `git rev-parse HEAD` in the clone and compares
   them with the source repository's own commit.
3. **The clone has no environment.** The script asserts that the clone holds
   no `.venv`, no `web/node_modules`, no `output/` and no `.labcairn/` before
   it starts. A clone that already carried an environment would be a
   developer's checkout with a different name.
4. **The code under test is the clone's.** The walk runs under the clone's
   own interpreter (`<clone>/.venv/Scripts/python.exe`), and it prints where
   the package was loaded from. The check is that the package is inside the
   clone and **not** inside the developer's repository — because a run that
   quietly used the developer's tree would satisfy every other assertion here
   and prove nothing.

**The report names the commit the clone was made from**, not the
repository's head at the end of the run. A run takes three minutes, and a
commit can land inside one — so the commit is read when the clone is made, and
the witness requires it to be a commit this repository holds. (The witness
caught the difference: a commit made while a run was going left the report
naming the later commit, and the clone was of the earlier one.)

The temporary directory is the run's own (`TEMP`, `TMP` and `MPLCONFIGDIR`
all point inside the work root). Two reasons, both measured on this machine:
the default base temporary directory fails here with `WinError 5`, and a
temporary directory inside the checkout makes two of the repository's own
tests fail for a reason that has nothing to do with what they test.

---

## 3. The walk, step by step

The P1 deliverable, in the order the deliverable names it:

> An unrelated researcher installs LabCairn, configures an eligible LLM
> provider, binds a research folder containing a text PDF, CSV/XLSX and
> Markdown, creates a task, receives a report and deterministic scientific plot
> with source locators and an evidence ledger, requests a revision, and reopens
> that same task following a simulated restart. CLI and local Web use the same
> application services. The original materials remain unchanged.

| # | The step | How it was done | The evidence |
|---|---|---|---|
| 1 | **Install** | `uv sync` in the clone | The clone's own `.venv`, with the project's package installed **editable from the clone's `src/`** |
| 2 | **Bind a research folder** | `labcairn task create --source-dir materials` | Three bound sources: `materials/paper.pdf` (kind `pdf`, readable), `materials/measurements.csv` (kind `csv`), `materials/notes.md` (kind `markdown`) |
| 3 | **Create a task** | the same command | One task; `labcairn task status --json` reports it |
| 4 | **A report and a deterministic figure** | the layer's `render_report`, and `run_analysis` under a granted `analysis.run` approval | `report/v1/` holds `report.json`, `report-manifest.json`, `report.md`, `report.html`, `report.docx`, `report.pdf`; the figure is an SVG whose bytes hash to its receipt, and **two renders of the same recipe are byte-identical** |
| 5 | **Source locators** | three anchors, one per kind of material | The report's citations are locators of three kinds — `csv` (row and column), `pdf` (page), `text` (line and section) — and each address **resolves** in the material the task holds |
| 6 | **An evidence ledger** | three evidence records | The report's snapshot names `ev-csv`, `ev-md`, `ev-pdf`; every claim cites the address it rests on |
| 7 | **A revision** | the researcher's own edit to the table | The repository's own measurement says the material moved; the walk marks the report's receipt `STALE` with the repository's own reason and **regenerates nothing**; the report is then generated again as **v2**, with **v1's bytes unchanged**; the refreshed material goes back through `labcairn sources ingest`; the analysis runs again over the revised bytes and draws a **different figure**; and the attempt to **recompute** the report from the revised bytes is **refused** — §7.2 |
| 8 | **A restart** | the service is started again in a **new process** | The task after the restart is the task before it; the service serves the same task; `labcairn task resume` makes **a new run against the same task** |
| 9 | **Two surfaces** | the CLI and the local service, against one workspace | 308 fields compared between the CLI's `task status --json` and the API's `/task`; 288 between the two artefact lists; for each of the four forms, the bytes on disk, the bytes the API serves and the receipt's hash **agree** |
| 10 | **The material unchanged** | every file's hash, before and after | The repository's own fixture corpus is byte-identical; the research folder still holds exactly the three files it was given; **every file the product produced is under the task's own output area** |

### 3.1 "The original materials remain unchanged" — exactly what that holds here

The deliverable's last sentence, and it is worth being precise about it,
because the run shows something narrower and something wider.

**The wider part.** The product wrote **nothing** into the research folder.
Every file it produced is under the task's own output area, the research
folder still holds exactly the three files it was given, and the repository's
own fixture corpus — the controlled table and the paper the folder was built
from — is byte-identical afterwards. LabCairn reads the material and writes
its own outputs somewhere else.

**The narrower part, stated rather than glossed.** The one file whose bytes
differ at the end of the run is the table, and **the walk changed it, not the
product**: that edit is the researcher's, and it is what makes the revision a
revision rather than a copy. The *original* material survives in two places —
the pristine corpus in the clone, and the first revision's manifest, which
still records the hash the claims were read from.

So the sentence holds in the sense that matters for a product — **LabCairn
does not write to the material it was given** — and it does not hold in the
sense that the file's bytes never move, because a revision means the
researcher's material moved. Reading it the other way would make the
deliverable's own two clauses ("requests a revision" and "the original
materials remain unchanged") contradict each other.

---

## 4. The README's commands, and what running them measured

The command list is **extracted from the README in the clone**, and compared
with the script's table in both directions: a command the README shows that
the script does not run is a failure, and a row in the table that the README
does not show is a failure too. The table is fail-closed.

| The README's command | Exit | Seconds |
|---|---|---|
| `uv sync` | 0 | 12.8 |
| `uv run pytest` | 0 | **1501.4** |
| `uv run ruff check .` | 0 | 0.1 |
| `uv run ruff format --check .` | 0 | 0.1 |
| `uv run mypy` | 0 | 1.9 |
| `uv run labcairn --help` | 0 | 0.6 |
| `pnpm install --frozen-lockfile` | 0 | 2.7 |
| `pnpm test` | 0 | 2.4 |
| `pnpm typecheck` | 0 | 1.5 |
| `pnpm lint` | 0 | 3.8 |
| `pnpm format:check` | 0 | 1.0 |

**Two modes, and two reductions.** The `reviewer` mode is the one a person
runs, and the table above is it: **every command the README shows, as the
README writes it, including the whole suite in the clone** (1501.4 s of the
1573.2 s the run took).

The `witness` mode is the one a test runs, twelve times over in the CI's
shards, and it reduces two of them — and **each reduction is recorded in the
report against the command it applies to**, so a witness run can never be read
as a reviewer run:

| The reduction | Why | What it does instead |
|---|---|---|
| `uv run pytest` | running the whole suite from inside the suite would recurse: `tests/test_outsider_path.py` runs the script, which runs the suite, which runs that file's own test | `uv run pytest --collect-only -q tests` |
| the five `pnpm` commands | they are the `web-quality` workflow's job, and the `python` workflow is not the `web` workflow; installing the web package's dependency tree in every Python shard proves once what the web workflow proves once | they are recorded as **not run, with the reason** (§7.8) |

**The lockfiles were watched too.** `uv sync` and `pnpm install
--frozen-lockfile` must leave `uv.lock` and `web/pnpm-lock.yaml`
byte-identical. An install that rewrites a lockfile is a change to the
repository rather than an install, and the run failed would have said so.

---

## 5. The provider: which steps were made against a fixture

**No real provider was called.** There is no credential for one in this
repository, so every step was made against the repository's own deterministic
material and the local surfaces, with no network call to a model and no
credential. `labcairn doctor` was asked, before anything else, and it reported
**no configured provider** — which is the fact this section rests on.

| The step | What it was made against |
|---|---|
| The material | `tests/fixtures/analysis/groups.csv` (the controlled table whose statistics were written down by hand beside it), `tests/fixtures/papers/arx-2610.10596.pdf` (a text PDF), and a Markdown the script writes |
| The figure | the repository's own deterministic renderer, driven by a chart recipe the script writes into the workspace |
| The report | the repository's own renderers — no model call anywhere in the path |
| The claims | written by the walk itself, because **the product has no operation that writes an evidence record or an anchor** (§7.3) |

**This is the "deterministic fixture without provider" half of LC-P1-14's
acceptance clause.** The other half — a real provider under a declared model,
version and parameter set, with its cost recorded — is T04's, and it waits on
the owner's answer about whose credential is used.

---

## 6. What the walk did not exercise

The run says this in its own output, and the report carries it:

- **The React application was not run in a browser.** The workbench was
  driven through the API it reads, and the paths the walk used were checked
  against the workbench's **own list of them** (`web/src/api/paths.ts`), so
  "the Web and the CLI use the same application services" is checked against
  the client's code rather than asserted.
- **The event stream was not consumed.** The workbench does not read it, by
  decision (`web/src/api/paths.ts` says so), and nothing here demonstrated a
  client reading it.
- **The workbench cannot switch the selected project.** The API has no such
  operation, so there was nothing to drive.
- **The DOCX and the PDF are not byte-reproducible.** Their bytes are recorded
  and compared as stored against served, not across two renders.
- **The product has no operation that writes an evidence record or an
  anchor.** The walk wrote the claims' own addresses and the records that
  rest on them itself. The report carries real claims, cited to real
  addresses in the material the CLI ingested — but the claims were made by
  the walk, not by the product. **This is the one step of the deliverable
  that is not the product's, and it is named rather than hidden** (§7.3).

---

## 7. The findings

These are what the walk found on the way. They are findings about the
repository, not about the script.

### 7.1 The report and the figure have no surface of their own

`labcairn` has no command that renders a report or draws a figure, and the
API has no route for either. The walk reached them through the application
layer's own operations — `run_analysis` and `render_report` — which is what
the G4 demonstration does as well. **A stranger following the README cannot
produce a report, because the README's command table has no command that
produces one.** The commands that exist today are the ones the README's table
lists (`init`, `doctor`, `task create|run|resume|status`, `sources
inspect|ingest`, `artifacts list`, `serve`), and none of them renders the
report the deliverable asks for.

*What it means for LC-P1-14:* the acceptance clause says an external
reviewer can "reproduce the canonical task". They can, but the last two steps
of it need a Python import rather than a command. **This is a gap for the
owner to rule on**: either the CLI grows a `labcairn report render` command,
or the acceptance record says plainly that the report path is reached through
the application layer.

**Corrected since this was written, and still true of the figure.** The CLI grew
`task report` and the service grew `POST /report`, both through the layer's own
`render_report` and answering with its own `ReportRendered`, and a fresh
workspace's default policy permits `report.render` (the registry binds the
capability to output roots; the content checks decide whether a report may
exist). The command list above is the one this walk measured, and it is now
twelve commands, not the ten it names — `task reconcile` and `task report`
arrived after the walk ran. **What did not change**: `run_analysis` still has no
command and no route, so the figure is still reached by import, and **the walk
still renders the report through the layer rather than through the new command** —
changing the walk was not measured locally, so the claim below stands as measured
rather than being rewritten to match the code.
See [`RELEASE-NOTES.md`](../RELEASE-NOTES.md) §2.1 for the current state.

### 7.2 The report cannot be recomputed from the revised material

**This is the finding that matters most for the deliverable's "requests a
revision".** The measured sequence, from the run's own report:

1. The researcher's edit changes the table. The repository's own measurement
   says the material moved, and the walk marks the report's artefacts `STALE`
   with the repository's own reason. **The stale mark regenerates nothing** —
   a stale mark is recorded, and a human decides whether the change mattered.
2. The report **is** generated again, as `v2`, and `v1`'s six files are
   byte-identical afterwards. So a revision is possible.
3. The refreshed material goes back into the ledger through
   `labcairn sources ingest`, the ledger records the new content hash, and the
   analysis runs again over the revised bytes and draws a **different figure**.
4. **The report is then rendered again, and the layer refuses**:

   > the report was refused before it could be written as a revision: the
   > chain names 'materials/measurements.csv' twice with different hashes. One
   > upstream thing is one dependency, and the chain would be recording two of
   > them under one name.

**Why.** A report's chain is the flat ancestor closure of its parts. The
document carries **every** figure the ledger holds, and the analysis service
writes each run's figure to a **new** path (`new_id().hex` in the run token),
so the old figure and the new one are both in the document — one naming the
material by its old hash and one by its new hash. The chain builder refuses to
name one upstream twice with two hashes, and it is right to: a chain like that
would mark the report stale for one of them and current for the other.

**What it means.** The product can mark a report stale and can generate a
second revision of it, but **the second revision still rests on the material
the claims were read from** — the report's content is not recomputed from the
revised bytes. Re-computing it would need either the stale figure to be
dropped from the document (there is no operation that removes an artefact
receipt, and the artefact ledger is in memory) or the material's chain to name
one hash rather than two.

*This is a Phase 2 finding, not a defect this work order fixes.* It is
recorded here because the deliverable says *"requests a revision"*, and the
honest answer is what the run measured: the revision is generated, and the
re-computation is refused with a reason that names itself.

### 7.3 The evidence ledger cannot be written through any surface

Already named by G4's demonstration, and confirmed here: there is no product
operation that writes an evidence record or an anchor. The walk wrote them
itself, against the addresses **the ledger itself holds** — the addresses are
read out of `source_texts` and parsed back, rather than guessed, because an
anchor at an address nothing answers is an anchor to nothing. (That is how the
Markdown's addresses turned out to be section-qualified: a locator built from
the line alone names an address the ledger does not hold, and an early run of
this script was refused for exactly that.)

### 7.4 The base branch was red when this work started

`origin/local/g5-work` at `26f161e` added `tests/test_earlier_exit_demos.py`
without adding it to `.github/ci-shards.json`, so
`tests/test_ci_shard_coverage.py` failed on two counts: the file was in no
shard, and no cost was recorded for it. **A test file in no shard is a test
CI never runs.** This work order's own test file needed a shard entry too, so
the shard file is repaired here (§9) — which is a change outside this work
order's three files, made because the file-ownership map has no owner for it
and the tree was red without it.

### 7.5 The README's command list is a shared contract

The script's table has a row for every command the README shows, and the
comparison is fail-closed in both directions. **So a command added to the
README without a row here fails the run, and a row here that the README does
not show fails it too.** T06 owns the README; the two have to change
together, and the check is what makes that visible rather than silent.

### 7.6 The product refuses a new file under a Windows short-spelled directory

**Measured here, and it is the defect the task breakdown's §2.6 names.** On
Windows, a directory with a long enough name is given an 8.3 short alias, and
the product compares the **declared** spelling of a path with the **resolved**
spelling of its root. A path that does not exist yet keeps its short
spelling — there is nothing for the OS to expand — while the root exists and
comes back long-spelled, so two spellings of one directory are compared as if
they were two directories.

The probe, on this machine, against the product's own path layer
(`labcairn.security.paths.canonicalize`):

```
long  : C:\Users\pc\AppData\Local\Temp\a-very-long-directory-name-for-the-short-name-test
short : C:\Users\pc\AppData\Local\Temp\A-VERY~1
root  : C:\Users\pc\AppData\Local\Temp\a-very-long-directory-name-for-the-short-name-test
declared with the SHORT spelling: REFUSED (outside_every_root)
declared with the LONG spelling: accepted, key = outputs/summary.md
```

**The walk works around it, and says that it does.** The script resolves its
work root before it makes anything under it, so the whole walk runs in one
spelling — and the report carries both spellings, so a reader can see whether
the workaround was needed on the machine that ran it.

**And the walk survives it.** The run in §1 was made with a work root that
has no short spelling, so it does not exercise the defect. So the walk was
run again with a work root **given in the short form**, and it held:

| | |
|---|---|
| The work root as given | `C:\Users\pc\AppData\Local\Temp\A-VERY~1\outsider-t03` |
| The work root the walk used | `C:\Users\pc\AppData\Local\Temp\a-very-long-directory-name-for-the-short-name-test\outsider-t03` |
| The result | **115 checks, all held**, in 215.5 s, at commit `2d968d2` |

**What is the script's and what is the product's.** The workaround is the
script's. **The product's defect is still there**, and it is T02's to fix in
the path layer: the declared spelling and the root have to be compared in one
spelling. This work order does not fix it, and does not pretend to.

### 7.8 The CI's Python job has neither pnpm nor the web package's Node

**Found on CI, and it is an environment difference rather than a defect in the
walk.** The `python` workflow installs Python and uv and runs the suite; pnpm
lives in the `web` workflow, where `pnpm/action-setup` installs it and
`actions/setup-node` pins Node 24.16.0. So a runner that runs the Python
suite has **the runner's own Node and no pnpm**, and the walk's sweep of the
README's web commands could not run them — the report had no `clone` key and
the witness failed on a `KeyError`.

**Then the install itself failed**, with corepack having enabled pnpm
successfully. The web package declares `"node": ">=24.16.0 <25"`, and the
Python job never asked for that Node.

**Two decisions came out of it.**

**The first is what the walk does about a machine that cannot run the web
package's commands.** The web package's five commands are the **`web-quality`
workflow's job**: the `python` workflow is not the `web` workflow, and
running them in every Python shard installs the web package's dependency tree
twelve times to prove what the web workflow proves once. **So the witness
mode does not run them, and says so per command in the report**, and **the
reviewer mode runs them** — the mode a person runs, and where §4's
measurement comes from. That is the same kind of reduction the whole-suite
command already had, and it is recorded the same way.

**The second is that the script obtains pnpm itself** when the machine has
Node but no pnpm, in the order that is cheapest and most likely to work, and
**the version is the repository's own pin** — read out of
`web/package.json`'s `packageManager` field rather than written down twice:

| | |
|---|---|
| 1. `pnpm` on PATH | the normal case, and the one a machine that followed the README has |
| 2. `corepack enable pnpm` | Node's own mechanism, which uses the version `packageManager` pins |
| 3. `corepack pnpm` | the same thing without writing a shim, for a Node whose directory is not writable |
| 4. `npm install` of that same pinned version into the work root | needs nothing but npm |
| none of them | the commands are recorded as not run, with the reason |

**Both fallbacks were measured**, on this machine, with the tool removed from
`PATH`:

| The machine had | The walk ran the web commands with | The result |
|---|---|---|
| no pnpm, corepack yes | `corepack pnpm`, using the pnpm@9.15.9 `web/package.json` pins | **115 checks, all held**; all five web commands ran and exited 0 |
| no pnpm, no corepack, npm yes | `npm install` of the same pinned version into the work root | **115 checks, all held**; all five web commands ran and exited 0 |

**And a failing command now says what it said.** pnpm writes its progress
and its errors to standard output, so a failure report built from the error
stream alone reads *"exit 1"* and nothing else — which is a failure nobody
can act on. The detail carries **both** streams now.

**What is left to the owner.** `pnpm format:check` is a command the README
documents, and **no CI workflow runs it**: the `web` workflow runs install,
typecheck, lint, test and build, and the Python suite runs it only on a
machine that has pnpm — which a runner does not. That gap is not this work
order's to close (the workflows are not its files), and it is named here
rather than left for the next reader to find.

### 7.9 The default temporary directory fails on this machine

`uv run pytest` as the README writes it fails here with `WinError 5` unless
`TEMP` and `TMP` point at a directory outside any repository. The script sets
them for every child it runs, and the repository's own rules (`CLAUDE.md`)
already say why. This is a fact about this machine, not about the README.

---

## 8. The witness, and what it was shown to catch

`tests/test_outsider_path.py` runs the script and reads the report it wrote.

| The test | The property it watches |
|---|---|
| `test_the_outsiders_path_runs_and_every_claim_holds` | the exit code is zero, and every claim the run recorded held |
| `test_the_run_was_made_in_a_clean_clone` | the clone was outside the repository, clean, and at the same commit |
| `test_the_walk_ran_the_clones_own_code` | the package under test was inside the clone and **not** inside the developer's repository |
| `test_every_readme_command_was_run_or_recorded_as_not_runnable` | the README's commands and the run's commands are **the same set**; each one either exited 0 or was recorded as not runnable **with a reason** — and only a web command may be the latter |
| `test_the_witness_run_records_the_suite_reduction` | the whole-suite command's reduction is recorded, so the run cannot be read as a full-suite run |
| `test_the_record_names_every_command_and_its_outcome` | this document names every command the run executed |
| `test_every_claim_the_deliverable_names_was_made` | each claim the P1 deliverable names was made, and held — **including the two controls**, which are what make the comparisons between the surfaces falsifiable |
| `test_the_walk_says_what_it_did_not_exercise` | the run named its own limits |
| `test_the_command_table_check_fails_when_the_readme_shows_a_command_it_does_not_run` | **the mechanism**, watched: the table's check refuses a README command it has no row for, and names it |
| `test_the_command_table_check_fails_when_the_script_runs_a_command_the_readme_does_not_show` | the same check, in the other direction |
| `test_the_command_table_check_passes_when_the_readme_shows_exactly_its_commands` | the control: the check accepts a README that agrees with the table |
| `test_the_extractor_reads_instructions_and_ignores_illustrations` | a ```` ```python ```` block is prose and is not run as a command |
| `test_the_extractor_ignores_comments_and_blank_lines` | a comment in a shell block is a comment |
| `test_the_extractor_finds_nothing_in_a_document_with_no_commands` | the control for the extractor: an empty answer is an answer |
| `test_the_version_comparison_reads_the_ranges_the_repository_writes` | the comparison the web-environment check uses, watched — and it says *unknown* about a range it cannot read rather than guessing |

### 8.1 The mutations, and which test went red

A witness that has never been shown to fail is not a witness. Each mutation
below was applied to `scripts/outsider_path.py`, the witness was run, and the
script was put back exactly as it was. **All four went red** — and they were run again, against the script as it
stands after the base was merged and the short-name workaround was added, so
the record is of the code that is committed rather than of an earlier draft.

The witness was run with:

```bash
uv run pytest tests/test_outsider_path.py::test_the_outsiders_path_runs_and_every_claim_holds -q --basetemp E:\labcairn-local\bt-mutation
```

| # | The mutation | The edit | What went red |
|---|---|---|---|
| M1 | A row was removed from the script's command table | the `pnpm lint` row deleted from `README_COMMANDS` | `test_the_outsiders_path_runs_and_every_claim_holds` — the run refused with *"every row in this script's table is a command the README shows"* and the script exited non-zero |
| M2 | The extractor was changed to read every fenced block, illustrations included | `if language not in SHELL_LANGUAGES: continue` → `if False: continue` | `test_the_extractor_reads_instructions_and_ignores_illustrations` — *"assert ['uv sync', '...illustration'] == ['uv sync', 'uv run pytest']"* |
| M3 | The staleness walk was given a hash that did not move | `invalidate_on_source_change(task_id, [original_hash])` → `invalidate_on_source_change(task_id, ["0" * 64])` | `test_the_outsiders_path_runs_and_every_claim_holds` — the walk's claim *"the report's own receipt is among the artefacts the walk marked stale"* did not hold |
| M4 | The difference function was narrowed until it compared nothing | the body of `differences()` → `return ()` | `test_the_outsiders_path_runs_and_every_claim_holds` — and the walk's own **control** *"the field-by-field comparison finds the difference it was given"* is what caught it, because the main check still passed |

**M4 is the one that matters most.** A comparison narrowed until it compares
nothing also reports "no differences", so the main check would have gone on
passing. It is the control — the same comparison, run once over a copy of the
API's document with a difference planted in it — that refuses to be narrowed.
That is why the walk has one.

---

## 9. The measured costs

The shard file is hand-edited and `tests/test_ci_shard_coverage.py` watches
it: **a test file in no shard is a test CI never runs**, and every other check
stays green while it goes. This work order adds one test file, and the base
branch added another without one, so the shard file is repaired here.

| File | Windows | Ubuntu |
|---|---|---|
| `tests/test_outsider_path.py` | **152.6 s** | **not measured on a runner** |
| `tests/test_earlier_exit_demos.py` | the base's runner number | the base's runner number |

Measured on 2026-10-25 on this machine, with `--durations=0`, and the
per-file seconds read out of the durations section — the same way the shard
file's other numbers were read out of the CI log's. `test_outsider_path.py`'s
cost is almost all of one thing: the run it makes, which is the script's
170.5 s.

**The witness was measured five times**, and the machine was busy every
time: **145.2 s**, **152.6 s**, **157.3 s** and **256.7 s**, and once more
at **149.0 s** after the web commands became a recorded reduction (§7.8) —
which is about ten seconds' worth, because the web package's dependency tree
was already in the store. The spread is the contention
— four other LabCairn worktrees were running their own suites throughout — and
**the recorded number is the least-contended of the three**, because the
shard plan's job is to predict what a runner will take, and contention only
inflates a local measurement. The largest of the three would be the
conservative choice for a budget and the wrong estimate of a runner's time.

**`tests/test_earlier_exit_demos.py` is the base's own row**, measured on the
runner, and it was not touched.

**Only this work order's own file is a development-machine measurement.**
The other 102 files' costs are the base's own runner re-measurement (the
shard file's `measured_at` names the commit they were measured at), and this
work order's file was measured here, on Windows, while four other suites were
running on the same machine — so its number is an upper bound, and the
**Ubuntu entry is the Windows measurement carried over**.

**That is the conservative direction** — a file that costs more than it does
makes its shard look dearer than it is, and the balance check compares shards
within one platform — but it is a number that was not measured on the platform
it is used for. **The next runner that runs this file should replace it**,
with `python .github/remeasure_shards.py <run-id>`, which reads the per-file
seconds out of the CI log's durations section and rebuilds the partition from
them.

---

## 10. The limits

- **The witness mode does not run the whole suite.** It collects it. The
  reviewer mode does, and the difference is recorded in the report (§4).
- **The browser was never opened.** The Web path is the API the workbench
  reads, checked against the workbench's own list of paths (§6).
- **No provider was called**, and the acceptance clause's other half — a real
  provider under a declared model, with its cost recorded — is T04's (§5).
- **The claims were written by the walk**, because the product has no
  operation that writes them (§6, §7.3).
- **A check in the script that stopped asking its comparison a question would
  not be caught by the witness.** The walk's two comparisons between the two
  surfaces are each run once over something that must answer the other way —
  a copy of the API's document with a difference planted in it, and a copy of
  the file on disk with its bytes altered — so a comparison *narrowed* until it
  compared nothing fails its own control (§8.1, M4). What no control would
  notice is a check that stopped asking its comparison anything at all and
  answered for itself; that is the limit of the controls, and it is stated
  here rather than left to be found.
- **The Ubuntu costs are not runner measurements** (§9).
- **The work order's own shard-file change is outside the three files this
  work order owns**, and was made because the tree was red without it
  (§7.3).
