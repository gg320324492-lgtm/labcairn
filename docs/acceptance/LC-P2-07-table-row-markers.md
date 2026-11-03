# LC-P2-07 — the revision no paragraph holds: the row marker, measured and read

**Date:** 2026-11-03 · **Base commit for the "before" numbers:** `e13b967` ·
**The fix:** `1f1529d` on `claude/reader-row-markers-41cc54` ·
**Measured by:** the executor, on the development machine ·
**Pushed:** no. **Pull request opened:** no (CLAUDE.md: a run is the owner's
call, and one was already in flight on the parent branch).

**What this record is.** `docs/acceptance/LC-P2-07-fidelity-baseline.md`
§5.6 found a defect, wrote down what it was, and **left it unfixed on
purpose** — it said the fix "belongs to its own work order". This is that
work order: the OOXML revision reader (`src/labcairn/material/ooxml.py`)
walked paragraphs, so a tracked change written **outside every paragraph**
was invisible to it. The record here measures how many such changes the real
material holds, fixes the scan, and names what the fix does not reach.

**What the defect was, in the baseline's own words** (§5.6, at `e13b967`):

> a table row's insertion marker (`w:trPr/w:ins`, an empty element
> **outside** any paragraph) is invisible to a scan that walks paragraphs.

---

## 1. The measurement, before the fix

**How it was counted.** A script outside the repository
(`E:\labcairn-local\row-marker-measure\measure.py`) opens every `.docx`,
parses `word/document.xml`, and takes every `w:ins`, `w:del`, `w:moveFrom`
and `w:moveTo` element in the tree — the same "straight from the package"
count §5.6 used. For each of them it re-derives the reader's element path,
then asks whether the reader reported that path. **The reader ran from this
worktree's `src`, not from the editable install**: `PYTHONPATH` pointed at
`E:\LabCairn\.claude\worktrees\reader-row-markers-41cc54\src`, and the
import was proved by printing `labcairn.material.ooxml.__file__`:

| run | `ooxml.py` resolved to |
|---|---|
| "before" | `E:\labcairn-local\row-marker-measure\prefix\src\labcairn\material\ooxml.py` (a copy of `src/` at `e13b967`, taken with `git archive`) |
| "after" | `E:\LabCairn\.claude\worktrees\reader-row-markers-41cc54\src\labcairn\material\ooxml.py` |

The "before" copy is not the checked-out reader: it is the reader **at the
base commit**, extracted so a pre-fix and a post-fix run can be compared on
one machine without moving a branch under a running measurement.

**What was measured.** Every `.docx` in the local materials library — **193
files in five sets**: the owner's UNPUBLISHED manuscript (23 numbered drafts
and 23 review copies), the pilot's first corpus (18), the second corpus (99)
and the two later sets (15 and 15). **The sets are named here by their role
and their file count, and never by their directory names**: a directory name
in that library carries the subject of a manuscript that has not been
published, and this repository is public. The same rule holds for everything
below — no manuscript text, no revision id, no author name, no timestamp from
a file, and no per-comment label; a file is identified only by what it
demonstrates, and only where the demonstration needs it.

| | at `e13b967` | at `1f1529d` |
|---|---|---|
| revision elements in the parts | **4499** | 4499 (the files did not move) |
| events the reader reported | **4498** | **4499** |
| elements the reader never reported | **1** | **0** |
| files where the reader reported fewer than the part holds | **1** | **0** |
| reported events sharing one element path | 0 | 0 |

**The one file.** One review copy of the owner's manuscript — named here by
what it is and not by its file name, since the file names of this manuscript
are not public: the part holds **223** revision elements, the reader reported
**222**. The missing one is:

```
/document[1]/body[1]/tbl[5]/tr[1]/trPr[1]/ins[1]
```

`w:ins`, **no children** (so no text of its own), carrying a `w:id`, an
author and a date — the same three attributes a run-level insertion carries.
It is on the row's properties: Word writes "this row was inserted" there, and
no paragraph contains it, so no paragraph ever reported it.

**And what the invisible markers actually are.** Counting them across all
193 files, the answer is narrow and it is worth stating as a number rather
than as a category:

| shape | elements in the real material |
|---|---|
| `w:trPr/w:ins` — a row's insertion mark | **1** |
| `w:trPr/w:del` — a row's deletion mark | **0** |
| any revision element in a part other than `word/document.xml` | **0** (4499 of 4499 are in the document part) |
| comment range markers (`commentRangeStart/End/Reference`) outside a paragraph | **0** (232 of 232 are inside one) |

The `w:del` counterpart was **checked rather than assumed**: the real
material holds none, but `w:trPr/w:del` is what a row's *deletion* mark is
called — python-docx 1.2.0's `CT_TrPr._tag_seq` (generated from the
ECMA-376 sequence this reader is written against) lists `w:ins` and `w:del`
as siblings in a row's properties. So the scan is fixed for both kinds, and
the `del` arm is witnessed by a built document (§4) because no real file
carries one.

**The same document, read by both readers.** The hand-built document of §4
holds five revision elements. Run against the reader **as it stood at the base
commit** — the extracted `git archive e13b967 src`, not a reconstruction — it
reported **two** of them, `301` (an insertion in a paragraph's run sequence)
and `304` (the paragraph's own mark, `w:pPr/w:rPr/w:ins`); the three row marks
`302`, `303` and `305` were absent. Run against the fixed reader it reports
**five**. That is the defect and the fix in one line, on a document small
enough to read at a glance, and it settles the first of the two points below
by measurement rather than by reading the walk.

**Two things this measurement also settles.** First, a paragraph's *own* mark
(`w:pPr/w:rPr/w:ins`) was already reported before this fix, because the
paragraph scan descends into `w:pPr` — it is only the elements with **no
paragraph ancestor** that were lost, which is why the fix adds a scan instead
of narrowing one. Second, this is the opposite failure from §5.6's:
there the reader reported one element twice, here it reported an element
never.

---

## 2. The fix

`_scan_outside_paragraphs(document_root)` walks the part once with an
explicit stack, carries "am I inside a paragraph" and "am I inside a
revision" as it descends, **stops reporting the moment it enters a
paragraph**, and returns the revision elements it found outside every
paragraph, in document order. `read_document` appends an event for each.

**Why that keeps §5.6's property.** The two scans split the part's revision
elements on one question — *does a paragraph contain this element* — and the
answers are disjoint and exhaustive: every element under some `w:p` is that
paragraph's to report (and the nearest one reports it, which is what §5.6
established), and every element under no `w:p` is the new scan's. One
element, one reporter, one event. The descent still goes *through* a
paragraph's subtree without reporting, because a nested paragraph is a
paragraph and the paragraph loop reaches it on its own.

**What the event carries, and what it refuses to invent.** A row's mark is
an empty element: the event's text is `_text_in(element, view)`, which is
`""` — not the row's cell prose, which belongs to the cells' paragraphs and
is reported by them, once each, as it already was. Its author, date, `w:id`,
part and element path are its own. **`paragraph` is `None`, and
`baseline_start`/`baseline_end` are `None` with it**: there is no paragraph
for the index to name and no baseline text for the coordinate to sit in. An
invented index would claim the change sits in a paragraph it does not sit
in, and a coordinate that names no text is a coordinate nobody can check —
the same rule §5.3's refusals and the `CommentAnchor` design already run on.
The three fields became `int | None` in `RevisionEvent`; nothing else had to
move, because the store's columns are already nullable and
`read_revision_activity` already filters `None` out before it counts the
paragraphs a manuscript touched.

**What the fix does not change.** `derive_extraction_version` hashes the
reader's own source, so the version moved, which is what it is designed to
do: **`38e0d9591c8e2a9a13c913b5f2b5f0f3` at `e13b967`,
`b021d3c3c61fd7fd2e4563db5c7eeba1` at `1f1529d`** (both measured on this
machine; a later change to that file moves it again). A **new** ingestion of
the file that held the marker therefore records 223 rows where it recorded
222. The pilot chain's
existing rows do not move: read-only against
`E:\labcairn-local\pilot-ws\labcairn.db`, `revision_events` holds **2164**
rows with **0** null paragraphs, written by the two parser versions
`d375f3a8…` and `38e0d959…` that were running when they were read — the
chain is written by the reader's version, and this fix does not reach back
into it.

---

## 3. The after numbers, and what moved

Re-measured over the same 193 files with the fixed reader:

- **Every file's event count is the same as before except one.**
  The one review copy that held the row marker went **222 → 223**, which is
  exactly its part's element count. The other 192 files are unchanged at the
  element, event and address level.
- **No previously-visible event disappeared.** 4498 events before; 4499
  after; the 4498 are all still there (the comparison is per file on the
  reader's own element paths).
- **No event duplicated.** Reported addresses are distinct in every file,
  before and after: 0 collisions both ways.
- **The library-wide gap is closed: 0 elements the reader never reports.**

**The synthetic corpus did not move: 30 fixtures, 35 revisions** — counted
again at `1f1529d`, not carried from the baseline. So §2 and §4 of
`LC-P2-07-fidelity-baseline.md` stay the measurement they were, and the arm
numbers in it needed no re-run.

---

## 4. The witnesses, and the mutations

Three cases were added to `tests/test_ooxml_revisions.py` (27 → **30**
cases, counted by collecting the file at the commit, not carried), all reading
one hand-built document that holds **five** revision elements in the places
one can sit: an insertion in a paragraph's run sequence (`w:ins` among the
runs), a paragraph's own mark (`w:pPr/w:rPr/w:ins`), and **three** row marks
(`w:trPr/w:ins`, `w:trPr/w:del`, and a second `w:trPr/w:ins` written with no
`w:author` and no `w:date` at all). The deletion-side row mark is in the
document because the real material holds no instance of it and the shape still
has to be held somewhere; the unnamed one is in the document because the new
scan reads the same two attributes the paragraph scan reads, and the rule
"absent is absent, never guessed" has to be witnessed on the path that was
just added, not only on the one that already had a witness.

| witness | the property |
|---|---|
| `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it` | the row's mark comes back, with its kind, author, date, view and address; its text is `""`; its paragraph and baseline place are `None`; a third row's mark with **no author and no date at all** stays `None` on this path too (the no-guess rule, witnessed where the new code reads the attributes); the cells' prose still stands once in the paragraph list |
| `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph` | the partition runs on the container, not on the element's shape: an empty `w:ins` under `w:pPr` keeps a paragraph index, an empty `w:ins` under `w:trPr` does not |
| `test_a_table_row_marker_is_reported_once_and_not_twice` | one element, one event, over a document read by **two** scans |
| `test_the_reader_reports_each_revision_element_exactly_once` (already there, widened) | the count straight from the part now runs over the hand-built table document too |

**Why the count witness was widened rather than the corpus extended.** §5.6's
lesson is that a witness looping over `FIXTURES` can only catch what the
corpus holds — so the shape has to be inside the count. It cannot be inside
the corpus *as it is declared*: the fixture model anchors every revision in
a paragraph (`revision_range` derives a range from a paragraph's baseline
text), and giving it a paragraph-less revision would mean re-opening the
gold machinery that `tests/evaluation_docx_fidelity.py` scores the
comparison arms against — the arms' numbers in §4 of the baseline are the
30-fixture corpus, re-measured, and this work order has no licence to change
what they measure. The count therefore reads the hand-built document
alongside the corpus, which puts the shape in the witness without touching
the measured corpus. Re-homing it into the corpus is named in §6.

**The mutations.** Each was applied to a **copy** of `src/` outside the
repository (`E:\labcairn-local\row-marker-measure\mut\src`) and run through
`PYTHONPATH`, so the measured tree never changed while a measurement was in
flight — the rule this project learned the hard way (CLAUDE.md: a run showing
a failure is re-measured before it is believed, and a tree edited mid-run
invalidates the run). Each row is `pytest tests/test_ooxml_revisions.py`
(30 cases) against that copy, `--basetemp` outside the repository.

| # | The mutation | What went red |
|---|---|---|
| A | **not a reconstruction: the reader as it stood at the base commit.** `git archive e13b967 src` was extracted and used unchanged, so the witnesses ran against the behaviour that had the defect | `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph`, `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once` — **4 failed, 26 passed** |
| B | one row marker, two events (the element appended twice to the scan's found-list) | `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once` — **2 failed, 28 passed** |
| C | the row's mark is given paragraph `0` and baseline `0..0` instead of `None` | `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph` — **2 failed, 28 passed** |
| D | the event quotes borrowed prose instead of the marker's own empty text | `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it` — **1 failed, 29 passed** |
| E | the new scan drops its "a paragraph owns this element" guard, so the §5.6 double-read comes back | `test_every_revision_in_the_corpus_is_reported`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_a_missing_author_or_date_is_unknown_and_never_guessed`, `test_a_revision_nested_inside_another_is_reported_separately`, `test_a_revision_inside_a_drawing_textbox_is_reported_once`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph`, `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once`, `test_the_derived_revision_event_id_names_one_change_per_address` — **9 failed, 21 passed** |

**Why E is in the list at all.** The work order's constraint was to keep
§5.6's property while removing the blind spot, and a mutation that restores
the double-read is how that is checked rather than asserted: the drawing's
text-box witness and the corpus-wide id witness went red with the new ones.
**An earlier form of B was wrong and is recorded as a failure of method:** it
pushed the element back onto the walk's stack, which never terminates. That
run was stopped; a mutation that hangs is not a witness that failed, so it
was rewritten into the two-appends form, which does terminate and does bite.

Mutation B was first written as "push the element back on the stack", which
loops forever; that attempt is recorded because it is the kind of mutation
that *looks* like a red test and is in fact a hung run — it was stopped and
rewritten into the two-appends form above, which terminates.

**The rest of the tree.** Everything that consumes a revision event was run
against the widened types: `tests/test_ooxml_revisions.py`,
`tests/test_docx_fixture_corpus.py`, `tests/test_version_store.py`,
`tests/test_feedback_events.py`, `tests/test_guidance_distillation.py`,
`tests/test_analysis_report_revisions.py` — **276 passed**. `ruff check .`,
`ruff format --check .` (423 files) and `mypy` (383 files, `--strict` from
`pyproject.toml`) are clean. The one known red is
`tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`,
which the parent branch owes a runner: two of its heavy test files changed
there, and no cost may be invented locally. Nothing was regenerated.

---

## 5. What this reaches and what it does not

**Downstream, checked rather than assumed.** `papers/revisions.py` copies
`paragraph` and the baseline pair into columns already declared nullable;
`application/chain.py:read_revision_activity` filters `None` before it
counts paragraphs touched, so a row mark adds a revision event without
pretending to touch a paragraph. No id moved: re-deriving the stored ids of
a document whose only row mark was previously invisible changes nothing
about the other rows, because the id is the version, the part and the path —
and this fix adds a path, it does not renumber one.

**One thing this fix makes visible and does not classify.** The chain counts
an event by `classify_revision_change(text, element_path)`
(`src/labcairn/papers/chain.py`), whose mark steps are `{rPr, pPr}`. Measured
at this commit, not reasoned from the source:

```
/document[1]/body[11]/tbl[2]/tr[1]/trPr[1]/ins[1]  ->  formatting_only
/document[1]/body[11]/tbl[2]/tr[1]/trPr[1]/del[1]  ->  formatting_only
/document[1]/body[3]/p[1]/pPr[1]/rPr[1]/ins[1]     ->  empty_marker
/document[1]/body[1]/p[1]/ins[1]   (text "")       ->  formatting_only
```

**Two things follow, and the second one keeps this honest.** A row's mark is
*counted as a change* and never discarded, which is right: a row was
inserted. What is wrong is the name — `formatting_only` reads "a run whose
formatting changed", and a row's mark changed no run's formatting. But the
same bucket already holds an empty insertion in a run sequence (the last line
above), so **this is not damage this fix did; it is a hole in the vocabulary
that the fix made reachable**. Widening `_MARK_STEPS` to `trPr` would put a
row's mark in `empty_marker` instead, which is worse — an `empty_marker` is
the classifier's name for "a cursor left behind, and it carries no
judgement", and a row's insertion carries a judgement. What the four names
need is a fifth, and that is `papers/chain.py`'s decision, not this order's:
the file belongs to another window today, and CLAUDE.md's rule is that a
window which needs another's file says so rather than reaching for it. It is
named here so it is a listed gap and not a silently-wrong number, and it is
not yet live data: the pilot chain holds no such row (0 null paragraphs, §2),
because the reader never reported the marker that would have made one.

**And a stale sentence in a file this order may not edit.** The docstring of
`_revision_event_id` (`src/labcairn/papers/revisions.py:140-142`) still says
the reader reports each revision element "from the paragraph that contains
it". After this fix that is the *majority* rule, not the whole rule: some
elements are reported by the document scan. It is a sentence, not a
behaviour — the uniqueness the id rests on is unaffected, and
`test_the_reader_reports_each_revision_element_exactly_once` is what holds
it. It is named here for whoever owns that file next.

---

## 6. Not fixed, and why

| the gap | the reason it stands |
|---|---|
| A row mark is now an event, and the row's *content* is not one | The cells' paragraphs are reported as text and their own tracked changes are reported; the marker itself holds nothing. Folding a row's prose into its marker would be a second copy of text the reader already reports (§4 mutation D shows the witness refuses it). |
| a row mark is counted under the name `formatting_only` | The count is right — it is a change, not a cursor — and only the four-name vocabulary is wrong, because `empty_marker` means "carries no judgement" and a row's insertion does. The fifth name is `papers/chain.py`'s, and that file is another window's today. Measured in §5, named here, not reached. |
| Revisions in parts other than `word/document.xml` | Measured: **0** revision elements outside the document part in all 193 real files, and 0 comment markers outside a paragraph. A latent gap, not a live loss, and the reader's part list is unchanged by this order. |
| The shape is not a synthetic corpus fixture | The corpus's gold model derives a revision's range from a paragraph's baseline text, so it cannot declare a paragraph-less revision without reopening the harness the §4 arm numbers are measured with (§4). The count witness holds the shape instead. Moving it into the corpus — and re-measuring the arms against 31 fixtures — is a work order of its own. |
| Shard costs for this change | `.github/ci-shards.json` records costs measured on a runner at `49e81f2`; `tests/test_ooxml_revisions.py` grew 3 cases and 205 lines here, so the coverage witness is red until a run re-measures it. `python .github/remeasure_shards.py <run-id>` is the fix, and it needs the run the owner batches. |

---

## 7. How to reproduce

```bash
# the before/after count over the real material (outside the repository)
cd E:/labcairn-local/row-marker-measure
PYTHONIOENCODING=utf-8 \
PYTHONPATH=E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54/src \
  python measure.py "E:/labcairn-local/materials-library" > after.json 2> after.err

# the same over the reader as it stood at the base commit
git -C E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54 archive e13b967 src \
  | tar -x -C E:/labcairn-local/row-marker-measure/prefix
PYTHONPATH=E:/labcairn-local/row-marker-measure/prefix/src \
  python measure.py "E:/labcairn-local/materials-library" > before.json 2> before.err

# the witnesses (30 cases), and the five mutations A-E
# (A is run against the extracted pre-fix copy above, not against this tree)
TEMP=E:/labcairn-local/tmp TMP=E:/labcairn-local/tmp \
PYTHONPATH=E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54/src \
  python -m pytest tests/test_ooxml_revisions.py tests/test_docx_fixture_corpus.py \
    --basetemp=E:/labcairn-local/tmp/bt-rowmark -p no:cacheprovider -q
```

`measure.py`, its JSON outputs and the extracted `e13b967` copy live outside the repository,
alongside the material they read: the repository is public and this
manuscript is not published. The scripts read it and write nothing to it;
the pilot database was opened `mode=ro`.
