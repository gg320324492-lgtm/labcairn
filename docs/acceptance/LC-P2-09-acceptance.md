# LC-P2-09 — The feedback chain: acceptance

**Work order:** LC-P2-09 (feedback, response and follow-up) · **Subtasks:** T00–T07.
**Task breakdown:** [`docs/plans/LC-P2-09-task-breakdown.md`](../plans/LC-P2-09-task-breakdown.md)
**Status of the work order:** **implemented and measured**, and **not independently reviewed** — see §6.
**Measured:** 2026-10-30 on the tree this record was written at, on Windows 11 (AMD64),
Python 3.12.13.

**What this is.** The second implementation of the mentor-trajectory line: the
four tables a chain of feedback lives in, the contracts that hold them, the
reader that carries the text a comment covers, the version graph's writer that
was missing, and the four annotation events a stream-only reader can replay.

**What this is not.** It does not say whether the advisor was right; it does not
render the chain; it does not identify people; and it does not let a model
originate guidance. Those are ADR-0017's own boundary and the task breakdown's
§5, and each is a decision rather than an oversight.

---

## 1. The three decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **A comment is an observation with two addresses** — what was written, and where it was written about | `feedback_events` carries `comment_locator` **and** `anchor_paragraph`/`anchor_start`/`anchor_end`, and neither is derivable from the other | `test_a_feedback_row_carries_both_addresses` |
| **A response is a judgement with evidence, not a status** | the schema refuses a non-`pending` state with no decider, no moment or no evidence; the writer asks the same rule first | `test_a_response_state_needs_a_decision_and_its_evidence` |
| **Unknown is a value** — no author, no date, an unpaired range | the row carries `author_unknown_reason`/`date_unknown_reason` and `anchor_status`, and the reader's own answer is inherited rather than re-decided | `test_a_missing_author_or_date_is_unknown_and_never_guessed` |

**And the fourth, which had nowhere to live until this work order:** the version
graph had **no writer**. LC-P2-08 landed the contracts and the checks and no way
to store a row, so an edge a chain needs to name could not exist. `T00` landed
`src/labcairn/application/papers.py`, and `T00`'s own brothers — the rejection
row, the frozen version hash, and the project consent being **resolved rather
than recorded** — are held by `0012_version_edge_rejections.py`.
**The two gaps the design named are now rows, not notes.**

## 2. The gap this work order found in its own predecessor, and closed

**The four chain events existed and nothing emitted them.** `T05` landed the
payload models, the registration and the four `emit_*` functions — and **no
operation called one of them.** The event stream a report's hash chain covers
would have proved the bookkeeping and not the chain, which is the distinction
ADR-0017 §14 exists to remove. The witness for "the events exist" was there;
the property "the chain lands in the stream" had no witness because it had no
code.

**It is wired now**, and in one transaction per operation:

- `record_feedback` writes the rows and emits one `feedback_recorded` per **new**
  row, in the same unit of work — a second reading of the same bytes finds the
  rows already there and emits nothing, because recording the same fact twice is
  one fact;
- `record_edit` emits `edit_action_recorded` with the actor it recorded
  (ADR-0017 D4: there is no default actor);
- `record_response` emits `response_recorded` **only when the state is not
  `pending`** — a pending row is not a judgement, and "no row" is how "not
  answered" is represented;
- `record_assessment` emits `followup_assessed` with the verdict, including
  `not_established`, which is a verdict and not an absence.

**The witness is the exit demonstration**, whose last step reads the stream
through `events_after` and refuses to finish unless the four annotation types are
in it. **A mutation of the wiring is what proves it**: removing the emit from
`record_edit` turns `test_the_feedback_demo_runs` red with the message *"an edit
event is in the stream"* (§4, mutation 6).

## 3. The seventeen acceptance clauses

Every clause in the task breakdown's §4 names a test, and the test exists
**under the name the breakdown gives it**.

| # | The clause | The test |
|---|---|---|
| A1 | A comment becomes a feedback row carrying **both** addresses | `test_a_feedback_row_carries_both_addresses` |
| A2 | The feedback row carries the anchored text and its hash, and the offsets and the text agree in the version the row names | `test_the_anchored_text_agrees_with_the_offsets_in_the_version_named` |
| A3 | A missing author or date is unknown, and never guessed | `test_a_missing_author_or_date_is_unknown_and_never_guessed` |
| A4 | A feedback row names the version it was written against, and a row that names none is refused | `test_a_feedback_row_names_its_version_and_one_that_names_none_is_refused` |
| A5 | A comment that cannot be anchored is still written, with its body and the reason | `test_an_unanchorable_comment_is_still_a_comment` |
| A6 | An edit names who made it, and a model's change is not the advisor's | `test_an_edit_names_who_made_it` |
| A7 | A response's state cannot be reached without a decision and its evidence | `test_a_response_state_needs_a_decision_and_its_evidence` |
| A8 | A comment with no response is **listed as unaddressed** | `test_an_unanswered_comment_is_listed_as_unaddressed` |
| A9 | A change that does not answer the comment is recorded as `not_addressed` and exists | `test_a_change_that_does_not_answer_is_recorded_as_not_addressed` |
| A10 | A partly-answering change is `partially_addressed` and not `addressed` | `test_a_partial_answer_is_not_an_answer` |
| A11 | No `issue_key` is inferred from the text, and a comment with no key is uncategorised | `test_no_issue_key_is_inferred_from_the_text` |
| A12 | Two comments with the same key in different versions are visible as one recurring issue | `test_the_same_issue_recurring_is_visible_as_one_issue` |
| A13 | An assessment carries its own evidence, and one that derives the advisor's correctness from the change's acceptance is refused | `test_an_assessment_cannot_derive_correctness_from_acceptance` |
| A14 | The four chain events are annotations and carry a registered payload schema | `test_the_chain_events_are_annotations_with_registered_payloads` |
| A15 | A version and an edge can be stored, and a stored edge round-trips through the models' checks | `test_a_stored_edge_round_trips_through_the_models_own_checks` |
| A16 | The demo is run by a test | `test_the_feedback_demo_runs` |
| A17 | A model's candidate carries **no** `comment_locator`, and a row that claims the advisor's words without having read them is refused | `test_a_candidate_does_not_claim_the_advisors_words` |

**Two names were changed to meet the contract rather than the other way
round**: the edge round-trip test was written as
`test_an_edge_is_stored_and_read_back_as_the_model`, and the demonstration's
witness was written as `test_the_feedback_chain_demonstration_still_holds`; both
were renamed to A15's and A16's wording. **The breakdown is the contract.**

## 4. The mutations, and what each broke

**A witness that has never been broken is not known to be a witness.** These six
were applied to the source, watched, and reverted; the tree was checked before
each one, because **a mutation that was never applied looks exactly like a
success**.

| # | The mutation | What went red | What it tells you |
|---|---|---|---|
| 1 | the response evidence rule is skipped (`if state != "pending"` → `if False`) | `test_a_response_state_needs_a_decision_and_its_evidence` | the Python rule and the schema's CHECK both hold; the schema caught it, so the witness is not the only defence |
| 2 | the `pending` refusal is removed from `ResponseRecordedPayload` | `test_a_response_with_no_judgement_made_is_not_an_event` — *"DID NOT RAISE ValidationError"* | this one is clean: the model is the only place the rule lives |
| 3 | the reader's anchored text is replaced with `""` | `test_the_anchored_text_agrees_with_the_offsets_in_the_version_named` | the chain's first link is watched, not assumed |
| 4 | `change_accepted` is added to the assessment's allowed bases | `test_an_assessment_cannot_derive_correctness_from_acceptance` | again the schema's CHECK caught it; the acceptance-is-not-evidence rule has two guards |
| 5 | `list_unaddressed` skips a comment with no response | `test_an_unanswered_comment_is_listed_as_unaddressed` | the listing is a fact about the chain, not about its rows |
| 6 | `record_edit` commits the row and emits no event | `test_the_feedback_demo_runs` — *"an edit event is in the stream"* | **the wiring this work order added is watched** |

**Two of the six went red through the database rather than through the code's
own refusal.** That is not a clean witness — the test still named the property,
and the schema is a real second guard — but it means the Python rule is not the
only thing standing between the caller and the bad row. The limit is stated here
rather than presented as a clean mutation.

**The other eleven clauses' mutations are not in this record.** They are the
reviewer's pass: the task breakdown's §7 asks for every claim in §2 to be
mutation-checked, and this record covers the six above. §6 records the gap as a
limit, not as a completion.

## 5. What was measured

| | |
|---|---|
| **The merged tree** | the three agent branches (`T00`, `T01`–`T04`, `T05`) merged into `claude/p2-lc-p2-09`; the only code conflict was `application/refusal.py` and `tests/evaluation/manifest.py`, and both were additions on both sides |
| **The migration number** | two branches claimed `0012`. `T00`'s `0012_version_edge_rejections.py` kept the number; the chain's four tables became `0013_feedback_chain.py`, with `down_revision = "0012"` |
| **The whole suite** | see §5.1 |
| **The exit demonstration** | `uv run python examples/feedback_demo.py` — nine steps, every claim in a `check()` that raises, and `test_the_feedback_demo_runs` runs it |
| **The demonstration's determinism** | two runs print **identical output**: the moment is fixed, and the synthetic manuscript's archive entries carry one timestamp |
| **Lint and types** | `ruff check .`, `ruff format --check .`, and `mypy` are clean |
| **The shard table** | `.github/ci-shards.json` carries the six chain files plus the demonstration's, **apportioned rather than measured** — see §5.2 |

### 5.1 The suite on this tree

**Measured on the tree at `fed5161`, on Windows 11 (AMD64), Python 3.12.13.**

```
4101 passed, 5 skipped, 0 failed, in 30 minutes 1 second
```

**The first full run of this tree had seven failures, and all seven were one
long line.** The renamed witness
(`test_a_stored_edge_round_trips_through_the_models_own_checks`) was written on
one line, `ruff check` refused it at 110 characters, and the outsider-path walk
— which runs the README's own commands against a clone of this tree — failed six
times downstream of that one lint failure. **The line is formatted in `fed5161`,
and the full suite was re-run on it**: the number above is the re-run's, not the
pre-fix one.

**The five skips are all of the project's own accepted kinds**, and none of them
is new or about this work order: a POSIX permission-bit case, the real-provider
smoke that needs the owner's credential, a Windows drive form that is
meaningless on POSIX, and two 8.3 short-name cases this machine's volume cannot
carry.

### 5.2 The shard cost is apportioned, and that is what it is

**Neither the runner nor a previous run has executed the seven new test files.**
The costs in `.github/ci-shards.json` are the local suite's measurements
multiplied by the platform ratio the table already carries (`ubuntu = 0.473 ×
windows`), and `measured_at` names the commit they were apportioned at.

**The shard coverage witness is green on that number, and the number is not a
measurement.** The next CI run executes the files, and the measurement after it
replaces this one — the same two-step the Phase 2 evidence pack records, and the
same honesty LC-P2-06's record used.

## 6. Limits, and what is left for the reviewer

- **The mutation pass is six of seventeen.** The remaining clauses have named
  witnesses and no mutation recorded against them in this record (§4).
- **The review is not independent.** The agent that wrote most of the code also
  merged it; the board's independent-review rule is **not discharged**.
- **The shard costs are apportioned, not measured** (§5.2).
- **The chain is not rendered.** Whether a report shows it, and what a reader
  sees, is the owner's decision — ADR-0017's first re-evaluation trigger.
- **Identity is kinds, not people.** ADR-0015 D6's conditions are open, and they
  are the acceptance list for the moment the pilot opens beyond the
  administrator.
- **A model may not originate a comment or decide a response**, and that is a
  rule this work order holds — LC-P2-12 owns the guidance cards, and ADR-0016
  owns the promotion rules.
- **The demonstration writes the grant row itself.** The product still has no
  writer for grants, which is LC-P2-06's gap and not this work order's.
