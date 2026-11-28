# LC-P4-PILOT — the report's door sees the source move under an attested claim

**Ticket:** LC-P4-PILOT (the gap the review measured on 2026-11-27 in the
evidence gate the report goes through).
**Date:** 2026-11-28.
**Tree:** `21ea0725ebd4dd833d50eeacd4698e31c4b34cd1`, the commit this work
sits on; the change is the commit that carries this record. Worktree
`.claude/worktrees/attested-drift-2026-11-28`, branch
`claude/attested-drift-2026-11-28`. Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.13 (the project's own `.venv`).
**Status:** local evidence only. No push, no pull request, no CI run, no
merge. The test files this work touches are under `src/` and `tests/`, so the
shard-cost witness (`tests/test_ci_shard_coverage.py`) will need
`python .github/remeasure_shards.py <run-id>` at the integrating session's
next run — that is the integrating session's step, not this one's.
**Material:** **none of the pilot's was read.** Every shape below is built in
a scratch workspace under the registered temp area
(`E:/labcairn-local/tmp/`), from a synthetic CSV of the tests' own whose cells
read `1` and `2`. No document text, digest of a document, or key of the pilot
appears in this record. No model request was made.

## The gap, as it was measured on 2026-11-27

The review's probe (outside this repository, at
`E:/labcairn-local/tmp/probe-attested-drift/probe.py`) recorded four facts at
`21ea0725ebd4dd833d50eeacd4698e31c4b34cd1`'s predecessor, and each one named a different mechanism:

1. An attested record whose source file changed bytes — the quoted cell did
   not move, only the file's hash — was reported **successfully**: `labcairn
   task report --json` exited 0, the report was written, and the receipt said
   `staleness: "current"`.
2. That record's log held **one C4 entry** (`not_checked`) and nothing else:
   `store.attest` writes C4 and no C1. C4's only verdict is `not_checked`, so
   the gate's drift question — re-run the checks the log holds and compare —
   compared `not_checked` with itself and had nothing to find.
3. `src/labcairn/reports/checks.py` says `source_content_hash` is deliberately
   not compared by the content check, and the links check only resolves
   addresses. An address that resolves is not bytes that are unchanged.
4. The receipt's staleness walk compared the **ledger's stored** hash with the
   manifest's material, and the ledger's hash only moves when somebody
   re-ingests — so a file edited on disk was still `current`.

`advance` has no caller in `src/`, so `verified_by_rule` is not reachable from
any surface; the only citable status a person can reach is `user_attested`,
and it was exactly the one the re-run could not see drift on.

## Where the two questions belong, and why

**1. The gate's own question set.** The gate now asks C1 about every record it
judges in a citable state, whether or not the record's log holds a C1 verdict
to re-run (`_the_source_still_supports`, called from `_judge`). It belongs
there rather than at the report's call site because both doors — the
whole-task `evaluate_task` and the subset `evaluate_records` — go through
`_judge`, and a rule written at one call site is a rule the other door does
not get. The finding is `kind="drift"`, the same kind the re-run reports,
because it is the same fact ADR-0004 I4 names: the verification recorded
against the record no longer holds. When the log's C1 verdict *disagrees* with
today's, `_reverify` has already reported that disagreement and this function
adds nothing; one fact is one finding. The existing witness
`test_a_source_edited_after_verification_fails_the_gate` still asserts exactly
one finding, and stayed green unweakened.

**2. The report's call site, and the file.** The gate's index answers from the
ledger, whose `content_sha256` is never refreshed (ADR-0004 I4); it cannot see
a file edited on disk since ingestion. Only the render has the workspace, so
the render opens every source the document's citations name, hashes it, and
compares it with the ledger's stored hash (`_refuse_moved_material`, step 5a
of `render_report`). A source that moved, or cannot be read at all, refuses
the report **before it is written**.

The card offered staleness-marking or refusal for this second point. Refusal
was chosen because a `STALE` mark is the receipt's label for an artifact that
*was current when it was made* and whose input moved since; a report made
after the move was never current, and its body would still state its claims as
established. With refusal there is no receipt to disagree with the gate, and
no born-stale revision for a reader to find later.

**The two points cannot disagree about the same fact.** The report compares
the **file** with the ledger; the gate compares the **record** with the
ledger. The record's binding to the file follows from the two, and each point
refuses on its own link. A moved file with an unchanged ledger row is refused
by the report; a re-ingested file with a stale record hash passes the report's
link and is refused by the gate. Neither door can pass a source the other
refuses.

**The refusal vocabulary is unchanged.** Both refusals use
`ApplicationRefusal.REPORT_EVIDENCE_REFUSED`, whose own documentation is "the
ledger's own account no longer holds: a verification that stopped being true
when the source moved". No new member is needed: the repair the member names —
repair the record and the source behind it, not the document — is exactly the
repair here, and a new reason would duplicate that sentence with a longer
spelling.

## What changed

- `src/labcairn/evidence/gate.py` — `_the_source_still_supports(record,
  index)` and its call from `_judge`; the module docstring's two new sections
  (every citable record is asked about its source; the ledger is one account
  of the source, the file is the source).
- `src/labcairn/application/reports.py` — `_refuse_moved_material(context, *,
  document, sources)`, called at step 5a of `render_report` before the gate;
  the module docstring's order description and the two new sections; the
  `content_hash` import (the approval machinery's own chunked hasher, the same
  primitive `sources_intact` uses).
- `tests/test_evidence_gate.py` — three new unit witnesses (below); the import
  of `load_record`; the nineteen existing tests untouched.
- `tests/test_report_evidence_gate.py` — two new end-to-end witnesses through
  the console script; the four existing tests untouched.
- `docs/acceptance/LC-P4-PILOT-attested-source-drift-2026-11-28.md` — this
  record.

No file outside the list above was changed. `src/labcairn/reports/manifest.py`
and `src/labcairn/analysis/manifest.py` were in this window's ownership and
were read, but needed no change: the manifest already names a source link per
cited source with the hash the claim was read from, and the file comparison
belongs where the workspace is, not in the manifest builder.

## The witnesses, and what would make each red

- `test_an_attested_record_is_asked_about_its_source_with_no_c1_in_its_log`
  (unit, whole-task door) asserts the record's log holds C4 alone, the gate
  passes while the ledger is unchanged, and refuses — one `drift` finding
  naming the absent C1 — after the ledger's hash moves. Red if the gate stops
  asking a C1-less citable record about its source.
- `test_the_subset_door_asks_an_attested_record_about_its_source_too` (unit,
  subset door) asserts the other door reaches the same verdict for the same
  record. Red if the rule is ever written at one call site instead of
  `_judge`.
- `test_a_non_citable_record_is_not_asked_about_its_source_twice` (unit)
  pins the scope: an extracted record over a moved source yields the `status`
  finding alone, not a second finding about one record. Red if the source
  question is broadened past the citable states by accident.
- `test_an_attested_claim_over_a_moved_file_is_refused_before_anything_is_written`
  (e2e, the probe's exact shape: the quoted cell `1` does not move, the other
  cell becomes `9`) asserts exit `EXIT_REFUSED` (3), reason
  `report_evidence_refused`, the source id and `has moved` in the message,
  and **no artefact and no report file** left behind. Red if the render stops
  hashing the cited file.
- `test_an_attested_claim_is_refused_after_the_moved_file_is_ingested_again`
  (e2e) re-ingests the moved file, so the file and the ledger agree and the
  report's link passes; the gate then refuses because the record's binding is
  the old bytes, and the message names the record, `drift` and the absent C1.
  Red if the gate stops asking the source.

**Mutation checks, run in this worktree (2026-11-28):**

1. Delete the `findings.extend(_the_source_still_supports(record, index))`
   line from `_judge`: both unit witnesses fail, and the re-ingest e2e
   witness fails. Measured: `2 failed, 20 deselected` for the unit pair and
   `1 failed, 5 deselected` for the e2e.
2. Insert an early `return` at the top of `_refuse_moved_material` so the file
   is never asked: the moved-file e2e witness fails. Measured: `1 failed, 5
   deselected`.

Both mutations were reverted; `git diff` holds no mutation text.

## Measurements

- The two focused files at the base revision, before the change: **23
  passed** in 46.54 s.
- The same two files with the change and the five new witnesses, measured
  again after the final format pass on this tree: **28 passed** in 70.49 s
  (73.21 s on the run before the format-only edit).
- The wider report path — `tests/test_application_layer.py`,
  `tests/test_application_evidence.py`,
  `tests/test_analysis_report_checks.py`, `tests/test_quickstart_commands.py`,
  `tests/test_cli_evidence_writer.py`, `tests/test_cli_layer_models.py`,
  `tests/test_identifier_records.py`: **227 passed** in 289.91 s.
- `ruff check`, `ruff format --check` and `mypy --strict` over the two changed
  modules and the two changed test files: clean.
- The review's own probe, re-run against this worktree with
  `PYTHONPATH` pointing at it: `task report` now exits **3**, with the
  refusal message naming the source, the ledger's hash and the file's hash —
  the same script and the same synthetic material as the 2026-11-27
  measurement, where it exited 0 and wrote a `current` receipt.

## What was not measured, and what it would take

- **No CI run and no merge.** The numbers above are this machine's, not a
  runner's; the shard costs and the seventeen required checks are untouched by
  this record and belong to the integrating session's run.
- **The cost of hashing every cited source at render time was not measured on
  large material.** The read is one pass in 1 MiB chunks (the approval
  machinery's `content_hash`), and it happens once per cited source per
  render; a hundred-megabyte PDF would cost one such pass. Measured: nothing
  beyond the test-size files (10–20 bytes of CSV and one small Markdown
  file).
- **The API surface was run separately** (`tests/test_api.py`): **103 passed,
  1 skipped** in 87.45 s (the skip is `POSIX permission bits`, unrelated to
  this change). It reaches the report through `render_report`, as the CLI
  does. The moved-file refusal itself is witnessed through the CLI only,
  because both surfaces call the one operation and neither has a code path of
  its own that compares hashes.
- **The `user_attested` path of the API was not driven through a moved
  file end-to-end.** The behaviour is inherited from `render_report`, which is
  the same function the CLI test drives; no API-specific code compares hashes.
- **A citable record whose log records a C1 that agrees with a present
  failure** (the defensive branch of `_the_source_still_supports`) is reasoned
  but not witnessed: the store's doors (`advance`, `attest`) refuse that state
  on the way in, so reaching it needs a direct SQL edit, and a witness built
  that way would test the test's own edit rather than the product.
- **The report's staleness for non-citable claims was not changed.** The file
  comparison is made for every source the receipt's chain names, but the gate
  still judges only the records the document states as established; a report
  whose only claims are `extracted` is refused for a moved file and is not
  judged per record. That is the scope the card set, and it is stated here
  rather than left to be inferred.