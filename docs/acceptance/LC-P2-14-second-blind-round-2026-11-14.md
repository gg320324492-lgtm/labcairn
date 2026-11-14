# LC-P2-14 — the second blind-rating round: agent raters, closed 2026-11-14

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the revision this record was measured against
(`114a8a4c36ae34a897f7cbd0e68b286dc9ab877f`, local `main` at this writing);
the tree has moved since. Follow the sentence, not the number.

**Date:** 2026-11-14. **Work order:**
[LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation and
ablation). **Machinery:**
[`LC-P2-14-preparation.md`](LC-P2-14-preparation.md) and
[`LC-P2-14-rating-closeout.md`](LC-P2-14-rating-closeout.md). **This
record:** the second round of the close-out's rating — both raters and the
third reader were independent agent sessions — and nothing else. It is
recorded under the owner's 2026-11-05 reader rule ([`LC-P2-14-rating-closeout.md:391`](LC-P2-14-rating-closeout.md) — `independent agent sessions, not human beings`), the standing substitution statement the first round's record already carries.

**Anchors:** 8 — every converted pointer below carries the words it cites.

## 1. What ran, and what did not

The second round repeated the close-out's rating half on both unseen papers:
two fresh agent sessions rated each paper's blind sheet independently
(salted item ids, different sheet orders, no arm key, no unblinding map, no
answer-route metadata), a third agent session — the arbiter, distinct from
both raters — settled every disagreement, and the settled tables went
through the close-out's consistency check and paired sign tests. The check
and the close ran in a temporary directory against the completed sheets;
the kit's original directory was read but not modified, and nothing outside
`docs/` changed in this tree.

What did **not** happen: no human being rated a sheet in this round, no
capability claim is made, and no result here reopens Phase 2's closed gate ([`LC-P2-28-phase2-open-items.md:3`](LC-P2-28-phase2-open-items.md) — `Phase 2's measured exit gate is **CLOSED, PASS WITH NOTES**`). The first round's record ([`LC-P2-14-rating-closeout.md:387`](LC-P2-14-rating-closeout.md) — `## 9. The close-out ran — with model readers, not human ones`) already holds the machinery's description; this record adds only the second round's numbers.

## 2. Agreement, with its denominator

Per the protocol — agreement is counted over every item × dimension and
reported with its denominator
([`LC-P2-14-ablation-protocol.md:73`](../plans/LC-P2-14-ablation-protocol.md) — `inter-annotator agreement is reported with its`),
and the two raters' completed tables compare like this:

| Paper | Labels compared | Agreed | Rate | Disagreements | Settled by arbiter | Excluded |
|---|---|---|---|---|---|---|
| 1 (84 volumes) | 420 | 395 | **0.9405** | 25 | 25 | 0 |
| 2 (91 volumes) | 455 | 451 | **0.9912** | 4 | 4 | 0 |

Every disagreement fell in the **`advisor_comprehension`** dimension —
25 of 25 in paper 1, 4 of 4 in paper 2. No rater pair gave opposite
`yes`/`no` labels on any item; every dispute sat on the `yes`/`unknown`
boundary, and the arbiter read each disputed answer's text before labelling.
Paper 1's arbiter settled all 25 disputes as `unknown`; paper 2's settled 1
`yes` and 3 `unknown`.

**The `unknown` label is deliberate, not a gap.** The dimension asks whether
an answer shows it understood what the advisor said and how the student
answered; an answer that never touches that exchange cannot show either, and
the protocol says exactly that such a case carries `unknown` as its verdict
([`LC-P2-14-ablation-protocol.md:77`](../plans/LC-P2-14-ablation-protocol.md) — `"The evidence does not settle this" is a`); the dimension's own denominator is the table row that names it ([`LC-P2-14-ablation-protocol.md:89`](../plans/LC-P2-14-ablation-protocol.md) — `| 3 | **comprehension of the advisor's response** — did it understand what the advisor said and how the student answered? | the cases with a known advisor comment |`). The concentration of disputes in this one
dimension is a statement about where two careful
readers' line-drawing differs, not about the other four dimensions.

## 3. The contrasts: all fifteen NOT SIGNIFICANT, both papers

After the arbiter settled the disagreements, the settled tables ran through
the close-out's paired sign tests: three contrasts (D vs C, E vs D,
B+C vs B-only) over the five dimensions — 15 verdicts per paper, 30 in the
round. **All 30 are NOT SIGNIFICANT.** The only non-all-tied contrast in
paper 1 is B+C vs B-only on `advisor_comprehension` (4 wins, 1 loss,
7 ties, p = 0.3750); in paper 2 it is the same contrast (1 win, 0 losses,
12 ties, p = 1.0000). As in the first round, a not-significant verdict is
reported as not significant — it is not rounded up into a claim.

## 4. The two rounds side by side — numbers only

| Round | Raters | Paper 1 agreement | Paper 2 agreement |
|---|---|---|---|
| First (2026-11-05) | independent agent sessions | 343/420 (0.8167) | 441/455 (0.9692) |
| Second (2026-11-14) | independent agent sessions | 395/420 (0.9405) | 451/455 (0.9912) |

The first round's figures and dispute counts are recorded in [`LC-P2-14-rating-closeout.md:406`](LC-P2-14-rating-closeout.md) — `| 1 (84 volumes) | 420 | **343/420 (81.7%)** | 77 | 420 | 0 |` and its paper-2 row beside it. This record states the two rounds' numbers
and nothing more: **a higher agreement rate is not a quality claim**, and
neither round's rate measures how well any rater hit the property a
dimension asks about. The two rounds also differ in where their
disagreements sat — the first round's paper-1 disputes spread across
several dimensions (77 settled labels), the second round's all sat in one —
so the rates are not measuring the same distribution, and no trend is
claimed.

## 5. Where the evidence lives

The run's sheets, the arbiter's per-dispute decisions, the consistency
check's and close-out's outputs, and the report the numbers above were read
from live **outside the repository**, under
`E:\labcairn-local\blind-rating-agent-run\` (`arbitration\`,
`kit-check\paper{1,2}\sheets\`, `rater-A\`, `rater-B\`). They stay outside
for the same reason the first round's do ([`LC-P2-14-unseen-material.md:13`](LC-P2-14-unseen-material.md) — `**What this record does not carry.** The paper's title, its`).
`tests/test_no_reference_leakage.py` is what keeps them out. This record
carries none of that material: no answer text or digest beyond the counts,
no item id, no case key, no issue key, no annotator route — only the
agreement counts, the dimension names the protocol itself defines, and the
verdict labels.
