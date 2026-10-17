# ADR-0008: The PDF library LC-P1-08 will depend on, and why not the one its work order names

**Status:** Accepted
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-17

> **Scope note, added after review.** This ADR decides the **library** and nothing else. An earlier draft also prescribed how to build a span anchor from it. That prescription was wrong four separate times when measured, and it does not belong in a licensing decision. What replaces it is a list of **measured constraints** — every one reproducible via the probe scripts in `scripts/probes/` — which LC-P1-08 must satisfy without this ADR dictating the algorithm.
>
> **Correction, added on reading the contract.** An earlier draft of this ADR described a span anchor as a group of character records with a **bounding box**. That is not what LabCairn anchors. `PdfLocator` in `src/labcairn/sources/locators.py` addresses a page and a half-open **character range within the page's extracted text**, and no geometry field exists anywhere in `SourceAnchor` or any of the five locator types. This ADR was describing a locator the project does not have.
>
> The constraints below are therefore restated against what LC-P1-08 actually has to produce: **a canonical, reproducible text for each page**, such that a character range into it resolves to the same characters every time. Every measured finding still applies, but to a different target — not "where is this span on the page" but "what does this page read as".

## Context and concrete problem

`docs/PHASE_1_WORKORDERS.md` named the library:

> **Build:** ingestion from text PDFs (PyMuPDF, page and span), MD/TXT (line/section), CSV (row/column), XLSX (sheet+cell)

PyMuPDF is dual-licensed. Its PyPI metadata for 1.28.2 reads, verbatim:

```
Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License
```

Both branches cost something this project cannot currently pay.

- **AGPL-3.0.** LabCairn is being built toward an MIT release. Under AGPL §§4–6 a combined work must itself be AGPL, and the FSF's position is that linking a copyleft library into an application makes that application subject to the copyleft — there is no independent-work claim for mere linking. The obligation that would bite here is ordinary linking and distribution, **not** §13.
- **Commercial.** No public price list; reported to run from the low four figures, typically recurring. Copyright ownership in this repository is **still unresolved** and there is still no `LICENSE` file, so there is no settled legal person to contract with. Buying a licence before ownership is settled buys it for somebody we cannot yet name.

**AGPL §13 is not the hook, and this ADR previously cited it wrongly.** §13 is conditioned on *"if you modify the Program"*. LabCairn would not modify PyMuPDF, and it is local-first with no network interaction — the one situation §13 addresses. A reader who opened §13 and found it conditioned on modification would have been right to conclude the argument did not hold. The conclusion survives on §§4–6; the citation did not.

This was carried since G1 as "deferred, decide before LC-P1-08." LC-P1-08 is now the next work order, so the deferral has run out.

**What is at stake is narrower than it looks.** The locator contract is already fixed — `LocatorKind` in `src/labcairn/sources/locators.py:65` names the five addressable materials: page-and-span for PDF, line-and-section for text, row-and-column for CSV, sheet-and-cell for XLSX, operator-and-inputs for a computation. (An earlier draft of this ADR attributed that list to ADR-0004, which does not contain it. ADR-0004 does say something that matters here — §36, that locators must be structured addresses rather than prose labels like `"pages 1-3"` — and §120, that LC-P1-08's page/span design is future work. The design is therefore independent of PyMuPDF, and **nothing needs undoing.** The question is only which library produces the page text the existing contract indexes.)

No PDF dependency has been added to the repository. PyMuPDF appears in documentation only.

## Alternatives

| Package | Licence | Role | Verdict |
|---|---|---|---|
| **pdfplumber 0.11.10** | MIT | proposed direct dependency | **Chosen** |
| pdfminer.six 20260107 | MIT | pdfplumber's engine | transitive |
| pypdfium2 5.14.0 | Apache-2.0 OR BSD-3-Clause, **plus bundled third-party licences** | pdfplumber's renderer | transitive — see obligation note |
| Pillow 12.3.0 | **MIT-CMU** (HPND, attribution required) | pdfplumber's imaging | transitive — see obligation note |
| charset-normalizer | MIT | pdfminer.six dependency | transitive |
| cryptography | Apache-2.0 OR BSD-3-Clause | pdfminer.six dependency | transitive |
| pypdf 6.21.0 | BSD-3-Clause | *rejected alternative* | Rejected: weaker layout analysis; C2 cannot tolerate a wrong reading order |
| **PyMuPDF 1.28.2** | **AGPL-3.0 OR Artifex commercial** | *named by the work order* | **Rejected** — both branches constrain the project's own licence posture |

The full runtime tree was resolved in a clean environment rather than inferred. **No strong copyleft ships.** Two attribution obligations do, and they are real: Pillow's MIT-CMU carries the PIL/HPND notice requirement, and pypdfium2's wheel bundles components under their own licences — Apache-2.0, BSD-3-Clause and **CC-BY-4.0**, alongside icu, freetype, libopenjpeg, libpng, zlib, lcms, abseil, simdutf, pdfium and llvm-libc. An earlier draft of this ADR said "no licence obligations anticipated"; that was wrong and is corrected here. Both obligations are satisfiable by shipping the notices, and neither reaches LabCairn's own licence.

**The "no dependency" option is real and was not skipped.** PDF parsing is the one part of LC-P1-08 that could plausibly be done with stdlib plus hand-rolled parsing. Rejected on maintenance, not on principle.

## Upstream evidence (reference only)

Licences were read from upstream `LICENSE` files and PyPI metadata, not from a package index summary or a search result, and independently re-derived by a reviewer who was not the author.

- **pdfminer.six** — `LICENSE` @ `a18de2a9c479b4c847538500017b449ddaec177e`. MIT, "Copyright (c) 2004-2016 Yusuke Shinyama".
- **pdfplumber** — `LICENSE.txt` @ `4c64b92d5caccd71c645e98e0fabb0c4dba7ff45`. MIT, "Copyright (c) 2015, Jeremy Singer-Vine". PyPI classifier `License :: OSI Approved :: MIT License`.
- **pypdf** — `LICENSE` on `main`. BSD-3-Clause, verified clause by clause.
- **PyMuPDF** — PyPI metadata, quoted above. Not re-derived from its source tree.

**Behavioural probes.** Five, run because this ADR's predecessor asserted a mechanism and an asserted mechanism is not evidence. Each builds a PDF by hand — computed xref, no library — and reads it back with pdfplumber 0.11.10 / pdfminer.six 20260107. Reproduce with:

```bash
uv run --with pdfplumber python scripts/probes/pdf_spans.py
```

The scripts are **not** wired into CI: they need `pdfplumber`, which is not yet a project dependency, and LC-P1-08 turns them into real tests when it adopts it. Parsing source was not studied, and **none of this is a benchmark** — no timing, no large document, no speed claim.

## Decision

**LC-P1-08 will depend on `pdfplumber` (MIT), which pulls `pdfminer.six` (MIT).**

**This ADR does not decide how page text is produced from it.** That is LC-P1-08's design work, and the measurements below show why prescribing it here was wrong: four candidate rules were tried and each failed on material LabCairn actually ingests.

What LC-P1-08 must deliver is narrower and harder than it first looks. Because a `PdfLocator` is a character range into the page's extracted text, and a `SourceAnchor` carries `excerpt_sha256` as the field meant to bind that text — **a field no check consumes yet**, see below — the library is not asked "can you find this span" but **"does the same file always produce the same string, and does that string contain the characters a reader would quote"**. Both halves of that sentence are load-bearing:

- A character range is meaningless unless the string it indexes is fixed for that file. Anything non-deterministic — an unordered container leaking into the text, a locale-dependent sort — silently re-points every anchor in the database.
- The string must contain the author's words *with their spaces*. This is measurement 3 below, and on the real corpus it is not a refinement: joining character records returns `Theorem1revealsthatpairwisecontrastivelearning` for a sentence any reader would quote as `Theorem 1 reveals that pairwise contrastive learning`.

A further consequence deserves stating because it is not obvious and it constrains dependency management: **a library upgrade can invalidate every anchor ever written.** If a pdfplumber or pdfminer.six release changes extraction, the page text changes and every character range that indexed the old text now indexes something else.

An earlier draft of this ADR got the *mechanism* wrong in a way worth correcting rather than quietly dropping. It claimed the page-text change would make `excerpt_sha256` stop matching and C1 fail. Both halves are false. `excerpt_sha256` has **no consumer anywhere** — it is declared at `sources/source.py:266` and described in the adjacent docstring, and nothing compares it, so it cannot stop matching anything. And C1 compares the *source file's* content hash, via `LocatedContent.observed_content_sha256`, against `bound_source_sha256`; a library upgrade does not change the PDF's bytes, so C1 would pass.

What actually breaks is two things. The character range **silently re-points**, which is the determinism problem above. And by C2's contract — match `record.extracted_span` against the text at each anchor's located span — the located span would no longer contain what was quoted, so a quotation check would return `fail` rather than `pass`. Neither C1, C2 nor C3 is implemented in Phase 1; all three raise `CiteSupportNotImplementedError`. So this is a statement about the contract, not about observed behaviour, and it is the kind of claim that is easy to make sound stronger than it is.

Either way the extraction version is part of the data contract rather than an implementation detail. Pinning is not enough on its own; LC-P1-08 needs to record which extraction produced a given page text, and that is a design decision it inherits.

## Measured constraints on any ingestion implementation

Every item below is a property of real material, reproduced by the probe scripts, and each one is a trap rather than a starting point.

1. **Grouping page-wide on `(fontname, size)` merges lines.** Two runs 40 points apart produced one span spanning both:
   `'Group A mean was 3.0Group B mean was 5.0'`, bbox `(72.0, 62.48, 194.72, 114.48)`. Font and size identify a *style class*, not a span.

2. **Baseline clustering merges columns.** `extract_text_lines()` on a two-column page returned `'Left column line one. Right column line one.'` — the ~160-point gutter between the columns entirely swallowed, and two unrelated sentences joined. The paper contains no such contiguous string, so a verifier built this way rejects correct citations and accepts quotations matching text no author wrote.

3. **`page.chars` contains no synthesised whitespace.** This corrects an earlier claim in this ADR, which said `page.chars` carried spaces. It does — *only when the PDF emits a space glyph.* Measured on the same string both ways:

   | Built as | chars | of which `' '` | joining chars yields |
   |---|---|---|---|
   | literal `0x20` bytes in the string | 35 | 5 | `'Efficacy of Widgets in Field Trials'` |
   | `TJ` positioning offsets, no glyph | 30 | **0** | `'EfficacyofWidgetsinFieldTrials'` |

   The second row is the dominant real-world case — LaTeX and Word space words by positioning, not by glyph. **Span text cannot be produced by joining character records**; whitespace must be reconstructed from inter-glyph gaps, or taken from an extraction that does it. An earlier draft of this ADR generalised a property of its own fixture into a property of pdfplumber, and was wrong.

   **Confirmed on real papers, not only on the fixture.** Across three CC BY arXiv papers, space glyphs are **0.03%, 0.05% and 1.08%** of characters in the first ten pages, where running text is normally 15–18% spaces. These documents space their words by positioning.

4. **A single gutter threshold cannot work, and gap size cannot work at all.** Sweeping `min_gap` over `5, 10, 20, 30, 40, 50, 70, 100, 140, 200` across two fixtures: the two-column page segments correctly at **5–40 and wrong from 50 up**; the single column containing one wide intra-column gap is correct **from 50 up and wrong at 40 and below**. The two sets do not intersect, so no constant serves both. The boundary itself is bracketed in the interval `(40, 50]` and was not swept more finely.

   The reason the boundary falls there is instructive, and it is a projection rather than a swept value. Projecting the two-column page onto x yields bands `[(72.0, 278.2), (320.0, 414.5)]` — a gap of **41.8 points**, not the ~160 the columns actually leave between them, because the **full-width title** reaches `x1 = 278.16` and bridges the left column. Every real paper has a full-width title, and often a figure or table spanning both columns, so the effective gutter is set by the narrowest gap between *any* two bands on the page, not by the column layout.

   **Then, measured on real papers, the threshold idea was abandoned entirely.** Word gaps and column gutters sit on one continuum with **nothing to cut on**. On `arXiv:2610.12393`, first ten pages, characters grouped by `round(doctop, 1)` sorted by `x0`, keeping gaps over 0.5pt: **n = 5016**, p50 = 2.51pt, p75 = 3.50, p90 = 16.68, p95 = 37.44, p99 = 135.92. Buckets from 6 to 45 points run 26, 26, 21, 32, 36, 51, 26, 30, 17, 36, 16, 27, 19, 19, 8 … 8, 11, 7 — **every integer value in gutter territory is populated**, and 4% of all gaps fall in 15–30pt, which is where a real gutter lives. The distribution decays, but it decays *continuously*, so a threshold set anywhere in that range slices straight through the word-gap population.

   An earlier revision of this ADR called that distribution "essentially flat". It is not, and the correction matters more than the conclusion it was hung on: **a measurement whose method is not written down is not evidence.** A reviewer could not reproduce the original bucket counts under six variants of line filtering and page scope. The method is now stated alongside the numbers, and the claim is the continuity, not the shape.

5. **`(fontname, size)` is not a valid key for rotated text.** One 10pt run reported sizes `[2.22, 2.78, 5.56, 7.22]` and fragmented into `'oaedabe'`, `'tt '`, `'ll'`, `'R'`. `size` is a per-glyph transformed height when `upright` is False. Worse, `extract_text()` on the same page returns `'lebal\ndetatoR'` — reversed and split — so the failure is not confined to glyph joining. Rotated text is common: figure axis labels, sideways stamps, scanned pages.

## What real papers changed, and what they could not settle

A corpus of CC BY papers was obtained to test this rather than reason about it — [`tests/fixtures/papers/MANIFEST.md`](../../tests/fixtures/papers/MANIFEST.md), three papers, licence and attribution recorded, digests asserted by `tests/test_paper_fixtures.py` so a fixture cannot be silently swapped.

It settled two things. Measurement 3 is confirmed on real material at the figures above. And **every magnitude-based segmentation rule tried against these papers underperformed**, which is what forced measurement 4's rewrite from a threshold to a positional argument.

It could not settle the main question. **Eleven CC BY arXiv papers were downloaded and all eleven classified as single-column.** Recent arXiv uses single-column submission format, and the only pages showing two line-start clusters were tables, confirmed by reading them. Three are kept in the repository; the other eight were discarded, so that count is **not independently checkable** and rests on the author's record alone. The three that were kept are verified single-column by two independent methods — recurring line-start x, and right-edge occupancy against a two-column control — because the first method on its own has a failure mode that was found during review: grouping characters by baseline across the full page width merges the two columns of a two-column page, so it reports one column for material that plainly has two. The classification of the eight discarded papers used that weaker method and should be treated with corresponding caution.

So the corpus verifies one direction — a segmenter must not split these — and leaves the other untested: **nothing establishes that a segmenter will find two columns in a two-column paper.**

That gap is why the line-support hypothesis below stays labelled unproven, and it cost more than a threshold did. An intermediate attempt at ground truth deserves recording: a "median row width under 75% of page width" heuristic was used to label the corpus two-column, and **three segmentation rules were rewritten to agree with a label nobody had checked.** Direct inspection showed the labelled papers were plainly single-column, and the rules had been right all along. Inventing ground truth, then treating disagreement with it as evidence against the algorithm, is the same error as asserting a fixture's property as a library's.

## The signal most likely to replace a threshold

A gutter's distinguishing property is not its size but its recurrence: **a real column is occupied by many lines at the same x-range, whereas an intra-column word gap appears on one line**, so a split proposed by a single line is not a gutter.

The status of that idea is narrower than it was and narrower than it should be. It has been implemented and run against real papers, and it correctly returns one column for all eleven — but that is only the easy direction, and a rule that never sees two columns has not been tested. It remains **unproven for the case it exists to solve.**

## Risks, tradeoffs and reversibility

- **Version coupling.** pdfplumber pins an exact `pdfminer.six` version per release; upgrading `pdfminer.six` independently can silently change extraction. The pin is part of the contract, not an accident of the lockfile.
- **Coordinate normalisation binds the extraction adapter, not the anchor.** pdfplumber uses a top-left origin where most PDF examples use pdfminer's bottom-left. A sign error inside LC-P1-08's extraction code would reverse reading order and invent gutters. This is a live risk **inside the adapter**; it is not a constraint on the persisted locator, which carries no coordinates, and an earlier revision of this ADR said "anchors must not mix the two", which required a constraint this document has since dropped as moot.
- **Column segmentation is the hard part, not PDF reading.** Measurement 4 shows a magnitude threshold provably fails and measurement 5 shows a key assumption does not hold for non-upright text. An estimate treating LC-P1-08 as a thin wrapper over a parsing library is wrong.
- **Pure Python is slower than MuPDF on large documents.** Accepted. Phase 1 processes a researcher's working set, and the acceptance criterion is that anchors resolve exactly, not that parsing is fast.
- **Reversible.** The dependency is confined to one ingestion adapter behind the `SourceAnchor` and `LocatorKind` contracts. Swapping libraries later means reimplementing one adapter, and the fixtures and anchor assertions survive the swap — which is the point of having made the contract independent of the library first.

## Known gap: two-column reading order is not reconstructed

Recorded here rather than left for someone to discover from a wrong citation.

`material/pdf.py` extracts each page as pdfplumber renders it, with **no
attempt to reconstruct reading order across columns**. For a page laid out in
two columns of running text, that output places a left-column line and the
right-column line at the same height beside each other. The result is not what
the paper says, and a citation built on it will not resolve to the author's
words. This is the fabrication of measurement 2 above, and the adapter cannot
detect the page it happens on.

**Why there is no detector.** Two rounds of measurement on the repository's
three CC-BY single-column fixtures ruled out the obvious rules. Measured over
sixty-eight body pages:

| signal | range across genuine single-column pages |
|---|---|
| median body-line width | 0.10 – 0.65 of page width |
| fraction of body lines crossing the page midpoint | 0.07 – 0.95 |

**21 of those 68 pages** — all confirmed single-column — have fewer than half
their body lines crossing the midpoint, because those pages carry a full-width
figure above a single-column body. A width rule or a midpoint rule therefore
separates real single-column pages from two-column pages by coincidence, not by
geometry. Shipping one would mean building the extraction on a rule that
misclassifies known-good input, which is what constraint 1 forbids.

**What would close it.** Two-column CC-licensed material, to measure against.
The search is recorded in the work-order status: eleven recent arXiv CC-BY
papers are all single-column; twenty older hep-th papers, the two-column
golden era, carry **zero** CC licences, because arXiv's default perpetual
licence is not Creative Commons. Europe PMC and NCBI serve no fetchable PDF
under automated access. So the intersection is not merely unfound — in the
sources tried it is close to empty.

Until then the gap is stated, not papered over: a reader who cannot see it
cannot price it.

## Constraints LC-P1-08 must satisfy

Each traces to a **measurement** above, numbered 1–5, so none can be satisfied by a test that was written to match whatever the code happened to do. They are written against **page text**, because that is what a `PdfLocator` indexes — an earlier revision of this list spoke of "span geometry", which the anchor contract does not have. A rewrite of this list dropped the exactness constraint without replacing it; that is restored below, and the omission mattered, because exactness is the property the whole correction is about.

1. Every anchor resolves against the ingested material. A page 99 anchor in a 3-page PDF fails rather than falling back.
2. **A character range resolves to exactly the characters that were quoted** — the same ones, in the same order, with the same spacing. Not "text from this page that resembles it". This is the property C2 exists to check, and it is the one thing the corrected scope is about.
3. **Page text is deterministic.** The same file yields byte-identical text every time, so a character range cannot silently re-point. Asserted by extracting the same fixture repeatedly and across repeated runs, not once.
4. **The page text is the author's words, with spaces.** `'Theorem 1 reveals that pairwise contrastive learning'`, never `'Theorem1revealsthatpairwisecontrastivelearning'` (measurement 3). This is the constraint most likely to be quietly weakened, because a test written against the lossy output will pass on it.
5. **Reading order is column-aware.** A character range must not land in interleaved text. On a two-column page, `'Left column line one. Right column line one.'` is not a sentence anyone wrote and must never appear (measurements 1, 2).
6. **A full-width element creates no gutter**, and **an intra-column gap is not a gutter** (measurement 4).
7. **Rotated text is either read correctly or excluded and reported** — never silently reversed, which is what `extract_text()` does to it (measurement 5).
8. **The extraction version is recorded** with the page text, so a library upgrade that changes extraction is attributable rather than mysterious. **No field for this exists today** — `Source` carries none, and `SOURCE_SCHEMA_VERSION` is bumped only with a migration — so satisfying this is a schema addition, not an implementation detail.
9. Hash drift is detected: modify a fixture after extraction and the anchor is invalidated.
10. Unreadable, empty, duplicate and modified inputs are handled without fabrication, and unreadable stays distinct from "no results".

## Re-evaluation trigger

Re-open the **library** decision if any of these holds:

- LC-P1-13 evaluation shows ingestion is the binding constraint rather than retrieval recall. Then parsing cost matters at scale, the speed trade stops being acceptable, and the commercial option is worth pricing properly.
- A span-level requirement appears that glyph geometry cannot satisfy — for example a true graphical/textual distinction requiring a rendering pass.

Re-open the **segmentation** work, independent of the library, if line support turns out not to be a sufficient replacement signal for a magnitude-based rule.

The immediate blocker is material, not conceptual: **no two-column CC-licensed corpus has been obtained.** Eleven CC BY arXiv papers were all single-column, because that venue now uses single-column submission. Older arXiv papers are predominantly two-column but rarely CC BY, so the intersection is narrow. Until two-column material exists in the repository, any two-column test must be written against synthetic fixtures and **named so that nobody later mistakes it for real coverage.** If line support fails on that material too, column segmentation is a research problem rather than an engineering one, and the LC-P1-08 effort estimate is wrong.
