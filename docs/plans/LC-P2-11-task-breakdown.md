# LC-P2-11 — The mentor guidance memory — task breakdown

**Work order:** LC-P2-11 (the guidance memory) · **Status:** drafted
2026-10-31, on the branch `claude/p2-lc-p2-10-plans`, while LC-P2-10's PR
#133 is still open — **the two share the branch and the one pull request**,
because the owner's rule is one pull request and one run for a whole body
of work, and the files the two tickets own do not overlap. **Priority:** the
work order table puts it after LC-P2-10 and before LC-P2-12, and the
adjustment of 2026-10-30 (P2-AMD-01) keeps the route on **retrieval over a
rule memory, not a trained model** — this ticket is the memory and the
retrieval half of that route.

## 0. How to read this document

**This is a contract.** §4 names the acceptance clauses and, for each, the
witness that carries it; **every witness in this breakdown is planned to be
mutation-checked** before the work is called done, in the way LC-P2-10's
thirty-four were. **Nothing here needs a person's judgement at build time**:
the gold set and the labels exist already (LC-P2-10), the chain exists
already (LC-P2-09), and what this ticket adds is the rule record between
them and the retrieval over it. **What genuinely needs a person is
proposing and confirming rules from real histories** — §5 says why that is
the owner's, not the ticket's.

## 1. Goals and boundaries

### 1.1 What LC-P2-11 must produce

| | |
|---|---|
| **A rule record** | `GuidanceRule` as an append-only, versioned row: a problem from the closed vocabulary, a context, a scope, a statement, a status (`candidate` / `confirmed` / `retracted` / `superseded`), who proposed it, who confirmed it |
| **A counterexample record** | Counterexamples as rows bound to a rule, each with its own source — **a rule with a counterexample is never served without them** |
| **A source binding** | Every rule binds to **real chain material** — the `issue_key` of the feedback events and the before/after edit it was learned from — and the binding is checked at serve time, not believed |
| **A retraction path** | A rule whose source material is withdrawn stops being served, and a person can retract a rule with a reason |
| **A retrieval** | Query in, rules out: relevant rules **with their counterexamples and their source states**, conflicting rules **both returned**, no winner by recency |

### 1.2 Already done — removed from scope

- **The chain.** LC-P2-09's four tables, its `issue_key`, its response
  states and assessment outcomes are the material rules are learned from;
  **they are not redefined here**. LC-P2-09's writer (its T00) already
  closes the version-graph write gap that ADR-0017 recorded.
- **The vocabulary.** LC-P2-10's `ISSUE_LABELS` is the closed set a rule's
  problem is chosen from; the gold set is the measurement corpus the
  retrieval will eventually be judged against (LC-P2-14), not here.
- **The retrieval machinery.** LC-P2-04/05's `evidence/index.py` search,
  its `Hit.is_drifted` and its match-expression builder are the pattern
  this ticket's retrieval follows; the guidance retrieval composes them,
  it does not fork them.
- **The roles.** ADR-0018's three roles are a contract, not a model. This
  ticket builds what role B reads ("the confirmed rules") and what role C
  consults ("counter-examples"); the roles themselves are LC-P2-12's.

### 1.3 Explicitly not in scope

- **The guided-revision agent.** `GuidanceCard` is LC-P2-12; this ticket
  delivers what a card would cite, not the card.
- **Rule quality.** Whether a retrieved rule is *any good* is a
  measurement LC-P2-14 makes blind; this ticket's acceptance is structural.
- **Model-authored rules.** A model proposal reaching a confirmed state
  would misreport who confirmed it — ADR-0016's D2 applies unchanged. If a
  model proposes a rule one day, it lands as a `candidate` whose
  `proposed_by` names the model, and **no shortcut exists to confirm it**.

## 2. The decisions that shape it

### 2.1 A rule is a row, and a new statement is a new row

**Rules are append-only and versioned.** `guidance_rules` carries
`(rule_id, version)` pairs; editing a rule's statement inserts version n+1
and marks version n `superseded` — the same never-overwrite shape the
version graph and the confirm-edge table already have. Retrieval serves
the highest version of each `rule_id` and nothing else.

### 2.2 The confirmer is a second reader

**Whoever proposed a rule cannot confirm it.** This is the arbiter rule of
2026-10-31 applied to the rule memory: one person reading twice is one
person reading once with extra steps. `confirm` refuses
`confirmed_by == proposed_by` with a machine-readable reason, and a witness
makes the refusal red-able.

### 2.3 A candidate is not served

**Retrieval serves `confirmed` rules by default and says so.** ADR-0018
has role B read *the confirmed rules*; a candidate reaching a card would
be a proposal dressed as a record. `include_candidates` exists as an
explicit parameter — role C reviewing a candidate needs it — and the
default refusal carries a reason, not silence.

### 2.4 Withdrawal is read at serve time, from the state

**A rule's validity is checked when it is served, not when it was
confirmed.** The lesson LC-P2-10's review wrote down — *an expired thing is
judged by its state, not by the clock* — becomes this ticket's serve-time
source check: the retrieval resolves each hit's `issue_key` against the
chain's current response states, and a source that no longer stands
(withdrawn response, missing material) stops the rule from being served.
`Hit.is_drifted` is the pattern for the shape of this check.

### 2.5 The problem comes from the closed vocabulary

**A rule's problem is an `ISSUE_LABELS` member, and the schema refuses
anything else.** The gold set's labels and the rule memory's labels are
one vocabulary; a rule whose problem is outside it cannot be measured
against the gold set, so it cannot be stored. The "must not" of the work
order — *store "an advisor prefers this style"* — is enforced here: a rule
without a problem, a context, a scope, a statement and a version does not
insert.

### 2.6 Conflicts are returned, not resolved

**Two conflicting rules are both returned, and neither wins by being
newer.** The retrieval has no winner field and no recency tie-break; the
caller sees both rules and their counterexamples, because *a paraphrase is
not a quote* taught Phase 1 that hiding a conflict is worse than showing
it. Ranking is by relevance to the query only.

### 2.7 Migration 0015, additive

The tables arrive as **migration 0015** and nothing existing changes
shape. The chain, the versions and the consent rows keep their numbers
and their columns.

## 3. The work

### T00 — The tables, and the migration

`guidance_rules`, `guidance_rule_counterexamples`,
`guidance_rule_sources`, migration 0015, and the schema-level refusals:
a problem outside `ISSUE_LABELS`, a missing context or statement, an
illegal status, and a counterexample without a source are all insert-time
errors. **The refusals are witnessed with illegal rows, not with reading
the code** — the lesson of the constraint checks is that a constraint
nobody has tried to violate is a comment.

### T01 — The lifecycle, as an API

`propose`, `confirm`, `retract`, `supersede` in
`src/labcairn/papers/rules.py`, each refusing what it must (the second
reader rule, the closed vocabulary, retract-without-reason) and each
recording who did what when. Every lifecycle action writes an annotation
event in the pattern LC-P2-09's chain writes, so the rule memory is
replayable the way the chain is.

### T02 — The source binding, and the serve-time check

A rule binds to one or more `issue_key`s; the binding stores the chain's
own identifiers so the serve-time check can resolve the response states
*now*. This is where "a rule's source material withdrawn invalidates the
rule" is carried — and the witness for it withdraws the material and
expects the rule to stop being served.

### T03 — The retrieval

`src/labcairn/papers/retrieval.py`: a query (an issue kind and free text)
returns rule hits with counterexamples and source states attached,
conflicting rules together, ranked by relevance, candidates out by
default. The match expression reuses `evidence/index.py`'s builder rather
than growing a second query language.

### T04 — The refusals, with reasons

Every refusal in T00–T03 is a typed, machine-readable reason in the
manifest's pattern — a caller that misuses the rule memory learns *why*,
and the wording is witnessed so a rewording that breaks a caller's
matching is caught.

### T05 — The demonstration

The four acceptance clauses, each shown on the synthetic corpus the gold
set already ships: a rule proposed from a real chain and confirmed by a
second reader; a source withdrawn and the rule gone from the results; a
counterexample served with its rule; two conflicting rules returned
together. **No service is started** — the demonstration drives the
library, the way LC-P2-08's and LC-P2-09's demonstrations did.

### T06 — The acceptance record, and the shard list

`docs/acceptance/LC-P2-11-acceptance.md`, written from measurements: each
witness with its mutation, the demonstration's output, the suite run the
record was measured on, and the anchors. The four new test files join the
shard list through the existing apportion-then-remeasure path, and the
record says which the runner has measured.

## 4. Acceptance, mapped to where it is carried

| Work-order clause | Where it is carried | Witness shape |
|---|---|---|
| Every retrieved rule reaches a real comment and a real before/after difference | T02, T03 | Every hit resolves to an existing feedback event and an edit whose before and after hashes differ; a rule bound to nothing cannot be served |
| A rule's source material withdrawn invalidates the rule | T02 | Withdraw the source's response; the rule leaves the retrieval's results on the next query |
| A counterexample stops the rule being served unconditionally | T00, T03 | The hit type carries counterexamples non-optionally; a rule with one is served only with it |
| Two conflicting rules are both returned, neither wins by being newer | T03, T06 | Two contradictory rules in; both out; the hit carries no winner and no recency break |
| The "must not": no style preference without a problem | T00 | Insert-time refusal witnessed with the exact row the work order forbids |

## 5. What this work order cannot deliver, and why

- **Rules.** Proposing and confirming rules from real histories is a
  person's work, and the pilot histories are the owner's. The ticket ships
  the memory, the retrieval and the demonstration data; **the first real
  rules are the owner's to seed**, with the second-reader rule in force
  from the first one.
- **A measurement of retrieval quality.** The corpus is three papers and
  the locator-validity metric is `NOT MEASURED` (reuse matrix §3.7);
  LC-P2-14's blind evaluation is where a number comes from, and this
  ticket refuses to invent one.
- **A card.** LC-P2-12 consumes this; nothing in this ticket presumes its
  shape beyond ADR-0018's contract.

## 6. The file-ownership map

| Ticket | Files it owns (new unless stated) | Phase 1 files it touches |
|---|---|---|
| LC-P2-11 | `src/labcairn/papers/rules.py`, `src/labcairn/papers/retrieval.py`, `tests/test_guidance_rules.py` | `db/models.py` (rule tables), `db/migrations.py` (migration 0015), `evidence/index.py` (match-expression reuse) |

**The overlap with PR #133 is none:** LC-P2-10's files are
`papers/labels.py`, `papers/gold_manifest.py`, the four gold-set test
files and the records; LC-P2-11 touches none of them, and the two tickets
share a branch because the owner's landing model is one pull request per
body of work, not one per ticket.

## 7. What "done" means

- Every §4 clause has a witness, and **every witness has a mutation that
  makes it fail** — recorded, with the tree the mutations ran on.
- The migration runs from an empty database and from a migrated one, and
  the store tests stay green on both.
- The demonstration runs and its output is in the acceptance record.
- The shard list carries the new test files, with costs the runner has
  measured or the record explains why not.
- No push and no pull request beyond the one the branch already carries;
  the suite evidence is local until the owner spends a run.
