# LC-P3-04 — comment-to-revision loop: substitute run

**Date:** 2026-11-10.
**Branch:** `claude/musing-cray-46abd9` (worktree
`E:\LabCairn\.claude\worktrees\musing-cray-46abd9`; the worktree's own path
is named here because this is a local run record, not a public-boundary
document).
**Base:** `4855ea6` (LC-P3-03's merge into `main`).
**Head of this work:** the last commit on this worktree branch when the
record was written; its full SHA is printed by `git rev-parse HEAD` in the
checkout, and the six code/evidence commits are `3d3a8ea…` (the binding and
the two renders), `0ea0eef…` (the integration witnesses), `15a29d7…` (the
refusal witnesses), `159c161…` (the tightened witness), `a2334a7…` (the
workbench wiring) and `62c02c9…` (lint and strict typing).
**Status:** local evidence only. No push, no pull request, no CI run. The
board row is the commander's to move; this record does not claim `PASS` for
Phase 3 G2.
**Substitute-first:** all-synthetic by nature (`PHASE_3-work-orders.md` §9
2.8). No provider call, no credential, no spend, no advisor material, no COM
or UI automation. The suggestion source is an injected pure function
(`binding_support.substitute_suggester`); every byte in every witness is
authored in the test tree.

## 1. What ran, and on which machine

| What | Where | How measured |
|---|---|---|
| 17 witnesses (two new files) | Windows 11 Pro 10.0.26300, CPython 3.12, local venv at `E:\LabCairn\.venv`, `PYTHONPATH` pointed at this worktree's `src` | `python -m pytest tests/test_binding_loop.py tests/test_binding_loop_refusals.py --basetemp=E:\labcairn-local\tmp\b404\btN` → **17 passed** (`bt33`; repeated `bt6` through `bt32` while the code was being fixed). |
| The whole suite | same machine, same interpreter | `python -m pytest --basetemp=E:\labcairn-local\tmp\p304-suite\bt1` → the count is recorded in §5 below, measured on this tree at `62c02c9…`. |
| Six counter-mutations | same machine | `run_mutations.py` in `E:\labcairn-local\tmp\p304-mutations`; each patch applied to the product module with raw bytes, one witness run, module restored. All six ended **RED** — see §4. |
| The witness ledger | same machine | `python scripts/witness_ledger.py 4855ea6 62c02c9` → **LOST — none**; **ADDED — 17**. |
| The workbench | same machine | `pnpm typecheck`, `pnpm lint`, `npx vitest run` in `web/` → **14 files, 129 tests passed**, lint clean. |

Every pytest run set `TEMP`, `TMP` and `TMPDIR` to
`E:\labcairn-local\tmp\…` (outside the repository) and pinned
`MPLCONFIGDIR` under it. Every run used its own `--basetemp` subdirectory;
no two runs shared one. No status was read from a piped command.

## 2. What the binding is

`src/labcairn/papers/binding.py` binds what existed:

- **open** imports the original through LC-P3-03's `open_loop` and records
  the input version's comments through `record_feedback`. Every opinion is
  then placed: a comment whose anchor resolved is `located`; anything else
  (`unknown`, `position`) is `uncertain_location` — **a location failure
  with a name, never a skip**.
- **suggest** asks the injected source about the located opinions only. The
  source's answers are `ModelSuggestion` records — **separate records from
  anything a person says**, per ADR-0016.
- **apply** takes the reviewer's verdicts (accepted / partly accepted /
  rejected / pending, plus a `needs_evidence` flag), applies the approved
  suggestions through the edit seam (`plan_edit`/`surgical_bytes`), and
  publishes each draft through **its own LC-P3-03 loop** — one import, one
  copy, one publication, one receipt each. The marked draft is registered
  as the output version (status `unresolved`, per the version graph's own
  rule), with a human-accepted edge from the input version. The chain's
  edit rows and judgements are minted from the approval records, idempotently
  (ids derived from the correspondence and the verdict).
- **close** writes the **dossier manifest** — the four deliverables' shared
  binding to one task, one input version and one output version — as an
  artefact row (`labcairn.papers.binding` producer) beside the drafts.

Two render surfaces over the manifest, inside ADR-0013's report-only
boundary: `src/labcairn/reports/response_table.py` (the point-by-point
table; an opinion absent from the table is a hole the witness asserts shut)
and `src/labcairn/reports/quality_report.py` (file delivery and research
quality as two sections that do not answer for each other). Product-minted
identifiers render verbatim behind a character whitelist; retrieved text is
escaped through `escape_markdown`.

The workbench gains a **Binding review** panel (`web/src/views/ReviewView.tsx`)
that finds the newest dossier manifest among the task's artefacts, reads its
bytes through the artefact content route, and draws every opinion, verdict,
unresolved task and handover. No binding closed, no panel.

## 3. What was refused, and what was handed over

The refusal witnesses (negative class) assert, against real files:

- a binding with **no review decisions** refuses before any byte lands — no
  publication rides it, and the output area holds no `published.bin` from
  the call;
- an edit the seam refuses becomes a **handover** carrying the seam's own
  reason (`text_not_located`), its detail and its next sentence — while the
  rest of the approved set still applies;
- a **second application** lands under distinct receipts (a second revision,
  not a replay) with the original's hash intact;
- an **unreviewed suggestion** produces no change and no dossier entry;
- the dossier's opinion list is **matched against the chain's rows** — the
  negative of the completeness claim caught by comparison.

## 4. Counter-mutations

Each patch made one property false; the named witness went red for it.
Every patch was applied with raw bytes and reverted with raw bytes; the tree
was clean at commit time (`git status` checked after the runs).

| Mutation | What it broke | Witness that went red |
|---|---|---|
| `uncertain-locations-silently-located` | uncertain anchors reclassified as located | `test_unresolved_opinions_surface_as_explicit_tasks` (and the placement witness) |
| `no-decisions-sails-through` | the no-review-decisions refusal neutered | `test_a_binding_with_no_decisions_refuses_before_any_byte_lands` |
| `pending-verdicts-applied` | pending suggestions applied | the unresolved-tasks witness (red via the chain's settled-correspondence guard) |
| `dossier-drops-the-clean-draft` | the manifest stopped naming the clean receipt | `test_the_four_deliverables_bind_to_one_task_one_input_one_output` |
| `table-drops-an-opinion` | the table dropped its last opinion row | `test_the_response_table_names_every_opinion` |
| `quality-report-collapses-the-sections` | the two sections merged | `test_the_quality_report_keeps_the_two_statuses_apart` |

The mutation harness lives outside the repository
(`E:\labcairn-local\tmp\p304-mutations\run_mutations.py`), as LC-P3-03's
does.

## 5. Measured gaps

1. **The chain's listings do not see the output area.**
   `source.inventory` and `source.read` declare source roots only
   (`src/labcairn/security/capabilities.py`), so
   `labcairn.papers.responses.list_response_links`,
   `labcairn.papers.edits.list_edit_actions` and the API's trajectory panel
   **drop** the rows whose child version is a published draft, and the
   papers layer's mint-from-the-file paths (`record_edits_from_revisions`,
   `record_revision_events`, `record_feedback` on an output version)
   **refuse** it. The binding therefore mints its rows from the approval
   records through the store's own writers, keeping every vocabulary and
   grant check the short-circuited paths would have run — and the rings
   witness reads the rows from the store, not through the listings. A
   reviewer reading the trajectory panel sees the input round's rows; the
   binding's rows are in the dossier. Widening the capability's
   `root_kinds` is an owner decision; this ticket did not widen it.
2. **The proposal table's response rows carry the four chain states** but
   the four statuses the work order names for the *review* (accepted /
   partly accepted / rejected / pending) live in the manifest's decision
   entries and are drawn by the review panel and the response table's
   Verdict column. The two vocabularies are related by
   `VERDICT_RESPONSE_STATES`, written once, and both are drawn — but a
   rejected suggestion has no chain row (there is no change for a link to
   name), so its rejection is recorded in the manifest and the table's
   Verdict column only.
3. **The workbench panel reads the newest dossier only.** A task with
   several closed bindings shows the latest round; earlier rounds are in
   their own manifests, reachable through the artefacts panel.
4. **The runner-measured shard costs are owed.** The two new test files and
   the support module are **reported to the commander for registration**
   (§6); the shard-balance witness is expected red until the batch's own
   runner run, exactly as §3 rule 3 states. No local timing is offered as
   a cost.

## 6. Registration entries reported to the commander (§3 rule 3)

The window does not edit the registration files. The entries it needs:

| File | Suggested class / clause | Notes |
|---|---|---|
| `tests/test_binding_loop.py` | `integration` / `approvals` | 12 witnesses; real files on disk; no provider. |
| `tests/test_binding_loop_refusals.py` | `negative` / `missing-material` | 5 witnesses over the refusal classes (no decision, seam refusal, duplicate, unreviewed, completeness). |

`tests/binding_support.py` is a support module, not a test file — it
collects no tests and needs no shard entry. Both test files declare their
`pytestmark` (`integration`, `negative`) already.

## 7. What reproducibility meant in this run

The substitute model is `binding_support.substitute_suggester`: **a pure
function of the opinion it is given** — the same comment yields the same
`ApprovedEdit` every run, no clock, no randomness, no provider. The
timestamps are one fixed moment (`MOMENT`, 2026-02-01 UTC); the receipts'
ids are UUIDv7 from the product's own minting, so two runs differ in ids
but not in behaviour. "Reproducible input and output" here means: the
sample bytes are fixed by the corpus builder, the suggestions are
deterministic, and every hash, state and render is a pure function of
those. The real-model loop is LC-P3-08's deliverable and §9 2.3's held-open
half; CI stays on substitutes (LC-P3-00 §4).

## 8. What stays open

- The §14 item 5 decision is **answered** (2026-11-09: provisional is
  sufficient); ADR-0021's record stays `proposed`, and this ticket edited
  nothing in it.
- The real advisor loop stays LC-P3-08's; the substitute loop is this
  ticket's own deliverable and nothing in it claims more.
- The owner decisions the measured gaps name (§5 items 1): widening the
  inventory capability's root kinds, or leaving the chain's output-side
  rows dossier-visible only.
- Runner-measured shard costs, and the board row's move: the commander's.
