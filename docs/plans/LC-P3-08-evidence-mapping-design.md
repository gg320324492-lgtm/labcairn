# LC-P3-08 — mutual evidence mapping with LC-P3-02 (design)

**Status:** DESIGN — the trial itself waits on the installed build.
**Work order:** [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §13
decision 3 ("one supply, one run"), §13 §§6.4–6.8, §5.9, §14 item 4 and the
§12 owner-decision block; [`PHASE_3-execution-plan.md`](PHASE_3-execution-plan.md)
§4 and §9; [`LC-P3-00-board-opening-decisions.md`](../acceptance/LC-P3-00-board-opening-decisions.md)
§3. **This document is not a trial record, not a review, and not an exit
decision.** No cross-reference has been executed here.

All links are relative to `docs/plans/`. The trial protocol whose rows this
mapping protects is
[`LC-P3-08-trial-protocol-design.md`](LC-P3-08-trial-protocol-design.md);
the reviewer form whose honesty checks use this checklist is
[`LC-P3-08-reviewer-form-design.md`](LC-P3-08-reviewer-form-design.md).

## 0. The decision, stated exactly

§13 decision 3, answered 2026-11-10, accepts option A: `LC-P3-02`'s recorded
real-sample loop is an **input** to 08's trial record; 08 still runs its own
advisor-to-student-to-advisor loop and cites 02's result. The two records
cross-reference each other, and **08 never claims a row from 02's evidence
alone**. A second real sample was not commissioned, and 02's measurement
does not stand in for 08's real-advisor row. §14 item 4 and §5.9 record one
supply serving 02's real-sample half, ADR-0021's final adoption and 08's
trial. §6.5 names that sample as a one-directional dependency; §6.2 and
[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3 forbid
substituting for the real-advisor rows.

Therefore the shape of "one supply, two uses" is:

| | `LC-P3-02`'s real-sample loop | `LC-P3-08`'s trial |
|---|---|---|
| Material | The same owner-supplied advisor sample (one supply, no second commission). | The same owner-supplied advisor sample, used in 08's own advisor → student → advisor loop. |
| Product of the use | A measured fidelity/loop record: digests, structure counts, refusal classes, artifact facts. | A trial record: what a real advisor, a real participant and the installed build did, row by row. |
| Relation | **Input** to 08; 02 cites 08 as the trial that consumes its result. | **Consumer** of 02's result; 08 cites 02's record by anchor, never as its own row. |
| What it cannot become | A substitute for 08's real-advisor row, real reopen, named review or exit decision. | A claim that any §4 row passed because 02 measured something. |

A cross-reference is a **field-level citation with an address**, not a
verdict transfer. The trial record always carries its own observation for
each §4 row it claims.

## 1. What actually exists today, and what does not

Verified against the tree this design is written in:

| Record / file | Exists now | Role in the mapping |
|---|---|---|
| [`LC-P3-02-support-matrix.md`](../acceptance/LC-P3-02-support-matrix.md) | Yes | The synthetic support matrix (31 samples, structure-class verdicts) and its own "real advisor sample held open" statement. It is a matrix, not the real-sample loop. |
| [`LC-P3-02-substitute-run-2026-11-08.md`](../acceptance/LC-P3-02-substitute-run-2026-11-08.md) | Yes | The substitute-set run record. Its §"The open half" now cites the later measured 42-arm machine half and keeps the human dual-host reopen checklist open. The old `NOT RUN` label for the real-sample loop belongs to its dated 2026-11-08 state, not to the later tree. |
| [`LC-P2-02-acceptance.md`](../acceptance/LC-P2-02-acceptance.md) and [`LC-P2-02-review.md`](../acceptance/LC-P2-02-review.md) | Yes | Phase 2 restart-durable consent records. They are **not** `LC-P3-02`'s real-sample record; a `LC-P2-02-*` name must not be cited as if it were. |
| [`ADR-0021-manuscript-editing-rewrite.md`](../adr/ADR-0021-manuscript-editing-rewrite.md) | Yes | Status `proposed`; final adoption must cite the real-sample run. It is a third consumer of the supply, not a substitute for either loop. |
| [`LC-P3-02-real-sample-2026-11-10.md`](../acceptance/LC-P3-02-real-sample-2026-11-10.md) | Yes | §5.9's dated machine-half record, landed with `LC-P3-02`'s merge: 42/42 arms, 14 produced, 28 refused, 8 artifacts and report digest `a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`. It closes the machine half only; the human dual-host reopen half stays `NOT RUN`. |
| 08's trial record, its review and its exit decision | **No** | These are the gated half of §6.8; they wait on the installed build and the trial itself. |

The `LC-P3-*` acceptance records that do exist —
[`LC-P3-06-substitute-first-2026-11-10.md`](../acceptance/LC-P3-06-substitute-first-2026-11-10.md)
and [`LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md) —
are 06's own bounded validation. §12 decision 5 says 06's real half having
run changes what the "One real model" named gap names, not §14 item 7's
ruling. They are not 02's real-sample record and are not converted into a
trial row.

## 2. Fields 08 may cite from 02's real-sample record

Decision 3 says 02's recorded loop is an input. The citation surface is
**digests, counts, refusal classes and record addresses — never prose**.
This table fixes the allowed fields and the exact reason each is safe. A
field not in this table is not a citation field; it stays in the authorised
environment.

| Field group | Examples of the field (shape, not a value invented here) | Why it is citable | What 08 may do with it |
|---|---|---|---|
| Sample identity | `sha256` of the advisor sample, byte size, sample's role label (`real-advisor-sample`), supply date and authorised-location handle | A fingerprint names bytes without carrying them; §6.4 requires actual samples by fingerprint, never by content. | Assert that 08's trial sample is the same supply, or record a measured mismatch as a finding with its own address. |
| Structure counts | comment count, tracked-insertion/deletion counts, media-part count, paragraph count, structure-class verdicts | Counts are safe fields; they identify an observation without reproducing text. | Compare 08's import-time counts to 02's; name a disagreement with both addresses. |
| Artifact and text digests | input/output `sha256`, accepted/rejected-text digests, artifact digests, manifest digests | A digest is a content-bound identifier and no prose; execution plan §9 anchors values to printed SHAs. | Bind 08's delivery record to the same input version by digest; compare an output digest only where 08 itself produced the bytes. |
| Refusal classes and outcomes | refusal class names, location-failure class names, open/reopen result classes, host/version identifiers | Class names are the vocabulary the §4 rows already use; they carry no material text. | Cite 02's refusal evidence as **supporting context** for a support-matrix expectation; 08 still records its own refusal observation for its own §4 row. |
| Row/record addresses | 02's record path, section anchor, finding/row id, commit printed by the command that named it | An address is how a claim is checked; execution plan §9 requires the named commit. | Build the mutual anchor (§3) and let a reader re-open the cited place. |
| Status labels | `NOT RUN`, `named gap`, `PASS WITH NOTES` as they appear in 02's own record | A label is a record fact, not a verdict for 08. | State honestly what 02's record says; never promote it into 08's row. |

Fields 08 must **not** cite or copy: comment bodies, tracked-change text,
paragraph text, replies, advisor prose, model prose, raw DOCX, or any
reconstruction of the sample's content. Execution plan §4's closing rule
and §13 §6.4 keep raw samples and replies in the authorised environment;
only de-identified evidence or synthetic reproductions belong in this
public repository. Where a refusal detail could carry prose, it is reduced
to its class name and digest before it enters a repository record.

## 3. The mutual anchor

A cross-reference is valid only when both records can be opened at the
named place. The anchor shape is:

```
record path + section anchor + identifying digest/count/refusal class + printed full commit SHA
```

| Direction | What the citing record carries | What the cited record carries back |
|---|---|---|
| 08 → 02 | `02 record path`, the section where the field was measured, the field's value (digest/count/refusal class), the printed full SHA of the tree read, and a one-line statement of what 08 used it for. | — (08's side of the anchor is the citation itself.) |
| 02 → 08 | — | 02's real-sample record names 08's trial record as the consumer of its result, with 08's record path and section anchor, and states explicitly that its own measurement is an **input**, not 08's advisor row, reopen, review or exit decision. |

The reverse link is a decision-3 obligation ("the two records cross-reference
each other"), not a licence for 02 to grade 08. Both directions say the same
three things: one supply, two distinct runs, and no verdict transfer. A
cross-reference without a section anchor is a path, not an address; a
cross-reference with a SHA that was not printed by the command that named it
is not a citation at all.

Because §5.9's real-sample record does not exist in this tree, the 08 → 02
half of this anchor is **designed, not filled**: the trial record will fill
`02 record path` and its section anchor only when the record lands with
`LC-P3-02`'s merge. Until then the honest value is
`record lands with LC-P3-02's merge`, and no 08 row may be marked satisfied
by that placeholder.

## 4. Anti-impersonation checklist

This is the checklist 08's trial record must satisfy and the reviewer form's
H-04 check applies. Each line is answerable from the record; a blank or a
prose answer is a failure.

| # | Check | Passing condition |
|---|---|---|
| 1 | Own observation | Every §4 row 08 claims has at least one evidence address produced by 08's own loop (T1–T7 in the trial protocol), not only a citation to 02. |
| 2 | Field boundary | Every 02 citation is one of the §2 field groups. No comment body, tracked-change text, paragraph text, reply, advisor prose, raw DOCX or model prose appears in 08's repository record. |
| 3 | No verdict transfer | No 02 status label (`PASS`, `NOT RUN`, `named gap`, `PASS WITH NOTES`, `real-sample loop: NOT RUN`) is used as 08's row verdict. |
| 4 | No substitute advisor | 02's measured loop, a synthetic rehearsal, a dev-build dry run and an agent reading are never entered in a real-advisor, student, real-reopen, named-review or exit-decision row. |
| 5 | Real-model row | The "One real model" §4 row remains a named gap (§12 decision 5, §14 item 7). 06's substitute-first and real-half records are cited as their own ticket's bounded validation, never as 08's passing row; Phase 2's `real_model_smoke = NOT RUN` keeps its wording. |
| 6 | Mutual anchor completeness | Both records name each other by path + section anchor; the 08 trial record's 02 citation carries a printed full SHA; a missing record is written `record lands with LC-P3-02's merge` rather than given an invented filename. |
| 7 | Identity, not equality of results | The shared sample fingerprint lets 08 assert "same supply". It does not let 08 assert "same result". A count/digest disagreement is recorded as a finding with both addresses. |
| 8 | Seam and boundary | The `root_kinds` seam is cited as a known limit from [`LC-P3-04-binding-loop-2026-11-10.md`](../acceptance/LC-P3-04-binding-loop-2026-11-10.md) §6, not as a defect found by 02 or 08; raw evidence stays outside the repository. |
| 9 | Honest status | Where 02's real-sample record has not landed, 08's own row says so. A citation to a non-existent file, a `LC-P2-02-*` record mistaken for 02's real-sample record, or an unprinted SHA is a blocker of the record's honesty in [`LC-P3-08-reviewer-form-design.md`](LC-P3-08-reviewer-form-design.md) §4.2. |
| 10 | Owner's decision untouched | The cross-reference does not sign the exit decision. The owner decides from 08's evidence; the reviewer classifies findings at a named commit; the arbiter is a third reader on disagreement. |

## 5. What the eventual trial record writes

At trial time, and only after `LC-P3-02`'s real-sample record lands, the 08
trial record carries a short mutual-citation section with exactly these rows:

| Row | Content |
|---|---|
| M-01 | Sample identity: 02's record path + section anchor, the sample `sha256` and byte size from 02's record, 08's own T1 supply fingerprint, and `same supply: YES/NO` with both addresses. |
| M-02 | Fields cited: one row per cited digest/count/refusal class, each with 02's path + anchor and 08's own observation address. |
| M-03 | 08's own loop: the T1–T7 record addresses, so a reader can see the trial's rows do not rest on M-01/M-02. |
| M-04 | The named gap: "One real model" with §12 decision 5 / §14 item 7 and 06's two records cited as their own ticket's validation. |
| M-05 | Reverse link: 02's real-sample record's path + anchor where it names 08 as the consumer; if that link has not landed, the honest value is `record lands with LC-P3-02's merge`. |
| M-06 | Boundary statement: no material text or raw DOCX in this repository record; raw samples and replies remain in the authorised environment. |

M-01…M-06 are the shape of the mutual citation, not evidence that any of
them has run. The reviewer re-opens every address at the named commit; the
owner signs the classification with the exit decision.
