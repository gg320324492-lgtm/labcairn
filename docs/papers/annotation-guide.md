# LC-P2-10 — The annotation guide

**Work order:** LC-P2-10 (process annotation and the gold set) · **Subtask:**
T01 · **Status:** drafted 2026-10-30, **not yet used to label anything**.

**What this is.** The instructions a person follows when they read a
manuscript and write down what each comment is about. It is the
description the annotation task is carried out from: the label set in
`src/labcairn/papers/labels.py` says *which words* are allowed, this says
*what each word means* and, for every one of them, what a person sitting
with the manuscript should do when they cannot decide.

**What this is not.** It is not a rubric for good advice, a source of
guidance rules, or a description of how to revise a paper. §7 says which of
those it is not and where each one lives instead.

**Read this before you label anything.** Every label below carries three
things: what it names, a worked example you could point at in a real
manuscript, and a boundary case that shows where it stops and the
neighbouring label starts. The third one is the one that decides the
label; the first two only tell you what you are reading.

---

## 1. What you are doing

### 1.1 The unit is one comment

**One comment, one reading.** You read a manuscript, you take one comment
at a time, and for that comment you write down a label on each of three
axes. Then you do the next comment. There is no label for a paragraph, no
label for a paper, and no label for a revision; a revision is not a
comment, and two comments that say the same thing are two comments.

**A comment is an observation, not a verdict.** The chain's first clause
(LC-P2-09) is that a comment has *two* addresses, and §2 is about that.
For now, one thing: you are recording what a comment **is about**, not
whether it was good, not whether it was followed, and not what should
happen next.

### 1.2 Three axes, three different questions

The three axes are separate because they answer three different questions,
and one label per comment would have had to choose which of them it was
talking about. The questions below are the ones in
`src/labcairn/papers/labels.py` (`AXIS_QUESTIONS`), and they are the same
words the manifest uses.

| The axis | The question it answers | The answers it accepts |
|---|---|---|
| **issue kind** | What problem did the advisor point at? | the twelve kinds of `IssueKind` — `other` is the twelfth of them — or `unknown` |
| **response state** | Did anything in the manuscript answer it? | `pending`, `addressed`, `partially_addressed`, `not_addressed`, or `unknown` |
| **assessment outcome** | Did the advice turn out to hold? | `established`, `not_established`, `conflicted`, or `unknown` |

**Three labels per address, not one.** An issue kind says *what* the
comment is about; a response state says *whether the manuscript answered
it*; an assessment outcome says *whether the advice turned out to be
right*. A comment can be about the sample size (`data_quality`), go
unanswered (`pending`), and turn out to have been right (`established`) —
three facts, three labels, no one of them standing in for another.

### 1.3 Why these labels and not an imported taxonomy

**The labels are this project's own, and the reason is recorded.**
`docs/research/upstream-study/arXivEdits.md` reads the arXivEdits
edit-intention taxonomy and explains why it cannot be imported here: its
classes describe **what kind of text edit was made**, which is a
different axis from **what problem the advisor was pointing at**. A
rewrite can be motivated by an evidence gap and be implemented as a
paraphrase, so the two labels answer different questions, and an
annotation set built on the wrong axis measures the wrong thing.

**The consequence for you is concrete.** You are labelling the advisor's
problem, not the editor's edit. If the student implemented the advisor's
advice by paraphrasing two sentences, that fact is not part of the
issue kind — the issue kind is the evidence gap that made the paraphrase
necessary.

**And the two other axes are imported, deliberately.** The response states
come from `src/labcairn/papers/responses.py` and the assessment outcomes
from `src/labcairn/papers/assessments.py`, because a second spelling of
"what a response state is" would be a second vocabulary for the same
rows. The issue kinds are named here rather than imported, because a
renamed external class would claim a comparability that does not exist.

### 1.4 What you read, and in what order

For each comment, read in this order. It is the order the questions come
in, and it saves you from labelling a problem before you know what the
manuscript did about it.

1. **The comment element** — the text the advisor wrote, in the comments
   part of the document. This is *what was written*.
2. **The body-side address** — the paragraph and character range in the
   body that the comment is anchored to. This is *what it was written
   about*.
3. **The later version of the manuscript**, if the corpus holds one. This
   is what tells you the response state, and it is where the assessment
   evidence comes from.
4. **Any assessment record** the corpus holds for the comment. This is
   what tells you the assessment outcome.

If the corpus holds no later version, step 3 gives you nothing, and §6.2
says what you write then.

---

## 2. The two addresses

### 2.1 The comment address

**The comment element in the comments part** of the Word document —
`word/comments.xml`, the element the comment locator names. It carries
the advisor's words, the author, the date, and nothing about where in the
manuscript the comment belongs.

**The issue kind you label here is the one the comment's own text
points at.** Read the comment as a piece of writing and ask: what problem
is this comment saying exists?

### 2.2 The body address

**The paragraph number and character range in the body** that the comment
is anchored to. The offsets are into the **baseline** text — the
manuscript as it read *before* the revisions — so paragraph 4 of the
baseline is paragraph 4 you look up, not paragraph 4 of the latest
version.

**The issue kind you label here is the one the anchored position
exposes.** Read the words at the anchor, in the context of the paragraph
they sit in, and ask: what problem is visible *here*, in this piece of the
manuscript?

### 2.3 A worked example that shows the two apart

**This is the example to keep in your head; the rest of the guide uses
the same manuscript.** The example manuscript is a synthetic one, referred
to here as `example-perov`: *"Graph Attention Networks for Band-Gap
Prediction on Perovskite Surfaces."* It is an illustration, not a fixture
— the corpus's real fixture names come from the manifest.

Take one comment, `c7` of `example-perov`.

**The comment element** says:

> Add a control experiment: with GAT as the only model, a reader cannot tell
> whether the gain comes from the graph structure or only from the features;
> please add a geometry-only network as a baseline and report it on the same
> test set.

**The body-side anchor** points at paragraph 4 of the baseline, the
sentence *"We evaluate on a held-out set of 800 surfaces."*

**The two issue kinds are different, and both are right.**

| Address | What you read | The issue kind | Why |
|---|---|---|---|
| `comment_address` | the advisor's own words: *add a control experiment, add a geometry-only baseline* | `controls_and_ablation` | the problem the comment names is a missing comparison |
| `body_address` | the anchored sentence: *a held-out set of 800 surfaces* | `data_quality` | the problem visible at that position is that the evaluation set is small |

**Why this is not a mistake, and why one label would have lost it.** The
advisor asked for a comparison, and the comment happened to be anchored on
the sentence that reports the evaluation-set size. One label per comment
would have had to pick one of them, and the other would have been lost.
LC-P2-09's first clause is that a comment has two addresses precisely so
that both can be recorded — and this example is the reason it is two
fields in the manifest (`comment_address` and `body_address`) rather than
one.

### 2.4 The rule for the body address's issue kind

**The body address's issue kind is the problem at the anchor that this
comment is about** — not the section the anchor happens to sit in, and
not the comment's issue kind repeated.

Three rules settle it:

1. **The anchor is where the advisor's attention landed.** The problem is
   the one the comment picks out of that position. If the anchor sits on
   the sentence that reports the evaluation-set size, and the comment says
   the evaluation set is too small, the body-side problem is `data_quality`.
2. **Section membership is not a label.** A comment anchored in the
   Methods section is not automatically `method_and_hypothesis`. The
   label follows the problem, and the anchor only tells you where to look
   for it.
3. **When the anchor carries no problem you can see, the answer is
   `unknown`.** If the comment is about the sample size but the anchor
   landed on a figure caption that says nothing about sample size, then
   you cannot say what problem the comment picked out *there*, and
   `unknown` is the honest answer (§6.2). It is not `other`, and it is
   not a guess at the comment's issue kind copied into the other slot.

### 2.5 The other two axes on both addresses

**The response state and the assessment outcome are labelled on each
address too, and they can differ.** The response states are properties of
the comment, not of the two addresses, but they are recorded on both
because the manifest's shape asks for them on both, and because the
arbiter resolves each address's three labels separately.

**What this means in practice:** you write the same response state on
`comment_address` and `body_address` whenever the comment was answered
as a whole, and you write different ones when the answer addressed only
one of the two problems. If the manuscript added the geometry-only
baseline (answering the comment's request) but never mentioned the 800
surfaces (leaving the body-side problem alone), then:

- `comment_address`: issue kind `controls_and_ablation`, response state
  `addressed`;
- `body_address`: issue kind `data_quality`, response state
  `pending`.

**And `pending` here means "no answer to *this* problem", not "no answer
to the comment".** §4.1 says when that distinction matters and when
`unknown` is the better word.

---

## 3. The issue kind axis

### 3.0 How to read this section

**Each label below is a thing a reader of the manuscript could disagree
with** — a problem that exists in the paper and that a comment points
at. Not a transformation of the text, and not a stage of the process.

**There are twelve of them, and `other` is the twelfth.** They are the
twelve members of `IssueKind` in `src/labcairn/papers/labels.py`, and
the axis accepts one more value on top of them: `unknown`, which §6
covers.

Every entry has the same three parts:

- **What it names** — one sentence, the definition.
- **Worked example** — a sentence of the kind an advisor would write, and
  enough of the manuscript around it that you can see why the label
  holds.
- **The boundary** — the neighbouring label, and the question that tells
  them apart. The boundary is the part that decides; when you are
  hesitating between two labels, the boundary question is what you
  answer.

**If you still cannot decide between two of them, that is `unknown`,
not `other`.** `other` means the advisor pointed at a real problem that
none of the other eleven kinds names (§6.1).

### 3.1 `research_question_and_motivation`

**What it names.** The research question itself, or the reason for asking
it — what the paper is trying to answer, and why that is worth answering.

**Worked example.** *"What exactly is this paper asking? If this is only a
transfer of an existing GNN to perovskites, then say which quantity you
are predicting — the band gap or the formation energy. I have read §1 twice
and I cannot tell which one it is."*

**The boundary.** Against `novelty_and_contribution`: the research
question is *what is being asked and why it is worth asking*; novelty is
*what this paper adds that the literature does not have*. "This question has
already been answered" is `novelty_and_contribution` when it means the work
exists already; "you never say which question you are asking" is
`research_question_and_motivation` even when the sentence mentions the
literature.

### 3.2 `novelty_and_contribution`

**What it names.** What the paper claims is new, and whether the claim
holds up.

**Worked example.** *"Contribution 1 says we are the first to apply attention
mechanisms to band-gap prediction on perovskite surfaces, but [12] in
Appendix B did exactly that in 2019. Either 'first' comes out, or you write
down how you differ from [12]."*

**The boundary.** Against `sources`: a claim about the literature is
`novelty_and_contribution` when the question is *does my contribution
claim survive comparison*; it is `sources` when the question is *is this
citation here correct, and does it support the sentence it sits next to*.
A comment that criticises a contribution claim by pointing at a paper is
still `novelty_and_contribution`.

### 3.3 `introduction_and_storyline`

**What it names.** How the paper is laid out and how its argument is
told — what is said where, and in what order.

**Worked example.** *"Related work takes three pages of §2, and by the time
the reader reaches your method they have forgotten what you were trying to
solve. Cut §2 down to a page and move the problem statement that opens §4
to the end of §1."*

**The boundary.** Against `language_and_format`: storyline is *where
information sits and what order it arrives in*; language is *how the
sentence that is already there is written*. "This information should come
earlier" is `introduction_and_storyline`; "it takes three readings to work
out where this sentence ends" is `language_and_format`.

### 3.4 `method_and_hypothesis`

**What it names.** The design, the hypothesis, and the method as
described — whether what the paper says it did is clear and whether it is
the right design for the question.

**Worked example.** *"Are the attention weights shared across all atoms, or
shared per head? §3.2 says 64 hidden units and 3 layers, but never says
whether that is 3 attention heads or 3 stacked copies of one head — those
are not the same model."*

**The boundary.** Against `controls_and_ablation`: the method is *what
your method is*; the controls are *what you compared it against*. "You
never say which kind of attention you use" is `method_and_hypothesis`; "you
have no ablation" is `controls_and_ablation`. Against `data_quality`: the
method is the model
and the processing; the data is the data itself — where it came from,
how it was labelled, whether it leaks.

### 3.5 `data_quality`

**What it names.** The data itself: whether it is sound, whether it is
adequate, and what it can support.

**Worked example.** *"These 800 test surfaces were drawn from a single family
of crystal structures — do the training and test sets overlap? §3.1 says
only 'a random split', and never says how a family is kept out of both."*

**The boundary.** Against `statistical_conclusion`: the data is *the
data's own condition*; the conclusion is *what the numbers are allowed to
be said to show*. "800 is too few" is `data_quality`; "a p < 0.05 computed
on 800 of them does not hold up" is `statistical_conclusion`. Against
`method_and_hypothesis`: as above — the method is the procedure, the data
is what it was applied to.

### 3.6 `controls_and_ablation`

**What it names.** The comparison that makes the claim stand up —
baselines, controls, ablations.

**Worked example.** *"Add a control experiment: with GAT as the only model, a
reader cannot tell whether the gain comes from the graph structure or only
from the features; please add a geometry-only network as a baseline."*

**The boundary.** Against `method_and_hypothesis`: as above — a missing
comparison is `controls_and_ablation`, an unclear method is
`method_and_hypothesis`. Against `review_response`: if the missing
comparison is one the advisor promised in a reply to a reviewer, the
failure to deliver the promise is `review_response` (§3.10), and the
comparison that is missing is `controls_and_ablation`.

### 3.7 `statistical_conclusion`

**What it names.** What the numbers are permitted to conclude — whether
the inference drawn from the results is licensed by those results.

**Worked example.** *"Table 2 reports the mean and standard deviation over 12
runs, but you trained on 3 random seeds and then ran 12 pairwise
comparisons. There is no multiple-comparison correction, so 'better than
the baseline' is the best of twelve."*

**The boundary.** Against `data_quality`: the data is the condition of
the inputs; the conclusion is the inference drawn from them. Against
`controls_and_ablation`: a missing comparison is a missing comparison; a
comparison that exists and is analysed with the wrong statistics is
`statistical_conclusion`.

### 3.8 `figures`

**What it names.** The figures: whether they show what the text says
they show.

**Worked example.** *"The caption of Figure 3 says the error falls with
training steps, but the figure plots error against epochs, and the error
band only appears after 100k steps — the drop at the left of the plot is a
truncated axis, not a falling error."*

**The boundary.** Against `language_and_format`: the figure is *the
figure's content* — axes, labels, and whether the picture and the
caption say the same thing; the language is *the prose*. A wrong axis
label is `figures`; a typo in the caption's prose is `language_and_format`.
Against `statistical_conclusion`: figures are about *the picture
matching the text*; the conclusion is about *the inference*.

### 3.9 `sources`

**What it names.** The references: whether the claims rest on them, and
whether they are cited correctly.

**Worked example.** *"You write here that 'transfer learning reduces the need
for annotation', but [7] reports pre-training on 80,000 hand-labelled
surfaces — that sentence has no support here, or you have read [7]
backwards."*

**The boundary.** Against `novelty_and_contribution`: as above — a
criticism of the *contribution claim* is novelty, a criticism of *the
citation* is `sources`. Against `language_and_format`: sources is about
what the references say and support; language is about the prose.

### 3.10 `review_response`

**What it names.** An answer to a reviewer, and what was done with it.

**Worked example.** *"Reviewer R2 asked for a transfer-learning control; you
replied that it would be added in the final version, and there is no such
section in §5 of the final version. Either add it, or say in the response
letter why it is not coming."*

**The boundary.** Against `controls_and_ablation`: the missing
experiment is `controls_and_ablation`; the unkept promise about it is
`review_response`. If the comment says "R2 asked for this and you did
not do it", the label is `review_response` even when the thing not done
was an ablation. Against `method_and_hypothesis`: a review response is
about *the reply and its follow-through*; the method is about *the
described procedure*.

### 3.11 `language_and_format`

**What it names.** The writing and the presentation that is none of the
above — wording, grammar, terminology, formatting, and the presentation
of the manuscript as a document.

**Worked example.** *"The first paragraph of §3.2 has three long sentences
with no clause markers, and it takes three readings to find where each one
ends; and 'band gap' is written 'band-gap' in one place and 'bandgap' in
another — pick one and use it throughout."*

**The boundary.** Against `introduction_and_storyline`: as above —
*where it is said* versus *how it is said*. Against
`method_and_hypothesis`: language is how the sentence reads, the method
is what the sentence reports.

### 3.12 `other`

**What it names.** The advisor pointed at something real that none of the
other eleven kinds names.

**Worked example.** *"This supplementary material has no data-availability
statement and no IRB approval number. This is not a problem with the
science, but the paper cannot go out as it stands."*

**The boundary.** Against `unknown`, and this is the whole boundary:
`other` means **you can say what the advisor pointed at** — here, a
missing ethics approval and data-availability statement — and the
taxonomy has no name for it. `unknown` means **you cannot say what the
advisor pointed at**. §6.1 says why mixing them up is a measurement
error and not a rounding difference.

---

## 4. The response state axis

### 4.0 What this axis asks

**Whether anything in the manuscript answered the comment.** The four
states come from `src/labcairn/papers/responses.py`, and they are not
four labels for one thing: they separate *nobody answered* from *somebody
answered and it did not help*.

**The state is about the chain, not about the text.** A comment can sit
in a paragraph that is perfectly clear and still be `not_addressed`.

### 4.1 `pending`

**What it names.** Nobody answered the comment. There is no response
record for it.

**Worked example.** Comment `c3` in `example-perov` says *"Please state the
splitting criterion of your dataset"*. The corpus holds v1 and v2; in v2 the
sentence about the split is unchanged and no reply text mentions it. No
response record links the comment to a change: `pending`.

**The boundary.** Against `not_addressed`: `pending` is **nothing
happened**; `not_addressed` is **something happened and it did not
answer the comment**. The chain's own rule follows this: `pending` is the
only state a row may hold without a decider and without evidence, because
nobody decided anything. **And against `unknown`**: `pending` requires
that you *looked and found nothing* — see the condition below, which is
the most common way this axis is annotated wrongly.

> **`pending` requires a corpus in which an answer could have appeared.**
> If the corpus holds no later version of the manuscript, then there was
> nothing in it for an answer to be in, and your reading of the chain is
> "no evidence", not "nobody answered". Write `unknown` in that case
> (§6.2). A comment in a single-version corpus is `unknown` on this
> axis, and it is `unknown` on both addresses.

### 4.2 `addressed`

**What it names.** The comment was answered — the manuscript does the
thing the comment asked for.

**Worked example.** Comment `c5` says *"Please state the splitting criterion
used for training"*. In v2, §3.1 gains two sentences: *"We split by crystal
family, so no family appears in both the training and the evaluation set.
The families are listed in Appendix C."* The question the comment asked is
answered by the manuscript: `addressed`.

**The boundary.** Against `partially_addressed`: `addressed` means the
comment's request is met in full. If the manuscript answers the question
but leaves part of it open — adds the splitting rule but not the list of
families, when the comment asked for both — that is
`partially_addressed`. If the manuscript changes something near the
comment without answering it at all, that is `not_addressed`.

### 4.3 `partially_addressed`

**What it names.** The comment was answered in part — some of what it
asked for is done, and some of it is not.

**Worked example.** Comment `c7` asks for two things: a geometry-only
baseline *and* a statement of whether the 800-surface test set is big
enough. In v2 the author adds the geometry-only baseline and the
comparison table, and never mentions the test-set size again:
`partially_addressed`.

**The boundary.** Against `addressed` and `not_addressed`: the middle
state is for comments that carry **more than one ask**. If the comment
carries a single ask, the answer is either met (`addressed`) or not met
(`not_addressed`) — `partially_addressed` is the one that needs a
sentence with two clauses and only one of them met. **And it is not a
hedge.** If you are reaching for `partially_addressed` because you are
unsure whether the change was big enough, that uncertainty is `unknown`
(§6.2), not a partial answer.

### 4.4 `not_addressed`

**What it names.** Something was done — the manuscript changed — and the
change does not answer the comment.

**Worked example.** Comment `c9` says *"Please remove the rows of Table 2
that report no variance"*. In v2 the rows of Table 2 are reordered and the
table's font is changed, and no variance is reported anywhere: the student
did something, and it did not help. `not_addressed`.

**The boundary.** Against `pending`: as above — *something happened* is
what separates them, and it is the difference the chain's unaddressed
listing exists to show. Against `partially_addressed`: nothing of the
ask was met.

---

## 5. The assessment outcome axis

### 5.0 What this axis asks

**Whether the advice turned out to hold.** The three outcomes come from
`src/labcairn/papers/assessments.py`, and they are the answer to a
question about the science, not about the process.

**The line this axis must not cross.** The chain's own rule: *the
advisor's advice may not be recorded as correct because the student's
change was accepted*. Acceptance is a fact about the process and belongs
to the response state; whether the advice was right is a separate claim
that needs its own evidence. If the only thing you have is "the student
made the change", that is **not** `established` — that is `unknown`.

### 5.1 `established`

**What it names.** The evidence supports the advice: the advice's point
holds.

**Worked example.** Comment `c2` says *"The training and test sets may share
crystal families; please split by family and re-run"*. After the
family-wise split, v2 reports GAT MAE 0.11 eV against the geometry-only
network's 0.19 eV, and the gap is larger than the seed spread. The advice's
point — that the split mattered — holds: `established`.

**The boundary.** Against `not_established` and `conflicted`: the
evidence points one way, and it is not "the change was accepted". If the
change was made and the numbers moved the other way, that is
`not_established` — not "the change was made, so it must be right".

### 5.2 `not_established`

**What it names.** The evidence shows the advice's point does not hold —
and this is a verdict, not an absence of one. The chain's design keeps
this member for exactly that reason: a system that can only say
"correct" cannot say "we do not know", and it cannot say "this was
wrong".

**Worked example.** Comment `c4` says *"800 test surfaces are too few; please
extend to at least 5,000 and re-run"*. At 5,000 surfaces the GAT–baseline
gap shrinks from
0.08 eV to 0.01 eV, which is inside the seed spread: the advice's point
— that the small test set was hiding the difference — does not hold.
`not_established`.

**The boundary.** Against `established`: one is the evidence pointing
for, the other the evidence pointing against, and neither is the default.
Against `unknown`: "the evidence does not show it" is
`not_established`; "there is no evidence to judge it by" is `unknown`.

### 5.3 `conflicted`

**What it names.** The evidence is in conflict — two readings of the
same question disagree.

**Worked example.** Two assessment records on comment `c2` disagree. The
advisor's own re-check, on the family-wise split, finds the gap still
there. An independent re-check on a different splitting seed finds GAT
and the baseline statistically indistinguishable. Both records are in the
corpus and they say opposite things: `conflicted`.

**The boundary.** Against `not_established`: `not_established` is one
body of evidence pointing one way; `conflicted` is two bodies of evidence
pointing two ways. **And it is not a tie to be broken by preference.**
The corpus's evidence ledger treats a conflict as a state to surface
rather than a terminal failure, and neither reading wins by being more
recent.

---

## 6. `unknown` is an answer

### 6.1 `unknown` and `other` are different things

| | What it asserts |
|---|---|
| **`other`** | the advisor pointed at a problem that is real, and none of the other eleven kinds names it — **you know what the problem is** |
| **`unknown`** | you cannot tell what the problem is — **you do not know** |

**Why the difference is a measurement, not a nicety.** Collapsing them
counts a gap in the taxonomy as a gap in the reading. `other` is
evidence that the label set is missing a class, and the frequency of
`other` is what tells the project so. `unknown` is evidence about a
particular comment and a particular annotator. If both are reported as
one number, then a taxonomy that needs one more class looks exactly
like a corpus that is too hard to read, and the two need opposite
responses.

**And `unknown` is never a shrug.** It is a value you chose, it is
scored as an answer, and it is in the distribution rather than filtered
out of it. An `unknown` row is a row somebody read and could not
settle; a missing row is a row nobody read, and the manifest's witness
tells those two apart.

### 6.2 The cases where `unknown` is the honest answer

**Case one — the anchor does not pair.** The comment element's locator
names a comment, but the body-side address is empty: there is no paragraph
and no character range, because the anchor did not resolve against the
baseline. The body-side address has nothing to read, so **all three of
its labels are `unknown`**. The comment address still gets its three
labels — the comment's own text is perfectly readable — and they are not
`unknown` for the same reason.

> *Scenario.* In `example-perov`, comment `c11` is a general remark about
> the paper as a whole and its anchor was never placed, so the manifest's
> `paragraph`, `start` and `end` are absent. The comment address gets
> `introduction_and_storyline` (the comment says the paper never says
> what it is trying to show); the body address gets `unknown`,
> `unknown`, `unknown`.

**Case two — the evidence is insufficient.** There is nothing in the
corpus that settles the question the axis asks, and the annotator cannot
settle it either. This is the assessment axis's most common honest
answer.

> *Scenario.* Comment `c8` says *"What are the units on the y axis of Figure
> 2?"*. The corpus holds the manuscript's text and the comments, but the
> figure is an image and no image is among the corpus's artefacts, and no
> sentence in the text states the unit either. Nothing in the corpus says
> what the unit is, so the assessment outcome is `unknown`. The issue kind
> is not `unknown` — the comment plainly asks about a figure's labelling,
> so that is `figures` — and the response state is `unknown` too, because
> with no later version there was nothing in which an answer could have
> appeared (§4.1).

**Case three — nobody responded, and the corpus cannot tell you so.**
A comment with no response record is `pending` **only when a later
version exists in which an answer could have appeared** (§4.1). When the
corpus holds no later version, you cannot distinguish "the student never
answered" from "the answer is in a version the corpus does not hold" —
and the second is the one the chain exists to refuse to guess about. The
response state is `unknown`.

**Case four — the label does not fit and you cannot say what does.** A
comment you can read, pointing at something you cannot place in any of the
twelve kinds, and you cannot even say what the problem was:
`unknown`, never `other`.

**One rule for all four.** You reach for `unknown` when the *reading* ran
out of evidence, and for `other` when the *reading* succeeded and the
*taxonomy* ran out of names. Those are different failures and they have
different owners.

### 6.3 `unknown` stays in the distribution

**Do not quietly leave a label blank.** A blank is not an answer, it is a
gap, and the manifest counts labels, not gaps. Every one of the three
axes on every one of the two addresses gets a word, and the word may be
`unknown`.

---

## 7. What you are not asked

### 7.1 Not whether the advice was good

**You are not asked to judge the quality of the advice.** "This comment
was a good suggestion", "the advisor was right to ask for this", "I would
have phrased it differently" — none of these is an annotation.

**This is LC-P2-14's blind question, not this axis's.** The blind
evaluation protocol (`docs/plans/LC-P2-14-ablation-protocol.md`) asks its
annotators whether the system reproduced an advisor's judgement; that
question is asked blind, by people who did not build the system, and it
is asked of the system's output rather than of a corpus. **The assessment
outcome axis is not that question**, because it is about whether a
specific piece of advice turned out to hold in a specific manuscript — a
claim with evidence behind it — and not about whether an advisor's taste
was reproduced.

**So what do you do with the feeling that a comment was a bad idea?**
You do not act on it. If a comment names a problem that is genuinely
outside the eleven kinds other than `other`, that is `other` (§3.12). If
you cannot place what it names, that is `unknown` (§6.2).

### 7.2 Not why the change was made that way

**You are not asked to infer the reason for a revision.** "The student
rewrote the paragraph this way *because* the advisor wanted X" is not
something you determine, and it is not something the manifest records.

**That inference is LC-P2-11's job.** The mentor guidance memory
(`docs/plans/LC-P2-11-task-breakdown.md`) reads this gold set to derive
guidance rules — rules that carry their source comment and their
counterexample. It cannot do that if the gold set already contains the
inference: a rule learned from a set that contains the answer is a rule
nobody learned. **Your reading supplies the raw material — what the
comment was about, what the manuscript did, and whether it held — and
LC-P2-11 does the reasoning.**

### 7.3 Not what the next version should do

**You are not asked what should happen next.** "You should add an
ablation over the number of layers" is advice, and advice is what the
advisor gave, not what the label set holds.

**The labels are descriptions of what is there.** Every label in this
guide can be filled by reading what exists in the manuscript and the
comment, with no judgement about what ought to exist.

### 7.4 And where an observation that does not fit goes

**There is no free-text field for it, and that is deliberate.** The
manifest's schema (`src/labcairn/papers/gold_manifest.py`) has a place
for every label and none for a remark. A note you want to write has
exactly two honest destinations:

- it changes **which** label you would choose, in which case choose the
  better one and say so in the disagreement (§8); or
- it is an observation about the manuscript that the label set does not
  carry, in which case the label that fits is `other` — if you can say
  what the advisor pointed at — or `unknown`, if you cannot.

**Do not smuggle a judgement into a label slot.** A response state of
`addressed` means the manuscript answered the comment; it never means the
answer was a good one.

---

## 8. The procedure

### 8.1 Two independent readings

**Two people label every item, and they do not see each other's work
before they have both finished.** Not "two people, then a discussion":
the independence is the point, and it is what makes the agreement number
mean anything. The manifest's own witness refuses an item whose two
annotations carry the same `annotator_id` — one person reading twice is
one reading, and an agreement computed over it is a statement about that
person's consistency on a single pass.

**What each annotator produces** is one block per item, containing their
`annotator_id`, the moment they finished (`annotated_at`), and the three
labels for the comment address and the three for the body address.

### 8.2 The arbiter writes a row, and does not overwrite

**The arbiter resolves each disagreement into a row of its own.** The
resolution block carries the arbiter's `arbiter_id`, the moment
(`resolved_at`), and their own labels for both addresses. **The two
original annotations stay exactly where they were.**

**Why the disagreement is kept rather than replaced.** A disagreement
that existed is information: it is the thing the agreement number is
computed from. A resolution that overwrote both readings would leave
nothing to compute an agreement over, and the number would be a
statement about the arbiter alone. **The manifest's witness watches for
this by name**: LC-P2-10's acceptance clause A5 names the test
`test_a_resolution_does_not_overwrite_the_disagreement`.

**When there is no disagreement,** the arbiter still writes a resolution
block — the manifest expects one per item — and their labels will match
the two readings.

### 8.3 Why the agreement number is worth having

**The number is reported with its denominator, and the denominator is the
number of items both annotators labelled** — not the number of items in
the manifest, and not the number either annotator labelled. An agreement
rate without the number it was computed over is a number nobody can read.

**And `unknown` is in the distribution.** Items where both annotators
wrote `unknown` count as agreement on that view; items where one wrote
`unknown` and the other a label count as disagreement. Filtering
`unknown` out of the denominator would make the taxonomy look better
than it is, and would hide exactly the rows a reader most needs to see.

### 8.4 The split is by project, and it is not the annotator's job

**Every version of one paper is in one partition.** Two versions of one
paper are two observations of one thing, and a split by row would put
version 1 on one side and version 2 on the other, where a system that
memorised version 1 could score on version 2 without having generalised.
The partition is a property of the corpus, it is in the manifest, and it
is not something you choose while annotating.

---

## 9. What you fill in for each comment

**The manifest's field names are the ones below**, taken from
`src/labcairn/papers/gold_manifest.py`. Do not invent a spelling: the
manifest refuses a field it does not know, and it refuses by name.

**The manifest's own top level** is `version` (the manifest's version),
`corpus` (the manuscripts it reads and the fixture each project came
from), `partitions` (the split, by project) and `items` (the entries
below). Those four are the corpus's to write, not yours, and §9.1–§9.3
describe the item block that is.

### 9.1 The item — its two addresses, and who owns what

| Field | Who fills it | What it is |
|---|---|---|
| `item_id` | the corpus | the item's id |
| `project_id` | the corpus | the paper project this comment belongs to |
| `version_id` | the corpus | the version the comment was written against |
| `feedback_id` | the corpus | the chain's feedback row for the comment |
| `fixture` | the corpus | the synthetic manuscript the item reads |
| `comment_id` | the corpus | the comment inside that fixture |
| `comment_locator` | the corpus | **the comment element's address** — the chain's locator, naming the part, the element path and the character range |
| `paragraph`, `start`, `end` | the corpus | **the body-side address** — the paragraph number and the half-open character range in the baseline's text |
| `annotations` | **you** | the two independent readings |
| `resolution` | the arbiter | the arbiter's row |

**The two addresses are already there.** Your job starts at
`annotations`. You do not write the locator and you do not write the
offsets — you read them, because §2 is about what each of them means.

### 9.2 One annotation — the block you write

| Field | What it is |
|---|---|
| `annotator_id` | who you are, as an id — **not** your name, and not a label |
| `annotated_at` | the moment you finished, ISO-8601 |
| `comment_address` | the labels for the comment element |
| `body_address` | the labels for the body-side position |

**And each of the two address blocks holds exactly three labels**, under
the axis names the manifest uses:

| Field | The axis | The values it accepts |
|---|---|---|
| `issue_kind` | issue kind | `research_question_and_motivation`, `novelty_and_contribution`, `introduction_and_storyline`, `method_and_hypothesis`, `data_quality`, `controls_and_ablation`, `statistical_conclusion`, `figures`, `sources`, `review_response`, `language_and_format`, `other`, `unknown` |
| `response_state` | response state | `pending`, `addressed`, `partially_addressed`, `not_addressed`, `unknown` |
| `assessment_outcome` | assessment outcome | `established`, `not_established`, `conflicted`, `unknown` |

**Six labels per annotation, twelve per item once both annotators have
filled it in.** All six are required, and a label outside the set is
refused by name — the refusal tells you which word was wrong rather than
saying only "invalid".

### 9.3 The resolution — the block the arbiter writes

| Field | What it is |
|---|---|
| `arbiter_id` | who arbitrated, as an id |
| `resolved_at` | the moment of the resolution, ISO-8601 |
| `comment_address` | the arbiter's three labels for the comment element |
| `body_address` | the arbiter's three labels for the body-side position |

**The same three-axis shape, and it sits beside the two annotations
rather than on top of them** (§8.2).

---

## 10. A whole item, end to end

**One comment of `example-perov`, carried all the way through.** This is
the same comment as §2.3, and it is here so that the whole chain —
reading, labelling, and filling in — is visible in one place.

**The item.**

- `item_id`: `item-perov-001-c7`
- `fixture`: the synthetic perovskite manuscript
- `comment_id`: `c7`
- `comment_locator`: the comment element in `word/comments.xml`, named by
  part, element path and character range
- `paragraph`, `start`, `end`: paragraph 4 of the baseline, the character
  range of *"We evaluate on a held-out set of 800 surfaces."*

**The comment element says:** *"Add a control experiment: with GAT as the only
model, a reader cannot tell whether the gain comes from the graph
structure or only from the features; please add a geometry-only network as
a baseline and report it on the same test set."*

**The later version.** v2 adds the geometry-only baseline and the
comparison table; it never mentions the 800-surface test set again.

**Annotator A writes:**

| | `issue_kind` | `response_state` | `assessment_outcome` |
|---|---|---|---|
| `comment_address` | `controls_and_ablation` | `addressed` | `not_established` |
| `body_address` | `data_quality` | `pending` | `unknown` |

**Annotator B writes:** the same `comment_address` labels except
`assessment_outcome` = `unknown`, and the same `body_address` labels.
B read the v2 numbers and could not tell whether the baseline gap of
0.01 eV is inside the seed spread, and said so rather than guessing.

**The arbiter resolves** the one disagreement. Reading the seed spread in
the corpus settles it: the gap is inside it, so the advice — that the
comparison would show the graph structure matters — does not hold, and
the arbiter's `comment_address` carries `not_established`. B's
`unknown` and A's `not_established` both stay in the manifest, and the
disagreement is what the agreement number is computed over.

**And the body address is left as the two annotators agreed it:** the
800-surface problem was never answered (`pending`), and nothing in the
corpus says whether that mattered (`unknown`).

---

## 11. Quick reference

**The twenty labels and the mistake each is most often mistaken for.**

| Axis | Label | Most often mistaken for | The question that settles it |
|---|---|---|---|
| issue kind | `research_question_and_motivation` | `novelty_and_contribution` | is the question unasked, or is the contribution wrong? |
| issue kind | `novelty_and_contribution` | `sources` | is *my claim* wrong, or is *the citation* wrong? |
| issue kind | `introduction_and_storyline` | `language_and_format` | should this information be elsewhere, or is this sentence badly written? |
| issue kind | `method_and_hypothesis` | `controls_and_ablation` | what *is* your method, or what *is it compared to*? |
| issue kind | `data_quality` | `statistical_conclusion` | is the data itself flawed, or is the inference from it too strong? |
| issue kind | `controls_and_ablation` | `method_and_hypothesis` | is a comparison missing, or a description missing? |
| issue kind | `statistical_conclusion` | `data_quality` | is the *inference* unsound, or the *inputs* unsound? |
| issue kind | `figures` | `language_and_format` | does the picture contradict the text, or is the prose clumsy? |
| issue kind | `sources` | `novelty_and_contribution` | is the citation wrong, or is your claim wrong? |
| issue kind | `review_response` | `controls_and_ablation` | is a promise unkept, or is an experiment missing? |
| issue kind | `language_and_format` | `introduction_and_storyline` | is the wording wrong, or the placement wrong? |
| issue kind | `other` | `unknown` | can you say what the problem was? |
| response state | `pending` | `not_addressed` | did *nothing* happen, or did something happen that did not help? |
| response state | `addressed` | `partially_addressed` | is every part of the ask met? |
| response state | `partially_addressed` | `unknown` | is one part of a two-part ask met, or are you unsure? |
| response state | `not_addressed` | `pending` | is there a change that did not answer it? |
| assessment outcome | `established` | `not_established` | does the evidence point for the advice, or against? |
| assessment outcome | `not_established` | `unknown` | does the evidence point against, or is there no evidence? |
| assessment outcome | `conflicted` | `not_established` | do two readings disagree, or does one reading say no? |
| all three | `unknown` | `other` | is it the *reading* that ran out, or the *taxonomy*? |

**And three things that are true everywhere in this guide:**

1. **Both addresses get all three axes.** Six labels per annotation.
2. **`unknown` is an answer, and it stays in the distribution.**
3. **You are describing what is there, not judging what should be**
   (§7).
