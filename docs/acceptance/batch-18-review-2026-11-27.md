# Batch 18 review — a name in the published history, a chain over a bare document, and a budget that could not see

**Date:** 2026-11-27
**Range reviewed:** `fbffd9a16fad6921eac958699233d4c7a3ac4b18..c7e275618ae09b00a8e0e3a363cd674eb194a212` on `main` — the three windows that
closed what batch 17's review found: the attestation's source check, the
name watcher's total load beside the history's cost, and the role chain
over a document the advisor never wrote in. Pull request #225 is open and
carries the batch.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.** Three windows: the attestation's source check, the
name watcher's total load beside the history's cost, and the role chain over
a document the advisor never wrote in.

**A note on the order.** Batch 17's review found the ground this batch was
to cover, and this batch is its answer. Where the two disagree, the
measurement wins — and one place where batch 17's own review was wrong is
corrected below.

## R1. No witness depends on a build artifact the runner does not have

**Pass.** Neither new witness file names a `dist/`, a `build/`, a wheel, a
sdist or a `site-packages` path. The comment-less run's witnesses build
their own premises — a chain whose manuscripts carry no comment, a project
holding two versions and a key — through the product's own operations.

## R2. No witness hard-codes one platform's facts

**Pass, after a correction made here.**

The comment-less run's command witness **built the path to the console
script itself**, naming the binary with a second spelling of the platform
fact (`sys.platform` against the project's `os.name`). **A second spelling
of one fact is the thing this rule is about** — the same fact told two
ways can be told two ways wrong, and this project's own history has a
witness that was hollow for exactly that reason.

The correction is to use the derivation the project already has, and it
brings what the project's other CLI witnesses set: `COLUMNS` at two hundred
and the child's encoding. **That is not a detail** — the CLI renders
through Rich, Rich asks the terminal how wide it is, and a pipe is not a
terminal, so a wrap that falls *inside* a phrase truncates it and an
assertion about that phrase fails for a reason that has nothing to do with
the property under test. The hand-rolled subprocess had neither.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** Neither new witness file contains a `skip`, a `skipif` or an
`xfail`. **No arm of them can pass by not running.**

The new totals pin is itself a guard of a guard — a pin beside the
longest-run budget — and **it witnesses its own blind spot**: it appends a
run *shorter* than the file's existing longest and shows the longest run
**not moving** while the total **does**. The old pin's blind spot is
demonstrated rather than asserted.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** Both new records carry no Han run and no fullwidth enumeration
comma. The names witness holds them.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

**Pass.** The rule the batch implemented is the one the ADR already states:
ADR-0004 I4 — a record whose `source_content_hash` no longer matches the
source is invalidated, not refreshed — and the implementation runs **C1**,
the check that decides it, reached through the same `_run_check` that
`advance` uses. The refusal names the source and carries C1's own detail.

The comment-less run's rule is stated in the record and implemented where
the rule lives: **the chain's state, not the request's shape.** A chain
that holds no comment at all is a shape like any other, and a chain that
holds comments but not under the key the request named is **still refused
exactly as it was** — same reason, same place, same witnesses. The refusal
did not move; the branch did.

**Two edges the fix's own record names, and this review does not close
either.** `advance` to `verified_by_rule` is not re-guarded against a
*stale passing* C1 entry written before the source was taken back, and a
source that was never readable at all is C1's `indeterminate`, which the
new gate refuses on as well — correctly, but not separately witnessed.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, and the batch's own debt is paid.** The two witnesses that carried
`0.0` were measured from pull request #225's completed run's log, the
anchor moved, and the three documents that print costs were carried with
the table.

**Three new files now carry `0.0`** — `test_attest_source_presence.py`,
`test_chinese_totals_pin.py` and `test_role_run_commentless.py`. They are
filed in the manifest and in a shard, so CI will run them; the number is
what is owed, and it comes from a runner and not from here.

**The tree's Chinese budget and the new pin measure different things, and
the review checked that they were not quietly merged.** The budget stays a
budget — it is not a ban, and it is not widened — and the new pin holds a
different quantity over a different scope. **Checked here by hand:** a
four-character name appended to a file whose longest run was 7 left the
longest run at **7** and moved the total from **34** to **38**. The gap
the batch measured is closed, and the demonstration is a measurement.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The comment-less witnesses build the **premise** — a chain whose
manuscripts carry no comment — and then read the product's own answers:
the roles that ran, what each could not answer, the shape the chain
reports, the event the log holds, and the run and stage states beside it.
**No witness writes the answer it looks for.** The refusal for a key the
chain does not hold is kept as its own case with its own witnesses, so
the new path is not proved by the old path's absence.

## The correction to batch 17's review

**Batch 17's review said the fix would land with four witnesses. It
landed with four from the window and a fifth added here**, because the
fix's record claimed the CLI and the API inherit the layer's refusal, and
**that inheritance was a claim about how a surface renders an error**. It
was measured by hand first — the console script driven whole, record a
claim, take the source back, then attest — and gave exit code **3**, the
reason `citation_source_unobservable`, and the source's id in the message.
**A hand measurement is not a witness**, so the path is now driven from the
command line by a test, and the mutation turns it red with the other four.

## What the published history holds

Measured, and **not acted on**: two commits carry a name in a document, the
repository is public, and fetching either file at its commit over plain
HTTPS without a credential answers **200** with the runs in the body. The
redactions cleaned the **tree tips**; the blobs stayed in history, and
history is what the remote serves.

**Three options, with their measured costs, are in the record** — do
nothing; rewrite the delivery line only; rewrite both. **None is
performed, none is recommended here, and none is the session's to choose.**
The rewrite costs are measured in commits re-hashed and tracked citations
re-measured, and the largest of them moves the required-check revisions,
the shard cost anchor and six `test_status_consistency` anchors.

## What this review did not cover

- **The remedy for the published history.** Measured; the owner's.
- **Whether the earlier records that carry Chinese for other reasons hold
  anything material.** The new pin measures the tree's whole load; it does
  not judge what each run is.
- **A run over a document with no comment *and* a rule the card would
  cite.** The comment-less run has no card to cite a rule from, and the
  rule the request names is not fetched. That is the honest shape of the
  case, and no witness covers that path yet.
  **Correction, made here: the middle clause is false, and the measurement
  is what says so.** `the_role_run_question` calls `_the_rule(context,
  request)` — which is `cite_rule`, and which **raises**
  `RULE_NOT_IN_THE_MEMORY` when the memory holds no rule under that id —
  and the question is built **before** `_run_role_run` reaches its
  comment-less branch. So naming a rule the memory lacks **refuses the
  whole request**, before the chain's "no comment" state is consulted: a
  document with no comments that names a rule the memory lacks is
  **refused, not abstained**. The record is corrected in place, and the
  path is now open work.
- **The blast radius of the comment count's new scope.** The count is the
  **project's**, not one version's, because the chain reads comments by
  key wherever they were written — so the count and that read have to
  agree about the same fact. The window's own witness holds it; what a
  *narrowed* count would have said is not measured.
- **Whether `advance` re-guards a stale passing C1 entry** (named above).

## Where each finding went

| Finding | Where it went |
| --- | --- |
| A record could be certified citable over a source that is gone | closed — `store.attest` runs C1 before the move, the origin witness flipped, and a fifth witness added here for the surface |
| The name is in the published history | measured, three options costed, none performed; the tree's blind spot closed |
| The budget could not see a short name | closed — a companion pin on the whole Han load, with the blind spot demonstrated on the live tree |
| The comment-less document was a dead end | closed — the branch is on the chain's state, the old refusal untouched, each role abstains through its own primitive |
| The console script was derived a second way | corrected here — the shared derivation, and the two environment settings the project's other CLI witnesses set |
| The three new witnesses' costs | `0.0` until a runner measures them; filed in the manifest and in a shard |
