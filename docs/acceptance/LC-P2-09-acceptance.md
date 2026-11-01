# LC-P2-09 — The feedback chain: acceptance

**Work order:** LC-P2-09 (feedback, response and follow-up) · **Subtasks:** T00–T07.
**Task breakdown:** [`docs/plans/LC-P2-09-task-breakdown.md`](../plans/LC-P2-09-task-breakdown.md)
**Status of the work order:** **implemented and measured**, and **not independently reviewed** — see §7.
**Measured:** 2026-10-30 on the tree this record was written at, on Windows 11 (AMD64),
Python 3.12.13. §6 (the reply) was measured on 2026-11-01.

**What this is.** The second implementation of the mentor-trajectory line: the
four tables a chain of feedback lives in, the contracts that hold them, the
reader that carries the text a comment covers, the version graph's writer that
was missing, and the four annotation events a stream-only reader can replay.
**And a fifth table**, which the work order's own material asked for and the
four could not hold: *a reply* — one party's answer to another's objection,
read out of a document. §6.

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
mutation-checked, and this record covers the six above. §7 records the gap as a
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

### 5.2 The shard cost is measured, in two steps

**The first step was apportioned, and the second is a measurement.** The seven
new test files had never run, so the table carried the local suite's seconds
multiplied by the platform ratio it already holds (`ubuntu = 0.473 × windows`).
**Then the CI run at `b20fa1b` (run `41025301922`) executed them**, and
`.github/remeasure_shards.py` read each file's seconds out of the durations
section of that run's logs and wrote them back with `measured_at = b20fa1b`.

| | Ubuntu | Windows |
|---|---|---|
| **Shard balance factor** | **1.545** | **1.000** |

**The Ubuntu partition is the lopsided one**, and the reason is a single file
that costs more than the rest of its shard's contents; the greedy balance lands
there and the coverage witness accepts it, because no file can be moved to
shorten the longest shard. **The Windows partition is even to three decimals.**

**The two numbers that matter are that the files ran and that the table says
which run measured them.** The apportioned step is kept in the history rather
than rewritten: it is what the table held before any runner had executed the
files, and the difference between the two is the point of the process.

## 6. The reply: the shape the chain held not at all

**What this is.** The work order's material holds four shapes of feedback. The
chain holds three of them — a comment, the change made in answer to it, the
judgement that the change answered it — and a fourth is **a decision and its
reasoning together**: *a reviewer's objection paired with the authors' answer*,
read out of a response document. **Neither half was anywhere in the product**,
and the answer is the half that carries the reasoning.

**What this is not.** It is not a fifth link in the mentor's chain. The chain's
four tables are the mentor's line with a student; these two halves are a
*reviewer* and *the authors*, and they are the paper's own review history.
**So the chain's issue keys, its `set_issue_key` and its judgements do not
reach it** — and the table says so by its shape: it holds no state, no decider
and no evidence, because a reply is a record of what was said and not a verdict
on anything.

### 6.1 The decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **A reply is one row holding both halves** — one half alone is not a reply | `replies` carries the objection and the answer together, and the schema refuses a row whose half is empty. **Two tables, one half each, could not say so**: a CHECK sees one row and never another | `test_a_reply_without_both_halves_is_refused` |
| **The objection is copied, not pointed at** — it is not a comment the chain holds | `replies` has no foreign key to `feedback_events`, and recording a reply creates no comment row | `test_a_reply_is_a_record_and_not_a_verdict` |
| **The parties are the reply's own** — the chain's `actor_kind` cannot say what a reviewer and the authors are | `objection_party` and `answer_party` are closed to `reviewer` and `author`, and the schema refuses the chain's own values | `test_the_parties_are_the_replies_own_and_the_chain_cannot_say_them` |
| **A reply is one party's answer to *another's*** — a row whose two halves are the same party is a monologue | the schema refuses it | `test_the_parties_are_the_replies_own_and_the_chain_cannot_say_them` |
| **The address the row carries is the address it has** — the objections' own addresses do not resolve | `objection_paragraph` and `answer_paragraph` are the reader's own coordinates in the response document, and the row names no place in the manuscript under review | `test_the_reply_names_the_document_it_was_read_from` |
| **A reply is a record, not a verdict** | the table's columns are exactly the record's — no state, no decider, no evidence, no `feedback_id` | `test_a_reply_is_a_record_and_not_a_verdict` |
| **The pairing is the caller's and the words are the document's** | `record_replies` takes two paragraph numbers and reads the words itself; a caller never types a reply's text | `test_a_reply_is_recorded_without_a_caller_writing_the_text` |

**And what the copy costs**, because a decision without its cost is a decision
nobody has made. **The objection's words are held here and, in other cases, in
the chain's comment table as well** — a second spelling of something the chain
may also hold. The price is paid knowingly, and it is these three: the reply
cannot be joined to `feedback_events` to say "this reply answers that
comment"; it carries no issue key; and the chain's `set_issue_key` does not
reach it.

**And why the objection cannot be pointed at.** A `feedback_events` row is the
*advisor's* remark *in a manuscript*: it names the version it was written
against (ADR-0017 D1 refuses a feedback row without one), and a row that was
read carries the locator in `word/comments.xml` that the reader read. **A
reviewer's objection in a response letter names no version** — it is addressed
to a manuscript that was submitted — and the place it points at is a line in a
rendering the corpus does not hold. **Pointing at a comment would mean
inventing a version and an address the material does not have.**

**And the parties, said plainly.** The chain's `actor_kind` is closed —
`student`, `advisor`, `model`, `human` — and it answers *who acted in the
mentor's chain*. **A peer reviewer of a submitted manuscript is neither the
mentor nor the student**, so a value coerced out of that vocabulary would be a
wrong value; and `human` on both halves would be worse than wrong, because it
would say "two people spoke" and be unable to say which was which, which is
the whole content of a reply. **So the reply names its own parties**, and the
schema refuses the chain's values rather than translating them.

### 6.2 The operation, and where the reply sits

`record_replies` in `src/labcairn/papers/replies.py` reads the document a
version was made from, asks the policy about it, checks the bytes against the
version's own hash, and writes one row per exchange. `read_replies` in
`src/labcairn/application/chain.py` reads them back, and it is named in
`application/__init__.py`'s table of the operations the layer owns.

**The permission that governs a reply is the permission on the material the
reply was read from** — the response document the version names — and it is
asked where that material is named, exactly as the chain's own reads are.
**It is neither the mentor's material nor the student's**, and the record says
so rather than leaving a reader to assume the chain's rules reach it.

**And the caller names the two places and the product reads the words.**
Deciding that one paragraph answers another is a judgement, and the project
asks a judgement to name its decider; the caller makes it, and the *words* are
a fact about the file that the product supplies. **So a caller never types a
reply's text**, and a reply cannot say something the document does not say.

### 6.3 The mutations, and what each broke

**Each schema mutation was applied to the model *and* to the migration**, so
the parity test stayed green and the redness was the property's and not the
drift's. **The files were restored byte for byte**, and their hashes were
compared with the ones taken before the first mutation.

| # | The mutation | What went red | What it tells you |
|---|---|---|---|
| 1 | the "both halves" constraint is gone from the model and the migration | `test_a_reply_without_both_halves_is_refused` — *"DID NOT RAISE IntegrityError"* | the refusal is the database's, and the parity test stayed green |
| 2 | the "two parties" constraint is gone from the model and the migration | `test_the_parties_are_the_replies_own_and_the_chain_cannot_say_them` | a reply is an exchange and the schema says so |
| 3 | the party vocabulary is widened to take the chain's values | `test_the_parties_are_the_replies_own_and_the_chain_cannot_say_them` | the reply's vocabulary is its own, and it is closed |
| 4 | the writer takes the objection from somewhere other than the document | `test_a_reply_is_recorded_without_a_caller_writing_the_text` and `test_a_reply_row_carries_the_objection_and_the_answer` | **the words are the document's** |
| 5 | the layer's read ignores the versions the caller named | `test_the_layer_reads_the_replies` | a version nobody named holds no exchange |
| 6 | the drift check is gone | `test_a_document_that_changed_under_the_name_records_nothing` | a document that changed under the name records nothing |
| 7 | the table grows a column that could hold a verdict | `test_a_reply_is_a_record_and_not_a_verdict` | the table holds the record and nothing else |
| 8 | recording a reply also writes a comment | `test_a_reply_is_a_record_and_not_a_verdict` | a reply is not the chain's comment, and it creates none |
| 9 | the paragraph range check is gone | `test_a_reply_names_no_paragraph_the_document_does_not_have` — *"DID NOT RAISE ApplicationRefusedError"* | a paragraph number names a place the document has |
| 10 | the duplicate-exchange check is gone | `test_a_reply_names_no_paragraph_the_document_does_not_have` | one exchange is one row |

**The mutations the record does not cover.** The reply's *shape* is witnessed
by the column set and by the refusals above, and **no mutation was recorded
against the hash shape, against the ordering of the two halves' paragraphs at
the schema's level, or against the "the whole plan is made before anything is
written" ordering in the writer** — the first two are witnessed by the same
raw-`INSERT` test as the rest of the schema's rules, and the third rides on
mutation 9, whose refusal happens before the plan is complete.

### 6.4 What the reply does not do

- **The reply's addresses into the manuscript under review do not resolve, and
  the row carries none.** The objections in this family address lines in a
  rendering the corpus does not hold. **A reply names no place in the paper
  under review**, and the place an objection points at lives in the
  objection's own words and nowhere else. **A reader must not assume that
  `objection_paragraph` is a place in the paper**: it is a place in the
  response document the version names, and it is the reader's own coordinate.
- **A reply is not replayable from the event stream.** The revision adds no
  event type — the chain's four objects are on the stream and this is a fifth
  waiting for a fifth event — so a stream-only reader cannot reconstruct the
  exchanges.
- **A pairing's grade cannot be corrected in place.** The reply's id is a
  function of the version and the two paragraphs, so a second recording of the
  same exchange with a different grade is **refused** rather than applied: a
  change of judgement is a correction, and this table holds one version of a
  reply and has nowhere to put a second.
- **One exchange is one row, and a document half-recorded is a document nobody
  can count.** The whole plan — the words read, the rows already there
  checked, every conflict found — is made **before** anything is written, so a
  refusal leaves nothing behind for a later commit to pick up. The same
  exchange named twice in one call is refused for the same reason.
- **The reply's objection is not the chain's comment**, so the chain's
  recurrence, its issue keys and its follow-up assessments do not reach it.
- **Nothing of the material enters the repository.** The four paragraphs the
  witnesses read are written in `tests/test_feedback_events.py`, because the
  repository is public and the paper is the owner's.
- **The migration chains to `0017`, not to `0018`.** `0018` had not landed on
  `main` when this revision was written, and **a migration that chains to a
  revision that does not exist breaks the chain**. The one line that changes
  at merge time is `down_revision`; a revision that chains to a revision that
  is not its parent leaves two heads.

## 7. Limits, and what is left for the reviewer

- **The mutation pass is six of seventeen.** The remaining clauses have named
  witnesses and no mutation recorded against them in this record (§4).
- **The review is not independent.** The agent that wrote most of the code also
  merged it; the board's independent-review rule is **not discharged**.
- **The shard costs are measured at `b20fa1b`**, and the Ubuntu partition's
  balance factor is 1.545 (§5.2).
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
- **The reply has its own limits, and they are in §6.4.** The one a reader is
  most likely to get wrong is the address: **`objection_paragraph` is a place
  in the response document, not a place in the manuscript under review**, and
  the latter does not resolve.
