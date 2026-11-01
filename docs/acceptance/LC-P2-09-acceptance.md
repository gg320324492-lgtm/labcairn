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
| 11 | the answer's paragraph is no longer the ordering tiebreaker | `test_two_exchanges_may_answer_the_same_objection_and_their_order_is_total` | two exchanges may answer the same objection, and the listing says which is first |

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

- **The chain's middle rings were empty until §8.** The second ring
  (`edit_actions`) and the third (`response_links`) had tables and
  contracts and **no way to be filled**, and the guidance memory served
  nothing because of it. **§8 adds the step that fills the second ring
  from what a manuscript's file records, and the step that puts the third
  ring forward without deciding it** — and §8.7 is where its limits are.
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

## 8. The middle rings: the change that was made, and the link put forward

**What this section is.** The step that fills the chain's **second ring**
(`edit_actions`) from what a manuscript's file records, and the step that
**puts the third ring forward** (`response_links`) **without deciding it**.
The work order above landed the four tables and their contracts; **the
rings themselves were empty**, and §8.1 says what that cost.

**And the examples are invented.** No comment, no revision, no author name
and no file name of the owner's manuscript is in this record or in the
tree. The witnesses are written on two made-up names and made-up prose.

### 8.1 The gap, measured

**Read on the owner's own pilot workspace** (two projects, twenty versions,
sixteen accepted edges):

| | rows |
|---|---|
| `feedback_events` | **80** |
| `revision_events` | **0** |
| `edit_actions` | **0** |
| `response_links` | **0** |

**And the consequence was that the memory served nothing.**
`labcairn.guidance.retrieval.search_rules` returned **no rule at all**, and
`invalidated_rules` reported **every confirmed rule the memory holds** as
withdrawn — each one saying its sources are *found, reachable, and **not
addressed***. The retrieval asks whether a judgement says the change
answered the comment, and there was no judgement. **The chain's own
`list_unaddressed` said all eighty comments were unaddressed**, and could
not say why: they were unaddressed because nobody had answered them *and*
because nobody had said anything either.

**So this section is not a feature.** It is the difference between a chain
that is silent and a chain that says what it is waiting for.

**And what the operator has to place, measured on the material itself.**
The first corpus's Chinese versions directory holds **fourteen documents**:
**eight of them carry tracked changes**, **1,532 tracked changes in all**,
**by two author names** — and **forty-six comments**. The forty-six is
the pilot's own first project, so the counts agree; and the two names are
what the roster has to place. **Two names, and the chain refuses every
author the roster does not name**, so a roster that names one of them
fills half the ring and refuses the other half — **the refusal names the
author, and nothing is written.**

**And the row count that follows.** One row per tracked change means
**1,532 rows for this one directory**, and the other corpora hold
directories of the same shape. **That is the second ring's real size**,
and it is why the table holds no text: the content is in the reader's own
rows, and the chain's row names the change and the person.

### 8.2 The questions, answered

**What one row of `edit_actions` is.** **One tracked change**, and **not**
one change-that-answers-a-comment. `EditActionRow`'s own docstring settles
it: *"a change that answers nothing is not an error … so `feedback_id` is
nullable and says so rather than forcing every edit into a feedback it
does not answer."* A table that held only the answers would have nothing
for that column to say. **So the ring holds every change the file records**,
and the column names the comment a change answers **where the caller says
it answers one**.

**Where a change comes from.** **From the file, through the reader.** The
reader produces the revision events — ADR-0014's `revision_events`, each
with its own text, its own address and **the name the file records** — and
the chain's second ring is that history read through the chain's own
vocabulary: *who made this change, on which edge, answering which comment.*

**Who made the change.** **The operator says, and the operator says it
every time.** The vocabulary is closed and **there is no default**, because
a default is how a model's change becomes the advisor's. The name in a
file is a string somebody typed into a box: the same person is spelled two
ways across two drafts, and **a change a model drafted and a person pasted
into Word carries that person's name**. So the operation takes a **roster**
— the file's name mapped to a kind and a plain id — and:

- **a name the roster does not name is refused**, and the refusal names the
  author. The whole operation stops, **before the first row**;
- **the file's name is never copied into the row.** It is the *key* the
  roster is looked up by and never the *value*: `actor_id` is the
  operator's own handle for that person, and LC-P2-09's own boundary says
  the chain records kinds of actor and plain ids and does not decide who a
  person is;
- a revision the file gives **no** author is refused too, because a roster
  cannot name an author the file does not give.

**What the correspondence is.** **The caller's, and the file's is not
there.** Word does not record which change answers which comment, so the
operation takes the correspondence as an argument, keyed by the change's
own revision-event id. **A change that answers nothing is not an error** —
the column is nullable for that reason — so a change the caller does not
name a comment for is recorded with no comment.

**And which of the two is the default.** **Both, and they are different
defaults for different rings.** The *change* is the unit the second ring
records, and the ring is filled from a fact, so **the change is what
arrives and the correspondence is the exception**. The *comment* is what
the third ring judges, and there is nothing in the file to judge, so
**the comment waits**: it sits on the unaddressed listing with the reason
that says whether nobody has answered it (`no_response`) or somebody has
put a link forward and nobody has judged it (`pending`).

**The judgement.** `record_response` takes a state, a decider and the
evidence behind it, and **a model may not decide one**. So the third ring
is filled by **a person or a rule**, and **the operator's step puts the
link forward instead**: `propose_responses` writes a `pending` link and
**has no state to decide it with**. That is structural, not a promise —
the operation that the operator's script calls cannot express a decision.

### 8.3 The two operations

| | |
|---|---|
| **`record_edits_from_revisions`** (`labcairn.papers.edits`) | reads the version's material through the reader, and writes **one `edit_actions` row per tracked change** — the actor from the roster, the edge the change travelled, the comment from the caller's answer, and a derived id (`ea-<revision event id>`) that names the change the row records |
| **`propose_responses`** (`labcairn.papers.responses`) | writes **one `pending` `response_links` row per proposed correspondence** — the id derived from the pair, so the same correspondence proposed twice is the same link |

**And what each of them refuses.** The first refuses a project, a version
or an edge that is not there, an edge that does not arrive at the version,
a roster that names a kind outside its vocabulary or a model carrying a
person's id, an author the roster does not name, an answer naming a
change or a comment the chain does not hold, and **a recorded change
whose actor, correspondence or edge contradicts what the roster now
says**. The second refuses a proposer that is not a person or a model, a
comment or a change the chain does not hold, a **correspondence that joins
two manuscripts**, and a correspondence that has already been judged.

**And the plan is made before anything is written.** Both operations check
everything first, so a refusal leaves nothing behind for a later commit to
pick up — the rule the reply's writer already follows.

**And a cursor left behind is not a change.** Word writes a revision with
no children under a run's or a paragraph's properties when an operation at
a point leaves one behind; it carries no judgement, and the chain records
changes and not marks. The rule that tells the two apart now lives in
`labcairn.papers.chain` — **below both the read layer and the writer** —
and both use that one copy.

### 8.4 The witnesses, and the mutations

**Thirteen mutations, and what each broke.** Each was applied to the source,
watched, and reverted; the two files' hashes were compared with the ones
taken before the first mutation and are equal.

| # | The mutation | What went red | What it tells you |
|---|---|---|---|
| 1 | the check that an answer names a change this version records is removed | `test_an_answer_must_name_a_change_and_a_comment_the_chain_holds` — *"DID NOT RAISE"* | an answer names a change the chain holds, and not a name that matches nothing |
| 2 | an author the roster does not name is given a default actor | `test_a_name_the_roster_does_not_name_is_refused_and_nothing_is_written` — *"DID NOT RAISE"* | **the default the design forbids**: a guess here is how a model's change becomes the advisor's |
| 3 | the cursor left behind is counted as a change | `test_a_cursor_left_behind_is_not_a_change` — *"assert 2 == 1"* | the chain records changes and not marks |
| 4 | the check that a recorded correspondence is not rewritten in place is removed | `test_a_recorded_change_is_not_rewritten_in_place` — *"DID NOT RAISE"* | a recorded fact is not rewritten in place, and the roster and the record cannot disagree |
| 5 | the proposal writes an `addressed` link with a decider and evidence | `test_a_proposal_is_put_forward_and_decides_nothing` — *"assert 'addressed' == 'pending'"* | **the operation that puts a link forward cannot decide one** |
| 6 | the check that a settled correspondence is not put forward again is removed | `test_a_settled_correspondence_is_not_put_forward_again` — *"DID NOT RAISE"* | a question that has an answer does not take a second one |
| 7 | the proposal's own checks are removed, so each proposal is checked as it is written | `test_a_proposal_about_a_row_the_chain_does_not_hold_is_refused` — *"a refused proposal writes nothing"* | **the whole plan is checked before the first link is written**: with the mutation the good proposal beside the bad one *was* written |
| 8 | the file's author name is copied into the row | `test_a_change_is_recorded_from_the_file_and_the_actor_is_the_roster_say` — *"assert 'Dr. Chen' == 'advisor-1'"* | the file's name is the key the roster is looked up by and never the value |
| 9 | the row's id stops naming the change it records | `test_a_change_is_recorded_from_the_file_and_the_actor_is_the_roster_say` — *"the row's id names the change it is"* | the id is what joins the row to the file's record — and to the file's name, which is how ADR-0016's forgery is caught |
| 10 | the retrieval's living states gain `pending` | `test_a_chain_of_pending_links_serves_no_rule_and_a_judged_one_serves_it` — *"a pending link is not an answer"* | **a pending link serves nothing** |
| 11 | the check that a link does not join two manuscripts is removed | `test_a_link_does_not_join_two_manuscripts` — *"DID NOT RAISE"* | a link across manuscripts joins two archives, and a chain that does that is a chain about nothing |
| 12 | the check that a recorded change keeps the edge it moved along is removed | `test_a_recorded_change_is_not_rewritten_in_place` — *"DID NOT RAISE"* | a change moves along one edge, and a version that is the child of two edges makes "the edge" a question with more than one answer |
| 13 | a person's proposal is graded `human_verified` instead of `observed` | `test_a_proposal_is_put_forward_and_decides_nothing` — *"a person's proposal is not an inference"* | a person's proposal and a model's inference are two different things, and the row says which is which |

**And mutation 10 was applied in memory, and this is said plainly because
it matters.** The rule that decides it lives in
`src/labcairn/guidance/retrieval.py` (`LIVING_STATES`), and
**`src/labcairn/guidance/` is outside this task's ownership map** — so the
file was **not edited**, and the mutation patched the module attribute the
retrieval reads, from a plugin outside the tree. **The tree stayed
byte-identical**; the witness went red on exactly the assertion it names.

**And the reviewer's own pass, from outside the tree.** The thirteen
mutations above were applied by the author of the code. **A second reader
applied them again**, from outside the worktree, with the tree rebuilt from
its own commit between each one — and the second pass found **four guards
that nothing watched**:

| The guard | What happens without it | The witness that watches it now |
|---|---|---|
| the edge must arrive at the version the change is in | a change is recorded on an edge that goes elsewhere | `test_a_change_must_travel_the_edge_it_is_recorded_on` |
| the edge must be of the change's own project | a change is recorded on another manuscript's edge | `test_a_change_must_travel_an_edge_of_its_own_project` |
| the version must belong to the project | a change is recorded under a project the manuscript is not part of | `test_a_change_is_recorded_against_the_project_its_manuscript_belongs_to` |
| the comment an answer names must be of that project | a change in one manuscript answers a comment in another | `test_a_change_in_one_manuscript_cannot_answer_a_comment_in_another` |

**With each guard made unable to fire, the whole file stayed green.** The
four witnesses above are new, and each of them reddens when its own guard
is gone — **one at a time, and each alone**.

**And the retrieval's own rule was mutated on disk this time**, not in
memory: `LIVING_STATES` in `src/labcairn/guidance/retrieval.py` was given
`pending`, and the witness that says a pending link serves nothing went red
on exactly its own assertion.

**And the decision of 2026-11-01, which the second pass turned up.** The
retrieval's own docstring said a re-judgement — *"the row's state,
changed"* — brings the rule back, and **no writer does that**:
`record_response` is insert-only. **The sentence had no carrying**, and the
test helper that re-judged a row in place — which the product cannot do —
was watching the product's absence rather than the product.

**The owner's ruling.** A judgement on the chain is a fact about what
somebody decided, and the chain is append-only: **a second judgement on
the same correspondence does not undo the first one**, so a source that
was judged answered stands. **A judgement that turns out to be wrong is
corrected on the rule** — withdrawn, disputed or superseded — and not on
the chain.

**And three things followed from it, and each is watched:**

| | |
|---|---|
| the retrieval's docstring | says that a judgement is a fact, that a second one does not undo the first, and that the correction is made on the rule |
| the column `response_links.decided_by` | says what it holds: the proposer on a pending link, the decider on a judged one, `None` when nobody has put the link forward |
| the witnesses | a source that does not stand is judged so **from the start** — the fixture asks for it — because the chain is append-only and a judgement is not rewritten in place |

**And the helper that re-judged a row in place is gone**, because it did
what the product cannot do and the witnesses it served were watching an
absence. `test_a_judgement_on_the_chain_is_a_fact_and_a_wrong_one_is_corrected_on_the_rule`
watches the behaviour that is real: a second judgement does not undo the
first, a withdrawn rule is not served, and a new version stands again only
once a second reader has confirmed it. **Four mutations were applied to it
and each reddened it** — the retrieval reading the latest judgement, a
withdrawn rule served again, a candidate served without a second reader,
and the fixture's judgement state ignored.

### 8.5 What filling the rings changes, and what the product says meanwhile

**And the retrieval's rule still holds.** It serves a confirmed rule on the
sources that are *addressed*, and reports the others with their reasons —
and **nothing about filling the rings changes that rule**. **The rings
change the chain's state, and the rule reads the chain's state**: a chain
with no links and a chain full of pending links both serve nothing, and
both are reported as withdrawn. **The difference between them is in the
chain's own listing**, which says `no_response` for the first and
`pending` for the second — and that difference is the whole of what this
section buys.

**What it changes.** Three things, and only the third is the one the work
order's material asks for.

1. **The chain can say who made the changes.** The second ring's rows name
   the actor in the chain's own vocabulary, and the row's id names the
   change it records — so a reader can join the chain's row to the file's
   record and to the name the file gives it. **That is where ADR-0016's
   forgery becomes visible**: a change recorded as the advisor's whose file
   says otherwise is now a two-row disagreement rather than a row nobody
   can check.
2. **The chain can say what it is waiting for.** A comment with a proposal
   and no judgement is on the unaddressed listing with the reason
   `pending`, and the proposal is on `response_links` for a decider to
   read. **A chain that is silent and a chain that is waiting are now two
   different facts.**
3. **The memory can serve the rule — once somebody decides.** That is the
   only thing that makes a rule servable, and **the operator's step cannot
   do it**.

**What the product says while the judgements are pending.** **It says the
comment is unaddressed, and it says why.** The chain's listing gives the
reason (`pending` rather than `no_response`), and the guidance memory
reports the rule as withdrawn with its source saying *found, reachable,
not addressed*. **It does not say the advisor's advice was wrong, and it
does not say it was right** — it says **nobody has judged it yet**, which
is the only true thing about a chain whose judgements are pending.

**And the honest limit: this does not make role B's card cite a rule by
itself.** The retrieval serves a confirmed rule only when a judgement says
`addressed` or `partially_addressed`, and **the operator's step writes
`pending` and cannot write anything else**. Before this section the
memory served nothing and said nothing; **now it serves nothing and says
what it is waiting for**, and the deciding is a person's or a rule's work.

### 8.6 What was deliberately not done

- **No model was allowed to decide, and no script was given the power to.**
  `propose_responses` has no state parameter; a proposal is `pending` and
  the operation cannot express a judgement.
- **No roster was persisted, and no name was inferred.** The roster is the
  operator's own input, supplied every time the ring is filled. **The
  chain stores the result of that judgement — the actor kind and a plain
  id — and not the roster itself**, and it stores no name.
- **No new table, no new migration, and no new test file.** The two
  operations live in the modules that already own those tables, and the
  witnesses extend `tests/test_feedback_events.py` — **so the shard table
  is untouched** (`tests/test_ci_shard_coverage.py` stays green, and the
  file's recorded cost is inside the partition's slack on both platforms).
- **No rule was written, and no correspondence was invented.** The
  material records *who* made a change; it does not record *which comment*
  a change answers, and **the operation does not guess**: the caller names
  the correspondence or the change is recorded answering nothing.
- **The corpus was not touched.** Nothing of the owner's manuscript — no
  comment, no revision, no author name, no file name — is in the tree or
  in this record.

### 8.7 The limits

- **The roster has no table of its own.** Its natural home is a per-project
  roster of the people a manuscript's files name — the thing that makes
  "whose change is this?" answerable once instead of every time. **The
  schema and the migrations are outside this task's ownership map**, so
  the roster is an argument the operator passes each time instead. **The
  chain holds the result of that judgement — the actor kind and a plain
  id — and not the roster**, and a roster that contradicts a row already
  written is refused rather than applied.
- **The second project in the pilot workspace cannot hold a second ring at
  all.** It has three versions and **no edge**, and an edit names the edge
  it moved along — so until that graph has edges, the operation refuses
  every version in it. **This is the graph's gap and not this section's**,
  and it is measured, not guessed.
- **A correspondence is fixed when the change is recorded.** The writer is
  insert-only — a second write with the same id returns the row that is
  there — so **the comment a change answers cannot be added later**. A
  further correspondence can live in `response_links`, which is
  many-to-many, but **the layer's `read_edits` reads the primary one only**,
  and so the mentor-trajectory role sees the primary correspondence.
- **A judgement is a second row, not an edit of the first — and that is
  now the design, not only the writer's shape.** The pending link stays
  pending, and the judgement is written under a caller's id. **The owner's
  ruling of 2026-11-01** is that the chain keeps what was judged and the
  correction is made on the rule, so the retrieval's docstring no longer
  describes a row's state being *changed*: it says a judgement is a fact
  and a second one does not undo the first. **What the ruling costs is
  named in §8.4**: a source that was wrongly judged answered cannot be
  withdrawn on the chain, and the rule that stands on it has to be
  withdrawn instead.
- **On a pending link, `decided_by` names who put it forward, and the
  column now says so.** The model's candidate — which the writer already
  had — carries `decided_by='model'`, and a person's proposal follows that
  case. **The column's own docstring said `None` while the link is
  pending**, and the writer wrote a proposer there anyway; the two
  disagreed, and **the docstring is now the one that says what the row
  holds**: the proposer on a pending link, the decider on a judged one,
  and `None` when nobody has put the link forward.
- **The guidance memory's invalidation does not say why a source died.**
  It says *not addressed*; the chain's own listing says *pending* or *not
  addressed*. **The two answers are at different levels and the product
  shows both.**
- **The layer's `read_edits` carries the actor's *kind* and not the
  actor's handle.** The handle is the operator's own bookkeeping, and the
  trajectory panel therefore shows *the student* and not *which* student.
  **Adding the handle would change the shape of a published API response**,
  and `src/labcairn/api/` is outside this task's ownership map — so it is
  not added here, and it is the API's owner to ask for it.
- **A revision the file gives no author cannot be recorded**, and the
  operation refuses rather than guessing. A corpus with unattributable
  revisions needs a different answer, and this one says so.
- **The mutation pass covers the claims this section makes.** The clauses
  of §3 above are the reviewer's (§4), and the eleven of them with no
  mutation recorded are still not covered.

### 8.8 What was measured

**The whole suite**, on Windows 11 (AMD64), Python 3.12.13, on the tree this
record was written at:

```
4454 passed, 5 skipped, 0 failed, in 38 minutes 39 seconds
```

**The five skips are the project's own accepted kinds** — a POSIX
permission-bit case, the real-provider smoke that needs the owner's
credential, a Windows drive form that is meaningless on POSIX, and two
8.3 short-name cases this machine's volume cannot carry — **and none of
them is about this section.**

**The chain's own file**: `tests/test_feedback_events.py` — **39 tests,
green**, 24.8 seconds on this machine.

**And the lint and the types**: `ruff check .`, `ruff format --check .` and
`mypy --strict` are clean.

**And how the suite was launched, because in a worktree it matters.** A
worktree's tests must import the *worktree's* code, and the editable
install in this virtualenv points at the main checkout — so the worktree's
``src`` goes first on ``sys.path`` **and on ``PYTHONPATH``**, so the
nested pytest runs the suite spawns see it too. **Two end-to-end files
must not see it**: the outsider's walk asserts that the *clone's* code
runs, and the wheel test asserts that the *installed* wheel is what gets
imported — **and a CI runner has no ``PYTHONPATH`` at all**. **Those two
files were therefore run without the variable**, and they are green.

**And this is said because it cost a run to find out.** **The first
whole-suite run put the worktree on ``PYTHONPATH`` for everything, and six
tests failed for that reason and no other** — the walk imported the
worktree's ``src`` instead of the clone's, and the wheel test found the
worktree's ``src`` instead of the wheel it had just installed. **Both
failures name the worktree's own path**, which is what gave them away.
**The second run reproduced a CI runner's environment** — the worktree on
``sys.path`` and on the variable, and the two clean-room files without it
— and it is green.

**And the shard table is not touched.** The file's recorded cost is
8.57s on Ubuntu and 66.65s on Windows, and the partition's slack is
87.1s and 400.3s — **so the file is inside the slack on both platforms**
and `tests/test_ci_shard_coverage.py` asks for no re-measurement. The
recorded costs are runner-measured and **this section does not re-measure
them**: it changes no test file's membership, only its content.


---

## 9. The rings filled on the pilot's own workspace

**What this section is.** §8 says what the two operations are. **This
section says what happened when the operator's step was actually run**,
on the owner's own pilot workspace, and **what the memory serves
afterwards** — which is the question §8 could not answer.

**Nothing here is a claim about the owner's manuscript.** The counts, the
issue keys and the states are facts about the chain; no comment's words
and no manuscript's text appear in this record or in the tree.

### 9.1 What the chain holds now

| | rows |
|---|---|
| `feedback_events` | 80 |
| `revision_events` | **1528** |
| `edit_actions` | **1439** |
| `response_links` | **32** — 2 `addressed`, 8 `not_addressed`, 22 `pending` |
| `guidance_rules` | 16 (all confirmed) |
| `guidance_rule_sources` | 32 |

**The two middle rings were empty when this work order started, and they
are not empty now.** The second ring holds **one row per change the
files record**, and the third holds **the correspondences and the
owner's judgements of them**.

### 9.2 How the second ring was filled, and what it took

**The facts come from the files, and the names come from the operator.**
Every version of the first paper whose file records changes was
recorded on the edge that arrives at that version, with the actor the
roster names — **and the change rows carry no comment of their own**,
because the correspondence is a judgement and it lives in
`response_links`, which is many-to-many. **A paragraph of forty-three
changes can answer four comments, and the change row has one column for
it.**

**And the empty markers are not in the count.** Of the 1528 recorded
changes, **89 are `empty_marker`** — the marks an operation at a point
leaves behind — and the chain records changes and not marks.

### 9.3 What the operator could put forward, and what the owner judged

**Twenty-two correspondences** were put forward, each a `pending` link:
a comment and the change in its own paragraph. **That is the whole of
what the material supports** — the file does not say which change
answers which comment, and a paragraph is the finest address both sides
have.

**And the owner judged the ten that a confirmed rule was waiting on.**
Two hold, eight do not:

| | |
|---|---|
| `iss-v03-copy-chinese-draft-116` | **addressed** — the comment asked for the background to bring out the bubbles' features, and the change moved that passage away |
| `iss-v04b-variant-2-copy-chinese-draft-60` | **addressed** — the comment said the passage does not apply before the data, and the change deleted the words that put it there |
| the other eight | **not_addressed** — the change in the same paragraph was not an answer to the comment |

**The twelve proposals no rule was waiting on were not put to the
owner**, and they stay `pending`, which is exactly what the chain says
about them: somebody put them forward and nobody has judged them yet.

### 9.4 What the memory serves, and what it does not

**Before this, the memory served nothing**: `search_rules` returned no
rule at all, and `invalidated_rules` reported every one of the sixteen
confirmed rules as withdrawn.

**After the owner's judgements it serves one** —
`rule-6cc14b60015b7945` (`introduction_and_storyline`), on the two
sources that were genuinely answered — **and it reports the other
fifteen**, each with its sources' reasons.

**One rule out of sixteen, and that is the honest number.** The material
says that of the mentor's forty-six comments on the first paper, the
ones a later version really answered are few. **The retrieval asks
whether a judgement says the change answered the comment, and on this
material most of them did not.** A memory that served all sixteen would
be serving rules the chain cannot show to have been applied — which is
the difference between **absorbing** the mentor's judgement and
**arranging** it.

**And the second paper contributes none of them.** Its three versions
have **no version edge** — the material does not say which came first,
so the chain does not order them — and a change travels an edge, so the
operation refuses every version in it. **Its fourteen rule sources have
no candidate either**: the changes in its files sit in paragraphs its
comments do not. **So the eight rules distilled from it stay unserved,
and the memory says so.**

### 9.5 A defect the ruling exposed, and the fix

**The owner's ruling made the listing lie.** The chain is append-only,
so the proposal that led to a judgement stays on the chain after
somebody has judged it — and the listing read the states in the order
they arrived, so **a comment somebody had judged unanswered was
reported as "a judgement is outstanding"**. **On the pilot's workspace,
eight judged comments were called pending.**

**A judgement now outranks a proposal**: the reason is `not_addressed`
when somebody has judged the correspondence and not answered, and
`pending` only when nobody has. **The comment stays on the listing
either way** — judged or not, it is unaddressed. The witness is
`test_a_judged_comment_is_listed_as_judged_and_not_as_waiting`, and the
mutation that puts the old order back makes it red.

### 9.6 A finding that belongs to the reader, not to this section

**The reader records one change twice in one file.** On the first
paper's fourth version, the reader reports **243 changes and there are
239** — four of them are read a second time. **The chain does not lose
anything**: the revision event's id is derived from the element's path,
so the second reading lands on the row the first one wrote, and the
table holds 239. **But the assumption the id rests on is false as
written** — *the element's path is unique inside a part* — and it holds
only because the four duplicates are the same change. **Two different
changes sharing a path would lose one of them silently**, and the
witness for that belongs to LC-P2-07.

## 10. The settlement over a reply: the judgement that an answer settled a point

**What this is.** LC-P2-13's half of the peer-review loop. The reply
(recorded in §6) is a record of what was said, and a record still needed
the judgement over it: *did the authors' answer settle the reviewer's
point, on what evidence, and where in the manuscript the change it
claims lives*. That judgement is the `reply_settlements` table
(migration 0020) and the operation `settle_reply`, with the two listings
`list_reply_settlements` and `list_unsettled_replies` — all in
`src/labcairn/papers/replies.py`, beside the record they judge.

### 10.1 The decisions, and where each is held

| The decision | Held by | Witnessed by |
|---|---|---|
| **The verdict is a row of its own, never a column on the reply** — a record of what was said must not be readable as a ruling | `ReplyRow`'s columns are unchanged; the judgement lives in `reply_settlements`, and the reply's table still carries no state, no decider and no evidence | `test_a_reply_is_a_record_and_not_a_verdict` (unchanged; the reply's shape is the same as §6 recorded it) |
| **The judgement goes through the same door as `record_response`** — a state other than `pending` needs a decider and evidence, and a model may put a settlement forward but may not decide one | `settle_reply`'s discipline checks, plus the schema's `reply_settlements_a_judgement_names_its_decider_and_its_evidence`, `..._a_model_may_not_settle` and `..._an_inferred_settlement_is_a_candidates` | `test_a_judgement_the_door_refuses_never_reaches_the_store` |
| **A response that claims an experiment the manuscript does not contain is not marked done** — refused or held, by name | A settled settlement names its `claim_terms`, and the operation reads the manuscript's accepted text and checks every one before the row is written; a claim that is not found is refused with the term named (`ChainRefusal.CLAIM_NOT_IN_MANUSCRIPT`), and the caller's honest path past the refusal is `held` with a named `hold_reason` | `test_a_settlement_whose_claim_the_manuscript_does_not_hold_is_refused_by_name`, `test_an_answer_whose_claim_cannot_be_found_is_held_by_name` |
| **Acceptance is not proof the advice was scientifically right** | What `settled` says is exactly what the operation checked — the claimed terms are findable in the manuscript's accepted text. No column in the table carries a wider claim, and the row's docstring says so | the same settled-judgement witness, whose docstring states the boundary |
| **An unanswered point stays unanswered** — an answer that was never judged does not make the point answered | `list_unsettled_replies` lists a reply with no settlement as `unjudged` and a pending one as `pending`; only `settled` keeps a reply off the listing | `test_an_unjudged_reply_stays_on_the_unsettled_listing` |
| **A review point is located in the response and, if it can be, in the change** — a missing address is a value, never a guess | The settlement carries `anchor_status` (`resolved`/`unknown`, the chain's own vocabulary), and the schema holds the two address columns to agree with it in both directions (`reply_settlements_an_address_is_a_value_not_a_guess`); a resolved address is checked against the manuscript's own length | `test_a_settlement_places_the_change_or_says_it_could_not` |
| **A conflict between the advisor's view and the settlement's is shown as two sides, not resolved by recency** | The correspondence with a chain comment is part of the judgement (`feedback_id`, given by the decider, never inferred), and the listing joins **every** state the chain holds for that comment into `chain_states` | `test_a_disagreement_between_the_chain_and_a_settlement_is_shown_as_two_sides` |
| **A point is judged once** — a judgement is a fact, and the store holds no revisions of facts | `reply_settlements.reply_id` is unique; a judged reply is refused rather than judged again, and a pending settlement is completed under the name it was put forward with | `test_a_reply_that_has_already_been_judged_is_not_judged_again` |
| **The schema refuses what the writer would have to be trusted not to write** | Nine forbidden rows written raw — a settled settlement with no claim, one with no address, an unknown that names a place, a hold with no reason, a judgement with no decider, a model's verdict, a pending settlement carrying a decision's trappings, an anchor status outside its vocabulary, a state outside its vocabulary — and a second judgement over one reply | `test_the_store_refuses_a_settlement_the_schema_forbids` |

### 10.2 The mutations, and what each broke

**Eight mutations applied, watched, and reverted.** Each was applied to
the source, the named witness was run alone, and the working tree was
restored from the commit taken before the first mutation.

| # | The mutation | What went red | What it tells you |
|---|---|---|---|
| 1 | the claim-findability check returns "nothing missing" whatever it reads | `test_a_settlement_whose_claim_the_manuscript_does_not_hold_is_refused_by_name` — *"DID NOT RAISE"* | an answer's claim is checked against the manuscript before the row is written, not reported beside it |
| 2 | the operation's own judgement-discipline block is short-circuited (`elif False`) | `test_a_judgement_the_door_refuses_never_reaches_the_store` — refused `CHAIN_SETTLEMENT_NEEDS_EVIDENCE`, got `IntegrityError` | **the door refuses first, saying why** — the schema holds the same line, but an `IntegrityError` is a refusal nobody can act on |
| 3 | the unsettled listing's state set drops `pending` | `test_an_unjudged_reply_stays_on_the_unsettled_listing` — the pending reply is not on the listing | an answer that was never judged does not make the point answered |
| 4 | the resolved address's range check is short-circuited | `test_a_settlement_places_the_change_or_says_it_could_not` — *"DID NOT RAISE"* at the out-of-range paragraph | an address the manuscript does not have is not an address |
| 5 | the listing's chain-side join keeps only the newest link's state | `test_a_disagreement_between_the_chain_and_a_settlement_is_shown_as_two_sides` — *"assert 1 == 2"* | **both sides are shown, and the newer one is not picked** |
| 6 | the already-decided check is short-circuited | `test_a_reply_that_has_already_been_judged_is_not_judged_again` — *"DID NOT RAISE"* | a judgement is a fact, and the store holds no revisions of facts |
| 7 | the migration's `reply_settlements_an_address_is_a_value_not_a_guess` CHECK is deleted | `test_the_store_refuses_a_settlement_the_schema_forbids` — *"DID NOT RAISE"*: the forbidden row was written | the schema holds the address to the status in both directions, and the parity test holds the model and the migration together |
| 8 | the operation-layer `held`-reason check is short-circuited | **survived** — the schema's `reply_settlements_a_hold_names_what_it_holds` refuses the row instead, and the held witness (which records a well-formed hold) stays green | recorded rather than counted: the hold's *bottom line* is the schema's, and mutation 2's witness covers the door's own voice. **A hold without a reason is still unrecordable** |

### 10.3 What was measured

See §10.5.

### 10.4 What was deliberately not done

- **No trajectory event.** A chain judgement emits one
  (`emit_response_recorded`, `emit_followup_assessed`); a settlement
  emits none, because `src/labcairn/runtime/trajectory.py` is outside
  this work order's file-ownership map. **A settlement is therefore not
  replayable from the event stream** — the same debt 0019 recorded for
  the reply, and the fix is the same shape: an event type when the
  stream's fifth object is wanted.
- **No `propose_reply_settlements`.** The chain's correspondence has a
  batch proposal operation (`propose_responses`) because the operator's
  step puts correspondences forward in bulk; the work order names no
  such step for settlements, and `settle_reply`'s `pending` state is
  the single forward a caller needs. A bulk forward is a small
  addition to an existing door, not a design.
- **No claim extraction.** `claim_terms` are given by the caller and
  checked mechanically; the product does not read "we ran X" out of the
  answer and guess what X is. **A rule that guesses the claim would be
  a rule that can be wrong in a way nobody named** — the caller says
  what is claimed, and the product says whether the manuscript bears it
  out. A model's reading of an answer belongs in the caller's hands,
  at grade `inferred`, subject to the same door.
- **The word-level findability is deliberately plain.** A claim term is
  found when its words appear in the accepted text, case-folded, with
  no guess at morphology. A paraphrase the manuscript makes in other
  words will not be found — **and that failure is on the safe side**:
  it holds or refuses rather than settling.

### 10.5 What was measured

*pending the full suite run; filled in below.*

