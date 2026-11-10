# Changelog archive — Phase 1 — gates G0 to G5, closed, never released

Archived verbatim from the root [`CHANGELOG.md`](../../CHANGELOG.md) on
2026-11-11. The body is byte-identical to the sections as they stood there,
except that each relative link gained the depth of `docs/changelog/`.
The root file keeps [`[Unreleased]`](../../CHANGELOG.md#unreleased) as the
container and [the archives index](../../CHANGELOG.md#archives).

### The public alpha (G5) — closed on two independent reviews

The handoff: evaluation, fault injection, and the documents.

**Added**

- **The public fixture corpus** — four scenarios across three genres plus
  the negative one, every byte synthetic, with source locators, hashes and
  answer keys that are **not** the product's own output.
  `tests/fixtures/public/` · [record](../acceptance/LC-P1-13-fixtures.md)
- **The evaluation harness** — one command that runs the protocol's five
  gate classes and writes the results with their denominators, and that
  reports the Phase 1 blockers honestly, including the ones that did not
  hold. `tests/evaluation/` ·
  [record](../acceptance/LC-P1-13-evaluation.md)
- **The outsider's path** — a script that clones the repository outside the
  checkout, builds an environment inside the clone, runs the README's
  commands there for real, binds a research folder, produces a report and a
  deterministic figure with source locators and an evidence ledger, revises
  it, survives a restart, and reads the same task back through two surfaces.
  Every step is a check that raises rather than warns, so the exit code is
  the assertion. `scripts/outsider_path.py` ·
  [record](../acceptance/LC-P1-14-outsider-path.md)
- **The threat model** — six faces (writes, reads, network, credentials,
  crash and concurrency) with `path:line` citations, and a larger §6 of
  **what the product does not claim**.
  [docs/THREAT-MODEL.md](../THREAT-MODEL.md)
- **The documentation set** — the bilingual README and its standalone
  Chinese document, the quickstart, the contribution guide, this changelog,
  and the release notes with the known limitations.
  [docs/QUICKSTART.md](../QUICKSTART.md) ·
  [docs/RELEASE-NOTES.md](../RELEASE-NOTES.md)
- **The font licence audit** — measured, and the factual half of the licence
  audit is done: **no third-party font file reaches any artefact**, so the
  GPL font reportlab bundles does not attach to what a user receives.
  [record](../acceptance/LC-P1-14-font-licence-audit.md)

**Still open in this gate** — and named rather than glossed:

- the fault injection run **through the surfaces**, and the two exit
  demonstrations that were run by nothing;
- the **real-provider smoke**, which waits on the owner's credential and on
  the owner's decision about what a declared skip means;
- the **competitor baseline**, at whatever scope the owner settles;
- the **NOTICE**, the dependency and security checks, and the release's own
  member lists;
- the **review dossier**.

**Known limitations of this alpha** are listed in one place:
[the release notes](../RELEASE-NOTES.md). They are the larger half of the
handoff, and none of them is estimated.

---

## Phase 1, gates G0 to G4 — closed, never released

### G0 — upstream source study (LC-P1-00)

**Added** — the curated checkout strategy, the source/commit/licence index,
the architecture decisions, and no vendored dependencies.
[Record](../acceptance/LC-P1-00-evidence.md) ·
[review](../acceptance/LC-P1-00-review-623e3ca.md)

### G1 — the trusted core (LC-P1-01 to LC-P1-04)

**Added** — the deterministic `FakeProvider`; the versioned typed contracts
and their JSON serialization; the capability policy and the approval
binding; the workspace roots and the path guard; the security invariants;
the `research-report` skill contract.
[Acceptance](../acceptance/LC-P1-01-evidence.md)

### G2 — durable work (LC-P1-05 to LC-P1-07)

**Added** — the SQLite task store with transactional event append; the stage
plan; the injected restart; and crash recovery that enters `UNCERTAIN`
rather than guessing, so an uncertain side effect is never replayed blindly.
[Acceptance](../acceptance/G2-acceptance.md) ·
[narrative record](../acceptance/G2-evidence.md)

### G3 — the evidence path (LC-P1-08 to LC-P1-10)

**Added** —

- **Material ingestion and locators.** Text, Markdown, CSV, XLSX and PDF
  adapters produce text units addressed by page, line, row and header, or
  sheet and cell. The PDF library was settled by
  [ADR-0008](../adr/ADR-0008-pdf-ingestion-library.md) on `pdfplumber` and
  `pdfminer.six`, both MIT — **not** PyMuPDF. A page that reads as two
  columns is **refused and disclosed** rather than extracted, because
  splicing two columns stores sentences the author never wrote.
  [Acceptance](../acceptance/LC-P1-08-acceptance.md)
- **Retrieval and the evidence ledger.** An FTS5 index over a trigram
  tokenizer; four working cite-support checks; a record state machine whose
  only transitions are `advance` and `attest`; and a gate that **refuses as
  a whole**, so a partial citable list can never be handed to a caller.
  [Acceptance](../acceptance/LC-P1-09-acceptance.md)
- **Bounded analysis and a deterministic figure.** Seven descriptive
  operators and a catalogue built from their own id constants; a grouped
  aggregate that returns a table rather than a number; a figure's editable
  source as a recipe of exactly three parts — **data, encoding, output** —
  with no script beside it and no way to run one; a deterministic renderer
  whose controls were measured rather than asserted; and the reproducibility
  manifest, with six fields and one hash lineage.
  [Acceptance](../acceptance/LC-P1-10-acceptance.md)

### G4 — the usable application (LC-P1-11 and LC-P1-12)

**Added** —

- **The report path.** One `ReportDocument` — the model — with four
  renderers over it (Markdown, HTML, DOCX and PDF), the report artefact
  manifest, the revisions, the staleness that finds them, five content
  checks, the document builder, and the application layer's `render_report`.
  A report cites **locators only**, and an address that does not resolve is
  refused and cited **nothing** in its place.
  [Acceptance](../acceptance/LC-P1-11-acceptance.md)
- **Three surfaces behind one application layer.** The layer the CLI, the
  local API and the web UI all call; the event read with the cursor that
  resumes it; the Typer CLI; the local FastAPI service on `127.0.0.1` with
  its three guards; and the React workbench. The gate's exit test — *"CLI
  and Web produce same versioned report"* — is demonstrated: the CLI's task
  document and the local service's, field by field, and the report's bytes
  by hash. [Acceptance](../acceptance/LC-P1-12-acceptance.md) ·
  [gate review](../acceptance/G4-acceptance.md)

**Also in this period**

- **The CI runs in six shards per platform.** 34.5 minutes → 7.3. The shard
  file records the commit its costs were measured at, and a witness fails if
  anything under `src/` or `tests/` has changed since — because a value that
  can change is re-measured, not carried forward.
- **The earlier gates' exit demonstrations are run by a test.** They had been
  run by nobody since G1 closed, which is how a broken one survived to G5.
- **The G1 path-guard limit is stated and watched.** A write to a new file
  under an 8.3 short-spelled directory is accepted — the key names the tail
  below the root, and the tail is the same in both spellings.

