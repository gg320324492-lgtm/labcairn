# LC-P3-02 — DOCX structure support matrix (2026-11-08)

**Date:** 2026-11-08. **Head:** `bbed26cf0c0468c0bc625542bd94ac9f0bd948ad`.
**Type:** dated record for the support table in
`docs/plans/PHASE_3-work-orders.md` §5. The class list is
`labcairn.editing.survey.StructureClass`; the verdicts are
`labcairn.editing.survey.SUPPORT`, re-derived by
`tests/test_docx_edit_records.py`.

The corpus is **synthetic**: 31 samples, 11 the seam writes and 20 it refuses.
This dated matrix held the real advisor sample open on 2026-11-08; the later
dated [`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md)
measured the sample's 42-arm machine half. No host result is claimed here, and
the machine loop is not a human dual-host reopen observation.

**Rider, 2026-11-16/17:** the human dual-host reopen half is complete —
all 16 rows of the real-sample reopen ledger are `PASS` (eight WPS primary
rows on 2026-11-16, eight Word 2019 `16.0.17932.21140` reference rows on
2026-11-16/17); see `docs/handoff/CURRENT.md`'s 2026-11-17 entry and the
external ledger under
`E:/labcairn-local/phase3-g1-evidence/LC-P3-02-real-half-2026-11-10/`.

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
| `part_outside_support_matrix` | the change is aimed at a part the seam does not rewrite | `17-refuse-edit-aimed-at-the-comment-part`, `12c-refuse-edit-aimed-at-a-media-part` |
| `package_outside_support_matrix` | the package carries a part class never rewritten here | `14-refuse-package-carrying-macros`, `15-refuse-package-carrying-an-embedded-object`, `16-refuse-package-carrying-custom-xml`, `16b-refuse-package-carrying-a-digital-signature` |
| `edit_changes_nothing` | there is no change to write | `21-refuse-unchanged-edit` |
| `package_unreadable` | the bytes are not a package the seam can plan against | `25-refuse-a-package-that-is-not-a-package`, `26-refuse-a-package-with-no-document-part` |
| `paragraph_absent` | the address names no paragraph | `22-refuse-paragraph-number-that-is-not-there` |
| `paragraph_holds_no_plain_run` | the paragraph holds nothing a run splice can replace | `24-refuse-a-paragraph-with-no-plain-run` |
| `text_not_located` | the passage is not the whole text of any one run | `19-refuse-edit-cutting-a-run-in-two`, `20-refuse-absent-text` |
| `text_ambiguous` | the passage occurs more than once, so the seam would be guessing | `18-refuse-ambiguous-occurrence` |
| `target_inside_unsupported_structure` | the passage sits inside a class the seam may carry but not write | `10-refuse-edit-inside-an-equation`, `11-refuse-edit-inside-a-text-box`, `12-refuse-edit-of-a-fields-cached-answer`, `12b-refuse-edit-of-a-vml-figure-caption`, `13-refuse-edit-inside-a-content-control` |

## The human half

The WPS Office and Microsoft Office 2019 (see LC-P3-00 §5's 2026-11-16
re-measurement) open/reopen checklist is **NOT RUN**
in this 2026-11-08 record. No operator launched either host at that time, and
no host result is claimed here. The form and the evidence directory are in
`G1-ENV-EVIDENCE-PREP-2026-11-08.md`; the rows were held open pending the
owner's execution. **Read 2026-11-10:** the later 44-row checklist has 4/44
completed rows, remaining WPS rows are observed by screenshot, and Word 2010
rows stay `PENDING-HUMAN` — the host is installed (`C:\Program Files
(x86)\office2010\Office14\WINWORD.EXE`, file version 14.0.7252.5000, the
version the ledger names, verified 2026-11-13), so its rows are open to be
observed with the same mode. **Read 2026-11-13** in
[`PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md)'s open-gaps table.
The 42-arm machine half is recorded in
[`LC-P3-02-real-sample-2026-11-10.md`](LC-P3-02-real-sample-2026-11-10.md);
it does not close the human half. **Read 2026-11-17:** the separate 16-row
real-sample human ledger is now **16/16 PASS** — the eight WPS primary rows
on 2026-11-16 and the eight Word 2019 reference rows on 2026-11-16/17, all
re-hashed unchanged — in the same dated record; this matrix's fifth-version
44-row checklist remains an owner obligation. **Read 2026-11-17
(completion):** the fifth-version 44-row checklist itself is now complete —
**44/44 rows** (31 `PASS`, 11 `PRESENCE-LOSS`, 2 `REFUSAL-RECORDED`), every
file re-hashed unchanged, validator `PASS` — recorded in
[`LC-P3-02-fifth-version-44-rows-2026-11-17.md`](LC-P3-02-fifth-version-44-rows-2026-11-17.md)
with external ledger SHA-256 `b24f22e5…`. The Word reference rows were
measured on Word 2019 `16.0.17932.21140` (the host re-measured 2026-11-16 —
PR #184; Word 2010 is not installed on the machine), and the two
2026-11-10 PASS rows keep their historical Word 2010 `14.0.7252.5000`
identity by owner ruling, preserved byte-for-byte. The "4/44" and
"Word 2010 rows stay `PENDING-HUMAN`" readings above are superseded by
this one.

**Read 2026-11-17 (one row is a host limitation, not a defect).** One of the
eleven `PRESENCE-LOSS` rows is not a defect in the documents this matrix
covers. `06b-hyperlink-target-inside-the-wrap-surgical-marked` shows
`hyperlinks:no` on WPS Office `12.1.0.29690` while the Word 2019 reference
row for the same artifact is `PASS`. The construction is
`w:hyperlink` **containing** `w:del` and `w:ins` — measured element by
element from the artifact's `word/document.xml`, and it is the schema-legal
direction: ECMA-376 Part 1 (5th ed.) `CT_Hyperlink` admits the edit-content
group, so revision runs inside a hyperlink are valid. The generator-side
alternatives were examined and each either breaks the property under test —
the edit must happen inside a surviving hyperlink wrap — or is schema-illegal,
so **no generator change is made**: this is a WPS rendering limitation, and
the WPS row stays `PRESENCE-LOSS` as observed, which is a statement about
what the host displayed, not a claim that the document is malformed. Recorded
as issue [#190](https://github.com/gg320324492-lgtm/labcairn/issues/190)
(labelled `wontfix`); the root-cause analysis is in the external report
`E:/labcairn-local/defect-rootcause-d234-20261117/REPORT.md` §1.
