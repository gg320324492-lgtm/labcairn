# LC-P2-11 — The mentor guidance memory — acceptance

**Work order:** LC-P2-11 (the mentor guidance memory) · **Subtasks:**
T00–T05 · **Task breakdown:**
[`../plans/LC-P2-11-task-breakdown.md`](../plans/LC-P2-11-task-breakdown.md) ·
**Status of the work order:** the schema, the migration, the lifecycle, the
distillation, the retrieval, the demonstration and this record are landed.

**What this is.** The mentor line's rule memory: one row per version of a
rule, one per binding to the chain material it was learned from, one per
case where the rule does not hold; the lifecycle that proposes, confirms,
disputes, withdraws and supersedes; the distillation that proposes a
candidate on the model's behalf; and the retrieval that answers a query
with **rules that carry their sources and their cases**, resolving every
source against the chain at the moment of the query.

**What this is not.** It is not a model. No training, no fine-tuning, no
stored weights — P2-AMD-01's route is retrieval over rules a person can
check. It does not make the rules good (LC-P2-14's question), and it does
not make a rule true; it records what the advisor did and where it applies.

---

## 1. The decisions, and where each is held

| # | The decision | Held by | Witnessed by |
|---|---|---|---|
| 1 | **The state machine is closed**: `candidate → confirmed \| disputed \| withdrawn`, and only a person moves a rule out of `candidate` (ADR-0016 D8) | `src/labcairn/guidance/rules.py`, the `guidance_rules` CHECKs | `tests/test_guidance_rules.py`, the schema refusals by raw `INSERT` |
| 2 | **The confirmer is a second reader** — the owner's rule of 2026-10-31, carried into the memory: whoever proposed a rule cannot confirm it, and `model_proposal` is refused as a confirmer like any other proposer | `confirm_rule`'s refusal | `test_the_proposer_cannot_confirm_their_own_rule`, and `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` for the model's name |
| 3 | **A source stands or falls at query time, by its state and not by a clock**: the chain's presence under the key, the reader's reach through the permission layer (denied materials dropped, ADR-0003 C5), and a judgement that says the change answered | `src/labcairn/guidance/retrieval.py` | `test_a_withdrawn_source_invalidates_its_rule_and_says_so`, `test_a_rule_outside_the_readers_consent_is_not_retrieved`, `test_the_memory_reads_through_the_consent_layer` |
| 4 | **The invalidation is not silent**: a rule the memory stops serving is reported, each dead source saying which of the three ways it died | `invalidated_rules` | the same withdrawal witness, whose second half reads the report |
| 5 | **Conflicts are not resolved**: two confirmed rules that disagree are both returned, ordered by state and rule id, and **the ordering never consults a version or a timestamp** | `search_rules`'s ordering | `test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency` |
| 6 | **The distillation may not invent a scope**: it has no scope parameter — the scope is assembled from the cases' anchored text, the example is the advisor's own words beside the case's key, and a named key the chain holds nothing under is refused | `src/labcairn/guidance/distil.py` | `test_a_rule_with_an_unsupported_scope_is_refused` |
| 7 | **A candidate's review conditions differ from a card's citation conditions**: a candidate is shown to its reviewer on cases that exist and are in reach; a confirmed rule stands only on sources a judgement has answered | `search_rules`'s per-state source conditions | `test_a_candidate_is_not_served_unless_asked`, `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` |
| 8 | **The problem comes from the closed vocabulary**, LC-P2-10's thirteen labels, imported rather than retyped — at propose, at distil, and at the query boundary | `ISSUE_LABELS` checks | `test_a_problem_outside_the_vocabulary_is_refused`, `test_the_query_filters_and_the_vocabulary_gates_it` |

**A finding the state conditions produced.** The first draft required every
served rule's sources to carry an *answered* judgement, and the
distillation's witnesses exposed the mistake: a proposal's cases have
usually not been judged at all, and requiring a judgement to show the
proposal would hide from the reviewer the very thing they are to judge.
Decision 7 is the fix, and it is written into `search_rules`'s docstring.

## 2. What the schema refuses, and how that is witnessed

The three new tables' CHECKs are witnessed the way revision 0007 taught:
**by writing the rows the schema must refuse**, with a raw `INSERT` that
bypasses the ORM — eleven of them in
`test_the_schema_refuses_what_the_api_refuses`. The lesson of that
revision is that a constraint nobody has violated is a comment; the
lesson these rows bought is recorded in the work order's own history:
**SQLite's `length()` counts the spaces a shrug is made of**, so every
emptiness check trims before it counts — in `models.py` and in migration
0015, both, and the parity test holds them together.

## 3. The work order's acceptance clauses, and where each is carried

| # | The clause | The test | State |
|---|---|---|---|
| A1 | every rule reaches a real comment and a real before/after difference | `test_every_rule_reaches_a_real_comment_and_a_real_difference` | landed |
| A2 | a rule carries a problem, a context, a scope, a counterexample and a version | `test_a_rule_carries_a_problem_a_context_a_scope_a_counterexample_and_a_version` | landed |
| A3 | a withdrawn source invalidates the rule, and the invalidation is reported | `test_a_withdrawn_source_invalidates_its_rule_and_says_so` | landed |
| A4 | a counterexample comes back with the rule | `test_a_counterexample_comes_back_with_the_rule` | landed |
| A5 | two conflicting rules are both returned, neither wins by recency | `test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency` | landed |
| A6 | a rule outside the reader's consent is not retrieved | `test_a_rule_outside_the_readers_consent_is_not_retrieved` | landed |
| A7 | a distilled rule is a candidate until a person confirms it | `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` | landed |
| A8 | a suggestion does not become a rule by being retrieved often | `test_a_frequently_retrieved_suggestion_is_still_a_candidate` | landed |
| A9 | a rule whose scope the cases do not support is refused | `test_a_rule_with_an_unsupported_scope_is_refused` | landed |
| A10 | the retrieval returns source and conditions, never a bare sentence | `test_the_retrieval_returns_the_rule_with_its_source_and_its_conditions` | landed |
| A11 | the memory reads through the consent layer | `test_the_memory_reads_through_the_consent_layer` | landed |
| A12 | a new comment changes the retrieval, nothing trained | `test_a_new_comment_changes_the_retrieval_without_anything_trained` | landed |
| A13 | the demo is run by a test | `test_the_guidance_memory_demo_runs` | landed |

## 4. The mutations, and what each one proved

| # | The mutation | The witnesses it reddened |
|---|---|---|
| 1 | the standing-source guard neutered (`if not standing: continue` dropped) | `test_a_withdrawn_source_invalidates_its_rule_and_says_so`, `test_a_source_that_names_no_material_does_not_stand` |
| 2 | the policy's answer discarded (`frozenset(paths)` for the permitted set) | `test_a_rule_outside_the_readers_consent_is_not_retrieved` — exactly one, and the other ten stayed green |
| 3 | the second-reader check neutered (`if False and confirmed_by == proposed_by`) | `test_the_proposer_cannot_confirm_their_own_rule` — exactly one |
| 4 | the demonstration's first claim planted false from outside the source | `test_the_demonstrations_exit_code_still_means_something` observes the non-zero exit |

**And one mutation that was thrown away rather than counted.** The first
attempt at mutation 2 spliced a name that does not exist in its scope, and
the suite went red with a `NameError` — ten failures whose reason was a
crash, not a bypass. A mutation that makes the code crash is not a mutation
that verifies anything, so it was replaced with the semantic one above
before anything was claimed.

## 5. What was measured, and on what tree

**Local, incremental, at commit `826cc49` plus this record's own commit.**
Thirty guidance witnesses (twelve rules, fifteen retrieval, three
distillation), the migration suite's twelve, the demonstration's two, the
store's parity checks — all green, under the suite's environment rules
(`TEMP`/`TMP`/`TMPDIR` at `E:\labcairn-local\tmp`, a fresh `--basetemp` per
run, statuses read from the command and not from a pipe). `ruff`, `ruff
format` and `mypy` are clean on every file the work order added.

**No one-shot whole-suite run was made on the final tree.** The standing
decision of 2026-10-31 applies: after the machine's restart, the suite is
re-measured on the final tree and its figures go into this section. The
incremental evidence above is local until a runner says otherwise.

## 6. What this work order does not carry, and where that is written

- **Four new test files have no runner-measured cost.**
  `tests/test_guidance_rules.py`, `tests/test_guidance_retrieval.py`,
  `tests/test_guidance_distillation.py` and
  `tests/test_guidance_memory_demo.py` are in no shard, and
  `test_ci_shard_coverage` is red **on purpose** — the costs are measured
  on the runner, and the fix is
  `python .github/remeasure_shards.py <run-id>` against the next run's
  logs. No shard partition was guessed.
- **A re-judgement has no writer.** The retrieval reads the response
  row's state, so a re-judged row brings its rule back — and the path
  that writes that state is LC-P2-09's, which records but does not
  re-record. The withdrawal witness changes the row directly, and the
  demonstration withdraws a source through the permission layer instead,
  saying so in its own header.
- **The rules are not good; they are sourced, scoped and checkable.**
  Whether retrieval-augmented rules help a student is LC-P2-14's question,
  and nothing here answers it.
