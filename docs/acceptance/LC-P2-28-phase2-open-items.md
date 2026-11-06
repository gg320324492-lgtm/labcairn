# Phase 2 — final open-item ledger (2026-11-06)

**Status.** Phase 2's measured exit gate is **CLOSED, PASS WITH NOTES**; this
document is the administrative closeout's list of what remains open. It is a
record, not a new implementation order. Nothing here starts Phase 3.

## 1. The unaccepted version edges stay unaccepted

A read of the pilot store on 2026-11-06 found **7 batch-10 edges** and **28
batch-11 edges**, all `source='model'`, all with `accepted_by IS NULL`. The
owner's 2026-11-06 decision is to **leave all 35 unaccepted**. The material
does not establish the editorial rounds' order, and a judgement on the chain
would be a person's decision, not a parser's inference. No edge has been
accepted, rejected or rewritten by this closeout.

## 2. Gaps that no further material batch will close

The owner expects **no further paper-material batches**. Two gaps that the
phase had marked "closed by material, not by code" therefore become permanent
limitations of the measured record:

- the second paper's three versions have no connecting edge;
- the author-draft versus mentor-copy edge type is not established.

`F027`'s role in batch 11 also remains undecided. It was ingested as a source
but was not placed on a version edge. The batch-11 editorial rounds remain
branches rather than a settled sequence, and their edges are unaccepted model
proposals.

## 3. Measurements that remain outside the result

- The real-provider smoke is **NOT RUN** in the frozen P1 baseline. The owner
  retains the credential and the decision to spend; see
  [`LC-P2-26-ci-provider-secret.md`](LC-P2-26-ci-provider-secret.md).
- The independent G1/G2 re-review ran on Windows only; its POSIX-only
  witnesses remain **NOT MEASURED**. Its clean whole-suite run was stopped
  because it was concurrent with the baseline harness, so no whole-suite
  count backs that review.
- No human being rated a blind sheet, settled a dispute, or performed the
  independent G1/G2 re-review. Independent agent sessions stood in under the
  owner's 2026-11-05 rule, and the records say so. A later human rating, if
  it ever exists, replaces the current sheets rather than adding to them.
- Agent-to-agent agreement is not inter-human reliability; the 30
  NOT SIGNIFICANT verdicts are not equivalence and do not generalise beyond
  the two unseen papers, the five-arm ablation and the chosen denominator.

## 4. Design, not phase-2 debt

`ADR-0020` and
[`LC-P2-28-review-ingestion-task-breakdown.md`](../plans/LC-P2-28-review-ingestion-task-breakdown.md)
were **design only**: quoted opinions, flagged text, version pairs,
mixed-source refusal and full review ingestion. They were not Phase 2
acceptance clauses and were not implemented by the closeout. The owner
archived both as historical Phase 2 design on 2026-11-06; neither is accepted,
renumbered into Phase 3, or dispatched. The Workbench / desktop shell belongs
to the Phase 3 packaging row, which is a strategic target and not an approved
work order here.

## 5. Delivery and branch state

PR #148 merged as `0d654b2038051805eb0ab410783ea2fe90545506`, its delivery
branch was deleted locally and on the remote, and batch 11's two scratch refs
were merged locally then deleted. The final closeout branch carries this
ledger, the MIT grant, the credential owner's instructions and the
administrative status below. Its runner check, if the owner sends it, is the
last delivery measurement; this document claims no runner result.

## 6. Administrative close

Phase 2's machine-buildable work and its measured gate are closed. The
remaining owner-side items are the credential decision, branch protection and
evaluation-trigger policy, any future human reading, and the permanent
material gaps above. The project does not proceed to Phase 3 without a new
owner decision.

**Scoping note (2026-11-06).** The owner later authorised a Phase 3
[`scoping / ADR pack`](../plans/PHASE_3-scoping-pack.md) and no Phase 3
implementation beyond it. The pack creates no work order, accepts no
design-only ADR, and starts no Phase 3 implementation. It also records the
boundary that a later operator-side WSL measurement of POSIX-only witnesses
does not change this ledger's frozen gate result. The owner's follow-up
decisions defer every candidate scope family and leave the real-provider
smoke NOT RUN and unconfigured. A later same-day decision authorised one
repository-tidy delivery PR and one runner run for the local records; that
changes only their delivery disposition, not the measured gate result or the
Phase 3 boundary.
