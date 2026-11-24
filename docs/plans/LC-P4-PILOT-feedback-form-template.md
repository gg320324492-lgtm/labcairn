# LC-P4-PILOT — unified trial feedback form template

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Status:** `DRAFT — template for the pilot; the pilot ticket may extend
fields but may not drop the mapping to the Issue record`

**How to confirm.** The advisor (as the pilot's owner of the trial
protocol) reviews the form against plan §9.4 and G0 §6, confirms the
severity/type scales and the Part 2 → Issue mapping, and signs the
confirmation with a date on the pilot ticket's preparation record. The
pilot ticket may extend fields (its stated right) but the mapping to
the Issue record must survive. **Until that signature exists, the form
must not be handed to participants and step 12 (participants supply
quality conclusions) must not run.** The signature goes on the pilot
ticket's preparation record; this document stays `DRAFT` until then.
**Source plan:** [`PHASE_4-execution-plan.md`](PHASE_4-execution-plan.md)
§9.4 (problem recording: severity + type on every issue) and §9.2 step 12
(participants supply quality conclusions).
**Data-model source:** [`LC-P4-G0-baseline-freeze.md`](LC-P4-G0-baseline-freeze.md)
§6 (Issue link fields).

Plan §9.4 defines two recording channels: the system records the objective
trace (task, version, opinion, operation steps, errors, durations, retries),
and the unified feedback form records subjective experience, problem
descriptions and improvement suggestions. This template is that form. Every
feedback item is designed to map onto one Issue record in the pilot data
model (G0 §6), so a completed form can be ingested without re-typing or
guessing links.

**Severity scale (plan §9.4):** `blocking` — the loop cannot
continue; `severe` — a wrong or lost result, or a workaround that
risks the data; `normal` — an inconvenience with a usable
workaround; `suggestion` — an improvement idea, nothing broken.

**Type scale (plan §9.4):** `function`, `ui`,
`performance`, `model`, `documentation`.

## Part 1 — Submitter context (once per form)

| Field | Kind | Notes |
|---|---|---|
| Submitter role | choice: `advisor | student` | Plan §9.1: one advisor, 2–4 students |
| Session date | date | When the reported use happened |
| Task id | system-filled | The pilot task the form belongs to (G0 §6 `Task.id`); the form tool or template pre-fills it so submitters never guess ids |
| Stages used this session | multi-choice: import / parse / model-suggestions / review / preview / apply / publish / deliverables / export | Mirrors plan §9.2's loop steps; anchors Part 2 items to where they happened |

## Part 2 — Problem items (repeatable; one item per problem)

Each item below becomes one Issue record. Fields marked *(system)* are
filled by the form tool from the session's trace, so the submitter's
subjective report and the system's objective record meet at the same id.

| # | Form field | Filled by | Maps to Issue field (G0 §6) |
|---|---|---|---|
| P-1 | Problem title (one line) | submitter | — (human-readable companion to `Issue.id`) |
| P-2 | What happened — free text | submitter | feeds the Issue's description record |
| P-3 | Steps to reproduce | submitter | description record |
| P-4 | What you expected | submitter | description record |
| P-5 | Stage where it happened | submitter (choice from the Part 1 stage list) | `Issue.stage` |
| P-6 | Severity | submitter (choice: `blocking | severe | normal | suggestion`) | `Issue.severity` |
| P-7 | Type | submitter (choice: `function | ui | performance | model | documentation`) | `Issue.type` |
| P-8 | Related opinion (if any) | submitter picks from the session's opinion list (title/locator shown, id behind the label) | `Issue.linked_opinion_ids` |
| P-9 | Related deliverable (if any) | submitter picks from the session's deliverables (`marked | clean | reply-table | quality-report`) | `Issue.linked_deliverable_ids` |
| P-10 | Related version (if any) | *(system)* the version ids in play during the reported stage | `Issue` ↔ `Version` trace via `task_id` |
| P-11 | Evidence attachment pointer | submitter (path/screenshot id in the authorised environment) | stored as a path/digest pointer only (G0 §4 boundary — no material in the repository) |
| P-12 | Session trace reference | *(system)* operation steps, errors, durations, retries from the system record for the same time window | the objective counterpart the form cannot see (plan §9.4 channel 1) |
| P-13 | Workaround used, if any | submitter | description record; a `blocking` item with a working workaround is re-graded in triage |
| P-14 | Frequency | submitter (choice: once / sometimes / every time) | description record |

**Mapping rule:** one Part 2 item = one Issue record. A form with three
problem items produces three Issues, all linked to the same `task_id`.
The form's own submission id is stored on each Issue so the batch stays
traceable.

## Part 3 — Session experience (once per form; not per problem)

| # | Field | Kind |
|---|---|---|
| E-1 | Overall, could you complete the full loop this session? | yes / partially / no |
| E-2 | Steps you had to do by hand that the system should have done | free text (feeds §9.3's "manual redo steps" metric) |
| E-3 | Where you waited too long | stage multi-choice + free text (feeds the performance view) |
| E-4 | Model suggestions this session: too many / about right / too few; useful / mixed / not useful | two choices (feeds the model line; never overrides per-suggestion approvals) |
| E-5 | One thing to keep as-is | free text |
| E-6 | One thing to change first | free text |
| E-7 | Anything the system recorded that does not match what you experienced | free text (a reconciliation hook between the system trace and the human account) |

Part 3 items are experience data: they inform the pilot report and the
fix-version plan; only Part 2 items become Issue records.

## Part 4 — Triage fields (pilot team fills after receipt; not the submitter)

| # | Field | Maps to Issue field (G0 §6) |
|---|---|---|
| T-1 | Triage decision: accepted as Issue / merged into Issue `id` / not a defect | `Issue.status` |
| T-2 | Confirmed severity and type (may differ from P-6/P-7; the record keeps both the submitted and confirmed values) | `Issue.severity`, `Issue.type` |
| T-3 | Fix target version | `Issue.fix_version` (per plan §10's trial-fix version rhythm) |
| T-4 | Status tracking | `Issue.status` — `open | triaged | fix-planned | fixed | verified | closed | wont-fix` |
| T-5 | Verification note | links the re-test that closed the issue back to the same task/version trace |

## Completion notes for submitters

- One form per working session; add a Part 2 item the moment a problem
  happens rather than reconstructing at the end.
- Severity is your judgement, not a report of how you feel about the
  product overall — "annoying but I finished" is `normal`, "I could not
  finish" is `blocking`.
- If a problem involved the model's suggestions (wrong suggestion, wrong
  evidence location, refusal, timeout), set type to `model` and name the
  opinion it concerned (P-8) — that link is what lets the team compare the
  model's record with your experience.
- Do not paste manuscript text, reviewer comments, or screenshots of
  un-redacted pages into the form's free-text fields; reference them by
  locator (P-11). The form travels; the material stays in the authorised
  environment.

## How to ingest

A completed form is ingested into the system's Issue record with
`scripts/pilot_feedback_ingest.py`. The input is one JSON file holding one
or more completed forms: each form carries the Part 1 context
(`project_id`, `task_id`, `submission_id`, `submitter_role`,
`session_date`, `stages_used`) and an `issues` list with one object per
Part 2 item. Every item becomes exactly one Issue record — the same
one-item-one-record rule the template states above.

The form's severity and type words are the submitter's words, and the
record's two closed vocabularies (G0 §6) are the system's. The tool maps
between them, once, in the template's own correspondence:

| Form word (P-6) | Issue severity |
|---|---|
| `blocking` | `blocker` |
| `severe` | `serious` |
| `normal` | `minor` |
| `suggestion` | `suggestion` |

| Form word (P-7) | Issue type |
|---|---|
| `function` | `function` |
| `ui` | `interface` |
| `performance` | `performance` |
| `model` | `model` |
| `documentation` | `documentation` |

A word outside the form's vocabulary is reported as an error in that item;
nothing outside the record's vocabulary is ever written, because the write
goes through the application layer's `record_issue`, which refuses it.

The item's free-text fields (P-2 what happened, P-3 steps, P-4
expectations, P-8/P-9 pointers, P-11 evidence, P-13 workaround, P-14
frequency) are composed into the record's `error_text` in the template's
own order, so the record reads as the form did instead of losing every
field but the first. The form's `submission_id` opens that text: the
record's `feedback_id` column names an opinion comment the chain holds,
which a submission id is not, so the batch stays traceable in the text
rather than through a link the chain does not hold.

Two modes:

- **`--dry-run`** (the default) parses the file, validates every item
  against the closed vocabularies and the required fields, and prints the
  Issue records that would be created. Nothing is written. Every bad item
  is reported with all of its problems, so a stack of forms can be
  corrected in one pass.
- **`--apply`** records the items through the application layer — the same
  `record_issue` the API's `POST /issues` calls — against the workspace
  named by `--workspace`, reporting each item as created, skipped (its
  issue id is already recorded), or failed with the reason. Ingesting the
  same file twice does not duplicate rows: the issue id is the record's
  primary key, so re-ingestion is idempotent by the record's own identity.

```console
$ python scripts/pilot_feedback_ingest.py forms.json --dry-run
$ python scripts/pilot_feedback_ingest.py forms.json --workspace . --apply
```

Exit status is 0 when every item was created or skipped (or, on a dry run,
when nothing failed validation), 1 when at least one item failed, and 2
when the input could not be read or parsed at all.
