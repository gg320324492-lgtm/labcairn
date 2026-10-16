# ADR-0008: The PDF library LC-P1-08 will depend on, and why not the one its work order names

**Status:** Accepted
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-17

> **Scope note, added after review.** This ADR decides the **library** and nothing else. An earlier draft also prescribed how to build a span anchor from it. That prescription was wrong four separate times when measured, and it does not belong in a licensing decision. What replaces it is a list of **measured constraints** — every one reproducible via the probe scripts in `scripts/probes/` — which LC-P1-08 must satisfy without this ADR dictating the algorithm.

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

**What is at stake is narrower than it looks.** ADR-0004 already decided the locator contract — page, span, line, section, row, column, sheet, cell — and its §120 records that no design conclusion was drawn from PaperQA's AGPL subpackage, deliberately. **Nothing needs undoing.** The question is only which library produces the anchors the existing contract asks for.

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

**This ADR does not decide how a span is built from it.** That algorithm is LC-P1-08's design work, and the measurements below show why prescribing it here was wrong: four candidate rules were tried and each failed on material LabCairn actually ingests.

## Measured constraints on any ingestion implementation

Every item below is a property of real material, reproduced by the probe scripts, and each one is a trap rather than a starting point.

1. **Grouping page-wide on `(fontname, size)` merges lines.** Two runs 40 points apart produced one span spanning both:
   `'Group A mean was 3.0Group B mean was 5.0'`, bbox `(72.0, 62.48, 194.72, 114.48)`. Font and size identify a *style class*, not a span.

2. **Baseline clustering merges columns.** `extract_text_lines()` on a two-column page returned `'Left column line one. Right column line one.'` — a 41.8-point gutter swallowed and two unrelated sentences joined. The paper contains no such contiguous string, so a verifier built this way rejects correct citations and accepts quotations matching text no author wrote.

3. **`page.chars` contains no synthesised whitespace.** This corrects an earlier claim in this ADR, which said `page.chars` carried spaces. It does — *only when the PDF emits a space glyph.* Measured on the same string both ways:

   | Built as | chars | of which `' '` | joining chars yields |
   |---|---|---|---|
   | literal `0x20` bytes in the string | 35 | 5 | `'Efficacy of Widgets in Field Trials'` |
   | `TJ` positioning offsets, no glyph | 30 | **0** | `'EfficacyofWidgetsinFieldTrials'` |

   The second row is the dominant real-world case — LaTeX and Word space words by positioning, not by glyph. **Span text cannot be produced by joining character records**; whitespace must be reconstructed from inter-glyph gaps, or taken from an extraction that does it. An earlier draft of this ADR generalised a property of its own fixture into a property of pdfplumber, and was wrong.

4. **A single gutter threshold cannot work.** Sweeping `min_gap` over a two-column page and a single column containing one wide intra-column gap: the first segments correctly only below **41.8**, the second only above **70**. The overlap is empty. The reason is instructive — projecting the two-column page onto x yields bands `[(72.0, 278.2), (320.0, 414.5)]`, a 41.8-point gap, not the 160 the columns leave between them, because the **full-width title** reaches `x1 = 278.16` and bridges the left column. Every real paper has a full-width title, and often a figure or table spanning both columns.

5. **`(fontname, size)` is not a valid key for rotated text.** One 10pt run reported sizes `[2.22, 2.78, 5.56, 7.22]` and fragmented into `'oaedabe'`, `'tt '`, `'ll'`, `'R'`. `size` is a per-glyph transformed height when `upright` is False. Worse, `extract_text()` on the same page returns `'lebal\ndetatoR'` — reversed and split — so the failure is not confined to glyph joining. Rotated text is common: figure axis labels, sideways stamps, scanned pages.

**The signal most likely to replace a global threshold is line support** — a real column is occupied by many lines at the same x-range, whereas an intra-column word gap appears on one line, so a split proposed by a single line is not a gutter. This is **unproven**. It is reasoned from two hand-built fixtures and has never seen a real paper.

## Risks, tradeoffs and reversibility

- **Version coupling.** pdfplumber pins an exact `pdfminer.six` version per release; upgrading `pdfminer.six` independently can silently change extraction. The pin is part of the contract, not an accident of the lockfile.
- **Coordinate normalisation differs from the ecosystem norm.** pdfplumber uses a top-left origin where most PDF examples use pdfminer's bottom-left. Anchors must not mix the two. Accepted as the cost of removing a class of sign error.
- **Column segmentation is the hard part, not PDF reading.** Constraint 4 shows a global threshold provably fails and constraint 5 shows a key assumption does not hold for non-upright text. An estimate treating LC-P1-08 as a thin wrapper over a parsing library is wrong.
- **Pure Python is slower than MuPDF on large documents.** Accepted. Phase 1 processes a researcher's working set, and the acceptance criterion is that anchors resolve exactly, not that parsing is fast.
- **Reversible.** The dependency is confined to one ingestion adapter behind the `SourceAnchor` contract ADR-0004 already froze. Swapping libraries later means reimplementing one adapter, and the fixtures and anchor assertions survive the swap — which is the point of having made the contract independent of the library first.

## Constraints LC-P1-08 must satisfy

Each traces to a measurement above, so none can be satisfied by a test that was written to match whatever the code happened to do.

1. Every anchor resolves against the ingested material. A page 99 anchor in a 3-page PDF fails rather than falling back.
2. Span anchors are **exact** against fixtures — not "the text is somewhere on the page".
3. Span geometry uses **one** coordinate convention, asserted by a test that fails if a second origin convention appears.
4. **No span spans a gutter or a line break** (constraints 1, 2).
5. **Span text preserves synthesised whitespace** — `'Efficacy of Widgets in Field Trials'`, never `'EfficacyofWidgetsinFieldTrials'` (constraint 3).
6. **A full-width element creates no gutter**, and **an intra-column gap is not a gutter** (constraint 4).
7. **Rotated text is either handled correctly or excluded and reported** — never silently shredded into spans (constraint 5).
8. Hash drift is detected: modify a fixture after extraction and the anchor is invalidated.
9. Unreadable, empty, duplicate and modified inputs are handled without fabrication, and unreadable stays distinct from "no results".

## Re-evaluation trigger

Re-open the **library** decision if any of these holds:

- LC-P1-13 evaluation shows ingestion is the binding constraint rather than retrieval recall. Then parsing cost matters at scale, the speed trade stops being acceptable, and the commercial option is worth pricing properly.
- A span-level requirement appears that glyph geometry cannot satisfy — for example a true graphical/textual distinction requiring a rendering pass.

Re-open the **segmentation** work, independent of the library, if line support turns out not to be a sufficient replacement signal for a global gutter threshold. Two hand-built fixtures are not evidence, and real papers — with figures, tables, footnotes and multi-region layouts — are the first real test of it. If line support fails too, column segmentation is a research problem rather than an engineering one, and the LC-P1-08 effort estimate is wrong.
