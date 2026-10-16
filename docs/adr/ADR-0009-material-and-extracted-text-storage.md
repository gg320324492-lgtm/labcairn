# ADR-0009: Where ingested material and its extracted text live

**Status:** Proposed
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-17

## Context and concrete problem

LC-P1-02 froze the contract for addressing material. `Source` names a file
with a workspace-relative path, a content hash, a size and a readability
state; `SourceAnchor` addresses a place inside a `Source`; `LocatorKind`
covers page-and-span, line-and-section, row-and-column, sheet-and-cell and
operator-and-inputs.

**None of it is persisted.** The store created by LC-P1-05 has
`tasks`, `runs`, `stages`, `operations`, `approvals`, `checkpoints`,
`artifacts` and `events` — and no table for materials. `artifacts` holds
*outputs*; nothing holds the *inputs* a report cites. So today a locator
resolves against a file that must be re-read, with a parser, at the moment
somebody checks it.

ADR-0008 adds the pressure. A `PdfLocator` is a **character range into the
page's extracted text**, so resolving one requires that text to exist as a
fixed string. The library question was settled there — pdfplumber, MIT — and
what remains is the question this ADR answers: does that string get produced
on demand and thrown away, or stored?

## The concrete problem this creates

Two consumers need the same text at different moments, and they disagree
about when.

- **C2** matches `record.extracted_span` against the text at an anchor's
  located span. It runs at verification time, possibly much later, possibly
  on a machine that is not the one that ingested the file.
- **LC-P1-09 retrieval** returns verbatim source spans. It runs repeatedly
  and often.

If the text is re-derived on demand, both consumers depend on the installed
pdfplumber and pdfminer.six producing byte-identical output to whatever ran
before. ADR-0008 measures that this is not a small risk: the same file under
the same library, re-extracted, must be identical, and a library release can
change it. The failure is silent and retroactive — every anchor written
under the old extraction quietly addresses different characters.

## Alternatives

**A. Re-extract on demand. Nothing new is stored.**

Simplest, and no copy of the user's material exists anywhere except the
original file. Rejected as the default for the reason above: correctness
depends on an environment reproducing an extraction exactly, across a
dependency upgrade nobody controls, and the failure mode is silent
re-pointing rather than an error. It is not obviously wrong — it is
*unanchored*.

**B. Store the extracted text, keyed by content hash and extraction version.**

Re-extraction becomes an optimisation rather than a correctness requirement:
the stored text is authoritative for anything anchored, and re-extraction
only ever produces a candidate to compare against it. Chosen.

**C. Store only the extracted text's hash.**

Rejected. It answers "has this text changed" and not "what is this text",
and C2 needs the text. A hash with no text behind it protects nothing that
the source file's own hash does not already protect.

**D. Keep the text out of SQLite — a sidecar cache directory.**

Rejected. A second store with no transactional coupling to the event log
means the text and the anchors that reference it can disagree, and nothing
would notice. ADR-0003's C3 is one transaction = the events and the state
rows they describe; a sidecar is exactly the split that rule exists to
prevent.

## Decision

**Ingested material is inventoried as rows; its extracted text is stored in
SQLite, keyed by the material's content hash, the locator, and the extraction
version.**

The key is the whole design:

| Column | Why it is in the key |
|---|---|
| `source_content_sha256` | The text is bound to the exact bytes it came from. A modified file cannot inherit old text, and ADR-0004's A2 hash drift fires rather than silently re-reading. |
| `locator` (page / line / row+column / sheet+cell) | Same content, many addresses. |
| `extraction_version` | The same bytes under a different extraction are different text, and must not collide. |

Because the key contains the content hash, extraction is effectively
**content-addressed**: the same bytes and the same extractor always yield the
same row, and re-ingesting an unchanged file is idempotent. Because the key
contains the version, an upgrade produces *new* rows beside the old ones
rather than overwriting them, so an anchor written under the old version can
still be resolved — and its divergence from the new text becomes a
**detectable** fact rather than a silent one.

**Extraction is eager, at ingest.** Doing it once, recording the version,
means C2 and retrieval read a stored string and never re-derive one. The
cost is that ingesting a large corpus does the work up front. Accepted:
Phase 1 ingests a researcher's working set, not an archive, and the eager
path is the one that makes the version a fact rather than a hope.

**The source material itself is never written.** Extraction reads through
`SourceMaterial`, which raises `SourceIsReadOnlyError` on write and delete.
LC-P1-04's promise — the original materials remain unchanged — is enforced by
the boundary that already exists, not by discipline in this module.

**Extracted text is untrusted data.** It is material read out of a file, and
ADR-0003 §C6 requires imported text to be wrapped in `UntrustedText` at the
moment it is ingested, so it cannot be passed where a path or a parameter is
expected. Storage does not change that: what comes back out is still wrapped,
and the wrapper is not a storage format detail that gets dropped on the way
through the database.

### What is a *new copy* of the user's material, and what is not

Stated plainly because it is a real consequence. The database will hold text
extracted from the user's research materials. That is a second copy of
derived content, on the same machine, inside the same local store that
already holds task state and evidence records.

It is not the original material: the PDFs, CSVs and spreadsheets are read and
never modified, and deleting the workspace does not leave the originals
behind. But a user who deletes a source file has **not** deleted its text
from the database. Phase 1 has no "forget this material" operation, and that
is a gap LC-P1-08 should record rather than assume is someone else's problem.

## Risks, tradeoffs and reversibility

- **Schema addition, not just an implementation.** Two new tables. The
  material rows persist a contract that exists today only as Pydantic models,
  and the extracted-text rows are genuinely new.
- **Storage grows with the corpus.** Extracted text is roughly 1–3% of a
  PDF's bytes. Acceptable for a working set; unbounded ingestion of an
  archive would need a retention policy that Phase 1 does not have.
- **The version key can go stale.** If `extraction_version` is not bumped
  when behaviour actually changes, the key lies. The version is therefore
  derived from something mechanical — the library version and an adapter
  revision — not from a constant somebody remembers to bump.
- **Reversible.** Both tables are additive. Dropping them loses extracted
  text and material rows, both of which are derivable from the workspace
  itself, which is why this is safe to undo and cheap to redo.

## Contracts and acceptance tests

1. Re-ingesting an unchanged file is idempotent: identical rows, no
   duplicates, and the second run writes no new extraction version.
2. Modifying a file after extraction does **not** produce new text under the
   old content hash; the new hash yields its own rows, and anchors bound to
   the old hash still resolve to the old text.
3. Two extractions of the same bytes at the same version produce
   byte-identical text. Asserted by repeating, not once.
4. A `PdfLocator` with a character range resolves to exactly the characters
   in the stored text, and a range one character outside fails rather than
   clamping.
5. Extraction never writes to the source. Asserted by reading the material
   bytes before and after a full ingest and requiring them equal, and by
   asserting `SourceMaterial.write` raises for the same path.
6. A scanned PDF yields `readability=UNREADABLE_NO_OCR` with a non-empty
   disclosure, and is **not** recorded as an empty page.

## Re-evaluation trigger

Re-open this decision if any of these holds:

- LC-P1-08's corpus turns out to be far larger than a working set, at which
  point eager extraction and unbounded storage need a retention policy this
  design does not have.
- A "forget this material" requirement arrives from the export or deletion
  side. Text derived from a file the user asked to forget is a different
  problem from text the user never had.
- The security constraints on storing research material tighten, in which case
  option A's minimal footprint deserves a second look despite the
  re-pointing risk.
