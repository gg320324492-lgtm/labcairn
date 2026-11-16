# LC-P3-02 - real-sample half-loop (2026-11-10)

**Date:** 2026-11-10. **Branch:** `claude/lc-p302-real-half-resume-20261110`. **Base head:** `47a6d8d98f44c215599a9672734326d504fd3ce7`.
**Type:** dated machine-side evidence record for section 5.9 and the section 14 item 4 real-material half.
**Status:** COMPLETE.

## Final status sentence

**real-sample loop: 42/42 arms measured; complete = true; report_sha256 = a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638; human dual-host reopen: 16/16 PASS on 2026-11-16/17.**

This is the exact status sentence the completion report quotes. It names the 42-arm machine loop and now names the completed human dual-host reopen half; the two halves are distinct measurements. **Read with the dated update in [Open half](#open-half) below:** the eight WPS rows were measured `PASS` on 2026-11-16 and the eight Word 2019 rows on 2026-11-16/17, all with unchanged hashes.

## Branch roles

- branch carrying this work and its checkpoints: `claude/lc-p302-real-half-resume-20261110`
- branch the task was originated from: `claude/compassionate-torvalds-5c5fee` (head `92ee1d0c19571ae901471813d9afd1af1a060913`)

the originated window wrote no commits; the measured half-loop, its dated record and its batch checkpoints live only on this branch. Both branches are named here so neither side is dropped at review-merge time.

## What is real here, and what is not

The sample is the owner-picked advisor-annotated manuscript, called here only by role. Its live SHA-256 and byte size were re-measured before any arm ran:

- sample role: `real-advisor-sample`
- sample SHA-256: `9154e56c5fe47da151fdb636b3cc4f8170965a8ccdbca94f292390254607652d`
- sample bytes: 4443105
- plan digest: `19ff69ef5051cc8dbd06df50f120840d33992655c4a9b52ebeaf233c0eeb71e2`

The proposals are deterministic structural constructions behind the provider gate. No real-model call was made; that belongs to LC-P3-06. No human host was launched: the two-host reopen checklist remains the owner's half and is recorded as `PENDING-HUMAN` outside the tree.

## Import

- carried structure classes: `body-text, comment-part, comments, equations, images, media, tables, tracked-revisions`
- blocked structure classes: `(none)`
- revisions: 400 (`{"del": 119, "ins": 270, "moveFrom": 3, "moveTo": 8}`)
- revisions with author/date/paragraph: 400/400/400
- comments: 4, anchored: 4 (`{"position": 1, "resolved": 3}`)
- paragraphs: 202 (baseline: 202)
- accepted text SHA-256: `c7d085e6036e36b70e827eee941d8cc33340234827a3ec0da02b76df7acfafae`
- rejected text SHA-256: `20d55f7bfdac403b75a942f8abf111e8de5e9e476f9cb067b3e3e330e0865137`
- reader problems: `{"docx_comment_position_anchor": 1, "docx_nested_revision": 1}`

## Locate

- paragraphs: 202
- unique plain runs: 2201
- body candidates: 2127
- revision paragraphs / targets: 46 / 600
- comment paragraphs / targets: 4 / 20
- table paragraphs / targets: 54 / 74
- same-paragraph duplicates: 503
- plain runs inside equations: 0
- plain runs inside images: 0
- first equation paragraph: 91
- first drawing paragraph: 81

R05 and R06 aim at whole paragraphs, not at one of their runs. A separate pre-loop probe found one plain run outside the first equation structure; aiming at that run would have measured a body-text edit instead of the equation class. The paragraph-level aim is unlocatable by design, so both proposals refuse. Zero plain runs inside equations and zero inside images are themselves results, not missing rows.

## Cost and batching

The single-arm budget is taken from the measured cost probe, not guessed:

| step | measured seconds |
|---|---:|
| refused arm | 0.6 |
| produced arm | 861.0 |
| produced-arm reservation | 900.0 |
| refused-arm reservation | 30.0 |
| one batch budget | 1800.0 |

The produced figure is 36.34 s of region comparison plus 409.50 s and 413.97 s of per-part class spans, with the reader and class table. `arms.jsonl` is an append-only ledger outside the tree; every batch skips completed arms, writes one row and one incremental statistic per arm, and never clears the ledger. A crash is a completed arm with a named exception class, never a blank row.

## Batch ledger

| batch | arms | completed after | produced | refused | errors | elapsed s | exit code | status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `smoke-001` | 28 | 28/42 | 0 | 28 | 0 | 23.92 | NOT_MEASURED | partial |
| `batch-002` | 2 | 30/42 | 2 | 0 | 0 | 1614.81 | 0 | partial |
| `batch-003` | 3 | 33/42 | 3 | 0 | 0 | 1604.67 | 0 | partial |
| `batch-004` | 1 | 34/42 | 1 | 0 | 0 | 1124.89 | 0 | partial |
| `batch-005` | 1 | 35/42 | 1 | 0 | 0 | 966.34 | 0 | partial |
| `batch-006` | 2 | 37/42 | 2 | 0 | 0 | 1891.47 | 0 | partial |
| `batch-007` | 1 | 38/42 | 1 | 0 | 0 | 1275.67 | 0 | partial |
| `batch-008` | 1 | 39/42 | 1 | 0 | 0 | 1138.27 | 0 | partial |
| `batch-009` | 1 | 40/42 | 1 | 0 | 0 | 1319.88 | 0 | partial |
| `batch-010` | 1 | 41/42 | 1 | 0 | 0 | 1198.45 | 0 | partial |
| `batch-011` | 1 | 42/42 | 1 | 0 | 0 | 1062.19 | 0 | complete |

Each batch's exit code is read back from a file, and the file it came from is printed beside it. Where no exit code was recorded and the batch log carries no exit-status line, the entry says so: a batch's completion is then evidenced by its summary row and its arm rows, not by a remembered number.

| batch | exit code | source |
|---|---:|---|
| `smoke-001` | NOT_MEASURED | no recorded exit code and no exit line in the batch log; the batch's completion is evidenced by its summary row and its arm rows, not by an exit code |
| `batch-002` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-002.txt |
| `batch-003` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-003.txt |
| `batch-004` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-004.txt |
| `batch-005` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-005.txt |
| `batch-006` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-006.txt |
| `batch-007` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-007.txt |
| `batch-008` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-008.txt |
| `batch-009` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-009.txt |
| `batch-010` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-010.txt |
| `batch-011` | 0 | read from E:\labcairn-local\tmp\p302-real-half-resume\logs\batch-011.txt |

## 42-arm results

- arms measured: 42/42
- produced: 14
- refused: 28
- errors: 0
- expectation mismatches: 0
- artifacts named in the ledger: 8
- artifact files in the output directory: 8
- the two inventories agree: True
- dual-host reopen rows: 16 (`PENDING-HUMAN`; `NOT_MEASURED` until the finalizer writes them)
- external report SHA-256: `a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`

## Ledger binding

F-3. The record is bound to the append-only files it summarises, by digest:

| ledger file | lines | bytes | sha256 | parses |
|---|---:|---:|---|---:|
| `arms.jsonl` | 42 | 134782 | `7e1f9dec3658a6214bf347a1b7f413e6a1343b56d3fac1b5e0fa9cffc8549776` | 42 |
| `arm-stats.jsonl` | 42 | 30880 | `ad1e1791a3f3f0822666e861344515f6c94d788c82b9d5b7b9b85baf893537a7` | 42 |
| `batch-summary.jsonl` | 11 | 5036 | `8d7508cb7ffd31ea5e779195aee9071eadc9693c4b5f37e2b4d9fa50f8cae4aa` | 11 |
| `batch-exits.jsonl` | 0 | 0 | `-` | 0 |

the dated record and its JSON summary are derived from these files at the digests printed here; a reader can recompute each sha256 and confirm the record was written against this ledger rather than against a remembered total

Each line count is the count of non-blank rows, and `parses` is the count of rows that decode as JSON objects: a file whose last row was cut off would show a smaller `parses` than `lines`, and the record would say so here.

### Refusal reason distribution

| value | count |
|---|---:|
| `date_not_iso_8601` | 4 |
| `edit_changes_nothing` | 4 |
| `paragraph_absent` | 4 |
| `paragraph_holds_no_plain_run` | 4 |
| `part_outside_support_matrix` | 4 |
| `text_ambiguous` | 4 |
| `text_not_located` | 4 |

### Structure-class result distribution

| value | count |
|---|---:|
| `body-text:produced` | 8 |
| `body-text:refused` | 16 |
| `comment-part:refused` | 4 |
| `comments:produced` | 2 |
| `equations:refused` | 4 |
| `images:refused` | 4 |
| `tables:produced` | 2 |
| `tracked-revisions:produced` | 2 |

| arm | structure | expect | observed | refusal reason | elapsed s | regions | non-identical regions |
|---|---|---|---|---|---:|---:|---:|
| `R05|library|marked` | `equations` | refused | refused | `text_not_located` | 0.73 | 0 | 0 |
| `R05|rebuild|marked` | `equations` | refused | refused | `text_not_located` | 0.84 | 0 | 0 |
| `R05|reserialize|marked` | `equations` | refused | refused | `text_not_located` | 0.76 | 0 | 0 |
| `R05|surgical|marked` | `equations` | refused | refused | `text_not_located` | 0.73 | 0 | 0 |
| `R06|library|marked` | `images` | refused | refused | `paragraph_holds_no_plain_run` | 0.74 | 0 | 0 |
| `R06|rebuild|marked` | `images` | refused | refused | `paragraph_holds_no_plain_run` | 0.74 | 0 | 0 |
| `R06|reserialize|marked` | `images` | refused | refused | `paragraph_holds_no_plain_run` | 0.77 | 0 | 0 |
| `R06|surgical|marked` | `images` | refused | refused | `paragraph_holds_no_plain_run` | 0.83 | 0 | 0 |
| `R07|library|marked` | `comment-part` | refused | refused | `part_outside_support_matrix` | 0.64 | 0 | 0 |
| `R07|rebuild|marked` | `comment-part` | refused | refused | `part_outside_support_matrix` | 0.66 | 0 | 0 |
| `R07|reserialize|marked` | `comment-part` | refused | refused | `part_outside_support_matrix` | 0.67 | 0 | 0 |
| `R07|surgical|marked` | `comment-part` | refused | refused | `part_outside_support_matrix` | 0.67 | 0 | 0 |
| `R08|library|marked` | `body-text` | refused | refused | `text_ambiguous` | 1.55 | 0 | 0 |
| `R08|rebuild|marked` | `body-text` | refused | refused | `text_ambiguous` | 1.5 | 0 | 0 |
| `R08|reserialize|marked` | `body-text` | refused | refused | `text_ambiguous` | 1.5 | 0 | 0 |
| `R08|surgical|marked` | `body-text` | refused | refused | `text_ambiguous` | 1.59 | 0 | 0 |
| `R09|library|marked` | `body-text` | refused | refused | `edit_changes_nothing` | 0.7 | 0 | 0 |
| `R09|rebuild|marked` | `body-text` | refused | refused | `edit_changes_nothing` | 0.67 | 0 | 0 |
| `R09|reserialize|marked` | `body-text` | refused | refused | `edit_changes_nothing` | 0.67 | 0 | 0 |
| `R09|surgical|marked` | `body-text` | refused | refused | `edit_changes_nothing` | 0.64 | 0 | 0 |
| `R10|library|marked` | `body-text` | refused | refused | `paragraph_absent` | 0.8 | 0 | 0 |
| `R10|rebuild|marked` | `body-text` | refused | refused | `paragraph_absent` | 0.75 | 0 | 0 |
| `R10|reserialize|marked` | `body-text` | refused | refused | `paragraph_absent` | 0.74 | 0 | 0 |
| `R10|surgical|marked` | `body-text` | refused | refused | `paragraph_absent` | 0.72 | 0 | 0 |
| `R11|library|marked` | `body-text` | refused | refused | `date_not_iso_8601` | 0.67 | 0 | 0 |
| `R11|rebuild|marked` | `body-text` | refused | refused | `date_not_iso_8601` | 0.67 | 0 | 0 |
| `R11|reserialize|marked` | `body-text` | refused | refused | `date_not_iso_8601` | 0.69 | 0 | 0 |
| `R11|surgical|marked` | `body-text` | refused | refused | `date_not_iso_8601` | 0.91 | 0 | 0 |
| `R01|library|clean` | `body-text` | produced | produced | `-` | 801.23 | 162 | 0 |
| `R01|library|marked` | `body-text` | produced | produced | `-` | 813.5 | 162 | 0 |
| `R01|rebuild|clean` | `body-text` | produced | produced | `-` | 375.64 | 218 | 218 |
| `R01|rebuild|marked` | `body-text` | produced | produced | `-` | 379.76 | 218 | 218 |
| `R01|reserialize|clean` | `body-text` | produced | produced | `-` | 849.17 | 162 | 162 |
| `R01|reserialize|marked` | `body-text` | produced | produced | `-` | 1124.8 | 162 | 162 |
| `R01|surgical|clean` | `body-text` | produced | produced | `-` | 966.02 | 162 | 0 |
| `R01|surgical|marked` | `body-text` | produced | produced | `-` | 893.59 | 162 | 0 |
| `R02|surgical|clean` | `tracked-revisions` | produced | produced | `-` | 997.11 | 162 | 0 |
| `R02|surgical|marked` | `tracked-revisions` | produced | produced | `-` | 1275.42 | 162 | 0 |
| `R03|surgical|clean` | `comments` | produced | produced | `-` | 1137.58 | 162 | 0 |
| `R03|surgical|marked` | `comments` | produced | produced | `-` | 1319.36 | 162 | 0 |
| `R04|surgical|clean` | `tables` | produced | produced | `-` | 1198.23 | 162 | 0 |
| `R04|surgical|marked` | `tables` | produced | produced | `-` | 1061.92 | 162 | 0 |

## Corrections applied after the independent audit

An independent critic read this record against the ledger while the loop was still running and found four defects in the record's generator. Each was reproduced from the ledger before being fixed, and each is described here rather than fixed silently, because the earlier checkpoint commits were rendered by the generator that had them:

| id | the defect | what the measurement showed | what the record now does |
|---|---|---|---|
| F-1 | the partial record printed `artifacts: 0` while the ledger already named artifact files | `arm-stats.jsonl` already named artifact files and the output directory held the same count | the count is read from the ledger and from the output directory and both are printed; an unmeasured final quantity is printed as the sentinel `NOT_MEASURED` instead of a zero |
| F-2 | a partial record used the headings "Final state sentence" and "completion report" | neither `report.json` nor `run-complete.json` existed at the time | only the completed render uses the final wording; a checkpoint says it is not final and says which files are missing |
| F-3 | the record was not bound to the ledger it summarised | the ledger files' bytes had digests the record never printed | a binding table prints each ledger file's line count, byte size, sha256 and how many lines parse as JSON rows |
| F-5 | the shared note asserted "finished with exit code 0", and the orchestrator's ledger reader let a truncated row escape as a bare traceback while the driver's reader raised a `STOP:` message | `batch-summary.jsonl` carries no exit-code field; the two readers described the same file differently | every batch's exit code is read from `batch-exits.jsonl` or from its batch log and printed with its source; the one batch whose exit code was never recorded is reported as `NOT_MEASURED`; both readers now reject a truncated row the same way |

The append-only ledger was not rewritten: no arm row, statistic or batch summary was edited, deleted or back-filled to match the corrected record. The correction is visible in this section and in the commit that re-renders the record from the same ledger bytes.


Every refusal is a completed arm with a named reason and an unchanged original digest. No refusal was retried until it produced, dropped from the ledger, or converted into a blank row. Where an option could not produce bytes, that limitation is counted as its own result. This is the section 5.10 discipline: a row left blank is the same defect as a witness deleted in a merge.

## Material boundary

The sample, outputs, artifacts, full arm rows, fidelity files and full report all stay outside the repository. This tree carries the dated record and a machine-readable summary only: SHA-256 digests, byte sizes, counts, structure classes, refusal reasons, elapsed seconds, batch status and the external report digest. No sample path, sample text, reviewer name or reviewer text enters a committed file. Runtime temp directories, including the pytest basetemp, are outside the repository on the same isolated root.

## Machine-checkable summary

The companion JSON file is derived from the same append-only ledger. Its `complete`, `arm_count`, `completed_arms`, `produced`, `refused`, `refusal_reasons_seen` and `report_sha256` fields are the values printed above; a witness can parse the JSON and check that the prose prints the same values rather than merely claiming a status word.

## Open half

The dual-host reopen rows were **NOT RUN** at the record's date. No operator
launched WPS Office or Microsoft Office 2010 then, and no host result is
claimed by this record.

**Measured 2026-11-16 — the WPS half has run.** A person opened each of the
eight `-primary` artifacts in WPS Office 12.1.0.29690 twice (first open,
then reopen; closed without saving between passes), screenshotted both
passes, and judged the eight structure tokens from each pass separately.
After the cycle each file was re-hashed: **all 8 measured
`sha256_after` values equal their `sha256_before` values, byte sizes
included, `hash_changed = no`**, and every row is `PASS` in
`reopen-rows.csv` (operator `LabCarin`). Measured values:

| row | bytes | sha256 (unchanged across the cycle) |
|---|---:|---|
| R01 clean | 4,438,788 | `2843198175b1…` |
| R01 marked | 4,438,835 | `72f0472e86c7…` |
| R02 clean | 4,438,795 | `ec63960564e3…` |
| R02 marked | 4,438,859 | `ba8381f0099a…` |
| R03 clean | 4,438,801 | `bb63cef41541…` |
| R03 marked | 4,438,846 | `9e9e9d3d7154…` |
| R04 clean | 4,438,807 | `28e0e502caaa…` |
| R04 marked | 4,438,860 | `cd1e7a357c80…` |

**Measured 2026-11-16/17 — the Word `-reference` half has run.** The machine
used for the WPS half carried no Word 2010; re-measured live on 2026-11-16 it
carries **Office Home & Student 2019, WINWORD `16.0.17932.21140`**, and the
owner ruled that **Word 2019 is the compatibility reference** for these rows
(recorded in `LC-P3-00-board-opening-decisions.md` §5). A person opened each
of the eight `-reference` artifacts in Word 2019 twice (first open, then
reopen; closed without saving between passes), screenshotted both passes,
and judged the eight structure tokens from each pass separately. After the
cycle each file was re-hashed: **all 8 measured `sha256_after` values equal
their `sha256_before` values, byte sizes included, `hash_changed = no`**,
and every row is `PASS` in `reopen-rows.csv` (operator `LabCarin`). Measured
values:

| row | bytes | sha256 (unchanged across the cycle) |
|---|---:|---|
| R01 clean | 4,438,788 | `2843198175b1…` |
| R01 marked | 4,438,835 | `72f0472e86c7…` |
| R02 clean | 4,438,795 | `ec63960564e3…` |
| R02 marked | 4,438,859 | `ba8381f0099a…` |
| R03 clean | 4,438,801 | `bb63cef41541…` |
| R03 marked | 4,438,846 | `9e9e9d3d7154…` |
| R04 clean | 4,438,807 | `28e0e502caaa…` |
| R04 marked | 4,438,860 | `cd1e7a357c80…` |

The two halves were decided separately. No WPS `PASS` was copied, averaged
or extrapolated into a Word `PASS`; the reference half was decided by a
person on the reference host. After the final write-back, all **16/16 rows
are `PASS`**, every row has all thirteen human cells filled, and the ledger
SHA-256 is `2d8b133b5c077e0808d8d2c9235df1ea75557d397741ebd2264aa287aa5c7e19`
(27,107 bytes, 16 data rows).

Evidence lives outside the tree, as the SOP requires: the ledger with its
measured cells, 32 first-open/reopen screenshots, five auxiliary review/last-page
screenshots captured during observation, and a per-row snapshot taken before
each write under
`E:/labcairn-local/phase3-g1-evidence/LC-P3-02-real-half-2026-11-10/`.
