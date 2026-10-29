# PeerRead — upstream study

**Role in Phase 2:** reference for LC-P2-13 (the peer-review loop) and for
LC-P2-14's evaluation corpus. Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/allenai/PeerRead |
| **Pinned SHA** | `9bb37751781a900cee9e74ec3105997732c8e8e5` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Paper** | Kang et al., *PeerRead: A Large-Scale Dataset of Peer Reviews*, NAACL 2018 — https://arxiv.org/abs/1804.09635 |
| **Licence of the repository** | **none declared** — see below |
| **Licence of the data** | **none declared** — see below |
| **Decision** | **study only; no code copied, no data ingested** |

## The licence, and it is the same shape as arXivEdits'

**The repository ships no `LICENSE` file.** A walk for `LICENSE*` and
`COPYING*` at the pinned SHA returns nothing, and the README — which is
short and does not mention the word "licence" at all — says nothing about
one.

**This is the third of the six A-level clones with no licence file**, after
arXivEdits and XtraGPT, and it is the one where the consequence is
clearest, because **PeerRead's value is its data**.

The repository's `data/` directory holds the corpora by venue and year:
`acl_2017`, `acl_accepted.txt`, `arxiv.cs.ai_2007-2017`,
`arxiv.cs.cl_2007-2017`, `arxiv.cs.lg_2007-2017`, `conll_2016`,
`iclr_2017`, `nips_2013-2017`. Each is a set of paper drafts with the peer
reviews written on them.

**Those drafts and those reviews are third-party scientific writing, and
the repository states no terms for their use.** PeerRead's own paper
describes how the data was collected and released; a paper is not a
licence. So the position is the same as arXivEdits', but with more at
stake:

- The **code** is unlicensed, so nothing may be copied.
- The **data** is unlicensed, so nothing may be ingested into a Phase 2
  run, a training set, an index, or a retrieval corpus.

**And the privacy point is sharper than for a corpus of published papers.**
PeerRead's reviews are reviews *of* papers and *by* named reviewers, drawn
from public venues. The review text is public, but it is written about
identifiable work and, in the conference-review tradition, it may be
anonymised in the released form and un-anonymised in the original. **An
ingested PeerRead review is a piece of text that was written by a named
person about someone else's work**, and the design's data rules make that a
fact to handle rather than a fact to ignore.

**Nothing was ingested.** The clone is a source tree; `data/` was listed,
not copied into anything.

## What the tree actually contains

| Path | What it is |
|---|---|
| `code/` | the processing pipeline for the corpora |
| `data/` | the corpora, by venue and year |
| `requirements.txt` | the pipeline's dependencies |
| `setup.sh` | the pipeline's setup |

The structure is the one LC-P2-13 needs to imitate: **a review is
attached to a paper, and a paper has a canonical id.** The design's
`ReviewerComment → AuthorResponse → RevisionEvidence → NextReview` chain
has the same shape, and the difference is that PeerRead's papers have no
*revision history* — a draft and its reviews, and nothing in between.

## How it fits the mentor-trajectory question

**Partial, and the gap is the same gap as arXivEdits', one level up.**

| Phase 2 needs | PeerRead provides | Gap |
|---|---|---|
| review text attached to a paper | yes | — |
| reviewer identity | **anonymised** in the released data | — |
| the paper's revision history | **no** — a draft and its reviews | the central gap |
| an author response | **no** | — |
| the outcome of acting on a review | **no** | — |
| a decision (accept/reject) | yes | — |

**The middle row is the one that matters.** PeerRead gives *"what reviewers
said about a draft"*, which is the **input** to the guidance problem and
not the **chain** the phase is about. The phase's unit is
*问题 → 指导意见 → 修改行动 → 修改后的证据 → 后续评价* — and PeerRead
supplies the first two terms and none of the last three.

That is exactly why the design says PeerRead is **not a substitute for
advisor data** (*"不可当导师指导数据替身"*), and the tree confirms the
reason: there is no response, so there is no outcome, so there is nothing
to learn a rule *from*. A rule needs a case where an advice was given, an
action was taken, and something later happened. PeerRead has advice and a
paper; it does not have an action or an outcome.

## What it is good for, then

**A vocabulary and a format reference, and a candidate for a *test* set —
subject to the licence question being settled.**

1. **The data format.** How a review is stored against a paper: the
   fields, the identifiers, the levels. LC-P2-13's `ReviewerComment` needs
   a shape, and this is a published one.
2. **The "anonymous reviewer" problem, solved once and for all.** PeerRead's
   data is anonymised at the level of the *review*, and the design's
   `FeedbackEvent.actor_role` has to carry the same distinction between
   "the advisor" and "an anonymous reviewer 3" without pretending the
   second is a person.
3. **The acceptance-decision vocabulary.** A review round ends in a
   decision, and the design's §5 `FollowupAssessment.source_of_outcome`
   has to say what a decision *is* — and a decision is **not** evidence
   that the advice was right. PeerRead's inclusion of the accept/reject
   labels alongside the reviews is the concrete reason that rule needs
   writing down.

**And a negative case worth stating plainly.** If PeerRead were ingested
and used to build the guidance experience, the system would learn
*"reviewers object to X in papers like Y"* — which is a claim about
**reviewers of papers**, not about **an advisor guiding a student**, and
the two populations are not interchangeable. The design's rule — *"不同
导师/课题组隔离"* — exists for the advisor case, and the same separation
applies here for a different reason.

## Reproducing the reference

```bash
git clone --filter=blob:none https://github.com/allenai/PeerRead.git
git -C PeerRead rev-parse HEAD   # 9bb37751781a900cee9e74ec3105997732c8e8e5
```

**No data file was read, no corpus was ingested, and no pipeline was run.**
The claims above are about the tree's *structure* — which directories hold
what, and what a README says — and every one of them was checked at the
pinned SHA.

## What is decided, and what is not

**Decided:**

- Study only. No code copied, no data ingested, no pipeline run.
- The licence position is recorded as **"none declared, for both the code
  and the data"**, and the consequence is stated: the data may not enter a
  Phase 2 run, a training set, an index, or a retrieval corpus until the
  licence question is settled by someone with the authority to settle it.
- PeerRead's role is **a format and vocabulary reference for LC-P2-13**,
  and the design's rule that it is not a substitute for advisor data is
  confirmed by the tree: there is no response and no outcome in it.

**Not decided:**

- Whether the data may be used **at all**, and if so under what terms.
  This is the owner's, and the answer may well be "no" — in which case
  LC-P2-13's format reference is the whole of the benefit, and it is a
  real benefit.
- Whether any *public* review data is needed for LC-P2-14's evaluation.
  The design requires the evaluation set to be split **by paper project**
  and to exclude anything used for training; a public review corpus would
  be a **test**-side resource only, and only if its licence allows it.
