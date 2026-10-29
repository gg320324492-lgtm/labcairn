# openreview-py — upstream study

**Role in Phase 2:** reference for LC-P2-13 (the peer-review loop) — the
structured access to a public review process. Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/openreview/openreview-py |
| **Pinned SHA** | `9e8ba8e677289f79944c486d706539c3ddb50404` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Licence** | **MIT**, verified by opening `LICENSE` at the pinned SHA ("MIT License / Copyright (c) 2022 OpenReview") |
| **Decision** | **study only; not a dependency; no data fetched** |

## The licence, read from the file

The root `LICENSE` at the pinned SHA is the MIT licence, "Copyright (c) 2022
OpenReview". A walk for other licence files finds none.

**This is the cleanest licence position of the six**, and it does not
change the decision: MIT permits use, and Phase 2 does not use it. The
reason is not the licence — it is that **the client is a way to reach other
people's confidential material**, and the licence of the *code* says nothing
about the *data*.

## What the tree actually contains

| Path | What it is |
|---|---|
| `openreview/api/client.py` | the API client; `get_notes` at `:1720` |
| `openreview/openreview.py` | the older client surface; `get_notes` at `:1127` |
| `openreview/venue/`, `openreview/conference/`, `openreview/journal/`, `openreview/arr/` | per-venue workflows |
| `openreview/profile/`, `openreview/mfa.py` | profile and authentication |
| `openreview/duplicate_domains.json` | a de-duplication table |

**The thing to study is `Note`.** OpenReview's whole data model is a note
with a `forum` (the thread's root, which is the submission), an
`invitation` (which kind of note it is — a review, a rebuttal, a
meta-review), a `replyto` (what it answers), a `content` dictionary, and
timestamps.

**That is the review-loop shape, already solved, and it is worth
borrowing the *idea* of:**

```
submission (forum root)
  ├── review          invitation=Review, replyto=submission
  ├── rebuttal        invitation=Rebuttal, replyto=review
  └── meta-review     invitation=MetaReview, replyto=submission
```

LC-P2-13's chain — `ReviewerComment → AuthorResponse → RevisionEvidence →
NextReview` — is the same shape with one extra term, and **the extra term
is the one OpenReview does not have**: a revision's *evidence* is the
change in the manuscript, and OpenReview has no manuscript history either.

## What was measured about the API surface

`get_notes` (both clients) takes a filter set, and the filters that matter
for LC-P2-13 are:

| Filter | What it selects |
|---|---|
| `forum` | every note in one submission's thread — **the review chain** |
| `invitation` | one kind of note — reviews, rebuttals, decisions |
| `replyto` | the notes answering one specific note |
| `content` | a content-value filter |
| `details` | whether replies and signatures come back with the note |
| `after`, `limit`, `offset`, `sort` | paging and ordering |

**`forum` plus `invitation` is the whole of a review loop in two filters**,
and that is the design's LC-P2-13 shape. A `ResponseLink` is a `replyto`
edge; a review round is a `forum`; the actor is a signature.

## How it fits the mentor-trajectory question

**The structure fits; the data does not reach.**

| Phase 2 needs | openreview-py | Gap |
|---|---|---|
| a review attached to a submission | yes — `forum` | — |
| a rebuttal attached to a review | yes — `replyto` | — |
| a meta-review | yes — `invitation` | — |
| a decision | yes | — |
| **the manuscript's revision history** | **no** | the central gap |
| **whether the rebuttal was acted on** | **no** | the central gap |
| a structured, queryable store of the above | yes | — |

The third row from the bottom is the one that decides the phase's honesty.
**OpenReview gives the conversation; it does not give what happened
after.** The design's `FollowupAssessment.source_of_outcome` has to name a
source of outcome, and an accepted submission is a **decision**, not
evidence that the advice was scientifically right — the design says this
outright (*"把作者响应与审稿后录用等同于建议正确"* is forbidden).

**So OpenReview's usable contribution is the data model and the query
shape, not the data.** And the model has one property Phase 2 should copy
and one it must not.

**To copy: the thread identity.** `forum` is a stable id for "this
submission's review conversation", and it survives across rounds. LC-P2-13's
`NextReview` needs exactly that: a second round of reviews on a revised
paper is a **new forum**, and the link between the two is the paper, not
the thread.

**Not to copy: the note-as-everything shape.** OpenReview stores a
submission, a review, a rebuttal and a decision as the *same kind of
object*, distinguished by an `invitation` string. LabCairn's model already
separates the kinds — `SourceMaterial` from `SourceText`, an evidence
record from an artifact — and the project's own history records what
happens when two vocabularies meet: *"the capability registry and the
append-only event vocabulary are the two places where two work orders have
already made one answer impossible twice."*

## The privacy point, and it is the reason this study is short

**This is the finding that matters, and it is not about the code.**

OpenReview's API is a way to reach **conference material**, and a
significant part of that material is **not public**: reviews in flight,
author rebuttals before a decision, confidential comments, and — depending
on the venue — the identities behind pseudonyms.

Three consequences, and they are the design's own rules:

1. **An API is not permission.** The design says *"只访问明确公开且许可允许
   的数据；API 不意味着所有审稿记录可二次利用"*. A client that can fetch a
   note can fetch a note that was not meant to be kept.
2. **A confidential review must never reach a third-party model.** ADR-0015's
   `external_transmit` grant is **default-deny**, and this is the case it
   exists for: *"未发表或保密审稿材料未经授权不得调用第三方模型"*.
3. **The pilot's corpora are the private ones.** LC-P2-13's real data is the
   teacher's own students' review correspondence, collected under the
   consent ADR — not OpenReview.

**Nothing was fetched.** The clone is a source tree; no request was made to
any OpenReview API, and no note, forum or profile was retrieved.

## Reproducing the reference

```bash
git clone --filter=blob:none https://github.com/openreview/openreview-py.git
git -C openreview-py rev-parse HEAD   # 9e8ba8e677289f79944c486d706539c3ddb50404
```

The client was **not installed** and **no API call was made**. Every claim
above was read from the source at the pinned SHA, and the line references
are checkable against it.

## What is decided, and what is not

**Decided:**

- Study only. Not a dependency, not installed, no data fetched.
- Its contribution to LC-P2-13 is **the thread model and the query shape**
  — `forum` for a review chain, `invitation` for a note's kind, `replyto`
  for the edge between them.
- **LabCairn will not adopt OpenReview's one-object-many-kinds shape.**
  LabCairn's kinds are already separated, and a second vocabulary for the
  same thing is the failure the project's own history records.
- **No OpenReview material enters the pilot.** The pilot's review data is
  the teacher's own, collected under ADR-0015.

**Not decided:**

- Whether OpenReview's public records are useful as a **test-side**
  resource for LC-P2-14 — for example to check that a review-chain reader
  can reconstruct a thread that is already public. That is a separate
  question from the pilot's data, and it needs the owner's view on what
  public review data may be used for.
- Whether LC-P2-13 should support a **live** OpenReview connection at all.
  The case for it is thin — the phase's data is private and consent-bound —
  and the case against it is a third-party endpoint holding confidential
  material.
