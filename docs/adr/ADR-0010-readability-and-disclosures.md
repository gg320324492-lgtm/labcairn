# ADR-0010: A third readability state, and where a disclosure is stored

**Status:** Accepted — amends a contract frozen by LC-P1-02
**Work order:** LC-P1-08 (material inventory and source locators)
**Date:** 2026-10-17

> This ADR **modifies a frozen contract.** `SourceReadability` and `Source` come from
> LC-P1-02, which declared them fixed. The project owner's standing rule is that
> status, technical decisions, acceptance results and implementation standards
> change through a PR, and that anything material is escalated. A frozen contract
> that cannot record the truth is not a contract worth freezing, so the change is
> made here rather than worked around — and the owner is told, rather than
> discovering it later.

## Context and concrete problem

LC-P1-08 wrote an ingest pipeline, and review asked the obvious question of it:
what happens to a file this project cannot read?

Nothing good. `ingest_bytes` recorded every such file as
`SourceReadability.READABLE`, and a workbook that would not open was inventoried,
hashed, and filed under a claim that says it **"may be indexed and cited."**

That is false. The file produced no cells. A citation resolved against it would
resolve to nothing, which is precisely what ADR-0004 exists to prevent.

The alternatives were both false too. `UNREADABLE_NO_OCR` asserts *no text
layer* — a claim about a scanned page, which is a different thing from a
corrupt container, an encrypted workbook, or a file whose `.xlsx` extension is a
lie. Recording it would have been a second falsehood, in the same row, and a
subtler one because it would have looked handled.

And the disclosures had nowhere to go. Every adapter in `labcairn.material`
produces `ExtractionProblem` records — why a workbook would not open, why a cell
holds a formula whose result is not stored, why a sheet is empty — and **nothing
in `src/` wrote them anywhere**. They were returned to a caller and dropped.

`readability_disclosure` could not absorb them, and the reason is in LC-P1-02's
own validator: a disclosure is required exactly when a source is not readable and
**forbidden** when it is. So a file that opened perfectly and produced three
disclosures had no legal place to put any of them.

That makes the whole disclosure apparatus decorative, and the project already
made this argument once, about `readability_disclosure` itself: a disclosure
nobody has to write is a disclosure nobody writes. The same holds for a
disclosure nobody has anywhere to put.

## Decision

**Two changes.**

**A third member, `SourceReadability.UNPARSEABLE`.** The bytes could not be
parsed at all: corrupt, encrypted, truncated, or not the format its name claims.
Ingestable and hashable, **not citable**, and — like `UNREADABLE_NO_OCR` —
carrying a non-empty `readability_disclosure`.

The vocabulary stays small on purpose. It answers one question: *can these bytes
become addressable text?* Three states, and the second and third exist because
"we could not look" and "there was nothing there" and "the file is broken" are
three different facts that a two-member vocabulary has to conflate. Every
non-readable member now requires a disclosure and a readable one forbids it, so
the validator's rule became *"not readable ⟺ disclosed"* rather than naming one
member.

**A place to put the other disclosures.** `source_problems`, keyed
`(source_id, extraction_version, code, location)`. The extraction version is in
the key because a disclosure is a fact about *an extraction*, not about a file:
the same workbook read under a later library version may disclose differently,
and overwriting would lose the earlier statement.

`location` is a not-null sentinel rather than a nullable column, because SQLite
compares NULLs as distinct inside a UNIQUE index — a nullable location would
make "the same whole-file problem, once per run" succeed, forever.

## What this costs

- `SourceReadability` is no longer the two-member vocabulary LC-P1-02 froze, and
  the migration rebuilds `sources` because SQLite cannot ALTER a CHECK. The
  parity test compares types, nullability, unique constraints and CHECK bodies,
  so the rebuild is verified rather than trusted.
- The downgrade deliberately **does not** narrow the vocabulary back. Doing so
  would refuse a database legitimately holding an `UNPARSEABLE` row, and
  refusing a downgrade that would lose a truthful record is worse than a schema
  that stayed wider than its predecessor. This is a known asymmetry and it is
  recorded rather than hidden.
- A material that cannot be read is now visibly distinct in the store, which
  means some downstream query written against "readable" sees a third state.
  That is the point, and it is also a change.

## Re-evaluation trigger

Re-open if a fourth state proves necessary — for example material whose *format*
is readable but whose encoding is not, which today lands in `UNPARSEABLE` with a
disclosure saying so. The test is whether the disclosure alone is enough for a
reader to decide whether the material is citable; if it is not, the vocabulary
was too small and should grow again.
