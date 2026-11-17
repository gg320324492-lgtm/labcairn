# LC-P3-02 — fifth-version 44-row dual-host reopen (2026-11-17)

**Date:** 2026-11-17. **Type:** dated external-ledger completion record for
section 4.9 of the Phase 3 work orders. No DOCX material, screenshot bytes,
personal reviewer text, or raw ledger is committed here; all of that stays
under `E:/labcairn-local/phase3-g1-evidence/LC-P3-02-fifth-fix-2026-11-09/`.

## Final status sentence

**44-row fifth-version checklist: 44/44 rows completed and format-validated;
31 PASS, 11 PRESENCE-LOSS, 2 REFUSAL-RECORDED; every row re-hashed unchanged;
validator PASS.**

This sentence reports observation completion and format validity. It does not
say all 44 host judgements are PASS, and it does not extrapolate a WPS result
into a Word result.

## Hosts and prior-state boundary

- WPS Office `12.1.0.29690`: 22 primary rows.
- Word reference rows: 20 rows on Microsoft Office 2019 `16.0.17932.21140`.
- Two grandfathered 2026-11-10 PASS reference rows retain their historical
  Word 2010 `14.0.7252.5000` identity by owner ruling; they were preserved
  byte-for-byte from the prior-state snapshot and were not re-run.
- The anchor `reopen-rows.csv` was never written. All new observations went
  into `reopen-rows-filled-2026-11-10.csv`.

## Ledger binding

| measured value | result |
|---|---|
| ledger SHA-256 | `b24f22e5a163bfb9d6663a8f049b0f9d11adda84bc33ef01166868e10a2354aa` |
| bytes | 47,156 |
| data rows | 44 |
| columns | 27 (12 machine, 13 human, verdict, notes) |
| ordered WPS/Word pairs | 22/22 |
| human cells | 44/44 complete |
| `sha256_before == sha256_after` | 44/44 |
| `byte_size_before == byte_size_after` | 44/44 |
| `hash_changed` | `no` in all 44 rows |
| prior-state preservation | 4/4 grandfathered rows unchanged |
| validator | `VALIDATOR RESULT: PASS`, format and boundaries only |

The validator's PASS does not certify that screenshots were truthfully read;
it certifies the ledger's format, host identities, ordered pairs, preservation
of prior rows, hash invariants, and legal verdict vocabulary.

## Verdict distribution

| verdict | rows | meaning |
|---|---:|---|
| `PASS` | 31 | all expected structure tokens were observed in both passes on that host |
| `PRESENCE-LOSS` | 11 | the row was observed, but an expected structure was not visible on that host |
| `REFUSAL-RECORDED` | 2 | Word refused the file on open; no content was observable |

By host: WPS 15 PASS / 7 PRESENCE-LOSS; Word 2019 14 PASS /
4 PRESENCE-LOSS / 2 REFUSAL-RECORDED; the two historical Word 2010 rows are
PASS and were preserved.

## Named findings

### Images and media parts

Four artifacts carry an inline `word/media/image1.png` that renders as a blank
area in both WPS and Word. Package inspection finds a 1×1 RGBA PNG whose IDAT
stream fails checksum validation and a 360000-EMU drawing extent. The affected
row pairs are:

- `05-image-and-relationship-surgical-clean` (primary + reference)
- `05-image-and-relationship-surgical-marked` (primary + reference)
- `07-everything-at-once-surgical-clean` (primary + reference)
- `07-everything-at-once-surgical-marked` (primary + reference)

These eight rows are recorded as `PRESENCE-LOSS` with `images:no` and
`media-parts:no`. The empty drawing object is not counted as a visible image.

### Wrapped hyperlink in marked revision

`06b-hyperlink-target-inside-the-wrap-surgical-marked` is recorded as
`PRESENCE-LOSS` on WPS with `hyperlinks:no`. The OOXML carries the link inside
nested insertion/deletion markup, but WPS did not display the inserted link
sentence. The Word 2019 reference row for the same artifact is PASS: Word
displayed the nested tracked revision and link sentence.

### Refusal records

`08-refusals-elsewhere-in-the-document-surgical-clean-reference` and
`...surgical-marked-reference` are recorded as `REFUSAL-RECORDED`. Word 2019
showed the same severe-open-error dialog on the first attempt and on one fresh
retry; no recovery was attempted, and the corresponding WPS primary rows carry
their own `PRESENCE-LOSS` observations. Both prompts were screenshotted.

### Fields, content controls, and text boxes

The `08-refusals-elsewhere-in-the-document-surgical-*` row pairs record
`content-controls:not-inspectable`, `fields:not-inspectable`, `images:no`, and
`text-boxes:no` where the host view gave no visible boundary or shading and the
package used a 1×1 anchored text box. They are `PRESENCE-LOSS`, not PASS.

## Evidence location

- Fillable ledger: `reopen-rows-filled-2026-11-10.csv`.
- Screenshots: `screenshots/` (first-open, reopen, and error evidence).
- Backups: per-row `.bak-before-*` files beside the ledger.
- Validator output: `checklist44-final-check-20261117/validator-final-44.txt`.
- All listed paths are under
  `E:/labcairn-local/phase3-g1-evidence/LC-P3-02-fifth-fix-2026-11-09/` or its
  adjacent audit folders, outside the repository.

No WPS observation was copied into a Word row. The two grandfathered Word
2010 rows remain historical snapshots.
