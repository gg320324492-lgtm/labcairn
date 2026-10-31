# The Phase 2 pilot — how the readings were made

**Date:** 2026-10-31 · **Corpus:** one draft of the owner's manuscript, and
the advisor's comments on it, read out of the Word file with LabCairn's own
OOXML reader.

**What this file is.** The method, and where the records are. **It carries
no label, no rationale, no agreement number and no word of the paper**,
because the corpus is the owner's unpublished manuscript and **this
repository is public**. The readings, the labels and the number live in the
material library, outside the repository, at
`E:\labcairn-local\materials-library`.

## 1. Why the readings are made at all

The pilot is the first time LabCairn reads the owner's real paper rather
than a fixture. Two things have to be true before the product's claims can
be said to hold on real text: that the **advisor's comments can be read
and labelled** by more than one route, and that **the model's judgement
about them enters the ledger as a proposal** rather than as a fact.

The label vocabulary is the project's own: the twelve `IssueKind` members
plus `unknown`, decided by [`annotation-guide.md`](annotation-guide.md) §3,
where each label carries a worked example and **the boundary** — the
question that tells two neighbouring labels apart.

## 2. The arrangement

**Two independent blind readings, and a third reader to arbitrate.**

| | What it was given | What was withheld |
|---|---|---|
| Reading 1 | the comments with their anchors and paragraphs, the guide, the vocabulary | the other reading, the arbiter's resolutions, any manifest of expected labels, the network |
| Reading 2 | the same | the same |
| The arbiter | the corpus, the guide, **both readings as two readings** — which is which was not its to know | any manifest of expected labels, the network |

**The two readings were made by different routes, not by the same prompt
twice.** One read the comment and asked what problem in the paper it points
at; the other wrote down what would have to be true of the manuscript for
the comment to be satisfied, mapped that requirement onto the taxonomy, and
then checked it against the paper. A reading is a judgement, and two
samples of one prompt measure one judgement twice.

**The arbiter is a third reader, not one of the two.** Where the readings
agree, the arbiter still says why that label is right on the guide's terms
— an agreement is not automatically right, and a resolution that only says
"they agree" has not been arbitrated. Where they differ, it answers the
boundary question and says which stands, or `unknown` if the guide does not
settle it. **It does not split the difference and it does not pick by
count.**

## 3. What the agreement number is, and what it is not

**It measures how far two independent readings of the same material
converge. It does not measure how far two people would agree.** The
readings were sessions of one model, not two people, and
[`annotation-guide.md`](annotation-guide.md) §1.0 says exactly this of the
gold set, whose labels were read the same way. **A human reading of the
same corpus is the comparison the number is meant to be read against.**

This is stated here rather than only in the guide because the pilot's
number will be read against the gold set's, and the two are the same kind
of number only if both are described the same way.

## 4. Where the records are

| What | Where | Why there |
|---|---|---|
| the draft, the comments, the revisions | `E:\labcairn-local\materials-library\versions-chinese/`, `comments/`, `revisions/` | the paper is the owner's data, and it is not in a public repository |
| the two readings, with their rationales | `E:\labcairn-local\materials-library\labels/reading-1.json`, `reading-2.json` | same |
| the agreement, and the arbiter's resolutions | `E:\labcairn-local\materials-library\pilot-blind-readings.json` | same |
| the untouched archive, and every file's original name and hash | `E:\labcairn-local\materials-library\originals/`, `MANIFEST.json` | so the library can be checked against what arrived |

**The library is the pilot's record, and it is not in the repository.** The
project's rule is that a record must be checkable; the rule that the
owner's unpublished paper does not enter a public repository is the stronger
one here, and the library keeps the checkability by keeping the bytes.

## 5. What the pilot found about the product

**Four defects in the provider layer's probe**, found by the first live
probe and fixed with witnesses: the acceptance record is
[`../acceptance/LC-P1-03-probe-wire-fixes.md`](../acceptance/LC-P1-03-probe-wire-fixes.md).

**Four gaps the product has**, and one that is bigger than the others: no
product door writes an access grant; the probe's result is measured but not
persisted; the model path has no CLI; `request_model` is not exported from
the application package; and **six domain modules read the store from
outside the application layer**, which the repository's own witness says
and which is the next piece of work. The pilot's task book is
[`../plans/PHASE_2-pilot-task-breakdown.md`](../plans/PHASE_2-pilot-task-breakdown.md).
