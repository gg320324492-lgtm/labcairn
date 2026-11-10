# LC-P3-08 — trial protocol (design)

**Status:** DESIGN — the trial itself waits on the installed build.
**Work order:** [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §13
(`LC-P3-08`), with the owner decisions answered 2026-11-10 at the end of
§13 and the sequencing answer at the end of §12. **This document is not a
trial record, not a review, and not an exit decision.** It defines what those
records must say before any of them is written.

All links in this file are relative to `docs/plans/`.

## 0. What this design is, and what it is not

`LC-P3-08` is the executed exit gate: one advisor-to-student-to-advisor loop
on the installed build, its named reviewer's independent read, and the
owner's decision from the evidence ([execution plan §2](PHASE_3-execution-plan.md),
[§4](PHASE_3-execution-plan.md) and [§9](PHASE_3-execution-plan.md);
[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §§2–3).
The 2026-11-10 sequencing answer (§12 decision 2) keeps 07 and 08 `BLOCKED`
on `LC-P3-05`'s installed build: only substitute-first **design** work may
start now, and each piece is labelled design, not a deliverable until run.
A dev-build rehearsal is not authorised and may never be entered in an
execution plan §4 row.

This batch therefore writes:

| Design document | What it fixes before the trial |
|---|---|
| this file | The loop's steps, the per-row evidence map, the `root_kinds` seam statement and the shape of its witness. |
| [`LC-P3-08-reviewer-form-design.md`](LC-P3-08-reviewer-form-design.md) | A fillable independent-review form: two readers, the literal disclosure, the classification ladder and third-reader arbitration. |
| [`LC-P3-08-evidence-mapping-design.md`](LC-P3-08-evidence-mapping-design.md) | How 08 cites `LC-P3-02`'s real-sample record without claiming 02's evidence as its own row. |

It writes no product code, no implementation test, no trial row, no reviewer
reading, and no owner signature. The three designs are the permitted half of
§13's §6.8 table; the advisor's real sample, the real reopen, the named
reviewer's read and the exit decision are the gated half. The owner decides
from the evidence whether Phase 3 is closed — no document in this batch
declares the exit.

## 1. Authorities and dependencies

| Authority | What binds this protocol |
|---|---|
| [`PHASE_3-execution-plan.md`](PHASE_3-execution-plan.md) §2, §4, §9 | The gate's shape, the eight §4 rows plus the sample-class rule, independent review at a named commit, and no unprinted SHA. |
| [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §13 §§6.1–6.8 and its decision block | Scope, deliverables, dependencies, the substitute-first split, and owner decisions 3, 4, 6 and 7. |
| [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §12 decision 2 and §14 item 7 | Installed-build precondition; the "One real model" row stays a named gap at the exit decision and does not pass on a substitute. |
| [`LC-P3-00-board-opening-decisions.md`](../acceptance/LC-P3-00-board-opening-decisions.md) §§2–3, §5 | The gate wording, the reviewer form, and the trial machine's support matrix. |
| [`PHASE_3-work-orders.md`](PHASE_3-work-orders.md) §5.9 and §14 item 4 | One advisor sample supply serves 02's real-sample half, ADR-0021's final adoption and 08's trial; 08 cites 02 and does not stand on 02 alone. |
| [`LC-P3-04-binding-loop-2026-11-10.md`](../acceptance/LC-P3-04-binding-loop-2026-11-10.md) §6 | The measured `root_kinds` seam, restated as a known limit in §4 below. |

Dependencies are one-directional: the installed build (`LC-P3-05`), the
operator manual, backup/rollback and known limits (`LC-P3-07`), the owner's
advisor sample and named trial participant, the owner's named reviewer, and
the owner's exit decision. `LC-P3-06`'s two halves are cited as their own
records; neither half turns into 08's real-advisor row. Q77 and Q82 stay at
their triggers.

## 2. Sample classes and the no-material boundary

[Execution plan §4](PHASE_3-execution-plan.md) names three sample
classes: public synthetic DOCX for CI and negative tests, a de-identified
owner-authorised domain sample for the controlled real model, and an
authorised trial sample for advisor review. **Raw samples and replies remain
in the authorised environment; only de-identified evidence or synthetic
reproductions belong in this public repository.** §13 §6.4 repeats this rule.

The protocol therefore fixes these rules for every step and every record:

1. The advisor's real sample is named by role and fingerprint (`sha256`,
   byte size, structure counts), never by its prose. The repository carries
   no material text and no raw DOCX from the sample.
2. The student and advisor exchanges happen on the authorised trial machine
   and the supported Word hosts recorded in
   [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §5
   (WPS Office primary, Microsoft Office 2010 compatibility reference).
   The hosts are re-measured live if the trial environment changes.
   §3 rule 2 and §4.9 of the work orders make open/reopen **human-performed
   checklist steps**: no COM, no ProgID and no UI automation of WPS or Word
   may drive them, and no agent may fill a human host result.
3. A repository record cites an evidence address — a path outside the
   repository, a section anchor, and a digest or count — not the content at
   that address. Counts, digests, refusal class names and row identifiers
   are safe fields; paragraph text, comment bodies, tracked-change text,
   replies and model prose are not.
4. **No real advisor row is simulated.** §13 §6.2, §6.7 and §6.8,
   [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3 and
   execution plan §4's closing rule all say so. A substitute reading, a
   synthetic rehearsal and an agent's own run may be labelled exactly that;
   none may be reported as advisor use, student use, a real reopen or a
   real-advisor §4 row. The disclosure sentence in
   [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3
   covers a reading only, never an advisor.
5. A dry run of the §4 mapping against the substitute build, if one is ever
   authorised, is a rehearsal: it is labelled as one and is never entered in
   a §4 row. Under §12 decision 2 no dev-build rehearsal is authorised now.

## 3. The advisor → student → advisor loop

The loop follows [execution plan §2](PHASE_3-execution-plan.md):
the advisor supplies a DOCX carrying comments or tracked changes; an
authorised participant imports the paper and approved reference material on
one machine; the product locates each opinion, proposes an evidence-linked
response, performs only approved edits on an independent copy, and exports
a marked-up draft, a clean draft, a point-by-point response table and a
quality report. The advisor reopens the marked-up draft in Microsoft Word
and the two sides exchange DOCX files. The Word hosts actually used are
those of [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md)
§5: WPS Office primary, Microsoft Office 2010 compatibility reference.
Each step below fixes who, on which
host, and which record the step produces. The record names are the shapes
the trial record must carry; none of them exists yet, and none is created by
this design batch.

| Step | Actor and host | Action | Record produced (at trial time) |
|---|---|---|---|
| T0 — Preconditions | Owner; installed build on the clean supported Windows machine | Designate the advisor, the student/participant and the named human reviewer; name the advisor sample by fingerprint; freeze the build's commit, package hash, OS and Word versions. | Precondition sheet: roles, sample fingerprint, build identity, support-matrix re-measurement, and the recorded fact that the installed build exists (the §12 decision 2 precondition). No role is filled by an agent. |
| T1 — Advisor supplies | Real advisor; authorised environment, outside the repository | Supply the commented/revised DOCX and the approved reference material. | Supply receipt: sample `sha256`, byte size, structure counts, date, and the authorised location. No prose enters the repository. |
| T2 — Import | Real participant; installed build on the trial machine | Create a new project, import the paper and approved material, keep the original read-only and record the content hash and independent-copy id. | Import record: task id, input version id, original digest, independent-copy id, refusal/acceptance result, and the original-hash comparison. |
| T3 — Locate and propose | Installed build, with model suggestions kept separate from human decisions | Locate every supported input opinion; propose an evidence-linked response; mark each location failure explicitly. | Proposal record: per-opinion id, located/failed location, evidence address, suggestion record, and the four review statuses (accepted, partly accepted, rejected, pending) as separate decision entries. |
| T4 — Review and approve | Real participant; installed build | Review each suggestion; accept or reject; keep model suggestions and advisor confirmations separate. Where the real advisor confirms, that confirmation is the advisor's own record. | Approval/decision record: decision id, actor, verdict, evidence address, version edge, and the approved-edit set. This is the record `_fill_chain` mints chain rows from (§4). |
| T5 — Apply and deliver | Installed build; trial machine | Apply **only approved edits** to the independent copy; export the marked-up draft, clean draft, point-by-point response table and quality report. | Delivery record: four deliverable ids and digests, one task/input/output version binding, publication receipts, and the clean-draft match to approved edits. |
| T6 — Advisor reopens | Real advisor; supported Word hosts, human-performed | Reopen the marked-up draft in the supported Word environment (§5: WPS Office primary, Microsoft Office 2010 reference); check open/reopen without a repair prompt and verify non-target equations, images, tables and relationships; the two sides exchange DOCX files. | Reopen record: host names and versions, human-performed open/reopen result, repair-prompt result, non-target preservation result, and the advisor's own confirmation. No COM/ProgID/UI automation and no agent stands in for this row. |
| T7 — Gate rows | Trial operator; installed build and 07's handover products | Exercise the §4 rows that need refusal, interruption or distribution evidence, using the operator manual, backup/rollback and known limits; the "One real model" row stays a named gap per §14 item 7. | Per-row evidence records, each addressed in §5. The real-model row's own record stays `named gap`; [`LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md) is cited as its own ticket's bounded run, not converted into a trial row. |
| T8 — Trial record | Trial operator; repository record (de-identified) | Assemble the loop as run: sample by fingerprint, versions, what each participant did, what each gate row's evidence shows, and the cross-reference to 02's real-sample record. | Trial record under `docs/acceptance/`, with the evidence-address table of §5 and the mutual citation of [`LC-P3-08-evidence-mapping-design.md`](LC-P3-08-evidence-mapping-design.md). Raw evidence stays outside. |
| T9 — Independent review | One named human reviewer + one independent agent second reader; third reader only on disagreement | Read the trial record and its evidence at a named commit, classify each finding, and sign the review. | The fillable form in [`LC-P3-08-reviewer-form-design.md`](LC-P3-08-reviewer-form-design.md), carrying the literal disclosure where the agent stands in for a human reader. Real-advisor rows are not read by agents alone. |
| T10 — Exit decision | Owner only | Decide from the evidence whether Phase 3 is closed; sign the classification with the exit decision. | Exit-decision record: the owner's verdict, the row-by-row evidence addresses, the named-gap list, and any blocker's evidence address keeping the decision blocked. |

A step that produces no named record does not satisfy its row. A row whose
evidence is a substitute run is labelled a rehearsal, not a trial result.

## 4. Seam statement: `root_kinds` and approval-record minting

**Seam statement (to be carried verbatim in the trial protocol record).**

> `source.inventory` and `source.read` declare `root_kinds={"source"}` in
> [`capabilities.py`](../../src/labcairn/security/capabilities.py). Output
> versions therefore do not appear in the trajectory listing, and the
> papers layer's mint-from-the-file paths —
> `labcairn.papers.edits.record_edits_from_revisions`,
> `labcairn.papers.revisions.record_revision_events` and
> `labcairn.papers.feedback.record_feedback` when addressed at an output
> version — refuse before a rule is asked. This is a known limit, not a
> defect, and widening
> the capability's root kinds before the trial was not authorised. The
> product's actual behaviour is `labcairn.papers.binding._fill_chain`: it
> mints the chain's edit rows from the **approval records** through the
> store's own writers, with the actor `model` and the grade
> `human_verified`, keeping every vocabulary and grant check. The dossier
> carries those rows; the trajectory panel shows the input round's rows.

The measured basis is
[`LC-P3-04-binding-loop-2026-11-10.md`](../acceptance/LC-P3-04-binding-loop-2026-11-10.md)
§6 gap 1. The source check for this design was
[`capabilities.py`](../../src/labcairn/security/capabilities.py)
(`CapabilityId.SOURCE_READ`, `CapabilityId.SOURCE_INVENTORY`),
[`binding.py`](../../src/labcairn/papers/binding.py) (`_fill_chain`, its
docstring and the `EditActionRow` writer), and
[`test_binding_loop.py`](../../tests/test_binding_loop.py)
(`test_the_chain_rings_are_filled_from_the_published_bytes`, which reads the
minted `EditActionRow` from the store and states the listing drops the child
version's material). Owner decision 4 at §13 keeps `root_kinds={"source"}`
and requires this statement to carry its own witness.

### 4.1 Witness design for the seam statement

The witness is a **statement witness**: it fails when the trial protocol
record stops saying what the product does. It is designed here, not
implemented in this design batch. Its intended shape:

| Witness property | What the eventual check asks |
|---|---|
| The exact seam statement is present | The trial protocol record contains the quoted statement's four assertions: `root_kinds={"source"}`; the listing does not show output versions; the limit is known, not a defect; `_fill_chain` mints from approval records and is the product's actual behaviour. A protocol that omits, weakens or reverses one fails. |
| The assertion is bound to its source, not to a copy | The check reads the registry's `root_kinds` for the two capability ids and the bound edit rows from the store the way [`test_binding_loop.py`](../../tests/test_binding_loop.py) does; it does not trust a hand-copied literal. A widened root kind or a mint-from-file path that starts working makes the statement stale and the check red. |
| The witness watches its own reading | A negative case removes or alters one assertion in a fixture copy of the protocol and requires the check to fail for that assertion, not for lint or an unrelated edit. This is the project's "a rule needs a witness of its own" discipline, applied to a statement. |
| The trial's own classification honours it | The reviewer form's finding for "output versions absent from trajectory listing" is classified as a **known limit**, not a blocker or a routed defect, with §6 gap 1 and this statement as its evidence address. A finding that reclassifies it without a measurement is a disagreement for the third reader (see the reviewer-form design). |

The witness belongs to the trial protocol record's owning batch, not to this
design: a design document is not a deliverable until run. The check must not
be written so that a phrase in a comment, rather than the protocol record's
own statement, keeps it green.

## 5. Per-row evidence mapping (execution plan §4)

Each of the eight §4 rows, plus the closing sample-class rule that governs
them all, is mapped **before** the trial runs to its evidence requirement
and its named output file. The names below are the record shapes
the trial must produce; they are not claims that the files exist. No row may
be graded by a record written after the row was graded. "Evidence address"
means the authorised path or repository record plus its section anchor and
the digest/count/refusal class that identifies the observation.

| §4 row | Evidence requirement | Output file (to be produced at trial time) | Address shape |
|---|---|---|---|
| Import to delivery | A commented or revised sample runs through the installed build from a new project; marked draft, clean draft, response table and quality report all bind to one task, one input version and one output version. | `trial-delivery-record` | One row per deliverable: task id, input/output version ids, four deliverable ids and digests, publication receipts; §4's binding equality asserted. |
| Original and format | Original hash unchanged; both DOCX files open and reopen in the supported Word environment without a repair prompt; clean draft matches approved edits; non-target equations, images, tables and relationships survive; changes outside the support matrix refused or handed to a person. | `trial-original-and-reopen-record` | Pre/post `sha256`, host names/versions, open/reopen and repair-prompt results, non-target class counts, refusal or handover class names; [`LC-P3-02-support-matrix.md`](../acceptance/LC-P3-02-support-matrix.md) cited for the matrix. |
| Point-by-point response | Every supported input opinion located or explicitly a location failure; accepted/partly accepted/rejected/pending status; automatic edits link to opinion, evidence, operator and version; model suggestions and advisor confirmations separate records. | `trial-response-record` | Per-opinion id, location result, decision id, evidence address, operator, version edge, suggestion id and advisor-confirmation id; §4's seam statement explains why minted rows are read from the dossier. |
| Research quality | The sample contains a directly editable case, a case needing further evidence and an uncertain-location case; missing experiments, references or data block a quality pass or become named tasks; file-delivery and research-quality statuses decided separately. | `trial-quality-record` | Three named case ids, missing-item/task ids, two separate status fields with their own evidence addresses; no status inferred from the other. |
| Permission and privacy | Cross-project references, path escape, writes to the original, forged or expired approvals, unauthorised outbound data and instructions embedded in the document all have refusal evidence; the real model receives only approved, de-identified content; logs and receipts use safe fields. | `trial-refusal-record` | One refusal class per observation, its injected case id, the observed refusal name, and the safe-field list; no material text in the repository record. The real-model clause cites its own approved/de-identified scope, not a substitute's. |
| Cancel, retry and recovery | Two side-effectful interruption points around publication exercised; cancellation, duplicate submission and restart resolve to safe retry, recovered result or manual check; original intact and output receipts not duplicated. | `trial-recovery-record` | Two interruption ids, each with the injected state, outcome class, original digest before/after, and the receipt-id set showing no duplicate. |
| One real model | The installed build runs one controlled de-identified case; the model returns at least one locatable, reviewable revision suggestion and a person reviews it before delivery; budget/permission failure causes no outbound call; timeout and unavailability have explicit degraded paths; Phase 2's `real_model_smoke = NOT RUN` is not rewritten. | `trial-real-model-gap-record` — **held open as a named gap** | The named gap's evidence address plus the citation to [`LC-P3-06-substitute-first-2026-11-10.md`](../acceptance/LC-P3-06-substitute-first-2026-11-10.md) and [`LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md) as their ticket's records. §12 decision 5 and §14 item 7 keep this row a named gap at the exit decision; a substitute never passes it. |
| Distribution and review | A clean supported Windows environment proves install and run; rollback preserves user data; evidence names commit, package hash, OS and Word versions, case results and limits; a failure in core security, original protection or delivery gating keeps the exit decision blocked. | `trial-distribution-record` | Build identity, install/run results, rollback result with user-data comparison, case-result ids, limits list, and a blocker's evidence address if the failure clause applies. 07's drill and handover products are cited, not silently assumed. |
| Sample-class rule (§4 closing rule, applies to all rows) | Raw samples and replies remain in the authorised environment; only de-identified evidence or synthetic reproductions belong in the repository. | `trial-evidence-boundary-record` | For each output file: where the raw evidence lives, which safe fields the repository record carries, and what was proven absent. A row whose repository record carries material text fails this rule. |

The "One real model" row is deliberately the only row whose output is a
named-gap record: §13 §6.5's 2026-11-09 answer and §12 decision 5 leave it
held open. 06's real half having run under its own authorisation changes
what the gap names, not the owner's ruling. A trial record that converts
that half into a passing §4 row is the exact substitution
[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §3 forbids.

## 6. What the trial record must not do

1. It must not present the owner's decision as the reviewer's, or the
   reviewer's classification as the owner's signature.
2. It must not claim a §4 row from `LC-P3-02`'s evidence alone. The mutual
   citation rules are in
   [`LC-P3-08-evidence-mapping-design.md`](LC-P3-08-evidence-mapping-design.md).
3. It must not cite a commit SHA that was not printed by the command that
   named it; execution plan §9's discipline applies.
4. It must not widen the `root_kinds` capability, suggest that widening as
   a trial fix, or classify the known limit as a defect. That remains an
   owner decision for its own ticket.
5. It must not enter a dev-build rehearsal, a substitute reading or a
   synthetic sample in a real-advisor row. A rehearsal is labelled as one;
   the disclosure sentence covers a reading only.
6. It must not edit a Phase 2 record's verdict. Execution plan §5's
   standing rule keeps Phase 2's wording.
7. It must not infer from Q77 or Q82 away from their triggers.
