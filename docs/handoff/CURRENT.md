# LabCairn — Current handoff

**Date:** 2026-10-20
**Current `main`:** `7c816a2` — the merge of PR #59, the exit demonstration. The merges since the previous refresh are #32 (LC-P1-09's task breakdown), #33 (T01, the evidence tables), #34 (T02, normalisation), #35 (the ground-truth query set), #36 (T03, the FTS5 index), #37 (T04, building the index from ingestion), #38 (T05a, the anchor registry), #39 (T05, C1), #40 (T06, C2), #41 (T07, C3), #42 (T08, the store), #43 (T09, the gate), #44 (T10, retrieval and the acceptance review), #46 (T00, the chart library), #47 (T01, the corpus), #48 (T02 and T03, the operator contract and the selection), #49 (T04, the descriptive operators), #51 (T06, the chart recipe), #52 (T08, the manifest), #53 (the plan's two wrong examples), #54 (T05, the grouped aggregate), #55 (T09, the run path, and the published record brought back into line), #56 (the header's declared unit, checked against the data) and #57 (four properties no test observed) and #58 (T07, the deterministic renderer) and #59 (T10, the exit demonstration).

**This file rots on every merge and no test can catch it.** `tests/test_status_consistency.py` checks that the gate table agrees with the plan, that every status is from the declared vocabulary, that a row claiming progress cites evidence, and that relative links resolve — but "how far along is the work" is a semantic judgement, not a parseable fact. This file was **six merges stale** when it was last checked: it named PR #24 as current and claimed no material parsing existed, which stopped being true at #25. It was then stale again at #32, and the claim it made — "Nothing is implemented" for LC-P1-09 — stopped being true at #33. Refresh it in the PR that reports the change, and check `git log origin/main` rather than trusting it.

## Gates

| Gate | Status |
|---|---|
| G0 | **closed** — LC-P1-00 PASS WITH NOTES, subject `623e3ca` |
| G1 | **closed** — LC-P1-01 PASS WITH NOTES, LC-P1-02 PASS, LC-P1-04 PASS, LC-P1-03 PASS WITH NOTES |
| **G2** | **closed** — LC-P1-05/06/07 all PASS WITH NOTES. [Acceptance](../acceptance/G2-acceptance.md) · [narrative record](../acceptance/G2-evidence.md) |
| G3 | **the exit test is met; the [gate review](../acceptance/G3-acceptance.md) recommends closure, and on 2026-10-20 the owner decided that G3 closes only after an **independent review** rather than instead of one; G4 proceeds in the meantime**

## What exists now

The engineering floor from G2: versioned contracts, provider adapters with fail-closed budgets, workspace permissions, a SQLite task store with transactional events, crash recovery that enters UNCERTAIN rather than guessing, and the `research-report` Skill contract.

And, from LC-P1-08: **material ingestion works end to end.** Text, Markdown, CSV, XLSX and PDF adapters produce text units with locators — page, line, row+header, sheet+cell — which a workspace walk reads through `SourceMaterial` and stores as `sources` rows plus content-addressed `source_texts`, with hashed bytes and workspace-relative paths. Unreadable material is separated from empty material and from readable material, and neither unreadable state is citable.

And, from LC-P1-09: **the ledger has a store, an index, four working checks and a gate.**

- Revision 0005 creates `evidence_records`, `evidence_anchors`, `verification_records` and the `evidence_fts` FTS5 table; 0006 rebuilds that table on a **trigram** tokenizer, and 0007 adds `source_anchors`, the anchor registry.
- Normalisation is an index-side copy with a declared profile and an `alters_letters` flag, so a comparison can report how lossy it was (T02).
- Retrieval works over the real papers: fifteen ground-truth queries, eleven that must find the right pages and four that must find nothing, validated against the PDFs before any index existed (T03).
- The index is built from the store and reports what it excluded (T04).
- **All four cite-support checks answer.** `check_source_exists` resolves every cited anchor and
  compares three separate hashes (T05). `check_quotation_support` walks a ladder of four
  normalisation profiles and refuses to promote a lossy match to `pass` (T06).
  `check_numeric_consistency` re-reads the anchored cell and compares parsed values under a
  declared tolerance (T07). C4 returns `not_checked` and always will.
- **The ledger persists records through a state machine** (T08). `advance` and
  `attest` are the only ways a status changes, and each refusal names the
  Contract 2 rule it refused. A `verified_by_rule` record's passing entry must
  name a checker id in the rule catalog -- the one rule the model cannot
  enforce, because it accepts any id, and a human attestation is logged by a
  human's id.
- **The evidence gate refuses** (T09). It re-runs the checks rather than reading
  their verdicts -- a record whose source has drifted is invalidated, not kept
  with a stale "pass" -- and it refuses as a whole: `citable` is empty when any
  record fails, because a partial list would invite a caller to cite the ones
  that survived. A conflict is handed over as data with two interchangeable
  sides, so the structure itself cannot express a winner.

Both exit demonstrations run green:

```bash
uv run python examples/g2_exit_demo.py      # persist, crash, restart, resume — 14 checks
uv run python examples/g2_uncertain_demo.py # the uncertain path end to end — 18 checks
```

## What does not exist yet

**No research capability yet.** There is no CLI, no server, no web UI, and no model call that
leaves the machine. All four cite-support checks now have bodies, and `IMPLEMENTED_CHECKS` is
every one of them — the set no longer distinguishes "implemented" from "not", and what still
separates them is that C4 can never return a pass.

Retrieval now answers the two-negative question (T10): a search that breaks is a `PROVIDER_FAILURE` and never a `no_hit`, and the boundary refuses to hand a caller an empty context. What is still unbuilt is everything around it — the analysis, the report renderer, and the model call the evidence would feed. And the gate is reachable from a ledger rather than from a report: nothing renders a `GateResult` yet, so "a report cites nothing when the gate refuses" is enforced at the gate and asserted at the record model, not observed in a rendered document. That demonstration is LC-P1-11's to make. The ledger's conflict rule covers numeric records about the same cell; the claim-side conflict ADR-0004 A5 also describes is not implemented, because the schema's own uniqueness constraint makes two claim records unable to collide.

## Next: G3's closure, then G4

LC-P1-08 (material parsing and locators) → LC-P1-09 (FTS5 retrieval and the evidence ledger) → LC-P1-10 (bounded statistics and deterministic plots).

**LC-P1-08 was accepted with notes by owner decision, not by independent review.** Its acceptance review is [written up](../acceptance/LC-P1-08-acceptance.md) and records eight defects found and fixed — most seriously, a two-column PDF storing sentences the author never wrote and marking them citable. The review and the fixes are the same party, so the board's rule is not discharged; the owner decided on 2026-10-18 to proceed without it, and the board records that as a decision rather than as a review.

**LC-P1-09 is implemented and reviewed — PASS WITH NOTES.** All ten subtasks are merged, the acceptance review is [written up](../acceptance/LC-P1-09-acceptance.md), and it found three defects, all of the family LC-P1-08's review found eight of: a claim made in a docstring that the code did not enforce, and a column nothing ever wrote. Two are fixed; the third is a **clause of the acceptance that is not discharged** — the *fabricated DOI* half has no implementation, and the gap is structural rather than an oversight. The review and the fixes are the same party, so the board's independent-review rule is **not discharged**; the same caveat as LC-P1-08.

One thing worth knowing before reading the code: **`SourceIndex`'s members were never specified by ADR-0004.** The ADR requires C1 to "fail if an anchor id is unknown", but the Protocol it names takes no id — `locate` wants a whole anchor and `content_hash` a source id, and a record carries only `anchor_ids` as bare strings. Revision 0007 and `load_anchor` close that seam. It is recorded as an execution note at the head of ADR-0004, because it is the requirement's missing implementation rather than a change to the contract.

**G3's exit test is met, and the review recommends the gate be closed** — but the board's rule that a row is marked done only when an **independent** review at a named commit says so is not satisfied for any of G3's three work orders, so the closure is the owner's decision rather than the review's. The [gate review](../acceptance/G3-acceptance.md) names what an independent reviewer would still want to look at: LC-P1-08's two-column threshold, LC-P1-10's manifest not naming a version for the renderer, and the fact that **G1's and G2's exit demonstrations are run by nothing** and can rot without anyone noticing.

**LC-P1-10 is [reviewed and accepted](../acceptance/LC-P1-10-acceptance.md) — PASS WITH NOTES.** [Task breakdown](../plans/LC-P1-10-task-breakdown.md): eleven subtasks (T00–T10) with a file-ownership map, and the work order's five acceptance clauses plus the ADR-0004 conditions it touches each mapped to the subtask and test that carries them.

**T00 — the dependency decision — is [ADR-0012](../adr/ADR-0012-chart-rendering-library.md).** `matplotlib>=3.9,<4`, locked at 3.11.2, seven new packages and 78.7 MB of installed bytes. Two things in it are worth knowing before the renderer is written:

- **The licence was read from the distribution's own `LICENSE` file, and it brings a second obligation.** matplotlib's own licence is PSF-style and permissive — but the wheel **bundles forty TrueType fonts under two further licences** (DejaVu: Bitstream Vera; STIX: SIL OFL 1.1), so the G5 licence audit must cover the bundled fonts and not the root licence line alone. That is exactly the failure ADR-0004 records for paper-qa.
- **The determinism controls were measured, and the one you would guess is not the one that works.** Fixing `svg.hashsalt` **alone is not enough**: matplotlib writes a creation date into the SVG metadata, and two renders a second apart get different ones. The two controls govern different things — the **date** governs stability *within* a process, the **salt** governs it *across* processes, because left unset matplotlib generates a fresh random salt per interpreter. PNG needs neither. `tests/test_analysis_dependency.py` fails if either control is removed, and its cross-process assertion is the only one that can observe the salt at all.

**T02 and T03 — the operator contract and the selection.** T02 fixes the id grammar (`labcairn.analysis.<name>`) and the one reference spelling (`…@1.0.0`) a manifest quotes; the catalogue of shipped operators lands with the operators themselves, because it has to be built from their own id constants, exactly as `evidence/catalog.py` is built from the checks' constants. T03 is the selection — which columns, which rows, and a **declared** missing-value policy — and it **moved the quantity reader to `labcairn/sources/quantity.py`**, so the ledger and the analysis layer cannot answer "is this a number" two different ways. C3's existing tests pass **unmodified**, which is the proof the move changed no behaviour.

**T01 — the fixture corpus — is the first thing in the repository that is a CSV or a spreadsheet at all.** Eight committed CSVs under `tests/fixtures/analysis/`, each with a hand-written `<fixture>.expected.json` beside it, and a test that recomputes those values with Python's `statistics` — an implementation that is **not** LabCairn's, so an expectation cannot share a bug with the code the operators will be written against. The corpus is also where the format asymmetry was pinned in data rather than in prose: `holes.csv` and `holes.xlsx` are the same table with one value cell emptied, and the CSV **keeps** the cell (empty) while the spreadsheet has **no cell at all** — so a spreadsheet's rectangular extent is not recoverable from the ledger. A second difference is in the same pair: a spreadsheet's header row *is* a set of addressable cells (A1, B1) and a CSV's is not.

**T04 — the descriptive operators and the catalogue that holds them.** Seven operators (`count`, `sum`, `min`, `max`, `mean`, `median`, `stdev`) and the catalogue built from their **own id constants**, for the same reason `evidence/catalog.py` is: **one id has one spelling**, and the manifest quotes an operator by name, so two spellings of one operator would be two manifests that do not compare equal. A catalogue cannot precede its implementations, so it landed *with* the operators rather than before them — LC-P1-09's precedent, where the evidence catalogue was created in T08, after the checks it registers existed. The unit rule is C3's, inherited: compared as written, never converted, and the known false negative (`kilograms` and `kg` are one unit spelled two ways, and a selection holding both is refused, naming both tokens) is stated rather than hidden.

**T05 — the grouped aggregate.** One vetted statistic per group, over a selection, returning a **table** rather than a number: there is no "the grouped mean" of three groups, and a number would have thrown away the very thing that makes it grouped. The statistic is **composed** from a registered operator rather than reimplemented, so the grouped mean and the scalar mean cannot drift apart — there is exactly one implementation of "mean" in this codebase — and an aggregate that names no registered operator is a **refusal**, not a guess. The aggregate's unit is checked **per group** and not across the selection. A group with no quantity has **no statistic** (never zero), and its reason names **that group** rather than the selection, because in a table of groups "the selection" is the wrong thing to blame. The group key is the cell's text **as written**, so the empty key is a group while a cell that was never recorded is not — for a spreadsheet those are the same observation, and inventing a key would be inventing a group.

**T06 — the chart recipe.** A figure's editable source is a JSON document of exactly **three** parts (data, encoding, output), with **no script beside it and no way to run one**. That is what makes the work order's *"Explicitly no general-purpose model-authored code execution"* **satisfiable rather than aspirational**: a recipe names an operator from the catalogue, a selection, an encoding and an output, and the renderer draws it. The figure's numbers are therefore a **vetted operator's output** and not a second reading of the file, and the parameters are checked by **the operator's own argument model**, so the question "which parameters does this operator accept?" has exactly one answer and it is the operator's. The **caption and the interpretation are separate fields**: ADR-0004 A10 holds that an interpretation is never machine-verified, so the marker that says so belongs to the **renderer** and cannot be left out by forgetting.

**The acceptance review's verdict is PASS WITH NOTES**, and its three findings were closed before the verdict rather than after it: a unit check that passed **vacuously** (the function that reads a column header's declared unit had no caller in the production code, so a table that keeps its units in the header found nothing to check); four properties no test observed; and a caption drawn **across the axis tick labels**, found by the exit demonstration. Two limits are recorded rather than closed — the manifest names **no version for the renderer**, and the aggregate's numbers are not re-checked by C1, C2 or C3 — and the review is **not independent**, which is the same open item LC-P1-09's review carries.

**T10 — the exit demonstration.** `examples/analysis_demo.py`, in the shape of `examples/g2_exit_demo.py`: a controlled CSV is ingested, a grouped aggregate runs and prints the value **and the cells it came from** (each with its locator), a figure is drawn from the recipe, the manifest prints its six fields and both hashes, the figure is rendered twice and the bytes compared, and then the **input file is changed**. The last step uses the repository's own machinery rather than a comparison the demo wrote: the material's checkpoint no longer verifies, `invalidate_on_source_change` marks the figure and the manifest `STALE` with the reason, a run over the new bytes is refused, and the figure on disk is unchanged. The **recipe is committed** and the run's arguments are read out of it, so the recipe and the run cannot disagree. And unlike the earlier exit demonstrations, this one is run by a test — `g1_exit_demo.py` and `g2_exit_demo.py` are run by nothing, and a demonstration nobody runs is one that quietly stops working.

**T07 — the deterministic renderer.** A figure is drawn from the **recipe** and from **the operator's result object**, so the numbers plotted are the operator's numbers, and the renderer neither re-reads the file nor re-implements the aggregate. The chart operator that does the drawing is a **catalogue entry** (`labcairn.analysis.chart@1.0.0`), so *"a vetted chart operator renders"* is code rather than convention, and the renderer dispatches through the catalogue to it. `render()` returning `None` means exactly one thing — *this result does not produce a figure* — and everything else is a **refusal** that names the fault. The determinism controls were **demonstrated rather than asserted**: the SVG's creation date and its salt each shown to matter, **PNG shown to need neither**, and a hostile ambient `matplotlibrc` shown unable to change the bytes; the `rcParams` come from a **declared, hashed** defaults file, and the renderer's declared drawing parameters (the figure's size, the histogram's bin count, the settings' digest) are published as constants the manifest's environment does **not** carry — recorded in the breakdown's §5 as something this work order does not deliver.

**T08 — the reproducibility manifest.** A computed number is a statement about a **derivation**, and what makes it checkable is not a check but the document: the input file's hash, the selection, the operator and its version, the parameters, the recipe and the output's hash — the **six fields** the work order names. The manifest is the document; the receipt is the record that points at it, and the `artifacts` table already mirrors the receipt field for field, so there is **no new table and no migration**. And **one hash lineage**: the manifest's input hash, the selection's `content_sha256`, the source's `content_sha256` and the file's actual bytes are the same value, and the builder refuses to produce a manifest in which they are not — the definition of that value already had two implementations in this repository, and the manifest reuses one of them rather than adding a third.

**T09 — the run path.** From a granted `analysis.run` to a recorded artefact: admit the path into the named source root, build the selection, resolve the source (the ledger's row, the file's bytes, the source's readability), evaluate the operator, `prepare()` the environment, write the manifest, render, and record the receipts. **The consent is the existing machinery and is not optional** — the digest is *recomputed* at the moment of use over the capability's canonical arguments, so an approval to analyse one selection does not authorise another, and the approval's source binding is re-hashed, so a file that has drifted since is a refusal rather than a run over different bytes. Every refusal is one type with a machine-readable reason and a message that names what is wrong, and the refusals the machinery underneath raises are translated rather than swallowed, with the original kept as the cause. A refusal **before** the consent point does not spend the approval — re-asking a human is cheap — and the operator's refusal does, because the operator's evaluation *is* the operation the capability names. The bounds are the enforceable ones: a row limit and a cell-count limit, both checked **before** a cell is read, because a limit checked afterwards is a report and not a bound. The one that cannot be enforced — a wall-clock timeout on an in-process numeric loop — is named in `UNENFORCED_LIMITS` rather than shipped, because a timeout that does not fire is worse than no timeout at all.

Three facts about the rest of it are worth having before the code is written, because each one removes work rather than adding it:

- **No schema migration is needed.** `ArtifactReceipt` already reserves `ArtifactKind.FIGURE` (*"LC-P1-10's concern"*), `ArtifactKind.MANIFEST` and `ArtifactProducerKind.ANALYSIS_OPERATOR`, the `artifacts` table already mirrors the receipt, and `ComputationLocator` was written for this work order — its docstring names ADR-0004's re-evaluation trigger 3 as the reason it exists.
- **The repository contains no CSV and no XLSX file at all.** `tests/fixtures/` holds `papers/` and `retrieval/`, and a repository-wide search for `*.csv` and `*.xlsx` returns nothing. So the "controlled fixtures" the acceptance clause names are a **deliverable of LC-P1-10**, not an input to it — the same gap LC-P1-09's review recorded when it noted that every C3 case was a row written by a test.
- **An aggregate cannot be an evidence record, and the schema already says so.** `evidence_records.anchor_ids` name rows in `source_anchors`, whose `locator_key` is CHECK-constrained to the four extractable kinds, and `render_locator_key` raises for `LocatorKind.COMPUTATION` because a derived number has no address in `source_texts`. The owner chose to keep it that way on 2026-10-19: an aggregate is an **artifact** with a manifest, and the ledger keeps doing what it is good at — statements about located cells. The cost is stated in the breakdown rather than glossed: **a figure's numbers are traceable to the input file but are not re-checked by C1, C2 or C3.**
- **The two spreadsheet formats disagree about what an empty cell is, and it was measured rather than assumed.** A **CSV** emits a `source_texts` row for an empty cell, so empty cells can be counted; an **XLSX** emits no row for one, so a spreadsheet's **blank cells are not recoverable from the ledger** — a cell that holds nothing and a cell that was never there are the same observation. The consequence is narrower than "the missing count is unknown": the count of *addresses with no recorded value* is known in both formats; what is not knowable for a spreadsheet is **how many of them were blanks the author left**, and a range that overshoots the table cannot be told apart from a range full of blanks. A count of zero is never used to mean "unknown" — ADR-0004 A8, applied to statistics.


**Its PDF library question is settled.** [ADR-0008](../adr/ADR-0008-pdf-ingestion-library.md) puts it on pdfplumber + pdfminer.six, both MIT, rather than PyMuPDF, whose AGPL branch would have constrained LabCairn's own MIT release. Nothing needed undoing.

**The two-column PDF question is also settled, as a refusal.** Reading order is not reconstructed. A page that reads as two columns is refused and disclosed rather than extracted, because splicing two columns stores sentences the author never wrote — that defect was real, reproduced, and is the reason the refusal exists. Rotated text is still not detected, and there is no two-column paper in the repository to test detection against.

**G4 is the next gate, and its plan is written.** [LC-P1-11 and LC-P1-12's task breakdown](../plans/LC-P1-11-12-task-breakdown.md): the report's document model with four renderers over it, the report artefact manifest, the revisions and the staleness, the content checks, and then the three surfaces — the Typer CLI, the local FastAPI service and the React workbench — behind one application layer they all call. **The four decisions in §1.4 were taken by the owner on 2026-10-20**: a report cites **locators only** (the source model has a place for identifiers that ingestion never fills and that nothing resolves); the CLI and the API serve the **same bytes**, so the gate's exit test is a hash comparison; the report's **reproducible form is Markdown and HTML** (a DOCX is a ZIP and a PDF carries a creation date, so by default neither is); and the local API **refuses a foreign origin** and requires a token minted at start-up **None of it is implemented**: there is no `cli/` module, no `api/` module, the web package is a placeholder skeleton, and the store has **no list query** for tasks, runs, stages or artefacts, which all three surfaces need. The G3 gate's closure — the owner's decision — comes first.

## Carried limitations, none blocking

- **LC-P1-08:** rotated PDF text is **not detected**. A rotated page would
  extract in the wrong order and nothing would record it. ADR-0008 constraint 7
  is unmet, and this is the honest reason the two-column work stopped at
  refusal rather than proceeding to reconstruction.
- **LC-P1-08:** the two-column detector is bracketed against single-column
  fixtures, not calibrated against two-column ones — there is no two-column
  paper in the repository to calibrate against. Its threshold is defensible
  because it refuses loudly, not because it is known to catch every layout.
- **LC-P1-08, discharged by LC-P1-09:** anchors were validated only in their
  **positive** direction — no code consumed a locator and returned content, so
  nothing showed that a wrong locator misses. `locate_anchor` now does exactly
  that, and C1's tests assert both halves: a locator naming page 99 of a
  three-page paper fails, and the failure names that address and no other.
  What is *not* yet shown is the end-to-end version — that a report built from
  a record whose locator failed cites nothing — because there is no report
  renderer (LC-P1-11).
- **LC-P1-08:** `UNPARSEABLE` is a mixed bucket — a container that would not
  open, and a page deliberately not read. Both are honestly "not citable, here
  is why", but only the disclosure separates them.
- **G1:** `ApprovalLedger.consume()` does not resolve the capability against the registry. Only `policy.evaluate()` turns an unknown id into DENY, and nothing enforces that a caller evaluates first. The ordering constraint belongs in an ADR.
- **G1:** path-guard tests ran on Windows only. POSIX ADS and case semantics are unverified.
- **G1:** ADR-0006's outbound-consent bridge is not built. Both modules exist.
- **G1:** structured-output capability is unmeasured — both probes fail in pydantic-ai's client layer before a request is sent.
- **G2:** `ArtifactLedger` is in memory. LC-P1-07's ledger does not survive a restart; the store does.
- **Cross-gate:** the Gitleaks allowlist guard is textual and has a multi-line/nested TOML weakness.
- **Cross-gate:** the README capability-claim detector has known holes. It is a floor, not a truth-checker.
- **Cross-gate:** copyright ownership is unresolved and there is still **no `LICENSE` file**. The project describes itself as in development with open-source licensing pending.

## Merge authority

The implementing agent merges its own PRs after both the parent and a non-implementing reviewer have signed off and all required CI checks pass. Merge authorisation comes from the project plan, not from an external auditor.

## Escalate to the project lead

Expanding data access scope, write permission to original material, unapproved outbound transmission, any model-generated code execution, and major architecture change. The PyMuPDF licence obligation is now **resolved** (ADR-0008) and no longer needs escalating; **copyright ownership remains unresolved** and still does.
