# G3 — Formal acceptance

**Gate:** G3 (Evidence path)
**Work orders:** LC-P1-08, LC-P1-09, LC-P1-10
**Subject:** `main` @ `15a729f` — 303 tracked files
**Date:** 2026-10-20
**Scope of this document:** the gate's exit test, with the evidence for each of
the three work orders it spans, what the work found and fixed, and the one
rule of this repository's board that the gate cannot satisfy on its own.

## Gate exit test

> G3 — Evidence path: **correct source/cell locators, ledger, deterministic
> plot; evidence design ADR**

```
uv run python examples/g1_exit_demo.py       → exit 0, 36 checks
uv run python examples/g2_exit_demo.py       → exit 0, 14 checks
uv run python examples/g2_uncertain_demo.py  → exit 0, 18 checks
uv run python examples/analysis_demo.py      → exit 0, 19 checks
```

The first three are G1's and G2's, carried in because a gate is a claim about
the whole product and the earlier demonstrations are the only end-to-end
evidence the earlier gates produced. The fourth is LC-P1-10's, and it is the
one that carries the gate's own exit test: a figure drawn from a recipe, a
manifest that makes the derivation repeatable, and a changed input that leaves
a record saying so.

**The evidence design ADR** is [ADR-0004](../adr/ADR-0004-scientific-provenance-and-evidence-model.md),
and it is the document the three work orders are three readings of: what a
claim is, what it is bound to, and what may not be asserted without a check.
Two more ADRs carry the parts of it that the storage and the disclosure
needed: [ADR-0009](../adr/ADR-0009-material-and-extracted-text-storage.md) and
[ADR-0010](../adr/ADR-0010-readability-and-disclosures.md), with
[ADR-0011](../adr/ADR-0011-canonical-policy-matching.md) closing the seam
between them.

## Verification actually run at this commit

| Check | Result |
|---|---|
| The whole suite | **2600 passed, 2 skipped** (`uv run pytest -q`, 361 s, exit 0). The two skips are pre-existing and explain themselves: a provider credential this machine does not have, and a Windows-drive assertion that is meaningless on POSIX |
| `ruff check` / `ruff format --check` | clean |
| `mypy` (strict) | clean, 185 files |
| The four exit demonstrations | all exit 0, 87 checks between them |
| The status board's own consistency test | 113 passed, after every change to the board, the handoff file and the breakdown |
| Independent mutation checks | **71** written against the merged branches for LC-P1-10 alone, 63 caught; every survivor checked by hand before it was called a finding |

## LC-P1-08 — Material inventory and source locators

**Verdict: PASS WITH NOTES** — [acceptance review](../acceptance/LC-P1-08-acceptance.md).

The ingest path runs end to end through `SourceMaterial`, so the permission
boundary applies to ingestion and a denied subtree is invisible to it. The
adapters cover text, Markdown, CSV, XLSX and PDF, and each one's locators are
derived rather than hand-written.

**Eight defects were found and fixed, all of the same family: a docstring or
an ADR asserting a boundary the code did not enforce.** A two-column PDF
stored text the author never wrote and marked it citable; `UNREADABLE_NO_OCR`
was a dead state, so a scanned PDF came out `readable`; PDF page anchors were
unbound to their content, so rotating every page's text left all 26 PDF tests
green; CSV row locators counted records rather than physical rows; and
`ingest_into_store` could not be called twice on an edited file.

The two-column gap was decided by the owner — **detect and refuse**, not
record-only — and the thresholds are bracketed by measurement against the
three real fixture papers in both directions.

## LC-P1-09 — Local retrieval and evidence ledger

**Verdict: PASS WITH NOTES** — [acceptance review](../acceptance/LC-P1-09-acceptance.md).

The FTS5 index, the source-specific locators, and the evidence records with
their verification states, are in place, and the records are bound to sources
rather than merely mentioning them.

**Three review findings were fixed**: a query the index cannot serve was
reported as a miss; the miss message claimed more than a lexical search
establishes; and `superseded_by` was a column nothing ever wrote.

**Two clauses of the acceptance are not discharged**, and they are not
LC-P1-10's to fix: the *fabricated DOI* half has no implementation, and the
gap is structural — no record can carry an identifier, nothing resolves one,
and ingestion records none; and *source provenance preserved through report
generation* is LC-P1-11's.

## LC-P1-10 — Bounded scientific analysis and plots

**Verdict: PASS WITH NOTES** — [acceptance review](../acceptance/LC-P1-10-acceptance.md).

All eleven subtasks merged, from the chart library's decision to the exit
demonstration. The operators are vetted and registered, the selection is typed
and declares what it does with cells it cannot use, the manifest carries the
six fields the work order names and shares one hash lineage with the ledger,
and the figure is drawn from a declarative recipe with no code-execution
surface.

**Three findings the review made were closed before the verdict**: a unit
check that passed **vacuously** (the function that reads a column header's
declared unit had no caller in the production code, so a table that keeps its
units in the header found nothing to check); four properties no test observed;
and a caption drawn **across the axis tick labels**, found by the exit
demonstration.

**Two limits are recorded rather than closed**: the manifest names **no
version for the renderer**, so two figures whose manifests name the same
operator, recipe and environment can differ in their bytes because the
renderer changed between them; and the aggregate's numbers are not re-checked
by C1, C2 or C3, which is the work order's most important limitation and a
narrowing of the product's central promise.

## Cross-line integration

The three work orders are one system only if the facts they share are actually
shared, and the evidence for that is not three acceptance documents but three
places where the same rule is enforced.

- **One hash lineage.** The ledger's `content_hash`, the anchor's
  `bound_source_sha256`, the evidence record's `source_content_hash` and the
  manifest's input hash are **the same value** — SHA-256 of the file's raw
  bytes — and the manifest's builder refuses to produce a manifest in which
  they are not. The plan warned against adding a third implementation of that
  hash; there are two, and the third was not written.
- **One cell address.** The locator LC-P1-08 derives is the one LC-P1-09
  cites and the one LC-P1-10 reads: `k=3:csv|r=1:2|c=5:value` names the
  format, the physical row and the column, and the exit demonstration prints
  that address beside the number it produced.
- **One unreadable rule, three places.** A source whose readability is not
  `readable` is excluded from the index, from citation, and from analysis —
  and is not an empty one in any of the three.
- **One consent machinery.** The approval the run path consumes is the same
  one the ledger already used, bound to the capability, the resource key and
  the arguments' digest, so an approval to analyse one selection does not
  authorise another.

## Defects found and fixed during G3

Fourteen, across the three work orders, and they are worth counting
because they are not one kind of defect: **a docstring or an ADR asserting a
boundary the code did not enforce** (LC-P1-08's eight, including the two-column
PDF that stored sentences the author never wrote and marked them citable);
**a check that looked like a check and was not** (LC-P1-10's vacuous unit
check, and the four properties no test observed); **a message that was true of
one case and false of another** (LC-P1-09's miss message, and the policy
denial reported with the message an unanswered question gets); **a layout
that assumed what it should have measured** (the caption across the tick
labels); and **a published claim that the measurement contradicted** (the
plan's T07 table said matplotlib writes a creation date into PNG metadata; it
does not, and PNG needs neither determinism control).

## Independent cross-review

**There is none, for any of the three work orders, and that is the gate's one
unmet condition.**

The board's rule is that a row is marked done only when an **independent**
review at a named commit says so. The reviews that produced these findings
and the fixes that answered them were the same party in all three cases. The
owner has already recorded one decision of this kind — LC-P1-08 proceeded to
LC-P1-09 without an independent review, on 2026-10-18, and the board says so
rather than dressing it up as a review.

What an independent reviewer would still want to look at, in the order the
reviewers themselves named it:

- LC-P1-08's two-column detector's 35% threshold, which is bracketed against
  single-column fixtures rather than calibrated against two-column ones;
- LC-P1-10's manifest not naming a version for the renderer, and the recipe
  check comparing the file's bytes rather than the parsed models;
- the exit demonstrations of G1 and G2, which **no test and no CI job runs**,
  so they can rot without anyone noticing — LC-P1-10's demonstration is
  covered by a test, and the earlier ones are not.

## Gate verdict

**The gate's exit test is met, and the gate's work is complete.** Three work
orders, each accepted with notes; the locators, the ledger and the
deterministic plot are all in place and demonstrated end to end; the evidence
design ADR exists and the three work orders are readings of it.

**The gate cannot be marked closed by this document, because the board's rule
is not satisfied and only the owner can decide to set it aside.** That is the
same situation LC-P1-08's row records, and the recommendation is the same: the
exit test is met, the work is done, and the condition that is outstanding is a
review by someone who did not write the fixes. **The review recommends that the
owner close G3, and records that the closure rests on that decision rather than
on an independent review.**

**And on 2026-10-20 the owner declined the exemption.** G3 is to be closed
**after an independent review**, not instead of one — the rule is to be
satisfied, not waived, and the difference from LC-P1-08 is deliberate. G4
proceeds in the meantime; the gate's closure waits for a review by someone who
did not write the fixes. The three things such a reviewer would want to look at
are named above, and the verification this document records is written so that
they can be re-run rather than taken on trust.

## Open items carried beyond G3

- **The fabricated-DOI half of LC-P1-09's clause** — still no implementation,
  and the gap is structural rather than a missing line.
- **Source provenance preserved through report generation** — LC-P1-11's, and
  the reason the ledger's records reach a report is not yet built.
- **An aggregate's numbers are not re-checked by C1, C2 or C3** — traceable to
  the file and to the manifest, and not re-derived at gate time.
- **The manifest names no version for the renderer** — and the recipe check
  compares the file's bytes rather than the parsed models.
- **The exit demonstrations of G1 and G2 are run by nothing.**
- **No independent review of any of the three work orders.**
- **The repository still has no LICENSE file**, and matplotlib's bundled fonts
  bring an obligation the root licence line does not cover — both are G5's.
