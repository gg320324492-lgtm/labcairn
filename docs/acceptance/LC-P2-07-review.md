# LC-P2-07 — independent review of the fidelity baseline and the reader

**Record reviewed:** `docs/acceptance/LC-P2-07-fidelity-baseline.md` (the DOCX
revision-fidelity baseline, the reader `src/labcairn/material/ooxml.py`, the
double-read fix of §5.6 and corpus fixture 30), as it stands in this branch.
**The tree reviewed:** `e10359e`, the branch tip this review worked in.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreter:** the repository's virtualenv at `E:\LabCairn\.venv` (CPython
3.12) with `PYTHONPATH` pointed at this worktree's `src/` — `import labcairn`
verified to resolve to this worktree before any run. Each run had its own
`--basetemp` under `E:\labcairn-local\tmp`.

**Method.** Every mutation in the record's tables (§5.4's eight plus the
write-path mutation, and §5.6's four numbered on from them) was re-applied
against this worktree, one at a time; each mutation's diff was read before
its witnesses ran, and the file was restored with `git checkout --` after.
Two applications did not take on the first attempt (an f-string anchor whose
`\x00` escapes were rewritten as literal NUL bytes; an `itertools.count()`
spelled inside the f-string, which builds a fresh counter per evaluation and
therefore never advances); neither result was reported — each was redone with
a correct form before anything was believed.

## 1. Baseline

`tests/test_ooxml_revisions.py`, `tests/test_docx_fixture_corpus.py`,
`tests/test_gold_set_corpus.py` — **141 passed**. The record's §1
reproduction command was also run as written:
`python tests/evaluation_docx_fidelity.py --corpus-dir=<dir>` exits 0 and
writes the corpus — **30 fixture files**, the 30-fixture corpus the record's
re-measured numbers are about.

## 2. What was re-applied, and what happened

| # | The mutation | Result |
|---|---|---|
| 1 | `w:delText` contributes nothing | **4 red**: `test_every_deletion_text_is_recovered`, `test_the_two_views_are_the_texts_adr_0014_names`, `test_a_revision_nested_inside_another_is_reported_separately`, `test_every_revision_carries_its_kind_text_author_and_date` — the record's set |
| 2 | un-anchorable comments dropped | **4 red**: the three the record names, plus `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor` — consistent, the cross-paragraph case is an unknown anchor too |
| 3 | a missing author filled with a placeholder | **2 red**: `test_a_missing_author_or_date_is_unknown_and_never_guessed`, `test_every_revision_carries_its_kind_text_author_and_date` — the record's set |
| 4 | the locator's view forced to `accepted` | **2 red**: `test_a_revision_locator_resolves_to_the_revisions_own_text`, `test_a_deletion_is_addressed_in_the_rejected_view` — the record's set |
| 5 | a cross-paragraph range reported resolved (end offset borrowed) | **4 red**: the three the record names plus `test_a_resolved_anchor_never_names_a_range_outside_its_own_paragraph` — the record's set |
| 6 | the cross-paragraph anchor reports a non-empty text | **1 red**: `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor` — exactly one, as the record states |
| 7 | the fixture's end marker written into the starting paragraph | **3 red**: `test_a_comment_with_no_resolvable_anchor_is_still_a_comment`, `test_each_unresolvable_anchor_names_its_own_reason`, `test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor` — the record's set |
| 8 | the gold derivation says a cross-paragraph anchor resolves | **1 red**: `test_a_comment_with_no_resolvable_anchor_is_still_a_comment` (the un-anchorable count is 4, not 5) — exactly as the record states |
| 9 | the walk reports inside nested paragraphs again (the defect restored) | **5 red**: `test_a_revision_inside_a_drawing_textbox_is_reported_once` and the four corpus-wide witnesses the record names (`test_every_revision_in_the_corpus_is_reported`, `test_every_revision_carries_its_kind_text_author_and_date`, `test_the_reader_reports_each_revision_element_exactly_once`, `test_the_derived_revision_event_id_names_one_change_per_address`) |
| 10 | `_element_path` stops indexing same-tag siblings | **3 red**: the drawing test, the per-element count, and the id witness — the record's "all three new witnesses" |
| 11 | `_revision_event_id` drops the element path from its digest | **1 red**: `test_the_derived_revision_event_id_names_one_change_per_address` |
| 12, form A | the wall clock mixed into the digest | **Survived** — 1 passed. The witness's determinism check calls `_revision_event_id` twice back-to-back, and on Windows two calls land inside one clock tick, so the ids came out equal. Exactly the record's account of why this survivor is timing-lucky. |
| 12, form B | every call counts itself (module-level `itertools.count()`) | **Red** — the same witness, on the `again == ids[0]` assertion. The record's re-measurement form reproduces. |
| W | a write path added to the reader module | **Red**: `test_the_reader_module_writes_nothing`. The module as committed contains no write call (a source scan for the witness's forbidden list finds none), and the watch catches the added one. |

**Every mutation behaved as the record states.** The one survivor (12 form A)
is reported by the record as a survivor with the reason — the tick boundary —
and the re-measurement form (B) reddens as the record says.

## 3. What was checked against the tree, not against the tests

- **The extraction version moved as claimed.** `_parser_version()` computed
  on this tree returns `38e0d9591c8e2a9a13c913b5f2b5f0f3` — the record's
  "after" value, unchanged since the fix, which also means §5.6's statement
  that the fix's value is the hash of `ooxml.py` at `f4a7e94` still holds
  for this tree.
- **The reader has no write path.** A scan of `src/labcairn/material/ooxml.py`
  for every string on the no-write witness's forbidden list finds none, and
  the witness (`tests/test_ooxml_revisions.py:452`) watches the module's
  source — mutation W proves it fires.
- **The `ooxml-native` arm.** The record says the measurement tool's arm is
  still the *not written yet* placeholder and the §4 row of zeros is what
  the tool did not produce. The tool's source agrees (the arm is a stub);
  the record's honesty here is verifiable and verified.

## 4. What could not be checked, and why

These are claims about files and a database outside the repository; this
review cannot re-measure them and does not pass them silently:

- **The real-file numbers**: the 897 real tracked changes of §5, the 239
  events / 239 distinct addresses / 239 elements of the affected draft
  (§5.6), the other review copies' element counts (384, 349, 311, 225, 219,
  219, 210, 203, 114, 52, 27, 8), and the borrowed-offset example's
  character positions. The files are the owner's material and are not in
  the tree.
- **The pilot-chain figures**: 46 recorded comments, 18 with an empty
  anchored text under a `resolved` status, 3 of the 18 the cross-paragraph
  case (§5.2.1), and the pilot `revision_events` counts of §5.6. The pilot
  workspace is outside the repository.
- **The "before" extraction version** `d375f3a81242e9cbbd6075155d67f365`: it
  is the hash of the reader *before* the fix, which no longer exists in
  this tree to hash. The "after" value was verified; the "before" value is
  accepted on the record's own account of how it was measured.

## 5. Findings

1. No witness stayed green under a mutation that reached it. The single
   survivor is the record's own, honestly reported, with the re-measurement
   that pins it.
2. The record's own corrections (the invocation that did not run, the
   breakdown that did not add up, the fixture wrongly claimed extracted,
   the reader not scored by the measurement) are the record correcting
   itself on the page; nothing in this review retracts any of them.
3. **(Note)** Two of the record's mutations are sensitive to *how* they are
   spelled: mutation 12's f-string form only works if the injected
   expression is a module-level counter (an inline `itertools.count()`
   builds a fresh iterator per evaluation and always yields 0 — a survivor
   that is the mutation's fault, not the witness's). A re-applier who
   spells it inline will report a survivor where the record reports a red.
   This is the same reproducibility shape as LC-P2-16's mutation 8 and is
   worth a line in a future revision of the record, though the property and
   the verdict are unaffected.

## 6. Verdict

**Holds.** All thirteen mutations (the record's twelve plus the write-path
mutation) were re-applied with the outcomes the record states, including the
one honest survivor and its re-measurement. The extraction version and the
no-write guarantee were verified against the tree itself. The real-material
and pilot-chain numbers are outside this review's reach and are named as
such in the record.
