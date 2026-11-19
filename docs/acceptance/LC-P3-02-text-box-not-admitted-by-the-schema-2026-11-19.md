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
rerun measures have been re-based onto the repaired corpus. Whether Word
2019 opens the repaired file is still open, and the ledger's D-4 finding
stays open with it.**

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
markup-compatibility branches are resolved.

**The witnesses were mutation-checked on 2026-11-19.** Six mutations of
the generator, each applied to the source and then reverted from a
byte-for-byte backup rather than from git:

| mutation | the suite |
|---|---|
| baseline, unmutated | 19 passed |
| `wp:positionH` dropped | 1 failed, 18 passed |
| `wp:wrapSquare` dropped | 1 failed, 18 passed |
| `wp:positionH` moved after `wp:extent` | 1 failed, 18 passed |
| the anchor's `relativeHeight` attribute dropped | 1 failed, 18 passed |
| the `mc:AlternateContent` moved back out of the `w:r` | 1 failed, 18 passed |
| `wps:bodyPr` dropped | 1 failed, 18 passed |

All six were caught, and the fifth is the finding the earlier repair
missed.

## What is still open

- **Whether Word 2019 opens the repaired file.** That is unmeasured. The
  schema says the old shape was not admissible and the new one is; a host
  agreeing is a separate reading, and it has not been taken.
- **D-4.** The 44-row ledger's D-4 finding stands, with its cause now
  named rather than guessed.
- **The tables without a `w:tblGrid`.** Three corpus samples -- `02`,
  `03` and `07` -- carry a `w:tbl` with no `w:tblGrid`, which the schema
  rejects. **Word tolerates it**: the `07` family's artifact has the
  violation and Word opened it. It is not fixed here, because fixing it
  changes the `07` family's bytes and would re-base four more rows of the
  rerun for a defect that blocks nothing. **The owner ruled on
  2026-11-19: leave it, and close the twelve rows first.** It stays an
  open finding, not a closed one.

## What the rerun now owes

The corpus's bytes changed, so the rerun was **re-based onto them**:

- the `08` family's two artifacts were regenerated; the superseded ones
  were kept, not deleted;
- the `08` family's two artifacts then moved into a folder of their own,
  `E:/labcairn-local/rerun12-opaque-20261118/artifacts/outputs-08-to-open/`,
  so that the folder the operator opens holds one document instead of
  twenty-four; the pack's template, the copy the operator fills and the
  four cards that print the path all say the new path, and the pack's own
  validator passes on it;
- the ledger's `sha256_before` and `byte_size_before` were re-baselined
  for the rows whose artifact changed;
- the observation cells of those rows were **cleared, not re-filled**;
- the other twenty artifacts are byte-identical, so rows R05-R12 stand.

**Rows R01-R04 are open and are to be run again on the new bytes.** Row
R01, which was complete, is void: its observation was taken on the broken
shape. The eight rows that carry no anchored drawing were never affected.

## Evidence location

Nothing in this record's evidence is in the repository. The artifacts, the
screenshots and the rerun's own CSV live under
`E:/labcairn-local/rerun12-opaque-20261118/`; the probe copy of the
repaired `08` artifact and its refusal screenshot live in
`E:/labcairn-local/ac6-anchor-probe-20261119/`; the schemas and the
scripts that took the readings live in
`E:/labcairn-local/ooxml-schemas/` and
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
