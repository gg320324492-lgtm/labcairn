# LC-P1-08 — Acceptance review

**Work order:** LC-P1-08 (material inventory and source locators)
**Gate:** G3
**Subject:** `main` @ `de28b42`, with the findings below fixed on
`fix/lc-p1-08-acceptance-findings`
**Date:** 2026-10-18
**Verdict:** **PASS WITH NOTES**
**Scope of this document:** the work order's acceptance clause, clause by
clause, with the evidence. Every defect listed here was reproduced before it
was fixed and mutation-checked after.

## Verification actually run

| Check | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 146 files already formatted |
| `uv run mypy` | no issues, 135 source files |
| `uv run pytest` | **1756 passed, 2 skipped** |

## The clause

> **Acceptance:** fixtures validate page, row, column and spreadsheet cell
> anchors exactly; unreadable, empty, duplicate and modified files handled
> without fabrication.

## What the review found

Eight defects, in one family. Every one of them was a claim made in a
docstring, an ADR or a test name that the code did not enforce — the shape of
failure ADR-0011 exists to correct, appearing seven weeks later in the layer
that ADR pointed at. The tests were green throughout, and green for a reason
worth naming: several asserted the *adapter's* problem code when the claim
lives in the *stored* `Source`, so they stayed green while the stored row said
the opposite.

| # | Defect | How it was reproduced |
|---|---|---|
| 1 | A two-column PDF stored **text the author never wrote**. `ingest.py` listed "reading order is column-aware" among the constraints it binds; the adapter had no column logic at all. Two unrelated sentences were spliced into one line, `problems` was empty, and the source landed in `source_texts` as `readable` — citable | Hand-built PDF, full path through `ingest_into_store`, then read back from `source_texts` |
| 2 | `UNREADABLE_NO_OCR` was **dead**. It has an enum member, a schema CHECK, an ADR-0010 definition and a non-null disclosure rule, and no code path in `src/` produced it. A scanned PDF came out `READABLE` | `ingest_bytes` on a valid text-free PDF: `readability=readable`, `disclosure=None` |
| 3 | **PDF page anchors were never bound to content.** Rotating every page's text by one, leaving locators and order intact, kept all 26 PDF tests green | Monkeypatched rotation, full suite |
| 4 | **CSV row locators counted records, not physical rows.** A quoted field containing a newline makes the next record's locator point at the wrong line. `CsvLocator`'s docstring promises the physical row and assigns the resolution to LC-P1-08 | `bravo` sits on physical line 4; the adapter recorded `row=3` |
| 5 | `walk.py` claimed cross-root dedup happens "through the workspace's own `cross_root` refusal". No such mechanism is consulted by `list_dir`; `CROSS_ROOT` is a denial reason in `security/paths.py` that nothing in the walk path calls | Read the call graph |
| 6 | `ingest_into_store` derived its fallback `source_id` from the **content**, while its own docstring said the path. Re-ingesting an edited file raised `IntegrityError` and left the caller's session poisoned (`PendingRollbackError`) — `walk.py` passed an explicit id and so never hit it, which is why 508 material tests stayed green against a public API that could not be called twice | Called twice on an edited file, then called again for an unrelated file |
| 7 | Three docstrings asserted capabilities that did not exist: column-aware reading order, scanned pages "recorded as unreadable", page character ranges "computed against this page's stored text" (`char_start`/`char_end` are never set) | Read against the code |
| 8 | Two tests credited "ADR-0004 A2" for old-text survival. A2 says the opposite — it requires C1 to return `fail`. The real source is ADR-0009 item 2 | Read both ADRs |

## Clause 1 — anchors validated exactly

| Format | Verdict | Evidence |
|---|---|---|
| PDF page | **PASS** (was: not validated) | `test_each_page_number_carries_that_pages_own_text` binds each `unit.locator.page` to that page's own words, read independently through pdfplumber. The rotation mutation that left 26 tests green now fails all three fixtures |
| CSV row | **PASS** (was: wrong) | `test_a_row_is_numbered_by_where_it_sits_in_the_file_not_by_its_ordinal` — a record carrying an embedded newline pushes the next locator from 3 to 4 |
| CSV column | **PASS** | `test_the_header_is_row_one_and_data_starts_at_two` and siblings resolve `(row, header)` to the exact value |
| XLSX cell | **PASS** | `test_material_ingest.py` asserts `[("A1","trial"),("B2","3.5"),("C3","alpha")]` and sheet attribution |
| MD/TXT | **PASS** | `test_material_adapters.py` asserts the full locator list equals `[TextLocator(line=1),(2),(3)]` with matching texts, and sections exactly |

**Recorded limitation.** "Exactly" has only its positive half. No code in
`src/` consumes a locator and returns content — `SourceIndex.locate` has no
implementation and C1–C3 raise `CiteSupportNotImplementedError` — so the
negative half, that a deliberately wrong locator demonstrably misses, is
**untestable today** and untested. It becomes checkable in LC-P1-09, and until
then no anchor in this work order has been shown to reject a wrong lookup.

**Recorded limitation.** The clause's word "column" is ambiguous between a CSV
column and a two-column PDF page. Both readings were reviewed; the CSV reading
passes, and the PDF reading is defect 1.

## Clause 2 — unreadable, empty, duplicate and modified, without fabrication

| Case | Verdict | Evidence |
|---|---|---|
| Unreadable | **PASS** (was: fabricates citability) | A scan now records `UNREADABLE_NO_OCR` with a disclosure; a broken container records `UNPARSEABLE` with a different one. The two are no longer confusable, and neither is citable |
| Empty | **PASS** | A readable file that produced neither text nor explanation records `extracted_nothing_and_said_nothing` rather than passing as empty |
| Duplicate (same bytes, two paths) | **PASS** | Two `sources` rows, one content-addressed extraction; the second writes nothing and is present |
| Duplicate (two roots, same name) | **PASS WITH NOTE** | Recorded schema limit, pinned by a test. `sources` has **no `root_id` column at all**, so the obvious fix — make the key `(root_id, relative_path)` — cannot be expressed, and the existing test does not say so |
| Modified | **PASS** | Identity is stable across an edit, `content_sha256` moves, superseded text survives in the store so an anchor into the old version still resolves, and drift is caught by `bound_source_sha256` |
| Fabrication | **PASS** (was: it fabricated) | No path yields a text row or locator for material that produced none. The two-column case that did is now refused |

**Recorded limitation.** `UNPARSEABLE` is now a mixed bucket: a container that
would not open, and a page the reader chose not to read. Both are honestly
"not citable, here is why", but the disclosure is the only thing
distinguishing them, so a query over `readability` alone cannot separate them.
A fourth state would be honest but is a contract change, and the vocabulary's
own reasoning is that the disclosure is where the truth belongs.

## The two-column decision

The work order's own status line required "a decision on whether the two-column
gap blocks the gate". **The owner decided: detect and refuse.**

Implemented rather than only recorded: each page's baselines are cut into
horizontally contiguous runs and the runs' left edges clustered; two clusters
at least 80pt apart, the rival holding at least 35% of the page's line starts,
is a two-column page, and that page is refused and disclosed rather than
spliced.

The thresholds are bracketed by measurement in both directions rather than
chosen by feel. MANIFEST.md records that a gap-*size* threshold cannot work
here — on `arx-2610.12393` the gap distribution decays continuously with no
break and 4% of gaps fall in 15–30pt, exactly where a gutter lives — so the
signal is positional. Cutting each baseline first is mandatory, because the two
columns share baselines and taking only each line's first word would place
every start in the left column.

The share threshold is bracketed the same way: real single-column pages *do*
produce a second cluster, because a wide internal gap around a figure or an
equation looks like one — seven pages across the three fixtures cluster at
20–26%, the highest 26%. 30%, 35% and 40% each refuse nothing on the real
corpus and each still refuses the synthetic control, so 35% is the midpoint of
the empty band rather than an edge of it.

Both directions have tests, and the false-positive direction is the one that
costs content: `test_no_real_paper_is_refused_as_two_column` pins that none of
the 70 fixture pages is refused. An earlier iteration of the detector refused
seven of them, and a still earlier one refused forty-nine; the second failure
was invisible until it was measured against the real papers rather than a
synthetic control.

**Still open, and not closed by this decision.** There is no two-column paper
in the repository. Detection is therefore proven only against a synthetic
fixture, and MANIFEST.md already records that the corpus cannot establish this
direction. A page whose columns are close enough to fall under 80pt, or whose
text is rotated, will still be read in the wrong order — **rotated text is not
detected at all**, and that limitation is now stated in `ingest.py`'s module
docstring rather than claimed as handled.

## Reviewer independence

This review and these fixes are the same party. The project's merge authority
requires a non-implementing reviewer, so this document records a verdict but
does not discharge that requirement: LC-P1-08 still needs a review by someone
who did not write the fixes.

## Not covered by this review

Nothing here was re-reviewed beyond the clause above: the event and permission
model, the store's transactionality and the crash-recovery paths were taken
from G2's record and not re-examined.
