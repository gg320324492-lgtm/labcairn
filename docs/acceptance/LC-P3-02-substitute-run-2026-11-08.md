# LC-P3-02 — substitute-set run record (2026-11-08)

**Date:** 2026-11-08. **Head:** `940cd7a6a738d287dfd6d819330cf767d6e90591`.
**Type:** dated machine-side run record for `LC-P3-02` §5.7–§5.10.

## What ran

31 samples, 11 the seam writes and 20 it refuses; 248 results over the four
options and two forms (`marked`, `clean`); 22 artifacts; 44 reopen checklist
rows. The run was local on the trial machine; no runner took these numbers.

Sample-input digests from the manifest bridge include
`63d24818b2a5529d870412349d27ed6b9b6520751a642ad37d6c721b5fcb8ca4`,
`4db47fb725a52e2cd83bc5b48a2b4f70ff5aec3fbc7539e7f389e8f10101280b` and
`6dd5b3eba9cafc1c8def5aa0b60063e3efcf53317f7ea5350908338d6d4cf8db`.
The longest visible path was 143 characters; the run stayed under the measured
259-character ceiling (`MAX_PATH` is 259; 260 is the first length the machine
refuses), and `LongPathsEnabled` is read from the registry in the host snapshot.

## The four options, counted

Columns are the option, produced and refused counts, identical class and region
rows, respelled rows, and the declaration, entry-order and marked-draft
results.

| surgical | 22 | 40 | 76 | 66 | 0 | yes | yes | yes |
|---|---|---|---|---|---|---|---|---|
| reserialize | 22 | 40 | 68 | 44 | 22 | no | yes | no |
| library | 22 | 40 | 68 | 66 | 0 | no | no | no |
| rebuild | 22 | 40 | 16 | 0 | 0 | no | no | no |

The surgical option left 66 of 66 region rows identical and kept declaration,
entry order and the marked draft's change; its one reopen problem is
`docx_nested_revision`. The other options changed or respelled rows, lost the
declaration or entry order, or (rebuild) lost 52 of 68 class rows and all
region rows.

## The open half

The human half is **NOT RUN**. No operator launched WPS Office 12.1.0.29690 or
Microsoft Office 2010, and no host result is claimed; the dual-host reopen
checklist is held open pending the owner. The real advisor sample is
**real-sample loop: NOT RUN — held open pending the owner's sample**. No ticket
verdict is claimed here.
