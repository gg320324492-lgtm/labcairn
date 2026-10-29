# LC-P2-08 — The paper project and the version graph: acceptance

**Work order:** LC-P2-08 (the paper project, the version graph, and the
alignment) · **Subtasks:** T00–T05.
**Task breakdown:** [`docs/plans/LC-P2-08-task-breakdown.md`](../plans/LC-P2-08-task-breakdown.md)
**Status of the work order:** **implemented and measured**, and **not
independently reviewed** — see §6.
**Measured:** 2026-10-29 on the tree at `ef1a36c`, on Windows 11 (AMD64),
Python 3.12.13.

**What this is.** The first implementation of the mentor-trajectory line:
the tables a manuscript's versions live in, the contracts that hold them, the
alignment that proposes which version came from which, the human path that
settles it, and the two checks that are about not lying about an archive.

**What this is not.** It is not the guidance agent, and it is not the
experience store. The reader that produces the events these tables will
hold is LC-P2-07's, and it is measured
([`LC-P2-07-fidelity-baseline.md`](LC-P2-07-fidelity-baseline.md)); the
feedback chain is LC-P2-09's. **What this work order stores is where a
version came from; what LC-P2-09 stores is what happened inside one.**

---

## 1. The three decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **A version graph, never a version list** — the process branches, and a column holding one parent cannot hold two | the schema: `paper_versions` has **no parent column**, and the parent lives in `version_edges` | `test_a_branch_is_representable` |
| **The edge carries how it was decided; the confidence is not the decision** | the schema's `version_edges_acceptance_names_an_acceptor` and the model's validator | `test_a_confident_proposal_is_still_unaccepted`, `test_an_edge_with_no_acceptor_is_refused`, `test_a_proposal_wearing_a_persons_name_is_refused` |
| **An unresolved relationship is a value, not an absence** | the schema's `status` column and the model's default | `test_a_version_with_no_established_parent_is_unresolved_and_listed` |

**And the fourth, which the schema cannot hold:** an edge's two versions
must belong to the edge's project. A CHECK constraint sees one row; this is
a fact about three, so the **model** says it —
`check_edge_within_project`, witnessed by
`test_an_edge_to_a_version_outside_the_project_is_refused`.

## 2. The fourteen acceptance clauses

Every clause in the task breakdown's §4 names a test, and the test exists.

| # | The clause | The test |
|---|---|---|
| A1 | Two files with the same name and different bytes are two versions | `test_two_files_with_the_same_name_and_different_bytes_are_two_versions` |
| A2 | Two files with the same name and the same bytes are one version | `test_the_same_bytes_are_one_version_whatever_the_name` |
| A3 | A version with no established parent is `unresolved` and is listed | `test_a_version_with_no_established_parent_is_unresolved_and_listed` |
| A4 | The order is never taken from a file name | `test_a_file_name_never_decides_the_order` |
| A5 | The order is never taken from an mtime | `test_a_modification_time_never_decides_the_order` |
| A6 | A proposal with high confidence is still unaccepted | `test_a_confident_proposal_is_still_unaccepted` |
| A7 | An edge claiming a human decision with no acceptor is refused | `test_an_edge_with_no_acceptor_is_refused` |
| A8 | An edge with `source='evidence'` and an `accepted_by` is refused | `test_a_proposal_wearing_a_persons_name_is_refused` |
| A9 | The alignment refuses to decide when the evidence points two ways | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| A10 | Two drafts whose prose matches and whose numbers differ are two versions | `test_two_drafts_that_differ_only_in_their_results_are_two_versions` |
| A11 | A missing round is reported, and no version is invented | `test_a_missing_round_is_reported_and_nothing_is_invented` |
| A12 | A correction is a new version of the edge, and the old one stays readable | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |
| A13 | An edge whose parent is outside the project is refused | `test_an_edge_to_a_version_outside_the_project_is_refused` |
| A14 | The demo is run by a test | `test_the_paper_version_demo_runs` |

**Two of the fourteen had no witness when this record was written**, and
both are now implemented: **A13** was a real gap (the schema cannot hold it
and the model did not either), and **A3** had the property but not under
the name the breakdown gave it. **The breakdown is the contract, so the
tests were renamed to the breakdown's wording** — the eleven whose names had
drifted — rather than the other way round.

## 3. The mutations, and what each broke

**A witness that has never been broken is not known to be a witness.**

| # | The mutation | What went red |
|---|---|---|
| 1 | the self-parent constraint is dropped from the migration | `test_a_version_cannot_be_its_own_parent` |
| 2 | the acceptance-names-an-acceptor constraint is dropped | `test_an_edge_that_claims_an_acceptance_must_name_the_acceptor` |
| 3 | **the acceptance constraint is reversed**, so every edge must name an acceptor | `test_a_proposal_with_no_acceptor_is_storable`, `test_a_high_confidence_proposal_is_still_unaccepted`, `test_a_branch_is_representable` |
| 4 | the proposal-may-not-name-an-acceptor refusal is dropped from the model | `test_a_proposal_wearing_a_persons_name_is_refused`, `test_a_model_proposal_is_not_an_acceptance` |
| 5 | acceptance is decided by the **confidence** rather than by who accepted | `test_a_confident_proposal_is_still_unaccepted` |
| 6 | the alignment's ambiguity margin is removed, so a near-tie always decides | `test_the_alignment_refuses_when_the_evidence_points_two_ways` |
| 7 | the fingerprint collects **no numbers** | `test_two_drafts_that_differ_only_in_their_results_are_two_versions`, `test_the_number_signal_is_not_optional`, `test_a_version_with_a_changed_result_is_not_the_same_version` |
| 8 | the correction **overwrites** the proposal instead of superseding it | `test_a_correction_is_a_new_version_and_the_old_one_stays_readable` |
| 9 | the proposal a **rejection** was about is discarded | `test_a_rejection_writes_no_edge_and_keeps_the_proposal`, `test_the_three_outcomes_produce_three_different_shapes` |
| 10 | the content hash decides nothing about duplicates | `test_the_same_bytes_are_one_version_whatever_the_name` |
| 11 | the gap is **renumbered away** | `test_a_missing_round_is_reported_and_nothing_is_invented`, `test_the_duplicate_and_gap_checks_are_independent` |
| 12 | a cross-project edge is allowed | `test_an_edge_to_a_version_outside_the_project_is_refused` |

**Mutation 3 is the one worth reading twice.** A constraint that is too
loose admits a fake acceptance; one that is too tight kills the proposals
the system exists to produce. **Both have witnesses**, and they are on
opposite sides of the same rule.

### 3.1 What a mutation cannot be, and what was learned the hard way

**Two mutations "survived" in this work order, and neither was a mutation.**

1. **One was never applied.** The text to be mutated did not match the
   formatted source, so the file was unchanged and the suite was green.
   **A mutation that was never applied is reported as a surviving
   mutation by anyone who does not check.**
2. **One deleted an assertion instead of making it fail.** Replacing a
   demonstration's guard with a comment leaves the demonstration running,
   printing its steps, and exiting zero: **a missing assertion is
   invisible to an exit code.** The effective mutation is the one that
   **inverts a condition**, and it is caught by five tests at once.

**The rule, and it is in the test file's docstring so the next reviewer
does not have to rediscover it:** *before reporting a surviving mutation,
check that the mutation **applied**, that it changed an **assertion's
condition**, and that the witness could **see** that kind of mutation.* A
guard-count witness catches a bulk removal and not a single one, because a
count with a floor is not an identity — and the limit is stated rather than
papered over.

## 4. What was measured

| | |
|---|---|
| **The whole suite** | see §5 |
| **The corpus and the reader** | revision recall 30/30, deletion recovery 8/8, comment recall 14/14 — [`LC-P2-07-fidelity-baseline.md`](LC-P2-07-fidelity-baseline.md) |
| **The schema** | the migration and the ORM agree — `tests/test_evidence_schema.py`'s parity test walks `Base.metadata` and the migrated schema independently |
| **The refusals** | every rule above is witnessed by **writing a row the schema must refuse**, not by comparing two texts. The project's own lesson from revision 0007 is that a parity test cannot catch both the migration and the ORM being wrong together |

## 5. The suite on this tree

**Measured on `ef1a36c`** — the commit this record was written at.

```
(see the number below)
```

## 6. What this work order has not had

- **No independent review.** The project's rule is that a work order is
  accepted on an **independent review at a named commit**, and per the
  owner's decision of 2026-10-29 the reviewer is the owner — they wrote
  none of this code. **That review has not happened yet**, and this
  document does not claim it has.
- **No real material.** Everything here is synthetic. A real manuscript
  brings run fragmentation inside a revision, revision ids Word renumbers on
  save, comments in headers and footnotes, and adviser prose with hedging
  and politeness in it. **The reader has never seen one**, and the
  pilot corpus is where it will.
- **No persistence of the events.** The tables hold projects, versions and
  the edges between them. **LC-P2-07's revision events are read and then
  go nowhere**, because the tables they would live in — `EditAction`,
  `FeedbackEvent`, `ResponseLink` — are LC-P2-09's.
- **No clustering into projects.** Which material belongs to which paper is
  the harder question, and it is a question about *identity* rather than
  about *history*. A version's parent is decidable by evidence; a version's
  project is declarable by a person.
- **No intake.** The design's §7 names the zip bomb, the path traversal
  and the macro. **None of those is a version-graph question**, and they
  belong to LC-P2-06's, because intake is where a grant is checked.
- **No retrieval over the graph.** LC-P2-11's case retrieval needs an
  index, and the index needs LC-P2-05's widened corpus to be measured
  against.

## 7. The next thing

**LC-P2-06, the data governance.** Its grant table names the paper project
this work order created, so the two fit together — and the reader's events
have nowhere to live until the response tables do.

**And one thing that is not a ticket:** the CI shard cost for this work
order's four new test files. The rule is that the cost must come from a
**runner**, and the two-step process for that is recorded in the Phase 2
evidence pack — the first run apportions, the second measures.
