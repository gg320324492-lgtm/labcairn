# ADR-0020: An opinion quoted in a letter, and a revision marked in colour

**Status:** Archived as historical Phase 2 design, 2026-11-06. Written as
`Proposed — design only` on 2026-11-05; no product code was changed by this
ADR.
**Work order:** none. The owner archived the LC-P2-28 design on 2026-11-06;
it was never dispatched.
**Date:** 2026-11-05 · **Archived:** 2026-11-06

## Context and concrete problem

Two material shapes have now been measured twice and the product honestly
reports them as absent:

1. **The reviewer's opinion as body text.** Batch 7's response letters quote
   `Reviewer #N:` in an ordinary paragraph and have no
   `word/comments.xml`. Batch 9's letters carry 44 such objection/answer
   pairs over six letters, 72 `Point` items in the full eight-letter set,
   and one mixed-source letter whose first two points are verbatim a
   different paper's. `papers/replies.py` can hold the objection and the
   answer as two paragraphs, but the product cannot say *"this is the same
   opinion the answer is about"*: a quoted opinion has no `comment_id`, no
   body-side anchor and no author the file states. A settlement
   (`settle_reply`) takes evidence and a decider, not an opinion address.
2. **A revision marked in red font.** Batch 7's marked manuscripts declare
   zero `w:ins` / `w:del` and carry 401 and 62 red runs; the clean files
   each carry one stray red run that is not an edit. Batch 9's letters use
   the same colour for the response side. The chain's `revision_events`
   speak of insertions and deletions with an actor and a date; a colour run
   states neither direction nor actor, and the deleted words are not in the
   marked file at all.

Both shapes are **real source types the material uses**, not reader bugs.
Guessing a Word comment from a paragraph that begins with a reviewer's name,
and guessing an insertion from a red run, would mint events the file does
not state — the two negative witnesses of
[`LC-P2-14-cej-pilot.md`](../acceptance/LC-P2-14-cej-pilot.md) §2 hold that
refusal. Batch 8 supplied a third fact: a translation pass with 1,108
insertions and 1,146 deletions is a language-rendering transform, and the
owner ruled on 2026-11-05 that it is **not** a distillation source.

## Decision

**Do not widen the existing event kinds.** Add two source distinctions, each
with its own identity, and keep the existing reader's honest refusal until a
source-typed reader exists.

### 1. A comment-source type, with a link the reply can name

- Extend the chain's comment records with a closed source type: at least
  `docx_comment` (today's shape) and `quoted_paragraph`. The quoted shape
  carries the source document, the paragraph index, and the text hash; two
  opinions with the same words in different places are different records.
- The author of a quoted opinion is **unknown** unless the material states
  it; `Reviewer #N` is a label, not a person.
- Add a join from a reply row to the comment record it answers, so a
  settlement can name the opinion. This is an identity, not a second reply
  mechanism.
- Keep the pairing rule (the paragraph before `Response:`) separable from
  the text, the way `record_replies` already keeps paragraph indices.

### 2. A flagged-text event, with a version pair behind it

- A run whose `w:rPr/w:color@w:val` matches the material's agreed mark
  colour is **flagged text**, an event of its own kind — never `ins`, never
  `del`.
- A flagged span has no before/after text until a (marked, clean) version
  pair is aligned paragraph by paragraph. The version graph already holds
  pairs; without the clean file the flag has no baseline.
- A flag means *"the authors marked this"*. It does not name an actor, a
  date, or a direction.
- The clean files' stray red run is a required false-positive witness: the
  rule must report it as flagged text and not as a change.

### 3. A mixed-source letter is refused, not merged

A letter whose points come from two papers must not be ingested as one
paper's response set. Batch 9's `09_Response` was measured as a mixed-source
re-issue and was not routed in the pilot. The reader must refuse it with a
reason rather than average the two sources.

## Consequences

- Full ingestion is a **two-work-order** effort: one for the quoted-opinion
  identity and reply join, one for the flag event and version alignment.
  Each needs witnesses that redden under the tempting guess (paragraph →
  comment, colour → insertion), and each needs a real-material pilot like
  the two already done.
- No capability claim comes from ingesting more material: the chain gains
  source honesty, not a measured guidance gain.
- Batch 7 remains a negative witness plus read-only route; batch 9 remains
  a 44-pair replies pilot. Neither becomes a rating case by this ADR.
- The translation pass of batch 8 stays out of distillation, by the
  owner's 2026-11-05 decision.

## Alternatives considered

1. **Treat a quoted paragraph as a Word comment.** Rejected: the file has
   no comment part, no range markers and no body-side anchor; the negative
   witness in [`LC-P2-14-cej-pilot.md`](../acceptance/LC-P2-14-cej-pilot.md)
   §2 goes red when the reader guesses this way.
2. **Treat red font as an insertion.** Rejected for the same reason, and
   because the deleted words are not recoverable from the marked file.
3. **Widen `revision_events` with a colour field.** Rejected: a colour on
   an existing insert/delete row would still assert a direction the file
   never states.
4. **Do nothing and keep only the negative witnesses.** Valid, but the
   owner chose on 2026-11-05 to write the design down. The owner archived
   that design on 2026-11-06; this ADR is the historical record of what a
   future ingestion would have had to prove, not permission to start it.
