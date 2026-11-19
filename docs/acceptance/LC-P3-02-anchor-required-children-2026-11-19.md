# LC-P3-02 — the corpus's anchored text box was missing four children the schema requires (2026-11-19)

**Date:** 2026-11-19. **Type:** dated defect record for the Phase 3 DOCX
corpus. It records one defect, the measurements that establish it, the
repair, the witness that now holds the repair, and the one claim that is
still open. It carries no DOCX material, no screenshot bytes and nothing
read out of the corpus; the artifacts and the evidence stay under
`E:/labcairn-local/`.

## Final status sentence

**The corpus's anchored text box carried three of the six children
`CT_Anchor` requires and no wrap element at all — `wp:simplePos`,
`wp:positionH`, `wp:positionV` and one of the five wrap elements were
absent from the bytes the twelve-row rerun put in front of WPS and Word
2019 — which is a schema violation in the measurement's own input. The
generator now writes the complete anchor and a witness holds it there.
Whether the missing children are what Word objected to is still open, and
the ledger's D-4 stays open with it.**

## What was measured

Two readings, both taken from the bytes on disk. The first is the
twelve-row rerun's own artifact, the file row R01 and row R02 name; it has
not changed since 2026-11-18 and its SHA-256 is the one the rerun's
`before` column carries. The second is the repository's corpus sample
`08-refusals-elsewhere-in-the-document` as this branch writes it.

| measured value | the rerun's artifact | the corpus sample on this branch |
|---|---|---|
| bytes | 2,531 | 2,701 |
| SHA-256 | `cbf08be135b26c8876075641421d9c4ee881bcb3387d80e14c8875585bc746dd` | `8533daeb88fd3337383f60140b1c0653c457c1e94cedabb18703b0971bd2aa53` |
| `wp:anchor` children, in document order | `extent`, `docPr`, `graphic` | `simplePos`, `positionH`, `positionV`, `extent`, `effectExtent`, `wrapSquare`, `docPr`, `cNvGraphicFramePr`, `graphic` |
| required children present | 3 of 6 | 6 of 6 |
| wrap elements present | 0 | 1 (`wrapSquare`) |

The first column is the defect: three required children, no wrap. The
second column is the repair. Both were produced by
`E:/labcairn-local/anchor-defect-20261119/measure_anchor_children.py`, which
reads the two files and prints what it finds; nothing here is written by
hand.

Two corpus samples carry an anchored drawing, `08-refusals-elsewhere-in-the-document`
and `11-refuse-edit-inside-a-text-box`. Both are written by the same
generator function, so both were defective and both are repaired.

## The rule the bytes break

ECMA-376 Part 1, §20.4.2.1, defines `CT_Anchor` as a sequence: `wp:simplePos`,
`wp:positionH`, `wp:positionV` and `wp:extent` are each required exactly
once; `wp:effectExtent` is optional; **exactly one** of `wp:wrapNone`,
`wp:wrapSquare`, `wp:wrapTight`, `wp:wrapThrough` and `wp:wrapTopAndBottom`
must be present; `wp:docPr` is required; `wp:cNvGraphicFramePr` is optional;
and `a:graphic` is required. The order is part of the definition.

The artifact's anchor had three of the six required children and no wrap
element; the three it had were in the schema's order. It is not a near-miss
— it is an element the schema does not admit.

The `08` family has two artifacts, and both carry that anchor: the
`surgical-clean` one the table above measures, and the `surgical-marked` one
at 2,624 B, SHA-256
`71396bd18f72…`, whose anchor reads `extent`, `docPr`, `graphic` in the
same way. Those two files are what rows R01–R04 name.

## The two symptoms, and what they do and do not establish

Both were observed by the owner on 2026-11-19, on the artifact above, and
both are recorded in the rerun's own evidence folder:

- **WPS Office 12.1.0.29690** opened the file and drew the body text and
  the picture, but **not the caption**. Row R01 records `text-boxes:no`.
- **Microsoft Word 2019 16.0.17932.21140** refused the file outright, with
  its severe-open-error dialog (the host's own Chinese text; the screenshot
  is in the evidence folder). Row R02 records the refusal.

**What follows.** A file whose `wp:anchor` the schema does not admit is
defective on its own terms, whatever a host does with it. The two symptoms
are consistent with the defect being the cause of both — an anchor with no
position has nowhere to put the box, and an anchor with no wrap has nothing
to wrap against — but consistency is not causation, and **this record does
not claim that restoring the four children makes Word open the file.**

**What that claim needs.** One experiment, not yet run: open a file whose
anchor carries the complete child sequence in Word 2019 and see whether it
opens. Until that reading exists, D-4 stays open. The evidence folder holds
a probe copy built for exactly that test.

## Why the earlier repair did not close it

PR #195 (merge `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8`) repaired the
text-box anchor and gave sample 08 its declared image. Its commit message
says the missing `wp:docPr` and `wps:spPr` were "the most likely trigger of
Word 2019's severe-open refusal" — the hedge was right, because the cause
was not only those two.

The witness that repair added,
`test_every_anchored_drawing_carries_its_required_children` in
`tests/test_docx_edit_samples.py`, checked that `wp:docPr` was present, that
`wp:extent` was present and was not 1×1, and that `wps:spPr` preceded
`wps:txbx`. It said nothing about `wp:simplePos`, `wp:positionH`,
`wp:positionV` or a wrap element, because the repair's author had not read
them off the schema. A search of `src/`, `tests/` and `docs/` for those four
names returned nothing before this record: **no line in the repository
watched them, so the defect survived the repair that was meant to close it,
and every later change to the same generator kept it.**

## The repair

`src/labcairn/editing/samples.py`, `text_box()`, now writes the anchor in
the schema's order: `wp:simplePos`, `wp:positionH`, `wp:positionV`,
`wp:extent`, `wp:effectExtent`, `wp:wrapSquare`, `wp:docPr`,
`wp:cNvGraphicFramePr`, `a:graphic`. The box is anchored at the column and
the paragraph it belongs to, at zero offset, with the text wrapping on both
sides; the `mc:Fallback` branch's `v:shape` keeps the same size, so both
branches still describe the same box.

## The witness

`tests/test_docx_edit_samples.py` now reads `CT_Anchor`'s sequence out of
the standard rather than out of a list of names somebody remembered, and
asserts three things on every anchored drawing in the corpus:

1. every required child is present exactly once;
2. exactly one of the five wrap elements is present;
3. the children that are present appear in the schema's order.

The rule is written out in the test file rather than imported, for the
reason that file's heading gives: the corpus must not be verified by the
machinery it constrains, and there is no schema validator here.

**The witness was mutation-checked on 2026-11-19.** Three mutations of the
generator, each applied to the source and then reverted from a byte-for-byte
backup rather than from git:

| mutation | the suite |
|---|---|
| baseline, unmutated | 18 passed |
| `wp:positionH` dropped | 1 failed, 17 passed |
| `wp:wrapSquare` dropped | 1 failed, 17 passed |
| `wp:positionH` moved after `wp:extent` | 1 failed, 17 passed |

All three were caught, and the third one matters: the children were all
present in that mutation, and only the order was wrong.

## What this record does not say

- **It does not say Word 2019 opens the file now.** That is unmeasured, and
  the reading that would measure it has not been taken.
- **It does not close D-4.** The ledger's D-4 finding stands, with its
  cause now narrower.
- **It does not change any row of the twelve-row rerun.** The rerun's
  artifacts are unchanged on disk; what changed is the corpus they were
  generated from.
- **It does not claim a WPS result for Word, or a Word result for WPS.**

## What the rerun now owes

The rerun measures what the corpus renders in a host, and the corpus's
bytes have changed. The eight rows whose artifacts carry no anchored
drawing — the `05` and `07` families — are byte-identical and stand. The
four rows of the `08` family are measured on bytes that no longer exist,
and **row R01, which is complete, has to be run again on the new bytes.**

So the re-basing is forced by the repair, and the only question is when.
Two orderings:

- **Re-base first, then run the rows.** The regenerated `08` artifact *is*
  the probe: if Word opens it, the cause is established and D-4 closes; if
  it refuses the same way, the cause is elsewhere and the next hypothesis
  has a real measurement to work from. Row R01 is run once, on the bytes
  that will ship.
- **Probe first, then re-base.** The owner opens the probe copy, and only
  once the cause is known does the pack's corpus get regenerated. Row R01
  is run twice if the probe says the fix was not the cause.

The first ordering spends one row instead of two, and turns the probe into
a row rather than a separate exercise.

## Evidence location

Nothing in this record's evidence is in the repository. The artifacts, the
screenshots and the rerun's own CSV live under
`E:/labcairn-local/rerun12-opaque-20261118/`; the probe copy of the
repaired `08` artifact lives in
`E:/labcairn-local/ac6-anchor-probe-20261119/`; and the two scripts that
took the readings below live in
`E:/labcairn-local/anchor-defect-20261119/`.

## How to reproduce the measurement

```
python E:/labcairn-local/anchor-defect-20261119/measure_anchor_children.py
```

It prints the table above from the bytes on disk: the rerun's artifact and
the corpus sample as this branch writes it, each with its size, its
SHA-256, its anchor's children in document order, and which of
`CT_Anchor`'s required children are missing. Nothing here is written by
hand.

The mutation check is the other script in the same folder:

```
python E:/labcairn-local/anchor-defect-20261119/mutate_anchor_witness.py
```

It applies each of the three mutations above to
`src/labcairn/editing/samples.py`, runs
`tests/test_docx_edit_samples.py`, prints the suite's verdict for each, and
restores the source from a byte-for-byte backup it took before the run. It
never uses `git checkout` to restore, because that would discard
uncommitted work.
