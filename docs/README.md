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
| Latest gate | **G2 closed** — LC-P1-05/06/07 all `PASS WITH NOTES`. [Acceptance](acceptance/G2-acceptance.md) · [narrative record](acceptance/G2-evidence.md) |
| Gate G3 | **IN PROGRESS** — spans LC-P1-08…10. LC-P1-08 `PASS WITH NOTES` by owner decision; [LC-P1-09 `PASS WITH NOTES`](acceptance/LC-P1-09-acceptance.md) (merged `a7a2f48`); [LC-P1-10 under way](plans/LC-P1-10-task-breakdown.md) — T00 merged ([ADR-0012](adr/ADR-0012-chart-rendering-library.md), the chart library), T01 merged (the fixture corpus), T02 and T03 merged (the operator contract and the selection), T04 merged (the descriptive operators and the catalogue), T05 merged (the grouped aggregate), T06 merged (the chart recipe), T08 merged (the manifest), T09 merged (the run path), T07 and T10 outstanding |
| Independent re-review | [PR #1 re-review](acceptance/PR-1-independent-review.md) — C-1/C-2/R-01/R-02 reproduced, not assumed |
| LC-P1-00 evidence diary | [LC-P1-00 evidence](acceptance/LC-P1-00-evidence.md) |
| Binding decisions for LC-P1-01 | [Approved amendments](plans/LC-P1-01-approved-amendments.md) |
| Task breakdowns | [LC-P1-09](plans/LC-P1-09-task-breakdown.md) · [LC-P1-10](plans/LC-P1-10-task-breakdown.md) |
| License | **Not granted.** No `LICENSE` file, no rights conveyed. The repository describes itself as in development with open-source licensing pending — see the [README](../README.md#licence-status--not-yet-granted) |
| LC-P1-01 | **Accepted and merged.** `PASS WITH NOTES` at `c23ef775`, merged [`89c16d4`](https://github.com/gg320324492-lgtm/labcairn/commit/89c16d4c40da857e42f34cef27d11617278e9670) via [PR #2](https://github.com/gg320324492-lgtm/labcairn/pull/2). [Evidence](acceptance/LC-P1-01-evidence.md) |

All reviews must identify subject commit SHA, actual inspected evidence, tests run (or not run), open issues and next action.
