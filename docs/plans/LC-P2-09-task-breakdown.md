# LC-P2-09 — The feedback chain: from a comment to what decided it — task breakdown

**Work order:** LC-P2-09 (feedback, response and follow-up) · **ADR:**
[`ADR-0017`](../adr/ADR-0017-feedback-chain.md) · **Status:** implemented
2026-10-30 (T00–T07); the acceptance record is
[`LC-P2-09-acceptance`](../acceptance/LC-P2-09-acceptance.md).

## 0. How to read this document

**This is a contract, not a suggestion.** §4 names the acceptance clauses
and, for each, the test that carries it; a work order that ships without
those tests has not met the contract, whatever the suite says. The names in
§4 are the task breakdown's, and the tests are renamed to match it —
**the breakdown is the contract and the implementation is supposed to meet
it**, not the other way round.

**§2 holds the three decisions that shape the work.** A decision is a
decision about what the tables *mean*; where the design says a thing may
not be decided by the system, the schema refuses it, and where it says a
thing is unknown, the unknown is a value.

**Every claim needs a witness, and the witness must fail when the property
breaks.** That is the project's own rule, and §4's last paragraph says what
to do about it.

## 1. Goals and boundaries

### 1.1 What LC-P2-09 must produce

**The chain, as a thing that can be traversed and questioned:**

| | |
|---|---|
| **A question** | `FeedbackEvent` — a comment found in a manuscript, with **both** of its addresses: where the advisor wrote it and where they wrote it about |
| **An edit** | `EditAction` — a change made in answer to it, naming **who made the change** |
| **A response** | `ResponseLink` — the judgement that the change answered the comment, **and the evidence that decided it** |
| **A later assessment** | `FollowupAssessment` — a judgement about the issue, with its own evidence, and the ability to say *"not established"* |

**And the chain's replayability**: four annotation events on the event
stream, each with a registered payload schema, so that the report's hash
chain covers what happened and when.

**And the thing the chain cannot be without**: a way to **store** a
version and an edge. LC-P2-08 landed the contracts and the checks; the
persistence layer is not in the tree, and an edit that names an edge which
cannot exist is a reference to nothing.

### 1.2 Already done — removed from scope

- **LC-P2-07's reader** reads the comments, the revisions, and the two
  views, and reports an unanchorable comment with its body and a named
  reason rather than dropping it. **The reader is not re-read here.**
- **LC-P2-08's contracts** — `PaperVersion`, `VersionEdge`,
  `StageCandidate`, `VersionStatus`, `EdgeSource`, `ConfirmationOutcome`,
  `confirm_edge`, `propose_alignment`, `check_edge_within_project`,
  `check_duplicates`, `check_missing_rounds` — are **the shapes this work
  order refers to and does not redefine**.
- **ADR-0014's** evidence grades, its view-in-the-address rule, its
  anchoring, and its new-table rule.
- **ADR-0016's** six-state machine, its `model_proposal` creator, and its
  prohibition on a model's output being recorded as a person's.
- **ADR-0015's** gates, and the consent vocabulary LC-P2-06 landed.

### 1.3 Explicitly not in scope

- **A model's own advice.** LC-P2-12's guidance cards are a different
  object, and ADR-0016 owns them. This work order's first link is the
  **advisor's comment**; a model may *act* on the chain (D4's `model`
  actor kind), and it does not get to *originate* it.
- **The model call itself.** LC-P2-01's path, with its approval, its
  egress grant and its transcript.
- **Identity.** ADR-0015 D6's conditions — the identity model, the audit
  trail, the withdrawal-deletion consistency check — are open. This work
  order records **kinds** of actor (`student`, `advisor`, `model`,
  `human`) and, where a person is named, a plain id; it does not decide who
  a person is.
- **The report's rendering of the chain.** Whether the chain is shown, and
  what a reader sees, is the owner's; the tables must not assume an
  answer.
- **Real material.** Everything measured here is synthetic, for the same
  reason LC-P2-06's is: **the corpus is the pilot's job, and a fixture
  that pretends to be a manuscript is a fixture that tests the fixture.**
- **Choosing the advisor's advice.** The chain records what was answered
  and by what evidence. It does not say whether the advice was good — see
  §2.3.

## 2. The three decisions that shape it

### 2.1 A feedback is an observation, and it has two addresses

**A comment is not a claim.** It is the fact that a person wrote these
words at this place. The ledger's vocabulary has no state for that, and
borrowing one would put a comment into the same denominator as a verified
number.

**Two addresses, because two questions.** `comment_locator` names the
comment element in `word/comments.xml` — *what was written*. The body-side
anchor — paragraph and offsets — names *where it was written about*. The
reader already keeps them apart, and a row that kept only one would answer
only one question.

**And the offsets are in the baseline's text.** The reader's anchor offsets
are into the paragraph's **rejected** view — the manuscript before the
revisions — while a version edge points at a later version. So the
feedback row **names the version it was written against**, and the edit row
names the edge that moved away from it. **That correspondence is the thing
that is easy to get wrong and impossible to assume.**

**Unknown is a value.** No author, no date, an unpaired range: the reader
reports `None` and a reason, and the row inherits that rather than
re-deciding it.

### 2.2 A response is a judgement with evidence, not a status

**The work order's hardest clause:** *"an unaddressed comment is not
reported as addressed, and neither is a wrong response or a partial one."*

So a link between a comment and a change carries a **state** and, for every
state other than `pending`, **the evidence that decided it** — a rule's
log, a person's attestation, a set of evidence rows. **A judgement with no
evidence behind it is refused by the schema**, because a status anybody can
set is not a status.

**And the four states are not the same claim.** `not_addressed` says the
change did not help; `partially_addressed` says it helped with part; only
`addressed` says the comment was answered. **The first two are records of
something that happened** — the student did something, and the record says
it did not answer — and a chain that only knew about "answered" would have
to either hide them or call them successes.

**A recurrence is recorded, not inferred.** Two comments are about the same
problem when somebody says they are, through an `issue_key`. **The same
wording is not the same issue**, and inferring it from similarity is the
thing ADR-0014 already refused to do for version order.

### 2.3 "The change was accepted" is not "the advisor was right"

**The design's hard line, and the one this work order is most likely to
break by accident.** The student's change was accepted; the advisor's
advice was correct. **These are different claims, and the second needs its
own evidence.**

So an assessment carries its own evidence and its own grade, and it can
say **"not established"** — the way `VerificationStatus` can be
`unsupported` and `conflicted`, and the way `StageCandidate` has an
`UNKNOWN` member. **An assessment that derives the advisor's correctness
from the change's acceptance is refused**, and the refusal is a fact about
the row rather than a convention nobody keeps.

**And who made the change is a first-class fact.** ADR-0016 names
*model → accepted change* as the third of its three promotion paths: a
model rewrites the manuscript, the change is recorded, and it is
attributed to the advisor. The schema would be satisfied, the report would
cite an address, and **nothing would say the sentence was invented.** The
`actor_kind` column is what makes that impossible to write by accident.

## 3. The work

### T00 — The version graph's writer

**Files:** `src/labcairn/db/repository.py`, `src/labcairn/application/papers.py`
(new), `tests/test_version_store.py` (new).

**Nothing in `src/` stores a `PaperVersion` or a `VersionEdge`.**
`confirm_edge` builds in-memory edges; `propose_alignment` builds a
proposal; the tables exist with no writer. **This subtask is first because
every other one refers to an edge**, and an edge that cannot exist is a
reference to nothing.

**What it must do:** store a `PaperVersion`, store an edge, read them
back, and **round-trip them through the models' own checks** — the
cross-project check (`check_edge_within_project`), the three facts that
stay apart (a human source needs an acceptor; an accepted edge needs an
acceptor *and* a moment), and the forbidden self-parent. **The store
refuses what the model refuses**, and a row that the model would refuse is
not written.

**And it must not become a second implementation of the checks.** The
models are the checks; the store's job is to write what they accept.

### T01 — The feedback row, and its two addresses

**Files:** `src/labcairn/db/models.py` (`FeedbackEventRow`), a migration,
`src/labcairn/papers/feedback.py` (new), `tests/test_feedback_events.py` (new).

**What it must do:** read a DOCX, take its `CommentEvent`s, and write a
`FeedbackEvent` per comment carrying the comment's own `DocxLocator`, its
body-side anchor, the **text the anchor names** and that text's hash, the
author and the date (or their unknowns), and **the version the comment was
written against**.

**And the text is the part the reader does not carry today.**
`CommentAnchor.text` is `""` on every path, so the first link of the chain
is currently empty. The row carries the text **and its hash**, and the
hash is what makes drift detectable — an anchor whose text no longer
hashes to what was recorded is **stale**, and a stale anchor is reported
as stale rather than silently re-pointed.

**And a comment that cannot be anchored is still written**, with its body,
its author and its unknown anchor and the reason — because **a comment the
reader could not place is a comment a person still wrote.**

### T02 — The edit, and who made it

**Files:** `src/labcairn/db/models.py` (`EditActionRow`), a migration,
`src/labcairn/papers/edits.py` (new), `tests/test_edit_actions.py` (new).

**What it must do:** record a change made in answer to a feedback — the
`feedback_id` (nullable: a change may answer nothing), the
`version_edge_id`, the `actor_kind` (`student | advisor | model |
human`), the `actor_id` where there is one, and the **grade**
(`observed | inferred | human_verified`).

**The `actor_kind` is the point of the table**, and the witness must fail
when it is wrong: a change the model made is recorded as the model's, and
a change the advisor made is recorded as the advisor's. **There is no
default actor**, because a default is how a model's change becomes the
advisor's.

### T03 — The response, and the evidence behind it

**Files:** `src/labcairn/db/models.py` (`ResponseLinkRow`), a migration,
`src/labcairn/papers/responses.py` (new), `tests/test_response_links.py`
(new).

**What it must do:** link a `feedback_id` to an `edit_action_id` and carry
the judgement — the state (`pending | addressed | partially_addressed |
not_addressed`), who decided it, when, and **what evidence decided it**.

**And the state cannot be reached without that evidence.** `pending` is the
default and the only state a row may hold without a decision; the other
three require `decided_by` and the evidence, and **the schema refuses a
judgement with no evidence behind it.**

**And the listing is the other half of the clause.** A comment with no
response is **listed as unaddressed** — not as addressed, and not absent
from the listing. A reader asking "what has not been dealt with?" must get
an answer from the store, not from a query the caller has to write.

### T04 — The recurrence, and the later assessment

**Files:** `src/labcairn/db/models.py` (`FollowupAssessmentRow`), a
migration, `src/labcairn/papers/assessments.py` (new),
`tests/test_followup_assessments.py` (new).

**What it must do:** carry an `issue_key` on the feedback row — a
person-given key for "the same problem" — and make a **recurrence
visible**: two feedback rows in one project with the same key in
different versions are one recurring issue. **And no key is inferred from
the text**, and a comment with no key is uncategorised rather than
guessed at.

**And the assessment:** a later judgement about an issue, with its own
evidence, its own grade, and the ability to say **"not established"**.
**An assessment that says the advisor was right because the change was
accepted is refused**, and the refusal is a fact about the row.

### T05 — The four chain events

**Files:** `src/labcairn/runtime/event.py` (`EventType`),
`src/labcairn/application/papers.py` (the emitters), the payload schemas,
`tests/test_feedback_events.py`.

**What it must do:** add `feedback_recorded`, `edit_action_recorded`,
`response_recorded` and `followup_assessed` as **annotations** — no
transition, no `run_id` — with a **registered payload schema** naming the
row each is about. The anti-bag rule refuses a payload for an unregistered
type, and **a chain whose events name nothing is a chain nobody can
replay.**

**And they are not the links.** The links are the foreign keys between the
four tables; the events say that the chain happened.

### T06 — The end-to-end demonstration

**Files:** `examples/feedback_demo.py` (new), `tests/test_feedback_demo.py`
(new).

**The same shape as LC-P2-06's and LC-P2-08's:** a comment found in a
synthetic DOCX, an edit made in answer to it, a response that is
**refused** for want of evidence, a response that is recorded with its
evidence, a recurrence of the same issue in a later version, and a
follow-up assessment that says **"not established"**. **Every claim is
carried by a `check()` that raises**, and a test runs the demonstration —
because a demonstration nobody runs is one that quietly stops working.

### T07 — What the tables cost, and the acceptance record

**Files:** `docs/acceptance/LC-P2-09-acceptance.md`, `.github/ci-shards.json`.

**And the shard costs**, by the two-step process the Phase 2 evidence pack
records — the first run apportions, the second measures. **The number in
the table comes from the runner**, and the first run's number is labelled
as what it is.

## 4. Acceptance, mapped to where it is carried

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

**Every one of these needs a witness, and the witness must fail for the
property.** A test that goes red because of an unrelated encoding or lint
matter is not a witness of that property; when a test goes red, ask what
made it red before believing that it caught something. **And a mutation
that was never applied is reported by anyone who does not check as a
surviving mutation**, which looks exactly like a success — so check the
diff before you believe a green result.

## 5. What this work order cannot deliver, and why

- **It does not say whether the advisor was right.** It says what was
  answered, by what evidence, and what a later assessment concluded. The
  correctness of the advice is a claim about the science, and it is not
  derivable from the process.
- **It does not render the chain.** The tables hold it; whether a report
  shows it, and what a reader sees, is the owner's decision.
- **It does not identify people.** It records kinds of actor and plain
  ids; ADR-0015 D6's conditions are open and are the acceptance list for
  the moment the pilot opens beyond the administrator.
- **It does not let a model originate guidance.** LC-P2-12 owns that, and
  ADR-0016 owns the promotion rules.
- **It does not find the changes a student made without recording them.**
  A change with no recorded edit is a change the chain does not know
  about, and the chain reports what it holds rather than what it wishes
  it held.
- **It does not merge rounds.** Two documents revised at once are two
  rounds, and the recurrence's scope is the project — see ADR-0017's
  re-evaluation trigger.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `src/labcairn/application/papers.py`, `tests/test_version_store.py` | `src/labcairn/db/repository.py`, `src/labcairn/db/models.py` |
| T01 | `src/labcairn/papers/feedback.py`, `tests/test_feedback_events.py` | `src/labcairn/db/models.py`, `migrations/versions/`, `src/labcairn/material/ooxml.py` |
| T02 | `src/labcairn/papers/edits.py`, `tests/test_edit_actions.py` | `src/labcairn/db/models.py`, `migrations/versions/` |
| T03 | `src/labcairn/papers/responses.py`, `tests/test_response_links.py` | `src/labcairn/db/models.py`, `migrations/versions/` |
| T04 | `src/labcairn/papers/assessments.py`, `tests/test_followup_assessments.py` | `src/labcairn/db/models.py`, `migrations/versions/` |
| T05 | — | `src/labcairn/runtime/event.py`, `src/labcairn/application/papers.py`, `tests/test_feedback_events.py` |
| T06 | `examples/feedback_demo.py`, `tests/test_feedback_demo.py` | — |
| T07 | `docs/acceptance/LC-P2-09-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**The shared files, and why they are shared.** `src/labcairn/db/models.py`
holds every table, so **only the migration subtasks write to it, and they
write it in one pass** (T01–T04 are one schema decision and four tables;
splitting the migration across four subtasks would mean four migrations
for one design). `src/labcairn/material/ooxml.py` is touched by T01 and
only by T01 — and **only to carry the anchored text the reader does not
carry today**, which is a change to what the reader returns and therefore
to LC-P2-07's own witnesses.

**And the migration number follows LC-P2-11's**, or whatever is next in
the sequence at the time this work order is dispatched.

## 7. What "done" means

1. A version and an edge can be **stored**, and a stored edge round-trips
   through the models' own checks.
2. The seventeen acceptance clauses above have a named test each, **and the
   tests are named as the table names them**.
3. The demonstration runs, and **a test runs it**.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-09-acceptance.md` names the
   commit every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md) —
   the review happens after the merge, so what to break has to be written
   down while the work is being done.
7. **Every claim in §2 has been mutation-checked**: the property broken,
   the witness red, the tree restored.
