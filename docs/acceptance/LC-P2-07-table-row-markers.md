# LC-P2-07 — the revision no paragraph holds: the row marker, measured and read

**Date:** 2026-11-03 · **Base commit for the "before" numbers:** `e13b967` ·
**The fix:** `1f1529d`, corrected and re-measured at `82d7161`, re-measured again
after the parent branch was merged in at `5984f1e` (parent tip `eff6561`, which
carries `bb8f8f6`) ·
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

Three cases were added to `tests/test_ooxml_revisions.py` by this order
(27 at the base commit → 30 at `1f1529d`; **32** on this branch now, the parent
branch's identity work adding two more — counted by collecting the file at the
merge commit, not carried), all reading
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

**The mutations.** Each was applied to a **copy** of the tree outside the
repository (`E:\labcairn-local\row-marker-measure\mut\`) and run through
`PYTHONPATH`, so the measured tree never changed while a measurement was in
flight — the rule this project learned the hard way (CLAUDE.md: a run showing
a failure is re-measured before it is believed, and a tree edited mid-run
invalidates the run). **The copy needs `migrations/` beside it**: `REPO_ROOT`
in `db/migrations.py` is derived from the package location, so a copy of
`src/` alone makes the writer's 52 database fixtures error out — and an error
count is not a witness result. The first battery run of this section had
exactly that bug in its own harness, and the numbers below are the re-run with
`migrations/` copied too. Each row prints the `ooxml.py` it actually imported.

**Every row is `pytest tests/test_ooxml_revisions.py
tests/test_docx_fixture_corpus.py tests/test_version_store.py` — 191 cases —
against that copy, `--basetemp` outside the repository.** The writer's file is
in the set because these mutations move what the writer stores, and because
collecting it first is what keeps the parent branch's import cycle (see §5)
from reddening three identity witnesses for a reason that is not the mutation.
The baseline for the set, on the merged tree with no mutation: **191 passed**.

| # | The mutation | What went red |
|---|---|---|
| A | **not a reconstruction: the reader as it stood at the base commit.** `git archive e13b967 src migrations` was extracted and used unchanged, so the witnesses ran against the behaviour that had the defect | my four witnesses — `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph`, `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once` — **plus five witnesses that belong to the identity work now on this branch** (`test_the_revision_event_id_carries_an_occurrence_per_change_at_one_address`, `test_the_revision_event_id_is_re_derivable_not_position_dependent`, and three in `test_version_store.py`), which fail here because the extracted tree predates them and takes no `occurrence` argument. **9 failed, 182 passed** |
| B | one row marker, two events (the element appended twice to the scan's found-list) | `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once` — **2 failed, 189 passed** |
| C | the row's mark is given paragraph `0` and baseline `0..0` instead of `None` | `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph` — **2 failed, 189 passed** |
| D | the event quotes borrowed prose instead of the marker's own empty text | `test_a_table_row_marker_is_reported_though_no_paragraph_holds_it` — **1 failed, 190 passed** |
| E | the new scan drops its "a paragraph owns this element" guard, so the §5.6 double-read comes back | nine in the reader's and corpus's files — `test_every_revision_in_the_corpus_is_reported`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_a_missing_author_or_date_is_unknown_and_never_guessed`, `test_a_revision_nested_inside_another_is_reported_separately`, `test_a_revision_inside_a_drawing_textbox_is_reported_once`, `test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph`, `test_a_table_row_marker_is_reported_once_and_not_twice`, `test_the_reader_reports_each_revision_element_exactly_once`, `test_the_derived_revision_event_id_names_one_change_per_address` — **and seven in the writer's**: `test_a_revision_event_carries_the_text_and_the_place_of_the_change`, `test_a_revision_with_no_author_or_date_is_unknown_and_never_guessed`, `test_recording_the_same_version_twice_is_the_same_rows`, `test_a_listing_drops_the_events_of_denied_material`, `test_the_four_kinds_of_change_are_told_apart`, `test_the_application_layer_reads_the_revision_events_and_the_activity`, `test_a_comment_and_a_change_in_one_manuscript_are_two_facts`. **16 failed, 175 passed** |

**Why E is in the list at all.** The work order's constraint was to keep
§5.6's property while removing the blind spot, and a mutation that restores
the double-read is how that is checked rather than asserted: the drawing's
text-box witness and the corpus-wide id witness went red with the new ones.
**An earlier form of B was wrong and is recorded as a failure of method:** it
pushed the element back onto the walk's stack, which never terminates. That
run was stopped; a mutation that hangs is not a witness that failed, so it
was rewritten into the two-appends form, which does terminate and does bite.

**The rest of the tree.** Everything that consumes a revision event was run
against the widened types, on the merged tree, as one command —
`tests/test_ooxml_revisions.py`, `tests/test_docx_fixture_corpus.py`,
`tests/test_version_store.py`, `tests/test_feedback_events.py`,
`tests/test_guidance_distillation.py`,
`tests/test_guidance_revision_distillation.py`,
`tests/test_workbench_live_service.py` and
`tests/test_analysis_report_revisions.py`: **304 passed, 0 failed**. The first
time this paragraph was written it named a test file that does not exist; the
names above are the directory's, listed from `tests/` rather than recalled.
`ruff check .`, `ruff format --check .` and `mypy` (`--strict`, over every
file `pyproject.toml` names) are clean at each commit. The ledger counts are
§8. The one red this branch carries is
`tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`:
the shard costs were measured at `bb8f8f6aaab46f0285f03b3ea511b8668b78ee45`
and a heavy test file changed since, so it wants a runner and no cost may be
invented locally. Nothing was regenerated.

---

## 5. What this reaches and what it does not

**Downstream, checked rather than assumed.** `papers/revisions.py` copies
`paragraph` and the baseline pair into columns already declared nullable;
`application/chain.py:read_revision_activity` filters `None` before it counts
paragraphs touched, so a row mark adds a revision event without pretending to
touch a paragraph.

**No stored id moves, and that was measured against the rule the branch runs
now.** The identity is `(version, part, element_path, occurrence)` since the
identity work landed, and the writer numbers each address in the order the read
events arrive, so an appended row mark could in principle renumber the changes
that follow it. It does not, because the number is **per address** and a row's
mark is the first and only change at its own. Measured, not argued: the
revision addresses of 64 real files (the manuscript's 46 and the pilot's first
corpus's 18) were dumped from the reader at the base commit and from the fixed
reader, then fed through the branch's own `_revision_event_id` with the
writer's own counting:

| | result |
|---|---|
| files whose id set differs | 1 — the one that held the invisible marker |
| ids that disappeared | **0** (222 of 222 in that file, unchanged, byte for byte) |
| ids added | 1 |
| addresses carrying two events in any of the 64 files | **none** |

Reproduce it with `dump_addresses.py` (once per reader) and `ids_stability.py`
(§7).

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

**A claim this record made, and the merge withdrew.** The first version of
this section named a sentence in `_revision_event_id`'s docstring — that the
reader reports each element "from the paragraph that contains it" — as stale
wording for whoever owned that file next. The parent branch had already
rewritten that docstring when the merge landed, and what it says now is
`identity = (version, part, element_path, occurrence)` plus "the reader's own
uniqueness keeps every address at `occurrence == 0`". So the naming is dropped:
**the claim the docstring rests on is exactly the property measured in §5
above** — 0 addresses carrying two events over 64 real files, and every stored
id byte-stable — and this order owes that file nothing.

**What the merge did surface, in a file this order may not edit.** An import
cycle, introduced upstream at `5f1e790` ("A rule may be learned from a tracked
change, not only from a comment") when `read_paragraph_context` moved into
`papers/revisions.py`: `labcairn.papers.revisions` imports
`labcairn.application.consent`, whose package `__init__` imports
`labcairn.application.chain`, which imports `labcairn.papers.revisions` back.
Measured, on a clean `git archive eff6561` of the parent branch *alone* — not
on anything this order touched:

```
$ python -c "import labcairn.papers.revisions"
ImportError: cannot import name 'read_paragraph_context' from partially
initialized module 'labcairn.papers.revisions'
```

It works when the application package is imported first. The visible symptom
is a test run that looks like a product failure and is not: collecting
`tests/test_ooxml_revisions.py` **by itself** turns three identity witnesses red
(`test_the_derived_revision_event_id_names_one_change_per_address`,
`test_the_revision_event_id_carries_an_occurrence_per_change_at_one_address`,
`test_the_revision_event_id_is_re_derivable_not_position_dependent`) with that
`ImportError`; add a file that imports the application layer and all three go
green. CI does not see it because the shard that holds the reader's tests
collects `tests/test_application_layer.py` first — the order is masking the
defect, not fixing it. **This is reported to the parent session rather than
repaired here**: `papers/` and `application/` are outside this order's files,
and a cycle that only shows when a module is imported first is exactly the
kind of thing that must not be quietly patched from a window that came in for
a row marker. It is also why every mutation row in §4 lists the file set it
was run with.

---

## 6. Not fixed, and why

| the gap | the reason it stands |
|---|---|
| A row mark is now an event, and the row's *content* is not one | The cells' paragraphs are reported as text and their own tracked changes are reported; the marker itself holds nothing. Folding a row's prose into its marker would be a second copy of text the reader already reports (§4 mutation D shows the witness refuses it). |
| a row mark is counted under the name `formatting_only` | The count is right — it is a change, not a cursor — and only the four-name vocabulary is wrong, because `empty_marker` means "carries no judgement" and a row's insertion does. The fifth name is `papers/chain.py`'s, and that file is another window's today. Measured in §5, named here, not reached. |
| Revisions in parts other than `word/document.xml` | Measured: **0** revision elements outside the document part in all 193 real files, and 0 comment markers outside a paragraph. A latent gap, not a live loss, and the reader's part list is unchanged by this order. |
| The shape is not a synthetic corpus fixture | The corpus's gold model derives a revision's range from a paragraph's baseline text, so it cannot declare a paragraph-less revision without reopening the harness the §4 arm numbers are measured with (§4). The count witness holds the shape instead. Moving it into the corpus — and re-measuring the arms against 31 fixtures — is a work order of its own. |
| Shard costs for this change | `.github/ci-shards.json` records costs measured on a runner at `bb8f8f6aaab46f0285f03b3ea511b8668b78ee45` (the parent branch's re-measurement, now merged in). `tests/test_ooxml_revisions.py` grew 3 cases and 305 lines on top of that, so the coverage witness is red until a run re-measures it. `python .github/remeasure_shards.py <run-id>` is the fix, and it needs the run the owner batches. Nothing here was regenerated. |
| A row mark's own `w:id` is not a stable identifier | Not this order's claim to make: the baseline records that Word renumbers `w:id` on every save (the corpus's `KNOWN_GAPS`), so the event carries `element_id` as the file states it and nothing downstream keys on it. |

---

## 7. How to reproduce

```bash
cd E:/labcairn-local/row-marker-measure

# the "after" count over the real material, with the fixed reader
PYTHONIOENCODING=utf-8 \
PYTHONPATH=E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54/src \
  python measure.py "E:/labcairn-local/materials-library" > after.json 2> after.err

# the "before" count: the reader as it stood at the base commit, extracted.
# `migrations` comes along because db/migrations.py derives REPO_ROOT from the
# package location, and a copy of src/ alone cannot run the writer's tests.
git -C E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54 archive e13b967 src migrations \
  | tar -x -C E:/labcairn-local/row-marker-measure/prefix
PYTHONPATH=E:/labcairn-local/row-marker-measure/prefix/src \
  python measure.py "E:/labcairn-local/materials-library" > before.json 2> before.err

# the id-stability check of §5: dump each file's addresses per reader, then
# derive ids with THIS branch's _revision_event_id and the writer's counting
PYTHONPATH=.../prefix/src python dump_addresses.py addr_before.json <two corpus dirs>
PYTHONPATH=.../reader-row-markers-41cc54/src python dump_addresses.py addr_after.json <same dirs>
PYTHONPATH=.../reader-row-markers-41cc54/src python ids_stability.py addr_before.json addr_after.json

# the witnesses and the writer's tests together — 191 cases, the set §4 used.
# test_version_store.py is not padding: it is what imports the application
# layer first, which keeps the import cycle of §5 from reddening three
# identity witnesses that have nothing to do with a row mark.
TEMP=E:/labcairn-local/tmp TMP=E:/labcairn-local/tmp \
PYTHONPATH=E:/LabCairn/.claude/worktrees/reader-row-markers-41cc54/src \
  python -m pytest tests/test_ooxml_revisions.py tests/test_docx_fixture_corpus.py \
    tests/test_version_store.py \
    --basetemp=E:/labcairn-local/tmp/bt-rowmark -p no:cacheprovider -q

# the five mutations, each on a copy of the tree, each printing the ooxml.py
# it really imported
bash E:/labcairn-local/row-marker-measure/run_mutations.sh
```

`measure.py`, `dump_addresses.py`, `ids_stability.py`, `run_mutations.sh`,
their JSON outputs and the extracted base-commit copy all live outside the
repository, alongside the material they read: the repository is public and
this manuscript is not published. The scripts read the material and write
nothing to it; the pilot database was opened `mode=ro`.

**Two harness traps this section exists to record.** First: a mutation battery
whose `PYTHONPATH` silently goes empty does not fail — it runs the *editable
install*, which is the main checkout, and prints a clean-looking result about
the wrong tree. Every row of §4 therefore prints the `ooxml.py` it imported;
one of the earlier battery runs was discarded precisely because a quoting
mistake did that and made five different mutations return five identical
failure lists. Second: `python -I` cannot be used here, because it drops
`PYTHONPATH` — and neither can a run that leaks `PYTHONPATH` into
`tests/test_no_reference_leakage.py::test_wheel_installs_clean_and_imports`,
whose clean-room subprocess would then resolve `labcairn` to this worktree
instead of the built wheel.

---

## 8. The state of the tree at this record

| | |
|---|---|
| Branch | `claude/reader-row-markers-41cc54`, based on `e13b967`, with the parent branch `eff6561` (carrying `bb8f8f6`) merged at `5984f1e` |
| The fix | `1f1529d` — `src/labcairn/material/ooxml.py`, +3 witnesses in `tests/test_ooxml_revisions.py` |
| This record | `82d7161` — the record, the baseline's corrections, and the unnamed-marker assertion |
| Pushed / PR / CI | **none**, on the parent's instruction and CLAUDE.md §1.5 |
| Reader's test file | 32 cases (27 at the base commit, +3 here, +2 from the identity work) |
| Verification set | 191 cases (reader + corpus + writer) green; 304 cases green over the eight files of §4 |
| Ledger `e13b967 → 82d7161` | 3117 → 3120 test functions, **LOST -- none**, ADDED 3 |
| Ledger across the merge | 3120 → 3202, ADDED 85, **LOST 3** — and the three are not this merge's doing: `tests/test_threat_model.py`'s two were removed upstream by `37591c7` (the workbench now *does* read its event stream, and the replacements `test_the_workbench_reads_the_event_stream` and `test_the_api_selects_a_task_and_the_document_says_so` are present), and `tests/test_analysis_report_render.py::test_the_two_container_forms_are_not_byte_reproducible` was removed by `521e481` once the DOCX became reproducible. The ledger is what makes "three fewer" a statement rather than a surprise. |
| Static checks | `ruff check .`, `ruff format --check .` and `mypy` (`--strict`) clean |
| Known red | `test_ci_shard_coverage::test_the_costs_belong_to_the_tree_they_were_measured_on` — costs measured at `bb8f8f6…`, a heavy test file changed since; it wants a runner, and no cost was invented locally |
| Not run | the whole suite. It is the review gate's measurement, not this order's, and the shard witness above is red on this branch until a runner re-measures |
| Pilot database | read-only: `revision_events` 2164 rows, 0 null paragraphs, parser versions `d375f3a8…` and `38e0d959…` — untouched by this fix, which changes what a *new* read reports |
| `docs/RELEASE-NOTES.md` | **not edited** — outside this order's files. Whoever batches the push may want a line for a defect the baseline named and this order closed. |

