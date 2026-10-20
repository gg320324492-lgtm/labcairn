# G3 — Formal acceptance

**Gate:** G3 (Evidence path)
**Work orders:** LC-P1-08, LC-P1-09, LC-P1-10
**Subject:** `main` @ `15a729f` — 303 tracked files
**Independent review:** of the tree at `d114810` — **PASS WITH NOTES**, the
section [Independent cross-review](#independent-cross-review) below
**Date:** 2026-10-20
**Scope of this document:** the gate's exit test, with the evidence for each of
the three work orders it spans, what the work found and fixed, and the
independent review that discharged the board's rule.

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

## Verification actually run

**Two runs, at two named commits, and neither of them is the current tip.**
This document's own numbers were run at `15a729f`, the subject of the gate.
The second table is the **independent reviewer's own run at `d114810`** — the
tree the review saw — and its numbers are the reviewer's evidence, not this
repository's current state. `main` has moved since `d114810`, so nothing in
this section is a claim about the tip.

**This document's own run, at `15a729f`:**

| Check | Result |
|---|---|
| The whole suite | **2600 passed, 2 skipped** (`uv run pytest -q`, 361 s, exit 0). The two skips are pre-existing and explain themselves: a provider credential this machine does not have, and a Windows-drive assertion that is meaningless on POSIX |
| `ruff check` / `ruff format --check` | clean |
| `mypy` (strict) | clean, 185 files |
| The four exit demonstrations | all exit 0, 87 checks between them |
| The status board's own consistency test | 113 passed, after every change to the board, the handoff file and the breakdown |
| Independent mutation checks | **71** written against the merged branches for LC-P1-10 alone, 63 caught; every survivor checked by hand before it was called a finding |

**The independent review's own re-run, at `d114810`:**

| Check | Result |
|---|---|
| `ruff check` | clean |
| `ruff format --check` | 217 files |
| `mypy` (strict) | clean, 201 files |
| The whole suite | **2721 passed, 2 skipped** (451 s) |
| The four exit demonstrations | all exit 0 — 36 / 14 / 18 / 19 checks |

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
record-only — and the threshold is bracketed by measurement against the three
real fixture papers in the false-positive direction; the two-column direction
is asserted rather than measured, and the band below the threshold is a
residual the independent review found stated nowhere (F2 below).

**The independent review broke this work order's fixes and no mutation
survived.** It added two findings: the PDF adapter's own docstring still
denied the detector it implements (F1), and the coverage band below the
threshold was unstated (F2). Both are fixed in `f0f7563`.

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

**The independent review broke this work order's three fixes and no mutation
survived**: `test_a_query_the_index_cannot_serve_is_a_failure_not_a_miss`;
`test_the_two_negatives_cannot_be_the_same_value`, which is the *sole* guard on
the miss message's scope and holds in both directions; and the two
`superseded_by` tests. The review did not check the two undischarged clauses.

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

**The independent review broke this work order's fixes and no mutation
survived** — the declared unit, the four unobserved properties, the caption
layout, and the two more that sit in the fixes table rather than among the
fourteen. It looked at the two limits above and found the manifest's missing
renderer version and the recipe check's byte comparison to be **stated limits
rather than defects**: deliberate, written down in the plan's §5, and in the
second case with the owner named.

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

**The independent review added three more**, of a kind the fourteen already
were — a docstring that denied a detector the code implements, a coverage band
whose consequence was nowhere stated, and an ADR credit in two test
docstrings. They are recorded in their own section below.

## Independent cross-review

**There is one, of the tree at `d114810`, and its verdict is PASS WITH
NOTES.** The reviewer wrote none of G3's fixes. The board's rule — a row is
marked done only when an **independent** review at a named commit says so — is
satisfied for all three work orders.

The reviewer's own report is a document outside this repository; what it holds
is recorded here, so that the review the gate closes on can be read in the
repository.

**The method: every fix broken, and the test never touched.** Each of the
gate's fourteen fixes was reverted to its pre-fix behaviour by mutating the
implementation only — never the test — and the reviewer's claim was that a
named test fails. **No mutation survived.** Where a second guard also fires,
the reviewer says so rather than calls it a finding: for #12 the corpus tests
fire too, and for #10 that one test is the *sole* guard, in both directions.
The reviewer's own re-run of the gates, at `d114810`, is the second table in
"Verification actually run" above.

### The mutation table

Every fix broken — implementation only, never the test.

| # | Fix | Mutation | Named test that caught it |
|---|---|---|---|
| 1 | Two-column refusal | share 0.35→0.60; →0.20 | `test_a_two_column_page_is_refused_rather_than_spliced` + `test_a_refused_page_does_not_become_a_citable_source`; `test_no_real_paper_is_refused_as_two_column` |
| 2 | `UNREADABLE_NO_OCR` live | `_NO_TEXT_LAYER` emptied | `test_a_page_with_no_text_is_unreadable_not_empty` |
| 3 | Page anchors bound | page N's text read from page N−1 | `test_each_page_number_carries_that_pages_own_text` |
| 4 | CSV physical rows | `previous_end+1` → record ordinal | `test_a_row_is_numbered_by_where_it_sits_in_the_file_not_by_its_ordinal` |
| 5 | `walk.py` cross_root | docstring only — `CROSS_ROOT` is still only in `security/paths.py`, never consulted by `list_dir` | none (documentation fix) |
| 6 | `source_id` from path | content-derived id restored | `test_editing_a_file_does_not_make_it_a_new_material` |
| 7 | Three docstrings | 2 of 3 corrected; the PDF adapter's is **not** — F1 | n/a |
| 8 | ADR credit | **half closed** — F3 | n/a |
| 9 | Refused ≠ miss | `query_is_servable` guard removed | `test_a_query_the_index_cannot_serve_is_a_failure_not_a_miss` |
| 10 | Miss-message scope | "lexical" dropped; overclaim restored | `test_the_two_negatives_cannot_be_the_same_value` (sole guard, both directions) |
| 11 | `superseded_by` | UPDATE removed; replacement unwritten; cross-task guard dropped | `test_superseding_keeps_the_old_record_and_marks_it`; `test_a_record_cannot_be_superseded_across_tasks` |
| 12 | Declared unit | `declaration_disagreement`→`None`; no-token cell contradicts | 9 and 10 tests respectively |
| 13 | Four unobserved properties | excluded-count check removed; filtered count→0; id grammar removed; value+reason validator removed | `test_the_excluded_count_must_agree_with_the_groups`; `test_the_result_counts_the_rows_the_selection_did_not_name`; `test_a_malformed_reference_is_refused`; `test_a_group_may_not_carry_a_value_and_a_reason_at_once` |
| 14 | Caption layout | old constant `_TEXT_TOP=0.33` restored | `test_the_caption_does_not_overlap_the_axis_labels`; `test_a_taller_axis_label_pushes_the_caption_down_rather_than_under_it` |

The share in row 1 is the threshold as it stood at the commit reviewed; it is
**30%** now, after `f0f7563` (F2 below).

Two more, in the LC-P1-10 fixes table rather than the fourteen, were broken
too and caught: the policy-denial message
(`test_a_denied_policy_is_refused`) and the manifest's emptied `parameters`
(`test_the_manifests_parameters_are_the_operators_own_arguments`).

### The three named items

The three things this document said an independent reviewer would want to look
at, in the order the reviewers themselves named them.

**1 — the 35% threshold.** Not calibrated; the rule is correct, but the
**consequence** of a page below the band was stated nowhere. `share_needed =
ceil(n*0.35)`, so a rival must hold **more than 35%** of the line starts. The reviewer's hand-built PDFs (248 pt gutter,
the repository's own geometry): 50/44/40% refused; **35% and below not
refused**. A 6-line-left / 24-line-right two-column page is stored `readable`
and citable with its columns spliced into `'LEFT … 0 RIGHT … 0'` — the
original fabrication, in a narrower band. ADR-0008 states the rule and states
the band; what it did not state was the **consequence** of a page below the
band, and this acceptance stated only the sub-80 pt gutter and rotated text.
The justification "a genuine two-column page splits near evenly" is asserted,
never measured. — **F2**, below.

**2 — manifest / recipe check.** The manifest carries no renderer version and
none of the renderer's build parameters (figure size, bin count,
declared-settings digest); `RenderEnvironment` holds only matplotlib's
version, salt, fonts, platform. This is a **stated** limit
(`RenderEnvironment`'s docstring and the plan's §5), not a quiet gap. The
recipe check compares file bytes, so a caller handing the renderer a different
parsed recipe is unnoticed — also **stated** in the plan's §5, with the owner
named ("the one who calls the renderer is the one who would have to lie").
Deliberate limit, not a defect. The figure's own receipt carries its bytes'
hash.

**3 — G1/G2 exit demonstrations.** The claim is **true**: no test and no CI job
runs them; only a comment in `test_analysis_demo.py` mentions them. They have
not rotted — 36, 14 and 18 checks, exit 0, at `d114810`.

### Three findings the acceptance documents did not record

All three are fixed in `f0f7563`, the commit that carried the
two-column band into the tree.

**F1 — the PDF adapter's docstring denied the detector it implements.**
`src/labcairn/material/pdf.py`'s module docstring still said *"Why no column
detection … so there is no such rule here … This adapter cannot detect that
page and does not pretend to"*, while the same module implements
`_two_column_evidence` and refuses such pages. The paragraph dates from
`221bd91`; the detector was added in `d5e9d89` without updating it. This is
LC-P1-08 defect 7's own family, reopened by its own fix. **Fixed in
`f0f7563`:** the docstring now says what the code does, names the threshold
and the band, and states the residual. The same document in ADR-0008 carried
two more claims of the same kind — "the adapter cannot detect the page it
happens on" and a heading "Why there is no detector" — and both were corrected
in the same commit.

**F2 — the coverage band below the threshold.** The review's wording was that
"ADR-0008 states the rule but not the band", and the band was in fact stated
there; what was missing was the **consequence** of a page below it. The band,
plainly: at the commit reviewed, a rival column holding **35% or below** of the
page's line starts was not a two-column page. The consequence, plainly:
such a page was stored `readable` and was citable, and its columns were
spliced into the extracted text — the fabrication the refusal exists to
prevent.

**The owner decided on 2026-10-20 to price the residual and narrow the
band.** The threshold drops from 35% to **30%**, the lowest share that refuses
nothing in the real corpus — the corpus's own single-column pages cluster at
20–26%, so 30% is the edge of the measured band rather than a point chosen
inside it. The residual below it is now **stated** in ADR-0008 and in the
adapter's docstring rather than implied — a two-column page whose rival column
holds **under 30%** of the page's line starts is stored `readable`, with its
columns interleaved — and it is **pinned by a test of its own**,
so it is a limit that is visible.

**The band cannot be closed with this signal.** The real single-column pages
the same rule would also catch cluster at 20–26% of their line starts, in the
same place, so any threshold that closed the residual would refuse seven
pages of good prose. The one thing that would calibrate the other direction —
two-column CC-licensed material — could not be obtained; ADR-0008 records the
search. **Fixed in `f0f7563`**, with the residual's own test.

**F3 — the ADR credit in two test docstrings.** `tests/test_material_walk.py`
(lines 367 and 410) still credited "ADR-0004 A2" for old text surviving. A2
(ADR-0004, line 349) says only that drift makes C1 return `fail`; the clause
that says the old text survives is ADR-0009's item 2. `test_material_indexing.py`
had been corrected; this one had not. **Fixed in `f0f7563`:** both docstrings
credit ADR-0009's item 2, and they say what A2 is about.

### What the review did not check

The fabricated-DOI half and report-generation provenance (both recorded as
undischarged); C1/C2/C3 arithmetic; ADR-0004's twelve conditions re-derived;
G1/G2's own work; ADR-0008's eleven-paper corpus claim; the G4
application/report layer; `docs/handoff/`.

The reviewer's tree was left clean — mutated, run, and reverted with
`git checkout --`; no commits, no stash.

## Gate verdict

**The gate is closed.** Two things are true, and this document has kept them
apart for months because only one of them was ever in question.

**The exit test is met, and the gate's work is complete.** Three work orders,
each accepted with notes; the locators, the ledger and the deterministic plot
are all in place and demonstrated end to end; the evidence design ADR exists
and the three work orders are readings of it. That was true at `15a729f`, and
the independent review re-ran all four exit demonstrations green at `d114810`
— the tree it reviewed, which is not the tip.

**The condition that was outstanding is now discharged.** On 2026-10-20 the
owner declined the exemption and decided that G3 closes **after an independent
review**, not instead of one — the rule is to be satisfied, not waived. The
review has happened: at `d114810`, by a reviewer that wrote none of the fixes,
verdict **PASS WITH NOTES**, and **no mutation surviving** — each of the
gate's fourteen fixes was broken and every one was caught by the test it names.
The three things such a reviewer would want to look at are answered above: the
two-column band by a finding and a fix, the manifest and recipe limits by the
finding that they are deliberate and stated rather than quiet, and the exit
demonstrations by the finding that the claim is true and they have not rotted.
The three findings the review added are fixed in `f0f7563`.

**The closure therefore rests on the independent review and not on an
exemption**, and the board's rule — a row is marked done only when an
independent review at a named commit says so — is satisfied for LC-P1-08,
LC-P1-09 and LC-P1-10.

**What is carried forward is what the review confirmed as a limit rather than
a defect**, and it is listed below: the manifest's missing renderer version,
the exit demonstrations of G1 and G2 that nothing runs, the aggregate's numbers
that C1, C2 and C3 do not re-check, and the two-column residual under 30%.
The review did not check the fabricated-DOI half, report-generation
provenance, C1/C2/C3 arithmetic, ADR-0004's twelve conditions re-derived,
G1/G2's own work, ADR-0008's eleven-paper corpus claim, the G4 layer, or
`docs/handoff/`.

## Open items carried beyond G3

- **The fabricated-DOI half of LC-P1-09's clause** — still no implementation,
  and the gap is structural rather than a missing line. The independent review
  did not check it.
- **Source provenance preserved through report generation** — LC-P1-11's, and
  the reason the ledger's records reach a report is not yet built. The
  independent review did not check it.
- **An aggregate's numbers are not re-checked by C1, C2 or C3** — traceable to
  the file and to the manifest, and not re-derived at gate time. The
  independent review did not re-derive C1, C2 or C3's arithmetic.
- **The manifest names no version for the renderer** — and the recipe check
  compares the file's bytes rather than the parsed models. The independent
  review looked at this and found it a **stated limit rather than a defect**:
  the manifest carries no renderer version and none of the renderer's build
  parameters (figure size, bin count, declared-settings digest), and
  `RenderEnvironment` holds only matplotlib's version, salt, fonts and
  platform. Both facts are written down — `RenderEnvironment`'s docstring and
  the plan's §5 — and the second is written down with the owner named: *"the
  one who calls the renderer is the one who would have to lie."* The figure's
  own receipt carries its bytes' hash.
- **The exit demonstrations of G1 and G2 are run by nothing** — the claim holds.
  No test and no CI job runs them; only a comment in `test_analysis_demo.py`
  mentions them. They have not rotted — 36, 14 and 18 checks, exit 0, at
  `d114810` — but nothing runs them, so they still can.
- **A two-column page whose rival column holds less than 30% of the page's
  line starts is not refused** — it is stored `readable`, it is citable, and
  its columns are interleaved in the extracted text. The band **cannot be
  closed with this signal**: the real single-column pages the same rule would
  also catch cluster at 20–26%, in the same place, and the two-column
  CC-licensed material that would calibrate the other direction could not be
  obtained (ADR-0008 records the search). The residual is stated in ADR-0008
  and in the adapter's docstring and pinned by a test of its own.
- **The repository still has no LICENSE file**, and matplotlib's bundled fonts
  bring an obligation the root licence line does not cover — both are G5's.
