# ADR-0014: Paper revision provenance — what a manuscript version is, and where a change is anchored

**Status:** Proposed
**Work order:** LC-P2-06, LC-P2-07, LC-P2-08 (proposed; not yet dispatched).
**Status:** the ADR is drafted and **not accepted**; LC-P2-07's reader
implements D4a and D5 against it (2026-10-29), and the contracts below
name the witnesses that hold it.
**Date:** 2026-10-29

## Context and concrete problem

Phase 1's material model addresses a file and a place inside it: a PDF page
and character span, a text line and section, a CSV row and column, a
spreadsheet sheet and cell. ADR-0009 stores the extracted text so that an
anchor resolves to the same string it named when the anchor was written.
The report path then cites locators only, and the link check resolves every
citation against the material and acts on the answer.

**None of that reaches a Word document's revision history.** The gap is not
that the feature is missing; it is that the concept does not exist in the
model, and three different things are being called "a revision":

| Thing | What it means today | Where |
|---|---|---|
| **Report revision** | a re-render of a generated document, with a staleness chain | `reports/revisions.py`, `ReportRevision` |
| **Extraction version** | the identity of a parser's output for unchanged bytes | `material/version.py` |
| **Manuscript revision** | *nothing* — no such concept exists | — |

Phase 2 needs the third one, and it is the one the whole mentor-trajectory
mainline rests on: *who changed this, when, and where in the file*.

Three properties make it different from the other two, and each one breaks
the existing model if the model is stretched to cover it:

1. **A manuscript revision is not a version of a file.** A `.docx` with
   tracked changes contains *several* texts at once — the original, the
   edited, and the intermediate states — and the file's own bytes are a
   single artifact that encodes all of them. A source hash names the file;
   it does not name which text within it.
2. **A change has an author and a time, and both may be absent.** Word
   permits `w:ins` and `w:del` with no `w:author` and no `w:date`. The
   design's rule is that a missing author is `UNKNOWN` and is never filled
   in.
3. **A change is anchored by XML structure, not by page and line.** There is
   no page in a Word document. The anchor is a character range inside a
   paragraph, inside a body, in a named part.

## The concrete problem this creates

The design's data contract (§5 of the execution spec) wants a
`DocumentSpan` carrying `location`, `original_xml_ref`, `text_hash` and
`parser_version`, and a `RevisionEvent` carrying `before_span`,
`after_span`, `author_raw_private`, `timestamp_optional`, `source_xml_ref`
and `confidence`.

Every one of those fields has to survive a round trip: **a change recorded in
Phase 2 must be clickable back to the exact place in the original file that
produced it.** The design's §2 exit condition for the first Phase 2 gate is
"every change can be opened in the original DOCX", and the first gate's stop
condition is "the original bytes changed, a comment was swallowed, or an
unauthorised file was readable".

So the question this ADR answers is narrow and structural:

> **What is the address of a change inside a Word document, and how is it
> stored so that it still resolves after the file is re-parsed, after the
> parser changes, and after the document is edited again?**

## Alternatives

### A. Treat the DOCX as a text source and diff the accepted text

Unzip, accept all revisions, produce plain text, diff two versions.

**Rejected.** It answers a question nobody asked. The design's thesis is
that the *process* is the value — "who found what problem, why they changed
it, whether it worked". Accepting the revisions first destroys the two things
that carry the process: the author, and the fact that a change happened at
all. A diff of accepted text cannot distinguish "the advisor deleted this
sentence" from "the advisor rewrote this sentence" from "the advisor moved
this sentence". It also cannot distinguish a change from text that was
always there.

This is not hypothetical. The upstream study of Docling records the same
failure at the pinned SHA (`docs/research/upstream-study/docling.md`): a
deleted run holds its text in `w:delText` rather than `w:t`, `Run.text`
reads empty, and the filter drops it — so **the text an advisor deleted
never reaches the document model at all.**

### B. Store the file's bytes and re-derive everything on demand

Store the DOCX; re-parse it whenever a change is displayed.

**Rejected as the default, for the reason ADR-0009 already settled.** A
locator that resolves by re-parsing means correctness depends on the
installed parser reproducing byte-identical output to whatever ran before,
and a parser change silently re-points every anchor. ADR-0009's answer was
to store the extracted text keyed by content hash *and extraction version*,
so that re-extraction becomes a comparison rather than a requirement. Phase 2
inherits that answer and applies it to revision events: the *derived* facts
are stored; the bytes stay read-only and untouched.

### C. Store the events, and anchor them by character offsets into the *accepted* text

Extract the accepted text once, store it, and give each event an offset
range into it.

**Rejected.** It has the same fatal property as A — the deleted text is not
in the accepted text, so a deletion has no span to point at — and it adds a
second failure mode: offsets into a derived string break whenever the
accepted text is re-derived. The design requires that a deletion be
locatable, and a deletion has no characters in the accepted text.

### D. Anchor by XML path into the original part, plus a content hash of the anchored text

Store, for each event, the part it came from (`word/document.xml`), an XML
path to the element, the character range within that element's text, and a
hash of the anchored text.

**Chosen.** It is the only one of the four that satisfies all three
properties:

- the **element path** survives re-parsing, because it names structure
  rather than content;
- the **text hash** detects drift — if the anchored text no longer hashes to
  what was recorded, the anchor is stale and says so, exactly as ADR-0009's
  stored text does;
- the **character range** locates the change inside the element, which is
  what a user clicking a comment needs.

### E. Store the whole XML subtree of each event

**Rejected.** It is lossless and it is unbounded: a revision event's
subtree can be a paragraph, and a document with a thousand tracked changes
would store a thousand paragraphs. It also makes every re-parse a
comparison of trees rather than a comparison of spans, and the tree's shape
is the least stable thing about it — Word rewrites run boundaries freely.
The element path plus the range plus the hash is the same information with
a stable reference.

## Decision

### D1 — A manuscript version is a node in a graph, not a row in a line

`PaperVersion` is a node. `VersionEdge` is a directed edge with a `source`
of `evidence | human | model`, a `confidence`, `evidence_spans` and an
`accepted_by`.

**A version graph, never a version list.** The design is explicit: a file
named `最终版2.docx` is not thereby newer than `投稿版.docx`, and the
teacher's process contains **parallel branches** — the student sent two
different revised drafts and the advisor replied to both. A chain cannot
represent that, and a chain would force the system to invent an order it
does not have.

**The order is never inferred from a filename.** The design's rule —
*"文件名不意味着它一定比另一个更新；时间顺序不确定时，应让学生确认"* — is
implemented by making `VersionEdge` carry `source` and `accepted_by`, and
by requiring a `human` edge before a version is treated as settled. An
`UNRESOLVED` state is a first-class value, not an error.

### D2 — A revision event is an observation with three evidence grades

Every event carries `observed | inferred | human_verified`.

- **`observed`** — read from the file's XML. A `w:ins` by "李老师" dated
  2026-03-02 with the text "补充对照组" is observed.
- **`inferred`** — a guess. "This deletion was *because* the innovation was
  unclear" is inferred unless a comment says so.
- **`human_verified`** — a person confirmed it.

**The distinction is the phase's scientific core and it is not negotiable.**
The design: *"Word 中一段文字由谁删除，可以在保留修订元数据的情况下得到证据；
但'导师删除它是因为创新点不明确'，如果没有批注或其他证据，就只能是推断，
而不是事实。"*

### D3 — Missing metadata is `UNKNOWN`, never filled in

A `w:ins` with no `w:author` yields `author_raw_private = None` and
`author_status = UNKNOWN`. A `w:ins` with no `w:date` yields
`timestamp_optional = None` and `timestamp_status = UNKNOWN`.

This extends the project's existing discipline rather than inventing one:
`SourceReadability` already separates "we could not look" from "there was
nothing there" (`sources/source.py:104`), and `CheckOutcome.INDETERMINATE`
already exists so that "I don't know" is not coerced into a boolean
(`evidence/states.py:174-192`, whose docstring warns that `outcome != FAIL`
turns "I don't know" into "yes").

**A missing author is never inferred from context.** Not from the document's
core properties, not from the file name, not from the fact that the change
is stylistically different. The design names this case explicitly — *"文档
属性无日期"* is in the §7 negative list — and the record must show it as
unknown.

### D4 — Three views are produced, and only two of them are content

For each parsed version:

| View | What it is | Is it citable? |
|---|---|---|
| **Revision-preserving** | the full event stream, with insertions, deletions, moves and comments | **yes** — this is the source of truth |
| **Accepted** | the text as if every revision were accepted | yes, as *that version's* text |
| **Rejected** | the text as if every revision were rejected | yes, as *that version's* original |

**The accepted and rejected views are derived, not stored as the truth.** A
derived text is a convenience for reading; it is not where a revision event
lives, because the deleted text does not exist in it (§C above).

### D4a — The view is part of the address, and that is what gives the deleted text one

**Added by LC-P2-07's implementation, 2026-10-29.** D4 names two texts, and
this is the consequence that was not visible until the reader was written.

**The same character range means different characters in the two views**, so
an address that did not say which view it was in would be ambiguous — and
an ambiguous address is not an address. So the view is a **field of the
locator**, and it is in the rendered key with everything else.

**This is also the answer to "what addresses the deleted text".** The
deleted text is not in the accepted view at all, so no range there could name
it — which is why a reader that works in one view cannot cite a deletion at
all. Under D4a, a `w:del` element's text **in the rejected view** is
exactly the deleted text, and that is the locator the deletion event
carries. One rule covers every case:

| The addressed element | The view | Its text |
|---|---|---|
| a paragraph | accepted | the paragraph as it now reads |
| a `w:ins` element | accepted | the inserted text |
| a `w:del` element | rejected | the deleted text |

**Two locators for one element in the two views are different addresses**,
and they resolve to different text — which is correct, because they *are*
different text. The consequence for the store is that `view` is a column and
a key component, and a row that names a third view is refused.

### D5 — A change is anchored by part, element path, range and hash

A `RevisionEvent` carries, at minimum:

```
part            word/document.xml | word/comments.xml | word/footnotes.xml | …
element_path    the path of the w:ins / w:del / w:comment element in that part
char_start      offset into the element's concatenated text
char_end        offset into the element's concatenated text
text_sha256     hash of the anchored text at record time
parser_version  the extraction version, derived like material/version.py does
```

`text_sha256` is what makes drift detectable: if the anchored text no longer
hashes to what was recorded, the anchor is **stale**, and a stale anchor is
reported as stale rather than silently re-pointed. This is ADR-0009's
mechanism applied one level down.

**`parser_version` is derived from the parser's own source**, exactly as
`material/version.py:78` `derive_extraction_version` does — so changing the
parser changes the version without anyone remembering to bump a constant, and
a re-parse of unchanged bytes under an unchanged parser is provably the same
parse.

### D6 — The original bytes are read-only and never rewritten

The parsed DOCX is opened for reading. Nothing writes to it, nothing
"accepts" revisions in place, and no normalising rewrite is performed. The
byte hash is recorded before parsing and verified after.

**No "accept all revisions" operation exists in Phase 2.** It is a
destructive transformation that produces a different document, and it is the
one operation the design's stop condition is about ("*原始字节改变*"). The
first-party docx skill ships an `accept_changes.py` that does exactly this
via a LibreOffice macro; it is a tool for producing a view, and **using it on
an original is the failure mode**, not a feature.

### D7 — A `DOCX` source kind and a `DOCX` locator kind are added, and both are closed

`SourceKind` gains `DOCX`; `LocatorKind` gains a kind addressed by part,
element path and character range.

Both enumerations are closed by design (`sources/source.py:88`,
`sources/locators.py:65`), and Phase 2 adds members rather than widening
them, so the CHECK constraint on `source_anchors.locator_key` keeps meaning
"this locator names something that can exist".

**This is not a small addition.** `SourceKind.OTHER` today exists for files
that "can be inventoried and hashed, just not cited" — so a Word file enters
the store today and cannot be addressed. Making DOCX addressable means the
report path's link check can resolve a DOCX citation, and that check is
load-bearing: a locator that can be written but not resolved would put a
citable claim on an address that resolves to nothing.

### D8 — A new table, not an extension of the report revision chain

`PaperVersion`, `VersionEdge`, `DocumentSpan` and `RevisionEvent` are new
tables. `ReportRevision` is not extended to cover manuscripts.

The two "revisions" answer different questions, and a table where "revision
3" means two things is a table nobody can read. See the reuse matrix §4.1.

## Upstream evidence (reference only)

| Project | SHA | What was observed | Licence |
|---|---|---|---|
| Docling | `8f7ae54409583908f06a2172d260e71b964cc4dd` | `docling/backend/msword_backend.py:2053` — deleted runs read empty and are filtered out; insertions not distinguished from author text; comments linked at paragraph granularity | MIT (verified in `LICENSE`) |
| docx2python | `66b1ae3e24ffa7040ed5244490ce2872ac2e86bb` | no `w:ins`/`w:del` handling anywhere in the tree; `docx_output.py:408-427` returns `[]` for the whole comment set when range and element counts differ | MIT (verified in `LICENSE.txt`) |
| arXivEdits | `113913d68522c1c8428d8e191d5c9bed633da6ce` | BERT+CRF alignment requiring CUDA; `diff_match_patch` character-offset edit extraction over plain strings — no author, no date | **none declared in the tree** |
| XtraGPT | `9f4be5c69878b16b5836a3769745bd190b585572` | instruction-conditioned revision; weights asserted under MG0-2.0 in the README with **no LICENSE file shipped** | **not established** |

Full records: `docs/research/upstream-study/`.

**No upstream code is copied.** The DOCX parser is written against ECMA-376 /
ISO-IEC 29500. Where upstream informed the *design* — the three-way
decomposition of align → extract → classify, the component-wise evaluation
shape — that is cited as design reference, and the licences above are
recorded because the design says a licence position must be known before a
decision to use anything.

## Risks, tradeoffs and reversibility

**Risk — the anchor path is brittle across Word versions.** Word rewrites
run boundaries and may renumber `w:id`s. Mitigation: the anchor is *not* the
path alone; it is path **plus** text hash, and a hash mismatch reports the
anchor as stale rather than wrong. A path that no longer resolves is a
detectable condition, not a silent corruption.

**Risk — a document may hold no revision metadata at all** (a clean `.docx`
with no track changes). Then the version has **no revision events**, and its
text is its own. That is a first-class state, and it is the "data quality
level C" the design assigns to such material: usable for version alignment,
**not** usable as supervision for advice–response.

**Risk — nested revisions.** Word permits a `w:del` inside a `w:ins`. The
parser must represent nesting, and D5's per-element path does, because the
paths differ. A parser that flattens nesting loses the distinction between
"inserted then deleted" and "inserted".

**Risk — orphan markers.** A `w:commentRangeStart` with no matching end, or
a `w:commentReference` with no matching comment, or a comment element with no
range at all. The upstream study records the failure these produce in
docx2python: the whole comment set disappears with a warning. Phase 2's
rule is the opposite — **each unresolvable marker is reported as
`UNKNOWN` with its reason, and the resolvable ones are still returned.**
The system must be able to say "I found 12 comments and could not place 2
of them", and it must never say "this document has no comments" when it has
twelve.

**Tradeoff — the store grows.** Storing derived events per version is
larger than storing a text extraction. That is the price of a locator that
resolves, and ADR-0009 already paid it once.

**Reversibility.** The schema is additive: new tables, one new `SourceKind`
member, one new `LocatorKind` member. Nothing in Phase 1 is modified except
the two enumerations, and both are additive. Dropping the new tables leaves
Phase 1 exactly as it was.

## Contracts and acceptance tests

| # | Contract | Witness |
|---|---|---|
| C1 | A `w:ins` with an author and a date yields one event carrying both, the anchored text, and the anchored hash | **written** — `test_every_revision_carries_its_kind_text_author_and_date` |
| C2 | A `w:ins` with **no** author yields `author_status = UNKNOWN` and an empty author, and **never** a guessed one | **written** — `test_a_missing_author_or_date_is_unknown_and_never_guessed` |
| C3 | A `w:ins` with **no** date yields `timestamp_status = UNKNOWN` | **written** — the same test |
| C4 | A `w:del`'s text is present in the recorded event, and absent from the accepted view | **written** — `test_every_deletion_text_is_recovered` |
| C5 | The accepted view contains the inserted text; the rejected view contains the deleted text; both are derivable from the same event set | **written** — `test_the_two_views_are_the_texts_adr_0014_names` |
| C6 | Every event's `element_path` resolves back to an element in the original part, and the text at that path hashes to the recorded `text_sha256` | **written** — `test_a_revision_locator_resolves_to_the_revisions_own_text` |
| C6a | **D4a**: a deletion is addressed in the rejected view, and the same element in the two views is two addresses | **written** — `test_a_deletion_is_addressed_in_the_rejected_view`, `test_the_same_element_in_the_two_views_is_two_addresses` |
| C7 | An orphan comment marker yields an `UNKNOWN` event naming the reason, and the other comments are still returned | **written** — `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason` |
| C8 | A nested revision (a `w:del` inside a `w:ins`) yields two events with distinct paths, and the flattening is detectable | **written** — `test_a_revision_nested_inside_another_is_reported_separately` |
| C9 | Parsing leaves the original bytes unchanged; the hash before and the hash after are equal | **written** — `test_reading_does_not_change_the_bytes`, and the stronger `test_the_reader_module_writes_nothing` |
| C10 | A version graph with two parallel branches is representable, and no total order is implied | to be written at LC-P2-08 |
| C11 | Two files with identical names and different bytes are two versions, not one | to be written at LC-P2-06 |
| C12 | A `DOCX` locator resolves through the report's link check, and an unresolvable one is refused rather than cited | **partly written** — the locator resolves (`test_a_revision_locator_resolves_to_the_revisions_own_text`); the link check's own path is **not** — the report's citation machinery has no DOCX case yet |

**Every one of these needs a witness, and the witness must fail for the
property.** A test that fails because of an unrelated encoding or lint matter
is not a witness of the property. That rule is the project's, and this ADR
names the properties so that a later reviewer can mutate each one and check
that the named test goes red.

## Re-evaluation trigger

This ADR is re-opened if **any** of these becomes true:

1. A document model is found in the wild whose revision metadata cannot be
   represented by D5's part + path + range + hash.
2. The anchor path proves unstable across two Word versions in the pilot
   corpus — i.e. the same file re-saved by two Word releases produces
   different paths for the same visible change. Then D5 needs a content-
   addressed fallback, and the measurement in LC-P2-07 must be re-run.
3. A licence review clears an upstream project for code reuse, which would
   change what "write our own parser" costs.
4. The fidelity measurement (LC-P2-07) shows the OOXML-native arm cannot
   beat the text-extraction arms on the properties that matter — which would
   mean the anchor machinery is not earning its cost.
