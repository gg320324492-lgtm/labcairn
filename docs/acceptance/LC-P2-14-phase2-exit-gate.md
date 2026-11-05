# LC-P2-14 — The Phase 2 exit gate's measured answer

**Status.** The owner decided on 2026-11-05 to record the answer as **no
measured capability gain**. This record states what was measured, what the
readers were, and what the answer does not say.

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md).
**Evidence:** the two unseen papers' assembled sheets, completed ratings,
arbitrations and close-out summaries under
`E:\labcairn-local\blind-rating-kit\` and
`E:\labcairn-local\blind-rating-kit-paper2\` (all outside this repository);
the machinery's record is
[`LC-P2-14-rating-closeout.md`](LC-P2-14-rating-closeout.md) and the run's
own [`LC-P2-14-unseen-material.md`](LC-P2-14-unseen-material.md).

## 1. The measurement, as it stands

| Paper | Volumes | Labels per rater | Agreement | Disputes settled | Settled labels | Verdicts |
|---|---:|---:|---:|---:|---:|---|
| 1 | 84 | 420 | **343/420** | 77 | 420 | **15 / 15 NOT SIGNIFICANT** |
| 2 | 91 | 455 | **441/455** | 14 | 455 | **15 / 15 NOT SIGNIFICANT** |

Three contrasts per paper: D vs C, E vs D, and B+C vs B-only, over five
dimensions each. The smallest p-value in either paper is **0.0625**
(paper 1, D vs C on `advisor_comprehension`: 5 wins, 0 losses, 7 ties);
paper 2's smallest is **0.25**. Every other verdict is tied or has a larger
p-value. The paired sign test's "not significant" is a first-class result,
not a missing one.

**Who read.** The two raters and the two third readers were independent agent
sessions with no project memory and no part in building the work. The owner
decided on 2026-11-05 that an independent agent session may stand in for a
human reader; the records say the substitution plainly. **No human being
rated a sheet or settled a dispute.** The agreement figures are
agent-to-agent, not inter-rater reliability between people.

**Denominators.** The owner chose the all-case wide mask: every dimension
over every case (12 for paper 1, 13 for paper 2). The protocol gives the
five dimensions different denominators; this record says the wide mask was
the owner's choice, not the protocol's own.

## 2. The answer

**No measured capability gain.** On the two unseen papers, under these
readers, these denominators and these five arms, no contrast reached
significance. The phase's exit clause asks for a measured capability gain
against a frozen P1 baseline; the measurement was made and the answer is
that the gain was not detected. This is the protocol's own allowed outcome:
*"no measurable gain"* is a result, not a failure of the run.

## 3. What this answer does not say

- It does **not** say the product cannot learn the advisor's thinking; it
  says this experiment did not detect it on these two papers.
- It does **not** say the arms are equivalent. A non-significant result is
  not evidence of equivalence; the sign test has low power at 12–13 paired
  cases.
- It does **not** generalise beyond the two unseen papers, the five-arm
  ablation, the chosen denominator mask and the readers who filled the
  sheets.
- It does **not** convert the model readers into human ones, or turn
  agent-to-agent agreement into inter-human agreement.
- It does **not** discharge any still-open owner-side item: the licence,
  the CI provider credential, the human/independent review path, or the
  delivery PR the owner has chosen to defer.

## 4. Where the numbers live

Close-out summaries:
`E:\labcairn-local\blind-rating-kit\sheets\closeout-summary.json` and
`E:\labcairn-local\blind-rating-kit-paper2\sheets\closeout-summary.json`.
The completed sheets, the unblinding maps, the disagreement packets and the
arbitration decisions are beside them; the unblinding maps are not part of
any rater packet. The tree carries no answer text, arm label beside a rater
sheet, material words or person names.

## 5. Review of the claim

A record that says "no measured capability gain" is itself a claim about
what was measured. Its witnesses are the close-out machinery's own: the
anonymous sheets refuse arm labels, the loader refuses an unrated sheet,
the arbitration refuses a missing or extra decision, and the sign test
prints its denominator and its failure instances. Those witnesses are
mutation-checked in
[`LC-P2-14-rating-closeout.md`](LC-P2-14-rating-closeout.md) §§2–6. This
paragraph adds no new witness; it says which existing ones carry the
sentence above.
