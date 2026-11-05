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

## 5. The gate verdict — 2026-11-05

**Owner decision: Phase 2's exit gate is CLOSED, PASS WITH NOTES.** The
protocol allowed *"no measurable gain"* as an answer; the measurement was
made, the answer was recorded in §2, and the gate is judged on whether the
phase produced an honest, witnessed answer — not on whether the answer was
favourable.

**The notes that travel with the verdict:**

1. **The readers were independent agent sessions, not human beings.** Under
   the owner's 2026-11-05 decision they may stand in for human readers, but
   the agreement figures are agent-to-agent, not inter-human reliability.
2. **Windows only for the independent G1/G2 re-review**; POSIX-only
   witnesses remain NOT MEASURED. Its clean whole-suite run was stopped
   because it was found concurrent with the baseline harness, so no
   whole-suite count backs that review — its 33 row-level mutations do.
3. **The real-provider smoke is NOT RUN** in the frozen baseline (harness
   exit 2) and the CI credential is the owner's.
4. **The licence is unresolved** and the repository deliberately carries no
   LICENSE file.
5. **The delivery PR is deferred** by the owner's choice; `main` is ahead of
   `origin/main` and nothing has been pushed.

**What the verdict does not do.** It does not start Phase 3, does not
claim a capability gain, does not turn a non-significant result into
equivalence, and does not close the owner-side items above. A later human
rating, if it ever exists, replaces the current sheets rather than adding
to them.

## 6. Review of the claim

A record that says "no measured capability gain" is itself a claim about
what was measured. Its witnesses are the close-out machinery's own: the
anonymous sheets refuse arm labels, the loader refuses an unrated sheet,
the arbitration refuses a missing or extra decision, and the sign test
prints its denominator and its failure instances. Those witnesses are
mutation-checked in
[`LC-P2-14-rating-closeout.md`](LC-P2-14-rating-closeout.md) §§2–6. This
paragraph adds no new witness; it says which existing ones carry the
sentence above.

## 7. Delivery follow-up (2026-11-06)

The five notes in §5 and the "does not discharge" sentence in §3 are a
2026-11-05 snapshot; they are kept verbatim as the gate's own historical
record. Three of their surrounding facts have since changed:

- PR #148 merged as
  `0d654b2038051805eb0ab410783ea2fe90545506`, with all required checks
  green. The delivery branch was deleted locally and on the remote. The
  deferred-PR note no longer describes the current delivery state.
- Batch 11's version-graph record, its approved real-store write and the
  three negative witnesses were merged into local `main` at
  `c2cd25a2f817a7a28e37f3ed2b571af8e979961f`. The merge's witness ledger
  reported `LOST -- none`.
- The owner chose MIT, confirmed an individual copyright holder and the
  year 2026, and required a coordinated local commit that waits for the
  next delivery batch. No `LICENSE` has been written yet, so "no rights
  granted" remains true of the current tree. The owner also expects no
  further paper-material batches.

The real-provider smoke is still NOT RUN and its CI credential is still
the owner's; the POSIX-only witnesses in the independent G1/G2 re-review
are still NOT MEASURED. Nothing in this section changes the measured
answer, starts Phase 3, or converts the independent agent readers into
human readers.
