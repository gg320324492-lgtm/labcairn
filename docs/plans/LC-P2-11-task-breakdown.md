# LC-P2-11 — The mentor guidance memory: rules that carry their sources — task breakdown

**Work order:** LC-P2-11 (the mentor guidance memory) · **Status:** drafted
2026-10-30, **not yet dispatched**. **Priority:** the adjustment of
2026-10-30 (P2-AMD-01) makes this the phase's **core route** — *"the
mentor experience library uses retrieval-augmentation and rule storage,
not model parameter memory"*.

## 0. How to read this document

**This is a contract, not a suggestion.** §4 names the acceptance clauses
and, for each, the test that carries it.

**And this work order is where the phase's central scientific discipline
becomes a table.** A mentor's experience is worth carrying **because it
can be traced to the moment it was learned** — a comment, a revision, a
response, an outcome. A rule that cannot name its source is a rule nobody
can check, and a rule nobody can check is a rule that will be applied to
the wrong paper.

## 1. Goals and boundaries

### 1.1 What LC-P2-11 must produce

**`GuidanceRule` — a candidate, a rule, a counterexample, a retraction —
and the retrieval over it.** Every rule carries:

| | |
|---|---|
| the **source anchor** | the real comment and the real before/after difference it was learned from |
| the **issue type** | the problem it addresses |
| the **rule text** | what it says |
| the **scope** | the domain and situation it applies in |
| an **example** | a case it was derived from |
| a **counterexample** | a case where it does **not** hold |
| the **version** and the **state** | `candidate \| confirmed \| disputed \| withdrawn` |
| **when**, and **who confirmed it** | |

**And the retrieval returns the rule with its evidence and its conditions**,
never a bare sentence the model has abstracted. *"王老师总是这样改"* is
not a rule; *"when the claim has no comparison group, the advisor asks for
one — see the comment of 2026-03-02, and note the two cases where
asking for one was declined"* is.

### 1.2 Already done — removed from scope

- **The retrieval machinery** — LC-P2-05's retrieval beyond three papers,
  and the FTS index and the source anchors it uses. **The memory's
  retrieval is a different query over the same store, not a second
  database without permissions.**
- **The chain the rules are learned from** — LC-P2-09's four tables and
  their events. **A rule's source is a row in that chain.**
- **The evidence ledger's vocabulary** — `model_proposal`, the six states,
  and the constructor's refusal to promote a proposal. **A rule distilled by
  a model is a `candidate`, and only a person makes it `confirmed`.**
- **ADR-0016's D8 and D9** — a rule distilled from cases is a candidate
  until a human confirms it, and **a suggestion does not become an
  advisor's rule by being retrieved often**.

### 1.3 Explicitly not in scope

- **Model parameters.** No training, no fine-tuning, no LoRA, no stored
  weights. P2-AMD-01 removed these from the phase; LC-P2-15 holds the
  optional research, **and it is decided by data volume, permission and a
  measured blind-review gain — not by this work order.**
- **The guidance card.** LC-P2-12 cites these rules; it does not produce
  them.
- **The rules' scientific correctness.** A rule is what the advisor did, and
  what it applies to. **Whether the advice was right is a claim about the
  science**, and it is assessed by LC-P2-14's blind protocol, not
  asserted here.
- **Sharing across people and projects.** The rules are retrieved **within
  the consent's reach**; a rule distilled from one person's unpublished
  material does not become readable by another person because they are in
  the same research group.

## 2. The decisions that shape it

### 2.1 The retrieval is a query, not a new store

P2-AMD-01: *"do not introduce a second database without permissions for
'memory'."* **So the rules live in the repository's own tables and are
retrieved through the same store, and every read goes through the same
consent layer.**

**And the retrieval's scope is the consent's scope.** A rule whose source
comment the reader may not read **is not retrievable by that reader** — not
because the query filters it, but because the retrieval asks the
permission layer for the rows it may show. **A memory that leaks is worse
than no memory**, because a rule applied without its sources looks like
knowledge.

### 2.2 A rule without a source is not a rule

**Every rule reaches a real comment and a real before/after difference.**
That is what makes it checkable: a reader can open the comment and see
what the advisor actually wrote, and the difference the student actually
made. **And a rule whose source material is withdrawn is invalidated** —
because the rule's authority was the source, and the source is gone.

### 2.3 A counterexample stops the rule being served unconditionally

**The counterexample is part of the rule, not a footnote.** A rule served
without its counterexample is a rule applied to a case it was shown not to
apply to. **So the retrieval returns the counterexample with the rule**, and
the card that cites it (LC-P2-12's A7) shows it too.

### 2.4 Two conflicting rules are both returned, and neither wins by being newer

**Recency is not a reason.** If two rules conflict, **both come back**, with
their sources, and the conflict is **displayed** — the same way the
evidence ledger displays a `conflicted` record rather than picking a side.
**A system that silently prefers the newer rule has replaced the advisor's
judgement with a timestamp.**

### 2.5 A model may propose a rule and never confirm it

**ADR-0016's D8**: a rule distilled from cases is a **candidate** until a
human confirms it. **And D9**: a suggestion does not become an advisor's
rule by being retrieved often. **So the state machine is
`candidate → confirmed | disputed | withdrawn`, and only a person moves a
rule out of `candidate`.**

### 2.6 A new comment updates the case library, not the weights

**This is the point of the whole route.** When the advisor writes a new
comment and the student answers it, **the case library grows and the
retrieval finds it** — with no training, no fine-tuning and no GPU. **The
phase's claim is that a retrievable, sourced, scoped rule is worth more
than a parameter that cannot be asked where it came from**, and this work
order is where that claim is made concrete.

## 3. The work

### T00 — The rule, its sources and its state

**Files:** `src/labcairn/db/models.py` (`GuidanceRuleRow`), a migration,
`src/labcairn/guidance/rules.py` (new), `tests/test_guidance_rules.py`
(new).

**The row carries everything §1.1 lists**, and **the state machine is
closed**: `candidate`, `confirmed`, `disputed`, `withdrawn`.

**And the sources are rows, not text.** A rule points at the feedback and
the edit it was learned from — **the chain's own ids** — so the rule's
provenance is checkable and its withdrawal is a fact about a row.

### T01 — Distilling a candidate, and a person's confirmation

**Files:** `src/labcairn/guidance/distil.py` (new),
`tests/test_guidance_distillation.py` (new).

**A candidate is distilled from cases and confirmed by a person.** The
distillation is a model's work, so **the candidate's creator is
`model_proposal`** and it is **never** `confirmed` without a person's
confirmation, and **the rule's state carries the confirmation's actor and
time**.

**And the distillation may not invent a scope.** A rule whose scope the
cases do not support is refused — the scope is *the applicability
condition*, and a rule with a guessed scope is applied to papers it was
never learned from.

### T02 — The retrieval, and what it returns

**Files:** `src/labcairn/guidance/retrieval.py` (new),
`tests/test_guidance_retrieval.py` (new).

**The retrieval returns the rule, its source anchor, its scope, its
example and its counterexample** — and it asks the permission layer which
rules the reader may see, so **a rule whose source is out of the reader's
reach does not come back**.

**And it does not rank by recency.** A rule retrieved because it was
confirmed last week is not more applicable than one confirmed last year.

### T03 — The withdrawal, and what it invalidates

**Files:** `src/labcairn/guidance/retrieval.py`,
`tests/test_guidance_retrieval.py`.

**A rule whose source material is withdrawn is invalidated**, and the
retrieval stops serving it. **And the invalidation is not silent**: the
rule is reported as invalidated, with the reason.

**And the rule's own withdrawal is recorded** — who withdrew it and when —
because *"the record of what was withdrawn is itself a record"*.

### T04 — The conflict, displayed

**Files:** `src/labcairn/guidance/retrieval.py`,
`tests/test_guidance_retrieval.py`.

**Two conflicting rules are both returned**, each with its sources, and
**the conflict is stated**. Neither wins by being newer, and **the
retrieval does not pick**.

### T05 — The demonstration, and the acceptance record

**Files:** `examples/guidance_memory_demo.py` (new),
`tests/test_guidance_memory_demo.py` (new),
`docs/acceptance/LC-P2-11-acceptance.md` (new), `.github/ci-shards.json`.

**The demonstration shows** a rule retrieved with its source and its
counterexample, a conflicting rule returned beside it, a withdrawn rule's
source making it invalid, and a candidate that a person has not yet
confirmed — **and it shows that a new comment changes what the retrieval
returns, with no training of anything.**

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | Every rule reaches a **real comment and a real before/after difference** | `test_every_rule_reaches_a_real_comment_and_a_real_difference` |
| A2 | A rule carries a problem, a context, a scope, a counterexample and a version | `test_a_rule_carries_a_problem_a_context_a_scope_a_counterexample_and_a_version` |
| A3 | A rule's source material withdrawn **invalidates the rule**, and the invalidation is reported | `test_a_withdrawn_source_invalidates_its_rule_and_says_so` |
| A4 | A counterexample stops the rule being served unconditionally, and is returned with it | `test_a_counterexample_comes_back_with_the_rule` |
| A5 | Two conflicting rules are **both** returned, and **neither wins by being newer** | `test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency` |
| A6 | A rule the reader's consent does not reach is **not retrievable** | `test_a_rule_outside_the_readers_consent_is_not_retrieved` |
| A7 | A rule distilled by a model is a **candidate**, and only a person confirms it | `test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it` |
| A8 | A suggestion does not become an advisor's rule by being retrieved often | `test_a_frequently_retrieved_suggestion_is_still_a_candidate` |
| A9 | A rule whose scope the cases do not support is refused | `test_a_rule_with_an_unsupported_scope_is_refused` |
| A10 | The retrieval returns the rule's source anchor and its conditions, never a bare sentence | `test_the_retrieval_returns_the_rule_with_its_source_and_its_conditions` |
| A11 | The memory is **not** a second store: every read goes through the consent layer | `test_the_memory_reads_through_the_consent_layer` |
| A12 | A new comment changes what the retrieval returns, **with nothing trained** | `test_a_new_comment_changes_the_retrieval_without_anything_trained` |
| A13 | The demo is run by a test | `test_the_guidance_memory_demo_runs` |

**Every one of these needs a witness, and the witness must fail for the
property.** When a test goes red, ask what made it red before believing
that it caught something. **And a mutation that was never applied is
reported by anyone who does not check as a survivor**, which looks exactly
like a success.

## 5. What this work order cannot deliver, and why

- **It does not make the rules good.** It makes them **sourced, scoped and
  checkable**. Whether they help is LC-P2-14's question.
- **It does not learn from a person who has not consented.** A rule
  distilled from material the reader may not read is not retrievable by
  that reader.
- **It does not make a rule true.** It records what the advisor did and
  where it applies. **Whether the advice was right is a separate claim**,
  and ADR-0015's and LC-P2-12's prohibitions on inferring correctness from
  acceptance apply here too.
- **It does not make a model remember.** It makes a **retrieval** find a
  rule that somebody confirmed, with the case it came from.
- **It does not carry a rule across people without permission**, however
  related the projects are.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `src/labcairn/guidance/rules.py`, `tests/test_guidance_rules.py` | `src/labcairn/db/models.py`, `migrations/versions/` |
| T01 | `src/labcairn/guidance/distil.py`, `tests/test_guidance_distillation.py` | — |
| T02 | `src/labcairn/guidance/retrieval.py`, `tests/test_guidance_retrieval.py` | — |
| T03 | — | `src/labcairn/guidance/retrieval.py`, `tests/test_guidance_retrieval.py` |
| T04 | — | `src/labcairn/guidance/retrieval.py`, `tests/test_guidance_retrieval.py` |
| T05 | `examples/guidance_memory_demo.py`, `tests/test_guidance_memory_demo.py`, `docs/acceptance/LC-P2-11-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**And the shared files.** `src/labcairn/db/models.py` is shared with every
work order that adds a table, and the migration number is shared with
them. **This work order may not be dispatched at the same time as another
one that takes a migration number.**

## 7. What "done" means

1. **Every rule reaches a real comment and a real difference**, and the
   thirteen acceptance clauses above have a named test each.
2. **The retrieval returns the rule with its source and its
   counterexample**, and a rule the reader's consent does not reach does
   not come back.
3. **A withdrawn source invalidates its rule**, and two conflicting rules
   are both returned.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-11-acceptance.md` names the commit
   every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md).
7. **Every claim in §2 has been mutation-checked**: the property broken,
   the witness red, the tree restored.
