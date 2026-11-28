# Batch 24 review — deadlines, encodings, and the round on real material

**Ticket:** the three cards of 2026-11-28 — sweep the tree for waits without
a deadline, make every child's output say which encoding it is, and replay
the pilot round on the tree as it stands.
**Date:** 2026-11-28.
**Tree:** the three windows' commits merged into the local `main`.
**Status:** local evidence. The batch's shard costs are red until a runner
re-measures them.
**The checklist** is `docs/review-checklist-2026-11-14.md` (R1–R6); R7 is
this batch's own.

## What each window did

- **The waits** (`4610c560`). **99 waits with no deadline, across 47 files.**
  97 were given one through a shared helper (`tests/deadline_support.py`),
  and the two that were left alone are read-only and watched instead. Sixteen
  witnesses in `tests/test_deadlines.py` ✓, each of which fails by hanging
  when its deadline is removed ✓.
- **The encodings** (`5c449d1a`). **30 text pipes** decoded a child's output
  with the host's code page, plus 13 missing `errors=` and 4 sites where the
  fix had been turned round. The witness `tests/test_child_encodings.py`
  names the file and the line when a pipe's encoding is removed ✓.
- **The round** (`8032ce87`). The pilot round was replayed on a **copy** of
  the pilot workspace at `19a7fc7`, with the pilot's own workspace untouched ✓.
  The verify door, the command line's drawing of the gate's verdict, the
  report's refusal over a moved source and both demonstrations **all behaved
  as designed on real material** ✓.

## What the round found

**The refusal names a remedy no surface can carry out.** A report over a
source whose bytes moved is refused, and the refusal says what to do: ingest
the material again, then re-verify or re-attest the claims it carries.
**Ingesting again works** — the ledger's row moves ✓. **Re-verifying or
re-attesting does not**: `user_attested → verified_by_rule`,
`verified_by_rule → verified_by_rule` and `user_attested → user_attested` are
all illegal transitions ✓, and **nothing under `src/` writes `extracted` as a
transition** ✓ — the store's two writers write `verified_by_rule` and
`user_attested` and nothing else ✓. So **a task whose material moved cannot
produce a report again** ✓: a fresh claim at a new address verifies cleanly ✓,
but the report still refuses over the four records that drifted ✓.

That is a finding about the product, and the round's record asks the question
rather than answering it: should a window close the gap, or should it stay
for the owner to decide ✓?

## R1. No witness depends on a build artifact the runner does not have

Neither sweep needs an artifact ✓. The round ran against the worktree's own
`.venv` and console script, and **verified that the editable install names
that worktree's `src/`** ✓ — not the main checkout's ✓.

## R2. No witness hard-codes one platform's facts

The encoding sweep's finding is the opposite of a hard-coded fact: the
**host's** code page is exactly what must not be assumed ✓. Its witness fails
on the *absence* of the encoding ✓, whichever code page the machine has ✓.
7-Zip is the exception the sweep documented: a native tool writes in
whatever code page it was built against ✓, so it is **asked** to write UTF-8
(`-sccUTF-8` ✓) and the parent decodes UTF-8 ✓ — pinning one half alone
turns the failure around rather than fixing it ✓.

## R3. A guard of a guard needs its own witness, and a skipped arm proves nothing

Sixteen deadline witnesses ✓, each failing by hanging ✓, and an encoding
witness that names the file and the line ✓.

**The two windows' witnesses caught each other.** The encoding sweep's
witness found that the *deadline* sweep's own new file read text without
saying which encoding ✓ — the two cards ran at the same time, and the second
one's witness held the first one's new code to the same rule ✓. That is what
a witness is for ✓.

## R4. External material is paraphrased in English with provenance, never quoted in the original

The round ran on real material and **the material is not in the tree and not
in the record** ✓ — ids, paths and summaries only ✓, and the pilot's own
workspace is untouched ✓.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

Both sweeps record what they found ✓, and the round's record says what
happened on real material ✓ and what broke ✓.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

The round's record names the commit it ran at ✓. The batch's shard costs are
red until a runner re-measures them ✓.

## R7. A witness that constructs what it watches cannot notice its absence

The encoding witness reads the tree's **source** and fails on a pipe without
an encoding ✓ — it would notice the absence ✓. The deadline witness drives
real children ✓.

**The integrating session's own script hit the defect class mid-task**, and
that is the measure of how ordinary it is: a `subprocess.run(..., text=True)`
with no encoding decoded git's UTF-8 output with the host's GBK and raised
`UnicodeDecodeError` inside the reader thread ✓. The fix was the one the
batch teaches ✓.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| 99 waits had no deadline | closed — 97 bounded through a shared helper, 2 read-only and watched; 16 witnesses |
| 30 text pipes decoded with the host's code page | closed — every pipe says which encoding it decodes, and the witness names the file and the line |
| The two windows' witnesses caught each other | closed — the deadline sweep's new file was held to the encoding rule and fixed |
| The round on real material | closed — the record of the run, with what behaved as designed and what did not |
| The refusal's remedy no surface can carry out | **open** — the round's record asks the question; it is the owner's, and the next batch's cards name it |
| The batch's shard costs | owed to a runner — red until the re-measurement |
