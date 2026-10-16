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
| LC-P1-08 | P0 | G3 | NOT STARTED | licensing **resolved** — pdfplumber/pdfminer.six (MIT), not PyMuPDF · [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md) |
| LC-P1-09 | P0 | G3 | NOT STARTED | contract pre-decided in [ADR-0004](adr/ADR-0004-scientific-provenance-and-evidence-model.md) |
| LC-P1-10 | P1 | G3 | NOT STARTED | see the priority legend above — still required for G3 |
| LC-P1-11 | P0 | G4 | NOT STARTED | |
| LC-P1-12 | P0 | G4 | NOT STARTED | |
| LC-P1-13 | P0 | G5 | NOT STARTED | |
| LC-P1-14 | P0 | G5 | NOT STARTED | |

**Gate status:** G0, G1 and **G2 closed**. **G3 next** — LC-P1-08, 09, 10. G4–G5 not started.

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

**Build:** `src/` Python package with `pyproject.toml`, `uv.lock`, Python 3.12 CI; `web/` React/TS/Vite project with lockfile; pytest/ruff/mypy, Vitest, GitHub Actions; `.env.example`, `.gitignore`, docs; no credentials or research private data. A FakeProvider and deterministic demo fixtures must run without paid APIs — minimally the value types `Known` / `Unknown` / `UsageValue` / `UnknownReason`, which LC-P1-03 builds real probes and adapters on top of (C-3). README must accurately mark incomplete features. **The initial commit already exists** (`623e3ca`); do not repeat a first-commit step. **Licensing:** add no `LICENSE` file while ownership is uncleared; a placeholder such as `LICENSE.PENDING.md` grants no rights, CI must not fail on its absence, and the README must state the true status — PyMuPDF's AGPL/commercial duality is still an open dependency decision (R-04, R-06). Also land the **binding reference-exclusion checklist** from [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md) exactly as ruled by [`LC-P1-01-approved-amendments.md`](plans/LC-P1-01-approved-amendments.md): packaging via **Hatchling** with `[tool.hatch.build.targets.wheel] packages = ["src/labcairn"]` as an explicit **recursive package root** — never a setuptools leaf list, which was measured to drop every subpackage from the wheel while still reporting success — plus sdist exclusions for `_references*` / `.upstreams*` / `labcairn-upstreams*` and **no `MANIFEST.in`** (C-2); `paths-ignore` on **optional or push-triggered** workflows only, never on a workflow GitHub reports as a required status check, since a filtered required check leaves a pull request permanently unable to merge, while still excluding reference paths from every `upload-artifact` and `cache` `path:` (C-1); a dedicated CI job asserting `git ls-files` contains no reference path; git-mode secret scan (never `--no-git`) with **no broad reference-path allowlist**, so a mistaken `git add -f` remains visible to it (C-4); IDE/indexer `search.exclude` and `files.exclude` with indexer ingestion root restricted to `src/` and `docs/`; and `git archive`/build-artifact-only release archiving. The same work order carries the operating rule that closes what configuration cannot: **verify the repository root resolves to LabCairn before any Git operation, and treat a `git init` rooted anywhere above it as an incident.**

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
