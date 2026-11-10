# LC-P3-08 — independent reviewer form (design)

**Status:** DESIGN — the trial itself waits on the installed build.
**Work order:** [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §13
(`LC-P3-08`), §13's owner decisions answered 2026-11-10 (decisions 6 and 7),
[`PHASE_3-execution-plan.md`](PHASE_3-execution-plan.md) §4 and §9, and
[`LC-P3-00-board-opening-decisions.md`](../acceptance/LC-P3-00-board-opening-decisions.md)
§3. **This document is a form design, not a completed review.** No reader has
read a trial record at a named commit here; no finding is classified; no
owner has signed.

All links are relative to `docs/plans/`. This form is the design of 08's
deliverable 3 ("the named reviewer's independent review at a named commit")
and of the classification half of the exit-decision evidence. The trial
protocol it reads is
[`LC-P3-08-trial-protocol-design.md`](LC-P3-08-trial-protocol-design.md);
the mutual-citation rules it checks are in
[`LC-P3-08-evidence-mapping-design.md`](LC-P3-08-evidence-mapping-design.md).

## 0. The two rules this form must carry

[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3 governs
Phase 3 reviews verbatim: an independent agent session with no project memory
may stand in for **one human reader only** when the record carries the literal
disclosure sentence; the arbiter of a disagreement **must be a third reader**;
and the internal-trial rows defined by real advisor use **cannot be simulated
by any substitute**. Execution plan §4's closing rule repeats the disclosure
sentence and adds that real advisor and student trial use cannot be simulated
by an agent and reported as human use. Execution plan §9 requires
independent review at a named commit and forbids quoting an unprinted SHA.

Owner decision 7 (§13) fixes the reading shape: **one named human reviewer
designated by the owner, plus one independent agent session with no project
memory as a second reader, carrying the literal disclosure sentence where an
agent stands in for a human reader. The arbiter of a disagreement is a third
reader. The trial's real-advisor rows are not read by agents alone.**
Owner decision 6 fixes the classification shape: **the named reviewer
classifies each finding (`blocker` / `measured gap` / `routed defect`) at a
named commit; a disagreement goes to a third reader as arbiter; the owner
signs the classification with the exit decision. A blocker keeps the decision
blocked with its evidence address. No finding passes on a note alone.**

The literal disclosure sentence, reproduced once so it cannot be paraphrased
away:

> `independent agent session stood in for a human reader; no human being performed this reading`

## 1. Form header — fill in before any reading

| Field | Value to enter | Rule |
|---|---|---|
| F-01 Review id | `[enter: LC-P3-08-review-<date>-<n>]` | One form per review round; a re-review gets a new id. |
| F-02 Record read | `[enter: repository-relative path to the trial record]` | Must be the trial record, not this design and not a substitute rehearsal. |
| F-03 Commit read | `[enter: full 40-character SHA printed by the command that named it]` | Execution plan §9: no unprinted SHA. Both readers name the same commit. |
| F-04 Trial protocol record | `[enter: repository-relative path]` | The protocol whose per-row map and seam statement this review checks. |
| F-05 Named human reviewer | `[enter: owner-designated name]` | Designated by the owner. Not filled by an agent session. |
| F-06 Human reader's independence | `[enter: what this reader did not implement/write, and what was re-run]` | Execution plan §4: a reviewer who did not implement the work re-runs key cases at a named commit. |
| F-07 Second reader's identity | `[enter: independent agent session id]` | Independent agent session with no project memory. |
| F-08 Second reader's disclosure | `independent agent session stood in for a human reader; no human being performed this reading` | Decision 7 fixes the agent second reader, so this field is required and must equal B-03 verbatim. A paraphrase or a blank is a failed disclosure check. |
| F-09 Memory boundary | `[enter: how the agent session's lack of project memory was established]` | The second reader reads the named record and its evidence, not the project's prior conclusions as instructions. |
| F-10 Real-advisor rows' human coverage | `[enter: which real-advisor rows the named human reviewer read]` | Decision 7: those rows are not read by agents alone. If any was read only by the agent session, the review is incomplete. |
| F-11 Arbiter | `[enter: third reader's name, or NONE — no disagreement]` | A third reader, never one of the two readers, and required when a §5.1 disagreement row (D-01…) records a disagreement. With no such row, the only allowed value is `NONE — no disagreement`. |
| F-12 Owner signature | `[enter: owner's decision and date, or PENDING]` | The owner signs the classification with the exit decision. The reviewer does not sign for the owner. |

## 2. Reader A — named human reviewer (fillable)

| Field | Value to enter |
|---|---|
| A-01 Date of reading | `[enter: YYYY-MM-DD]` |
| A-02 Commit actually checked out | `[enter: full SHA printed at checkout]` |
| A-03 Evidence addresses opened | `[enter: one row per §4 row — path + section anchor + digest/count/refusal class]` |
| A-04 Key cases re-run | `[enter: case id and observed result; a re-run is not a substitute for the human trial row]` |
| A-05 Findings raised | `[enter: finding ids, each pointing to a §3 classification row]` |
| A-06 Raw-material rule observed | `[confirm: no raw samples or replies entered the repository record; safe fields only]` |
| A-07 Real-advisor rows read | `[enter: row ids; agent readings do not stand in for these]` |
| A-08 Disclosure check | `[confirm: F-08 and B-03 are the literal sentence from §0]` |
| A-09 Signature | `[enter: name and date]` |

## 3. Reader B — independent agent second reader (fillable)

| Field | Value to enter |
|---|---|
| B-01 Session id and date | `[enter]` |
| B-02 Project memory | `[enter: NONE, and how the session was started without it]` |
| B-03 Literal disclosure | `independent agent session stood in for a human reader; no human being performed this reading` |
| B-04 Commit actually read | `[enter: full SHA printed at the read]` |
| B-05 Evidence addresses opened | `[enter: one row per §4 row — path + section anchor + digest/count/refusal class]` |
| B-06 Findings raised | `[enter: finding ids, each with its evidence address]` |
| B-07 Coverage limit | `[confirm: this session did not perform advisor use, student use, a real reopen, or the owner's decision]` |
| B-08 Real-advisor rows | `[enter: which rows were cross-checked only; the human reader's A-07 remains the coverage]` |
| B-09 Signature/transcript anchor | `[enter: the transcript or record section that holds this reading]` |

Reader B's disclosure sentence is copied literally, not generated. Decision
7 fixes the agent as the second reader, so there is no reading of this form
in which that field is optional; the named human reviewer remains the first
reader and the real-advisor rows' human coverage stays in A-07.

## 4. The classification ladder (decision 6)

The named reviewer classifies **each finding** at the named commit. The
second reader raises findings and classifications of its own; a difference
between the two is a disagreement and goes to the third reader (§6). The
owner signs the classification with the exit decision. No finding passes on a
note alone: a note is text, not a classification.

**Precedence, added after the synthetic dry run of 2026-11-10 (FO-01).** The
three predicates below are evaluated in the order `blocker` > `measured gap`
> `routed defect`, with one exception that outranks all three: **an
owner-authorised named gap under §12 decision 5 / §14 item 7 is
`measured gap`, not `blocker`.** Without that carve-out the held-open "One
real model" row satisfies both B (its §4 passing-condition evidence is
absent) and G (the owner ruled it a named gap), and a reviewer could keep
the exit decision blocked against the owner's own answer. Every other §4
row whose required passing-condition evidence is absent is `blocker`. The
C row prints the predicate that fired, so a classification is a checked
value rather than a label chosen after the fact.

| Class | Judging standard | What the evidence address must carry | Effect on the exit decision |
|---|---|---|---|
| `blocker` | The failure is in core security, original protection or delivery gating, or the trial record cannot show a §4 row its passing condition requires. Execution plan §4's "Distribution and review" row names the first three expressly. A claim with no evidence address, a simulated real-advisor row, or a raw-sample leak is also a blocker of the record's honesty. | A repository-relative record path or authorised evidence path, its section anchor, the digest/count/refusal class that identifies the observation, the named commit, and the §4 row id. For a core-security failure: the injected case and the observed refusal or its absence. | **Keeps the decision blocked with its evidence address.** It is not converted to a note or a gap by the reviewer or the arbiter on this form. |
| `measured gap` | A value or behaviour that is honestly not measured or not yet run, is named as a gap with the condition that would close it, and does not break a §4 row's passing condition. The held-open "One real model" row (§12 decision 5, §14 item 7) is the design's named example. | The gap's own name, the record path + section anchor where it is stated, the condition that would close it, and the citation to the ticket that owns it. If a digest or count is quoted, it is printed by the command that measured it and anchored to its commit. | Recorded in the named-gap list and signed by the owner; it does not pass the row on a substitute. |
| `routed defect` | A product defect found by the trial that is not a core-security/original-protection/delivery-gating failure: the product misbehaves, but the evidence can name the owning ticket or batch and the finding does not itself keep the exit decision blocked. §13 §6.3 says a gap is named with its evidence address and routed to the owner; it is not new scope for another ticket. | Defect id, reproduction case id, observed vs expected behaviour, evidence path + anchor + digest/count/refusal class, and the owning ticket or owner-routing destination. No repair is performed by 08. | Routed to the owner; the exit decision states the route and its evidence address. A routed defect is not silently "fixed" by reclassifying it as a note. |

Every classification row below must name its class from exactly those three
values. `known limit` is not a fourth class and it is not a finding: §13
decision 4 rules the `root_kinds` seam a known limit, not a defect, and it
is recorded in the trial protocol's seam statement and the record's known
limits. A reviewer who files it as a `routed defect` or a `blocker` without
a new measurement has raised a disagreement for the third reader
([`LC-P3-08-trial-protocol-design.md`](LC-P3-08-trial-protocol-design.md)
§4.1). A different, measured failure of the product's approval-record
minting is its own finding and is classified on its own evidence.

### 4.1 Fillable finding rows

| Id | Finding (one sentence) | §4 row or record section | Evidence address (path + anchor + digest/count/refusal class) | Fired predicate (`B` / `G` / `D` / `owner-authorised named gap`) | Class (`blocker` / `measured gap` / `routed defect`) | Reader raising it | Owner-signature state |
|---|---|---|---|---|---|---|---|
| C-01 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[A or B]` | `[PENDING / signed with exit decision]` |
| C-02 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[A or B]` | `[PENDING / signed with exit decision]` |
| C-03 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[A or B]` | `[PENDING / signed with exit decision]` |

The fired-predicate column is what makes the precedence rule checkable: `B`,
`G` and `D` name the three standards in the order they were evaluated, and
`owner-authorised named gap` is the carve-out whose class is forced to
`measured gap`. A row whose predicate and class disagree is a failed
honesty check, routed to the third reader as a disagreement.

Add rows as needed. A row with a blank evidence address is not a finding the
owner can sign. A row whose class is a note, an observation or "PASS WITH
NOTES" is not a classification and is returned to the reader.

### 4.2 The honesty checks each reader applies

| Check | What fails the review |
|---|---|
| H-01 Substitution | A substitute reading, synthetic rehearsal or agent run entered in a real-advisor/student/reopen row; the "One real model" row passed on 06's substitute half; the disclosure sentence missing where an agent stood in for a human reader. |
| H-02 Evidence address | A §4 row with no path + anchor + identifying digest/count/refusal class, or with a SHA not printed by the command that named it. |
| H-03 Raw material | Material text, raw DOCX or replies in a repository record; only de-identified evidence and synthetic reproductions belong there (execution plan §4's closing rule). |
| H-04 Mutual citation | A row claimed from `LC-P3-02`'s evidence alone, or a 02 citation without the record path + section anchor. The checklist is in [`LC-P3-08-evidence-mapping-design.md`](LC-P3-08-evidence-mapping-design.md). |
| H-05 Seam statement | The trial protocol's seam statement absent, or the root-kinds limit reclassified as a defect without a measurement; see [`LC-P3-08-trial-protocol-design.md`](LC-P3-08-trial-protocol-design.md) §4.1. |
| H-06 Role boundary | The reviewer or agent writing the owner's decision, the owner writing the reader's classification, or 08 repairing a product defect. |
| H-07 Independence | Either reader implementing the work under review; the arbiter being one of the two readers; the agent session carrying project memory. |

A failed honesty check is itself a finding with its own evidence address and
class. H-01, H-03 and H-06 failures are `blocker`s of the record's honesty.

## 5. Disagreement and third-reader arbitration (LC-P3-00 §3)

1. **Record the disagreement, do not average it.** A difference in a finding's
   existence, class, evidence address, or in whether an honesty check passed,
   is one disagreement row (§6, D-01…). The two readers keep their own
   readings; neither edits the other's form.
2. **The arbiter is a third reader.** Owner decision 7 and
   [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3 both
   say so. The arbiter is neither the named human reviewer nor the
   independent agent second reader, and is named in F-11. A second opinion
   from one of the two is not arbitration.
3. **The arbiter reads the same named commit** and the two readers' evidence
   addresses, then writes one ruling row per disagreement: which class holds,
   which evidence address decides it, and the reason. The arbiter does not
   implement a fix and does not sign for the owner.
4. **A blocker stays a blocker.** If either reading classifies a finding
   `blocker` and the arbiter's ruling does not overturn it with an addressed
   measurement, the decision stays blocked; §13 decision 6 says a blocker
   keeps the decision blocked with its evidence address. No finding passes
   on a note alone.
5. **The owner signs the final classification with the exit decision.** The
   arbiter's ruling, the two readings and the classification table travel
   together into the exit-decision record.

### 5.1 Fillable disagreement rows

| Id | Finding id | Reader A's class / claim | Reader B's class / claim | Third reader (F-11) | Ruling (class + deciding evidence address + reason) | Commit read by arbiter | Owner-signature state |
|---|---|---|---|---|---|---|---|
| D-01 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[full printed SHA]` | `[PENDING / signed]` |
| D-02 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[full printed SHA]` | `[PENDING / signed]` |

If there is no disagreement, F-11 says `NONE — no disagreement` and this
table stays empty. An empty table with two conflicting classifications in
§4.1 is a failed H-07/H-02 check, not a clean review.

## 6. Review close-out (fillable)

| Field | Value to enter |
|---|---|
| R-01 §4 rows covered | `[enter: the eight row ids and the sample-class rule, each with its evidence address]` |
| R-02 Findings | `[enter: count of C rows by class]` |
| R-03 Disagreements | `[enter: count of D rows; 0 only when F-11 says NONE]` |
| R-04 Blocker state | `[enter: NONE, or each blocker's id and evidence address]` |
| R-05 Named gaps | `[enter: gap names, owning tickets, and the condition that closes each]` |
| R-06 Routed defects | `[enter: defect ids and routing destinations]` |
| R-07 Real-advisor coverage | `[confirm: A-07 names the human reader's coverage; agent readings did not stand in]` |
| R-08 Disclosure | `[confirm: the literal sentence appears in F-08 and B-03]` |
| R-09 Owner decision | `[enter: owner's decision from the evidence, with date; PENDING until signed]` |
| R-10 Review status | `[enter: complete only when R-01…R-09 are addressed at the named commit]` |

The owner's decision is not a field the reviewers fill. This form ends with
`R-09 PENDING` until the owner signs the classification with the exit
decision; a design document never fills it.
