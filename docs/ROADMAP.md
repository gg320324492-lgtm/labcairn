# LabCairn Four-Phase Roadmap

**Version:** LCR-PLAN-1.1  
**Synchronized with:** `LC-P1-v1.1`, the Phase 1 work orders and gates in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md). Phase plan and work orders are revised together; they must never drift apart.
**Status:** Phase 1 in progress; later phases are strategic targets, not approved implementation work orders.

## Current position

**Phase:** P1 — Foundation & MVP · **Gate:** G0 closed · **`main` at time of writing:** `b526749` — see [`handoff/CURRENT.md`](handoff/CURRENT.md) for the authoritative pointer

| | |
|---|---|
| Completed | **LC-P1-00** — upstream source study, three architecture ADRs, pinned reference index. `PASS WITH NOTES`, reviewed at [`623e3ca`](https://github.com/gg320324492-lgtm/labcairn/commit/623e3ca31caba327d2f8b1af40ab67c35c7a61d3) and merged as PR #1 (`9b445cd`). Those are the **review subject and merge commit**, not the current tip. |
| Accepted and merged | **LC-P1-01** — reproducible engineering baseline. **PASS WITH NOTES** at [`c23ef775`](https://github.com/gg320324492-lgtm/labcairn/pull/2), fourth independent review, across four review rounds. Hatchling package, web baseline, five CI workflows green on Ubuntu and Windows, 174 tests, reference isolation enforced as a required status check. Evidence in [`acceptance/LC-P1-01-evidence.md`](acceptance/LC-P1-01-evidence.md). **Merged to `main` at [`89c16d4`](https://github.com/gg320324492-lgtm/labcairn/commit/89c16d4c40da857e42f34cef27d11617278e9670) via PR #2.** G1 stays open — LC-P1-02, 03, 04 are not started. |
| Next direction | Merge the accepted LC-P1-01, then **LC-P1-02…04** close **G1 (Trusted core)**: versioned contracts and module boundaries, model providers with truthful capability detection, and the workspace/tool permission boundary. LC-P1-02 must not start before LC-P1-01 is merged. |

**Open issues carried into LC-P1-01** (full table with owners in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md)):

- Copyright ownership is unresolved and the repository deliberately has **no `LICENSE` file**. No open-source rights have been granted.
- **PyMuPDF** is AGPL/commercial dual-licensed and is named by LC-P1-08; it constrains a future MIT release and needs a decision before that work order.
- Reference isolation is **prose, not enforcement** on `main`. On `feat/lc-p1-01-baseline` it is enforced: `tests/test_no_reference_leakage.py` exists with 99 tests and `reference-exclusion` is a required status check. It becomes a property of the project when LC-P1-01 is accepted and merged.
- The five upstream pin SHAs were **verified present on GitHub at LC-P1-00 review time**. The standing risk is upstream force-push or garbage collection, which no local practice prevents; re-verify with `git ls-remote <url>` before relying on a pin.

**What is not yet true of this project:** `main` now holds the engineering baseline — a Hatchling package, a web baseline, five CI workflows and 174 tests — and **still no product**: no CLI, no server, no database, no research capability. Every scientific feature described below is planned, not shipped. Do not read this roadmap as a status report on working software; the honest summary is that the floor is real and nothing on it is a research tool yet.

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
