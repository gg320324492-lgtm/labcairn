# LabCairn — Quickstart

**This page is the outsider's path.** It takes a directory of research
material — a text PDF, a CSV and a Markdown — binds it, creates a task,
produces a report with source locators and an evidence ledger, makes one
revision, and reopens the same task after a restart.

**It is written to be followed, not believed.** Every command on this page
either is a command [the command line](../README.md#the-command-line-what-exists-today)
has today, or is a step the repository's own walk script makes; §7 names the
witness for each. And the whole path can be **run by one command**, whose
exit code is the assertion — §3.

**What this page is not.** It is not a product tour, and it does not
describe a finished application. The report and the figure are reached
through the application layer's own operations, because there is no CLI
command that renders either — §4.7 says so precisely, and the
[release notes](RELEASE-NOTES.md) carry it as a known limitation rather than
a surprise.

---

## 1. What you need

| | |
|---|---|
| **uv** | [uv](https://docs.astral.sh/uv/). It provisions Python 3.12 itself; `.python-version` pins it. |
| **Node and pnpm** | Only for the web package's commands. Node ≥ 24.16 with pnpm ≥ 9.15.9 — the versions `web/package.json` declares. The path on this page does not need them. |
| **A provider credential** | **Not needed, and not used.** There is no credential in this repository, so every step below runs against the repository's own deterministic material with no network call to a model. §6 says what that does and does not establish. |

Everything below happens **inside a clone of this repository**. The walk
script (§3) makes its own clone; the by-hand path (§4) assumes you are in
one.

---

## 2. The material

Three files, of three kinds, in one directory:

| File | Kind | Where it comes from |
|---|---|---|
| `materials/paper.pdf` | a **text** PDF — one whose text layer can be read and cited | `tests/fixtures/papers/arx-2610.10596.pdf` — CC BY 4.0; its attribution is [`tests/fixtures/papers/MANIFEST.md`](../tests/fixtures/papers/MANIFEST.md) |
| `materials/measurements.csv` | tabular data | `tests/fixtures/analysis/groups.csv` — a controlled table whose statistics were written out by hand beside it |
| `materials/notes.md` | prose | one you write; three lines is enough |

A PDF whose text layer cannot be read is **not** a substitute. The walk
asserts that the PDF is `readable`, and an unreadable document is not
citable — the point of the material is that a claim can point *into* it.

The four public fixtures under `tests/fixtures/public/` are a different set:
they are the evaluation corpus, with answer keys, and every byte of them is
synthetic. The [fixture record](acceptance/LC-P1-13-fixtures.md) says which
is which.

---

## 3. The whole path, in one command

This is the part that is **watched**. The script clones the repository into
a directory of its own, builds an environment inside the clone, runs the
README's commands there for real, and then walks the path in §4 — and every
step it takes is a check that raises rather than warns, so **the exit code
is the assertion**.

```bash
uv run python scripts/outsider_path.py --mode reviewer --work-root E:\labcairn-local\outsider
```

- The **work root must be outside the repository**, and outside every other
  repository. The script refuses a work root inside the checkout and says so.
- `--mode reviewer` runs every command the README shows, as the README writes
  it, **including the whole test suite** — so it takes the length the whole
  suite takes. `--mode witness` collects the suite instead of running it,
  because running the whole suite from inside the suite would recurse; the
  reduction is recorded in the report against the command it applies to, so a
  witness run can never be read as a full-suite run.
- It writes a machine-readable report to
  `<work-root>/outsider-path-report.json` and prints where everything is.

**The measured run** is in
[the acceptance record](acceptance/LC-P1-14-outsider-path.md): 115 checks, all
held, in the reviewer mode, at the commit it names. §5 lists what the walk
asserts.

**The script is run by a test**, in the witness mode, on every CI run:
[`tests/test_outsider_path.py`](../tests/test_outsider_path.py).

---

## 4. The same path, by hand

### 4.1 Install

From the repository root:

```bash
uv sync
```

This creates `.venv/` and installs the `labcairn` console script into it.
`uv.lock` must survive this byte-identical; if it does not, `pyproject.toml`
has drifted from the lock and that is a change to the repository, not an
install.

### 4.2 Make a workspace

```bash
uv run labcairn --workspace ./workspace init --json
```

It creates the directory, a migrated SQLite database, the source directory
`materials/`, the output area `output/`, and a policy file. It refuses to
overwrite a workspace that is already there, because a workspace holds a
task's history and a second `init` must not be able to leave two of them
disagreeing about what the workspace is.

The JSON names what it made — `root`, `database_path`, `migration_revision`,
`source_dirs`, `created` and `policy_digest`.

**The policy denies by default.** The default policy permits nothing, which
is the right posture for a workspace nobody has configured; §4.7 says how the
walk configures one.

### 4.3 Put the material in it

The research folder lives **inside** the workspace, because the source roots
are the workspace's own:

```bash
mkdir -p workspace/materials
cp tests/fixtures/papers/arx-2610.10596.pdf workspace/materials/paper.pdf
cp tests/fixtures/analysis/groups.csv workspace/materials/measurements.csv
```

And write `workspace/materials/notes.md` — three lines are enough:

```markdown
# Field notes

The table holds one row per trial, and the group column says which series
a row belongs to.
```

### 4.4 Create the task

```bash
uv run labcairn --workspace ./workspace task create --title "The outsider's own task" --objective "One research folder, one report, one figure." --criterion "The report names the cells it rests on." --source-dir materials --json
```

The command **ingests the material and binds it to the task** before it
returns: a task that holds no material can carry disclosures and never a
claim, because a claim rests on a cited record and a citation points into
material the task holds.

The JSON's `bound_source_ids` names the three sources. **Read them from the
output** — the order is not the file order, and every later command takes a
source id.

A file the command cannot read **makes it refuse**, and the message names
each file and why. It is not swallowed.

### 4.5 Run the inventory stage

```bash
uv run labcairn --workspace ./workspace task run --source <source-id> --json
```

This build runs the `inventory` stage and no other: the work is the layer's
own `inspect_source`, and the stage's output hash is the material's content
hash. The other declared stages have bodies in later work orders, and this
command does not pretend to have them.

The JSON carries the run, the stage and the operation. The stage's
`output_hashes` is the material's content hash — the same value the ledger
holds.

### 4.6 Read the ledger's addresses

```bash
uv run labcairn --workspace ./workspace sources inspect --source <source-id> --json
```

It reports one source as the ledger holds it: `kind`, `display_name`,
`relative_path`, `content_sha256`, `size_bytes` and `readability`.

**This is where the locators come from.** The ledger stores the material's
text **addressed** — a page for a PDF, a row and a column for a CSV, a line
and a section for a Markdown — and each address resolves against the
material the task holds. The walk reads those addresses **out of the ledger**
rather than constructing them, because an anchor at an address nothing
answers is an anchor to nothing.

To see the addresses themselves, read the `source_texts` rows for the
source's `content_sha256`. The walk does this in
[`scripts/outsider_path.py`](../scripts/outsider_path.py) and is the place
to copy the pattern from.

### 4.7 The report and the figure

**The report and the figure each have a command and a route.**
`labcairn task report` (`POST /report`, and a **Render the report** button in the
workbench) calls the layer's own `render_report`; `labcairn task figure`
(`POST /analysis`) calls its own `run_figure`. A fresh workspace permits both
capabilities. **A figure needs consent as well as permission**: the approval binds
the material, the operator, its parameters and the recipe's path (ADR-0012
constraint 7), so the steps are

```bash
labcairn task approval-request --capability analysis.run --root source:0   --resource-key one.csv --arguments-json "$ARGS"
labcairn task approval-grant <approval-id>
labcairn task figure --path one.csv --operator labcairn.analysis.mean   --recipe recipe.json --parameters-json "$PARAMS" --approval <approval-id>
```

where `$ARGS` holds `path`, `operator_id`, `recipe` and `parameters`, spelled
exactly as the run spells them — a different spelling is a different approval, and
the run refuses it rather than squinting at it. The fifteen commands that exist are
listed in
[the README](../README.md#the-command-line-what-exists-today); `task report`,
`task reconcile` and the `POST /report` route are newer than that table, and the
table stays conservative rather than the commands being hidden.

**What has not changed is the harder half.** A report needs something to carry:

1. **The claims must exist.** **The product has no operation that writes an
   evidence record or an anchor.** The walk writes the claim's own address
   and the record that rests on it itself, against the addresses the ledger
   holds. The report then carries real claims, cited to real addresses in
   the material the CLI ingested — **but the claims were made by the walk,
   not by the product.** This is the one step of the deliverable that is not
   the product's, and it is named rather than hidden.
2. **A task with nothing to report is refused, and writes nothing.** Ask the
   command on a bare task and the answer is `report_content_refused`: the
   document builder refuses a heading with nothing under it, and the output
   area stays empty. That refusal is the correct behaviour, not a missing
   default — a report the ledger does not support must not exist.

The **complete, working** version of this step is
[`scripts/outsider_path.py`](../scripts/outsider_path.py) — §7.3 of the
acceptance record says what it writes and where. What the report path
produces is:

- `report/v1/` holding `report.json`, `report-manifest.json`, `report.md`,
  `report.html`, `report.docx` and `report.pdf`;
- **source locators** in the citations, of all three kinds the material has,
  each one resolving against the material;
- an **evidence ledger**: the report's snapshot names the records it is a
  view of, and every claim cites the address it rests on;
- a **deterministic figure** whose bytes hash to its receipt, and **two
  renders of one recipe are byte-identical**.

### 4.8 The revision

The researcher's own edit is what makes a revision a revision. Edit a cell
in `workspace/materials/measurements.csv`, then:

```bash
uv run labcairn --workspace ./workspace sources ingest --json
```

The refreshed material goes back into the ledger and the ledger records the
material's **new** content hash.

What the walk then shows, in this order:

1. The material moved, by the repository's own measurement.
2. The report's artefacts are marked **STALE**, with the repository's own
   reason — **and the stale mark regenerates nothing.** A stale mark is
   recorded; a human decides whether the change mattered.
3. The report **is** generated again, as `v2`, and **v1's six files are
   byte-identical afterwards**.
4. The analysis runs again over the revised bytes and draws a **different**
   figure.
5. **The report is then rendered again, and the layer refuses**:

   > the report was refused before it could be written as a revision: the
   > chain names 'materials/measurements.csv' twice with different hashes.

   **So the second revision still rests on the material the claims were read
   from.** The report's content is not recomputed from the revised bytes.
   This is a Phase 2 finding, and the acceptance record says why.

### 4.9 The restart

The service reads the workspace from disk when it starts, so a restart is
the service starting **in a new process**:

```bash
uv run labcairn --workspace ./workspace serve --port 8000
```

It binds loopback only, mints its own session token, and writes the token to
the workspace rather than printing it.

With the service up, the same task reads the same way through both surfaces:

```bash
uv run labcairn --workspace ./workspace task status --json
```

and, from another shell, `GET /task` on the service — with the session token
the workspace holds. The walk compares them **field by field**, and compares
each artefact's bytes on disk, the bytes the service serves and the
receipt's hash. The two comparisons each carry a **control**: the same
comparison run over a copy with a difference planted in it, which must find
it — otherwise a comparison narrowed until it compared nothing would go on
passing.

**After the restart**, `task status` reports the same task, the same runs
and the same artefacts as before it.

### 4.10 A new attempt against the same task

```bash
uv run labcairn --workspace ./workspace task resume --source <source-id> --json
```

This is a **new Run against the same Task** — never a new Task. The JSON's
`run.attempt` is one higher and `run.task_id` is the task's.

### 4.11 What the task holds

```bash
uv run labcairn --workspace ./workspace task status --json
uv run labcairn --workspace ./workspace task status --plan --json
uv run labcairn --workspace ./workspace artifacts list --json
```

The first reports what **did** happen; `--plan` reports what **should**
happen — the declared workflow, stage by stage. The layer keeps the two
apart because neither is derived from the other.

`artifacts list` reports the receipts a task has produced. **On the path
above it reports `[]`**, because the report and the figure are produced
through the application layer and their receipts are recorded there — the
list is not empty once §4.7 has run.

### 4.12 Exit codes

`0` is a result, `2` is a usage error, `3` is a refusal by the application
layer, and `1` is a crash. **A script tells a refusal from a crash by the
exit code alone.** A refusal is rendered rather than raised: it names what
was refused and carries the layer's `reason` and `message` in the JSON form,
and it writes nothing to standard output.

---

## 5. What the walk asserts

The script's checks are the claim, and there are **115** of them in the
reviewer mode. They are not a summary; the report carries each one with its
label, its outcome and its detail. The load-bearing ones:

| The claim | Where |
|---|---|
| The clone is outside the repository, clean, and at the same commit | §2 of the acceptance record |
| The code under test is the clone's code and **not** the developer's tree | §2 |
| The README's commands and the run's commands are **the same set** | §4 |
| Every command exited 0, and the lockfiles were left byte-identical | §4 |
| The task holds a PDF, a CSV and a Markdown, and the PDF is readable | §3 |
| Each of the three addresses resolves in the material the task holds | §3 |
| The report carries the claims, and every claim cites the address it rests on | §3 |
| The figure on disk is the bytes the receipt records, and two renders are byte-identical | §3 |
| The CLI's task document and the API's are the same, field by field — **and the control finds a planted difference** | §3 |
| The report is marked stale, the stale mark regenerates nothing, and v1's bytes are unchanged | §3 |
| The service, in a new process, serves the same task | §3 |
| Every file the product produced is under the task's own output area | §3 |
| The repository's own fixture corpus is byte-identical afterwards | §3 |

The full list, with the two comparisons' controls, is in
[the acceptance record](acceptance/LC-P1-14-outsider-path.md).

---

## 6. What this path does **not** exercise

The run says this in its own output, and the report carries it:

- **The React application was not run in a browser.** The workbench was
  driven through the API it reads, and the paths the walk used were checked
  against the workbench's **own list of them**
  (`web/src/api/paths.ts`). "The Web and the CLI use the same application
  services" is therefore checked against the client's code, not measured
  between two surfaces.
- **The event stream was not consumed.** The workbench does not read it, by
  decision — `web/src/api/paths.ts` says so.
- **The workbench cannot switch the selected project.** The API has no such
  operation, so there was nothing to drive.
- **No provider was called.** There is no credential in this repository, so
  the run is made against the repository's own fixtures, with no network call
  to a model.
- **The claims were written by the walk**, not by the product (§4.7).
- **The DOCX and the PDF are not byte-reproducible.** Their bytes are
  compared as stored against served, not across two renders. The report's
  reproducible forms are Markdown and HTML.

---

## 7. Where each command is witnessed

| The command | What runs it |
|---|---|
| `uv sync` | [`tests/test_readme_accuracy.py`](../tests/test_readme_accuracy.py) executes it, and asserts `uv.lock` is byte-identical afterwards. The walk runs it in the clone. |
| `uv run pytest` | The same file, reduced to `--collect-only` when it runs from inside the suite. The walk's reviewer mode runs it whole. |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | The same file, executed for real. |
| `uv run labcairn --help` | The same file — it proves the entry point resolves and every command is registered. |
| `pnpm install --frozen-lockfile`, `pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm format:check` | The same file, and the `web-quality` workflow. |
| `labcairn init`, `labcairn doctor`, `labcairn task create`, `labcairn task run`, `labcairn task resume`, `labcairn task status`, `labcairn sources inspect`, `labcairn sources ingest`, `labcairn artifacts list`, `labcairn serve` | The CLI is the authority: `tests/test_readme_accuracy.py::test_the_readme_documents_only_commands_that_exist` runs `labcairn <command> --help` for every one of them the README documents, and the walk runs the ones the path uses. |
| `uv run python scripts/outsider_path.py` | [`tests/test_outsider_path.py`](../tests/test_outsider_path.py) runs the script in the witness mode and reads the report it wrote. |

---

## 8. One gap in this page itself, stated

**Nothing watches that this page's command list and the README's are the
same set.** The two tables in §7 are the authority, and a command on this
page that is in neither would not be caught by anything.

The reason is the file-ownership contract this work order works under: it
does not own `tests/`, so it could not add the witness that would catch it,
and a test file added without a shard entry is a test CI never runs. **The
claim is therefore a procedure rather than a property**, and the procedure
is: *a command added here is added to the README's table and to
`scripts/outsider_path.py`'s table in the same change.* The README's own
table **is** fail-closed in both directions — a command the README shows
that the script does not run fails the walk, and a row in the script's table
that the README does not show fails it too.

**This is a gap for the gate to close**, and it is recorded here rather than
left for the next reader to find.

---

## 9. Where to go next

- **[The threat model](THREAT-MODEL.md)** — what the product protects, from
  what, and the larger half: what it does **not** claim.
- **[The release notes](RELEASE-NOTES.md)** — this alpha's known
  limitations, in one place.
- **[The evaluation protocol](EVALUATION.md)** — the five mandatory gate
  classes and the six Phase 1 blockers this alpha is measured against.
- **[The acceptance record](acceptance/LC-P1-14-outsider-path.md)** — the
  measured run, its command lines, its exit codes and its seconds.
