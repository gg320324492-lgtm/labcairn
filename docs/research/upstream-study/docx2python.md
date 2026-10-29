# docx2python — upstream study

**Role in Phase 2:** reference for LC-P2-07 (DOCX revision and comment
fidelity), and one of the two comparison parsers in the fidelity measurement.
Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/ShayHill/docx2python |
| **Pinned SHA** | `66b1ae3e24ffa7040ed5244490ce2872ac2e86bb` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Licence** | **MIT**, verified by opening `LICENSE.txt` at the pinned SHA |
| **Decision** | **study only; not a dependency; not a source of truth** |

## The licence, read from the file

`LICENSE.txt` at the pinned SHA is the MIT licence, "Copyright (c) 2019 Shay
Hill", with the standard grant, the standard attribution clause ("The above
copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software"), and the standard warranty
disclaimer.

MIT is permissive enough that the decision to *not* depend on it is not a
licence decision. The design's §2 rule — *"clone is not reuse permission"* —
is about more than permission, and this record applies it on the merits: the
library cannot be the revision-history source of truth, and a Phase 2 that
depended on it would inherit its behaviour, including the behaviour below.

## What the tree actually contains

`src/docx2python/` — thirteen modules. The ones that matter here:

| Module | Role |
|---|---|
| `docx_reader.py` | OPC package access; `comments` property reads `word/comments.xml` |
| `depth_collector.py` | walks the document tree, tracking `comment_ranges` by `w:id` |
| `docx_output.py` | the `comments` property that assembles `(reference_text, author, date, comment_text)` |
| `attribute_register.py` | the tag registry; `COMMENT_RANGE_START` / `COMMENT_RANGE_END` appear here |

## The measured finding: it does not read tracked changes at all

A search across every `.py` file in the tree for `w:ins`, `w:del`, `w:moveFrom`,
`w:moveTo` returns **no match**. The only revision-adjacent tags present are
the comment-range tags.

That is the load-bearing fact for LC-P2-07, and it is decisive on its own:
**docx2python cannot be the parser for a project's revision history, because
it does not read revisions.** A document with tracked changes in it is, to
this library, a document with some text in it.

The design's §2 note said to check *"whether `w:ins`/`w:del` and the comment
anchor are fully preserved"* rather than assuming it. The answer for
`w:ins`/`w:del` is **no**: they are not read at all, so they cannot be
preserved. The answer for comments is more nuanced and is below.

## The second measured finding: an unmatched comment silently empties the set

This is the finding that matters most, because it is a **failure mode, not a
missing feature**.

`docx_output.py:408-427` reads:

```python
comment_ranges = depth_collector.comment_ranges
comment_elements = self.docx_reader.comments

if len(comment_ranges) != len(comment_elements):
    msg = (
        "comment_ranges and comment_elements have different lengths. "
        + "Failed to extract comments."
    )
    warn(msg, stacklevel=2)
    return []
```

So when the number of comment *ranges* in `document.xml` differs from the
number of comment *elements* in `comments.xml`, the library emits a Python
warning and **returns an empty list — every comment in the document
disappears together**.

**What the measurement added, and it is more precise than the source
reading.** This record was first written from the source alone, and it said
the whole set vanishes on *any* malformed marker. The LC-P2-07 fidelity
measurement on the synthetic corpus
([`docs/acceptance/LC-P2-07-fidelity-baseline.md`](../../acceptance/LC-P2-07-fidelity-baseline.md))
shows the trigger is the **count mismatch**, not the malformed marker:

| Case | Ranges | Elements | Result, measured |
|---|---|---|---|
| a well-formed comment | 1 | 1 | extracted, with body, author and date |
| a range that starts and never ends | 1 | 1 | **extracted**, with an **empty anchor** |
| a range that ends and never started | 1 | 1 | **extracted**, with an **empty anchor** |
| a comment with no range markers at all | 0 | 1 | **lost entirely** |

So a comment whose marker is unpaired but whose count is balanced
**survives**; a comment with no marker at all does not. **Either way the
anchor is lost**, and the loss is silent in the output: the caller
receives a comment with an empty reference and no indication that an anchor
was there.

The measurement's number for this library is **comment recall 0.429** — six
of fourteen comments recovered, eight lost — and the six fixtures where
comments were lost are exactly the un-anchorable ones.

The mismatch is not exotic. The design's §7 negative list names *"isolated
comment marker"* as a case that must be handled. A comment whose
`w:commentRangeStart` has no matching `w:commentRangeEnd`, a comment whose
range markers were removed but whose `w:commentReference` survived, a
document edited in Word then re-saved by another tool — each of these makes
the two counts differ, and each therefore makes the whole comment set
vanish.

Contrast this with the project's own contract, which ADR-0009 and the Phase 1
material path already hold to: *"unreadable material is separated from empty
material and from readable material, and neither unreadable state is
citable"*. A partial parse that reports the comments it found, names the ones
it could not match, and distinguishes them from "this document has no
comments" is the contract. **A warning plus an empty list cannot express
that difference** — the caller sees "no comments", which is a false statement
about the document.

This is the single clearest reason the Phase 2 parser must be written rather
than configured, and it is why the fidelity measurement must score
**per-comment** rather than per-document. A document whose comments were
dropped as a set scores *worse* in a per-document metric only if the metric
notices it is different from "a document with no comments" — and a naive
"extracted comments == expected comments" comparison does notice it. But a
metric that only counts *correctly extracted* comments, without a
**false-negative floor**, would let a parser that returns nothing score
perfectly. The measurement must therefore report both.

## What it does well

The comment extraction that *does* work is good work, and it is a reasonable
reference for the shape of the output:

- **Anchor text.** `reference` is reconstructed from the runs between
  `comment_ranges[id_]`, i.e. the text the comment is attached to. That is
  the anchor Phase 2 needs, expressed as text.
- **Metadata.** `author` and `date` come from the `w:author` and `w:date`
  attributes of the comment element.
- **Body.** The comment text is assembled from the comment part's own
  paragraph tree.
- **Graceful absence.** A document with no `comments` part returns `[]`
  rather than raising — the `KeyError` is caught in `docx_reader.comments`.

The tuple `(reference_text, author, date, comment_text)` is, as a shape, very
close to what LC-P2-07's `RevisionEvent` wants. The difference is that
Phase 2 needs a **stable anchor into the original XML** — the comment's
`w:id`, and where its range markers sit — rather than only the anchor's
rendered text, because the text alone cannot be located back in the file.

## How it fits the mentor-trajectory question

| Phase 2 need | docx2python | Gap |
|---|---|---|
| comment body, author, date | yes | — |
| comment anchor text | yes | **paragraph-granular**, measured: two comments on different parts of one paragraph both report the same anchor |
| `w:ins` / `w:del` / `w:move*` | **no** | not read at all |
| revision author and date | **no** | not read at all |
| orphan / unmatched comment handling | **no** | whole set dropped with a warning |
| per-event fidelity report | **no** | one list, all-or-nothing |
| original bytes unmodified | yes (read-only) | — |

So: useful for the **comment** half of LC-P2-07's input surface, and
explicitly unsuitable for the **revision** half and for the failure
behaviour. It is a fair comparison parser for the comment dimension and no
parser at all for revisions.

## Where it is used in Phase 2, and where it is not

**Used as:** one arm of the LC-P2-07 fidelity measurement — the "extraction
library" arm, compared against the OOXML-native arm. Its contribution to that
measurement is exactly the finding above: it demonstrates that a
well-regarded library drops the comment set on a mismatch, so the
measurement must score false negatives separately.

**Not used as:** a dependency, a source of truth, or the basis for any claim
about revision history.

**Not copied:** MIT would permit it, with attribution. Nothing is copied, and
the implementation of the Phase 2 parser follows the OOXML specification
(ECMA-376 / ISO-IEC 29500) rather than this library's code. The reason is
not the licence; it is that this library's behaviour on the interesting
inputs is the thing to be *different* from.

## Failure cases carried into the negative-test list

1. **A comment with a start marker but no end marker** — the count mismatch
   that empties docx2python's whole set.
2. **A comment element with no range markers at all** — a comment that
   survives in `comments.xml` while its anchors were deleted. Phase 2 must
   report it as an **orphan comment** with a known body and *unknown* anchor,
   not drop it and not hang it on the wrong text.
3. **A `w:commentReference` with no matching `w:comment`** — a reference in
   the document pointing at a comment id that does not exist.
4. **Nested and overlapping comment ranges** — two comments whose ranges
   overlap, which Word permits.
5. **A document whose comments part is absent** — distinct from "a document
   whose comments part exists and is empty".
6. **Comments in headers, footers and footnotes** — parts other than
   `word/document.xml`, where a range and its element live in *different*
   files. A parser that only reads `document.xml` will report these as
   missing.

Cases 1, 2 and 6 are the ones that make the difference between "a parser that
extracts comments" and "a parser that reports what it found and what it
could not".

## Reproducing the reference

```bash
git clone --filter=blob:none https://github.com/ShayHill/docx2python.git
git -C docx2python rev-parse HEAD   # 66b1ae3e24ffa7040ed5244490ce2872ac2e86bb
```

The library was **not installed** into the project environment and **no
benchmark of it was run** as part of this study. The claims above are claims
about the source at the pinned SHA, read directly. The fidelity measurement
that would turn them into numbers is LC-P2-07's deliverable, and it will
install the library in an isolated environment to measure it — that number
will be reported with its own measurement record, and it is not yet measured.
