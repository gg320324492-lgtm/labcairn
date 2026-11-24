# LC-P4-PILOT — owner decisions before the pilot opens

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `DRAFT — a decision form for the owner; every decision is
TBD — owner to fill, and nothing here is decided until the owner signs`
**Source plan:** [`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md)
§12 (the three items still to be supplied before the work orders are cut).
**Related drafts:**
[`LC-P4-PILOT-desensitisation-checklist.md`](LC-P4-PILOT-desensitisation-checklist.md),
[`LC-P4-PILOT-model-authorisation-draft.md`](LC-P4-PILOT-model-authorisation-draft.md),
[`LC-P4-PILOT-feedback-form-template.md`](LC-P4-PILOT-feedback-form-template.md),
[`LC-P4-PILOT-runbook.md`](LC-P4-PILOT-runbook.md).
**Skeleton anchor:** [`../acceptance/P4-G1-G4-record-skeleton.md`](../acceptance/P4-G1-G4-record-skeleton.md)
"D-1 / D-2 / D-3" — the same three decisions carried in the exit skeleton.

The plan §12 names three pieces of information that must exist **before**
the pilot's work orders are cut. This document turns them into a decision
form: each item states the question, gives the owner a field to fill,
names which flows stay blocked while the field is empty, and lists what
code and documents already stand behind it. **Every answer field reads
`TBD — owner to fill`; this form does not guess an answer, and no
downstream step may read one into it.**

## How this form is used

1. The owner fills each decision field below and signs next to it.
2. The filled answer moves into the place the form's "answer lands"
   column names — the authorisation record, the checklist's boundary
   section, or a release record under `docs/releases/` — and the field
   here records the pointer, not a second copy of the decision.
3. A decision that is still `TBD — owner to fill` keeps its blocked
   flows blocked. Nothing downstream may start on the assumption of an
   answer.

## Decision 1 — How distilled multi-source rules are case-validated

Plan §12 item 1: *the case-validation method for multi-source distilled
rules.* This is skeleton decision **D-1**.

| Field | Value |
|---|---|
| Question to the owner | How is a distilled rule validated against cases before the advisor confirms it — which cases, how many, judged by whom, recorded where? |
| Answer (owner fills) | `TBD — owner to fill` |
| Blocked while unfilled | The rule-sharing flow (`/guidance/rules/{id}/confirm` → `/publish`) has no validation step to run, so no distilled rule can be confirmed or published; gate P4-G3's evidence (G3-2, G3-3, G3-4) cannot be produced. |
| What already supports this | The guidance-rules service and its confirm/publish refusals are built and witnessed (`tests/test_guidance_rules.py`, `tests/test_guidance_distillation.py`); the skeleton's D-1 row names where the answer lands (a section in the rule-sharing record or a plan amendment). |
| Answer lands in | The rule-sharing record's validation section, or an amendment to the plan — the skeleton's D-1 "where the answer lands" cell names both. |

## Decision 2 — Retention, withdrawal and sharing boundary for the materials

Plan §12 item 2: *retention period, withdrawal method and sharing
boundary for the audio, PPT and paper materials.* This is skeleton
decision **D-2**.

| Field | Value |
|---|---|
| Question to the owner | For each material kind (audio, PPT, paper): how long is it kept, how is it withdrawn, and who may share it? |
| Answer (owner fills) | `TBD — owner to fill` |
| Blocked while unfilled | The trial's material handling has no lawful boundary to sit inside: the desensitisation checklist's boundary section and the G0 §4 material-pointer record cannot be extended, so the pilot's material pointer record cannot open; gate P4-G4's sessions cannot be scheduled because what may be retained and shared is undecided. |
| What already supports this | The checklist's A/B/C/D items and the G0 §4 boundary (paths and digests only, no material bytes in the repository) are built and witnessed (`tests/test_pilot_runbook.py`, `tests/test_material_walk.py`, `tests/test_material_adapters.py`); the skeleton's D-2 row names the answer's landing place. |
| Answer lands in | An extension of the desensitisation checklist's boundary section, or the G0 §4 pointer record — the skeleton's D-2 "where the answer lands" cell names both. |

## Decision 3 — First runnable Phase 4 version and first trial date

Plan §12 item 3: *the first runnable Phase 4 version and the target date
of the first trial round.* This is skeleton decision **D-3**.

| Field | Value |
|---|---|
| Question to the owner | Which version is the first runnable Phase 4 version, and on what date does the first trial round run? |
| Answer (owner fills) | `TBD — owner to fill` |
| Blocked while unfilled | No release record can be cut for the first runnable version, so the pilot cannot run against a version anyone signed for (plan §10: every version gets a structured record under `docs/releases/`); the trial's dated session plan cannot be fixed, so gate P4-G4's dated evidence has no anchor. |
| What already supports this | The release-record tool is built and witnessed: [`scripts/release_record.py`](../../scripts/release_record.py) writes the seven-element record, [`docs/releases/README.md`](../releases/README.md) specifies it, and `tests/test_release_record.py` checks it. The runbook's session-logistics section names the baseline version the sessions run on. |
| Answer lands in | A release record under `docs/releases/<version>.json` (version line) and the trial's dated session plan (first trial date) — the skeleton's D-3 "where the answer lands" cell names both. |

## Signing

The owner signs each decision individually. A decision is **decided**
when its field carries the owner's answer, the pointer to where that
answer landed, and a signature with a date — not before. Until then the
status is `TBD — owner to fill`, and the blocked flows named above stay
blocked.

| Decision | Filled by | Signature / date |
|---|---|---|
| D-1 — rule case-validation | | |
| D-2 — material retention/withdrawal/sharing | | |
| D-3 — first runnable version and trial date | | |
