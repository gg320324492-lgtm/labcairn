# LabCairn Four-Phase Roadmap

**Version:** LCR-PLAN-1.1  
**Synchronized with:** `LC-P1-v1.1`, the Phase 1 work orders and gates in [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md). Phase plan and work orders are revised together; they must never drift apart.
**Status:** Phase 1 dispatched; later phases are strategic targets, not approved implementation work orders.

| Phase | Focus | Exit gate |
|---|---|---|
| P1 — Foundation & MVP | Standalone local-first Agent, typed tools, task/resume, evidence anchors, bounded analysis with a deterministic scientific plot, a first-party research Skill, report delivery, CLI + local Web | Fresh external install and end-to-end evidence-backed task, with security/recovery/quality tests |
| P2 — Scientific Intelligence | Better retrieval, citation identity/support, advanced analysis sandbox, higher-fidelity scientific plots, editing, expanded research Skills, conditional reviewers/subagents | Measured capability gain against a frozen P1 baseline, no scientific-claim inflation |
| P3 — Production & Ecosystem | Stronger isolation, packaging, plugin/MCP trust, Windows/macOS/Linux distribution, robustness, observability, docs, benchmark expansion | Secure, maintainable, multi-platform public release and documented operational limits |
| P4 — Continuous Improvement | User feedback, targeted refinements, provider/format coverage, incremental UX/performance improvements | Small reviewable releases with regression tests and clear changelogs |

Phase 2 items listed against scientific plots and research Skills are **upgrades** of Phase 1 capabilities, not their first delivery. Phase 1 already ships a deterministic plot (`LC-P1-10`) and a first-party `research-report` Skill (`LC-P1-07`); Phase 2 raises their fidelity and breadth.

## Phase 1 upstream research

**LC-P1-00** is a new lightweight prerequisite and continuing reference task: establish separate local clones of selected top Agent/scientific-Agent repositories, record precise SHAs and license context, and use ADRs/tests to justify architecture choices. Do not vendor/reference-clone entire repositories inside the public repo. See [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md). P1 now contains **15 work orders (00–14)**, with G0 for reference setup before the original G1–G5 gates.

## Review protocol

1. Complete all work orders and exit gates for the current phase. Internal commits and PRs may be used during the phase.
2. Push a verifiable GitHub commit SHA or PR, plus actual test results and demonstration evidence.
3. Independent reviewer examines source, contracts, tests, security and demonstration; statuses: PASS / PASS WITH NOTES / BLOCKED / FAIL.
4. Fix blocking findings before phase close. Only then issue the *next phase's detailed* work orders based on implemented reality.

**Hard principle:** Phase 2/3 features do not excuse failure of Phase 1 boundaries; security and evaluation start in Phase 1 and mature thereafter.
