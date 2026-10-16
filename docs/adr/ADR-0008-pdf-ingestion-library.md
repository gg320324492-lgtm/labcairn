# ADR-0008: The PDF library LC-P1-08 will depend on, and why not the one its work order names

**Status:** Accepted
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-17

## Context and concrete problem

`docs/PHASE_1_WORKORDERS.md` names the library:

> **Build:** ingestion from text PDFs (PyMuPDF, page and span), MD/TXT (line/section), CSV (row/column), XLSX (sheet+cell)

PyMuPDF is dual-licensed. Its PyPI metadata for 1.28.2 reads, verbatim:

```
Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License
```

Both branches cost something this project cannot currently pay.

- **AGPL-3.0.** LabCairn is being built toward an MIT release. AGPL §13 reaches beyond distribution to network use, and Artifex has enforced the point in writing to at least one MIT-licensed project. Choosing the AGPL branch would constrain the licence LabCairn itself ships under — a decision that belongs to the project owner, not to a dependency's default.
- **Commercial.** No public price list; reported to run from the low four figures, typically recurring. Copyright ownership in this repository is **still unresolved** and there is still no `LICENSE` file, so there is no settled legal person to contract with. Buying a licence before ownership is settled buys it for somebody we cannot yet name.

This has been carried since G1 as "deferred, decide before LC-P1-08." LC-P1-08 is now the next work order, so the deferral has run out.

**What is actually at stake is narrower than it looks.** ADR-0004 already decided the locator contract — page, span, line, section, row, column, sheet, cell — and its §120 records that no design conclusion was drawn from PaperQA's AGPL subpackage, deliberately: *"The AGPL subpackage was opened only to read its license header."* The design is already independent of PyMuPDF. **Nothing needs undoing.** The question is only which library produces the anchors the existing contract asks for.

No PDF dependency has been added to the repository. PyMuPDF appears in documentation only.

## Alternatives, including simpler/no-dependency option

| Option | Licence (verified) | Verdict |
|---|---|---|
| **PyMuPDF 1.28.2** | AGPL-3.0 **or** Artifex commercial | Rejected. Both branches constrain the project's own licence posture, and the commercial branch cannot be contracted before copyright is settled. |
| **pdfplumber 0.11.10** | MIT | **Chosen.** Character-level geometry (`x0`, `x1`, `top`, `bottom`, `fontname`, `size`) makes a span a groupable object rather than an approximation. |
| pdfminer.six 20260107 | MIT | Chosen *as pdfplumber's engine*, not as a direct dependency. It is the component that does the layout analysis. |
| pypdf 6.21.0 | BSD-3-Clause | Rejected. Lighter, but weaker layout analysis; text reading order is the property ADR-0004's C2 cannot tolerate being wrong about, and grouping spans from raw character matrices would be work this project would own. |
| pypdfium2 5.14.0 | BSD-3-Clause / Apache-2.0 | Not a substitute — a rendering engine. It arrives as a pdfplumber dependency anyway. |
| **No dependency; shell out** | — | Rejected. Would add a process boundary and a subprocess to a library whose whole advantage is being an in-process layout analyser. |

The "no dependency" option is real here and was not skipped: PDF parsing is the one part of LC-P1-08 that could plausibly be done with stdlib plus hand-rolled parsing. It is rejected on maintenance, not on principle.

## Upstream evidence (reference only)

Licences were read from the upstream `LICENSE` files themselves, not from a package index summary or a search result.

- **pdfminer.six** — `https://raw.githubusercontent.com/pdfminer/pdfminer.six/master/LICENSE` @ `a18de2a9c479b4c847538500017b449ddaec177e`. MIT text, "Copyright (c) 2004-2016 Yusuke Shinyama".
- **pdfplumber** — PyPI classifier `License :: OSI Approved :: MIT License` @ version 0.11.10; repository `LICENSE.txt` MIT @ `4c64b92d5caccd71c645e98e0fabb0c4dba7ff45`.
- **pypdf** — `https://raw.githubusercontent.com/py-pdf/pypdf/main/LICENSE` @ `main`. BSD-3-Clause text verified clause by clause ("Redistributions of source code must retain the above copyright notice…").
- **pypdfium2** — PyPI metadata "BSD-3-Clause, Apache-2.0, dependency licenses".
- **PyMuPDF** — PyPI metadata, quoted above. Not re-derived from its source tree.

**Scope of inspection, stated plainly:** licence files, package metadata, **and four behavioural probes.** They were run because this ADR asserts a mechanism — how a span anchor is produced — and an asserted mechanism is not evidence. Each built a PDF by hand (computed xref, no library) and read it back with pdfplumber 0.11.10 / pdfminer.six 20260107: a single-column page, a two-column page, a threshold sweep across both plus an intra-column gap, and the corrected rule re-measured. Parsing source was not studied and **this is not a benchmark** — no timing, no large document, no claim about speed that has not been measured.

**What the probe measured, and what it corrected.** Every key the mechanism depends on is present on a character record — `text`, `x0`, `x1`, `top`, `bottom`, `fontname`, `size` — so the claim is sound. But the first version of the grouping rule was **wrong**, and the probe is why it was caught before LC-P1-08 was built on it:

```
spans recovered by grouping on (fontname, size): 2
  Helvetica   12.0pt  bbox=(72.0, 62.48, 194.72, 114.48)  'Group A mean was 3.0Group B mean was 5.0'
  Times-Roman  8.0pt  bbox=(72.0, 85.74, 138.22,  93.74)  'smaller footnote text'
```

Two text runs 40 points apart on separate lines collapsed into **one** span, and the bounding box covered both. Grouping on font and size alone is therefore **not** a span — it is a style class, and it silently spans line breaks. Left uncorrected this would have let ADR-0004's C2 accept a quotation that matches text the author never presented as contiguous.

**The single-column probe was not enough, and saying so is the point.** It passed a narrow page. Two further probes were run against the material LabCairn actually ingests, and the rule changed twice.

**Probe two — two columns.** Papers are two-column. `extract_text_lines()` clusters by baseline alone, so on a page with a left and a right column sharing baselines it returned:

```
top=124.86 x0=72.00 x1=409.04  'Left column line one. Right column line one.'
top=134.86 x0=72.00 x1=408.03  'Left column line two. Right column line two.'
```

Both columns in one line, spanning a 337-point gutter. The paper contains no such contiguous string. Every span built this way would join two unrelated sentences — so C2 would reject correct citations and accept quotations matching text the author never presented as continuous.

**Probe three — whitespace.** Probe one grouped `page.chars` directly and kept its spaces. Probe two went through `extract_text_lines()`, and the spans it built came out as `'EfficacyofWidgetsinFieldTrials'` — every space gone. Cause, measured rather than guessed: `extract_text_lines()[0]['chars']` holds **30** characters for a 32-character line, because pdfplumber synthesises whitespace from glyph gaps and those synthetic spaces are not carried into the line's `chars`. The page-level `page.chars` **does** contain them (40 of 295 in the fixture). So span text must come from a source that preserves synthesised whitespace; joining a line's `chars` cannot be it, and a span that drops a space is a different string from the one the author wrote.

**The corrected rule, verified.** Derive everything from `page.chars` geometry: project glyphs onto x to find vertical gutters, cluster each column by baseline into lines, then group each line by `(fontname, size)`. On the two-column fixture that yields 12 spans with the columns separate, every span keeping its whitespace, and each line its own span:

```
col=0 Helvetica 9.0  x0= 72.00 x1=155.04 top=124.86  'Left column line one.'
col=1 Helvetica 9.0  x0=320.00 x1=409.04 top=124.86  'Right column line one.'
```

None of this makes the library wrong. `page.chars` carries every field the corrected rule needs. What was wrong was the rule, and it was wrong twice, in ways only a second and third probe exposed.

Licence obligations if code or text is copied or adapted: none anticipated. These are consumed as ordinary dependencies, not vendored.

## Decision and why this fits LabCairn

**LC-P1-08 will depend on `pdfplumber` (MIT), which pulls `pdfminer.six` (MIT).**

A span anchor is produced in three stages, all from `page.chars`:

1. **Columns.** Project glyph extents onto x and find vertical gaps wider than a threshold. Each gap is a gutter; the bands between them are columns.
2. **Lines.** Within a column, cluster characters by baseline (`doctop`).
3. **Spans.** Within a line, group by `(fontname, size)` and take the bounding box of each group.

Every stage is deterministic and re-derivable from the source file, which is what ADR-0004's C1 requires of a locator, and what its §36 explicitly rejects as insufficient:

> **Locators are display strings, not addresses.** … There is no structured, re-derivable, schema-bound locator. LC-P1-08's "fixtures validate page, row, column and spreadsheet cell anchors **exactly**" cannot be built on a prose label.

pdfminer.six reaches the same objects a layer lower (`LTTextBox` → `LTTextLine` → `LTChar`, each with a `bbox`). pdfplumber is chosen over it directly because it normalises coordinates to a top-left origin, which removes a class of sign error from span geometry, and because table extraction comes with it — LC-P1-10 plots and LC-P1-09's C3 numeric checks both want it.

**Known cost: pure Python is slower than MuPDF on large documents.** Accepted. Phase 1 processes a researcher's working set, not a scanned archive, and the acceptance criterion is that anchors resolve exactly, not that parsing is fast.

## Risks, tradeoffs and reversibility

- **Version coupling.** pdfplumber pins an exact `pdfminer.six` version per release; upgrading `pdfminer.six` independently can silently change extraction. This must be respected — the pin is part of the contract, not an accident of the lockfile.
- **Coordinate normalisation is a real difference from the ecosystem norm.** pdfminer's bottom-left PDF origin is what most PDF examples use. Anchors must not mix the two conventions. The acceptance test below exists for this reason.
- **Neither `extract_text_lines()` nor raw glyph joining is a span.** The first is baseline-clustered, so it merges columns; the second drops synthesised whitespace. Both failure modes are in the probe output above. LC-P1-08 must derive columns and lines from `page.chars` geometry itself, and must take span text from a source that preserves synthesised whitespace. Tests must fail if a span spans a gutter or loses an interior space — otherwise C2 quietly becomes a checker that passes on text no author wrote.
- **A single gutter threshold is provably insufficient, not merely fragile.** This was measured rather than assumed. Two fixtures: a page with two columns sharing baselines, and a single column containing one 120-point intra-column gap. Sweeping the threshold, the first is segmented correctly only at `min_gap < 42` and the second only at `min_gap > 70`. **The overlap is empty** — no constant satisfies both.

  The reason is the useful part. Projecting the two-column page onto x gives bands `[(72.0, 278.2), (320.0, 414.5)]` — a gap of **41.8 points**, not the 160 the columns actually leave between them. The full-width title reaches `x1 = 278.16`, so it bridges the left column and collapses the effective gutter to the narrowest gap between *any* two bands on the page. Every real paper has a full-width title, and often a figure or table that spans both columns, so this is the common case and not an artefact of the fixture.

  Consequently **column detection cannot be a global x-projection with one constant.** The signal LC-P1-08 should use instead is *support*: a genuine column is occupied by many lines at the same x-range, whereas an intra-column word gap appears on one line. A split proposed by a single line is not a gutter. That is a design requirement handed to the work order, stated here because it follows directly from the measurement — and it is **unproven** until real fixtures exist, which is what the re-evaluation trigger below is for.
- **Reversible.** The dependency is confined to one ingestion adapter behind the `SourceAnchor` contract ADR-0004 already froze. Swapping libraries later means reimplementing one adapter, and the fixtures and anchor assertions survive the swap — which is the point of having made the contract independent of the library first.

## Contracts and acceptance tests

1. Every anchor resolves: a `SourceAnchor` naming a page, span, row, column, sheet or cell re-resolves against the ingested material. A page 99 anchor in a 3-page PDF fails rather than falling back.
2. Span anchors are **exact**, asserted against fixtures — not "the text is somewhere on the page."
3. Span geometry is expressed in **one** coordinate convention, asserted by a test that fails if a second origin convention appears.
4. **A span never spans a gutter or a line break.** Given a two-column fixture with identical styling in both columns, it yields two spans per row, not one — the regression probes two and three caught. Asserted against exact expected span text and bounding boxes.
5. **A span keeps its interior whitespace.** `'Efficacy of Widgets in Field Trials'`, not `'EfficacyofWidgetsinFieldTrials'`. A span that loses a space is a different string, and C2 compares verbatim.
7. **A full-width element does not create a gutter.** A fixture with a title or figure spanning both columns must still segment into two columns — the regression the threshold sweep found, where a full-width title collapsed the effective gutter from 160 points to 41.8.
8. **An intra-column gap is not a gutter.** A fixture with one line containing a wide intra-column gap keeps that line whole.
9. Hash drift is detected: modify a fixture after extraction and the anchor is invalidated.
10. Unreadable, empty, duplicate and modified inputs are handled without fabrication — and unreadable stays distinct from "no results".

## Re-evaluation trigger

Re-open this decision if **any** of these becomes true:

- LC-P1-13 evaluation shows ingestion is the binding constraint rather than retrieval recall — i.e. parsing cost actually matters at scale. Then the speed trade-off above stops being acceptable and the commercial option is worth pricing properly.
- A span-level requirement appears that pdfplumber cannot satisfy — for example a true graphical/textual distinction requiring a rendering pass rather than glyph geometry.
- The gutter threshold is already known to be insufficient, so what LC-P1-08 must prove is that **line support** is a sufficient replacement signal: a real fixture corpus — actual papers, tables and figures — must segment correctly under a support-based rule where the global-threshold rule provably fails. If line support does not hold either, column segmentation is a research problem rather than an engineering one, and the effort estimate for this work order is wrong.
