# LC-P3-08 — independent reviewer form (2026-11-14)

**Record class:** FORM FINALISED — a fillable review instrument, not a
completed review. No reader has read a trial record at a named commit; no
finding is classified; no owner has signed. This form is 08's deliverable 3
design ([`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §13 §6.6
deliverable 3), finalised from
[`LC-P3-08-reviewer-form-design.md`](../plans/LC-P3-08-reviewer-form-design.md)
(2026-11-10) with the 2026-11-10 synthetic dry run's accepted findings
already folded into the design (the FO-01 precedence carve-out is in the
ladder; the FO-05/R-08 wording fix is applied below in R-08).

**Date:** 2026-11-14.
**Authorities:** [`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md)
§13 decisions 6 and 7 (2026-11-10);
[`PHASE_3-execution-plan.md`](../plans/PHASE_3-execution-plan.md) §4 and §9;
[`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
§3.
**Form copy:** `LC-P3-08-review-<date>-<n>` (F-01) — one form per review
round; a re-review gets a new id.
**Tree this form was finalised at:** worktree
`E:\LabCairn\.claude\worktrees\silly-margulis-65e484`, branch
`claude/silly-margulis-65e484`, HEAD
`a7cde5999a9db1524e2ec5514685b449e43de4b1` (printed by `git rev-parse HEAD`
immediately before this file was written).

## 0. The rules this form carries

[`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
§3 governs Phase 3 reviews verbatim: an independent agent session may stand
in for **one human reader only** when the record carries the literal
disclosure sentence; the arbiter of a disagreement **must be a third
reader**; and the internal-trial rows defined by real advisor use **cannot
be simulated by any substitute**. Execution plan §4's closing rule repeats
the disclosure sentence and adds that real advisor and student trial use
cannot be simulated by an agent and reported as human use. Execution plan
§9 requires independent review at a named commit and forbids quoting an
unprinted SHA.

**Owner decision 7 (§13).** One named human reviewer designated by the
owner, plus one independent agent session as a second reader, carrying the
literal disclosure sentence where an agent stands in for a human reader.
The arbiter of a disagreement is a third reader. The trial's real-advisor
rows are not read by agents alone.

> **Wording amended 2026-11-18 — the "no project memory" phrase.** Both
> paragraphs above formerly described the agent second reader as one "with
> no project memory". In this harness every agent session started in this
> repository is injected at start with the repository's `CLAUDE.md` and the
> assistant's auto-memory index, and this project's session-start
> instructions direct the session to read its siblings' hand-over notes
> first; the independent second-reader session of 2026-11-18 measured all
> three exposures in its own context and declined to sign the template
> sentence asserting otherwise
> (`E:/labcairn-local/g4-t9-review-prep-20261118/reader-b/READER-B-PREP-NOTES-2026-11-18.md`
> §2). The owner ruled the same day that the wording must say what the
> harness actually delivers. The protected property is unchanged — the
> reader enters with zero finding ids, zero verdicts, zero expected answers,
> zero recorded expected SHAs and zero prior readers' classifications — and
> is now carried by F-09/B-02's entry-and-disclosure boundary. The
> disclosure sentence, the F-08/B-03 byte-equality, the no-simulation rule
> for real advisor and student rows and the third-reader arbiter rule are
> all unchanged.

**Owner decision 6 (§13).** The named reviewer classifies each finding
(`blocker` / `measured gap` / `routed defect`) at a named commit; a
disagreement goes to a third reader as arbiter; the owner signs the
classification with the exit decision. A blocker keeps the decision blocked
with its evidence address. No finding passes on a note alone.

**Designation note (added 2026-11-16, status update only — resolved
2026-11-16).** The owner designated `LabCairn` (originally designated **`LabCairn` (originally designated Xiaoqi Zhushou; superseded **Read 2026-11-21 (owner's ruling): the reviewer designation is now `LabCairn`** — the project's own name replaces the personal designation everywhere the trial records name a reviewer.)**; superseded **Read 2026-11-21 (owner's ruling): the reviewer designation is now `LabCairn`** — the project's own name replaces the personal designation everywhere the trial records name a reviewer.) as the named human
reviewer on 2026-11-16 (recorded in `docs/handoff/CURRENT.md` and
`docs/changelog/phase-3.md` at commit `17a1abf73f254843cf54e62b5687fb7e884c62bc`).
Form field F-05's placeholder (`[enter: owner-designated name]`) is a
blank to be filled at review time, not an unresolved decision; the
designation it waits on now exists. The designation does not complete any
F-field: the named reviewer's own reading, the commit it reads at, and
the owner's signature remain the trial's future acts.

**The literal disclosure sentence** — reproduced so it cannot be paraphrased
away; every field that carries it must match it byte-for-byte:

```text
independent agent session stood in for a human reader; no human being performed this reading
```

## 1. Scope marker (filled first, always)

| Field | Value to enter | Rule |
|---|---|---|
| F-00 Record class | `TRIAL` / `DESIGN` / `DRY RUN` | One of the three, exactly. For `DRY RUN`, F-08 and B-03 are canonical strings copied by the form preparer and are **not** a disclosure that any reading occurred; A-08 and R-08 check the record class too. (Dry-run finding FO-06, folded in.) |

## 2. Form header — fill in before any reading

| Field | Value to enter | Rule |
|---|---|---|
| F-01 Review id | `[enter: LC-P3-08-review-<date>-<n>]` | One form per review round. |
| F-02 Record read | `[enter: repository-relative path to the trial record]` | The trial record itself — not this form, not the protocol, not a substitute rehearsal. |
| F-03 Commit read | `[enter: full 40-character SHA printed by the command that named it]` | Execution plan §9: no unprinted SHA. Both readers name the same commit. |
| F-04 Trial protocol record | `[enter: repository-relative path]` | The protocol whose per-row map and seam statement this review checks. |
| F-05 Named human reviewer | `[enter: owner-designated name]` | Designated by the owner; **not** filled by an agent session. |
| F-06 Human reader's independence | `[enter: what this reader did not implement/write, and what was re-run]` | Execution plan §4: a reviewer who did not implement the work re-runs key cases at a named commit. |
| F-07 Second reader's identity | `[enter: independent agent session id]` | Independent agent session; its independence is the entry boundary of F-09, not an absence of injected context. |
| F-08 Second reader's disclosure | `independent agent session stood in for a human reader; no human being performed this reading` | Byte-equal to §0's sentence — the same string as B-03. A paraphrase, a blank or trailing whitespace fails. |
| F-09 Memory and entry boundary | `[enter: (1) what this session was given at start — injected context such as the repository's CLAUDE.md, the auto-memory index, and any hand-over or sibling note the start instructions directed it to read; (2) what it deliberately did NOT read — the files that carry the trial's or the preparation's prior conclusions; (3) which threads it was pre-exposed to, and how each is re-derived from the record and the on-disk evidence]` | The second reader enters with **zero finding ids, zero verdicts, zero expected answers, zero recorded expected SHAs and zero prior readers' classifications** for this review. The second reader reads the named record and its evidence, not the project's prior conclusions as instructions. A session that received none of the five is the clean case; a session that received one discloses it here and re-derives that thread from the record — the disclosure is the requirement, not the exposure. H-07 fails only when the session carried a conclusion in and reports it as a reading. |
| F-10 Real-advisor rows' human coverage | `[enter: which real-advisor rows the named human reviewer read]` | Decision 7: those rows are not read by agents alone. If any was read only by the agent session, the review is incomplete. |
| F-11 Arbiter | `[enter: third reader's name, or NONE — no disagreement]` | A third reader, never one of the two readers; required when any §6 disagreement row (D-01…) records a disagreement. With no such row, the only allowed value is exactly `NONE — no disagreement`. |
| F-12 Owner signature | `[enter: owner's decision and date, or PENDING]` | The owner signs the classification with the exit decision. The reviewer does not sign for the owner. |

## 3. Reader A — named human reviewer (fillable)

| Field | Value to enter |
|---|---|
| A-01 Date of reading | `[enter: YYYY-MM-DD]` |
| A-02 Commit actually checked out | `[enter: full SHA printed at checkout]` |
| A-03 Evidence addresses opened | `[enter: one row per §4 row — path + section anchor + digest/count/refusal class]` |
| A-04 Key cases re-run | `[enter: case id and observed result; a re-run is not a substitute for the human trial row]` |
| A-05 Findings raised | `[enter: finding ids, each pointing to a §5 classification row]` |
| A-06 Raw-material rule observed | `[confirm: no raw samples or replies entered the repository record; safe fields only]` |
| A-07 Real-advisor rows read | `[enter: row ids; agent readings do not stand in for these]` |
| A-08 Disclosure check | `[confirm: F-00, F-08 and B-03 agree — the record class is stated, and the disclosure string is byte-equal to §0's sentence]` |
| A-09 Signature | `[enter: name and date]` |

## 4. Reader B — independent agent second reader (fillable)

| Field | Value to enter |
|---|---|
| B-01 Session id and date | `[enter]` |
| B-02 Memory and entry boundary | `[enter: what the session start injected or directed this session to read; what was deliberately not read; which threads were pre-exposed and how each was re-derived from the record and the on-disk evidence]` |
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
reader, and the real-advisor rows' human coverage stays in A-07.

## 5. Findings and the classification ladder (decision 6)

The named reviewer classifies **each finding** at the named commit. The
second reader raises findings and classifications of its own; a difference
between the two is a disagreement and goes to the third reader (§6). The
owner signs the classification with the exit decision. No finding passes on
a note alone: a note is text, not a classification.

**Precedence (the FO-01 carve-out, from the 2026-11-10 synthetic dry
run).** The three predicates are evaluated in the order `blocker` >
`measured gap` > `routed defect`, with one exception that outranks all
three: **an owner-authorised named gap under §12 decision 5 / §14 item 7 is
`measured gap`, not `blocker`.** Without the carve-out the held-open "One
real model" row satisfies both predicates, and a reviewer could keep the
exit decision blocked against the owner's own answer. Every other §4 row
whose required passing-condition evidence is absent is `blocker`. The C row
prints the predicate that fired, so a classification is a checked value
rather than a label chosen after the fact.

| Class | Judging standard | What the evidence address must carry | Effect on the exit decision |
|---|---|---|---|
| `blocker` | The failure is in core security, original protection or delivery gating, or the trial record cannot show a §4 row its passing condition requires (execution plan §4's "Distribution and review" row names the first three expressly). A claim with no evidence address, a simulated real-advisor row, or a raw-sample leak is also a blocker of the record's honesty. | A repository-relative record path or authorised evidence path, its section anchor, the digest/count/refusal class that identifies the observation, the named commit, and the §4 row id. For a core-security failure: the injected case and the observed refusal or its absence. | **Keeps the decision blocked with its evidence address.** Not converted to a note or a gap by the reviewer or the arbiter on this form. |
| `measured gap` | A value or behaviour honestly not measured or not yet run, named as a gap with the condition that would close it, not breaking a §4 row's passing condition. The held-open "One real model" row (§12 decision 5, §14 item 7) is the named example. | The gap's name, the record path + section anchor where it is stated, the closing condition, and the citation to the ticket that owns it. Any digest or count quoted is printed by the command that measured it and anchored to its commit. | Recorded in the named-gap list and signed by the owner; it does not pass the row on a substitute. |
| `routed defect` | A product defect the trial found that is not a core-security/original-protection/delivery-gating failure: the product misbehaves, but the evidence can name the owning ticket and the finding does not itself keep the exit decision blocked (§13 §6.3: a gap is named with its evidence address and routed to the owner; it is not new scope for another ticket). | Defect id, reproduction case id, observed vs expected behaviour, evidence path + anchor + digest/count/refusal class, and the owning ticket/batch. | Routed with its address; the exit decision carries the routing list. |

### 5.1 Fillable classification rows

| Id | Finding | §4 row | Evidence address (path + anchor + digest/count/refusal class) | Predicate that fired | Class | Reader (A/B) |
|---|---|---|---|---|---|---|
| C-01 | `[enter]` | `[enter]` | `[enter]` | `[enter: P-B / P-G / P-D]` | `[blocker / measured gap / routed defect]` | `[A / B]` |
| C-02 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` |
| C-03 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` |

(Spare rows continue as needed; every finding gets exactly one C row per
reader who raised it.)

## 6. Disagreement and third-reader arbitration (LC-P3-00 §3)

1. **Record the disagreement, do not average it.** A difference in a
   finding's existence, class, evidence address, or in whether an honesty
   check passed, is one disagreement row below. The two readers keep their
   own readings; neither edits the other's form.
2. **The arbiter is a third reader.** Owner decision 7 and
   [`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
   §3 both say so. The arbiter is neither of the two readers and is named
   in F-11. A second opinion from one of the two is not arbitration.
3. **The arbiter reads the same named commit** and the two readers'
   evidence addresses, then writes one ruling row per disagreement: which
   class holds, which evidence address decides it, and the reason. The
   arbiter does not implement a fix and does not sign for the owner.
4. **A blocker stays a blocker.** If either reading classifies a finding
   `blocker` and the arbiter's ruling does not overturn it with an
   addressed measurement, the decision stays blocked with its evidence
   address. No finding passes on a note alone.
5. **The owner signs the final classification with the exit decision.**
   The arbiter's ruling, the two readings and the classification table
   travel together into the exit-decision record.

### 6.1 Fillable disagreement rows

| Id | Finding id | Reader A's class / claim | Reader B's class / claim | Third reader (F-11) | Ruling (class + deciding evidence address + reason) | Commit read by arbiter | Owner-signature state |
|---|---|---|---|---|---|---|---|
| D-01 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[full printed SHA]` | `[PENDING / signed]` |
| D-02 | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[full printed SHA]` | `[PENDING / signed]` |

If there is no disagreement, F-11 says exactly `NONE — no disagreement` and
this table stays empty. An empty table with two conflicting
classifications in §5.1 is a failed H-07/H-02 check, not a clean review.

## 7. Honesty checks (H)

A failed honesty check is itself a finding with its own evidence address and
class. H-01, H-03 and H-06 failures are `blocker`s of the record's honesty.

| Check | Fails when |
|---|---|
| H-01 Substitution | A substitute reading, synthetic rehearsal or agent run entered a real-advisor/student/reopen row; the "One real model" row passed on 06's substitute half; the disclosure sentence missing or altered where an agent stood in for a human reader (byte-compare against §0's sentence, after one defined trim/backtick removal). |
| H-02 Evidence address | A §4 row with no path + anchor + identifying digest/count/refusal class, or a SHA not printed by the command that named it. |
| H-03 Raw material | Material text, a raw DOCX or replies in a repository record; only de-identified evidence and synthetic reproductions belong there (execution plan §4's closing rule). |
| H-04 Mutual citation | A row claimed from [`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md)'s evidence alone, or a 02 citation without record path + section anchor (mapping design §3's mutual anchor). |
| H-05 Seam statement | The trial protocol's seam statement absent, or the root-kinds limit reclassified as a defect without a measurement (protocol design §4.1; protocol record §4). |
| H-06 Role boundary | The reviewer or agent writing the owner's decision, the owner writing the reader's classification, or 08 repairing a product defect. |
| H-07 Independence | Either reader implementing the work under review; the arbiter being one of the two readers; the agent session carrying a conclusion about the trial into the review and reporting it as a reading (F-09/B-02 define the disclosure that keeps an exposed session honest; the disclosure sentence of §0 is unchanged). |

| Honesty-check row | H-01 | H-02 | H-03 | H-04 | H-05 | H-06 | H-07 |
|---|---|---|---|---|---|---|---|
| Result | `[pass / fail + evidence address]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` | `[enter]` |

## 8. Review close-out (fillable)

| Field | Value to enter |
|---|---|
| R-01 §4 rows covered | `[enter: the eight row ids and the sample-class rule, each with its evidence address]` |
| R-02 Findings | `[enter: count of C rows by class]` |
| R-03 Disagreements | `[enter: count of D rows; 0 only when F-11 says exactly NONE — no disagreement]` |
| R-04 Blocker state | `[enter: NONE, or each blocker's id and evidence address]` |
| R-05 Named gaps | `[enter: gap names, owning tickets, and the condition that closes each]` |
| R-06 Routed defects | `[enter: defect ids and routing destinations]` |
| R-07 Real-advisor coverage | `[enter: A-07's rows and each one's human-performed evidence address]` |
| R-08 Disclosure verified | `[confirm: F-00 states the record class; F-08 and B-03 are byte-equal to §0's literal sentence — no paraphrase, no blank, no trailing whitespace]` |
| R-09 Owner classification signature | `[enter: PENDING until the owner signs the classification with the exit decision]` |
| R-10 Review status | `[enter: REVIEW COMPLETE — OWNER PENDING when R-01…R-09 are addressed at the named commit; OWNER CLOSE-OUT COMPLETE only after R-09 is signed]` |

(R-08 carries the 2026-11-10 dry run's FO-05 fix: the disclosure check is
byte-equality with the §0 sentence plus the F-00 record-class statement,
not the weaker "appears" wording. R-10 splits review completeness from the
owner's close-out, per the same dry run's FO-10, so `PENDING` never blocks
a complete review and never substitutes for a signature.)

## 9. What this form does not do

It performs no reading, raises no finding, classifies nothing, and signs
nothing. It does not replace the named human reviewer, does not stand in
for any real-advisor row, and does not fill F-05, F-12, R-09 or any owner
field. The disclosure sentence covers a reading only — never an advisor, a
student, a reopen or a decision. A form filled from this copy enters the
trial record's review as its own dated deliverable, with both readers'
commit SHAs printed by the commands that named them.
