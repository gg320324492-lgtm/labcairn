# Phase 1 — Foundation & MVP / Complete Work Orders

**Plan ID:** LC-P1-v1.1  
**Release target:** `v0.1.0-alpha` once acceptance passes, not before.  
**Gate:** all listed work orders + evaluation + clean-room onboarding acceptance.  
**Scope:** one public standalone repository; no MicroBubble runtime dependency.

**Priority legend:**

| Priority | Meaning |
|---|---|
| **P0** | Gate-blocking. The work order must be complete before its gate may be declared passed. A gate with an incomplete P0 cannot be released. |
| **P1** | Must still be completed within Phase 1, but may be sequenced after all P0 items of the same block are ready, and carries lower delivery risk. It is **not** optional and **not** deferrable to a later phase; the Phase 1 deliverable above requires it. |

P0/P1 expresses ordering and risk inside Phase 1. It does not mean "required / optional", and it never overrides a gate exit test: where a gate names a capability, that capability must exist and pass regardless of its priority label.

## Phase 1 status board

**This board is the completion record.** It is updated in the same commit that changes a work order's state, and every non-`NOT STARTED` row cites the commit or report that is the evidence. A row is never marked done because something looks finished — it is marked done when an independent review at a named commit says so.

Status vocabulary: `NOT STARTED` · `IN PROGRESS` · `PASS` · `PASS WITH NOTES` · `BLOCKED` · `FAIL`

| Work order | Pri | Gate | Status | Evidence |
|---|---|---|---|---|
| LC-P1-00 | P0 | G0 | **PASS WITH NOTES** | `623e3ca` · [review](acceptance/LC-P1-00-review-623e3ca.md) · [re-review](acceptance/PR-1-independent-review.md) · [evidence](acceptance/LC-P1-00-evidence.md) |
| LC-P1-01 | P0 | G1 | **PASS WITH NOTES** | reviewed at `c23ef775` · [PR #2](https://github.com/gg320324492-lgtm/labcairn/pull/2) [review comment](https://github.com/gg320324492-lgtm/labcairn/pull/2#issuecomment-6191612033) · **merged to `main` at `89c16d4`** · [evidence](acceptance/LC-P1-01-evidence.md) |
| LC-P1-02 | P0 | G1 | **PASS** | merged `a79181b` · [G1 evidence](acceptance/G1-evidence.md) |
| LC-P1-03 | P0 | G1 | **PASS WITH NOTES** | merged `a79181b`, smoke fix `b237751` · real smoke run against a live Anthropic-protocol endpoint: `tool_calls` ok, `usage_reporting` ok, structured output **inconclusive** (client-layer, not endpoint) · [ADR-0002](adr/ADR-0002-model-and-tool-execution-boundary.md), [ADR-0006](adr/ADR-0006-capability-namespaces.md) |
| LC-P1-04 | P0 | G1 | **PASS** | merged `a79181b` · case-bypass blocker found by cross-review and fixed · [ADR-0003](adr/ADR-0003-event-and-permission-model.md) |
| LC-P1-05 | P0 | G2 | **PASS WITH NOTES** | merged `917f844` · [acceptance](acceptance/G2-acceptance.md) |
| LC-P1-06 | P0 | G2 | **PASS WITH NOTES** | merged `3c2269e` · three crash points injected; no blind replay · [acceptance](acceptance/G2-acceptance.md) |
| LC-P1-07 | P0 | G2 | **PASS WITH NOTES** | merged `a6c6671` · forged-input and placeholder tests · [acceptance](acceptance/G2-acceptance.md) |
| LC-P1-08 | P0 | G3 | **PASS WITH NOTES** | schema + [ADR-0009](adr/ADR-0009-material-and-extracted-text-storage.md) merged (`3f70d58`) · locator-key and extraction-version derivations, the **text / Markdown / CSV / XLSX / PDF adapters** and the ingest pipeline merged · **workspace walk merged**: the whole path (walk → read → extract → disclose → store) now runs through `SourceMaterial`, so the permission boundary applies to ingestion and a denied subtree is invisible to it · **permission boundary closed**: PR #29 (`729a84a`) and [ADR-0011](adr/ADR-0011-canonical-policy-matching.md), ratified in PR #30 (`de28b42`) · **acceptance review done — [LC-P1-08 acceptance](acceptance/LC-P1-08-acceptance.md), verdict PASS WITH NOTES**: eight defects found and fixed, all of the same family — a docstring or ADR asserting a boundary the code did not enforce. A two-column PDF stored text the author never wrote and marked it citable; `UNREADABLE_NO_OCR` was a dead state, so a scanned PDF came out `readable`; PDF page anchors were unbound to content (rotating every page's text left all 26 PDF tests green); CSV row locators counted records rather than physical rows; and `ingest_into_store` could not be called twice on an edited file. **Two-column gap decided by the owner — detect and refuse**, not record-only: a page reading as two columns is refused and disclosed rather than spliced, with thresholds bracketed by measurement against the three real fixture papers in both directions. **Remaining:** none the owner considers blocking. The review that produced these findings and the fixes that answered them are the same party, so this board's rule -- a row is marked done only when an **independent** review at a named commit says so -- was **not discharged**. The owner decided on 2026-10-18 to proceed to LC-P1-09 without it, and that is recorded here as a decision rather than dressed up as a review. What the accepting reviewer would still want to look at is the two-column detector's 35% threshold, which is bracketed against single-column fixtures rather than calibrated against two-column ones |
| LC-P1-09 | P0 | G3 | **PASS WITH NOTES** | merged `a7a2f48` (PR #44) · [acceptance review](acceptance/LC-P1-09-acceptance.md) — all ten subtasks merged; three review findings fixed (a query the index cannot serve was reported as a miss; the miss message claimed more than a lexical search establishes; `superseded_by` was a column nothing ever wrote); **two clauses of the acceptance are not discharged** — the *fabricated DOI* half has no implementation and the gap is structural (no record can carry an identifier, nothing resolves one, ingestion records none), and *source provenance through report generation* is LC-P1-11's. The review and the fixes are the same party, so this board's rule — a row is marked done only when an **independent** review at a named commit says so — is **not discharged**; LC-P1-09 still needs a review by someone who did not write the fixes |
| LC-P1-10 | P1 | G3 | **PASS WITH NOTES** | **[acceptance review](acceptance/LC-P1-10-acceptance.md)** — all eleven subtasks merged; three findings the review made were closed before the verdict (a unit check that passed vacuously, four properties no test observed, and a caption drawn across the axis tick labels); two limits recorded rather than closed (the manifest names **no version for the renderer**, and the aggregate's numbers are not re-checked by C1, C2 or C3); and the review is **not independent** — the same party specified, dispatched and reviewed the work. — **[task breakdown written](plans/LC-P1-10-task-breakdown.md)** — eleven subtasks (T00–T10) with a file-ownership map; the work order's five acceptance clauses and the ADR-0004 conditions it touches each mapped to the subtask and test that carries them. **T00–T10 merged**, the acceptance review outstanding. T04, T05, T06 and T08's entries are recorded here rather than in their own pull requests, which shipped their code without them. T02: the **operator contract** — the id grammar, the one reference spelling, and the closed argument model; the catalogue that holds the shipped operators lands with the operators, because it has to be built from their own id constants for the same reason `evidence/catalog.py` is. T03: the **selection** — which columns, which rows, and what to do about the cells that cannot be used — and the **quantity reader moved to `sources/quantity.py`**, so the ledger and the analysis cannot disagree about what a number is (C3's own tests pass unmodified). T00: the dependency decision — `matplotlib>=3.9,<4` (locked at 3.11.2), decided in [ADR-0012](adr/ADR-0012-chart-rendering-library.md), whose licence was read from the distribution's own `LICENSE` file and not from package metadata, and whose determinism requirement was **measured** — fixing `svg.hashsalt` alone is not enough, because matplotlib writes a creation date into the SVG metadata, and the salt governs *cross-process* stability while the date governs *within-process* stability. T01: the **fixture corpus** — the repository held no CSV and no XLSX file at all, so the "controlled fixtures" the acceptance clause names are a deliverable of this work order rather than an input to it; the corpus is eight committed CSVs with hand-written expected values beside them and a test that recomputes those values with Python's `statistics` — an implementation that is not LabCairn's — so the expectation cannot share a bug with the code the operators will be written against. T04: the **descriptive operators** and the **catalogue that holds them** — count, sum, min, max, mean, median and stdev, with the catalogue built from the operators' own id constants for the same reason `evidence/catalog.py` is, so **one id has one spelling** and a run can only name an operator this build implements; and the **unit rule**, compared as written and never converted, whose known false negative is stated rather than hidden (`kilograms` and `kg` are one unit spelled two ways, and a selection holding both is refused, naming both tokens). T05: the **grouped aggregate** — one vetted statistic per group, returning a **table** rather than a number, because there is no "the grouped mean" of three groups; the statistic is **composed** from a registered operator rather than reimplemented, so the grouped mean and the scalar mean cannot drift apart, and an aggregate that names no registered operator is a refusal rather than a guess; the aggregate's unit is checked **per group** and not across the selection; a group with no quantity has **no statistic** (never zero) and its reason names **that group** rather than the selection; and the group key is the cell's text **as written**, so the empty key is a group while a cell that was never recorded is not — for a spreadsheet those are the same observation, and inventing a key would be inventing a group. T06: the **chart recipe** — a figure's editable source is a JSON document of exactly **three** parts (data, encoding, output) with no script beside it and no way to run one, which is what makes the work order's *"Explicitly no general-purpose model-authored code execution"* **satisfiable rather than aspirational**; the figure's numbers are a **vetted operator's output** and not a second reading of the file, and the parameters are checked by **the operator's own argument model**, so the question "which parameters does this operator accept?" has exactly one answer; and the **caption and the interpretation are separate fields**, because ADR-0004 A10 holds that an interpretation is never machine-verified, so the marker that says so is the **renderer's** job and cannot be left out by forgetting. T08: the **manifest** — a computed number is a statement about a **derivation**, and what makes it checkable is not a check but the document: the input file's hash, the selection, the operator and its version, the parameters, the recipe and the output's hash, which are the **six fields** the work order names; the manifest is the document and the receipt is the record that points at it; and **one hash lineage** — the manifest's input hash, the selection's `content_sha256`, the source's `content_sha256` and the file's bytes are the same value, and the builder refuses to produce a manifest in which they are not, so no **third** implementation of that hash is added to the two the repository already had. T09: the **run path** — from a granted `analysis.run` to a recorded artefact: the path is admitted into the named source root, the selection is built, the source is resolved (the ledger's row, the file's bytes, the source's readability), the operator is evaluated, the environment is prepared, the manifest is written, the figure is rendered, and the receipts are recorded. **The consent is the existing machinery and is not optional** — the digest is recomputed at the moment of use over the capability's canonical arguments, so an approval to analyse one selection does not authorise another, and the approval's source binding is re-hashed, so a file that has drifted since is a refusal; every refusal is one type with a machine-readable reason and a message that names what is wrong, and a refusal **before** the consent point does not spend the approval. The bounds are the enforceable ones — a row limit and a cell-count limit, checked **before** a cell is read — and the one that cannot be enforced (a wall-clock timeout on an in-process loop) is named in `UNENFORCED_LIMITS` rather than shipped. T07: the **deterministic renderer** — a figure is drawn from the recipe and from the operator's result object, so the numbers plotted **are** the operator's numbers; the chart operator that does the drawing is a **catalogue entry**, so "a vetted chart operator renders" is code rather than convention, and `render()` returning `None` means only "this result is not a figure" while everything else is a **refusal** that names the fault. The determinism controls were **demonstrated, not asserted**: the SVG's creation date and its salt each shown to matter, PNG shown to need **neither**, and a hostile ambient `matplotlibrc` shown unable to change the bytes; the `rcParams` come from a **declared, hashed** defaults file, and the renderer's declared drawing parameters are published as constants the manifest's environment does **not** carry (the breakdown's §5 records that as something this work order does not deliver). T10: the **exit demonstration** — `examples/analysis_demo.py`, in the shape of `examples/g2_exit_demo.py`: a controlled CSV is ingested, a grouped aggregate runs and prints the value **and the cells it came from**, a figure is drawn from the recipe, the manifest prints its six fields and both hashes, the figure is rendered twice and the bytes compared, and then the **input file is changed** and the repository's own machinery says so — the material's checkpoint no longer verifies, the figure and the manifest are marked `STALE` with the reason, a run over the new bytes is refused, and the figure on disk is unchanged. The **recipe is committed** and the run's arguments are read out of it, so the recipe and the run cannot disagree; and the demonstration is run by a test, because the earlier exit demonstrations are run by nothing and rot quietly. Four owner decisions recorded: units are compared as written and **never converted** (C3's discipline, inherited); the figure's editable source is a **declarative chart recipe** with no code-execution surface; the determinism claim is **byte-identity inside one recorded environment**; and an aggregate is an **artifact, not a ledger record** — refused structurally, because `source_anchors.locator_key` is CHECK-constrained to the four extractable kinds and `render_locator_key` raises for `COMPUTATION`. **No schema migration is needed**: `ArtifactReceipt` already reserves `FIGURE`, `MANIFEST` and `ANALYSIS_OPERATOR`, the `artifacts` table exists, and `ComputationLocator` was written for this work order. The corpus pinned the second half of the format asymmetry too: **the two formats disagree about what an empty cell is** — CSV emits a row for one, XLSX emits none — so **the number of blanks the author left is not recoverable from the ledger for a spreadsheet** — a cell that holds nothing and a cell that was never there are the same observation, and a range that overshoots the table cannot be told apart from a range full of blanks |
| LC-P1-11 | P0 | G4 | NOT STARTED | **[task breakdown written](plans/LC-P1-11-12-task-breakdown.md)** — the report's document model, four renderers (Markdown, HTML, DOCX, PDF) over one model, the report artefact manifest, the revisions, the content checks, and the smoke path; **the four decisions in §1.4 were taken by the owner on 2026-10-20** — a report cites locators only, the CLI and the API serve the same bytes, the report's reproducible form is Markdown and HTML, and the local API refuses a foreign origin and requires a token The implementation has not started; the breakdown is the plan, and G4 opens when the owner closes G3 |
| LC-P1-12 | P0 | G4 | NOT STARTED | **[task breakdown written](plans/LC-P1-11-12-task-breakdown.md)** — one application layer that the CLI, the local API and the web UI all call, the Typer CLI, the FastAPI service on 127.0.0.1 with the origin and session guards, and the React workbench; the breakdown names what does not exist yet and has to be built — there is no `cli/` module, no `api/` module, the web package is a placeholder skeleton, and the store has **no list query** for tasks, runs, stages or artefacts, which all three surfaces need. The implementation has not started; the breakdown is the plan, and G4 opens when the owner closes G3 |
| LC-P1-13 | P0 | G5 | NOT STARTED | |
| LC-P1-14 | P0 | G5 | NOT STARTED | |

**Gate status:** G0, G1 and **G2 closed**. **G3 — the exit test is met and the [gate review](acceptance/G3-acceptance.md) recommends closure; the owner's decision is outstanding**: LC-P1-08 accepted with notes by owner decision, LC-P1-09 and LC-P1-10 both reviewed and **PASS WITH NOTES**. G4–G5 not started. The board's rule — a row is marked done only when an **independent** review at a named commit says so — is not satisfied for any of G3's three work orders, so the closure is the owner's decision and not this document's.

G2 closed with notes, all carried rather than dropped: the concurrency *behaviour* tests pass with `BEGIN IMMEDIATE` downgraded, so the SQL assertion is the load-bearing element rather than the behaviour suite; three of LC-P1-07's four placeholder conditions are textual heuristics; and `ArtifactLedger` is in memory. Full list in the acceptance document.

G1 was accepted with three limitations recorded rather than closed silently: structured-output capability is **unmeasured** (both probes fail in pydantic-ai's client layer before a request is sent, so they say nothing about the endpoint); `ApprovalLedger.consume()` does not resolve the capability against the registry, which is a defence-in-depth gap whose ordering constraint belongs in an ADR; and path-guard tests ran on Windows only, leaving POSIX ADS and case semantics unverified.

A work order being accepted is not a gate being closed. G1 closes when all four of its work orders are accepted.

**Verification basis for Phase 1 onwards.** Verification basis: internal double review — the implementing agent and a reviewer who was not the implementer. This is **not** an external independent audit. Branch protection was read by an admin-capable session belonging to the **implementing agent**, so the six required checks are implementer-confirmed, not independently proven.

**Carried open issues** — not owned by any single work order, each needs a decision before it can be closed:

| Issue | Owner work order | Note |
|---|---|---|
| Copyright ownership / no `LICENSE` file | LC-P1-14 (release) | A placeholder such as `LICENSE.PENDING.md` grants no rights. Blocks any claim of open-source licensing. |
| ~~PyMuPDF AGPL vs commercial~~ | LC-P1-08 | **RESOLVED** — [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md): LC-P1-08 uses pdfplumber + pdfminer.six (MIT). PyMuPDF's AGPL branch would have constrained the project's own MIT release, and the commercial branch cannot be contracted while copyright ownership is unsettled. Nothing needed undoing — ADR-0004's locator contract was already independent of PyMuPDF, and no PDF dependency was ever added. |
| ~~`tests/test_no_reference_leakage.py` absent~~ | LC-P1-01 | **RESOLVED** — merged to `main` at `89c16d4`: the file exists with 99 tests and `reference-exclusion` is a required status check. LC-P1-00's acceptance item can drop this caveat now that LC-P1-01 is accepted and merged. |
| Upstream pin SHAs were obtained locally | LC-P1-00 (recurring) | Shallow single-branch clones read the SHA from the local object store, so a fresh `git clone` does not reproduce it. **All five were verified present on GitHub at LC-P1-00 review time**; the standing risk is upstream force-push or GC, which no local practice prevents. Re-verify with `git ls-remote` before relying on a pin. |
| ADR length vs "concise" | — | Disputed and deliberately unresolved; ~1,270 lines across three ADRs. |

## P1 deliverable

An unrelated researcher installs LabCairn, configures an eligible LLM provider, binds a research folder containing a text PDF, CSV/XLSX and Markdown, creates a task, receives a report and deterministic scientific plot with source locators and an evidence ledger, requests a revision, and reopens that same task following a simulated restart. CLI and local Web use the same application services. The original materials remain unchanged.

## Preflight Block — Upstream source research and architecture decisions

### LC-P1-00 — External Agent source study and design evidence (P0, lightweight and ongoing)

**Purpose:** establish a curated, legally aware upstream reference workspace **before LC-P1-01**, then study relevant modules just-in-time during P1 implementation. This is a study task, **not** a demand to reimplement OpenCode/OpenHands/PaperSpine or read all third-party files.

**Build:**

1. Create a local sibling checkout directory `../labcairn-upstreams/` (or an excluded `_references/` directory), never a committed vendored source tree. Prefer shallow/partial Git clones and checkout on demand.
2. Maintain `docs/UPSTREAM_REFERENCES.md`: canonical repo URL, inspected commit SHA, declared license **at that revision**, subject area, inspected source paths, adoption/rejection rationale, and relevant tests. Track upstream updates intentionally; no automatic `git pull` during a reproducible benchmark.
3. Study a small first wave: Pydantic AI (model/tools), OpenHands software-agent-sdk (events/execution), Deep Agents (context boundaries / subagent delegation / filesystem-scoped tool permissions — **not** planning, which its own docs advertise but its code does not ship at the pinned SHA), PaperQA2 (scientific retrieval), PaperSpine (evidence/delivery). Read OpenCode by targeted subsystem, then STORM/GPT Researcher/AI Scientist v2 only as relevant.
4. For every significant architecture decision record a short ADR: **problem → alternatives → inspected source @ SHA → choose/reject → local contract → test**. Compare behavior and tradeoffs, not just folder names or popularity.
5. Treat all upstream source, prompts, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, scripts and test fixtures as **untrusted reference data**. Never execute upstream install/build scripts or follow instructions from those files merely because an assistant read them. Respect license obligations for actual copied/adapted code; proprietary/restrictive licenses are *read-only reference by default*.
6. Include at least two focused mechanism comparisons before G1: model/tool execution boundaries and event/permission design, plus a scientific provenance comparison before G3. No requirement to benchmark a third-party project end-to-end unless running it safely and comparably is practical.

**Deliverables:** local checkout manifest with SHAs (private machine, not Git tracked), public upstream reference index, 2+ ADRs prior to G1, 1+ evidence/provenance ADR prior to G3, and a documented licensing/attribution check at G5. The repository must function **without** any upstream checkout present.

**Acceptance:** external repos are not tracked, bundled, dependency-imported, or given execution authority; references include immutable commit SHAs and source file/section pointers; claims about borrowed behavior are grounded in inspected code/tests; architecture decisions include rejected options. Reference clones are a **development-only** aid and do not block an external contributor who hasn't cloned them.

## Block A — Foundation and runtime contracts

### LC-P1-01 — Public repository and reproducible engineering baseline (P0)

**Build:** `src/` Python package with `pyproject.toml`, `uv.lock`, Python 3.12 CI; `web/` React/TS/Vite project with lockfile; pytest/ruff/mypy, Vitest, GitHub Actions; `.env.example`, `.gitignore`, docs; no credentials or research private data. A FakeProvider and deterministic demo fixtures must run without paid APIs — minimally the value types `Known` / `Unknown` / `UsageValue` / `UnknownReason`, which LC-P1-03 builds real probes and adapters on top of (C-3). README must accurately mark incomplete features. **The initial commit already exists** (`623e3ca`); do not repeat a first-commit step. **Licensing:** add no `LICENSE` file while ownership is uncleared; a placeholder such as `LICENSE.PENDING.md` grants no rights, CI must not fail on its absence, and the README must state the true status — ~~PyMuPDF's AGPL/commercial duality is still an open dependency decision (R-04, R-06)~~ **RESOLVED** by [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md), which selects pdfplumber + pdfminer.six (MIT); copyright ownership and the no-`LICENSE`-file rule above are unaffected and still in force. Also land the **binding reference-exclusion checklist** from [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md) exactly as ruled by [`LC-P1-01-approved-amendments.md`](plans/LC-P1-01-approved-amendments.md): packaging via **Hatchling** with `[tool.hatch.build.targets.wheel] packages = ["src/labcairn"]` as an explicit **recursive package root** — never a setuptools leaf list, which was measured to drop every subpackage from the wheel while still reporting success — plus sdist exclusions for `_references*` / `.upstreams*` / `labcairn-upstreams*` and **no `MANIFEST.in`** (C-2); `paths-ignore` on **optional or push-triggered** workflows only, never on a workflow GitHub reports as a required status check, since a filtered required check leaves a pull request permanently unable to merge, while still excluding reference paths from every `upload-artifact` and `cache` `path:` (C-1); a dedicated CI job asserting `git ls-files` contains no reference path; git-mode secret scan (never `--no-git`) with **no broad reference-path allowlist**, so a mistaken `git add -f` remains visible to it (C-4); IDE/indexer `search.exclude` and `files.exclude` with indexer ingestion root restricted to `src/` and `docs/`; and `git archive`/build-artifact-only release archiving. The same work order carries the operating rule that closes what configuration cannot: **verify the repository root resolves to LabCairn before any Git operation, and treat a `git init` rooted anywhere above it as an incident.**

**Acceptance:** fresh clone and documented setup on CI-supported OS — Python lint/type/test on **Ubuntu and Windows**, Web initially on Ubuntu, which is explicitly *not* a real Windows application smoke test (C-6); lint/type/test pass; quick-start does not claim unimplemented commands; secret scan and lockfile consistency check included. Real Windows smoke later in Phase 1. Reference exclusion is **verified, not asserted**: `tests/test_no_reference_leakage.py` exists and passes, checking that both `git ls-files` and the member names of the built sdist and wheel contain no reference path, and the CI job asserting this **runs unconditionally on every pull request** — it is a required check and must not be made conditional by `paths-ignore` (C-1). The README must not imply that any license has been granted while none has.

### LC-P1-02 — Versioned contracts and module boundaries (P0)

**Build:** Pydantic models/schemas for `Task`, `Run`, `Stage`, `Operation`, `Approval`, `Source`, `SourceAnchor`, `EvidenceRecord`, `ArtifactReceipt`, `Checkpoint`, and stream/event envelopes. Stable IDs and schema versions. Document ADR covering decision to use Pydantic AI but app-owned task/evidence authority.

**Acceptance:** JSON round-trip and schema incompatibility tests; malformed payloads rejected; no API/CLI direct DB model coupling; Task/Run separation explicit.

### LC-P1-03 — Model providers, budgets and truthful capability detection (P0)

**Build:** Pydantic AI provider integration with at least OpenAI and Anthropic protocols and one OpenAI-compatible custom endpoint mode; FakeProvider for tests; environment/config-file credentials; tool-use and structured-output capability checks; per-run tool/turn/time/token/cost ceilings, including unsupported usage fields reported as unknown, not zero.

**Acceptance:** real smoke on at least one provider, fake tests across capabilities; safe failure on unsupported tool calling, stop/cancel/timeout, no API keys/excerpts in logs, clear outbound-material disclosure policy.

### LC-P1-04 — Workspace/tool permission boundary (P0)

**Build:** explicit allowed roots; read-only source materials; separate task output; path normalization, symlink/junction traversal guard, atomic output writes where feasible, resource-scoped `allow / ask / deny`, approvals bound to canonical arguments digest and task ID. Distinguish local-only analysis tools and outbound model requests. Imported text never grants permissions.

**Acceptance:** traversal, encoded/absolute path, symlink and permission-bypass negative tests; no silent network transmission; no arbitrary shell/Python tool in P1. No irreversible change to supplied source data.

## Block B — Tasks, recovery and controlled workflow

### LC-P1-05 — SQLite task store and transactional events (P0)

**Build:** SQLAlchemy/Alembic migrations, SQLite task/run/stage/event/operation/approval/checkpoint/artifact tables, unique event sequence, transactionally coupled event/state transitions; snapshots. User-level identity and future multiuser scope explicit, though Phase 1 is local single user.

**Acceptance:** migration rerun and fresh DB tests, event order, rollback-on-failure, race handling; same-task stable identity across restarts.

### LC-P1-06 — Checkpoint, operation reconciliation and revision (P0)

**Build:** stage-boundary checkpoints, material hashes, artifact hashes, task revision ID, run attempts, uncertainty states on crashed side effects; reconcile before replay, resume from last verified stage. Scoped pause/stop/resume.

**Acceptance:** injected crash before write, after write before commit and after commit before UI receipt; no blind replay; changed source invalidates downstream artifacts; no reuse of expired approval.

### LC-P1-07 — Minimal research workflow and Skill contract (P0)

**Build:** one declared first-party `research-report` Skill/flow with stages `intake → inventory → retrieve → evidence → propose → [user approval for important scientific direction] → draft → validate → deliver`, typed inputs/outputs/dependencies. The approval checkpoint sits between `propose` and `draft` and is required for important scientific direction and major goal/claim changes. A plan is a task artifact, not a new authoritative store. Clear budget and graceful blocking semantics.

**Acceptance:** every stage consumes actual previous artifacts; no empty placeholder passes; blocked user decision awaits approval; limited retries on no progress; user cancels without losing previous valid work.

## Block C — Evidence-aware scientific capabilities

### LC-P1-08 — Material inventory and source locators (P0)

**Build:** ingestion from text PDFs (pdfplumber/pdfminer.six, page and span — see [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md) for why not the originally named PyMuPDF), MD/TXT (line/section), CSV (row/column), XLSX (sheet+cell); file metadata, bytes/hash, warnings. Detect scanned PDF and disclose OCR not yet available; distinguish unreadable assets from no results. Keep source paths workspace-relative when exported.

**Acceptance:** fixtures validate page, row, column and spreadsheet cell anchors exactly; unreadable, empty, duplicate and modified files handled without fabrication.

### LC-P1-09 — Local retrieval and evidence ledger (P0)

**Build:** SQLite FTS5 lexical index over normalized source excerpts and structured table segments; source-specific locators; claim/numeric/result records linked to sources with verification states `planned/extracted/verified_by_rule/user_attested/conflicted/unsupported`; cite-support validator distinguishing source existence, quotation match, numerical consistency and scientific interpretation.

**Acceptance:** ground-truth queries identify correct excerpts; fabricated DOI/source, wrong locator, missing evidence and conflicting numbers do not pass final evidence gate; source provenance preserved through report generation.

### LC-P1-10 — Bounded scientific analysis and plots (P1)

**Build:** typed *vetted* analysis operations (descriptive statistics, grouped aggregates, charts) on consented CSV/XLSX; reproducibility manifest (input file hash, selection, operator version, parameters, script/recipe, output hash); deterministic Matplotlib figure with editable source. Explicitly no general-purpose model-authored code execution.

**Acceptance:** numerics recalculated from source with controlled fixtures; dimensions/units checked; charts match data and captions; missing/invalid data reported, not silently imputed. Deterministic output on identical inputs as applicable.

## Block D — Deliverable surfaces

### LC-P1-11 — Report assembly, export and artifact versioning (P0)

**Build:** Markdown/HTML preview + basic editable DOCX and PDF, evidence citations and stable artifact manifest; linked chart/data notes; content verification separate from formatting/rendering. Revisions keep v1 and generate v2 without altering originals. Limit first-pass report format and explicitly say not journal-ready.

**Acceptance:** exports are openable; numeric values agree with ledger, figures/captions intact, links resolve, output hash/lineage retained. Rerendering after material change invalidates stale output.

### LC-P1-12 — CLI and local Web research workbench (P0)

**Build:** Typer CLI for `init`, `doctor`, `task create/run/status/resume`, `sources inspect`, `artifacts list`; FastAPI localhost API with CSRF/origin/session guard and event stream; React UI for project selection, plan/steps, pending approval, source anchors, evidence status, artifacts/preview and revisions. CLI/API/UI call same application layer.

**Acceptance:** clean clone developer launch with working smoke path; Web refresh recovers DB snapshot, no repeated operation; request approval cannot be spoofed from another origin; CLI and UI show identical Task state.

## Block E — Verifiable quality and public alpha

### LC-P1-13 — Evaluation, fault injection and competitor baseline (P0)

**Build:** at least 3 publicly shareable fixture scenarios with actual answer/source locators and a negative/no-evidence scenario; deterministic fake-provider e2e plus one real provider integration smoke; security injection tests; metrics for source validity, numeric exactness, unsupported claim detection, task completion, crash replay, usage and latency. Compare at least one scoped baseline (e.g. model without evidence workflow), same materials/model/budget. External competitor comparison may be deferred if not reproducible.

**Acceptance:** transparent denominators, scores and failure cases; no invented superiority, no skipped blocking tests; forced-restart task continuation demonstrated; no unsafe file/network permissions.

### LC-P1-14 — Public alpha handoff and review dossier (P0)

**Build:** English and Chinese README, quickstart, example task, architecture docs, threat model, license/NOTICE audit, contribution guide, CHANGELOG, release notes with known limitations, dependency/security checks, GitHub Actions. Prefer a working repository-first install over pretending a polished installer exists. Screen recording or screenshots of real CLI + Web workflow.

**Acceptance:** an external reviewer can start fresh using docs and reproduce the canonical task with own provider, or deterministic fixture without provider; `uv run` and `pnpm` commands documented and actually tested; artifact examples real; commit SHA and CI URLs attached.

## Milestones and dependency order

| Gate | Work orders | Exit test |
|---|---|---|
| G0 — Upstream study setup | 00 | curated checkout strategy, source/commit/license index, initial ADRs; no vendored dependencies |
| G1 — Trusted core | 01–04 | fake provider, typed tools, safe workspace; >=2 architecture comparison ADRs |
| G2 — Durable work | 05–07 | persistent task, stage plan, injected restart |
| G3 — Evidence path | 08–10 | correct source/cell locators, ledger, deterministic plot; evidence design ADR |
| G4 — Usable application | 11–12 | CLI and Web produce same versioned report |
| G5 — Public alpha | 13–14 | outsider fresh install, 3 fixtures, fault injection, docs and real-provider smoke |

Tests and security reviews run continuously, not only at G5. All gates must pass before claiming Phase 1 complete. Optional enhancements must not displace P0 blockers.

## Out of scope for P1

- Full autonomous experiment planning/execution, generalized arbitrary code/shell execution, browser control and scientific hypothesis validation.
- Full OpenHands/Deep Agents/PaperSpine runtime embedding; permanent vector database stack; multiuser server/SaaS; distributed workers; universal local-model offline guarantees.
- Full journal-ready manuscript typesetting, sophisticated mechanism illustration and independent multi-reviewer swarm.
- Native Windows/macOS/Linux packaged desktop installers and an update service.

## GitHub handoff checklist (end of phase)

- Exact repo URL and PR or immutable commit SHA.
- `docs/UPSTREAM_REFERENCES.md` with selected upstream commit SHAs/decision records; explicit declaration that upstream copies were not committed, and any required code attribution.
- Work-order checklist with implementation pointers and deviations.
- CI run links, test counts, command logs and environment versions; real provider/version disclosed without keys.
- Sanitized test fixtures, baseline results and actual artifact outputs/hashes.
- Real app screenshots/demo and exact reproduce steps.
- List of unverified claims/known limitations/license notices.

Review outcome is one of `PASS`, `PASS WITH NOTES`, `BLOCKED`, `FAIL`, with per-work-order findings. Detailed P2 tasks will be authored **after** reviewing implementation and its measured results.
