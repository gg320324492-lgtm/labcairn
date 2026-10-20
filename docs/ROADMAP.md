# LabCairn Four-Phase Roadmap

**Version:** LCR-PLAN-1.1  
**Synchronized with:** `LC-P1-v1.1`, the Phase 1 work orders and gates in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md). Phase plan and work orders are revised together; they must never drift apart.
**Status:** Phase 1 in progress; later phases are strategic targets, not approved implementation work orders.

## Current position

**Phase:** P1 — Foundation & MVP · **Gate:** G0, G1, G2 and **G3 closed**; G3's closure rests on an independent review at `d114810` rather than on an owner decision · **G4 is in flight** · see [`handoff/CURRENT.md`](handoff/CURRENT.md) for the authoritative pointer

| | |
|---|---|
| Completed | **LC-P1-00** — upstream source study, three architecture ADRs, pinned reference index. `PASS WITH NOTES`, reviewed at `623e3ca` and merged as PR #1 (`9b445cd`). Those are the **review subject and merge commit**, not the current tip. |
| Accepted and merged | **LC-P1-01 … LC-P1-10** — the engineering baseline (LC-P1-01), the trusted core (02–04, G1), the durable work and its recovery (05–07, G2), and the evidence path (08 material and locators, 09 retrieval and the ledger, 10 bounded analysis and a deterministic figure). **Every work order is `PASS WITH NOTES`**, each with its own acceptance review under [`acceptance/`](acceptance/), and every one of them was reviewed by the party that wrote the fixes — except G3's three, which were also reviewed independently, at `d114810`. |
| Next direction | **G4 is in flight**: **LC-P1-11** (report assembly, export and artefact versioning) and **LC-P1-12** (the Typer CLI and the local FastAPI + React workbench), behind the one application layer they all call. G4's exit test is *"CLI and Web produce same versioned report"*. Three merges of it have landed — T00, the report's document model, ADR-0013, the libraries the report's four exporters will use, and T05, the application layer the three surfaces call — and the three surfaces branch behind them. **G3 is closed**, on the independent review at `d114810`: a reviewer that wrote none of the gate's fixes broke each of the gate's fourteen fixes and **no mutation survived**, verdict **PASS WITH NOTES** ([gate review](acceptance/G3-acceptance.md)). No decision stands between the two gates. |

**Open issues carried forward** (full table with owners in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md)):

- Copyright ownership is unresolved and the repository deliberately has **no `LICENSE` file**. No open-source rights have been granted.
- **PyMuPDF was avoided**: [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md) chose pdfplumber and pdfminer.six, both MIT, over PyMuPDF, whose AGPL branch would have constrained a future MIT release.
- Reference isolation **is now enforced on `main`** since `89c16d4`: `tests/test_no_reference_leakage.py` (99 tests) and `reference-exclusion` as a required status check. It was prose until LC-P1-01 merged.
- The five upstream pin SHAs were **verified present on GitHub at LC-P1-00 review time**. The standing risk is upstream force-push or garbage collection, which no local practice prevents; re-verify with `git ls-remote <url>` before relying on a pin.
- **The fabricated-DOI half of LC-P1-09's clause is still unimplemented**, and the gap is structural: the ledger holds no external identifier for a source, so a report can only cite locators unless G4 changes that.
- **G1's and G2's work orders still have no independent review.** The reviews that found their defects and the fixes that answered them were the same party in every case, and the board's rule — a row is marked done only when an independent review at a named commit says so — is unsatisfied for them. G3's three have one now, at `d114810`, and the decision of 2026-10-18 that let LC-P1-08 proceed to LC-P1-09 without one was superseded on 2026-10-20, when the owner decided that the gate closes **after** an independent review rather than instead of one.
- **The exit demonstrations of G1 and G2 are run by nothing**: no test and no CI job, so they can rot without anyone noticing. LC-P1-10's demonstration is covered by a test, and the independent review confirmed that the earlier three had not rotted — 36 / 14 / 18 checks, exit 0, at `d114810` — though nothing runs them, so they still can.
- **matplotlib's bundled fonts bring a licence obligation** that the root licence line does not cover, and G5's audit has to cover the fonts rather than the root line.

**What is not yet true of this project:** `main` now holds a research workspace's **spine** — versioned contracts, a permission boundary, a durable task store with crash recovery, material ingestion with locators, a lexical index and an evidence ledger, bounded statistics with a deterministic figure, and a reproducibility manifest — **and the beginning of its surfaces**: the report's document model, the report artefact manifest that lists what a report is made of, and the one application layer that the CLI, the local API and the web UI all call. The Typer CLI and the local FastAPI service are landing, and the React workbench and the end-to-end smoke path are behind them. **A person still cannot run a research task end to end from an interface** — that is the smoke path's demonstration, and it is the last piece of G4, which is the first work in Phase 1 that is about the person using the tool rather than about the tool's internals.

| Phase | Focus | Exit gate |
|---|---|---|
| P1 — Foundation & MVP | Standalone local-first Agent, typed tools, task/resume, evidence anchors, bounded analysis with a deterministic scientific plot, a first-party research Skill, report delivery, CLI + local Web | Fresh external install and end-to-end evidence-backed task, with security/recovery/quality tests |
| P2 — Scientific Intelligence | Better retrieval, citation identity/support, advanced analysis sandbox, higher-fidelity scientific plots, editing, expanded research Skills, conditional reviewers/subagents | Measured capability gain against a frozen P1 baseline, no scientific-claim inflation |
| P3 — Production & Ecosystem | Stronger isolation, packaging, plugin/MCP trust, Windows/macOS/Linux distribution, robustness, observability, docs, benchmark expansion | Secure, maintainable, multi-platform public release and documented operational limits |
| P4 — Continuous Improvement | User feedback, targeted refinements, provider/format coverage, incremental UX/performance improvements | Small reviewable releases with regression tests and clear changelogs |

Phase 2 items listed against scientific plots and research Skills are **upgrades** of Phase 1 capabilities, not their first delivery. Phase 1 **will deliver** a deterministic plot (`LC-P1-10`) and a first-party `research-report` Skill (`LC-P1-07`) — both are `NOT STARTED` on the status board; Phase 2 raises their fidelity and breadth.

## Phase 1 upstream research

**LC-P1-00** is a new lightweight prerequisite and continuing reference task: establish separate local clones of selected top Agent/scientific-Agent repositories, record precise SHAs and license context, and use ADRs/tests to justify architecture choices. Do not vendor/reference-clone entire repositories inside the public repo. See [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md). P1 now contains **15 work orders (00–14)**, with G0 for reference setup before the original G1–G5 gates.

## Review protocol

1. Complete all work orders and exit gates for the current phase. Internal commits and PRs may be used during the phase.
2. Push a verifiable GitHub commit SHA or PR, plus actual test results and demonstration evidence.
3. Independent reviewer examines source, contracts, tests, security and demonstration; statuses: PASS / PASS WITH NOTES / BLOCKED / FAIL.
4. Fix blocking findings before phase close. Only then issue the *next phase's detailed* work orders based on implemented reality.

**Hard principle:** Phase 2/3 features do not excuse failure of Phase 1 boundaries; security and evaluation start in Phase 1 and mature thereafter.
