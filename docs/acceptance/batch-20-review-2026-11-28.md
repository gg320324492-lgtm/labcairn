# Batch 20 review — what the Chinese is, and a door that asks the source

**Date:** 2026-11-28
**Range reviewed:** the two windows merged into `main` after batch 19's
review: the classification of every Han run in the tree, and the report's
door asking every citable record about its source.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.** Two windows, and the seam between them: the second one
is the answer to the gap the first one's review left open, and the seam is
where a batch is either one piece or two.

**A note on the order.** Batch 19's review found that a report over an
attested claim whose source had moved was written successfully, and the
receipt said `current`. This batch's second window closes that gap, and this
review re-ran the review's own probe — unchanged — against the merged tree.

## R1. No witness depends on a build artifact the runner does not have

**Pass.** The classification witness reads the tracked tree and the
registry; the tool it uses (`scripts/cjk_ceilings.py --classify`) reads text.
The drift window's witnesses drive the console script through the project's
own rig and build their ledger with the product's own writes. Neither names a
`dist/`, a `build/`, a wheel or a `site-packages` path.

## R2. No witness hard-codes one platform's facts

**Pass.** The classification witness names Chinese characters **by code
point** (`chr(0x…)`), so the rule does not depend on an encoding, a locale or
a console. The drift window's witnesses use the shared `run_cli` rig, so the
console script is **derived** rather than spelled a second time.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** The classification witness has two guards over the same rule and
each has its own arm: the **allowed class set is written in the test**, not
read from the registry (so relaxing a file's class cannot hide the rule in
the other), and the **name shape is checked independently of the registry**
(so a name re-pinned as `project-voice` still reddens). Neither new witness
file contains a `skip`, a `skipif` or an `xfail`: **measured, 0**. The four
skips in `tests/test_no_reference_leakage.py` are **pre-existing** — the
window added none (measured: 10 occurrences before its merge, 10 after).

**And the drift window's own blind spot is named rather than hidden:** the
defensive branch — a citable record whose log records a C1 that *agrees* with
a present failure — is reasoned but not witnessed, because the store's doors
refuse that state on the way in and reaching it needs a direct SQL edit. The
record says a witness built that way would test the test's own edit. **That
is the right answer**, and it is written down instead of being papered over.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** Both new records carry **no Han run** (measured: 0 characters) and
no fullwidth enumeration comma. The registry itself carries **no Han
character** (measured) — it holds digests, lengths and classes, and a reader
re-derives any entry from the tree.

**The judgement the window made, which is the owner's to accept.** The
design quotations — the execution design's rules, quoted verbatim
throughout the ADRs, the plans and the records — were classified
`design-quotation` and **kept**, with the reasoning that they are the tree's
own specification and not the manuscript. The four reader requirements in
`LC-P2-07-fidelity-baseline.md` §4.6 fall in the same class and carry an
English paraphrase beside each. The record states the reasoning; the ruling
is the owner's, and this review does not make it.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

**Pass.** The classification's rule is the owner's standing one — *the
repository keeps desensitised metadata, summaries, ids and paths, and a label
that carries a person's name is material too* — and the implementation is the
registry plus the two guards. Every run the tree holds is registered, every
registered class is checked against the allowed set written in the test, and
the name shape is refused whatever the class says.

**The drift window's rule is ADR-0004 I4** — a record whose
`source_content_hash` no longer matches its source is invalidated, not
silently refreshed — and it is implemented **where the rule lives**: the gate
asks C1 for every citable record, whether or not the log holds a C1 to
re-run, and the report compares the file with the ledger's account before it
writes anything.

**The two enforcement points do not disagree about the same fact.** The gate
asks the ledger; the report asks the **file**; and the ledger's hash is never
refreshed, so the second question is not the first question asked twice. The
record says this in its own words, and the refusal it produces names the
source, the ledger's hash and the file's hash — all three.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, and the batch's own debt is paid.** The classification window
**re-measured both quantity pins at its tree** rather than carrying them
forward: files carrying Chinese **56 → 53**, Han characters **13,139 →
13,074**, Han runs **1,971 → 1,956**, and the two pins' entries **56 → 53**
each. The registry the window shipped holds **53 files and 1,956 runs**
(measured, and it matches the record).

**Three files carry no Chinese now and dropped out of both tables** (the
trial record, the exit decision, the LC-P2-11 task breakdown); two files kept
a shorter run and their totals were **re-measured, not adjusted** (ADR-0014
121 → 113, readerB 11 → 5).

**The new files carry `0.0` cost until a runner measures them**, and they are
filed in the manifest and in a shard, so CI will run them.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The classification's registry is **derived from the tree and
compared against it** — a new, removed, reordered or same-length-replaced run
reddens — so it cannot be fooled by a stale registry, and the name shape is
checked independently of it.

**The drift window's witnesses build the premise and read the product's
answers.** And this review did the strongest thing available: **it re-ran the
review's own probe, unchanged, against the merged tree.**

| | before | after |
| --- | --- | --- |
| `labcairn task report --json` over an attested claim whose source moved | exit **0**, the report written, receipt `current` | exit **3**, **nothing written** |
| the refusal | — | `report_evidence_refused`, naming the source, the ledger's hash and the file's hash, citing ADR-0004 I4 |

**The same script, the same synthetic material, the same command.** The
window measured this too, against its own worktree, and got the same answer.

## What this review found that the batch did not say

**The published history still carries the labels and the names.** Measured on
2026-11-28, over `origin/main` and the delivery head, with the tree's own
definition of a name-shaped run (one surname and one title): **17 blobs in 4
files** — `docs/adr/ADR-0014-paper-revision-provenance.md` (5),
`tests/docx_corpus.py` (8), `docs/plans/LC-P2-11-task-breakdown.md` (3) and
`docs/acceptance/second-corpus-absorption.md` (1) — plus the corpus labels in
three more files' histories, all of them **ancestors of `origin/main`**
(measured, not read). The tree's tip is clean; the history is not.

**The owner's decision, made on this measurement: split it in two.** The
delivery line is rewritten now; `main`'s history is a batch of its own, with
its own run. The costs are in the record and the card.

**The citations in the records are not witnessed.** The tree checks that the
**status board's** cited commits exist; the hashes the acceptance records and
the handoff cite are not checked by any test. The rewrite re-pointed **66
citations in 15 files** with a script of its own, and **0 stale citations
remain** (measured) — but a wrong re-pointing would have been caught by
nothing. A witness for that is open work.

**The CLI's human-readable output does not show the gate's verdict.** The
result carries `evidence_gate` and `unjudged_records`, and the API's contract
exposes both; the CLI's rendered table prints neither, so a reader at the
command line cannot see which records the gate judged. The refusal — the
part that matters — is rendered on both surfaces.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| The tree's Chinese was measured but never judged | closed — every run registered by digest, length and class; the runs that did not belong removed, each record saying why |
| A name re-pinned as an allowed class would pass | closed — the name shape is refused independently of the registry |
| An attested record's source could move and the report still went out | closed — the gate asks every citable record, and the report compares the file with the ledger before writing |
| The published history still carries the names | measured; the owner's call was to split it, and the second half is the next batch |
| The records' citations are not witnessed | open — named here, and in the next batch's card |
| The CLI's table does not show the gate's verdict | open — named here |
| The new files' costs | `0.0` until a runner measures them; filed in the manifest and in a shard |
