# P4-G1–G4 exit-record skeleton

**Ticket:** LC-P4-PILOT (pilot execution, exit records)
**Status:** `SKELETON — every gate verdict is PENDING; nothing here is a
result until the evidence named beside it exists and is checked`
**Source plan:** [`PHASE_4-execution-plan.md`](../plans/PHASE_4-execution-plan.md)
§11 (the four exit gates), §12 (the three pre-opening decisions).
**Evidence producer:** [`LC-P4-PILOT-runbook.md`](../plans/LC-P4-PILOT-runbook.md)
— the runbook's twelve steps fill this skeleton's evidence slots.
**Machine-readable half:** [`scripts/pilot_gate_evidence.py`](../../scripts/pilot_gate_evidence.py)
collects the half of the evidence a machine can read and writes
[`P4-G1-G4-system-capability-record.json`](P4-G1-G4-system-capability-record.json).
**Format precedent:** the Phase 3 exit records under `docs/acceptance/`
([`LC-P3-08-exit-decision-2026-11-22.md`](LC-P3-08-exit-decision-2026-11-22.md)
is the signed form this skeleton anticipates).

This skeleton fixes, **before the trial runs**, what evidence each
Phase 4 gate reads — the same discipline the Phase 3 protocol record
applied to the Phase 3 trial, so the trial does not grade itself after
the fact. Each gate lists the plan's conditions — paraphrased into
English from plan §11, section by section; the plan's own wording
governs — the evidence slot that will satisfy each one (with the
command, record or path that produces it), and a status field that
starts at `PENDING`. The conditions are paraphrased rather than
transcribed for the same reason the trial's records carry no corpus
text: the repository's working language is English, and the section
numbers are the stable addresses.

**When the plan was read.** Every paraphrase below was taken from
`docs/plans/PHASE_4-execution-plan.md` **Read 2026-11-25**, and the
section number beside each one says where the wording lives. The plan's
section numbers do not move, but a paraphrase carries the date it was
made, the way the Phase 3 protocol record carries its reading dates
(`docs/acceptance/LC-P3-08-trial-protocol-2026-11-14.md`, "**Read
2026-11-18**").

**What is already covered by system capability, and what is not.** Some
conditions are backed by built and witnessed machinery — the
apply/publish binding, the real-model loop's authorisation gate, the
recover paths, the shared-rule publication boundary. For those, the
trial's evidence confirms the capability *on the pilot paper*; the
witnesses already exist. Other conditions are **only** decidable by the
real trial — efficiency numbers, usability judgements, blocker
discovery. The skeleton marks each condition which kind it is, and no
verdict is written in advance.

**How the status column reads once the collector has run.** A cell that
names a **capability** reading was written by
[`scripts/pilot_gate_evidence.py`](../../scripts/pilot_gate_evidence.py)
from the record it names beside it, and it says what the collector
measured and where it read it. Three readings are possible, and they
mean three different things:

* **`PASS` or `FAIL`** — the whole condition is decidable by reading the
  service, and the collector read it. The condition is decided.
* **`PENDING — capability PASS, trial confirmation outstanding`** — the
  machinery held, but the slot's condition also asks for the trial's
  confirmation on the pilot paper, so the slot is not decided.
* **`PENDING — <what the collector found>`** — the condition could not be
  exercised against the workspace the collector read, and the cell says
  why. A condition that was not exercised is not a condition that
  failed.

A cell that reads **`PENDING`** alone is one no tool has touched: the
slot's coverage kind says the real trial alone decides it, and the
evidence is a person's observation. **The four gate verdicts below stay
`PENDING` whatever the slots say** — a gate is judged by the trial, and
the slots are the evidence it reads.

**What a `PENDING` cell says it lacked, and why that differs between
slots.** A cell that reads `PENDING — <what the collector found>` names
one thing: the condition could not be exercised because the workspace
did not hold what it needs. **The thing it names is not the same for
every slot, and the difference is the point.**

* A slot that needs a **project** fails because no route lists the
  workspace's paper projects, so no project id could be addressed. The
  workspace may well hold a project; the collector cannot name it. **That
  is a limit of the routes the collector reads**, not a fact about the
  workspace.
* A slot that needs a **bound task**, a **closed binding**, an **applied
  round** or **published deliverables** fails because the trial has not
  run them yet. **That is a fact about the workspace**, and no tool can
  decide it.

The record names which of the two each slot is: every slot carries a
`requires` field naming the precondition its condition needs, an
`lacks` field naming what the workspace turned out to be missing, and
the record's own `preconditions` map says what each name means. **The
reasons are per slot**: two slots that lack different things are told
different things, so a reader can tell which limit stopped which slot.

**A slot that needs less than a closed binding is answered without
one.** The link from a raw source through a distilled rule to the rule's
record is walked from the rule's own chain key, and the task entry, the
declared workflow, the runtime's steps and the material ledger are all
read without a round. A workspace that has closed no round still
answers those slots, and the record says so.

**A route that refuses is named, not swallowed.** A cell may say that a
route refused — `GET /events` refuses while the service runs without an
event source, for instance — and the record's `reads` section carries
the refusal and its code. **A slot waiting on a route that is not there
yet says so**, rather than reporting an emptiness as though it were a
fact about the workspace.

**The record committed beside this table was read from a synthetic
workspace, not from the pilot paper.** Its own `workspace.note` says so,
and it says which workspace it was: a workspace holding a task and
nothing else. Running the collector against the pilot's own workspace
re-renders these cells and overwrites the record, and the runbook's
§4 session logistics is where that service is started.

---

## P4-G1 — UI interaction

**Plan §11 conditions, paraphrased (§11, P4-G1).** Read 2026-11-25.

- The manuscript-driven workbench carries an operator from task entry
  through to the delivery centre.
- The three-column layout and the opinion location work on real data.
- Task stages and manuscript changes both give evident, comprehensible
  feedback.
- The approval, preview, failure and retry states are correctly
  understood by users.

**Evidence slots.**

| # | Condition | Evidence to fill in | Produced by | Coverage kind | Status |
|---|---|---|---|---|---|
| G1-1 | Task entry through to the delivery centre, in one workspace | A walked path: task selected (`POST /task/select`), opinions read, suggestion loop run, preview, apply, deliverables exported — each step's route or workbench action recorded | Runbook steps 1–10 | System capability, **confirmed on real data by the trial** | PENDING — the path's first half was walked -- the task was selected, the workflow declares 8 stage(s) and the runtime holds 0 step(s) -- and its second half was not: the workspace holds no closed binding, so there were no opinions to read and no deliverables to export; the service refused the read of GET /events with not_implemented (403), so what it carries was not measured (record: P4-G1-G4-system-capability-record.json) |
| G1-2 | Three-column layout and opinion location work on real data | Workbench observation: opinion click locates the manuscript anchor; manuscript scroll switches the current opinion; only the current opinion's text highlights | Runbook step 5, observed in the workbench | **Real trial only** (usability on the pilot paper) | PENDING |
| G1-3 | Task stages and manuscript changes give evident, comprehensible feedback | Workbench observation per stage transition (import → suggest → review → preview → apply → deliverables); dynamic-feedback notes per change | Runbook steps 3–9, observed | **Real trial only** | PENDING |
| G1-4 | Approval, preview, failure and retry states are correctly understood by users | Participant walk-through notes: each state's meaning stated back correctly by at least one student participant; misunderstanding logged as an issue | Runbook steps 6–8 and the issue record | **Real trial only** | PENDING |

**Gate verdict:** PENDING — not judgeable until G1-1..G1-4 have their
evidence and the participants' observations are in.

---

## P4-G2 — Key capabilities

**Plan §11 conditions, paraphrased (§11, P4-G2).** Read 2026-11-25.

- A real desensitised paper completes the full revision loop.
- All four deliverables are generated and consistently bound.
- One real model generates suggestions within the authorised scope.
- Preview before modification, per-item approval, apply, publish,
  retry and recovery all pass.
- The key refusal paths and the evidence checks pass.

**Evidence slots.**

| # | Condition | Evidence to fill in | Produced by | Coverage kind | Status |
|---|---|---|---|---|---|
| G2-1 | A real desensitised paper completes the full revision loop | The runbook's steps 1–10 all completed on the pilot paper; task id, input version id, output version id recorded; the trace walk (step 11) resolves every link | Runbook steps 1–11 | System capability (apply/publish binding, witnessed in code), **confirmed end-to-end on the pilot paper by the trial** | PENDING — the chain was not read at all: GET /trajectory serves the comments under named issue keys, and no route lists the workspace's paper projects, so no key could be named -- the workspace holds no closed binding to carry a project id either, so the walk resolved no link (record: P4-G1-G4-system-capability-record.json) |
| G2-2 | Four deliverables generated and consistently bound | The four kinds (`marked`, `clean`, `response_table`, `quality-report`) with their sha256 digests, each equal to the manifest's binding; the dossier's task/input-version/output-version ids | Runbook step 9 | System capability (manifest-bound export, digest-checked), **confirmed on the pilot paper** | PENDING — the workspace holds no closed binding, so there were no deliverables to bind: the ledger holds 0 artefact(s) [] and none of them is a dossier manifest (record: P4-G1-G4-system-capability-record.json) |
| G2-3 | One real model generates suggestions within the authorised scope | The signed authorisation record (the model-authorisation draft, filled); the suggest run's record: mode `real`, model id, request count, tokens, durations, stop reason; approvals spent per opinion | Runbook step 3 | System capability (authorisation gate, per-opinion consent), **executed on the pilot paper** | PENDING — no read-only route publishes a suggestion run's account -- the mode, model id, request count, token estimate, duration and stop reason are returned by POST /review/suggest and held in the model_suggestion_runs row, and nothing reads them back; the workspace holds no applied round either, so a run had nothing to record (record: P4-G1-G4-system-capability-record.json) |
| G2-4 | Preview, per-item approval, apply, publish, retry and recovery pass | Preview/apply digest equality (step 6 vs step 8); per-suggestion decisions recorded (step 7); a forced failure's retry and a restart's recovery observed and recorded (the §7.3 paths) | Runbook steps 6–8, plus a deliberate interruption exercise | System capability (witnessed), **confirmed on the pilot paper** | PENDING — the workspace holds no closed binding, so no preview, decision or apply was recorded; the runtime holds 0 step(s) and the highest attempt any of them took was None, so the retry arm was not exercised either (record: P4-G1-G4-system-capability-record.json) |
| G2-5 | Key refusal paths and evidence checks pass | The refusal record: each named class injected and refused at an openable address (G0 §2 carried item 5's closing condition); the digest checks refusing a mismatched deliverable | The permission-boundary drill, plus runbook step 9's digest checks | System capability, **re-confirmed on the pilot deployment** | PENDING — the workspace holds no closed binding, so there was no deliverable whose digest could be checked: the ledger holds 0 artefact(s) [] and none of them is a dossier manifest (record: P4-G1-G4-system-capability-record.json) |

**Gate verdict:** PENDING — G2 closes when all five slots are filled and
consistent; a slot that fails is an issue with severity and an owner,
not a silent carry.

---

## P4-G3 — Multi-source learning

**Plan §11 conditions, paraphrased (§11, P4-G3).** Read 2026-11-25.

- The paper and its revision trajectory, the PPT decks and the meeting
  notes are all retrievable, located by their source.
- The two-layer structure — raw material, and the guidance rules drawn
  from it — is traceable.
- Rules the advisor has confirmed can be called on by the group's other
  projects.
- Unconfirmed relations cannot become guidance rules directly.

**Evidence slots.**

| # | Condition | Evidence to fill in | Produced by | Coverage kind | Status |
|---|---|---|---|---|---|
| G3-1 | Paper/revision trajectory, PPT and meeting text are retrievable by source | Search exercises per source kind: `GET /trajectory/search`, `GET /ppt/search`, `GET /meeting/search`, each returning hits addressed to their source; the pilot paper's own trajectory resolving | The multi-source line's witnesses, run against pilot-era data | System capability (the three search surfaces), **confirmed with the pilot's real sources** | PENDING — the trajectory, deck, meeting surface(s) answered with no hit for the query, so the retrieval was not exercised there; the workspace holds 1 task(s) and 0 of them is bound to material, and the ledger holds 0 source(s), so there was nothing indexed to retrieve (record: P4-G1-G4-system-capability-record.json) |
| G3-2 | The two-layer structure (raw material → guidance rules) is traceable | A walked link from a raw source through its distilled rule to the rule's record; the rule names the material ids it came from | The guidance rule records | System capability | PENDING — the memory holds no rule, so the link from a raw source through a distilled rule to the rule's record was not walked; the ledger holds 0 source(s) (record: P4-G1-G4-system-capability-record.json) |
| G3-3 | Advisor-confirmed rules are callable by other projects | A rule confirmed by the advisor (`POST /guidance/rules/{id}/confirm`, then `/publish`) read from a **second** project's context | The rule-sharing exercise | System capability | PENDING — the memory holds no confirmed rule, so no advisor confirmation was exercised; a second project's context is not reachable either, because no route lists the workspace's paper projects (record: P4-G1-G4-system-capability-record.json) |
| G3-4 | Unconfirmed relations cannot become guidance rules directly | The refusal: an unconfirmed rule's publish refused; the usable-rules read (`GET /guidance/usable`) returning only confirmed rules | The rule-sharing exercise's negative arm | System capability (witnessed) | PENDING — the listing was read and served no rule, so its filtering was not exercised; the memory holds no rule to filter (record: P4-G1-G4-system-capability-record.json) |

**Gate verdict:** PENDING. G3's evidence does not need the pilot
participants — it needs the pilot's data landscape (a real paper, a real
deck, a real meeting text) to exercise the surfaces against.

---

## P4-G4 — Real trial

**Plan §11 conditions, paraphrased (§11, P4-G4).** Read 2026-11-25.

- 3–5 members completed the first trial round.
- One paper completed the full loop.
- The efficiency, quality and traceability data are recorded.
- Blocker issues are fixed, or explicitly block any wider trial.
- Serious issues have an owner, a fix version and a regression record.

**Evidence slots.**

| # | Condition | Evidence to fill in | Produced by | Coverage kind | Status |
|---|---|---|---|---|---|
| G4-1 | 3–5 members completed the first trial round | The participant roster (roles, not names): 1 advisor + 2–4 students, each having completed the session(s); session dates | Runbook §0 roles + the session log | **Real trial only** | PENDING |
| G4-2 | One paper completed the full loop | Same evidence as G2-1 (the completed trace) | Runbook steps 1–11 | Shared with G2-1 | PENDING — the chain was not read at all: GET /trajectory serves the comments under named issue keys, and no route lists the workspace's paper projects, so no key could be named -- the workspace holds no closed binding to carry a project id either, so the walk resolved no link (record: P4-G1-G4-system-capability-record.json) |
| G4-3 | Efficiency, quality and traceability data recorded | The §9.3 measures: wall-clock time, manual-step count, decision counts, coverage, correctness, deliverable consistency — each with its number and where it was read from | Runbook step 12 + the assembled record | **Real trial only** | PENDING |
| G4-4 | Blocker issues are fixed, or explicitly block wider trial | The issue list filtered to severity `blocker`: each row's status `fixed` (with its fix version) or an explicit wider-trial block decision | The issue record (step 12), triaged | **Real trial only** | PENDING |
| G4-5 | Serious issues have an owner, a fix version and a regression record | The issue list filtered to severity `serious`: each row's owner, fix version and the regression check that re-ran | The issue record (step 12), triaged | **Real trial only** | PENDING |

**Gate verdict:** PENDING — G4 is the trial's own gate; it closes on the
participants' completed round and the triaged issue ledger, both of
which only the real trial produces.

---

## The three pre-opening decisions (plan §12)

The plan names three items that must be settled **before** the pilot's
work orders are cut (plan §12, paraphrased: how distilled rules are
case-validated; the retention, withdrawal and sharing boundary for
audio/PPT/paper material; the first runnable Phase 4 version and the
first trial's target date). They are decisions, not measurements; each
is recorded here with its owner and its `TBD` slot, so the skeleton is
honest about what is not yet decided.

| # | Decision (plan §12) | Where the answer lands | Owner | Status |
|---|---|---|---|---|
| D-1 | CONFIRMED 2026-11-24: mentor-only single-reviewer case validation, recorded on the rule version | A short section in the rule-sharing record (or an amendment to the plan) naming how a distilled rule is validated against cases before the advisor confirms it | Advisor + the multi-source line's owner | CONFIRMED |
| D-2 | CONFIRMED 2026-11-24: raw material deleted after trial, desensitised copy retained for group retrieval and rule reproduction | An extension of the desensitisation checklist's boundary section (or the G0 §4 pointer record), naming retention periods, the withdrawal procedure and the sharing boundary per material kind | Advisor (data owner) | CONFIRMED |
| D-3 | CONFIRMED 2026-11-24: v0.1.0, target date 2026-11-24 | The release record's version line and the trial's dated session plan | Owner | CONFIRMED |

**These three are prerequisites, not gate conditions.** The gates close
on their evidence; the decisions unblock the work orders that produce
the evidence. A gate section may not be marked PASS while its decision
is still TBD if the decision is a precondition of that gate's evidence
(D-2 bounds what the trial may retain; D-3 dates the sessions G4-1
counts).

---

## How this skeleton is filled and signed

1. The trial fills the evidence slots as the runbook produces them —
   each slot names its producer, so a slot with no evidence has a named
   reason.
2. The advisor reviews the filled record against the plan's conditions;
   disagreements become issues, not silent edits.
3. The owner signs the exit decision in the P3 record's form — verdict
   per gate, the commit the decision was made at, and the carried notes.
   **No verdict is written before its evidence exists**; a skeleton
   that predicted its own verdicts would be grading the trial in
   advance, which is exactly what this record exists to prevent.
