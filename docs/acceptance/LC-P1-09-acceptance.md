# LC-P1-09 — Acceptance review

**Work order:** LC-P1-09 (FTS5 retrieval and the evidence ledger)
**Gate:** G3
**Subject:** `main` @ `6834495`, with the findings below fixed on
`review/lc-p1-09-acceptance`
**Date:** 2026-10-19
**Verdict:** **PASS WITH NOTES**
**Scope of this document:** the work order's acceptance clause, clause by clause,
with the evidence. Every defect listed here was reproduced before it was fixed
and mutation-checked after.

## Verification actually run

| Check | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 173 files already formatted |
| `uv run mypy` | no issues, 158 source files |
| `uv run pytest` | **2051 passed, 2 skipped** |

Eight tests in `tests/test_no_reference_leakage.py` errored locally because
`uv build` could not reach PyPI through this machine's proxy. They error
identically with these changes stashed, so the error is environmental and not
new; CI covers them.

## The clause

> **Acceptance:** ground-truth queries identify correct excerpts; fabricated
> DOI/source, wrong locator, missing evidence and conflicting numbers do not
> pass final evidence gate; source provenance preserved through report
> generation.

## What the review found

Three defects. Two are the shape LC-P1-08's review found eight of — **a claim
made in a docstring that the code did not enforce** — and the third is a
**column that nothing ever wrote**, which is the same family as LC-P1-08's
defect 2 (a state that was dead). The tests were green throughout.

| # | Defect | How it was reproduced |
|---|---|---|
| 1 | **The "fabricated DOI" half of the clause has no implementation, and `sources/source.py` claimed it had one.** It said *"Existence is C1's job at LC-P1-09, against a ledger row or a registry."* C1 checks that an **anchored source** exists; it never looks at an identifier, no record can carry one, and ingestion writes `identifiers=()` because the PDF adapters do not extract a DOI | Read the call graph; `ingest.py:280`; no identifier lookup exists in `src/` |
| 2 | **A query the index cannot serve was reported as a negative result.** A trigram index refuses a query with a term shorter than three characters, and the refusal and an empty result are the same value at that layer — so the retrieval layer turned *"we did not search"* into *"the material does not say that"*. The refusal is invisible above the index | `retrieve(conn, "AI", …)` returned `no_hit`; `build_match_expression("AI")` is `None`, so no `MATCH` was ever issued |
| 3 | **`superseded_by` was a column nothing ever wrote.** The model documents it as *"set when a newer record replaces this one"*. With no superseding operation, a rule-written record whose quotation came out ambiguous had **nowhere to go**: it could not be verified (no check passed) and could not be attested (Contract 2 requires `created_by == "user"`), so A4's *"routed to `user_attested` only"* had no route | `attest()` on a rule-written record raised; `grep superseded_by` found only the model and the row copy |

## Clause 1 — ground-truth queries identify correct excerpts

**PASS**, and measured rather than read off a test name.

The ground-truth suite drives `search()`, but a caller gets excerpts from
`retrieve()`, so the clause was measured through the **public API** with the
**real** PDF extraction: all three fixture papers ingested page by page, then
all fifteen queries run.

- **11 of 11** positive queries returned every page the ground truth names.
- **4 of 4** negative queries returned `no_hit` — including
  `dq-neg-fabricated-doi`, `dq-neg-fabricated-title`, `dq-neg-out-of-corpus`
  and `dq-neg-other-project`.

## Clause 2 — fabricated DOI/source

**PARTLY DISCHARGED, and the gap is named rather than papered over.**

What *is* discharged: a fabricated **source**. A citation to a material that was
never ingested names an anchor the ledger does not hold, and C1 fails it —
`test_a_fabricated_source_fails_the_gate` writes such a record with a passing
C1 entry in its log and asserts the gate refuses it.

What is **not** discharged: a fabricated **DOI**, and the reason is structural
rather than an oversight:

- no record can carry an identifier — `EvidenceRecord` has `anchor_ids` and
  nothing else;
- nothing in `src/` resolves an identifier to a source;
- ingestion records none, so the ledger's identifier column is empty for every
  ingested material.

The fix here is to the **claim**, not to the code: `sources/source.py` now says
what C1 actually checks and says plainly that the DOI half is not discharged.
Implementing it means extracting a DOI from a PDF at ingest, giving a record a
place to cite one, and a resolution path for the gate — which is a new piece of
work and is recorded in the task breakdown rather than slipped in.

## Clause 3 — wrong locator

**PASS.** A page-99 anchor into a three-page document fails, and the failure
names **only** that address:

- `test_page_99_of_a_3_page_document_fails` — the outcome is `fail`;
- `test_the_failure_names_the_bad_address_and_no_other_one` — the detail
  contains "page 99" and **no other page number**, so the nearest-page
  fallback that ADR-0004 A1 forbids cannot be hiding in it;
- `test_a_failing_c1_cannot_lift_a_record_to_verified_by_rule` — the record
  model refuses `verified_by_rule` on a failing C1, and `unsupported` is the
  state it can take instead.

## Clause 4 — missing evidence

**PASS.** A record that cites nothing is refused
(`test_a_record_with_no_anchor_at_all_fails`), and so is one that cites
something nothing has confirmed (`test_a_record_that_was_never_verified_fails`).

## Clause 5 — conflicting numbers

**PASS.** Two records about the same cell with disagreeing C3 verdicts both
become `conflicted`, and **neither wins by recency**: the conflict is reported
from both sides, and the structured detail is **symmetric** — the two findings'
sides are each other's opposites, so the structure cannot express a winner.
`test_the_two_sides_carry_no_hint_of_which_record_is_the_subject` asserts the
side type has no field that could hold a preference.

## Clause 6 — source provenance preserved through report generation

**NOT DISCHARGED, and not implementable here.** Report generation is LC-P1-11's.
Nothing renders a `GateResult` or a `RetrievalOutcome` yet, so *"a report cites
nothing when the gate refuses"* is enforced at the gate and asserted at the
record model, but it is not observed in a rendered document. The gate and the
retrieval layer both carry the provenance a report will need — a locator
rendered by `describe_locator`, an origin, and the `UntrustedText` wrapper — but
carrying it is not the same as showing it.

## The twelve conditions of ADR-0004 Contract 4

| # | Condition | Where it lives now | Verdict |
|---|---|---|---|
| A1 | Unresolvable locator → `fail`, cites nothing | T05, T06 | **PASS** — and the "cites nothing" is asserted on the detail's text |
| A2 | Hash drift → `fail` | T05, T09 | **PASS** — the gate re-runs C1 and compares |
| A3 | Quotation mismatch → `fail`, cannot reach `verified_by_rule` | T06 | **PASS** |
| A4 | Ambiguous quotation → `indeterminate`, routed to `user_attested` only | T02, T06, T08 | **PASS after the fix** — the route was closed for rule-written records and is now open through superseding |
| A5 | Conflicting numbers → both `conflicted`, neither wins by recency | T08, T09 | **PASS** — for numeric records about the same cell; see the note below |
| A6 | Empty retrieval → explicit no-evidence, no model call | T10 | **PASS** |
| A7 | Unreadable source excluded and uncitable | T04 | **PASS** |
| A8 | Unknown is not zero | T10 | **PASS** |
| A9 | Failed search is not a negative result | T10 | **PASS after the fix** — a refused query was a miss |
| A10 | Interpretation always unverified | T08, LC-P1-11 | **PASS** for the record; the marker is LC-P1-11's to render |
| A11 | Retrieved text is data | T10 | **PASS** — for capabilities; see the note below |
| A12 | Fabricated source fails | T09 | **PASS** for a fabricated source; **not** for a fabricated DOI |

**Two conditions are narrower than they read, and the narrowing is recorded
rather than glossed.**

*A5* covers numeric records about the same **primary** anchor. The claim-side
conflict the ADR also describes cannot exist under this schema: two claim
records in one task cannot share a span hash, because
`uq_evidence_task_span` is `UNIQUE(task_id, extracted_span_sha256)`.

*A11*'s guarantee is about **capabilities**, and that is what is structural
here: the capability set is a parameter of `build_model_context` and the
context is frozen, so a retrieved passage's text has no path to the set of
tools a model may call. What is **not** guaranteed is that a model will *read*
the text as data rather than as instruction. A wrapper cannot make a language
model unpersuadable, and a claim that it could would be the kind of claim this
ledger exists to refuse.

## What the fixes were, and how they were checked

| Fix | Mutation-checked |
|---|---|
| The retrieval layer distinguishes a **refused** query from a **miss**, using the index's own `query_is_servable` | `a_refused_query_is_reported_as_a_miss` |
| The miss message claims only that **no passage matched**, and says the search is lexical | `the_miss_message_claims_the_material_denies_it`, `the_miss_message_stops_qualifying_its_scope` |
| `supersede_record` writes the replacement, marks the old record, keeps the old row, and refuses a cross-task, twice-over or self-supersession | five mutations, all caught |

Eight mutations, each caught by a named test, and each written so the mutated
file still parses.

**One of the review's own tests was wrong and the mutation check said so.** The
assertion that the miss message must not claim the material denies the claim
compared `'"deadbeef"'` against `"deadbeef"` — a stray quote in the extracted
token made the comparison always true, so the test was green whether or not the
message was honest. It now asserts the **absence** of the overclaim and the
**presence** of the qualifier, which is what makes the message's scope
falsifiable.

## Reviewer independence

This review and these fixes are the same party. The project's merge authority
requires a non-implementing reviewer, so this document records a verdict but
does not discharge that requirement: LC-P1-09 still needs a review by someone
who did not write the fixes.

## Not covered by this review

- **The twelve conditions were checked for their stated scope, not re-derived.**
  A4's route, A5's conflict rule and A11's capability guarantee are narrower
  than their wording, and the narrowing is recorded above rather than repaired —
  repairing A5 would mean a schema change, and repairing A11's reading half
  would mean a claim about language models this project cannot support.
- **Nothing was re-reviewed beyond LC-P1-09.** The event and permission model,
  the store's transactionality and the crash-recovery paths were taken from G2's
  record and not re-examined, as they were in LC-P1-08's review.
- **The corpus cannot establish a direction here either.** There is no
  spreadsheet in the fixture corpus, so every C3 case is a row written by a
  test; and no page contains a ligature codepoint, so C2's ligature rung is
  synthetic too.
