# Batch 22 review — three windows, and what the tree measured while they worked

**Ticket:** the three cards of 2026-11-28 — the drill tests' wait helper's
deadline, a reviewer mode that can finish, and a verify surface.
**Date:** 2026-11-28.
**Tree:** the three windows' commits merged into the local `main`
(`339f204`, `5d54391`, `69302d2`, `19595eb`, `6e945fe`).
**Status:** local evidence. One CI run has read the delivery this batch
belongs to; the three windows' own commits have not been on a runner yet,
and the shard costs they changed are red until one is.
**The checklist** is `docs/review-checklist-2026-11-14.md` (R1–R6); R7 is
this batch's own.

## What each window did

- **A verify surface** (`339f204`). The application layer gains
  `verify_claim`, which calls `store.advance` with the check the caller
  names; `task claim-verify --check c1|c2|c3` and `POST /records/{id}/verify`
  are its surfaces. A pass moves the record to `verified_by_rule` and the
  verdict is in its log; a check that does not pass is committed to the log
  and refused with what the rule found, **and the status does not move**; C4
  is refused up front; another task's record is refused as not found. **The
  store is still the only writer.**
- **A deadline for the drill tests' wait** (`5d54391`, `69302d2`). The
  helper that reads a killed child's output now has a **120-second**
  deadline and the injector fires on the write it names, so a child that
  dies before its marker line is a failure with a reason instead of a hang.
- **A reviewer mode that can finish** (`19595eb`, `6e945fe`). The
  whole-suite command's timeout goes from 5400 s to **14400 s**, resting on
  the runner's own measurement — the shard table's per-file costs sum to
  **10119.7 s** on Windows — with 42% of margin. The clone tree's
  interpreter is also pinned to UTF-8 mode, which removed a second ceiling
  the first measurement found.

## R1. No witness depends on a build artifact the runner does not have

The verify door's witnesses drive the console script and the API against
the tree's own sources ✓. The drill fix uses no artifact: it is a deadline
in a helper ✓. The outsider fix pins an **environment mode**, not an
artifact ✓.

## R2. No witness hard-codes one platform's facts

The TypeScript client is regenerated from the API's contract ✓ and the
web package's own README is updated with it ✓. The deadline is a bound, not
a platform's number: the drill file's measured cost is **29.03 s** on this
machine and **24.41 s** for its sibling, and the runner will give its own
✓. The 14400-second timeout rests on a measurement the shard file carries
with its anchor (`b56f9994`) ✓ — the same anchor the tree's witness checks
✓.

## R3. A guard of a guard needs its own witness, and a skipped arm proves nothing

The verify door has nine witnesses over the operation, the console command
and the API route, and the refusal arms are separate tests rather than
branches of one ✓. The static witness that watched the gap is **inverted**
into four arms that watch the door's presence instead of its absence ✓ — so
a door that was removed would turn it red ✓. The drill fix's witness is the
one that *kills the hang*: it drives a child that never prints its marker
and requires the helper to give up ✓.

**Twelve mutations over the verify door's witnesses, twelve reds** ✓.

## R4. External material is paraphrased in English with provenance, never quoted in the original

The verify door takes a **check kind** and a **record id** ✓ — no material
crosses it ✓ — and the rule's finding is a reason, not the material ✓.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

The unreachable-status record says what was wired, what it cost, and what
the witness now watches ✓, and its "What was not measured" section is
closed by the window that closed the gap ✓. The CLI record carries the
flake's mechanism and its reproductions ✓, and the drill fix says what
changed ✓. The outsider's own records are still to come — its measurement
runs for one to two hours, and the records follow it ✓.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**This is the one place the batch is not finished, and it is finished the
way the project's rule says it should be.** The drill fix changed two test
files whose measured costs were **603.91 s** and **1204.83 s**, and the
shard-cost witness is therefore **red until a runner re-measures** ✓ — the
witness says so in the tree's own voice, and that is the point ✓. The new
test file's costs are `0.0` until the same run measures them ✓.

**A prediction the re-measurement will settle.** The heaviest
ubuntu-latest file is the drill file the fix touches, at **1209.0 s** in a
shard whose other five carry 596–605 s — the partition's imbalance factor
is **2.028** for that reason alone ✓. With the file's cost measured at
24.41 s, the partition should balance. **That is a prediction, not a
measurement**, and the re-measurement is what turns it into one.

## R7. A witness that constructs what it watches cannot notice its absence

The verify door's witnesses drive the real surfaces, so a door that did not
exist would fail them ✓. The inverted static witness reads the **source**
for the operation and the surfaces that import it, so it would notice the
door's absence ✓ — which is the property the original witness had and the
gap needed ✓. The drill witness drives a real child process ✓.

## What the local run says

Merged into the local `main`, the three windows' witnesses and the harness
that watches them: **123 passed** (`tests/test_evidence_verify_door.py`,
`tests/test_surface_status_reach.py`, the two drill files,
`tests/test_evaluation_harness.py`, `tests/test_outsider_path.py`).

## Where each finding went

| Finding | Where it went |
| --- | --- |
| `verified_by_rule` was unreachable | closed — the verify door, with the static witness inverted to watch its presence |
| The drill tests could hang forever | closed — a 120-second deadline, and a witness that kills the hang |
| The reviewer mode could not finish at all | closed in the script — the timeout now rests on the measured cost; its records follow the run in flight |
| The shard costs the drill fix moved | owed to a runner — red until the re-measurement, which the next run provides |
| The analysis pipeline's capacity to carry verification | still the owner's second decision; the record says the coupling does not exist today |
