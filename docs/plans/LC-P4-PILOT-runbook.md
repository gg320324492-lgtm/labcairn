# LC-P4-PILOT — pilot execution runbook

**Ticket:** LC-P4-PILOT (pilot execution)
**Status:** `DRAFT — the operating manual for the pilot; every step's
evidence slot is PENDING until the trial fills it`
**Source plan:** [`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md)
§9 (the trial), §3.2 (the loop's ground rules), §7.2 (the real-model loop).
**Prerequisite records:** the three pilot-preparation documents —
[`LC-P4-PILOT-desensitisation-checklist.md`](LC-P4-PILOT-desensitisation-checklist.md),
[`LC-P4-PILOT-model-authorisation-draft.md`](LC-P4-PILOT-model-authorisation-draft.md),
[`LC-P4-PILOT-feedback-form-template.md`](LC-P4-PILOT-feedback-form-template.md)
— all three `DRAFT` at the time this runbook was written — plus the
owner-decisions form
([`LC-P4-PILOT-owner-decisions.md`](LC-P4-PILOT-owner-decisions.md))
for plan §12's three decisions, and a release record under
`docs/releases/` for the version the pilot runs on (plan §10; §0 below).
**Format precedent:** the Phase 3 trial's protocol and record pair
([`../acceptance/LC-P3-08-trial-protocol-2026-11-14.md`](../acceptance/LC-P3-08-trial-protocol-2026-11-14.md),
[`../acceptance/LC-P3-08-trial-record-2026-11-22.md`](../acceptance/LC-P3-08-trial-record-2026-11-22.md)).
**Exit skeleton:** [`../acceptance/P4-G1-G4-record-skeleton.md`](../acceptance/P4-G1-G4-record-skeleton.md)
— the gates this run feeds, with their evidence slots.

This runbook turns plan §9.2's twelve steps into executable operations.
Each step states: what is done, which entry point does it (a CLI command
or a service route, both verified against the tree this was written at),
what evidence is recorded, and what to do when the step fails. It fixes
the pilot's shape from plan §9.1 — **one project, 3–5 participants, one
advisor and 2–4 students** — and the material boundary every step sits
inside.

## 0. Before any step — the owner's decisions and the version record

The pilot does not open on this runbook alone. Three decisions belong to
the owner before the work orders are cut (plan §12: rule case-validation,
material retention/withdrawal/sharing, first runnable version and trial
date), and the owner-decisions form
([`LC-P4-PILOT-owner-decisions.md`](LC-P4-PILOT-owner-decisions.md)) is
where they are filled and signed. A decision still marked
`TBD — owner to fill` keeps the flow it gates blocked; the form names
which.

**The first runnable version must carry a release record.** Plan §10
requires every version to have one structured record under
`docs/releases/` (the seven elements the
[release-records README](../releases/README.md) specifies, written by
[`scripts/release_record.py`](../../scripts/release_record.py)). The
version the pilot runs on (G0 §3's frozen baseline, and decision D-3's
first runnable version) is no exception: **if `docs/releases/` holds no
record for it, the pilot does not open on it.** The version line in that
record is also where skeleton decision D-3's answer lands.

## 1. Standing boundaries (read before any step)

**The owner-decision boundary (plan §12, via the owner-decisions form).**
The three pre-opening decisions are the owner's, recorded and signed in
[`LC-P4-PILOT-owner-decisions.md`](LC-P4-PILOT-owner-decisions.md); an
unfilled decision keeps the flows it gates blocked, and a step that
depends on one refuses rather than assume an answer.

**The version-record boundary (plan §10).** The version the pilot runs
on carries a structured release record under `docs/releases/` (written
by [`scripts/release_record.py`](../../scripts/release_record.py)); no
record, no pilot on that version.

**The material boundary (G0 §4, the desensitisation checklist's frame).**
Raw files live only in the authorised environment: `E:/trial-material/`
for the samples and working copies, `E:/labcairn-local/` for the trial's
own run artefacts. **The repository receives metadata only** — ids,
digests (sha256), counts, paths and the records that name them. No
sentence of the manuscript, no comment body, no tracked-change text and
no raw DOCX enters the tree. Every evidence slot below follows this: the
pilot records *where* a thing is and *what it hashes to*, never the thing.

**The authorisation boundary (the model-authorisation draft §9).** No
real-model request is sent until the authorisation record's §1–§7 fields
are filled and signed. A step that would send a real request **refuses**
when the record is unfilled; the substitute path (step 3's fallback) is
the only model work an unfilled record permits.

**The desensitisation boundary (the checklist, part E).** The copy that
enters the pilot has passed every checklist item, and the import step
re-verifies the digest (D-4) and the metadata counts (D-3) on its side.
The pilot does not re-desensitise; it refuses a copy that fails either
re-check.

**The vocabulary for every problem (plan §9.4, as the code spells it).**
Severity: `blocker`, `serious`, `minor`, `suggestion`. Type:
`function`, `interface`, `performance`, `model`, `documentation`. These
are the words `PILOT_ISSUE_SEVERITIES` and `PILOT_ISSUE_CATEGORIES`
define in `src/labcairn/application/issues.py`, and they are closed: the
service refuses a record outside either (422 at the wire, by name from
the layer). The feedback form's own scales (`blocking|severe|normal` and
`ui`) are the template's submitter-facing spellings; **triage maps them
onto the system's words before a record is written** — `blocking` →
`blocker`, `severe` → `serious`, `normal` → `minor`, `ui` → `interface`.
A problem is recorded once per occurrence, with the form item and the
system record linked by the issue id (the form's P-2 field).

**Roles.** One advisor; two to four students; 3–5 participants in all.
The advisor owns the authorisation decision, the material supply and the
final quality conclusions. Students perform the loop's operating steps
under the advisor's direction. Every participant records their own
findings; nobody records on another's behalf.

## 2. The twelve steps (plan §9.2, one subsection each)

### Step 1 — Import the paper, its comments and its revision marks

**What.** Create the pilot's workspace and task, binding the
desensitised copy as the task's source material. The import ingests the
bound directories and records what arrived.

**Entry points.**

```bash
uv run labcairn init                       # once, at the workspace root
uv run labcairn doctor                     # pre-flight: workspace, db, policy
uv run labcairn --workspace ./workspace task create \
  --title "Pilot revision round" \
  --objective "One desensitised paper through the full revision loop." \
  --criterion "Four deliverables bound to one task, input version and output version." \
  --source-dir <desensitised-copy-dir> --json
```

`task create` ingests the material and binds it to the task before it
returns; the JSON's `bound_source_ids` names what arrived. The copy
lives under `E:/trial-material/` (the checklist's D-5 path); the
`--source-dir` argument names a directory **inside the workspace** that
holds or links it, per the workspace's own source-root rule.

**Evidence recorded.** The task id, the bound source ids, the material's
sha256 (checked against the checklist's D-4 digest) and the metadata
counts (against D-3) — ids and digests into the trial record, never the
bytes.

**On failure.** A digest or count mismatch is a **stop**, not a
workaround: the copy failed part E's re-check, and the material returns
to the advisor for re-desensitisation. A workspace that binds no source
root refuses with `PATH_REFUSED`; re-run `task create` with a valid
`--source-dir`. Record any refusal as an issue (`POST /issues`, step 12's
channel) with severity `blocker` if it stops the trial, type `function`.

**Evidence slot:** PENDING — task id, source ids, digest match result.

### Step 2 — Check the original file's digest and version information

**What.** Confirm what entered the system is what the checklist
registered: the copy's digest, its format, its structural counts and the
version record the import created.

**Entry points.**

```bash
uv run labcairn --workspace ./workspace task status --json
uv run labcairn --workspace ./workspace sources inspect --source <source_id> --json
```

and, with the service up (step 3 runs it), `GET /sources/{source_id}` and
`GET /task` with the workspace's session token. The version row the
import created carries the input version id every later step names.

**Evidence recorded.** The measured sha256 beside D-4's registered
value; the format, page/word/figure/table, comment and revision-mark
counts beside D-3's; the input version id. The P3 record's pattern is
the model: file, role, bytes, sha256 — a table of fingerprints, no
content.

**On failure.** Any mismatch between measured and registered values
fails the copy (checklist part E) — the trial stops until the advisor
re-registers or replaces the copy. Record the mismatch as an issue,
severity `blocker`, type `function`.

**Evidence slot:** PENDING — digest comparison, counts comparison,
input version id.

### Step 3 — Run the real model to generate suggestions

**What.** Run the suggestion loop over the version's pending opinions,
in `real` mode, under the signed authorisation record's budget and stop
conditions.

**Entry points.** Start the service first (loopback only; it mints its
own session token and writes it to the workspace):

```bash
uv run labcairn --workspace ./workspace serve --port 8000
```

then, with opinions in the chain (the advisor's imported comments),
select the task and run the loop:

```bash
POST /task/select          # select the pilot task
POST /review/suggest       # body: project_id, version_id, mode="real",
                           # approval_ids: {feedback_id: approval_id, ...},
                           # max_requests, max_tokens,
                           # max_consecutive_failures, retry_attempts
```

**The authorisation gate.** `mode="real"` spends one digest-bound
approval per opinion — the caller presents `approval_ids`, one per
opinion consent covers, and an opinion without one is recorded as
unauthorised and **skipped, not asked**. The request uses only
desensitised excerpts the authorisation record's §3 content boundary
allows. The run records model id, request count, tokens, durations,
failures, refusals and stop reason (§8's fields) — ids and counts, never
request/response prose.

**On failure.** A real-model failure takes the two paths plan §3.2
allows: **retry** (the loop's own `retry_attempts`, for the retryable
classes the authorisation record §5 names) or **substitute fallback**
(re-run with `mode="substitute"`, which spends nothing and needs no
approval). A substitute's output is **labelled as substitute** in every
record — it is never written as a real-model result. A refusal, auth
failure or budget stop ends the real run; record it as an issue,
severity `serious` (the loop continues on the substitute) or `blocker`
(no model path remains), type `model`.

**Evidence slot:** PENDING — run id, mode, model id, requests, tokens,
durations, stop reason (or substitute-fallback note).

### Step 4 — Advisor and students watch the stage progress

**What.** The participants observe the loop's stages as they run: which
stage the task is in, what each stage produced, where the run stands.

**Entry points.**

```bash
GET /plan                  # the task's stage plan
GET /steps                 # the steps, with their states
GET /task                  # the task's current state
GET /events?...            # the event stream, paged
```

The web workbench (P4-UI) renders the same state; the trial may watch
through it or through the routes directly. The event stream is the
system's own record of what happened when — it is evidence, not
narration.

**Evidence recorded.** Per-stage outcomes and timestamps, read from the
event stream at trial time and preserved in the trial record by
reference (the workspace's event log; ids and timestamps, no content).

**On failure.** A stage that reports a refusal or an error is recorded
as an issue with the step name in `step`, the error text, the duration
and the retry count the record carries. Severity by effect: the loop
cannot continue → `blocker`; a wrong or lost result → `serious`; an
inconvenience with a workaround → `minor`; an improvement idea →
`suggestion`. Type by where it happened: `function`, `interface`,
`performance`, `model` or `documentation`.

**Evidence slot:** PENDING — stage outcomes, event-stream reference.

### Step 5 — Read each opinion with its evidence, one by one

**What.** For every opinion the advisor's comments carry, the reviewer
reads the opinion, the model's suggestion for it and the evidence the
suggestion cites — before deciding anything.

**Entry points.**

```bash
GET /review/opinions?project_id=...&version_id=...
GET /review/manuscript?project_id=...&version_id=...
```

`/review/opinions` returns the three separate facts per opinion — the
comment and its anchor (the chain's), the suggestion (what the model
proposed) and the decision (what the reviewer did). The manuscript read
gives the paragraphs in document order with the feedback anchors'
1-based numbering, so an opinion's anchor locates the text it is about.

**Evidence recorded.** Per-opinion: read/unread, whether the suggestion
matched the comment's intent, whether the cited evidence located
correctly (this feeds §9.3's coverage and evidence-localisation
measures). The review stays in the workbench; the record keeps counts
and issue references, not manuscript text.

**On failure.** A suggestion that misreads its opinion, or evidence that
points at the wrong text, is recorded as an issue — severity `serious`
(wrong result) or `minor` (imprecise), type `model` (the suggestion's
content) or `function` (the locating). These observations are the
raw material of step 12's quality conclusions.

**Evidence slot:** PENDING — opinion count, per-opinion review notes
(ids and verdicts), evidence-localisation observations.

### Step 6 — Preview the modifications' impact

**What.** Before anything is applied, measure what the approved set
would do: how many edits, which paragraphs they touch, and the output
change summary.

**Entry points.**

```bash
POST /review/preview       # same body as /review/apply
```

The preview writes nothing — no file, no store row — and returns the
sha256 of the drafts the apply would publish. The workbench shows this
before the operator commits (plan §3.2's rule, at the surface).

**Evidence recorded.** The preview's edit count, affected-paragraph
list and output digests — recorded beside the apply result (step 7/8)
so the equality can be checked: **the digests the preview returned must
equal the digests the apply published**. A mismatch is a defect in the
loop's determinism, severity `serious`, type `function`.

**On failure.** A preview that refuses (no approved set, no operator
named) is a normal refusal — fix the precondition, not the tool. A
preview that succeeds but disagrees with the later apply is recorded as
an issue and investigated before the round continues.

**Evidence slot:** PENDING — preview digest set, edit count, affected
paragraphs.

### Step 7 — Approve the suggestions, one by one

**What.** Each suggestion receives a human decision: accept, partially
accept, reject, or request more evidence. **Nothing is applied without
this.** The decisions are recorded per suggestion, by the person who
made them.

**Entry points.**

```bash
POST /review/decision      # one verdict per suggestion
```

The verdicts come from the reviewer, not from the model and not from
another participant. The apply step (step 8) reads the decisions from
the store — it does not take them as call arguments — which is what
makes the applied set auditable after the fact.

**Evidence recorded.** Per-suggestion verdicts; the counts §9.3 asks
for (accepted / partially accepted / rejected / evidence-requested).
Each decision names its maker (the approver field the data model's
Approval record carries).

**On failure.** A decision that cannot be recorded (unknown suggestion
id, stale round) is refused by name; re-read `/review/opinions` and
decide against the current state. Record a lost or duplicated decision
as an issue, severity `serious`, type `function`.

**Evidence slot:** PENDING — decision counts, per-suggestion verdict
ids.

### Step 8 — Apply the approved modifications

**What.** Run the stored, approved set through the binding and close
the round: the approved edits are applied to the manuscript, the output
version is published, and the four deliverables' binding is created.

**Entry points.**

```bash
POST /review/apply         # same body as /review/preview
```

The apply reads the decisions from the store (step 7's), runs the
binding's duplicate, staleness and consent guards, applies the edits and
publishes the output version. The binding's dossier names the task, the
input version, the output version and the publication receipts — the
ids every deliverable binds to.

**Evidence recorded.** The apply result's receipt ids, the output
version id, and the digests of the published drafts — compared against
step 6's preview (they must match). The dossier artifact id is
**required by step 9's export**; record it here.

**On failure.** The apply refuses on a guard (duplicate, stale, consent
missing) by name; the refusal is the correct behaviour — fix the
precondition. A cancelled or interrupted apply is recoverable: the
binding's cancellation path records `apply_cancelled`, and a new apply
against the same round re-runs it. A crash between write and confirm
leaves the store's transaction intact; re-run the apply. Any guard
failure that looks wrong (a duplicate refused that is not one, a consent
refused that was granted) is an issue, severity `serious`, type
`function`.

**Evidence slot:** PENDING — apply result, receipt ids, output version
id, dossier artifact id, preview/apply digest equality.

### Step 9 — Generate the four deliverables

**What.** Produce the marked draft, the clean draft, the point-by-point
response table and the quality report — all four, bound to the one
closed round.

**Entry points.** The export reads the closed binding's manifest and
returns the four files (base64-encoded bytes, each with its sha256):

```bash
GET /review/deliverables?project_id=...&dossier_artifact_id=...
```

The manifest is the export's authority: the drafts are hash-checked
against the digests the manifest binds, and the response table and
quality report are rendered from the manifest's own JSON — not
re-derived. The workbench's delivery centre (P4-UI) drives the same
export.

**Evidence recorded.** Per deliverable: kind (`marked`, `clean`,
`response_table`, `quality-report`), relative path, size, sha256 —
checked against the manifest's bindings. The four digests and the
dossier id are the consistency evidence §9.3 and gate P4-G2 ask for.

**On failure.** A digest mismatch at export is a **stop**: the deliverable
would carry bytes nobody signed for. The export refuses; the trial
re-runs the apply (step 8) and re-exports. An interrupted export is
resumable — the resume re-lands only the files that do not hash to
their manifest digest, so an interruption costs one re-export, not a
corrupt deliverable. Record any mismatch as an issue, severity
`blocker` (the deliverable is untrustworthy until re-exported), type
`function`.

**Evidence slot:** PENDING — four deliverable digests, dossier binding
check results.

### Step 10 — Export the full package through the delivery centre

**What.** Export the complete delivery package (all four deliverables
in one action) and, as needed, individual files, from the unified
delivery centre.

**Entry points.** The delivery centre in the web workbench drives the
same `GET /review/deliverables` export; the full package is the one
call's four files, and a single file is one deliverable from the same
response. The export writes into the task's output area under the
relative paths the manifest names — inside the workspace, which lives
under `E:/labcairn-local/` (or the workspace root the trial chose);
the authorised-environment copy of the package, if the advisor keeps
one, stays under `E:/trial-material/`.

**Evidence recorded.** The export record: what was exported, when, to
which paths, and the per-file digests (again against the manifest).
The delivery-centre interaction itself (what the UI showed, what the
operator did) is observed for gate P4-G1's usability rows.

**On failure.** An export that cannot write (locked file, full disk,
interrupted) reports which file failed; the resume path re-lands it.
A file lock held by Word/WPS is cleared by closing the host; the trial
records the interruption and the recovery (this is §7.3's evidence).

**Evidence slot:** PENDING — export paths, per-file digest check,
interruption/recovery notes if any.

### Step 11 — Let the system keep the process records

**What.** No manual record-keeping: the system's own stores hold the
process — tasks, versions, opinions, suggestions, decisions, approvals,
stage runs, events, issues, artifacts and their digests. This step is
the **verification** that the records exist and bind to each other, not
a step that writes them.

**Entry points.**

```bash
GET /task                  # the task's state and its runs
GET /trajectory?project_id=...
GET /events?...
```

The trajectory view resolves the project's chain — task to versions,
opinions, suggestions, decisions, deliverables, issues — by id, which
is the trace the gates (P4-G2, P4-G4) are judged on.

**Evidence recorded.** A trace check: from input version to output
version, through the opinions and decisions, to the four deliverables
and every issue — all by id, all resolvable. G0 §6's link fields are
the checklist this walk verifies.

**On failure.** A link that does not resolve (a deliverable without its
version, a suggestion without its opinion) is an issue, severity
`serious`, type `function` — the trace is the product's own promise.

**Evidence slot:** PENDING — trace-walk result (ids resolved, gaps if
any).

### Step 12 — Advisor and students supply the quality conclusions

**What.** The participants record what the system cannot: subjective
experience, problem descriptions, improvement suggestions — through the
unified feedback form, and through the system's issue record for
anything that names a concrete defect.

**Entry points.** The feedback form
([`LC-P4-PILOT-feedback-form-template.md`](LC-P4-PILOT-feedback-form-template.md)):
Part 1 once per submitter, Part 2 one item per problem (each maps to one
Issue record), Part 3 session experience, Part 4 triage (advisor). The
system side:

```bash
POST /issues                        # record one problem
GET /issues?project_id=...          # list, filter by status/severity
PATCH /issues/{issue_id}/status     # open -> confirmed -> fixed|wontfix
```

**The vocabularies are closed** (see §0): severity
`blocker|serious|minor|suggestion`, type
`function|interface|performance|model|documentation`. The form's
submitter-facing words map onto these at triage (the mapping is in §0).
The status is never set outright — a recorded issue is `open`, and the
states are walked by `PATCH`, so a "fixed" nobody confirmed cannot
enter the record.

**Evidence recorded.** The completed forms (filed in the trial's
records, outside the repository if they carry experience prose tied to
the material; the repository carries the Issue rows and the form
counts). Every Issue row: id, task id, stage, severity, type, linked
opinion/deliverable ids, status. These rows are §9.3's problem measures
and gate P4-G4's blocker/serious evidence.

**On failure.** A refused issue record (word outside a closed
vocabulary, missing project) is corrected and re-submitted — the
refusal names the word. A form item that cannot map to an Issue (Part
3's experience items) stays a form item; it is not forced into the
system record.

**Evidence slot:** PENDING — forms collected, issue rows written,
triage outcomes.

## 3. After the twelve steps — the measures and the gates

**Trial measures (plan §9.3).** The record assembles: wall-clock time
for the paper's full pass; count of manual out-of-band steps; the
decision counts (accepted / partially accepted / rejected /
evidence-requested); opinion coverage; opinion-to-modification
correctness; evidence-localisation correctness; four-deliverable
consistency; and the blocker/serious issues the participants found.
Long-term usage intent is **not** a metric — the group's own continued
use is the setting, and the trial's job is to find and fix defects.

**Issue handling after the trial.** Every recorded issue is triaged
(form Part 4): `blocker` issues are fixed before any wider trial or
explicitly block it; `serious` issues get an owner, a fix version and a
regression check — these are gate P4-G4's conditions, and the exit
skeleton's P4-G4 section holds their slots.

**Where the gates are judged.** The exit skeleton
([`../acceptance/P4-G1-G4-record-skeleton.md`](../acceptance/P4-G1-G4-record-skeleton.md))
lists the four gates' conditions, which ones this runbook's evidence
slots feed, and which need the real trial's numbers. The runbook does
not judge them; it produces the evidence the judgement reads.

## 4. Session logistics

**Machine and service.** One Windows host per session, the installed
package (the baseline version G0 §3 freezes), the service on loopback
(`serve --port 8000`), the web workbench in a browser. The session
token is read from the workspace, not shared in chat.

**Files per session.** Each session opens the workspace, selects the
task, and works the steps in order. A session that ends mid-loop leaves
the task's state on disk; the next session resumes with `task status`
and `GET /task` — the restart path the quickstart walks, and §7.3's
recovery evidence when it follows a failure.

**Privacy in the record.** Participants are named by role (advisor,
student-1, …) or by a pseudonym they choose; no real names, no
affiliations, no project numbers anywhere in any record this trial
writes — the same rule the desensitisation checklist applies to the
paper, applied to the trial's own records.
