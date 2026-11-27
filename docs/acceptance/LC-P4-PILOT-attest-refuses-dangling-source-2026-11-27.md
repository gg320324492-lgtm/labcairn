# LC-P4-PILOT — the attestation refuses a record whose source is gone

**Ticket:** LC-P4-PILOT (the source-removal's own reading faces, the fix)
**Date:** 2026-11-27.
**Tree:** `3d99b07a2c3d45f6dd680fc1c82fca6ef38f0935` (worktree
`affectionate-carson-886aac`, branch `claude/affectionate-carson-886aac`), the
commit this work sits on; the fix is the commit that carries this record.
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Material:** **none of the pilot's was read.** Every shape below is built in a
scratch workspace under the registered temp area `E:/labcairn-local/tmp/`, from
a synthetic material of the tests' own (a CSV with one header row and one data
row, 15 bytes), through the product's own operations. No document text, digest
of a document, or key of the pilot appears in this record.
**Origin record:**
[`LC-P4-PILOT-dangling-source-ids-2026-11-26.md`](LC-P4-PILOT-dangling-source-ids-2026-11-26.md).

## What was measured

The origin record (tree
`124e843542b047c40712ddb01dd35642d0ce5f33`) measured a gap across the
product's faces. A source row is deleted; the address rows stay and still
resolve to the text; and then:

* `GET /records` (the layer operation `list_task_records`) answered 200 with the
  citing record intact — status `extracted`, its anchor ids and its
  `source_content_hash`;
* `task claim-attest` (the layer operation `attest_claim`) answered with exit 0
  and advanced that record to `user_attested`, which is in `CITABLE_STATUSES`,
  so a report could cite it;
* `observed_content_sha256` was `None`, because there was no source row left to
  read the hash from; and no wired face ran the C1-C3 comparison that would
  notice.

The cause, read from the code at that tree:
`src/labcairn/evidence/store.py::attest` moved a record to `user_attested`
after `_require_supported_identifiers` — which checks that the record's
*identifiers* resolved — and never asked whether the *source* its anchor names
still existed, nor compared the recorded hash against the source's current
bytes. `advance` runs C1 through `_run_check`, but the attestation path does not
go through `advance`. `src/labcairn/evidence/gate.py` has a `_reverify` step
that runs C1, but nothing under `src/` calls the gate.

ADR-0004 already states the rule. I4 (around line 297): a record whose
`source_content_hash` no longer matches the source is invalidated, not silently
refreshed, and downstream artifacts are marked stale. A2: a source whose bytes
moved makes C1 return `fail` and the record is invalidated per I4. A deleted
source row is the strongest case of that — the hash cannot be observed at all.

## What changed

The rule now lives at the layer that owns it — the store's state machine — and
reuses the check that already exists rather than a second implementation of it.

* `src/labcairn/evidence/store.py`: a new `DanglingSourceError(LedgerError)`, and
  a helper `_require_source_still_supports` that builds a `LabCairnIndex` over
  the connection and runs **C1** — `labcairn.evidence.checks.c1.check_source_exists`,
  the callable ADR-0004 fixes the home and signature of, reached through the same
  `_run_check` that `advance` uses. If C1's verdict is not `pass`, the helper
  raises `DanglingSourceError` with a message that names the source id (collected
  from the record's anchors) and carries C1's own detail — what could not be
  observed. `attest` calls it after `_require_supported_identifiers` and before
  the status is written, so a refused attestation leaves the record `extracted`.
* `src/labcairn/application/refusal.py`: a new code
  `CITATION_SOURCE_UNOBSERVABLE` in the closed vocabulary.
* `src/labcairn/application/evidence.py`: `attest_claim` catches
  `DanglingSourceError` ahead of the generic `LedgerError` clause and maps it
  onto `CITATION_SOURCE_UNOBSERVABLE`, keeping the store's message (which names
  the source). The CLI's `task claim-attest` and the API both render an
  `ApplicationRefusedError` through the same two fields, so they inherit the one
  answer without spelling their own.

No surface file was changed: `src/labcairn/cli/commands.py` and
`src/labcairn/api/routes.py` already render the refusal, so the new code reaches
them through the existing path.

## The witnesses

* `tests/test_dangling_source_read_faces.py` — the origin record's witness,
  **flipped**. The reading face is kept as the control: `list_task_records`
  returns the record as `extracted`, a status **not** in `CITABLE_STATUSES`, so
  a report may not cite it and the attestation's refusal is C1's rather than the
  removal having taken the record. The attestation face now asserts the refusal:
  `attest_claim` raises `ApplicationRefusedError` with reason
  `CITATION_SOURCE_UNOBSERVABLE`, the message names the source, and the record
  stays `extracted`.
* `tests/test_attest_source_presence.py` — new, five witnesses:
  1. a present, unchanged source still attests (the control that the check is not
     a blanket refusal);
  2. a source the ledger no longer holds refuses the store's `attest` with
     `DanglingSourceError` naming the source, the record left `extracted`;
  3. a source whose bytes moved under it — the hash no longer matches, the source
     row still present — refuses the same way (ADR-0004 A2's drift);
  4. `attest_claim` maps the refusal onto `CITATION_SOURCE_UNOBSERVABLE`;
  5. **the console script refuses with the layer's reason and the source's id
     named**, driven whole from the command line — record a claim, take the
     source back with `sources remove`, then attest — so the claim that the
     surface *inherits* the layer's answer is witnessed at the surface rather
     than assumed. This fifth witness was added by the integrating session,
     which measured the same path by hand first and found the exit code, the
     reason and the source's id all present; the witness holds it from then on.

## The mutation

**M1 — the pre-fix behaviour.** The helper's body was short-circuited with an
early `return`, so the attestation stopped asking the source — exactly the
behaviour the origin record measured. Under M1:

* `tests/test_dangling_source_read_faces.py::test_the_attestation_refuses_a_record_whose_source_is_gone` — **red**;
* `tests/test_attest_source_presence.py::test_a_missing_source_refuses_the_store_attestation_and_names_it` — **red**;
* `tests/test_attest_source_presence.py::test_a_moved_source_refuses_the_store_attestation_and_names_it` — **red**;
* `tests/test_attest_source_presence.py::test_the_application_refuses_with_its_own_code` — **red**;
* `tests/test_attest_source_presence.py::test_the_cli_refuses_with_the_reason_and_the_source_named` — **red**;
* the two controls — the reading witness and `test_a_present_unchanged_source_still_attests` — **green**.

Five red, two green (exit 1). The two that stay green are the point: a broken
implementation that refused *everything* would turn them red, so the five that
turned red are witnesses of *this* property and not of a blanket refusal. The
mutation was restored; `git status` shows `src/` carrying only the fix. The
integrating session re-applied M1 independently after adding the fifth
witness, and got the same five red and two green.

## What the fix does not cover

* **The report face is unchanged and already refuses.** The builder's C1
  re-verification (`src/labcairn/report/build.py`) refused a record citing a
  taken-back source before this change, naming the source; this record does not
  touch it. The fix closes the *attestation* door, through which a record could
  reach the citable set with nothing having asked.
* **`advance` to `verified_by_rule` is not re-guarded here.** That path runs C1
  when C1 is among the named checks, and `_require_precondition` requires a
  passing C1-C3 entry; a stale passing entry written before the source was taken
  back is a separate edge this window did not measure or close.
* **The reading face still returns the record.** `list_task_records` lists an
  `extracted` record whose source is gone; that is sound (it is not citable) and
  is the control the attestation witness leans on, not a defect.
* **A source that was never readable** is C1's `indeterminate`, not its `fail`;
  the attestation refuses on `not pass`, so that case is refused too, but it is
  not the measured gap and is not separately witnessed here.

## Claims, and the commit each is anchored to

* The gap, its cause and the faces it was measured through — the origin record,
  tree `124e843542b047c40712ddb01dd35642d0ce5f33`.
* The fix's behaviour, the five witnesses, the two controls and the M1 mutation
  result — this worktree, based on
  `3d99b07a2c3d45f6dd680fc1c82fca6ef38f0935`, local run on Windows (Python
  3.12.10), the commit that carries this record. Local evidence only; no runner
  has confirmed it.
* The local runs behind the numbers above: the flipped witness and the new file,
  6 passed; the blast-radius files (`test_evidence_store.py`,
  `test_evidence_gate.py`, `test_application_evidence.py`,
  `test_identifier_records.py`) 98 passed; the API attestation tests 2 passed;
  `mypy` (config `files = ["src", "conftest.py", "tests"]`) clean over 506
  source files; `ruff check` and `ruff format --check` clean on the changed
  files. The new test file is not yet in `tests/evaluation/manifest.py` or
  `.github/ci-shards.json`, so `tests/test_ci_shard_coverage.py` is red on this
  branch for that reason alone; the integrating session registers it after the
  batch merges.