# ADR-0017: The feedback chain — a comment, the change it prompted, and what decided it

**Status:** Proposed
**Work order:** LC-P2-09 (proposed; not yet dispatched).
**Date:** 2026-10-30

## Context and concrete problem

Phase 2's product goal is a system that gives a researcher guidance on a
manuscript it has never seen, grounded in real revision histories, and
honest about what it does not know. The deliverable is not a chatbot that
sounds like the advisor; it is a **replayable, verifiable, refutable chain
of guidance**.

That chain has five links, and the work order names them: *问题 → 指导意见 →
修改行动 → 修改后的证据 → 后续评价* — **a question, a piece of guidance,
an edit, the evidence after the edit, and a later assessment.**

Four facts in the tree shape what is possible, and two of them are gaps.

**First: the advisor's comments are already read.** LC-P2-07's OOXML reader
finds `w:commentRangeStart`/`w:commentRangeEnd` and returns a
`CommentEvent` (`material/ooxml.py:196`) carrying Word's own `comment_id`,
the author, the date, the body, the anchored text's hash, and **two**
addresses: `locator` — a `DocxLocator` into `word/comments.xml`, naming
the comment element itself — and `anchor`, a body-side coordinate of
`paragraph` plus character offsets. The reader never drops a comment: an
unanchorable one comes back with `status="unknown"` and a named `reason`,
and each of the four failure modes (never opened, never closed, no range,
spanning paragraphs) has its own code and its own wording. The unknown is
`None` plus a reason, **never a guess** — an unreadable date is not a date.

**Second: the edits are already a graph.** LC-P2-08's `paper_versions` and
`version_edges` hold a version graph rather than a list: the parent lives
in the edge, an edge carries how it was decided (`evidence | human |
model`), a confidence, evidence spans and an acceptor, and **a confidence
is not a decision**. `confirm_edge` produces a new edge on a correction and
**never overwrites**; a rejection is recorded as a rejection.

**Third: the evidence ledger already knows the difference between a
proposal and a fact.** `EvidenceCreator` has three members and the third,
`model_proposal`, exists so that a future proposal path is expressible.
`VerificationStatus` is a **six-state** machine — `planned`, `extracted`,
`verified_by_rule`, `user_attested`, `conflicted`, `unsupported` — and the
negative states exist so that "a paraphrase is not a quote" and "neither
side wins by recency" can be *displayed* rather than argued. ADR-0016 D1
and D2 make the rule explicit: **a model's say-so is a proposal, and only
a rule or a person can promote it.**

**Fourth, and this is the gap: nothing joins them.** There is no feedback
table, no link between a comment and the edit it prompted, no
representation of the same issue recurring, and no record of what decided
that a comment had been answered. The reader produces comments; the version
graph produces edges; the ledger produces records. **The chain between
them is a diagram in a design document and nothing else.**

**And the first link of the chain is empty.** `CommentAnchor.text` is
**always `""`** — every return path in the reader passes `text=""`
(`ooxml.py:766-773`, `789-796`, `812-819`, `838-845`), including the
resolved one. The anchor's coordinates are usable; **the text it names is
not carried.** And the anchor's offsets are into the **rejected
(baseline)** text of the paragraph, while the version graph's edges point
at later versions — so the coordinate a comment names and the version a
change produced are in **two different coordinate systems**, and nothing
records the correspondence.

## The concrete problem this creates

The phase's exit gate is *"measured capability gain against a frozen P1
baseline, no scientific-claim inflation"*. A feedback chain is where
scientific-claim inflation would be easiest and hardest to see.

A comment arrives from a Word file. A student edits the manuscript. Some
weeks later the advisor looks again. The questions a reader needs answered
are ordinary, and every one of them is currently unanswerable:

- **Where was this comment?** It must resolve to an address — and an
  address that names a view, because the same characters mean different
  things in the accepted and the rejected view (ADR-0014 D4a).
- **What did it prompt?** The change it prompted, if any.
- **Was it answered?** And **answered *correctly*** — because *"the student
  changed the text"* is not *"the student fixed the problem"*. The work
  order is explicit: **an unaddressed comment is not reported as
  addressed, and neither is a wrong response or a partial one.**
- **What decided that?** The response state must name **what evidence**
  decided it. A status with no evidence behind it is a status anybody can
  set.
- **Did the same thing come back?** The same issue recurring must be
  visible as a recurrence and not as two unrelated comments.
- **Was the advisor right?** And here the design draws a hard line: **the
  advisor's advice must not be recorded as correct because the student's
  change was accepted.** Acceptance is a fact about the process; the
  correctness of the advice is a claim about the science, and the second
  needs its own evidence.

There is a sharper version of the same hazard, and ADR-0016 names it as the
third of its three promotion paths: **model → accepted change**. A model
rewrites the manuscript, the change is recorded, and it is attributed to
the advisor. The schema would be satisfied, the report would cite an
address, and **nothing would say the sentence was invented.** A feedback
chain that records *who made the edit* is the only thing that catches it.

## Alternatives

### A. A feedback event is an evidence record

**Rejected.** An evidence record carries a *claim* — a statement that is
checked and may be cited. A comment is an **observation**: the advisor
wrote these words at this address. Recording it in the ledger would make it
citable, and a comment is not a claim about the manuscript; it is a claim
about the manuscript's **history**, made by somebody. The ledger's
vocabulary has no state for "a person said this, and nobody has checked it
against anything", and inventing one would put a comment into the same
denominator as a verified number.

### B. A feedback event is an event on the append-only stream

**Rejected, and the reason is that events cannot link.** The event stream is
the repository's append-only spine and the report's hash chain covers it;
that is exactly what it is for, and the four chain events below are on it.
But an event says *this happened*, and the chain's questions are *this
happened **because** that, and *this was decided by that evidence*. An
event cannot answer either, and the append-only property that makes the
stream trustworthy makes it worse here: a link added later cannot be
inserted into the history of the earlier event without rewriting it.

### C. One wide table for the whole chain

**Rejected.** A comment, an edit, a response and an assessment have
different owners, different clocks and different failure modes, and they
are not in one-to-one correspondence: one comment may be answered by three
edits, one edit may answer two comments, and one assessment may cover a
whole issue rather than a comment. A table that holds all four in one row
has to answer "how many comments does this edit answer?" with a list, and
the list is a place where a link can be lost without anything failing.

### D. Four first-class objects and explicit links between them

**Chosen**, and it is the shape the reuse matrix §3.1 and §3.3 point at.

## Decision

### D1 — A feedback event is an observation, and it carries two addresses

`FeedbackEvent` is a row in `feedback_events`. It records **that a
comment was found**, and it carries both of the reader's addresses:

| | |
|---|---|
| `comment_locator` | a `DocxLocator` into `word/comments.xml`, naming the comment element — **the comment's own address** |
| `anchor_paragraph`, `anchor_start`, `anchor_end` | the body-side coordinate — **where in the manuscript the comment sits** |

**Two addresses because they answer two questions**, and the reader already
keeps them apart: "what did the advisor write" and "where did they write
it". A row that kept only one would answer one of them.

**And the anchor's coordinates are in the baseline's text.** The reader's
offsets are into the paragraph's **rejected** text — the manuscript as it
read *before* the revisions — while a version edge points at a later
version. So a comment's anchor and the edit it prompted are in **two
coordinate systems**, and the correspondence between them is a fact that
has to be recorded rather than assumed. **The feedback names the version it
was written against** (`version_id`), and the edit names the edge that
moved away from it.

**What this refuses:** a feedback row without a version. A comment that
names no manuscript state cannot be said to have been answered by any
change, because there is no "before" to have been answered *against*.

**And a candidate is not a comment.** A row read out of the file is
`observed` and has a `comment_locator`, because the reader read it. **A
model may not write that row** — and the reason is not politeness: a row
carrying a locator nobody read **is** the advisor being claimed to have
said something. **The three objects have different standing:**

| | What it is | Who may create it | Grade |
|---|---|---|---|
| `feedback_events` | **a fact about a file** — a comment that is there | **only the reader** | `observed` |
| `edit_actions` | **a fact about the manuscript's history** — a change that is there | **only the reader and the version graph** | `observed` |
| `response_links` | **a judgement** — "this change answered that comment" | a rule, a person, **or a model** | `observed` / `human_verified` / **`inferred`** |

**So what a model proposes is a judgement and never a fact.** A model's
candidate is a `response_link` at grade `inferred`: it carries **no
`comment_locator`**, because it read no comment of its own — it *points at*
one. ADR-0018's role A works this way, and the mechanism is structural
rather than a promise: **the row that holds a locator is the row the reader
wrote.**

### D2 — The anchored text is carried, and it is hashed

**The reader does not carry it today** — `CommentAnchor.text` is `""` on
every path, and that is the first link of the chain being empty. The
feedback row carries the text the comment covers, **and its hash**, and
the hash is what makes drift detectable: if the manuscript's bytes have
changed under the anchor, the anchor is **stale**, and a stale anchor is
reported as stale rather than silently re-pointed. That is ADR-0014 D5's
mechanism applied to the other end of the chain.

**And the text is the *baseline's* text**, the same text the offsets are
into — so the offset and the text agree by construction, and a reader can
check that they do.

### D3 — Missing metadata is unknown, never guessed

A comment with no author has an unknown author; one with no date has an
unknown date. **Unknown is `None` plus a named reason**, not an empty
string and not the file's mtime. The reader already refuses to guess
(`ooxml.py:366-378`), and the row inherits that refusal rather than
re-deciding it.

### D4 — An edit is an observation about a version edge, and it names who made it

`EditAction` is a row in `edit_actions`. It records **a change made in
answer to a feedback**, and it carries:

| | |
|---|---|
| `feedback_id` | the comment it answers, **nullable** — a change may answer nothing |
| `version_edge_id` | the edge it is — the parent/child pair it moved |
| `actor_kind` | `student | advisor | model | human` — **who made it** |
| `actor_id` | a named id, where there is one |
| `grade` | `observed | inferred | human_verified` |

**The `actor_kind` is the whole point of the table.** ADR-0016's third
promotion path — *model → accepted change* — is a change made by a model
and recorded as somebody else's. **A row that says `advisor` for a model's
edit is a forged signature, and the column is what makes it impossible to
write one by accident.** The grade is ADR-0014 D2's three levels, unchanged:
*observed* is read from the file's XML, *inferred* is a guess, and
*human_verified* is a person who confirmed it.

**And a change that answers nothing is not an error.** A student may edit
for reasons the advisor never wrote down. The nullable `feedback_id` says
so rather than forcing every edit into a feedback it does not answer.

### D5 — A response is a link, and it is a judgement with evidence behind it

`ResponseLink` is a row in `response_links`. It connects a `feedback_id`
to an `edit_action_id` and carries the judgement:

| | |
|---|---|
| `state` | `pending | addressed | partially_addressed | not_addressed` |
| `grade` | `observed | human_verified | inferred` — **whose judgement this is**, and a model's candidate is `inferred` |
| `decided_by` | `rule | user | model` |
| `decided_at` | when the judgement was made |
| `evidence_refs` | **what decided it** — the evidence rows, the check log, or the person |

**The state is not a free choice.** `pending` is the default and the only
state a row may hold without an explicit judgement; the other three
require `decided_by` and `evidence_refs`, and **a judgement with no
evidence behind it is refused at the schema**.

**And this is where the work order's hardest clause lives.** *"An
unaddressed comment is not reported as addressed, and neither is a wrong
response or a partial one."* So:

- a comment with **no** link is `pending`, and it is **listed as
  unaddressed** — not as addressed, and not as absent;
- a link whose evidence says the change does **not** address the comment
  is `not_addressed`, and it **exists** — the student did something, and
  the record says it did not help;
- a link whose evidence says the change addresses **part** of the comment
  is `partially_addressed`;
- only `addressed` says the comment was answered.

**The acceptance of a change is not an answer.** A link is `addressed` only
when something says so — a rule, or a person — and the thing that said so
is on the row.

### D6 — A recurrence is a relation, and it is recorded rather than inferred

**The same wording is not the same issue**, and **the same issue is not the
same wording**. A similarity score cannot tell those apart, and ADR-0014's
alignment already refused to decide an order by similarity — so the
feedback row carries an **`issue_key`**: a person-given key for "the same
problem". A comment with no key is **uncategorised**, and it is not
guessed at.

A recurrence is then a **query**: two feedback rows in one project with
the same `issue_key` in different rounds. **It is visible without being
stored**, which is the reuse matrix's §3.1 rule about the event family
applied to a relation: the relation is in the rows, and the recurrence is
what the rows *say*.

**And a round is a document, not a new entity.** A round is the set of
comments written against one manuscript version — the `version_id` the
feedback names. A recurrence is therefore a fact about two versions, and
**no `rounds` table is needed**; a table whose name means two things is a
table nobody can read (ADR-0014 D8's rule).

### D7 — An assessment is an assessment, and "the change was accepted" is not one

`FollowupAssessment` is a row in `followup_assessments`. It records **a
later judgement about an issue**: `feedback_id` or `issue_key`, the
assessment, `assessor_kind`, `grade`, and the evidence behind it.

**And the design's hard line lives here.** *"The advisor's advice must not
be recorded as correct because the student's change was accepted."*
Acceptance is a fact about the process; the correctness of the advice is a
claim about the science. So an assessment must carry **its own evidence**,
and it must be able to say **"not established"** — the same way
`VerificationStatus` can be `unsupported` and `conflicted`, and the same
way `StageCandidate` has an `UNKNOWN` member.

**A follow-up assessment that says the advisor was right because the
change was accepted is refused**, and the refusal is a schema-level fact
rather than a convention.

### D8 — The chain is replayable, so it is on the event stream

Four **annotation** events are added to `EventType`:

```
feedback_recorded
edit_action_recorded
response_recorded
followup_assessed
```

They are **annotations**, so they carry **no transition** and **no
`run_id`** — the event model refuses both (`runtime/event.py:238-274`),
and a feedback is not an attempt. Each carries a **registered payload
schema** naming the row it is about, because the anti-bag rule refuses a
payload for an unregistered type, and a chain whose events name nothing
would be a chain nobody can replay.

**Why the stream at all, when the four tables already record the chain.**
Because the phase's deliverable is a **replayable** chain, and the event
stream is the one thing the report's hash chain covers. The tables hold
the current state; the events hold **what happened and when**, and a
question like *"when was this comment first answered, and was the answer
revised?"* is a question about the history.

**The events are not the links.** The links are the foreign keys between
the four tables, and they are what make the chain traversable; the events
say that the chain happened.

**And the payload carries a copy of the judgement, not only the ids.** An
id says *which row*; the chain the report renders is a chain of
**judgements** — "this change answered that comment", "this change was
made by a model", "this assessment found it not established". So the
payload carries the row's own word for the judgement — the response's
`state`, the edit's `actor_kind`, the assessment's verdict — **as plain
optional strings, so that the table keeps its vocabulary and the runtime
layer does not import it.**

**Why the copy matters.** The event stream is the one thing the report's
hash chain covers. With ids alone the chain proves *"these rows existed at
these times"* and **not what they said** — so the forgery ADR-0016's third
promotion path describes would be caught by the row and not by the chain.
The copy makes the chain carry the substance.

**And the chain's order is defined within one Task.** The event stream's
`seq` is **per-Task**, and `occurred_at` is *"informational only. Never
used to order anything."* So the four events of one chain are replayable in
order **when the chain lives in one Task**, which is the natural case, and
the `project_id` in the payload is what joins a chain that spans Tasks. **A
reader must not order two Tasks' events by their timestamps.**

### D9 — The version graph needs a writer, and that is the first subtask

**`paper_projects`, `paper_versions` and `version_edges` have no writer.**
`confirm_edge` builds in-memory edges; `propose_alignment` builds a
proposal; **nothing in `src/` stores a version or an edge.** LC-P2-08
landed the contracts and the checks, and the persistence layer is not in
the tree.

**So the first subtask of this work order is not feedback at all**: it is
to give the version graph a way to be written, because `EditAction` names
an edge and an edge that cannot exist is a reference to nothing. This is
recorded here rather than left to be discovered, and it is why the
acceptance clause *"a comment is clickable through to its anchor, the
change it prompted, and the later outcome"* cannot be witnessed before
it.

## Upstream evidence (reference only)

- **LC-P2-07's fidelity baseline** — `docs/acceptance/LC-P2-07-fidelity-baseline.md`
  (revision recall 30/30, deletion recovery 8/8, comment recall 14/14)
- **LC-P2-08's acceptance record** — `docs/acceptance/LC-P2-08-acceptance.md`
- **The reuse matrix** — `docs/plans/PHASE_2-capability-reuse-matrix.md` §3.1
  (the event family's shape), §3.3 (`model_proposal` and the six-state
  machine), §4.1 (a table that means two things is a table nobody can read)
- **ADR-0014** (paper revision provenance — D2's grades, D4a's view, D5's
  anchoring, D8's new-table rule) and **ADR-0016** (model proposal and
  human confirmation — D1's six states, D2's creator check, D6's
  prohibition) and **ADR-0015** (dataset consent — the gate the
  transmission path passes)

## Risks, tradeoffs and reversibility

**The risk that matters: a chain that looks answered and is not.** Every
state in D5 is a place where somebody could set a comfortable answer. The
mitigation is structural — the state cannot be reached without a decision
and its evidence — and it is the reason D5 refuses a judgement with no
evidence rather than defaulting one.

**The second risk: the two coordinate systems.** A comment's anchor is in
the baseline's text and an edge points at a later version. D1 and D2 keep
the two apart and record the correspondence, but a reader who forgets that
the offsets are baseline offsets will read a chain that says the wrong
thing. **The mitigation is the version id the feedback names**, and the
witness that the anchor's text is the text at those offsets **in the
version the feedback names**.

**The third: the recurrence's key is a person's judgement.** Two comments
about the same problem only recur if somebody says they are the same
problem. That is a human cost, and it is the price of not guessing. The
alternative — inferring recurrence from similarity — is the thing ADR-0014
already refused to do for version order.

**Reversibility.** The four tables are **additive**, and every row can be
dropped without touching anything else: the version graph, the evidence
ledger and the reader are unaffected by the chain's existence. A project
with no feedback in it behaves exactly as it does now. **The one thing
that is not reversible is the version graph's writer**, because a version
that has been stored is a fact about the world that the store now holds —
and that is an argument for doing it deliberately, which is why it is D9
and not an afterthought.

## Contracts and acceptance tests

| # | Contract | Witness |
|---|---|---|
| C1 | A comment becomes a feedback row carrying **both** addresses: its own locator in the comments part and its body-side anchor | to be written at LC-P2-09 |
| C2 | The feedback row carries the text its anchor names and that text's hash, and the offsets and the text agree **in the version the feedback names** | to be written at LC-P2-09 |
| C3 | A comment with no author has an unknown author, and one with no date has an unknown date — never a guessed one | to be written at LC-P2-09 |
| C4 | A feedback row names the manuscript version it was written against, and a row that names none is refused | to be written at LC-P2-09 |
| C5 | An edit row names who made it, and a row whose actor is `model` is not the row the advisor's change made | to be written at LC-P2-09 |
| C6 | A response's state cannot be reached without a decision and the evidence behind it | to be written at LC-P2-09 |
| C7 | A comment with no response is **listed as unaddressed**, and is not absent from the listing | to be written at LC-P2-09 |
| C8 | A change that does not address the comment is recorded as `not_addressed` and **exists** | to be written at LC-P2-09 |
| C9 | A partly-addressing change is `partially_addressed` and not `addressed` | to be written at LC-P2-09 |
| C10 | A comment with no `issue_key` is uncategorised, and no key is inferred from the text | to be written at LC-P2-09 |
| C11 | Two comments with the same `issue_key` in different versions are visible as one recurring issue | to be written at LC-P2-09 |
| C12 | An assessment carries its own evidence, and one that says the advisor was right **because the change was accepted** is refused | to be written at LC-P2-09 |
| C13 | The four chain events are annotations: they carry no transition and no `run_id`, and the event model refuses them if they do | to be written at LC-P2-09 |
| C14 | The four chain events carry a registered payload schema naming the row they are about, and the anti-bag rule refuses an unregistered payload | to be written at LC-P2-09 |
| C15 | A version and an edge can be **stored**, and a stored edge round-trips through the model's own checks | to be written at LC-P2-09 |
| C16 | A model's candidate carries **no** `comment_locator`, and a row that claims the advisor's words without having read them is refused | to be written at LC-P2-09 |

**Every one of these needs a witness, and the witness must fail for the
property.** A test that fails because of an unrelated encoding or lint
matter is not a witness of the property. That rule is the project's, and
this ADR names the properties so that a later reviewer can mutate each one
and check that the named test goes red.

## Re-evaluation trigger

This ADR is re-opened if **any** of these becomes true:

1. LC-P2-01's model path exists and can produce a change to a manuscript.
   **Then the `model` actor kind stops being a category and becomes a
   live path**, and D4's rule — that a model's change is recorded as the
   model's — needs a witness of its own against the real path.
2. LC-P2-12's guidance cards exist. **Then a "piece of guidance" is a
   thing the model produces**, and this ADR's first link may need a second
   source beside the advisor's comment.
3. The multi-user question opens (ADR-0015 D6). **Then "who made the edit"
   and "who decided the response" need identities rather than kinds**, and
   the same question arises for the recurrence's key.
4. A project holds more than one manuscript in flight. **Then "a round is
   a document" stops being sufficient**, because two documents may be
   revised at once, and the recurrence's scope needs a project.
5. The pilot's own advisor asks to see the chain. **Then the report's
   rendering of it is a requirement, and this ADR's four tables have to
   say what a reader sees** — which is not a question this ADR answers.
