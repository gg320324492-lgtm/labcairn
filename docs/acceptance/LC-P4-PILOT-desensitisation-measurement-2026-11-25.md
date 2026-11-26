# LC-P4-PILOT — the desensitisation checklist, measured

**Ticket:** LC-P4-PILOT (pilot material, desensitisation gate)
**Date:** 2026-11-25
**Status:** `MEASURED AND SIGNED — the owner signed item D-6 on 2026-11-25`

**What was measured.** The checklist
([`LC-P4-PILOT-desensitisation-checklist.md`](../plans/LC-P4-PILOT-desensitisation-checklist.md))
is written for a person to work through, and every reading in it is a number
somebody has to type. This record holds the readings of the registered copy
against the original it was derived from, as
[`scripts/pilot_desensitisation_check.py`](../../scripts/pilot_desensitisation_check.py)
computed them.

**The documents.** The copy is the one registered in
[`docs/pilot/registrations/pilot-paper-002.json`](../pilot/registrations/pilot-paper-002.json):
sha256 `04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`,
stored under the authorised root at
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`. The original is
the advisor's copy under `advisor-sample/`, sha256
`a7a38132cf35d3632c4cb8aacba910994e9ad7e8b27413761260ade2d6502278`.

Neither document's text is in this record. What is here is counts,
booleans and digests.

## The first reading, and what it said

The copy that was registered first, `pilot-paper-001`, had been made by
*accepting* every revision the advisor had made. The measurements against
it were:

| Item | Verdict | What the tool read |
| --- | --- | --- |
| A-1 Author names | **fail** | the `Author` and `Last Modified By` properties are non-empty and are the original's |
| A-6 Contact and identity metadata | **fail** | two built-in properties are non-empty and unchanged from the original; four custom properties are the original's; two revision author fields are not role labels |
| B-2 Revision marks | **fail** | the original carries 96 insertions and 17 deletions; the copy carries none of either |
| C-2 Markup authors are role labels | **fail** | two revision author fields are not role labels |

Its visible text was the original's, character for character — 22,442
characters over 155 paragraphs, and not one paragraph differing in position.
(That is the copy registered as `pilot-paper-001`, sha256
`42eefb065b82c833b213e6c0676b48e5b70417dab7634e9f89d8191aa4162a25`.)
The desensitisation that had been done accepted the revision trail and
removed nothing else.

## The copy that was redone

The owner chose to redo the desensitisation rather than sign the failures.
[`scripts/pilot_redaction.py`](../../scripts/pilot_redaction.py) does it,
from the **original**, so the trail stays and the identity goes:

- the built-in properties — `Author`, `Last Modified By`, `Company`,
  `Manager`, `Template` — are blanked;
- every custom property's **value** is blanked, which is where a WPS user
  id and a Grammarly document id live;
- every author field in the markup — the 198 revision marks' `w:author`
  and the two-person list Word keeps beside them — carries a **role
  label**;
- the paths inside the pictures' own metadata — a TIFF's description can
  carry the folder it was drawn in, and two of this paper's seven pictures
  carried one — are blanked in place, at the same length, so the picture's
  data does not move.

The copy's text, its figures, its structure and its revision trail are the
original's. **Every one of the seven pictures decodes to the same pixels
as the original's**; the two whose metadata changed differ in bytes and
not in a pixel.

## The readings of the redone copy

| Item | Verdict | What the tool read |
| --- | --- | --- |
| A-1 Author names | undecided | both author properties are empty; the byline is read by a person |
| A-2 Affiliations and addresses | undecided | no address-shaped string in either document; the affiliation sentences are read by a person |
| A-3 Project and funding identifiers | undecided | no project-number-shaped pattern in either document; a pattern search is a search, not a verdict |
| A-4 Table and figure numbering | undecided | 155 paragraphs in both documents; the numbering's continuity is read by a person |
| A-5 Headers and footers | pass | the copy carries no header or footer part |
| A-6 Contact and identity metadata | undecided | every built-in property is blanked and none is unchanged from the original; every custom property's value is blanked; both revision author fields carry role labels |
| A-7 Embedded identifiers | pass | the file's name carries the pilot's material id |
| B-1 Advisor annotations | pass | zero comments in both documents |
| B-2 Revision marks | pass | 96 insertions, 17 deletions and 85 format changes in both documents |
| B-3 Heading outline | pass | the two visible texts are identical, so the headings are identical |
| B-4 Revision positions | undecided | the copy carries the marks; their places are read by a person |
| C-1 Comment text is readable | pass | there are no comments to read |
| C-2 Markup authors are role labels | pass | both revision author fields are role labels |
| C-3 Revision text is readable | pass | 1,144 characters of revision text in the copy |
| C-4 Comment anchors are intact | pass | there are no comments to anchor |
| D-1 … D-5 | pass | the registration record's five fields match the copy in hand |
| D-6 The checklist result | undecided | the result is empty; the owner's signature is what is missing |

**Nothing fails: 14 items pass and seven are the owner's to read.** The
seven are the ones whose evidence is a person's reading — a byline, an
affiliation sentence, a numbering's continuity, a mark's place, and the
signature itself. The document carries no byline and no affiliation line
at all: a search of every paragraph for *author*, *corresponding*, *unit*,
*funding*, *affiliation*, *university*, *institute*, *laboratory* and
*e-mail* found none, so the identity in this paper was never in its text
— it was in its properties, in its markup's author fields and in its
pictures' metadata.

## Two things the owner should look at

**The role labels are a reading, not a fact.** The two people who marked
the document are named in Word's people list; the redaction replaced them
with `advisor` and `student-1`. The mapping was made from the number of
marks each of them left — 111 and 2 — and the owner confirmed it on
2026-11-25.

**D-6 is signed.** The owner signed the result on 2026-11-25: every item
A-1…A-7, B-1…B-4, C-1…C-4 and D-1…D-5 is recorded as `pass`, the
signature names `owner`, and the result is bound to the copy's digest, so
it applies to that copy and to no other. The tool's `--require-signed`
mode now passes on it, and the checklist's rule — *until the owner has
signed that result, the import step must not run and no copy enters the
pilot* — is satisfied for this copy. The part-E acceptance checks remain
the pilot ticket's own.

## Where each number came from

Every number in this record was measured, and a number that cannot be
traced to its reading is a number somebody typed. The readings, and what
produced each of them:

| Number | Produced by | Taken at |
|---|---|---|
| 96 insertions, 17 deletions, 85 format changes | the checker's item B-2 facts | the two digests named above |
| 1,144 characters of revision text | the checker's item C-3 facts | the two digests named above |
| 155 paragraphs | the checker's item A-4 facts | the two digests named above |
| 22,442 characters of visible text | the checker's item B-3 facts (`visible_text_characters_copy`) | the two digests named above |
| 198 revision marks, each with an author field | the redaction's own report (`author_fields_replaced=198`) | the copy's digest |
| 111 and 2 marks by the two who marked the document | the same report, read against the original | the original's digest |
| seven pictures, each decoding to the same pixels | [`scripts/pilot_picture_comparison.py`](../../scripts/pilot_picture_comparison.py)'s per-picture verdict | the two digests named above |

**The pixel comparison had no tool, and now has one.** It was taken by a
one-off script that was not in this repository, so the reading was recorded
here with the digests it was taken at rather than with a command that could
be re-run — a comparison a later reader cannot repeat is a measurement
nobody can check. It can be repeated:

```
python scripts/pilot_picture_comparison.py \
    --copy <the copy under the authorised root> \
    --original <the advisor's copy under advisor-sample/>
```

The tool reads the pictures out of both archives, decodes each one, and
compares the two over **decoded pixels** and not over bytes: the redaction
blanked a path inside two pictures' own metadata, in place and at the same
length, so those two pictures' bytes differ where their pixels do not, and
a comparison over bytes would have reported them as different.

Measured on 2026-11-26 against the digests named above, the reading is:

| Picture | Part | Size | Bytes | Pixels |
|---|---|---|---|---|
| 1 | `word/media/image1.png` | 1267 × 761 | the same | identical |
| 2 | `word/media/image2.tiff` | 6846 × 4783 | differ | identical |
| 3 | `word/media/image3.tiff` | 1519 × 496 | the same | identical |
| 4 | `word/media/image4.tiff` | 768 × 516 | the same | identical |
| 5 | `word/media/image5.tiff` | 1750 × 1767 | the same | identical |
| 6 | `word/media/image6.tiff` | 6846 × 4783 | differ | identical |
| 7 | `word/media/image7.tiff` | 2929 × 1290 | the same | identical |

Seven compared, seven identical, none differing, none that the decoder
could not read, and no picture on one side alone. The report names the
decoder and says what it refuses, because a picture the decoder cannot
read is a fact to report and not a failure to hide. The decoder is the
tool's own — `zlib` for PNG, and a TIFF 6.0 reader for uncompressed and
LZW strips — because the project's dependencies carry no image decoder and
this one adds none. The tool's witnesses are in
[`tests/test_pixel_comparison.py`](../../tests/test_pixel_comparison.py):
eighteen tests, and ten mutations between them, each of which was checked
to turn the witness that watches it red, with the file's own tests green
again when the script was restored.

**All of them were measured on this machine, on 2026-11-25 — and the pixel
comparison again on 2026-11-26 — against the digests named above.** A
digest identifies bytes; a different copy has a different digest, and the
numbers would be about that one.

## How the reading was taken

```
python scripts/pilot_desensitisation_check.py \
    --copy <the copy under the authorised root> \
    --original <the advisor's copy under advisor-sample/> \
    --outline <the heading outline exported from the copy> \
    --material-id pilot-paper-002 \
    --registration docs/pilot/registrations/pilot-paper-002.json
```

The tool's own witnesses are in
[`tests/test_pilot_desensitisation_check.py`](../../tests/test_pilot_desensitisation_check.py)
and the redaction's are in
[`tests/test_pilot_redaction.py`](../../tests/test_pilot_redaction.py):
fourteen and nine tests, and eleven mutations between them — one per
verdict — each of which was checked to turn the witness that watches it
red, with the file's own tests green again when the script was restored.
