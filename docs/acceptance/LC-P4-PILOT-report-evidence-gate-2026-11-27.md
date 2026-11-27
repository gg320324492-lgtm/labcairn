# LC-P4-PILOT — the evidence gate is the door a report goes through

**Ticket:** LC-P4-PILOT (the report's read-side door, and the gate no surface walked through).
**Date:** 2026-11-27.
**Tree:** `ba4e537db76e68962cd15c63d4a2da6e354710f2` (worktree
`elastic-elbakyan-73c189`, branch `claude/elastic-elbakyan-73c189`), the
commit this work sits on; the change is the commit that carries this record.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Material:** **none of the pilot's was read.** Every shape below is built in
a scratch workspace under the registered temp area `E:/labcairn-local/tmp/`,
from a synthetic material of the tests' own (a CSV whose cells read `1` and
`2`, 8 bytes), through the product's own operations. No document text, digest
of a document, or key of the pilot appears in this record.

## The gap, measured at the base revision

At `ba4e537`, `git grep -n evaluate_task` over `src/` returns **two** lines,
both in `src/labcairn/evidence/gate.py`: the export list and the definition.
No module in `src/` calls it. The gate's own docstring says it is *"the last
thing that runs before a report says something"*, and nothing ran it before a
report said anything.

The report operation (`src/labcairn/application/reports.py::render_report`)
gathered the task's records, built the document, ran the content checks,
rendered the four forms and wrote the revision. The gate was not in that
order. Both surfaces reach the operation — `labcairn task report`
(`cli/commands.py:1417`) and `POST /report` (`api/routes.py:781`) — so **one
call site covers both**, which is why nothing in either surface file had to
change.

This is the read-side counterpart of the gap the previous batch closed on the
write side (`LC-P4-PILOT-attest-refuses-dangling-source-2026-11-27.md`):
`store.attest` now refuses a citable status over a source the ledger dropped,
so a record cannot be *certified* over a dead source. Nothing asked the same
of a report about to *quote* certified records.

## What was built

| File | Change |
|---|---|
| `src/labcairn/evidence/gate.py` | `evaluate_records(connection, *, task_id, index, evidence_ids)` — the same four questions over a named subset, returning the same `GateResult`. `evaluate_task` keeps its whole-task contract and now delegates to the shared `_judge`, so the two doors cannot drift. |
| `src/labcairn/application/reports.py` | A new step 5: the gate runs over the records the document states as established, after the document is built and **before** the content checks. `ReportRendered` carries `evidence_gate` (the `GateResult`) and `unjudged_records`. |
| `src/labcairn/application/refusal.py` | `REPORT_EVIDENCE_REFUSED`, with its own docstring: a content refusal says the document and the ledger disagree; a gate refusal says the ledger's own account no longer holds. Different repairs, different reason. |
| `web/src/api/generated.ts` | Regenerated (`python -m labcairn.api.typescript web/src/api/generated.ts`) because `ReportRendered` changed. The diff is additive: `GateResult`, `Finding`, `ConflictDetail`, `ConflictSide`, and the two new fields. `tests/test_api.py::test_the_checked_in_typescript_is_what_the_python_models_produce` failed until it was regenerated, and passes after. |
| `tests/test_evidence_gate.py` | Four tests for the subset door; the fifteen existing tests are untouched. |
| `tests/test_report_evidence_gate.py` | **New**, four end-to-end tests through the console script. |

No CLI, API route, store, model, renderer or migration file changed. The
gate's refusal travels as `ApplicationRefusedError`, which both surfaces
already render with the reason and the message.

## What a finding does: the report is refused

The choice was between refusing the report and carrying the findings on it.
**Refused**, for three reasons:

1. **The gate's own contract.** Its docstring and `docs/plans/LC-P1-09-task-breakdown.md`
   §T09 say a gate that answers per-record and leaves the caller to decide is
   "a gate weakened into a suggestion", and that `citable` is empty when the
   gate fails. A report that renders with its findings attached is the
   caller citing the records that passed.
2. **A report is a citable artefact.** The Markdown, HTML, DOCX and PDF forms
   leave the workspace. A machine-readable finding beside a report whose PDF
   states a contradicted number is still a PDF that states it. Refusing keeps
   an unsupported report out of existence, which is the property
   `render_report` already holds: a report that cannot be produced leaves no
   file behind.
3. **The findings still reach the reader, in an actionable shape.** The
   refusal message enumerates every finding — record id, kind, and the gate's
   own sentence — because the gate reports the whole set rather than the
   first objection. A caller that fixed one and met the next would pay twice
   for the same mistake.

The scenario that would justify the other choice — a report that must go out
with its doubts visible — is already served by the document's own grading:
an `extracted` claim prints `(extracted)`, and an unresolved record is
disclosed in its own section. Those are statements the report makes; they do
not need the gate's findings to make them.

## The scope, and what each alternative costs

The gate judges a task's whole record set. The report is about some of them.
Three scopes were on the table; each was measured on a real migrated store
(the measurement script is outside the repository, in
`E:/labcairn-local/tmp/w-gate-measure/`, and its output is quoted verbatim):

| Scope | Measured cost |
|---|---|
| **The whole task** (`evaluate_task`) | A task holding a **planned** record: `passed=False`, `findings=[('ev-planned','status')]` — a record the report does not carry. A task holding a **superseded** record: `passed=False`, `findings=[('ev-old','status')]` — the old row is *kept by design* (`store.supersede_record`), so this refusal can never be repaired; every later report of that task would be refused. A refusal the product does not promise, and one the caller cannot act on. |
| **Every record the report carries** | A task with an **extracted** claim: `passed=False`, `findings=[('ev-extracted','status')]`. But the document prints that claim as `(extracted)` — the gate's finding is the report's own text, answered by the report. Refusing there deletes the graded claim (`reports/model.py`'s `FINDING_STATUSES`) and the unresolved-record disclosure (`UNRESOLVED_STATUSES`). Measured under mutation M2 (this scope): **6 of the 10 test functions in `tests/test_application_layer.py` that request the `report_world` fixture** go red with `report_evidence_refused` — the four that stay green are the tests that refuse before the gate (unknown template, wrong path, escaping path, changed recipe) — and so do the API's and the CLI's own success paths: `tests/test_api.py::test_a_claim_recorded_through_the_service_makes_the_task_reportable` (403, `report_evidence_refused`) and `tests/test_cli_evidence_writer.py::test_task_claim_makes_the_task_reportable` (exit 3, same reason). |
| **The records the document states as established** (chosen) | The claims whose status is in `CITABLE_STATUSES`. The gate's status question is satisfied by construction; its three other questions — identifier resolved, checks still hold, no contradicting record — are exactly the claims the report makes beyond the ledger's status label, and exactly what the report cannot state itself. |

**What the chosen scope costs, said plainly.** A defect in a record the report
labels with a non-citable status is not refused by the gate. The report's five
content checks still compare every named record to the ledger (its number, its
words, its status, its citation), and the result names the unjudged records so
the gate's extent is visible rather than inferred. Measured:
`test_the_gate_does_not_refuse_a_record_the_report_labels_with_its_status`.

**What the gate cannot judge is on the report's own record.**
`ReportRendered.evidence_gate.considered` is the established records the gate
judged; `unjudged_records` is the records the report names and the gate did
not. **The two lists partition the document's `snapshot.record_ids`** — the
snapshot is the report's own statement of every record it carries — and that
partition is asserted against the written `report.json` in the second witness.
The gate judges no figure, table, snapshot or artefact link; those are the
content checks'. A report is not sound because the gate passed it.

## Where the gate runs in the order

Gather (3), document (4), **gate (5)**, checks (6), forms (7), revision (8),
records (9), result (10). The gate runs **before** the content checks because
the two ask different questions of the same ledger: the checks compare the
document with the ledger as it is now, while the gate asks whether the
ledger's own recorded verification still holds. A document built from a
rule-verified record whose source has drifted would pass a comparison against
that unchanged record row, and the gate is the check that re-asks the source
by re-running the logged C1/C2/C3. Where that re-ask has no subject — an
attested record logs only C4 — the sibling gap in Limits is what remains.

The set is read from the **document**, not recomputed from the gathered
records: the document is what will be rendered and checked, and a second
computation of "which of these are established" is a second rule that can
drift from the builder's.

## Witnesses

All four new end-to-end tests run the console script (`run_cli`, the shared
rig at `tests/test_cli_support.py`, `COLUMNS=200` and `PYTHONIOENCODING` set
by that rig), over a workspace the CLI itself made, with the state machine
driven through the store's own write seam where the CLI has no command for it
(`advance`, `append_record`).

| Test | Property | Mutation that reddens it |
|---|---|---|
| `tests/test_report_evidence_gate.py::test_a_report_over_an_attested_record_carries_the_gate_s_verdict` | A citable record is judged, passes, and the result names it. | — (control) |
| `...::test_the_gate_does_not_refuse_a_record_the_report_labels_with_its_status` | An `extracted` claim renders, is named in `unjudged_records`, and `considered + unjudged` equals the document's `snapshot.record_ids`. | M2, M3 |
| `...::test_the_gate_does_not_refuse_a_record_the_report_does_not_carry` | A planned record in the task does not refuse the report, and is in neither list. | — (scope; M2's opposite arm) |
| `...::test_the_report_is_refused_when_the_gate_finds_a_contradicted_number` | Two records about one cell: the claim's number agrees with the ledger, every content check would pass, and the gate alone refuses. Exit 3, reason `report_evidence_refused`, both record ids and the conflict in the message, no artefact and no file written. | M1 |
| `tests/test_evidence_gate.py::test_the_subset_door_judges_the_records_it_is_given_and_no_others` | The subset door passes over a set the whole-task door refuses, and `considered` is exactly the named set. | — |
| `...::test_the_subset_door_keeps_the_ledger_s_order_not_the_caller_s` | Two callers naming one set get one `considered` sequence. | — |
| `...::test_the_subset_door_refuses_an_id_the_task_does_not_hold` | A record the task does not hold is a `ValueError`, not a silent pass. | — |
| `...::test_the_subset_door_still_names_the_record_a_conflict_is_with` | One side judged, both sides in the detail: A5 at the narrower door. | — |

### Mutations, applied and reverted

- **M1 — the gate's verdict changes nothing.** `if False and not result.passed`
  in `_the_evidence_gate`. The refusal witness goes red with exit **0**, the
  report's v1 written, and the result carrying
  `"evidence_gate":{"passed":false,...}`. The three other witnesses stay
  green. That output is the failure the task names: a finding merely logged.
- **M2 — every carried record is judged** (`judged =` every claim, not only
  citable ones). The labelled-record witness goes red: the report refuses its
  own `(extracted)` claim. The other three stay green. Run against the product
  suites as well, it reddens **6 of the 10** tests in
  `tests/test_application_layer.py` that request the `report_world` fixture,
  plus `test_api.py::test_a_claim_recorded_through_the_service_makes_the_task_reportable`
  and `test_cli_evidence_writer.py::test_task_claim_makes_the_task_reportable`,
  each with `report_evidence_refused` — the measured price of the wider scope.
- **M3 — the result does not say what was left out** (`unjudged = ()`). The
  labelled-record witness goes red on the partition assertion. The other
  three stay green.

The tree's measured state is the unmutated one; each mutation was reverted
and the witnesses re-run green.

## Runs

- `tests/test_evidence_gate.py`: **19 passed** (15 existing, 4 new).
- `tests/test_report_evidence_gate.py`: **4 passed** (~60 s; each test drives
  the console script several times).
- `tests/test_application_layer.py`, `tests/test_api.py`,
  `tests/test_cli_layer_models.py`, `tests/test_cli_evidence_writer.py`,
  `tests/test_evidence_gate.py`, `tests/test_report_evidence_gate.py`
  together, **at the final tree**: **253 passed, 1 skipped** (POSIX
  permission bits), **0 failed**, in **440.79 s (7:20)**, exit 0. This is the
  run whose count is quoted. An earlier run of the same six files had
  **252 passed, 1 skipped, 1 failed** — the failure was
  `test_the_checked_in_typescript_is_what_the_python_models_produce`; it was
  fixed by regenerating `web/src/api/generated.ts`, the parity test was
  re-run green, and the final run above is the one that confirms it.
- `ruff check .` and `ruff format --check .`: clean, 584 files.
- `mypy --strict` over the project's configured targets (`src`, `conftest.py`,
  `tests`): **no issues in 509 source files**.
- `tests/test_ci_shard_coverage.py`: **2 failed**, and the only file named is
  `test_report_evidence_gate.py` — the expected failure until the integrating
  session registers it.

## Limits

- **The pilot was not read and nothing is claimed about it.** The gate's
  refusal cases reachable through the surfaces are: a source edited after a
  rule verification (a C1/C2/C3 log re-runs differently), a write that went
  around the store with an unresolved identifier, and a contradicting record
  on one anchor. A person's attestation logs C4 only, and `store.attest` now
  refuses a dangling source and an unresolved identifier at the door, so the
  write side closes the cases the read side would catch.
- **The gate judges evidence records only.** It does not judge a figure's
  caption, a table's number, the snapshot, or an artefact link. The result
  says which records it judged and which it did not; it cannot say that it
  did not look at the figures, and the module docstring says it.
- **A conflict is reported from the judged side only**, with both records in
  the detail. A record outside the judged set can appear in a finding's
  detail but not in `considered`; that is A5's symmetry kept at the narrower
  door rather than a claim that the gate judged it.
- **The gate's drift question has no subject on an attested record, and this
  is measured, not argued.** `store.attest` appends a **C4** entry and nothing
  else (`src/labcairn/evidence/store.py:595`), and the gate re-runs only the
  checks the record's log holds (`gate.py::_reverify`, via
  `_logged_outcomes`). Re-running C4 yields `not_checked`, which is what the
  log says, so no drift finding is raised — **even when the source's bytes
  have moved.** A probe run in this window (`E:/labcairn-local/tmp/w-gate-probe/probe_attested_drift.py`,
  its own synthetic 2x2 CSV, no pilot material) measured it end to end: claim
  a cell, attest it, edit the file on disk without touching the cited cell,
  then `labcairn task report --json` → **exit 0**, the report written, the
  receipt's `staleness` `"current"`, and the gate
  `{"passed": true, "findings": [], "considered": [<the record>]}`. Three
  boundaries make that state possible, and none of them is a defect in this
  change:
  - the attested record's log holds only C4, so the gate's drift question has
    nothing to re-run it against;
  - the content check deliberately does **not** compare the record's
    `source_content_hash` (`src/labcairn/reports/checks.py:310-319`, and its
    docstring says why: drift is marked on the receipt, not refused as a
    content failure); the links check resolves the address, and an address
    that still resolves is not a hash that still matches;
  - the receipt's `staleness` is computed from the hash the **ledger** holds
    for the source, so a file changed on disk without a re-ingestion leaves
    the ledger's account — and therefore the receipt — `current`.
  A rule-verified record is different: its log holds C1/C2/C3, the gate
  re-runs them, and `tests/test_evidence_gate.py::test_a_source_edited_after_verification_fails_the_gate`
  witnesses the drift finding. But `advance` has **no caller in `src/`**
  (`git grep -n "advance(" HEAD -- src/` returns the definition only), so
  today the only citable status a surface can produce is `user_attested` —
  exactly the one this gap is about.

## What is still open (the next batch's work)

**The gate should ask the source directly for a citable record, not only
re-run the checks its log happens to hold.** A citable record's log is the
audit trail of how it became citable; it is not the list of questions the
last door owes the source. Running C1 for every record the gate judges
(whether or not C1 is logged) would make the probe above refuse — an attested
record whose source bytes have moved would be caught at the door rather than
surviving into a report whose receipt says `current`. That is a change to
`gate.py`'s re-verification rule and to what its witnesses assert, so it is
not made here: this change wires the door, and this record measures where the
door's question stops. Until it is made, an attested record over a source that
moved on disk since attestation is a state the report path does not catch.

## For the integrating session

1. **Register `tests/test_report_evidence_gate.py`** in
   `tests/evaluation/manifest.py` and `.github/ci-shards.json`. Marker `e2e`,
   four tests, ~60 s on this machine; it builds a CLI workspace per test and
   plants records through the store, like `test_cli_evidence_writer.py`.
   Until it is registered, `tests/test_ci_shard_coverage.py` is red for that
   reason alone.
2. **`web/src/api/generated.ts` changed** and must land with the rest: it is
   the checked-in contract generated from the models, and the parity test
   fails without it.
3. `src/labcairn/application/reports.py` and
   `src/labcairn/evidence/gate.py` are the two source files this window
   touched; neither is on another window's list.