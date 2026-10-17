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

**Extracted text is untrusted data, and the wrapper is applied on the way
*out*.** It is material read out of a file, so ADR-0003 §C6 applies: *"Imported
text is carried in fields explicitly typed as untrusted content and are never
parsed for policy."* C6's guarantee is structural and **consumer-side** — the
decision function's parameters have those types — so the type on the field is
what does the work.

A `TEXT` column cannot hold a dataclass, so `UntrustedText` is reconstructed
when a row is read. That is not a workaround; it is the only place the
guarantee can operate, because it is the boundary a consumer has to cross to
get characters at all. Reading text out as a bare `str` would hand the caller
something that compares equal to every other string and looks like any other
field.

An earlier draft of this ADR said the opposite — that C6 requires wrapping *"at
the moment it is ingested"*, that *"what comes back out is still wrapped"*, and
that the wrapper *"is not dropped on the way through the database."* C6 says no
such thing, and the statement was not true of any implementation. The model
comment in `db/models.py` says the right thing; this is the correction.

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
- **Storage grows with the corpus, by more than this ADR first claimed.** An
  earlier draft justified accepting unbounded growth with "extracted text is
  roughly 1–3% of a PDF's bytes", a figure sourced nowhere. Measured on the
  three CC BY fixtures in `tests/fixtures/papers/` — pdfplumber
  `extract_text()` character count over PDF file size — the real numbers are
  **4.8%, 8.3% and 13.4%, 7.4% overall**. So the claim was low by two to five
  times, in the direction that understates the problem. Two caveats on the
  measurement itself: it counts characters rather than UTF-8 bytes, so the
  stored ratio is *higher* than measured; and it is pdfplumber's extraction,
  not LC-P1-08's, which does not exist yet.
- **Compression is the cheapest mitigation and is not taken here.** Extracted
  text compresses several-fold, and the column could be a BLOB. Deferred
  rather than forgotten: it is premature for a working set and should be
  revisited with the retention policy below.
- **Storage lifecycle is part of this decision, not a gap someone else owns.**
  Deleting a source file leaves its text behind, but the store *is* the local
  database: deleting the database deletes the text with it. An earlier draft
  recorded only the half that sounds worse, which understated the choice.
- **The version key can go stale.** If `extraction_version` is not bumped when
  behaviour actually changes, the key lies. It is *specified* to be derived
  from something mechanical — the library version and an adapter revision —
  rather than a constant somebody remembers to bump. **That derivation does not
  exist yet**; no code in the tree produces an `extraction_version` at the time
  of writing. It is a requirement on LC-P1-08, not a property of this schema.
- **`locator_key` is specified as derived, and nothing derives it yet.** Same
  status: a canonical rendering from the typed columns is required, and until
  it is written, four spellings of one page can coexist and fork the key the
  design rests on. The schema cannot enforce a canonical form; only code can.
- **`LocatorKind.COMPUTATION` is deliberately not here.** It is a real member
  of the frozen contract, but a derived number is addressed by the operator
  that produced it and has no extracted text, so no row of this table is
  `computation`. Recorded so its absence reads as a decision rather than an
  oversight.
- **Reversible.** Both tables are additive. Dropping them loses extracted text
  and material rows, both of which are derivable from the workspace itself,
  which is why this is safe to undo and cheap to redo.

## Contracts and acceptance tests

**What is enforced today, and what is not, is stated per item.** This slice
ships the schema and no ingest code, so a reader must not take a numbered
requirement for a passing test. Status is: **schema** for something a CHECK
or the key enforces, **tested** for something a test demonstrates, **none** for
a requirement with neither.

1. Re-ingesting an unchanged file is idempotent: identical rows, no
   duplicates, and the second run writes no new extraction version.
   *Status: none.* The schema can refuse a duplicate row — **tested** — but
   "the second run writes no new extraction version" is application
   behaviour and has no implementation.
2. Modifying a file after extraction does **not** produce new text under the
   old content hash; the new hash yields its own rows, and anchors bound to
   the old hash still resolve to the old text. *Status: schema and tested* for
   the key behaviour; the anchor-resolution half needs C1, which is not
   implemented.
3. Two extractions of the same bytes at the same version produce
   byte-identical text. Asserted by repeating, not once. *Status: none.* No
   extractor exists.
4. A `PdfLocator` with a character range resolves to exactly the characters
   in the stored text, and a range one character outside fails rather than
   clamping. *Status: none.*
5. Extraction never writes to the source. Asserted by reading the material
   bytes before and after a full ingest and requiring them equal, and by
   asserting `SourceMaterial.write` raises for the same path. *Status: none*
   for the ingest half; the read-only boundary itself already exists and is
   tested in its own right.
6. A scanned PDF yields `readability=UNREADABLE_NO_OCR` with a non-empty
   disclosure, and is **not** recorded as an empty page. *Status: schema and
   tested* for the disclosure, which is what the database can enforce; the
   scanned-PDF detection is LC-P1-08's work.

What the schema *does* enforce, and each is now demonstrated by a test rather
than assumed: the address key really constrains (SQLite compares NULLs as
distinct inside a UNIQUE index, so the typed locator columns alone would
constrain nothing); `locator_kind` and `sources.kind` and
`sources.readability` are closed vocabularies, so no shape check is satisfied
vacuously; each kind's shape names every column, so no row can claim to be a
text locator and a page and a spreadsheet cell at once; `relative_path`
refuses absolute, parent-escaping, Windows-separator and `.`-segment shapes;
and the migration and the models are compared on types, nullability, unique
constraints and CHECK bodies, not just column names.

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
