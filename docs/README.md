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
- A PR is opened for review and is **not** merged by the party that produced it. See the division of responsibility below.

### Division of responsibility

| Role | Owns |
|---|---|
| **Project lead / reviewer** (AI assistant) | Phase architecture, technology-selection analysis, task constraints, acceptance criteria, GitHub code review, and the next phase's work orders |
| **Implementer** | Development, testing, commits, and actual runtime evidence |

At the end of each phase the reviewer inspects a **named GitHub commit or PR** — architecture, code, tests, scientific behaviour and security boundaries — and issues a verdict of `PASS`, `PASS WITH NOTES`, `BLOCKED` or `FAIL`. Only after a pass does the next phase receive detailed work orders; blocking findings are fixed first.

This deliberately does not lock four phases of technical detail on day one. Strong open-source projects move quickly, so LabCairn's later route should be adjusted on evidence and measured results rather than on a frozen plan.

## Reconciliation note

This index reflects a strategic plan that originally specified **14 work orders and 5 gates (G1–G5)**. The repository is now at **15 work orders and 6 gates (G0–G5)**: LC-P1-00 (upstream source study) and gate G0 were added after that plan was written, on the grounds that architecture decisions must be grounded in inspected upstream code before product code exists. The plan document was **not** pasted in wholesale, which would have regressed the repository; its genuinely new content — name rationale, positioning, repository topics, Rich/pybtex/OpenTelemetry stack entries, the framework-selection rationale and this protocol — was distributed to the documents where it belongs.

| Document class | Directory | Holds |
|---|---|---|
| Work orders | [`PHASE_1_WORKORDERS.md`](PHASE_1_WORKORDERS.md) | Per-batch goals, implementation requirements, acceptance criteria, and a **status board** updated in the same commit as any state change |
| Architecture decisions | [`adr/`](adr/) | Technical choices, upstream reference, trade-off rationale, and later supersession |
| Acceptance reports | [`acceptance/`](acceptance/) | Subject commit SHA, inspected evidence, findings, verdict. One per reviewed commit |
| Roadmap & progress | [`ROADMAP.md`](ROADMAP.md) | Current phase, what is done, open issues, next direction |
| Handoff | [`handoff/CURRENT.md`](handoff/CURRENT.md) | Short current-state summary so a new session or another agent can resume |

## Index

- [Roadmap](ROADMAP.md)
- [Phase 1 work orders](PHASE_1_WORKORDERS.md)
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
| Latest gate | **G0 closed** — LC-P1-00 `PASS WITH NOTES`, subject `623e3ca` |
| Formal review | [LC-P1-00 review](acceptance/LC-P1-00-review-623e3ca.md) |
| Independent re-review | [PR #1 re-review](acceptance/PR-1-independent-review.md) — C-1/C-2/R-01/R-02 reproduced, not assumed |
| LC-P1-00 evidence diary | [LC-P1-00 evidence](acceptance/LC-P1-00-evidence.md) |
| Binding decisions for LC-P1-01 | [Approved amendments](plans/LC-P1-01-approved-amendments.md) |
| LC-P1-01 | **Not started.** [Plan](plans/LC-P1-01-task-breakdown.md) is partially superseded by the amendments |
| License | **Not granted.** No `LICENSE` file exists; see the README |
| LC-P1-01 | **In review.** [Evidence](acceptance/LC-P1-01-evidence.md), [PR #2](https://github.com/gg320324492-lgtm/labcairn/pull/2). No verdict issued. |

All reviews must identify subject commit SHA, actual inspected evidence, tests run (or not run), open issues and next action.
