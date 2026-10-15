# LabCairn — Project source of truth

The GitHub repository at a fixed commit is the project's authoritative record. Conversations are advisory, not proof of implementation.

## Working principle

**GitHub holds project facts. An AI assistant does analysis, design and review.**

Every review is conducted against the actual code and documents at a **named commit SHA** — never against a chat transcript as the only memory. If a fact is not in this repository, it is not established, no matter how confidently it was discussed. When an assistant's recollection and the repository disagree, the repository wins and the document is corrected.

This applies to this index too: the principle is only worth anything if the repository is where the state actually lives.

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

All reviews must identify subject commit SHA, actual inspected evidence, tests run (or not run), open issues and next action.
