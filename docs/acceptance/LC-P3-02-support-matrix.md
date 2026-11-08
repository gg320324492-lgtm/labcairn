# LC-P3-02 — DOCX structure support matrix (2026-11-08)

**Date:** 2026-11-08. **Head:** `9765527ba16c2bfdafc61d32ce78616d2aa2deb1`.
**Type:** dated record for the support table in
`docs/plans/PHASE_3-work-orders.md` §5. The class list is
`labcairn.editing.survey.StructureClass`; the verdicts are
`labcairn.editing.survey.SUPPORT`, re-derived by
`tests/test_docx_edit_records.py`.

The corpus is **synthetic**: 31 samples, 11 the seam writes and 20 it refuses.
The real advisor sample is held open for the owner; no host result is claimed
here.

## The matrix

Columns are structure class, what it is, whether the seam carries it, and
whether it writes into it.

| `body-text` | body text outside the edit target | carried | written into |
|---|---|---|---|
| `tracked-revisions` | tracked insertions and deletions | carried | written into |
| `comments` | comment anchors and replies | carried | written into |
| `tables` | table cells and rows | carried | written into |
| `equations` | Office Math equations | carried | refused |
| `images` | inline and anchored images | carried | refused |
| `text-boxes` | text boxes and VML shapes | carried | refused |
| `fields` | field codes and cached answers | carried | refused |
| `content-controls` | content controls | carried | refused |
| `hyperlinks` | hyperlinks and their relationships | carried | written into |
| `comment-part` | the comments part itself | carried | refused |
| `media` | media parts under `word/media/` | carried | refused |
| `vba` | macro parts | not carried | refused |
| `embedded-objects` | embedded OLE objects | not carried | refused |
| `custom-xml` | custom XML parts | not carried | refused |
| `signatures` | package signatures | not carried | refused |

## What the gate refuses, and with what words

Columns are the reason code, what it means, and the refusal sample that raises
it.

| `date_not_iso_8601` | the edit's own stamp is not the form the format declares | `23-refuse-a-date-that-is-not-a-date` |
|---|---|---|
| `part_outside_support_matrix` | the change is aimed at a part the seam does not rewrite | `17-refuse-edit-aimed-at-the-comment-part` |
| `package_outside_support_matrix` | the package carries a part class never rewritten here | `14-refuse-package-carrying-macros`, `15-refuse-package-carrying-an-embedded-object`, `16-refuse-package-carrying-custom-xml`, `16b-refuse-package-carrying-a-digital-signature` |
| `edit_changes_nothing` | there is no change to write | `21-refuse-unchanged-edit` |
| `package_unreadable` | the bytes are not a package the seam can plan against | `25-refuse-a-package-that-is-not-a-package`, `26-refuse-a-package-with-no-document-part` |
| `paragraph_absent` | the address names no paragraph | `22-refuse-paragraph-number-that-is-not-there` |
| `paragraph_holds_no_plain_run` | the paragraph holds nothing a run splice can replace | `24-refuse-a-paragraph-with-no-plain-run` |
| `text_not_located` | the passage is not the whole text of any one run | `19-refuse-edit-cutting-a-run-in-two`, `20-refuse-absent-text` |
| `text_ambiguous` | the passage occurs more than once, so the seam would be guessing | `18-refuse-ambiguous-occurrence` |
| `target_inside_unsupported_structure` | the passage sits inside a class the seam may carry but not write | `10-refuse-edit-inside-an-equation`, `11-refuse-edit-inside-a-text-box`, `12-refuse-edit-of-a-fields-cached-answer`, `12b-refuse-edit-of-a-vml-figure-caption`, `12c-refuse-edit-aimed-at-a-media-part`, `13-refuse-edit-inside-a-content-control` |

## The human half

The WPS Office and Microsoft Office 2010 open/reopen checklist is **NOT RUN**.
No operator launched either host, and no host result is claimed. The form and
the evidence directory are in `G1-ENV-EVIDENCE-PREP-2026-11-08.md`; the rows
are held open pending the owner's execution.
