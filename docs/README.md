# LabCairn — Project source of truth

The GitHub repository at a fixed commit is the project's authoritative record. Conversations are advisory, not proof of implementation.

## Working principle

**GitHub holds project facts. An AI assistant does analysis, design and review.**

Every review is conducted against the actual code and documents at a **named commit SHA** — never against a chat transcript as the only memory. If a fact is not in this repository, it is not established, no matter how confidently it was discussed. When an assistant's recollection and the repository disagree, the repository wins and the document is corrected.

This applies to this index too: the principle is only worth anything if the repository is where the state actually lives.

### Change-control rule

**Any modification that changes a task's status, a technical decision, an acceptance result, or an implementation standard goes through a pull request.**

Rationale: those four are the facts the rest of the project is built on. A direct commit to `main` can make the repository assert something no one reviewed — which is exactly the failure mode this project's own principle exists to prevent.

Exempt are changes that cannot alter project facts — typos, formatting, broken-link fixes, whitespace. **These still require a commit**, never an uncommitted edit.

Two consequences worth stating explicitly:

- A status-board update ships **in the same PR as the work it reports**, so the board can never drift from the code it describes.
- A PR is opened for review. **The rule that the producing party never merges is historical (through 2026-10-24)**; the current merge authority is stated below.

### Division of responsibility

| Role | Owns |
|---|---|
| **Executing agent** | Work-order decomposition, dependency ordering, task assignment, integration, CI, scope control, and the GitHub status record |
| **Cross-review agent** | Reviews work it did not implement: contract conformance, malformed-input handling, permission/privacy/path/network checks, **adversarial attempts to prove a claimed guard is ineffective**, cross-module integration and regression, and doc claims against actual behaviour |
| **Project lead** | Architecture and phase decisions, licence obligations, scope expansions, anything touching original data, outbound transmission, or model-generated code execution |

**Two-layer review is internal cross-verification, not external independent audit.** Where older acceptance records say "independent review", they mean *a reviewer who did not implement the work* — independent of the implementation, not of the project. The two senses must not be confused: an internal reviewer is not an external auditor. Every
work order is reviewed by a sub-agent that did not write it, and the executing agent then
independently re-checks that agent's findings, runs the key tests, and inspects the final
commit. Neither layer substitutes for an outside auditor, and no document may describe this
as one.

**Merge authority.** From LC-P1-01 onward the executing agent merges its own pull requests
once both layers have signed off, all required CI checks pass, and the status board matches
the merged commit. The authorisation comes from the project plan, not from an external
reviewer.

**Auto-advance to the next work order** requires: acceptance evidence that is executable
rather than asserted, both layers concluding, no open blockers, required CI green without
skipped tests or lowered thresholds, and the status board consistent with the merge.

**Always escalate to the project lead**, regardless of how routine it looks: widening data
access, write access to original material, unapproved outbound transmission, any
model-generated code execution, major architecture change, and unresolved licence
obligations — PyMuPDF's AGPL/commercial duality gates LC-P1-08.

**Report at gate boundaries, not per commit.** Concentrated reports when a gate closes, when a
decision is genuinely blocked, or on a security event. Ordinary bugs, test failures, lint and
type errors are fixed without escalation.

**Three states are kept distinct**: implemented · internally reviewed · merged into the
baseline. Never conflate them.

## Reconciliation note

This index reflects a strategic plan that originally specified **14 work orders and 5 gates (G1–G5)**. The repository is now at **15 work orders and 6 gates (G0–G5)**: LC-P1-00 (upstream source study) and gate G0 were added after that plan was written, on the grounds that architecture decisions must be grounded in inspected upstream code before product code exists. The plan document was **not** pasted in wholesale, which would have regressed the repository; its genuinely new content — name rationale, positioning, repository topics, Rich/pybtex/OpenTelemetry stack entries, the framework-selection rationale and this protocol — was distributed to the documents where it belongs.

| Document class | Directory | Holds |
|---|---|---|
| Repository map | [`REPOSITORY-MAP.md`](REPOSITORY-MAP.md) | Where product code, witnesses, records, generated files and current pointers live |
| Work orders | [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md), [`plans/PHASE_3-work-orders.md`](plans/PHASE_3-work-orders.md) | Per-batch goals, implementation requirements, acceptance criteria, and a **status board** updated in the same commit as any state change |
| Architecture decisions | [`adr/`](adr/) | Technical choices, upstream reference, trade-off rationale, and later supersession |
| Acceptance reports | [`acceptance/`](acceptance/) | Subject commit SHA, inspected evidence, findings, verdict. One per reviewed commit |
| Roadmap & progress | [`ROADMAP.md`](ROADMAP.md) | Current phase, what is done, open issues, next direction |
| Handoff | [`handoff/CURRENT.md`](handoff/CURRENT.md) | Short current-state summary so a new session or another agent can resume |
| Changelog archives | [`changelog/phase-1.md`](changelog/phase-1.md), [`changelog/phase-2.md`](changelog/phase-2.md), [`changelog/phase-3.md`](changelog/phase-3.md) | The changelog's dated record, split by phase on 2026-11-11; the root `CHANGELOG.md` keeps the container and the index |

## Index

- [Roadmap](ROADMAP.md)
- [Repository map](REPOSITORY-MAP.md)
- [Phase 1 work orders](PHASE_1_WORKORDERS.md)
- [Phase 3 G1 work orders](plans/PHASE_3-work-orders.md)
- [Phase 3 scoping pack](plans/PHASE_3-scoping-pack.md)
- [Phase 3 planning proposal](plans/PHASE_3-execution-plan.md)
- [Multisource research learning supplement](plans/MULTISOURCE-research-learning-plan.md)
- [Phase 3 Q1–Q96 traceability](plans/PHASE_3-design-traceability.md)
- [Phase 3 planning decisions](acceptance/PHASE_3-planning-decisions-2026-11-06.md)
- [Phase 3 board-opening decisions](acceptance/LC-P3-00-board-opening-decisions.md)
- [Architecture](ARCHITECTURE.md)
- [Evaluation](EVALUATION.md)
- [Upstream reference study](UPSTREAM_REFERENCES.md)
- [Architecture decisions](adr/)
- [Approved plans](plans/)
- [Review and acceptance](acceptance/)
- [Latest handoff](handoff/CURRENT.md)

## Current record

| Item | Value |
|---|---|
| Current phase (2026-11-14, replacing the 2026-11-12 pointer) | **Phase 1 closed at G5; Phase 2's exit gate and administrative closeout are CLOSED, PASS WITH NOTES.** Phase 3's board is open with work orders [`LC-P3-01` … `LC-P3-08`](plans/PHASE_3-work-orders.md); no Phase 3 gate is closed. The G1/G2/G3 implementation and the Electron shell follow-up batch are merged into local `main`, 07/08 remain blocked on 05's installed build, and the owner-picked sample's 42-arm machine loop is measured at 42/42 with 14 produced, 28 refused and 8 artifacts. The accumulated batch was delivered in [PR #156](https://github.com/gg320324492-lgtm/labcairn/pull/156) and merged as `777bb63192af4cb5aef51cd561d5031353d1f230`; the run reported 18 checks passing, with `evaluation` skipping by design. Since that merge, four delivery pull requests have landed — [#161](https://github.com/gg320324492-lgtm/labcairn/pull/161) merged `ef30823` (the live documents' pointers became wording anchors; the job-count witness gained its record list), [#162](https://github.com/gg320324492-lgtm/labcairn/pull/162) merged `6186fff` (the browser driver and the LGPL truth-arm archives reached `python.yml`'s shard jobs; the version-selection surface closed §17's gap at the wire and in jsdom, record [`LC-P3-01-version-select-2026-11-14.md`](acceptance/LC-P3-01-version-select-2026-11-14.md)), [#163](https://github.com/gg320324492-lgtm/labcairn/pull/163) merged `7ccc5c0` (the shell's T08 input policy, T06 update path and T09 two supply ways closed, record [`LC-P3-05-input-update-supply-2026-11-14.md`](acceptance/LC-P3-05-input-update-supply-2026-11-14.md)) and [#164](https://github.com/gg320324492-lgtm/labcairn/pull/164) merged `6ba6fa8` (the browser witnesses' measured standing recorded) — and local `main` stands with `origin/main` at `6ba6fa82caffd8a9ba78ab9ae9b7ea1b45c1f1e3` as this row was written. The `certifi` upgrade `2026.7.22` → `2026.10.23` cleared the CRITICAL emSign intermediate-CA advisory, the only immediate one of the 25 advisories found. The G4 checklist revision 2 carries 31 classifiable rows whose signatures stay `PENDING` until the gate's implementation (the installed build and the trial) is complete, and NOTICE records the full 268-package shell dependency closure (13 runtime packages and 255 build-only packages, none of them copyleft), and since 2026-11-12 its §0.1 names **four surfaces a distribution carries**, of which the two named here are the ones that file had left out — the eight installer-distributed binaries (two LGPL-2.1) and the web tree's 266 lock keys (12 MPL-2.0, one CC-BY-4.0); the python dependency closure and the shell npm tree were the two it already measured. The human dual-host reopen half is still `NOT RUN`: the 44-row checklist is 4/44, WPS rows continue by screenshot, Word 2010 rows stay `PENDING-HUMAN` — the host is installed (`C:\Program Files (x86)\office2010\Office14\WINWORD.EXE`, file version 14.0.7252.5000, verified 2026-11-13), so its rows are open for the owner to observe with the same screenshot mode, and the 16-row reopen ledger is 16/16 `PENDING-HUMAN` with its observation SOP ready for the owner. Shard costs have been re-measured from runner run `42733499009`. Current pointers: [ROADMAP.md](ROADMAP.md), [work orders](plans/PHASE_3-work-orders.md), [handoff/CURRENT.md](handoff/CURRENT.md), [planning decisions](acceptance/PHASE_3-planning-decisions-2026-11-06.md), [execution proposal](plans/PHASE_3-execution-plan.md), [multisource supplement](plans/MULTISOURCE-research-learning-plan.md), [Q1–Q96 traceability](plans/PHASE_3-design-traceability.md) and [scoping pack](plans/PHASE_3-scoping-pack.md). The rows below are dated gate records. |
| Gate G3 | **closed** — [LC-P1-08 `PASS WITH NOTES`](acceptance/LC-P1-08-acceptance.md) · [LC-P1-09 `PASS WITH NOTES`](acceptance/LC-P1-09-acceptance.md) (merged `a7a2f48`) · [LC-P1-10 `PASS WITH NOTES`](acceptance/LC-P1-10-acceptance.md) — all eleven subtasks merged. The independent review that closed the gate is [recorded in the gate review](acceptance/G3-acceptance.md) |
| Gate G4 | **closed** — [LC-P1-11 `PASS WITH NOTES`](acceptance/LC-P1-11-acceptance.md) · [LC-P1-12 `PASS WITH NOTES`](acceptance/LC-P1-12-acceptance.md) — the report path and the three surfaces, and the exit test — *"CLI and Web produce same versioned report"* — **demonstrated**: the CLI's task document and the local service's, field by field, and the report's bytes by hash. The independent review that closed the gate is at `9381036af0104172f16fe94a6edd2e8cb6d9ae04`, verdict **PASS WITH NOTES**, and is [recorded in the gate review](acceptance/G4-acceptance.md) |
| G3's independent review | At `d114810` — a reviewer that wrote none of the fixes broke each of the gate's fourteen fixes, implementation only and never the test, and **no mutation survived**; verdict `PASS WITH NOTES`. Its three findings are fixed in `f0f7563` (PR #70) |
| Independent re-review | [PR #1 re-review](acceptance/PR-1-independent-review.md) — C-1/C-2/R-01/R-02 reproduced, not assumed |
| LC-P1-00 evidence diary | [LC-P1-00 evidence](acceptance/LC-P1-00-evidence.md) |
| Binding decisions for LC-P1-01 | [Approved amendments](plans/LC-P1-01-approved-amendments.md) |
| Task breakdowns | [LC-P1-09](plans/LC-P1-09-task-breakdown.md) · [LC-P1-10](plans/LC-P1-10-task-breakdown.md) · [LC-P1-11 and LC-P1-12](plans/LC-P1-11-12-task-breakdown.md) |
| License | **MIT.** LabCairn original code is granted by the root `LICENSE` file, `Copyright (c) 2026 Tonghe Du`; third-party terms are in `NOTICE` — see the [README](../README.md#licence-status--mit) |
| LC-P1-01 | **Accepted and merged.** `PASS WITH NOTES` at `c23ef775`, merged [`89c16d4`](https://github.com/gg320324492-lgtm/labcairn/commit/89c16d4c40da857e42f34cef27d11617278e9670) via [PR #2](https://github.com/gg320324492-lgtm/labcairn/pull/2). [Evidence](acceptance/LC-P1-01-evidence.md) |

All reviews must identify subject commit SHA, actual inspected evidence, tests run (or not run), open issues and next action.
