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

**Scope of inspection, stated plainly:** this ADR inspected **licence files and package metadata**. It did not study parsing source or run a benchmark. That is the correct scope for a licensing decision, and it is deliberately not dressed up as a mechanism comparison the way ADR-0004 is.

Licence obligations if code or text is copied or adapted: none anticipated. These are consumed as ordinary dependencies, not vendored.

## Decision and why this fits LabCairn

**LC-P1-08 will depend on `pdfplumber` (MIT), which pulls `pdfminer.six` (MIT).**

A span anchor is produced by grouping pdfplumber's character records by `(fontname, size)` and taking the bounding box of each group. That is a few lines, it is deterministic, and it is re-derivable from the source file — which is what ADR-0004's C1 requires of a locator, and what its §36 explicitly rejects as insufficient:

> **Locators are display strings, not addresses.** … There is no structured, re-derivable, schema-bound locator. LC-P1-08's "fixtures validate page, row, column and spreadsheet cell anchors **exactly**" cannot be built on a prose label.

pdfminer.six reaches the same objects a layer lower (`LTTextBox` → `LTTextLine` → `LTChar`, each with a `bbox`). pdfplumber is chosen over it directly because it normalises coordinates to a top-left origin, which removes a class of sign error from span geometry, and because table extraction comes with it — LC-P1-10 plots and LC-P1-09's C3 numeric checks both want it.

**Known cost: pure Python is slower than MuPDF on large documents.** Accepted. Phase 1 processes a researcher's working set, not a scanned archive, and the acceptance criterion is that anchors resolve exactly, not that parsing is fast.

## Risks, tradeoffs and reversibility

- **Version coupling.** pdfplumber pins an exact `pdfminer.six` version per release; upgrading `pdfminer.six` independently can silently change extraction. This must be respected — the pin is part of the contract, not an accident of the lockfile.
- **Coordinate normalisation is a real difference from the ecosystem norm.** pdfminer's bottom-left PDF origin is what most PDF examples use. Anchors must not mix the two conventions. The acceptance test below exists for this reason.
- **Reversible.** The dependency is confined to one ingestion adapter behind the `SourceAnchor` contract ADR-0004 already froze. Swapping libraries later means reimplementing one adapter, and the fixtures and anchor assertions survive the swap — which is the point of having made the contract independent of the library first.

## Contracts and acceptance tests

1. Every anchor resolves: a `SourceAnchor` naming a page, span, row, column, sheet or cell re-resolves against the ingested material. A page 99 anchor in a 3-page PDF fails rather than falling back.
2. Span anchors are **exact**, asserted against fixtures — not "the text is somewhere on the page."
3. Span geometry is expressed in **one** coordinate convention, asserted by a test that fails if a second origin convention appears.
4. Hash drift is detected: modify a fixture after extraction and the anchor is invalidated.
5. Unreadable, empty, duplicate and modified inputs are handled without fabrication — and unreadable stays distinct from "no results".

## Re-evaluation trigger

Re-open this decision if **either** becomes true:

- LC-P1-13 evaluation shows ingestion is the binding constraint rather than retrieval recall — i.e. parsing cost actually matters at scale. Then the speed trade-off above stops being acceptable and the commercial option is worth pricing properly.
- A span-level requirement appears that pdfplumber cannot satisfy — for example a true graphical/textual distinction requiring a rendering pass rather than glyph geometry.
