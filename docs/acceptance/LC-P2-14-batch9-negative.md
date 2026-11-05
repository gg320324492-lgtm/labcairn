# LC-P2-14 — The batch-9 negative witnesses: answer range, red semantics, duplicate file, mixed-source letter — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation
and ablation) · **Route under test:** [`LC-P2-09`](LC-P2-09-acceptance.md) (the feedback
chain) · **This record:** the **negative half** of four properties that one material batch
exposed.

**Status.** Four properties, four witnesses. Two of them are new witnesses; two were
already carried and are cross-referenced here with the mutation that re-measures them.
**No product code was changed** — each mutation was applied to a working tree, the
witnesses were run against it, and the file was restored byte-for-byte and re-hashed.
**Nothing here rates the material, the reviewers or the answers.**

**What this record does not carry.** No title, sentence, comment, answer, file name or
person from the material is in this file or in the witnesses. Every fixture is synthetic
and written in the test files themselves; the material is referred to only as **batch 9**,
and only by counts and shapes. The reconnaissance that names the material and its shapes is
chain-external (`E:\labcairn-local\batch9-recon\RECON.md`).

**Measured:** 2026-11-05 on the worktree branch over `main` at `54ac696`, on Windows 11
(AMD64), Python 3.12.13.

---

## 1. The four properties and where each is carried

| Property | The reading this refuses | Witness | Carried by |
|---|---|---|---|
| **Answer range** | a `Point` reaching 1+N answer paragraphs is recorded as one complete answer | `test_an_answer_that_spans_paragraphs_is_not_recorded_as_one_full_answer` | **new**, `tests/test_feedback_events.py` |
| **Red semantics** | red font on the answer side is read as a reviewer's annotation | `test_red_font_is_not_a_revision_and_its_text_is_counted_once` | **existing**, `tests/test_ooxml_revisions.py` (batch 7) |
| **Duplicate file** | two byte-identical files are recorded as two contents | `test_two_byte_identical_files_are_one_content_and_not_two_versions` | **new**, `tests/test_version_duplicates.py` |
| **Mixed-source letter** | a letter whose first exchanges are copied from another paper is one paper's answer set | `test_a_mixed_source_letter_is_not_one_projects_reply_set` | **new**, `tests/test_feedback_events.py` |

**Two are new and two are cross-references, and the reason is the existing coverage.**
The red-semantics property was already carried by the batch-7 witnesses: the red run is
not a revision, and a body paragraph in a response letter is not a Word comment — the
reader reports **no comment** for a document with no comments part, in both cases. A third
witness for the same reader would have been a duplicate of a witness that already exists,
so this record cross-references the batch-7 one and re-measures it with a mutation of its
own (§3). The duplicate-file property was carried at the **check** layer
(`test_the_same_bytes_are_one_version_whatever_the_name`: two names, one hash, one
version) but **not at the byte layer** — nothing showed that two byte-identical files
really do carry one content hash. The new witness closes that gap with real bytes through
the product's own ingestion.

## 2. The two new witnesses, and the shapes they stand on

### 2.1 The answer range

The fixture is one objection paragraph and **three** answer paragraphs. The reader keeps
all four paragraphs; the product's exchange has **one** answer place, so recording
paragraph 1 stores exactly paragraph 1, and the hash in the row is that paragraph's hash.
The continuation paragraphs stay in the document and outside the row. The witness also
asserts that **no field exists** that could carry an answer range — the row is one
paragraph, and it does not pretend to be more.

The batch-9 pilot measured 35 answers spanning more than one paragraph out of 44 recorded
pairs, with the continuations outside the store. **That loss is the product's documented
limit, not a parsing loss** (see `LC-P2-14-batch9-pilot.md` §3), and this witness keeps it
visible: the row cannot be read as a completed answer.

### 2.2 The duplicate file

Two files are ingested through the product's own ingestion with **the same bytes under
two names**. The content hash is computed from the bytes, so the two agree, and their
source ids differ because the two names are two locations. The duplicate check then
reports **one content under two names** — not two versions whose relationship is
unresolved. The witness asserts both halves: the hashes agree, and the report says one
content.

### 2.3 The mixed-source letter

Two projects, two letters, and one letter whose first two exchanges are **byte-for-byte**
the other letter's first two exchanges while its remaining exchanges are its own. The
witness holds three things at once:

- the same words in two letters are **two rows with two derived ids**, and the two
  projects' listings do not overlap;
- the derived reply id **names its version**, so a copy is a second address, not a second
  reading;
- the door **refuses to borrow** another project's version as this project's reply set,
  and the refused call writes nothing.

The product does not claim provenance it was not given: there is no per-exchange source
field, and the witness asserts that too.

## 3. The measurements: five mutations, each one red

Every mutation was applied to one product file **in place**, the witnesses were run
against the mutated tree, and the file was then restored from a byte-for-byte backup.
The SHA-256 below is the file's own, taken before the mutation and again after the
restore; **the two are equal in every row**, which is what "restored" means here.

| Mutation | File | SHA-256 before → after restore | Witness | Result |
|---|---|---|---|---|
| **A** the reply layer folds the paragraphs after the answer into the answer text | `src/labcairn/papers/replies.py` | `d587605e9507…` → `d587605e9507…` | `test_an_answer_that_spans_paragraphs_is_not_recorded_as_one_full_answer` | **RED** — the row's answer text held all three paragraphs |
| **B** the reader mints a `CommentEvent` from a paragraph carrying a red run | `src/labcairn/material/ooxml.py` | `954e6825cbf7…` → `954e6825cbf7…` | `test_red_font_is_not_a_revision_and_its_text_is_counted_once` | **RED** — `document.comments` was no longer empty |
| **B** the same mutation, second witness | ″ | ″ | `test_a_quoted_reviewer_paragraph_is_not_a_comment` | **GREEN** — the two are two witnesses, not one count |
| **C** the duplicate check groups the same-content files by label as well as hash | `src/labcairn/papers/duplicates.py` | `6004932e0e3d…` → `6004932e0e3d…` | `test_the_same_bytes_are_one_version_whatever_the_name` | **RED** — the same bytes were no longer reported as one content |
| **C2** the content hash is computed per file rather than per bytes | `src/labcairn/material/ingest.py` | `9712c6e3d7b3…` → `9712c6e3d7b3…` | `test_two_byte_identical_files_are_one_content_and_not_two_versions` | **RED** — the two files carried two hashes |
| **D** the derived reply id drops the version | `src/labcairn/papers/replies.py` | `d587605e9507…` → `d587605e9507…` | `test_a_mixed_source_letter_is_not_one_projects_reply_set` | **RED** — the two letters' common words collapsed onto one row |

**Mutation B is the discriminating one.** It reddens the red-font witness and leaves the
quoted-reviewer witness green, so the two existing witnesses are two witnesses. Every
other mutation reddens the witness it was written for.

**A first attempt at B was invalid and was discarded.** It replaced the call to
`_collect_comments` instead of following it, so the reader raised `NameError` and both
witnesses failed for a reason that had nothing to do with the property. The mutation was
rewritten to append after the call, and it then reddened exactly the witness it was
written for. **An effective mutation is one that makes the assertion fail**, and a
mutation that breaks the module is not one.

**The harness is chain-external** (`E:\labcairn-local\batch9-negative\mutate.py`), beside
the byte-for-byte backups of the five product files. **Nothing was restored through git**,
because the tree carried uncommitted work; each file was written back from its backup and
re-hashed.

## 4. What the witnesses do not say

- They do **not** say a multi-paragraph answer is wrong, that red font is wrong, that two
  copies of a file are wrong, or that a copied passage is wrong. They say the product does
  not **classify** any of these as something it is not.
- The answer-range witness does **not** claim the product holds a 1+N answer. It claims the
  opposite: it holds one paragraph and says so.
- The mixed-source witness does **not** claim the product can see that a passage was
  copied. It claims the product cannot be made to collapse two copies into one row, and
  cannot be made to borrow another paper's version.
- The duplicate-file witness does **not** claim the archive merges the two files. The
  design's answer is to **report** the duplicate and let a person decide; the witness
  holds that the report calls them one content.
- The red-semantics witness is the batch-7 one, unchanged. This record adds a mutation
  of it and nothing else.

## 5. The gates

| Gate | Command | Result |
|---|---|---|
| the two reply-event files and the two reader/duplicate files | `pytest tests/test_feedback_events.py tests/test_ooxml_revisions.py tests/test_version_duplicates.py` | **111 passed** |
| the shard-cost witness and the evaluation gate-class witness | `pytest tests/test_ci_shard_coverage.py tests/test_evaluation_harness.py` | **100 passed** |
| lint | `ruff check .` | **clean** |
| format | `ruff format --check .` | **445 files already formatted** |
| types | `mypy --strict src conftest.py tests` | **Success: no issues found in 397 source files** |

**No new test file was added**, so no file needed the three registrations (its own
`pytestmark`, a shard entry, and a gate-class entry) — two existing test files carry the
two new witnesses. **The whole suite was not run**: other sessions are using the machine,
and the shard costs are measured on a runner rather than here.

## 6. Where the evidence lives

| What | Where |
|---|---|
| The two new witnesses | `tests/test_feedback_events.py`, `tests/test_version_duplicates.py` |
| The two cross-referenced witnesses | `tests/test_ooxml_revisions.py`, `tests/test_version_duplicates.py` |
| The mutation harness and the five byte-for-byte backups | `E:\labcairn-local\batch9-negative\` (outside the repository) |
| The reconnaissance of the material | `E:\labcairn-local\batch9-recon\RECON.md` (outside the repository) |
| The pilot that counted the shapes | `docs/acceptance/LC-P2-14-batch9-pilot.md` (in this repository) |
| The batch-7 precedent for these two properties | `docs/acceptance/LC-P2-14-cej-pilot.md` (in this repository) |
