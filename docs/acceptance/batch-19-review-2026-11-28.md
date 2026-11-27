# Batch 19 review — the gate on the report's path, and a drift the door cannot see

**Date:** 2026-11-28
**Range reviewed:** `ba4e537..8dacfea` on `main` — the window that wired
the evidence gate into the path a report takes: the read-side counterpart of
the write-side gap batch 18 closed (an attestation over a source the ledger no
longer holds).
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.** One window: the evidence gate now runs before a report
says anything, over the records the document states as established.

**A note on the order.** The gap was measured at the base revision: at
`ba4e537`, `git grep -n evaluate_task` over `src/` returned two lines, both in
`src/labcairn/evidence/gate.py` — the export list and the definition. **No
module in `src/` called it.** The gate's own docstring says it is *"the last
thing that runs before a report says something"*, and nothing ran it. The
window's answer is one call site — `render_report` — which both surfaces reach,
so neither surface file had to change.

## R1. No witness depends on a build artifact the runner does not have

**Pass.** The new witness file drives the console script through the
project's own rig (`run_cli`, from `tests/test_cli_support.py`) and builds its
ledger with the product's own writes, in a scratch workspace under the
registered temp area. No `dist/`, `build/`, wheel, sdist or `site-packages`
path appears in it. The material is a CSV of the tests' own: **no pilot
material is read and no model is asked**.

## R2. No witness hard-codes one platform's facts

**Pass.** The new file calls `run_cli`, so the console script's path is
**derived by the shared derivation** rather than spelled a second time, and the
two settings the project's other CLI witnesses set — `COLUMNS` at two hundred
and the child's encoding — arrive with the rig.

**This is the same failure batch 18's review caught in another window**, and
it is not repeated here: a second spelling of one fact is a fact that can be
spelled two ways wrong, and this project has already paid for that.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** Neither the new surface file nor the four new gate witnesses contain
a `skip`, a `skipif` or an `xfail`. **No arm of them can pass by not
running.**

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** The new record carries **no Han run** (measured: 0 characters) and
**no fullwidth enumeration comma** (measured: 0). The material the witnesses
use is synthetic and of the tests' own.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

**Pass, after a correction made here.**

The rule implemented is the gate's own four questions — status, identifier,
re-verification, conflict — and ADR-0004 A1's *"cites nothing"*: the gate
refuses **the set** rather than the failing record, and its `citable`
property is empty when it fails, because a partial list invites a caller to
cite the records that survived. Both sides are witnessed: the gate's own file
holds the questions, and the new file holds the seam the batch was about.

**The scope is witnessed on all three sides**, which is the property that
decides whether the narrower question is sound: a record the report prints
**with its status** does not refuse the report; a record the report does not
carry at all does not refuse it; and a record the report states as established
that the gate refuses does refuse it. The two lists the result carries —
`considered` and `unjudged_records` — are witnessed to partition the
document's snapshot.

**The correction.** The record claimed that drift on an attested record is
caught by the report's links check. **Measured, it is not** — the measurement
is below.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, and the batch's own debt is paid.** The new file is filed in
`tests/evaluation/manifest.py` (class `e2e`, clause `cli-task`, which is what
the file's own `pytestmark` declares) and in a shard on both platforms, at a
cost of `0.0` — the number is owed and it comes from a runner, not from here.

**One stale number corrected here.** `tests/test_evaluation_harness.py`'s
header said *"33 files declare `unit`, `integration` or `e2e`"*. Measured on
2026-11-28: **179** in `main` before this batch's file, **180** with it. The
number was stale by a hundred and forty-six, and it is not load-bearing — so
it was **removed rather than re-anchored**, with the reason written down: a
count that moves with every filed file is a number that has to be re-measured,
and the tree is the authority.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The surface witnesses build the **premise** — a ledger whose records
the product's own writes put there — and then read the product's answers: the
command's exit code, the refusal's reason, the result's `evidence_gate` and
`unjudged_records`. **No witness writes the answer it looks for.** The gate's
own four new witnesses read `evaluate_records` and `evaluate_task` on a store
the rig migrated, and one of them holds the case that matters most for a
narrower question: **a conflict is still reported in full when the record it
disagrees with is outside the subset** — the peer is named, and the finding is
not halved.

## The measurement that changed the record

**Measured on 2026-11-28**, with a probe outside the repository
(`E:/labcairn-local/tmp/probe-attested-drift/probe.py`, a synthetic two-by-two
CSV of the probe's own; nothing of the pilot's was read and no model was
asked):

> A `user_attested` record whose source file changed bytes — the quoted cell
> did not move, only the file's hash — is reported **successfully**. The
> command exits **0**, the report is written, and the receipt says
> `staleness: "current"`.

The chain behind it, each link measured rather than inferred:

1. The record's log holds **one C4 entry** and nothing else: `store.attest`
   writes C4 and no C1. The record is citable and it is the only citable
   status a person can reach.
2. The gate's drift question re-runs only the checks the record's log holds.
   Re-running C4 gives `not_checked`, which is what the log says, so **there
   is no drift finding**; the gate answers `passed: true, findings: []`.
3. `src/labcairn/reports/checks.py` says in its own words that
   `source_content_hash` is **deliberately not compared** — drift is a fact
   about time and not about the report's content — and the links check
   **resolves addresses**. An address that still resolves is not a file whose
   bytes are unchanged.
4. The receipt's staleness walk compares the **ledger's stored** hash with the
   material the manifest names, and the ledger's hash changes only when
   somebody re-ingests. A moved file is therefore still `current`.
5. `advance` has **no caller in `src/`**, so `verified_by_rule` is not
   reachable from any surface today. The rule-verified case — where the log
   holds C1 and the gate does find the drift — is witnessed in the gate's own
   file, but it is not a state a person can reach.

**So the gate's door is wired, and the door's question stops short of the one
citable status the surfaces can produce.** The record said so plainly after
the correction, and named the fix rather than making it: *the gate should ask
the source directly for a citable record, not only re-run the checks its log
happens to hold.* That work is open, and it is the next card.

## What this review did not cover

- **The fix itself.** The gate's re-verification rule, and the receipt's
  staleness walk, are not changed here. The window wired the door; this
  review measured where the door's question stops, and the next window
  changes the question.
- **Whether the two enforcement points should refuse or mark.** A claim whose
  material moved may be refused at the door, or marked stale on the receipt —
  ADR-0004 I4 marks the invalidation on the receipt, and the report's content
  checks deliberately do not refuse on drift. **The two points must not
  disagree about the same fact**, and which one owns it is the next window's
  call to make and record.
- **The CLI's human-readable rendering of the gate's verdict.** The result
  carries `evidence_gate` and `unjudged_records`, and the API's contract
  exposes both; the CLI's rendered table does not print them. The refusal —
  the part that matters — is rendered on both surfaces.
- **The figures, the captions and the snapshot.** The gate judges evidence
  records, and says so; it does not judge a figure's caption or a table's
  number. That is the scope the record states, and the record's own limits
  name it.

## What was measured here

Every run below was made on the merged tree, on this machine, with the
repository's own rules: `--basetemp` outside the checkout, `TEMP` and `TMP`
pointing at `E:\labcairn-local\tmp`, and **each run's own base temp
directory** — two runs that share one destroy each other's test tree.

| what | result |
| --- | --- |
| `tests/test_evidence_gate.py`, `tests/test_report_evidence_gate.py`, `tests/test_analysis_report_checks.py`, `tests/test_cli_layer_models.py`, `tests/test_ci_shard_coverage.py`, `tests/test_evaluation_harness.py`, `tests/test_chinese_totals_pin.py` | **206 passed**, 0 failed, 162.93 s |
| `tests/test_api.py`, `tests/test_application_layer.py` | **213 passed**, 1 skipped (POSIX permission bits — a platform fact, not a gap), 279.21 s |
| `ruff check .` | **All checks passed** |
| `ruff format --check .` | **584 files already formatted** |
| `mypy --strict src conftest.py tests` | **no issues in 509 source files** |
| `python scripts/witness_ledger.py ba4e537 HEAD` | **4345 → 4353** test functions, **LOST — none**; the eight added are this batch's four gate witnesses and four surface witnesses |

**The shard and manifest registrations are witnessed, not asserted.** The
shard file is read by `tests/test_ci_shard_coverage.py` and the manifest by
`tests/test_evaluation_harness.py`, and both ran in the table above: a file in
no shard is a test CI never runs, and a file in no class is a file whose cases
enter no denominator.

**One run was a false green, and it is named here.** The first attempt at the
table's first row named `tests/test_cjk_ceilings.py`, **which does not exist**;
pytest reported *"no tests ran"* and **exited 0**. A green that ran nothing is
the failure mode this project's rules are about, so the number above is from
the run that named only files that exist.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| No surface ran the gate before a report said anything | closed — `render_report` runs it after the document is built and before the checks, and both surfaces inherit one answer |
| The gate's scope had to be chosen, not guessed | closed — three scopes measured, two rejected on measured grounds, the choice and its cost written down |
| The record's claim that the links check catches drift on an attested record | **measured false**, corrected in place, and named as the next batch's work |
| A stale count in the evaluation harness's header | corrected here — the number was removed, with the reason |
| The new witness's cost | `0.0` until a runner measures it; filed in the manifest and in a shard |
