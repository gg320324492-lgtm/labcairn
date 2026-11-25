# LC-P4-PILOT — the desensitisation checklist, measured

**Ticket:** LC-P4-PILOT (pilot material, desensitisation gate)
**Date:** 2026-11-25
**Status:** `MEASURED — four items fail; the checklist's part D is not signed`

**What was measured.** The checklist
([`LC-P4-PILOT-desensitisation-checklist.md`](../plans/LC-P4-PILOT-desensitisation-checklist.md))
is written for a person to work through, and every reading in it is a number
somebody has to type. This record holds the readings of the registered copy
against the original it was derived from, as
[`scripts/pilot_desensitisation_check.py`](../../scripts/pilot_desensitisation_check.py)
computed them.

**The two documents.** The copy is the one registered in
[`docs/pilot/registrations/pilot-paper-001.json`](../pilot/registrations/pilot-paper-001.json):
sha256 `42eefb065b82c833b213e6c0676b48e5b70417dab7634e9f89d8191aa4162a25`,
stored under the authorised root at
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-001.docx`. The original is
the advisor's copy under `advisor-sample/`, sha256
`a7a38132cf35d3632c4cb8aacba910994e9ad7e8b27413761260ade2d6502278`.

Neither document's text is in this record. What is here is counts,
booleans and digests.

## The readings

| Item | Verdict | What the tool read |
| --- | --- | --- |
| A-1 Author names | **fail** | the `Author` and `Last Modified By` properties are non-empty and are the original's |
| A-2 Affiliations and addresses | undecided | no address-shaped string in either document; the affiliation sentences are read by a person |
| A-3 Project and funding identifiers | undecided | no project-number-shaped pattern in either document; a pattern search is a search, not a verdict |
| A-4 Table and figure numbering | undecided | 155 paragraphs in both documents; the numbering's continuity is read by a person |
| A-5 Headers and footers | pass | the copy carries no header or footer part |
| A-6 Contact and identity metadata | **fail** | two built-in properties are non-empty and unchanged from the original; four custom properties are the original's; two revision author fields are not role labels |
| A-7 Embedded identifiers | pass | the file's name carries the pilot's material id; an embedded image's own metadata is the tooling's work |
| B-1 Advisor annotations | pass | zero comments in both documents |
| B-2 Revision marks | **fail** | the original carries 96 insertions and 17 deletions; the copy carries none of either |
| B-3 Heading outline | pass | the two visible texts are identical, so the headings are identical |
| B-4 Revision positions | undecided | the copy carries no inserted or deleted text to place |
| C-1 Comment text is readable | pass | there are no comments to read |
| C-2 Markup authors are role labels | **fail** | two revision author fields are not role labels |
| C-3 Revision text is readable | undecided | the copy carries no inserted or deleted text to read |
| C-4 Comment anchors are intact | pass | there are no comments to anchor |
| D-1 … D-5 | pass | the registration record's five fields match the copy in hand |
| D-6 The checklist result | undecided | the result is empty; the owner's signature is what is missing |

**Four items fail: A-1, A-6, B-2 and C-2.** Six are the owner's to read.

## What the failures are, in fact

**The copy's visible text is the original's, character for character.**
22,442 characters over 155 paragraphs, and not one paragraph differs in
position. The one thing that separates the two documents is that the
original's revisions were accepted: the original carries 96 insertions and
17 deletions (and 85 format changes), and the copy carries none of the
insertions or the deletions, and all 85 of the format changes.

**The identity was not cleared.** The `Author` and `Last Modified By`
properties are non-empty and are the original's, byte for byte. The four
custom properties are the original's. The two revision author fields are
still the original's names and are not role labels.

**So the desensitisation that was done removed the revision trail and
nothing else.** A copy that reads as the original, carries the original's
identity properties and carries no revision trail is not a desensitised
copy of a paper with tracked changes; it is the paper with its tracked
changes accepted.

## The gate is shut

The tool's `--require-signed` mode fails while item D-6 carries no
signature, and the checklist says the same thing in its own words: *until
the owner has signed that result, the import step must not run and no copy
enters the pilot.* The registration record exists, the copy is registered,
and the result that would let the pilot import it is empty.

## What the owner has to decide

Three ways forward, and the choice is the owner's:

1. **Sign the result with the four failures recorded.** The checklist's
   result carries a per-item pass/fail, so a signed result may say `fail`
   on A-1, A-6, B-2 and C-2. The checklist's own rule — *the check is
   repeated until A-1…A-7 all pass on the same copy* — would then be
   breached, and the import step stays shut.
2. **Redo the desensitisation.** The copy needs the two identity properties
   blanked, the custom properties cleared, the two revision author fields
   replaced by role labels, and the 96 insertions and 17 deletions
   restored. The tool measures all four; a redone copy is measurable
   against the same original.
3. **Register a different copy.** The registration is one record per copy
   and the tool reads the copy's own digest, so another copy is another
   record and another measurement.

## How the reading was taken

```
python scripts/pilot_desensitisation_check.py \
    --copy <the copy under the authorised root> \
    --original <the advisor's copy under advisor-sample/> \
    --outline <the heading outline exported from the copy> \
    --material-id pilot-paper-001 \
    --registration docs/pilot/registrations/pilot-paper-001.json
```

The tool's own witnesses are in
[`tests/test_pilot_desensitisation_check.py`](../../tests/test_pilot_desensitisation_check.py):
fourteen tests, each of which was checked to go red when the property it
watches is broken and to stay green when the script is restored.
