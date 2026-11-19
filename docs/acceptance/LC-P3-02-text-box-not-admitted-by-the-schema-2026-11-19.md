# LC-P3-02 — the corpus's text box was not a shape Word admits (2026-11-19)

**Date:** 2026-11-19. **Type:** dated defect record for the Phase 3 DOCX
corpus. It records one defect, the measurements that establish it, the
repair, the witness that now holds the repair, and the one claim that is
still open. It carries no DOCX material, no screenshot bytes and nothing
read out of the corpus; the artifacts and the evidence stay under
`E:/labcairn-local/`.

> **This record was corrected twice on the day it was written, and both
> corrections are part of it.** The first diagnosis -- that the anchor's
> missing children were the cause -- was **refuted by a probe** and is
> recorded below as a refuted hypothesis, not as a finding. The second
> diagnosis -- the placement of the markup-compatibility element and the
> anchor's missing required attributes -- is what the schemas show. The
> earlier text is kept, dated and marked, so that a reader can see what
> was believed, when it was believed, and what measurement overturned it.

## Final status sentence

**The corpus's text box was not a shape the WordprocessingML content model
admits, in two ways at once: its `mc:AlternateContent` sat directly in a
`w:p`, where the run-level `w:drawing` and `w:pict` it carries are not
allowed, and its `wp:anchor` carried none of the five attributes
`CT_Anchor` marks `use="required"`. The generator now writes the shape
Word writes, a witness holds it there, and the artifacts the twelve-row
rerun measures have been re-based onto the repaired corpus. Word 2019 now
opens the repaired file and draws the caption, so the refusal the 44-row
ledger's D-4 recorded is gone. A second defect sat in the same document:
the inline picture's own shape properties were empty, so Word drew the
frame and no picture. That is fixed too, and Word now draws the blue
square.**

## The picture, which was empty of everything but its frame

**What was measured.** The owner's screenshot of the repaired file carries
**no pixel** of the corpus blue anywhere in the page area -- the only
blue on the screen is an 11 × 35-pixel accent in the ribbon -- while the
media part itself is sound: 70 bytes, IHDR 1 × 1 colour type 6 depth 8,
all three chunk CRCs correct, and the IDAT inflating to one filter byte
and the pixel (46, 116, 181, 255). The relationship and the `r:embed` are
intact. So the picture was not missing, and it was not transparent: it
was **not drawn**.

**The cause.** The corpus wrote the picture's own shape properties empty:
`<pic:spPr/>` with no `a:xfrm` and no `a:prstGeom`, an empty
`<pic:cNvPicPr/>`, and a `pic:cNvPr` at the id `0`. A picture with no
extent of its own has nothing to scale into the frame the drawing
reserved. **Every one of the 2,133 `<pic:spPr>` elements in the real Word
documents on this machine carries an `a:xfrm`** -- there is no
counterexample.

**The measurement that fixed it.** Two probes of the same artifact, opened
by the owner in Word 2019 16.0.17932.21140 on 2026-11-19: one whose
picture markup was made the way Word writes it, and the same one with a
16x16 pixel of the same colour. **Both drew the blue square**, so the
markup was the whole of it and the one-pixel image was never the
problem. The second probe is what rules the other suspect out: if the
size had been the cause, the one-pixel probe would have stayed blank.

**The repair.** `src/labcairn/editing/samples.py`'s `image()` now writes
`pic:spPr` with an `a:xfrm` -- the offset and the extent -- and an
`a:prstGeom`, `pic:cNvPicPr` with the `a:picLocks` Word writes, and a
`pic:cNvPr` with the id `1`.

## What the host did with the repaired file

Measured on 2026-11-19 by the owner, on the re-based artifact (2,789 bytes,
SHA-256 `c5404ec654969a1fd0b6ed20902f1f3bdc9dba3e95ba6130696c14d62fce3edc`),
in Microsoft Word 2019 16.0.17932.21140:

| thing | seen |
|---|---|
| the file | **opens** -- the severe-open-error dialog is gone |
| the caption | **"The caption inside the text box repeats itself."** is drawn, inside the box |
| the paragraph beside the figure | drawn **to the right of the box**, which is where the corpus's own wording puts it and what the box's 10 cm width does to it |
| the field and the content control | "The page reads 3." and "The sentence bound to a content control." |
| the word count | **34** -- the five sentences with the caption (7 + 8 + 8 + 4 + 7), so the text box's words are counted |
| **the picture** | **nothing.** The page area carries **no pixel** of the corpus blue; the only blue on the screen is an 11 × 35-pixel accent in the ribbon |
| the box's border | none drawn -- the corpus's text box carries no `a:ln`, so the box is invisible as a frame although it is there, and the wrap proves it is there |

The screenshot is outside the repository, under
`E:/labcairn-local/rerun12-opaque-20261118/screenshots/`, 2858 × 1512,
SHA-256
`8c694bbb8609e00c8872a73b9f4ad74ae5040a4e82717223a8448890b9379061`.

**So the refusal is fixed, and D-4's cause is established.** What the host
does with the picture is a different question, and it is open.

**And then, on the final bytes, the twelve-row rerun's own Word row
confirmed it.** Row R02 -- Microsoft Word 2019 16.0.17932.21140, the `08`
family's `surgical-clean` artifact at 2,814 bytes, SHA-256
`30c2d8f9669614a3d192e5093154e3e22afd1ff5912e0e7e1646082d01a5a4bc` -- is
recorded **PASS**: the file opens, the caption is drawn, the blue square is
drawn (42 x 43 pixels in the first pass and 44 x 44 in the second), the
content control shows its own frame and its alias tag "Title" when
clicked, and the `PAGE` field's result shows Word's grey shading when
clicked. The artifact's bytes were unchanged after the two looks.

**The two hosts differ on the field, and the difference is the point.**
Word shows the field's shading; WPS 12.1.0.29690 shows nothing when the
`3` is clicked, so WPS's answer for `fields` is `not-inspectable` and
Word's is `yes`. The same six tokens, two hosts, two answers, each bound
to its own host version.

## What the schema shows

The ECMA-376 Part 4 archive carries the transitional XSDs. They were
fetched, unpacked under `E:/labcairn-local/ooxml-schemas/` -- Ecma's, and
not in this repository -- and every one of the rerun's artifacts was
validated against `wml.xsd`, with the markup-compatibility preprocessing a
consumer performs applied first.

**The control is the point.** The rerun has 24 artifacts. Word 2019
16.0.17932.21140 refused **two** of them -- the `08` family's pair -- and
opened the other twenty-two, which the 44-row ledger records as PASS or
PRESENCE-LOSS rather than REFUSAL-RECORDED. Those twenty-two are the
control, and they were validated in the same run:

| artifact family | how Word treated it | `w:drawing` at paragraph level | `wp:anchor` without its required attributes |
|---|---|---|---|
| `01`, `01b`, `02`, `03`, `04`, `05`, `06`, `06b`, `07`, `09` | opened | no | no |
| **`08`** | **refused outright** | **yes** | **yes** |

The two artifacts Word refused are the only two with either violation, and
they are the only two carrying an anchored drawing at all. The validation
also found a third violation -- three samples' tables carry no `w:tblGrid`
-- which Word **tolerates**: the `07` family's artifact has it and Word
opened it. That finding is real and is **not** fixed here; it is recorded
in "What is still open" below, because fixing it would re-base four more
rows of the rerun for a defect that blocks nothing.

**The two violations, named.**

1. **The placement.** `w:drawing` and `w:pict` are run-level content:
   `CT_P` admits `w:r`, `w:hyperlink`, `w:fldSimple`, `w:subDoc` and the
   run-level elements, and `w:drawing` is not among them -- it belongs
   inside a `w:r`. The corpus's text box put the whole
   `mc:AlternateContent`, both branches, directly into a `w:p`. A consumer
   performs the markup-compatibility preprocessing **before** the content
   model applies: it replaces the `mc:AlternateContent` with the content of
   the branch it understands, and that content has to be legal where the
   element stood. After the preprocessing the `w:drawing` stood at
   paragraph level. **Every real Word document on this machine puts the
   element inside a `w:r`** -- measured over the sixty-odd Word-produced
   `.docx` files under `E:/labcairn-local/`, forty-five of which carry a
   `wp:anchor`.
2. **The attributes.** `CT_Anchor` marks five attributes
   `use="required"`: `relativeHeight`, `behindDoc`, `locked`,
   `layoutInCell` and `allowOverlap`. The corpus's anchor carried **none
   of them**. Validated against `dml-wordprocessingDrawing.xsd`, the
   anchor reports all five as missing.

## What the probe answered, and what it refuted

**The first diagnosis, and its refutation.** This record's first version
held that the anchor's missing children -- `wp:simplePos`, `wp:positionH`,
`wp:positionV` and a wrap element -- were the cause, on the strength of
the two hosts' symptoms and the schema's requirement that they be there.
**A probe tested it and the probe failed.** The probe was a copy of the
rerun's own artifact with the four children inserted and nothing else
changed: 2,620 bytes, SHA-256
`77d7a1ba366088faae99c625290f1cc54e31621178afcc5e73dab5302720d3eb`. Word
2019 refused it with the same severe-open-error dialog; the screenshot is
`E:/labcairn-local/ac6-anchor-probe-20261119/probe-20261119-word-refusal.png`
and both files were re-hashed afterwards and are byte-unchanged.

The probe refuted the hypothesis it was built to test. It had left the
attributes missing and the placement wrong, and the schema says both are
violations -- so the children were not the whole of it, and the "consistent
with both symptoms" reasoning was not strong enough to carry a repair.

**What the two hosts did with the broken shape.** WPS Office 12.1.0.29690
opened sample 08 and drew the body text and the picture but **not the
caption**; the rerun's row R01 records `text-boxes:no`. Word 2019
16.0.17932.21140 **refused the file outright**; row R02 records the
refusal. Both are measurements. Neither is a measurement of the *cause*,
and the cause is what this record had to get right.

## What was measured, before and after

| measured value | the artifact as the rerun measured it | the artifact as this branch writes it |
|---|---|---|
| bytes | 2,531 | 2,789 |
| SHA-256 | `cbf08be135b26c8876075641421d9c4ee881bcb3387d80e14c8875585bc746dd` | `c5404ec654969a1fd0b6ed20902f1f3bdc9dba3e95ba6130696c14d62fce3edc` |
| `mc:AlternateContent`'s parent | `w:p` | `w:r` |
| `wp:anchor`'s required attributes present | 0 of 5 | 5 of 5 |
| `wp:anchor`'s required children present | 3 of 6 | 6 of 6 |
| wrap elements present | 0 | 1 (`wrapSquare`) |
| schema violations, in Word's MCE view | `w:drawing` at paragraph level; five attributes missing | none beyond `mc:Ignorable` and the `wps` extension namespace |

The first column is the defect, the second is the repair, and both were
produced by running the validator over the bytes on disk. The two findings
the validator cannot have are the same for both columns and are not
defects: `mc:Ignorable` is on `w:document` in every file Word writes and
the ECMA schema has no opinion about it, and the `wps` namespace is
Microsoft's extension, which the ECMA schemas do not carry.

The superseded artifacts were **kept**, not deleted: they are in
`E:/labcairn-local/rerun12-opaque-20261118/artifacts/outputs-defective-20261119/`.

## Why the earlier repair did not close it

PR #195 (merge `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8`) repaired the
text-box anchor and gave sample 08 its declared image. Its commit message
says the missing `wp:docPr` and `wps:spPr` were "the most likely trigger
of Word 2019's severe-open refusal" -- the hedge was right, because the
cause was not only those two.

The witness that repair added,
`test_every_anchored_drawing_carries_its_required_children` in
`tests/test_docx_edit_samples.py`, checked that `wp:docPr` was present,
that `wp:extent` was present and was not 1x1, and that `wps:spPr` preceded
`wps:txbx`. It said nothing about the position children, the wrap, the
attributes or the placement, because the repair's author had not read them
off the schema. A search of `src/`, `tests/` and `docs/` for those names
returned nothing before this record: **no line in the repository watched
them**, so the defect survived the repair meant to close it and every
later change to the same generator kept it.

## The repair

`src/labcairn/editing/samples.py`, `text_box()`, now writes:

- the `mc:AlternateContent` **inside a `w:r`**;
- the `wp:anchor` with its five required attributes -- `relativeHeight`,
  `behindDoc`, `locked`, `layoutInCell`, `allowOverlap` -- and, in the
  schema's order, `wp:simplePos`, `wp:positionH`, `wp:positionV`,
  `wp:extent`, `wp:effectExtent`, `wp:wrapSquare`, `wp:docPr`,
  `wp:cNvGraphicFramePr`, `a:graphic`;
- the `wps:wsp` with `wps:cNvSpPr` and `wps:bodyPr`, the way Word writes a
  text box: every real Word text box measured on 2026-11-19 carries both.

## The witness

`tests/test_docx_edit_samples.py` now reads `CT_Anchor`'s sequence out of
the standard rather than out of a list of names somebody remembered, and
asserts on every anchored drawing in the corpus:

1. every required child is present exactly once;
2. exactly one of the five wrap elements is present;
3. the children that are present appear in the schema's order;
4. the five required attributes are present.

A second witness, `test_the_markup_compatibility_element_sits_inside_a_run`,
asserts that every `mc:AlternateContent` is inside a `w:r` and that every
`w:drawing` and `w:pict` ends up inside a `w:r` once the
markup-compatibility branches are resolved. A third,
`test_every_picture_carries_its_own_size_the_way_word_writes_it`, asserts
that every picture's `pic:spPr` carries an `a:xfrm` with a readable
extent, an `a:prstGeom`, a `pic:cNvPicPr` carrying the `a:picLocks` Word
writes, and a `pic:cNvPr` with a real id.

**The witnesses were mutation-checked on 2026-11-19.** Six mutations of
the generator, each applied to the source and then reverted from a
byte-for-byte backup rather than from git:

| mutation | the suite |
|---|---|
| baseline, unmutated | 20 passed |
| `wp:positionH` dropped | 1 failed, 19 passed |
| `wp:wrapSquare` dropped | 1 failed, 19 passed |
| `wp:positionH` moved after `wp:extent` | 1 failed, 19 passed |
| the anchor's `relativeHeight` attribute dropped | 1 failed, 19 passed |
| the `mc:AlternateContent` moved back out of the `w:r` | 1 failed, 19 passed |
| `wps:bodyPr` dropped | 1 failed, 19 passed |
| the picture's `a:xfrm` dropped | 1 failed, 19 passed |
| the picture's `a:picLocks` dropped | 1 failed, 19 passed |
| the picture's id put back to `0` | 1 failed, 19 passed |

All nine were caught, and the fifth is the finding the earlier repair
missed.

## What is still open

- **The tables without a `w:tblGrid`.** Three corpus samples -- `02`,
  `03` and `07` -- carry a `w:tbl` with no `w:tblGrid`, which the schema
  rejects. **Word tolerates it**: the `07` family's artifact has the
  violation and Word opened it. It is not fixed here, because fixing it
  changes the `07` family's bytes and would re-base four more rows of the
  rerun for a defect that blocks nothing. **The owner ruled on
  2026-11-19: leave it, and close the twelve rows first.** It stays an
  open finding, not a closed one.
- **D-4.** The 44-row ledger's D-4 finding is **closed by the measurement
  above**: the file opens, and the cause was the two schema violations
  this record names. The *ledger row* that recorded the refusal is R02's,
  and it is re-run against the repaired bytes.
- **Whether the repaired picture draws in Word.** The schema has no
  opinion -- the corpus's picture markup was legal, just empty -- so the
  owner's two probes are the measurement, and they say it draws. **The
  corpus's own witness now holds the shape**, so a later change to the
  generator that empties it again turns the suite red.

## What the rerun now owes

The corpus's bytes changed, so the rerun was **re-based onto them**:

- the `08` family's two artifacts were regenerated; the superseded ones
  were kept, not deleted;
- the six artefacts of the three families the rerun measures are the ones
  in `artifacts/outputs/`, and the eighteen of the families it does not
  measure were moved to `artifacts/others/`, so the folder the operator
  opens holds the six documents they are about to open;
- **an earlier arrangement was tried and withdrawn.** The three families
  were first given a folder each -- `artifacts/outputs-08-to-open/` and
  the like -- so that each folder held two documents. **That broke six
  tools**: the repository's `scripts/closeout_12_rows.py` and the pack's own
  `validate_pack.py`, `self_check.py` and `check_no_save_mutation.py` all
  resolve an artefact **by name** under `artifacts/outputs`, and the
  closeout reported **all twelve rows** as BLOCKERs ("the artefact ... is
  not in the pack"). A convenience that costs the tools their assumption
  is the wrong trade, and the arrangement was put back. The pack's
  template, the copy the operator fills and the twelve cards that print
  the path say `artifacts/outputs/`, and the pack's validator and the
  closeout both find every artefact again;
- the ledger's `sha256_before` and `byte_size_before` were re-baselined
  for the rows whose artifact changed;
- the observation cells of those rows were **cleared, not re-filled**;
- the other twenty artifacts are byte-identical, so rows R05-R12 stand.

**All twelve rows are open, and none has been run on the final bytes.**
Rows R01-R04 were measured on the broken shape and are void; the `05` and
`07` families were never run on this round's bytes at all. The picture
repair changed the `05` and `07` families' bytes too, which is why the
re-basing happened before any row was recorded: **the twelve rows run once,
on the final bytes, and nothing is wasted.**

## Evidence location

Nothing in this record's evidence is in the repository. The artifacts, the
screenshots and the rerun's own CSV live under
`E:/labcairn-local/rerun12-opaque-20261118/`; the probe copy of the
repaired `08` artifact and its refusal screenshot live in
`E:/labcairn-local/ac6-anchor-probe-20261119/`; the two picture probes
and the screenshots of them drawing the square live in
`E:/labcairn-local/picture-probe-20261119/`; the schemas and the scripts
that took the readings live in `E:/labcairn-local/ooxml-schemas/` and
`E:/labcairn-local/anchor-defect-20261119/`.

## How to reproduce the measurement

```
python E:/labcairn-local/anchor-defect-20261119/validate_against_ooxml_schema.py
```

It validates the rerun's artifacts against `wml.xsd`, with the
markup-compatibility preprocessing applied, and prints the violations with
the path they sit at. The control is in the same run: the twenty-two
artifacts Word opened are validated next to the two it refused.

```
python E:/labcairn-local/anchor-defect-20261119/validate_corpus_against_ooxml_schema.py
```

does the same for every sample the corpus writes, and judges both
markup-compatibility branches.

```
python E:/labcairn-local/anchor-defect-20261119/mutate_anchor_witness.py
```

applies each of the six mutations to `src/labcairn/editing/samples.py`,
runs `tests/test_docx_edit_samples.py`, prints the suite's verdict for
each, and restores the source from a byte-for-byte backup it took before
the run. It never uses `git checkout` to restore, because that would
discard uncommitted work.
