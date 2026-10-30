# LC-P2-14 — The blind evaluation and ablation protocol

**Status:** drafted 2026-10-30 with the route change, **before** the
implementation. **What it is for:** the phase's exit gate is *"measured
capability gain against a frozen P1 baseline, no scientific-claim
inflation"*, and P2-AMD-01 adds one more comparison and one more rule
about how it may be reported. **This protocol says what is measured, on
what, by whom, and what the result may and may not say.**

**The rule the protocol is built on:** *"没有在未见论文上的对照实验，就不能
宣称系统「学会了导师的科研思想」"* — **without a controlled experiment on
unseen papers, the system cannot be said to have learned the advisor's
scientific thinking.** So every arm below runs on papers the system has
never seen, and the split is checked.

## 1. The arms

**The five the phase already named**, on the same underlying model and a
comparable budget:

| | The arm |
|---|---|
| **A** | the current draft and a general model |
| **B** | + ordinary literature retrieval |
| **C** | + version differences |
| **D** | + the advisor's comments and the student's responses |
| **E** | + the review outcome and the confirmed rules |

**And the two contrasts that matter are D vs C and E vs D** — because the
question is not "does a model help" and not "does retrieval help", but
**"does the advisor's actual process help, and does the outcome of it help
more"**.

**And one more comparison, as an independent variable.** P2-AMD-01 asks
for the **role arrangement** to be measured separately from the evidence:

| | The arrangement |
|---|---|
| **B-only** | the guidance role alone |
| **B+C** | the guidance role with the independent critique role |

**Same evidence, same underlying model, same budget.** The only thing that
changes is whether a second role reviewed the output. **That is what makes
the comparison a measurement of the arrangement** — and it is why the
provider is held fixed here, even though a different supplier is a
legitimate thing to try later: **with a different supplier, a difference
measures the models and not the roles.**

## 2. The split, and the leak check

**The unit is the paper.** Every version of a paper, every comment on it,
every rule distilled from it and every assessment of it are in **one**
partition. **A test case is never a version and never an event.**

**And the leak check is a test, not a promise.** The final version of a
paper may not be reachable from the case that asks about its first draft:
not through the retrieval index, not through a rule distilled from a later
round, not through a case's own history. **The check runs over the
retrievable corpus of each case**, not over the database, because the
retrievable corpus is what the system can reach.

**The check is also run against the arms themselves.** An arm that differs
from another **only** because it can see more of the same paper's history
is a leak, and it is reported as one.

## 3. The annotators, and what they may not have done

**Blind.** The annotator **did not take part in the development** of the
system, and **did not annotate any case in the current test set**. A
person who wrote the rules cannot score the rules' effect.

**Two annotators and an arbiter**, for every case where they disagree
about the label — and the **inter-annotator agreement is reported with its
denominator**, because an agreement rate without the number of items it was
computed over is a number without a meaning.

**And `UNKNOWN` is a label.** "The evidence does not settle this" is a
**label**, not a failure and not a missing value. A protocol that forces
every case into a verdict has turned a measurement into a decoration.

## 4. What is measured, per case

**The five dimensions, each with its own denominator:**

| | The dimension | The denominator |
|---|---|---|
| 1 | **problem identification** — did it find the problem the advisor found? | the cases where the advisor's problem is known |
| 2 | **evidence support** — is the advice supported by what it cites? | the cases with a cited advice |
| 3 | **comprehension of the advisor's response** — did it understand what the advisor said and how the student answered? | the cases with a known advisor comment |
| 4 | **hallucination and mis-citation** — did it invent an experiment, a reference, an advisor's opinion, or misattribute one? | **every case** |
| 5 | **abstention** — did it abstain when the evidence was insufficient, and did it abstain for the right reason? | the cases where the evidence is insufficient |

**And two more, because the route is now a bill and a queue:**

| | | |
|---|---|---|
| 6 | **cost** — the spend per case, per arm | every case |
| 7 | **latency** — the wall clock per case, per arm | every case |

**Every dimension reports its denominator and its failure instances.** A
rate without a denominator is a number about nothing, and the failure
instances are what make the rate checkable.

## 5. What the result may and may not say

**This is the part the protocol exists to protect.**

- **D > C and E > D are not guaranteed.** The phase may find that the
  advisor's process does not help on these papers, and **that is a
  result**, and it is reported as a result.
- **More agents is not a gain.** If **B+C** does not beat **B-only**, or
  does not beat it enough to pay for itself, **that is the finding**,
  and the arrangement becomes a product decision rather than a default.
- **A significant difference in one dimension is not a phase gate.** The
  gate is about the whole, and a headline that carries one dimension
  while three others do not move is a headline, not a result.
- **The comparison is like-for-like or it is nothing.** A different model
  on one side of a comparison is a different comparison, and it is
  reported as a separate variable rather than folded into the arm.
- **"No scientific-claim inflation" is measured, not asserted.** Dimension
  4 is a count of inventions, and it is reported next to every gain.

## 6. What would make the result unusable

**These are the failure modes the protocol's checks exist to catch, and
each one is a test rather than a reviewer's diligence:**

1. **A paper's own later versions reachable from its earlier case** — the
   leak check.
2. **An annotator who developed the system, or who annotated the current
   test set** — recorded with the label set, before the labels are
   collected.
3. **An arm that differs from another only by seeing more of the same
   paper's history** — the arm-level leak check.
4. **A rate reported without its denominator, or without its failure
   instances** — the report's own check.
5. **A gain claimed on the dimensions that moved, with the ones that did
   not left out** — the report's own check.

## 7. The record

**The results land in `docs/acceptance/LC-P2-14-acceptance.md`**, with the
arms, the split, the annotators, the denominators, the failure instances,
the cost and the latency, **and the conclusion the numbers support — which
may be that the gain is not significant.**
