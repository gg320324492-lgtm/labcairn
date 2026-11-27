# Batch 17 review — the batch audited, and a name that was already out

**Date:** 2026-11-27
**Range reviewed:** `6b8e09f..40609d6` on `main` — the fifteenth batch's
delivery, carried by pull request #225, which is open.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.** The batch that pull request #225 carries: the CLI's own
model request, the removal that names itself in the log, the report's content
checks read and written down, the replay on the pilot copy, the two windows
that came after it, and the two reviews of the batch. Batches 15 and 16
already answered R1–R7 against their own pieces; **this review answers them
against the whole delivery**, and it covers the ground those two reviews
named as not covered.

## R1. No witness depends on a build artifact the runner does not have

**Pass.** Every new witness file was read for a dependency on something the
runner will not have: no `dist/`, no `build/`, no wheel or sdist path, no
`site-packages` reference. The six new test files
(`test_cli_suggest.py`, `test_dangling_source_read_faces.py`,
`test_source_removal_scope.py`, `test_source_removal_event.py`,
`test_store_migrations.py`, `test_pilot_records_carry_no_names.py`) read
only the tree and build their own premises.

## R2. No witness hard-codes one platform's facts

**Pass.** The same six files carry no `os.name`, no `sys.platform`, no drive
letter, no POSIX home path. The records name the machine and the tree they
were measured on, in prose, rather than a path a witness branches on.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** None of the six files contains a `skip`, a `skipif` or an `xfail`.
**No arm of them can pass by not running.** The shard coverage's own witness
is the third level here — it watches the partition — and it was run rather
than read.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass, and this is where the batch's failure was.** Every new record was
measured for Han runs and for the fullwidth enumeration comma: all seven are
clean. The three records that carry Chinese for other reasons —
`LC-P2-07-fidelity-baseline.md`, `LC-P2-25-guard-of-the-guards.md` and
`LC-P3-08-trial-record-2026-11-22.md` — carry the mentor's own rule
statements and the corpus's file names, in the owner's language, and each is
pinned in `CJK_RUN_CEILINGS` with a measured figure.

**Corrected 2026-11-27, by the classification batch.** It read every Chinese
run in the tree and gave each one a class. The trial record's corpus file
names were **not** the project's own voice: they carried the manuscript's
title-of-record, and they are redacted in place — the record says why, and
the rows stay identified by byte count and sha256. It carries no Chinese
now and is no longer in `CJK_RUN_CEILINGS`. The other two stand, with the
class the classification records for them: `design-quotation` for the
execution design's reader requirements in LC-P2-07, and `product-vocabulary`
for the overclaim detector's Chinese in LC-P2-25. See
[`LC-P4-PILOT-chinese-run-classes-2026-11-27.md`](LC-P4-PILOT-chinese-run-classes-2026-11-27.md).

**The review that answers R4 for the delivery finds one thing R4 does not
cover, and it is the finding below.**

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

**Pass on the batch's own rules, and one gap that the batch measured and did
not fix.**

The rules the batch implemented are stated and implemented together: the
`source_removed` event matches ADR-0004's account of what a removal writes;
the report's five checks match the gate's; the CLI's consent gate runs before
the approval is spent, and the thirteen witnesses in `test_cli_suggest.py`
hold that.

**The gap.** ADR-0004 I4 states: *"If `source_content_hash` no longer matches
the source, the record is **invalidated** — not silently refreshed — and
downstream artifacts are marked stale."* The implementation does not do this
on the attestation path. `src/labcairn/evidence/store.py::attest` moves a
record to `user_attested` — a state in `CITABLE_STATUSES`, which a report may
cite from — after checking that the record's **identifiers** resolved. It
never checks that the **source** its anchor names still exists, and never
compares the recorded hash against the source's current bytes. A source row
that has been deleted is the strongest case of the drift I4 names, and the
hash cannot even be observed, because there is no row to read it from.

So a record can be certified citable over a source that is gone. The batch
measured this across the product's faces and witnessed it, and said so; the
witness holds the behaviour **as it is**, so a face that learned to check the
source row again would turn it red. That is the shape a fix takes when the
fix is made. **This review did not design the fix, and the fix is the next
batch's work.**

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, after this review closed the batch's own debt.**

The batch's own records said the two newest witnesses carried `0.0` until a
runner supplied their numbers. **A runner has now supplied them.** The costs
were re-measured from the pull request's own completed run's log by
`.github/remeasure_shards.py`, which reads the per-file seconds out of the
`--durations=0` output rather than transcribing them:

| file | ubuntu-latest | windows-latest |
| --- | ---: | ---: |
| `test_source_removal_scope.py` | 1.33 s | 16.80 s |
| `test_dangling_source_read_faces.py` | 0.88 s | 8.42 s |

**No cost is `0.0` any more.** The anchor moved to `40609d6`, the partition
was rebuilt from the new numbers, and the three documents that print costs —
`.github/CI.md`, `.github/workflows/python.yml` and
`docs/plans/LC-P1-13-evaluation-ci.md` — were carried with the table. The
shard coverage's three cost witnesses were red until they were, and are now
green: **48 passed**.

The re-measurement also moved the partition and the floor's figures, so the
narration in `python.yml` was rewritten with them: Windows 1589.2 s × 6
(ratio 1.000), and on Ubuntu the floor is shard 0 alone — the single file
`test_drill_rewrite_interrupted.py` at 1206.1 s against 547.2 s for shards
2–5 and 604.7 s for shard 1 (max/min 2.204).

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The dangling-source witness builds the **premise** — a material
ingested, a claim recorded at one of its addresses, the material moved and
ingested again, and the row the old path left behind taken back by the
product's own removal — and then reads the product's own answers: the
records the task holds, the attestation it performs, the anchor that remains.
**No witness writes the answer it looks for.**

## The finding this batch produced: the name is already public

**The git history holds a name, and the repository is public.**

The delivery's own handoff said: *"whether the git history holds one — the
leak never left this machine, but no witness looks there."* **The first
half of that sentence is false, and the measurement is what says so.**

Two commits carry a Chinese personal name inside a document:

| commit | date | the document | Han runs | public ref |
| --- | --- | --- | ---: | --- |
| `e67269a` | 2026-11-01 | `docs/acceptance/second-corpus-absorption.md` | 3 | an ancestor of `origin/main` |
| `a399bfb` | 2026-11-27 | `docs/acceptance/LC-P4-PILOT-replay-2026-11-26.md` | 5 | an ancestor of `origin/claude/delivery-phase5` and of `refs/pull/225/head` |

Fetching either file at its commit over plain HTTPS, **with no credential**,
answers **200** with the runs in the body. The redactions — `f0f9cdb` and
`7fae861` — cleaned the **tree tips**; the blobs stayed in history, and
history is what a remote serves.

**Why this is a disclosure and not a stale tree.** The repository is public,
the rule this project works by is that a label carrying a person's name is
material, and the name was carried in a document that describes the owner's
unpublished corpus. The tree's promise — *"Nothing of the paper is in the
repository"* — is a promise about the repository, and the repository is the
history as much as the tip.

**And the tree's own budget could not have caught it.** `scripts/cjk_ceilings.py`
measures the **longest** Han run per tracked file, and
`tests/test_no_reference_leakage.py` pins those numbers. A file that already
carries a longer run measures the same after a short one is added to it.
Probed outside the repository: appending a four-character name to a file
whose longest run was 7 left the measurement at exactly 7, the pinned table
unchanged, and the witness green. The second mechanism does not cover it
either — `tests/test_pilot_records_carry_no_names.py` watches two globs under
`docs/acceptance/`, and inside its scope it catches a short name only because
that scope's rule is a zero-tolerance Han check rather than a budget.

**What is not decided here.** Rewriting published history on a public
repository is outward-facing and hard to undo; the objects and any cached
copies may persist; GitHub's process for purging cached views is the owner's
to start. **This review measures the options and their costs; it chooses
none and performs none.** The records that say otherwise are corrected in
place.

## The second reader

**A reader who has never seen the pilot can check every claim.** Each new
witness builds its own premise; the records' numbers name the command that
produced them; the material stays outside the tree.

**What a reader cannot repeat is the reading's own state** — the scratch
workspace a measurement ran against is gone with the run, and the records
say so.

## What this review did not cover

- **The gap itself.** A citable record over a deleted source is measured and
  witnessed; this review did not design the fix or say which face should
  refuse.
- **The remedy for the published history.** Measured here, decided by the
  owner.
- **Whether the other faces are consistent with the two that refuse.** The
  reading followed the faces the record names; it did not enumerate every
  face in the tree.
- **The record's own claims about the API** — the reading took the status
  codes the API returned, and it did not read the API's own contract for
  what it should return.
- **The git history's other documents.** This review measured the two
  commits that carry a name; it did not enumerate every blob in every
  revision.
- **Whether the same kind of leak exists in the earlier records that carry
  Chinese for other reasons.**
- **The cost of the two newest witnesses before this re-measurement**, which
  was `0.0` and is now measured.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| A record can be certified citable over a source that is gone | measured and witnessed; **closed the same day** — `store.attest` runs C1 before the move, the origin witness is flipped, and the mutation was re-checked here |
| The name is in the published history, and the repository is public | measured here, in the handoff, and in the records that said otherwise; the remedy is the owner's |
| The tree's Chinese budget cannot see a short name | measured here; the closing of it is the next batch's work |
| The two newest witnesses carried `0.0` | re-measured from the runner, the table rebuilt, the documents carried |
| The floor's figures and the partition moved | carried into `python.yml`, `CI.md` and `LC-P1-13-evaluation-ci.md` |
| The review itself | this document, and the handoff |

**Addendum, the same day.** The first row's fix landed while this review
was still open, and its own words are the reason it is here rather than
buried: the origin record said the witness holds the behaviour *as it is*,
so that a face which learned to check the source row again would turn it
red — *"which is the shape a fix takes when the fix is made."* The fix is
made. `store.attest` now runs **C1** — `check_source_exists`, reached
through the same `_run_check` that `advance` uses — and refuses with the
source's id named when the row is gone or its bytes have moved under it.
`attest_claim` maps that onto the new refusal code
`CITATION_SOURCE_UNOBSERVABLE`. The origin witness is **flipped**: the
reading stays as the control that the record is only `extracted` and not
citable, and the attestation now asserts the refusal. Four witnesses were
added by the window, and the mutation that restores the pre-fix early
return turns the four refusal witnesses red and leaves both controls
green — **re-checked independently here, not taken on the window's word.**

**A fifth was added here, because the surface's answer was a claim rather
than a measurement.** The fix's record says the CLI and the API inherit
the layer's refusal, and that inheritance is a claim about how a surface
renders an error. Measuring it by hand — driving the console script
whole, record a claim, take the source back with `sources remove`, then
attest — gave exit code **3**, the reason
`citation_source_unobservable`, and the source's id in the message. **A
hand measurement is not a witness**, so the path is now driven from the
command line by a test, and the mutation turns it red with the other
four.

Two edges the fix's own record names, and this review does not close
either: `advance` to `verified_by_rule` is not re-guarded against a
*stale passing* C1 entry written before the source was taken back, and a
source that was never readable at all is C1's `indeterminate`, which the
new gate refuses on as well — correctly, but not separately witnessed.
