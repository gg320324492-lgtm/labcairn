# LC-P3-08 — trial protocol record (2026-11-14)

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commit named below; the tree moves. Follow the sentence,
not the number.

**Record class:** TRIAL PROTOCOL — the substitute-first deliverable named in
[`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §13 §6.6
deliverable 1 and §6.8's permitted half ("the trial protocol and per-row
mapping under `docs/acceptance/`"). This record is **not** the trial record,
**not** a review, **not** an exit decision, and it enters no §4 result. It
fixes, before the trial runs, which evidence satisfies which execution-plan
§4 row, so the trial does not grade itself after the fact.

**Date:** 2026-11-14.
**Design basis:** [`LC-P3-08-trial-protocol-design.md`](../plans/LC-P3-08-trial-protocol-design.md),
[`LC-P3-08-evidence-mapping-design.md`](../plans/LC-P3-08-evidence-mapping-design.md),
[`LC-P3-08-reviewer-form-design.md`](../plans/LC-P3-08-reviewer-form-design.md)
— all three dated 2026-11-10 in `docs/plans/`.
**Tree this protocol was written at:** worktree
`E:\LabCairn\.claude\worktrees\silly-margulis-65e484`, branch
`claude/silly-margulis-65e484`, HEAD
`a7cde5999a9db1524e2ec5514685b449e43de4b1` (printed by `git rev-parse HEAD`
immediately before this file was written).
**Status:** PROTOCOL FIXED. The trial itself stays blocked on the
owner-supplied real-material inputs registered in §7; nothing in this record
claims a §4 row, a gate verdict, or Phase 3 closure.

## 0. What this protocol fixes

[`PHASE_3-execution-plan.md`](../plans/PHASE_3-execution-plan.md) §4 is the
Windows internal-trial acceptance checklist: eight rows plus the closing
sample-class rule. §13 §6.4 requires their evidence mapping to be decided
**before** the trial runs. This record performs that mapping. For each row it
fixes four things:

1. the **evidence requirement** — what observations the row's passing
   condition needs;
2. the **deciding rule** — how a reviewer reads that evidence to a verdict,
   fixed now so the trial cannot reinterpret it afterwards;
3. the **output file** — the named record shape the trial must produce
   (names only; none exists yet, and none is created by this protocol);
4. the **address shape** — the form every citation must take.

Every value this protocol quotes is anchored: either to a printed commit SHA
named beside it, or to a dated acceptance record that carried the value at
its own named commit. No unprinted SHA is quoted (execution plan §9).

## 1. The trial sample — fingerprint only

The owner picked the trial sample on 2026-11-09 and the pick is recorded at
[`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §5.9 and in
[`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md)
§"What is real here, and what is not". This protocol repeats the fingerprint
and no prose:

| Field | Value | Source |
|---|---|---|
| Sample role | `real-advisor-sample` | [`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md) |
| Sample SHA-256 | `9154e56c5fe47da151fdb636b3cc4f8170965a8ccdbca94f292390254607652d` | measured live before the 42-arm machine loop; printed in the record named beside |
| Sample bytes | 4 443 105 | same record |
| Structure counts | 4 comments, 270 tracked insertions, 119 tracked deletions, 10 media parts | [`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §5.9 |
| Authorised location | the owner's authorised environment, outside this repository | §5.9; no file enters the tree |

The sample is named by role and fingerprint, never by content. No sentence
of the manuscript, no comment body, no tracked-change text and no raw DOCX
enters this repository (execution plan §4's closing sample-class rule).

## 2. The loop this protocol governs

The advisor → student → advisor loop follows execution plan §2 verbatim in
substance, with the steps, actors, hosts and per-step records fixed by
[`LC-P3-08-trial-protocol-design.md`](../plans/LC-P3-08-trial-protocol-design.md)
§3 (T0 preconditions, T1 advisor supplies, T2 import, T3 locate and propose,
T4 review and approve, T5 apply and deliver, T6 advisor reopens, T7 gate
rows, T8 trial record, T9 independent review). This protocol adds the
per-row evidence map those steps must satisfy; it does not restate the steps.

Hosts are the supported Word environments of
[`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
§5: WPS Office primary, and the compatibility reference as re-measured there
(**Microsoft Office 2019, WINWORD 16.0.17932.21140** since the 2026-11-16
re-measurement; the record's original 2026-11-07 reading was Word 2010).
Open/reopen steps are human-performed; no COM, no ProgID, no UI automation,
and no agent stands in for them.

## 3. Per-row evidence map (execution plan §4)

Each row below names: the evidence requirement, the deciding rule fixed
before the trial, the output file the trial must produce, and the address
shape. "Evidence address" means an authorised path or repository record plus
its section anchor and the digest/count/refusal class that identifies the
observation ([`LC-P3-08-trial-protocol-design.md`](../plans/LC-P3-08-trial-protocol-design.md)
§5).

**Read 2026-11-18 — which template set the trial day fills.** The twelve
record templates this section names are filled on the day from the
**prefilled** set at `E:/labcairn-local/g4-templates-prefilled-20261117/templates/`,
in which every fixed value is already written and carries an `[Snn]` source
tag resolving to that pack's `PREFILL-SOURCE.md`. The empty source templates
at `E:/labcairn-local/p308-trial-run/RECORD-TEMPLATES/` are the set those
copies were made from; they are kept as history and are **not** filled. A
prefilled value is a **reference value**, not the day's value: the installer
SHA-256, the sample SHA-256 and both host versions are re-measured on the
trial machine, and the day's own printed measurement is what the record
carries. The record templates themselves live outside the repository, so
this protocol cites them by address and never quotes one as if it were here.

### Row 1 — Import to delivery

- **Evidence requirement.** The commented/revised sample runs through the
  installed build from a new project; the marked draft, clean draft,
  response table and quality report all bind to one task, one input version
  and one output version.
- **Deciding rule.** The row passes when the delivery record shows the four
  deliverables with digest-level identity to one (task, input version,
  output version) triple, and no deliverable binds to a different triple.
  A binding mismatch on any deliverable fails the row.
- **Output file.** `trial-delivery-record` — one row per deliverable: task
  id, input/output version ids, four deliverable ids and digests,
  publication receipts.
- **Address shape.** repository record path + §anchor + deliverable digests
  + the printed commit SHA of the trial record.

### Row 2 — Original and format

- **Evidence requirement.** The original hash is unchanged; both DOCX files
  open and reopen in the supported Word environment without a repair prompt;
  the clean draft matches approved edits; non-target equations, images,
  tables and relationships survive; changes outside the support matrix are
  refused or handed to a person.
- **Deciding rule.** Pre/post `sha256` equality on the original is required
  (a digest difference fails the row outright). Open/reopen results are
  human-performed observations on the §5 hosts; each is recorded as
  `opened` / `reopened` / `repair-prompt shown` per file. Non-target class
  counts are compared before/after; any surviving-diff outside the approved
  edit set fails the row. A change outside the support matrix must carry a
  refusal-class name or an explicit handover record; silent application
  fails the row.
- **Output file.** `trial-original-and-reopen-record` — pre/post digests,
  host names/versions, open/reopen and repair-prompt results, non-target
  class counts, refusal or handover class names; the support matrix is
  cited from [`LC-P3-02-support-matrix.md`](LC-P3-02-support-matrix.md).
- **Address shape.** repository record path + §anchor + digests and class
  names + printed commit SHA. The host observation carries the authorised
  environment path outside the repository.

### Row 3 — Point-by-point response

- **Evidence requirement.** Every supported input opinion is either located
  or explicitly marked as a location failure; each carries accepted /
  partly accepted / rejected / pending status; automatic edits link to
  opinion, evidence, operator and version; model suggestions and advisor
  confirmations are separate records.
- **Deciding rule.** The row passes when the response record covers every
  supported input opinion id with (a) a location result — located, or a
  named location-failure class, never blank — and (b) one of the four
  decision statuses as its own entry. Edit rows must name opinion id,
  evidence address, operator and version edge; a missing link fails the
  row. Model suggestions and advisor confirmations must appear as separate
  record types; a merged record fails the row.
- **Output file.** `trial-response-record` — per-opinion id, location
  result, decision id, evidence address, operator, version edge,
  suggestion id and advisor-confirmation id.
- **Address shape.** repository record path + §anchor + per-opinion ids and
  decision ids + printed commit SHA.

### Row 4 — Research quality

- **Evidence requirement.** The sample contains a directly editable case, a
  case needing further evidence, and an uncertain-location case; missing
  experiments, references or data block a quality pass or become named
  tasks; file-delivery status and research-quality status are decided
  separately.
- **Deciding rule.** The quality record must name the three case ids and
  show the two status fields set independently, each with its own evidence
  address. A quality pass while a named missing-item task is unresolved
  fails the row; the statuses must not be inferred from one another.
- **Output file.** `trial-quality-record` — three named case ids,
  missing-item/task ids, two separate status fields with their own
  evidence addresses.
- **Address shape.** repository record path + §anchor + case/task ids +
  printed commit SHA.

### Row 5 — Permission and privacy

- **Evidence requirement.** Cross-project references, path escape, writes to
  the original, forged or expired approvals, unauthorised outbound data and
  instructions embedded in the document all have refusal evidence; the real
  model receives only approved, de-identified content; logs and receipts use
  safe fields.
- **Deciding rule.** Each listed attack class needs its own injected case id
  and observed refusal name; a class with no refusal observation fails the
  row. The de-identification claim is checked against the real-model scope
  record (Row 7's citation): any material text in a repository log or
  receipt fails the row and is also an H-03 honesty blocker in the review
  form.
- **Output file.** `trial-refusal-record` — one refusal class per
  observation, its injected case id, the observed refusal name, and the
  safe-field list.
- **Address shape.** repository record path + §anchor + refusal class names
  and case ids + printed commit SHA. No material text in the record.

### Row 6 — Cancel, retry and recovery

- **Evidence requirement.** Two side-effectful interruption points around
  publication are exercised; cancellation, duplicate submission and restart
  resolve to a safe retry, a recovered result or a manual check; the
  original is intact and output receipts are not duplicated.
- **Deciding rule.** The record must name the two interruption points and,
  for each, the injected state, the outcome class (safe retry / recovered
  result / manual check), the original digest before and after (equality
  required), and the receipt-id set showing no duplicate. A duplicated
  receipt or a changed original digest fails the row.
- **Output file.** `trial-recovery-record` — two interruption ids with
  injected state, outcome class, original digest before/after, receipt-id
  set.
- **Address shape.** repository record path + §anchor + interruption ids
  and digests + printed commit SHA.

### Row 7 — One real model

- **Evidence requirement.** The installed build runs one controlled
  de-identified case; the model returns at least one locatable, reviewable
  revision suggestion and a person reviews it before delivery; budget and
  permission failure cause no outbound call; timeout and unavailability
  have explicit degraded paths; Phase 2's `real_model_smoke = NOT RUN` is
  not rewritten.
- **Deciding rule — this row is PENDING-OWNER as a named gap.** Per
  [`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) §13 decision 7
  (§14 item 7, answered 2026-11-09), if the trial is ready while
  `LC-P3-06` is still `BLOCKED`, **the row is held open as a named gap and
  the remaining rows run**; the trial does not wait on the provider. A
  substitute never passes this row ([`LC-P3-00-board-opening-decisions.md`](LC-P3-00-board-opening-decisions.md)
  §3). At the exit decision the row is presented as a named gap with its
  closing condition, citing `LC-P3-06`'s two halves as that ticket's own
  records — never converted into a trial row.
- **What is already measured on that ticket (cited, not claimed).**
  [`LC-P3-06-real-half-2026-11-10.md`](LC-P3-06-real-half-2026-11-10.md)
  records the bounded real-provider run on the dev build: 5 of 20 authorised
  requests, 5 136 of 50 000 tokens (its §"Cumulative budget" row), case B
  producing two locatable suggestions, gap G4 for case A's layout, and gap
  G7 (the driver granted its own asks). [`LC-P3-06-substitute-first-2026-11-10.md`](LC-P3-06-substitute-first-2026-11-10.md)
  is the substitute half. These citations support the gap's context; they
  do not satisfy this row.
- **Output file.** `trial-real-model-gap-record` — the named gap's
  statement, its closing condition, and the citations above.
- **Address shape.** repository record path + §anchor + the gap name +
  printed commit SHA; citations carry 06's record paths and section
  anchors.

### Row 8 — Distribution and review

- **Evidence requirement.** A clean supported Windows environment proves
  install and run; rollback preserves user data; evidence names commit,
  package hash, OS and Word versions, case results and limits; a failure in
  core security, original protection or delivery gating keeps the exit
  decision blocked.
- **Deciding rule.** The row passes when the distribution record binds the
  drilled installer identity (commit, package hash, size), the OS and Word
  host versions, install/run/rollback results with user-data comparison,
  case-result ids and the limits list. A core-security, original-protection
  or delivery-gating failure classifies `blocker` and keeps the exit
  decision blocked (execution plan §4; reviewer form H-checks).
- **Output file.** `trial-distribution-record` — build identity,
  install/run results, rollback result with user-data comparison,
  case-result ids, limits list, and a blocker's evidence address if the
  failure clause applies.
- **Address shape.** repository record path + §anchor + package digest and
  version identifiers + printed commit SHA. The installer drill it will
  cite is [`LC-P3-05-install-drill-2026-11-14.md`](LC-P3-05-install-drill-2026-11-14.md)
  (installer `LabCairn Setup 0.0.0.exe`, 234 325 233 B, sha256
  `9805be54821ae8af549bb7cd2e3c9924186550127005130004680e4ff5e155c4`,
  drilled from `main` at `7a44f569ceafb4c5c284c183e764f53b8f6ad1af` —
  values printed in that record). Its known supply gap — the installed
  package ships `shell-env.template.json` and no `shell-env.json`, so the
  first launch needs one operator action — is carried into the trial's
  limits list, not silently assumed.

### Closing rule — sample class (governs every row)

- **Evidence requirement.** Raw samples and replies remain in the authorised
  environment; only de-identified evidence or synthetic reproductions belong
  in the repository (execution plan §4 closing rule, quoted in
  [`LC-P3-08-trial-protocol-design.md`](../plans/LC-P3-08-trial-protocol-design.md)
  §2).
- **Deciding rule.** For each output file: name where the raw evidence
  lives, which safe fields the repository record carries, and what was
  proven absent. A row whose repository record carries material text fails
  this rule — and is an H-03 honesty blocker in the review form.
- **Output file.** `trial-evidence-boundary-record` — per output file: raw
  evidence location, safe-field list, absence check.
- **Address shape.** repository record path + §anchor + safe-field list +
  printed commit SHA.

## 4. The seam statement this protocol must carry

Owner decision 4 at §13 keeps `root_kinds={"source"}` and requires the
protocol to state the measured chain seam. The statement, quoted from
[`LC-P3-08-trial-protocol-design.md`](../plans/LC-P3-08-trial-protocol-design.md)
§4 (which measured it against
[`LC-P3-04-binding-loop-2026-11-10.md`](LC-P3-04-binding-loop-2026-11-10.md)
§6 gap 1):

> The chain-editing capabilities `labcairn.papers.revisions.record_revision_events`
> and `labcairn.papers.feedback.record_feedback`, when addressed at an output
> version, refuse before a rule is asked — the capability registry's
> `root_kinds={"source"}` means the listing does not show output versions.
> This is a known limit, not a defect, and widening the capability's root
> kinds before the trial was not authorised. The product's actual chain-fill
> behaviour is `labcairn.papers.binding._fill_chain`: it mints the chain's
> edit rows from the approval records through the store's own writers, with
> the actor `model` and the grade `human_verified`, keeping every vocabulary
> and grant check. The dossier carries those rows; the trajectory panel
> shows the input round's rows.

The four assertions a statement witness checks (design §4.1): the
`root_kinds={"source"}` limit is present; the listing does not show output
versions; the limit is a known limit, not a defect; `_fill_chain` mints from
approval records and is the product's actual behaviour. The trial record
must repeat this statement; the reviewer form's H-05 checks it, and the
"output versions absent from trajectory listing" finding is classified
`known limit` — not a blocker, not a routed defect — on the strength of this
statement and its measured basis.

## 5. Citation rules for LC-P3-02's real-sample record

Decision 3 (§13, answered 2026-11-10) makes 02's recorded real-sample loop
an **input** to 08's trial. The citation surface is fixed by
[`LC-P3-08-evidence-mapping-design.md`](../plans/LC-P3-08-evidence-mapping-design.md)
§§2–3: field-level citation with an address — sample fingerprint, structure
counts, digests, refusal classes, record addresses, status labels — never
prose, and never a verdict transfer. The mutual anchor shape is
`record path + section anchor + identifying digest/count/refusal class +
printed full commit SHA`. 08 cites
[`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md)
(42/42 arms measured, 14 produced, 28 refused, 8 artifacts, report sha256
`a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`, human
dual-host reopen `NOT RUN` — its "Final status sentence") as the same
supply's machine half; no §4 row of this trial passes on 02's evidence
alone, and 08 still records its own observation for every row it claims.
**Read 2026-11-17:** that record's "Final status sentence" now reads
`human dual-host reopen: 16/16 PASS on 2026-11-16/17`, so the `NOT RUN` above
is this protocol's 2026-11-14 reading of it.

## 6. Evidence-address discipline (all rows)

1. Every value is anchored to a printed commit SHA or a dated record that
   printed it; no unprinted SHA is quoted (execution plan §9).
2. Every address is `path + section anchor + identifying
   digest/count/refusal class` (mapping design §3).
3. Counts, digests, refusal-class names and row identifiers are safe fields;
   paragraph text, comment bodies, tracked-change text, replies and model
   prose never enter a repository record.
4. A record written after a row was graded never grades that row; the
   mapping above is fixed before the trial runs.
5. A rehearsal or substitute run is labelled as one and is never entered in
   a §4 row; under §12 decision 2 no dev-build rehearsal is authorised.

## 7. Owner-gated items — what this protocol does not supply

These are the real-material inputs the substitute-first half cannot
provide. Each is a named prerequisite, recorded here so the trial record can
point at what was missing if it runs without one — and so nothing in this
batch pretends to hold it.

| # | Owner-gated item | Where it is named | What is missing |
|---|---|---|---|
| 1 | Real advisor supplying the sample | §13 §6.5; execution plan §2 T1 | PENDING-OWNER — the advisor's live supply act on the trial machine (the sample's fingerprint is fixed in §1; the supply receipt is written at trial time) |
| 2 | Real trial participant running the loop | §13 §6.5; T2–T5 | PENDING-OWNER — the owner designates the authorised participant; no agent fills the role |
| 3 | Real advisor reopen of the marked-up draft | T6; §3 rule 2 | PENDING-OWNER — human-performed open/reopen on the supported hosts; no COM/ProgID/UI automation, no agent |
| 4 | Named human reviewer | §13 decision 7; reviewer form F-05 | PENDING-OWNER — the owner designates the name; an agent session is only the second reader, entering under the form's F-09/B-02 memory-and-entry boundary (zero finding ids, verdicts, expected answers, recorded expected SHAs or prior classifications; injected start context disclosed; pre-exposed threads re-derived from the record and the on-disk evidence) |
| 5 | Named trial participant's human review of model suggestions | Row 7; execution plan §4 | PENDING-OWNER — "a person reviews it" bites here, per [`LC-P3-06-real-half-2026-11-10.md`](LC-P3-06-real-half-2026-11-10.md) gap G7 |
| 6 | Exit decision | §13 §6.2; execution plan §2 | PENDING-OWNER — the owner decides from the evidence; this protocol claims no verdict |
| 7 | The "One real model" row's own evidence | §14 item 7 | PENDING-OWNER as a named gap — held open if `LC-P3-06` is still `BLOCKED` at trial time; never passed on a substitute |

The installed-build precondition itself is now evidenced:
[`LC-P3-05-install-drill-2026-11-14.md`](LC-P3-05-install-drill-2026-11-14.md)
records the candidate installer's drill (install, launch, uninstall,
reinstall, D14/D15/D16 passing on that machine), with the candidate
packages at `E:\labcairn-local\shell-o3-package\dist3\`. What remains
owner-gated is the **trial machine designation and its support-matrix
re-measurement** (T0), not the existence of an installable build.

**Registry status note (added 2026-11-16, status update only — row 4
resolved 2026-11-16).** The owner designated `LabCairn` (originally
designated Xiaoqi Zhushou; superseded **Read 2026-11-21 (owner's ruling):
the reviewer designation is now `LabCairn`** — the project's own name
replaces the personal designation everywhere the trial records name a
reviewer.) as the
named human reviewer on 2026-11-16, recorded in
`docs/handoff/CURRENT.md` and `docs/changelog/phase-3.md` at commit
`17a1abf73f254843cf54e62b5687fb7e884c62bc`. Registry row 4's
designation prerequisite is therefore resolved; the row itself stays as
written, because the reviewer's reading is still a future act. Rows 1,
2, 3, 5, 6 and 7 remain PENDING-OWNER — each names a live act or
decision (supply, participation, reopen, human review, exit, the
real-model evidence) that no designation settles.

## 8. What this record does not do

It runs no trial step, touches no real participant, opens no host, spends no
provider request, and writes no trial row, review finding, classification or
exit verdict. It creates no product code, no test, no workflow file. It does
not edit any Phase 2 record's verdict (execution plan §5's standing rule).
Q77 and Q82 stay at their triggers. It authorises no push, no pull request,
no CI run. The trial record, the review and the exit decision are separate
future records, governed by the mapping this protocol fixes.
