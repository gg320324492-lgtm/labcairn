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
| 1 | **The state machine is closed**: `candidate → confirmed \| disputed \| withdrawn`, and only a person moves a rule out of `candidate` (ADR-0016 D8) | `src/labcairn/application/guidance.py`'s transitions, `src/labcairn/guidance/rules.py`, the `guidance_rules` CHECKs | `tests/test_guidance_rules.py`, the schema refusals by raw `INSERT` |
| 2 | **The confirmer is a second reader** — the owner's rule of 2026-10-31, carried into the memory: whoever proposed a rule cannot confirm it, and `model_proposal` is refused as a confirmer like any other proposer | `confirm_rule`'s refusal | `test_the_proposer_cannot_confirm_their_own_rule`, and `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` for the model's name |
| 3 | **A source stands or falls at query time, by its state and not by a clock**: the chain's presence under the key, the reader's reach through the permission layer (denied materials dropped, ADR-0003 C5), and a judgement that says the change answered | `src/labcairn/guidance/retrieval.py` | `test_a_withdrawn_source_invalidates_its_rule_and_says_so`, `test_a_rule_outside_the_readers_consent_is_not_retrieved`, `test_the_memory_reads_through_the_consent_layer` |
| 4 | **The invalidation is not silent**: a rule the memory stops serving is reported, each dead source saying which of the three ways it died | `invalidated_rules` | the same withdrawal witness, whose second half reads the report |
| 5 | **Conflicts are not resolved**: two confirmed rules that disagree are both returned, ordered by state and rule id, and **the ordering never consults a version or a timestamp** | `search_rules`'s ordering | `test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency` |
| 6 | **The distillation may not invent a scope**: it has no scope parameter — the scope is assembled from the cases' anchored text, the example is the advisor's own words beside the case's key, and a named key the chain holds nothing under is refused | `src/labcairn/guidance/distil.py` | `test_a_rule_with_an_unsupported_scope_is_refused` |
| 7 | **A candidate's review conditions differ from a card's citation conditions**: a candidate is shown to its reviewer on cases that exist and are in reach; a confirmed rule stands only on sources a judgement has answered | `search_rules`'s per-state source conditions | `test_a_candidate_is_not_served_unless_asked`, `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` |
| 8 | **The problem comes from the closed vocabulary**, LC-P2-10's thirteen labels, imported rather than retyped — at propose, at distil, and at the query boundary | `ISSUE_LABELS` checks | `test_a_problem_outside_the_vocabulary_is_refused`, `test_the_query_filters_and_the_vocabulary_gates_it` |
| 9 | **A check is a decidable standard, and decidability is two things**: the question and the pass criterion, neither of which may be empty | `src/labcairn/guidance/checks.py`, the `guidance_checks` CHECKs | `test_a_check_carries_its_question_and_its_criterion`, `test_an_empty_check_field_is_refused` |
| 10 | **A check is a norm and lives beside the rules it decides** — not in the chain, and not beside the counterexamples, which are cases *against* a rule | `src/labcairn/guidance/checks.py`'s docstring, `guidance_checks` | `test_a_withdrawn_check_is_named_by_no_rule` |
| 11 | **The binding names the rule's version**, and **a new version starts with no check** — the check that decided the old words is not automatically the check that decides the new ones | `guidance_rule_checks`, `supersede_rule` | `test_a_new_version_starts_with_no_check` |
| 12 | **A binding is in force only while both of its ends are**: a withdrawn rule names no check, and a withdrawn check is named by no rule | `write_guidance_rule_withdrawal`, `write_guidance_check_withdrawal` | `test_a_withdrawn_rule_names_no_check`, `test_a_withdrawn_check_is_named_by_no_rule` |
| 13 | **What a model proposes, a person confirms** — a check is a candidate until a second reader confirms it, and **a rule may name only a confirmed check** | `confirm_check`, `write_guidance_rule_check` | `test_the_proposer_cannot_confirm_their_own_check`, `test_a_rule_may_name_only_a_confirmed_check` |

**And where the rows are reached.** The memory's three tables are read and
written through the application layer — `src/labcairn/application/guidance.py`
for the rules, `src/labcairn/application/chain.py` for the chain's facts — so
the mentor line is reached in one place and a guard applied there reaches every
caller. **The rules about words and people stay in
`src/labcairn/guidance/rules.py`** — the closed vocabulary, the fields that may
not be empty, the source a rule must name, the second reader, the reason a
dispute must carry. **The transitions are the layer's**, because a row may not
hold a state the memory forbids, and a layer operation that could write one
would be a hole in the layer.

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
| A14 | a check carries a question and a pass criterion, and neither may be empty | `test_a_check_carries_its_question_and_its_criterion`, `test_an_empty_check_field_is_refused` | landed |
| A15 | a check's proposer may not confirm it | `test_the_proposer_cannot_confirm_their_own_check` | landed |
| A16 | a rule may name only a confirmed check, and a rule that cannot be bound is not written | `test_a_rule_may_name_only_a_confirmed_check` | landed |
| A17 | the binding says which rule a checklist item is checking, in both directions | `test_a_rule_names_the_checks_that_decide_it` | landed |
| A18 | two rules may share one check | `test_two_rules_may_share_one_check` | landed |
| A19 | a withdrawn rule names no check, and a withdrawn check is named by no rule | `test_a_withdrawn_rule_names_no_check`, `test_a_withdrawn_check_is_named_by_no_rule` | landed |
| A20 | a new version starts with no check | `test_a_new_version_starts_with_no_check` | landed |
| A21 | the schema refuses what the API refuses, and a binding to a check or a rule version that is not there cannot be written | `test_the_schema_refuses_what_the_api_refuses_about_the_checks`, `test_the_schema_refuses_a_binding_to_a_check_that_is_not_there`, `test_the_schema_refuses_a_binding_to_a_rule_version_that_is_not_there` | landed |

## 4. The mutations, and what each one proved

| # | The mutation | The witnesses it reddened |
|---|---|---|
| 1 | the standing-source guard neutered (`if not standing: continue` dropped) | `test_a_withdrawn_source_invalidates_its_rule_and_says_so`, `test_a_source_that_names_no_material_does_not_stand` |
| 2 | the policy's answer discarded (`frozenset(paths)` for the permitted set) | `test_a_rule_outside_the_readers_consent_is_not_retrieved` — exactly one, and the other ten stayed green |
| 3 | the second-reader check neutered (`if False and confirmed_by == proposed_by`) | `test_the_proposer_cannot_confirm_their_own_rule` — exactly one |
| 4 | the demonstration's first claim planted false from outside the source | `test_the_demonstrations_exit_code_still_means_something` observes the non-zero exit |
| 5 | **the binding accepts a check nobody confirmed** (the layer's `confirmed` guard made dead) | `test_a_rule_may_name_only_a_confirmed_check` — exactly one, the other twenty-three stayed green |
| 6 | **a withdrawn rule keeps its checks** (the release dropped from the withdrawal) | `test_a_withdrawn_rule_names_no_check` — exactly one |
| 7 | **a new version inherits the old version's checks** (the supersession made to carry them forward) | `test_a_new_version_starts_with_no_check` — exactly one |
| 8 | **the schema stops refusing an empty question** (the constraint dropped from the model **and** from the migration, so the parity test stayed green) | `test_the_schema_refuses_what_the_api_refuses_about_the_checks` — exactly one, and the migration's own twelve stayed green |
| 9 | **the proposer may confirm their own check** | `test_the_proposer_cannot_confirm_their_own_check` — exactly one |
| 10 | **the binding's foreign key on the check is gone** (dropped from the model **and** from the migration) | `test_the_schema_refuses_a_binding_to_a_check_that_is_not_there` — exactly one |
| 11 | **the binding's foreign key on the rule version is gone** (dropped from the model **and** from the migration) | `test_the_schema_refuses_a_binding_to_a_rule_version_that_is_not_there` — exactly one |
| 12 | **a withdrawn check is still named by the rules that named it** | `test_a_withdrawn_check_is_named_by_no_rule` — exactly one |
| 13 | **the rule the reader is served no longer carries its checks** | `test_the_served_rule_carries_the_checks_that_decide_it` — exactly one |

**And one mutation that was thrown away rather than counted.** The first
attempt at mutation 2 spliced a name that does not exist in its scope, and
the suite went red with a `NameError` — ten failures whose reason was a
crash, not a bypass. A mutation that makes the code crash is not a mutation
that verifies anything, so it was replaced with the semantic one above
before anything was claimed.

**And one witness that was not a witness until it was rewritten.** The
first version of the binding's schema witness wrote the rule and the check
and then rolled the transaction back before writing the binding, so the
rule's own foreign key refused the row first — **and the mutation that
dropped the binding's foreign key on the *check* went unseen.** The
witness passed for the wrong reason, which is the shape of the gap LC-P2-10's
review found. **So it was split into two witnesses**, one where the rule
is there and the check is not, and one where the check is there and the
rule version is not, and each of them can only be refused by the key it
is about. **The mutation was then re-applied, and it was caught.**

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

## 7. T06 — The checks, and the binding from a rule to the check that decides it

**What this piece is.** The group's checklist and the advisor's distilled
rules were two documents that happened to say the same standard in two
places. **The binding is what makes them one thing**: a rule names the
checks that decide it, and a check names the rules it decides.

### 7.1 The shape that was chosen

| | |
|---|---|
| **the check** | a **question** and a **pass criterion** — two fields, neither of them empty |
| **where it lives** | `guidance_checks`, beside the rules it decides — **not in the chain**, and not beside the counterexamples |
| **its own state** | `candidate → confirmed \| withdrawn` — the rule's own state machine, and the confirmer may not be the proposer |
| **the binding** | `guidance_rule_checks`, naming **the rule's version** as well as the check |
| **sharing** | many-to-many: **two rules may name one check**, and one rule names one check once |

**And the four decisions the shape rests on.**

**A binding is in force only while both of its ends are.** A withdrawn
rule names no check, and a withdrawn check is named by no rule. **The rows
that bound a withdrawn thing are released**, and the thing itself stays
with its reason. **And that is what makes "a check no rule names" an
answerable question** — a check nobody's rule leans on is a norm nobody
uses, and the memory can say so because the bindings that were released
are gone.

**A new version starts with no check.** The binding belongs to the
version, and a rewording is not a confirmation: the check that decided
version 1's words is not automatically the check that decides version 2's.
The old version keeps what it was bound against, and `supersede_rule` takes
the new version's checks as an argument, so **the carry-forward is a
person's word and not a default**.

**A rule may name only a confirmed check.** The same rule the memory
applies to a rule: what a model proposes, a person confirms. And the
refusal comes **before** the rule is written, so a rule that could not be
bound is never half-written.

**The rule the reader is served carries its checks.** The binding reaches
the retrieval for free, because the checks travel inside the rule the
retrieval already returns — **a rule served without its checks is the same
defect a rule served without its counterexamples is**.

**And the contract moved with it, because the model did.** The API's
response model *is* the dataclass, so the rule the API serves now carries
the instruments that can decide it — **and that is the same reason it
already carried the cases against it.** The checked-in TypeScript was
regenerated with the repository's own command
(`python -m labcairn.api.typescript web/src/api/generated.ts`), and the
contract's own test passes against the file as regenerated. **No route and
no OpenAPI document was edited by hand**, because a hand-written contract
would be a second spelling of the model.

### 7.2 The migration

**Revision 0018**, next after the revision events' 0017. **Two tables in
one migration**, for the reason 0015 records: they are one design.

**And the migration was run against a real database**, not only through the
test suite: `upgrade head` on a file outside the checkout recorded
revision `0018`, produced `guidance_checks` and `guidance_rule_checks`
with both foreign keys in their DDL, refused a binding to a check that does
not exist (`FOREIGN KEY constraint failed`), and `downgrade to base`
returned the file to no revision at all.

**And the schema's own constraints are the witnesses**, in the way revision
0007 taught: **the rows the schema must refuse are written with a raw
`INSERT`** that bypasses the ORM, and the database refuses them.

### 7.3 What was measured, and on what tree

**Local, incremental, on this branch.** Forty-seven guidance witnesses
(twenty-four rules, sixteen retrieval, seven distillation), the migration
suite's twelve, and the store's parity checks — all green, under the
suite's environment rules (`TEMP`/`TMP`/`TMPDIR` at `E:\labcairn-local\tmp`,
a fresh `--basetemp` per run, statuses read from the command and not from a
pipe). `ruff`, `ruff format` and `mypy --strict` are clean on every file
this piece touched.

**Nine mutations were applied and reverted**, and each file was reverted
byte-for-byte — the SHA-256 of every mutated file was compared with the
copy taken before the mutation, and the two were equal. They are rows 5 to
13 of §4.

**No one-shot whole-suite run was made**, and no runner has seen this tree:
the evidence above is local until a runner says otherwise.

### 7.4 What this piece deliberately does not do

- **It does not run a check against a manuscript.** A check is decidable,
  and deciding it is the reader's work; the memory holds the question and
  the criterion and nothing else.
- **It does not put the group's checklist into the tree.** The template
  lives in the operator's library, outside the repository, and **none of
  its text is in the tree** — the questions, the criteria and the step
  list are the group's own words. **The witnesses use invented ones.**
- **It does not change what a rule is.** The rule's statement, scope,
  sources, counterexamples, state machine and second reader are exactly
  what they were; the check is an addition beside them and not a rewrite of
  them. **And confirmation was not made to depend on a check** — a rule may
  still be confirmed without naming one, because that precondition would
  change the memory's existing meaning and this piece does not ask for it.
- **It does not make the binding a chain row.** The chain is the mentor's
  material, and a checklist written down in advance is not the mentor's
  material.
- **It does not give a check a version.** The rule is the versioned thing —
  a new statement is a new version — and a check is a norm with an
  identity. **A check that is retired is withdrawn with a reason, and a
  rule that was superseded is bound again by hand.**

## The weakest point an independent review found

An independent read-only review re-applied the mutations in this
record's §4 — and two more, the closed state machine's schema check
and the distillation's scope — and found all thirteen claims
**hold**. Its weakest point is **A5's second half**: *the ordering
never consults a version or a timestamp.*

The witness seeds two conflicting rules **at the same instant and the
same version**, so **any** recency key added to the ordering would be
a no-op on that data. The test cannot tell "the ordering consulted
recency and found a tie" from "the ordering never looks". The property
is held today by a code fact — the key tuple contains exactly `state`
and `rule_id` — and not by behaviour. **That is the same shape as the
gap LC-P2-10's review found, met from the other side**: an expired
thing judged by its state rather than by its clock.

**The remedy:** a seed where the two rules differ in version or in
timestamp, still asserting the id order. One line of fixture closes
it.
