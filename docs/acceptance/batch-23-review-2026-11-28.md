# Batch 23 review — a writer outside the product, and what the pipeline cannot carry

**Ticket:** the two cards of 2026-11-28 — drive the three refusals with a
writer outside the product, and measure what the analysis pipeline would need
to carry verification.
**Date:** 2026-11-28.
**Tree:** the two windows' commits merged into the local `main` (`4407bfb`,
`20c00dd`).
**Status:** local evidence. The batch's shard costs are red until a runner
re-measures them; the delivery this batch belongs to has read a runner.
**The checklist** is `docs/review-checklist-2026-11-14.md` (R1–R6); R7 is
this batch's own.

## What each window did

- **A writer outside the product** (`4407bfb`). A writer that does not go
  through the product — the shape a SQL client or a future code path has —
  was built and driven against each of the three refusals the record names:
  the model's, the store boundary's and the schema's. **All three held.**
  They do not, however, add up to a closed door, and the record says so
  rather than claiming one. Nothing under `src/` changed.
- **The analysis pipeline's capacity** (`20c00dd`). The record had measured
  that the pipeline appends nothing to any evidence record's log and that
  the coupling it would need does not exist. This window measured the other
  half of that sentence: **the pipeline could not carry the ledger's rules
  as they stand**, because a computed number cannot be anchored, so C1, C2
  and C3 have nothing to read. Nothing under `src/` changed, and no option
  was chosen.

## R1. No witness depends on a build artifact the runner does not have

Both windows wrote no product code ✓. The outside writer's witness drives
the store's own refusals ✓ — the store, the model and the schema ✓ — and
needs no artifact beyond the tree ✓.

## R2. No witness hard-codes one platform's facts

The outside writer's attempts aim at each refusal in its own terms ✓ —
the model's own validation, the store boundary's method, the schema's
constraint ✓ — rather than at one platform's spelling of a failure ✓. The
pipeline window read the tree's own lines ✓.

## R3. A guard of a guard needs its own witness, and a skipped arm proves nothing

The outside writer's witness is the guard: it drives the outside writer
again and requires each refusal to hold ✓. The pipeline window produced a
measurement rather than a mechanism, and says so ✓ — a measurement that is
not a claim needs no witness ✓.

## R4. External material is paraphrased in English with provenance, never quoted in the original

Neither window handled material ✓. The outside writer writes rows into a
temporary store ✓; the pipeline window read the tree's own source ✓.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

The unreachable-status record now carries both windows' findings ✓: the
writer's item is closed with what the three refusals did ✓, and the
pipeline's capacity is priced in the options section ✓. **The option stays
the owner's**, and the record says so ✓.

**The threat model was caught by this batch.** The verify door — option A,
from the previous batch — made a true statement false: the threat model said
that no product module reaches for the ledger's verification write, and the
layer's verify operation now does. The claim was **inverted rather than
deleted** (`tests/test_threat_model.py::test_only_the_layers_operation_runs_the_ledger_checks`),
and the document, its C14 row and the confirmation operation's own docstring
say what is true now ✓. The pipeline window reported the red and did not
touch the file, which was not its own ✓.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

The pipeline window's finding is anchored in the tree's own lines ✓ and
names the file and the method it read ✓. The batch's shard costs are red
until a runner re-measures them ✓ — the same position the previous batch
left, and for the same reason ✓.

## R7. A witness that constructs what it watches cannot notice its absence

**The outside writer window found the failure mode in its own first run and
says so in the record.** The `.venv`'s editable install names the **main
checkout**, not the window's worktree, so a bare `pytest` run imported and
migrated the main checkout's tree: the first mutation check **mutated the
worktree's source and every mutation came back green**, because the tests
never loaded the files that were changed. That is the repository's own trap —
*"a copied virtualenv is not a virtualenv of its own"* — in a different
guise ✓. Every run the window reports sets `PYTHONPATH` to the worktree's
`src`, and its mutation script prints the module path the tests load and
refuses to mutate anything outside that worktree ✓.

**A witness that measures the wrong tree is green for the wrong reason**, and
the record says which tree its measurements were taken at ✓.

## What the local run says

The two windows' witnesses and the tree's own: the outside writer's file is
green ✓, the harness that watches the partition is green ✓, the threat
model's own witness is green after the inversion ✓, and the citation and
external-path witnesses are green after the citations the windows' records
made were re-pointed at the merged hashes ✓.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| The three refusals had never met a writer outside the product | closed — all three held, and the record says they do not add up to a closed door |
| The pipeline's capacity to carry verification was unmeasured | closed — it could not, as the rules stand, and option B's two sub-shapes are priced |
| The verify door had falsified the threat model's own claim | closed — the claim is inverted, and the document, its C14 row and the docstring say what is true |
| A window's first mutation check measured the wrong tree | closed in that window — `PYTHONPATH` is set, and the mutation script refuses to mutate outside the worktree |
| The threat model's witness was red | closed — inverted, and the document corrected |
| The batch's shard costs | owed to a runner — red until the re-measurement, which the next run provides |
