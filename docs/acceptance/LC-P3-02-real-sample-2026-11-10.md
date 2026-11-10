# LC-P3-02 - real-sample half-loop (2026-11-10)

**Date:** 2026-11-10. **Branch:** `claude/lc-p302-real-half-resume-20261110`. **Base head:** `47a6d8d98f44c215599a9672734326d504fd3ce7`.
**Type:** dated machine-side evidence record for section 5.9 and the section 14 item 4 real-material half.
**Status:** IN PROGRESS.

## Final state sentence

**real-sample loop: IN PROGRESS - 37/42 arms measured; human dual-host reopen: NOT RUN - held open pending the owner.**

This is the exact status sentence the completion report quotes. It names the 42-arm machine loop and keeps the human dual-host reopen half open; the two halves are not the same claim.

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

| batch | arms | completed after | produced | refused | errors | elapsed s | status |
|---|---:|---:|---:|---:|---:|---:|---|
| `smoke-001` | 28 | 28/42 | 0 | 28 | 0 | 23.92 | partial |
| `batch-002` | 2 | 30/42 | 2 | 0 | 0 | 1614.81 | partial |
| `batch-003` | 3 | 33/42 | 3 | 0 | 0 | 1604.67 | partial |
| `batch-004` | 1 | 34/42 | 1 | 0 | 0 | 1124.89 | partial |
| `batch-005` | 1 | 35/42 | 1 | 0 | 0 | 966.34 | partial |
| `batch-006` | 2 | 37/42 | 2 | 0 | 0 | 1891.47 | partial |

## 42-arm results

- arms measured: 37/42
- produced: 9
- refused: 28
- errors: 0
- expectation mismatches: 0
- artifacts: 0
- dual-host reopen rows: 0 (`PENDING-HUMAN`)
- external report SHA-256: `not finalized`

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
| `equations:refused` | 4 |
| `images:refused` | 4 |
| `tracked-revisions:produced` | 1 |

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

## Refusal is a result

Every refusal is a completed arm with a named reason and an unchanged original digest. No refusal was retried until it produced, dropped from the ledger, or converted into a blank row. Where an option could not produce bytes, that limitation is counted as its own result. This is the section 5.10 discipline: a row left blank is the same defect as a witness deleted in a merge.

## Material boundary

The sample, outputs, artifacts, full arm rows, fidelity files and full report all stay outside the repository. This tree carries the dated record and a machine-readable summary only: SHA-256 digests, byte sizes, counts, structure classes, refusal reasons, elapsed seconds, batch status and the external report digest. No sample path, sample text, reviewer name or reviewer text enters a committed file. Runtime temp directories, including the pytest basetemp, are outside the repository on the same isolated root.

## Machine-checkable summary

The companion JSON file is derived from the same append-only ledger. Its `complete`, `arm_count`, `completed_arms`, `produced`, `refused`, `refusal_reasons_seen` and `report_sha256` fields are the values printed above; a witness can parse the JSON and check that the prose prints the same values rather than merely claiming a status word.

## Open half

The dual-host reopen rows are **NOT RUN**. No operator launched WPS Office or Microsoft Office 2010, and no host result is claimed here. The owner's human half stays open until a person performs it.
