# Batch 13 review — the round, the removal, and the fallback estimate

**Date:** 2026-11-26
**Range reviewed:** `64f1bb7..f060ede` on `main` — the three windows'
work, merged, plus the ledger rebuild and the two records the handoff
and the reading carry.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.** Three independent windows reported, and their work
was merged into `main` here rather than in three pull requests:

| Window | Branch | Commit | What it produced |
|---|---|---|---|
| source-2 | `claude/agitated-snyder-e39ca5` | `30034cd` | [`LC-P4-PILOT-source-removal-2026-11-26.md`](LC-P4-PILOT-source-removal-2026-11-26.md) — the pilot's stale source row taken back by `sources remove` |
| session-5 | `claude/charming-wiles-ae095c` | `17c331c` | [`LC-P4-PILOT-first-round-2026-11-26.md`](LC-P4-PILOT-first-round-2026-11-26.md) — one whole round on the pilot copy |
| provider-2 | `claude/wonderful-goldwasser-07dd51` | `4650ac3` | `spend_from_report` refuses a fallback estimate that would read as a measurement, and six witnesses for it |

Two commits are not the windows' work but answer for them: `1edc528`
rebuilds the external-path ledger, and `f060ede` says when the ledger was
last read.

## R1. No witness depends on a build artifact the runner does not have

**Pass.** The batch's only new witness file is
[`tests/test_provider_budget.py`](../../tests/test_provider_budget.py).
It reads two things: the modules it imports, and one file of the
repository's own source — `Path(__file__).resolve().parents[1] / "src" /
"labcairn" / "providers" / module_name` — for the source-level check that
neither `budget` nor `ledger` coerces a quantity to a number. **There is
no `shell/build/`, no `dist*/`, no installed directory and no frozen
tree** in that file; it is a checkout, and the runner has one.

The two records are measurements, not witnesses, and both were measured
on a workspace outside the repository. Nothing they print depends on
anything the runner lacks.

**Checked, and worth saying out loud.** The round's own record notes that
the CLI's only route to a model is `roles run`, that it refused on this
copy, and that the request therefore went the way the earlier window's run
went — **through the Python surface, not through a command**. That is the
honest reading, and it is why the record's §3.1 is written as a refusal
with its exit code rather than as a success.

## R2. No witness hard-codes one platform's facts

**Pass.** `tests/test_provider_budget.py` contains no `os.name`, no
`sys.platform`, no drive letter and no backslash path; its only path is
built from `__file__`. The two records quote a Windows run because that
is the machine the pilot ran on, and each says which machine it was.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** The batch adds no new defence and no new guard, so there is no
guard of a guard to witness. `tests/test_provider_budget.py` contains no
`skip`, no `skipif` and no `pytest.mark.xfail` — **no arm of it can pass
by not running.**

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** Neither record quotes the manuscript. The round record names the
source (`src-0ac499ea4d3a7d82`), the file, the digest and the byte count;
the removal record names the row that was removed, the row that stayed and
the counts before and after. The one JSON block in the round record is
**the product's own refusal**, printed by the product — not material.

## R5. A documented rule and its implementation say the same thing, and both sides are witnessed

**Pass, and this is the batch's real content.** `TokenSpend.origin`
decided `MEASURED` from `estimated == 0`, so a caller that passed a zero
estimate for a side the provider left unreported produced a spend
claiming the provider had reported every side. The docstring said the
total "is never smaller than either part" and promised a fallback that
covers only the unreported sides; the implementation now **raises** on the
shape that would read as measured, and the docstring says so, with a
`:raises ValueError:` clause that names both refusals.

The witnesses are on both sides: the behaviour is asserted in
`tests/test_provider_budget.py` (six new tests), and the rule is checked
against the source text so that "we were careful" is a property somebody
can check next year.

**One claim the docstring had to give up.** The old text said the fallback
is "not smaller than either part", which reads as a bound. The pilot's own
measurement contradicts that reading — a character estimate of 416 tokens
for an answer the provider reported as 6,089 — so the docstring now says
the fallback is **not a bound on what the provider charged**, and cites
[`LC-P4-PILOT-real-request-2026-11-25.md`](LC-P4-PILOT-real-request-2026-11-25.md)
§8.4. **The record was corrected by the measurement, not the other way
round.**

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, with one thing still owed to the runner.** Every number in the two
records is anchored where a reader can check it: the digests of the
material and of every exported file, the byte counts, the database counts
read back from a copy taken immediately before the command, the ids, and
the timings. The removal record says explicitly that the *before* column
is read back rather than remembered.

**The shard cost table is not this batch's doing and is not violated by
it.** The new tests went into a file that already carried a measured
cost, and the shard file's `measured_at` was not moved by the window; the
drift witness's own slack rule is what says a change to a cheap file does
not spend a CI run. **The new files that still carry `0.0` — the
redaction, the checklist, the picture comparison and the rest — are owed
a runner measurement**, and that is owed by the next run rather than by
this review.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The source-level check reads the repository's own `budget.py` and
`ledger.py`; it does not build a copy of them and then check the copy. The
budget witnesses build *inputs* — an `Unknown` cost, an `Unknown` token
total, an unverified `usage_reporting` capability — and watch what the
production code does with them. **The thing under test is never the thing
the test made.**

The same question was asked of the two records, and both pass it in the
other direction: neither claims an absence it did not measure. The round
record's §6 lists four places where the product's own bookkeeping stopped
— a refusal that left no event, a stage that stayed `blocked` after its
approval was consumed, a read that wrote an event, and the stale source
row — **each one observed on the workspace, not inferred.**

## The second reader

**A reader who has not seen the pilot can check every claim in these
records without the workspace.** Every number is a count, a digest, an id,
a byte count or a timing; the material itself is outside the repository,
and the paths the records name are answered for by
[`docs/ci/external-paths.json`](../ci/external-paths.json). The two
records name their commands, so the round can be repeated and the removal
can be repeated — **which is the difference between a measurement and a
story about a measurement.**

## What this review did not cover

- **The pilot's suggestion loop.** It did not run — the copy carries no
  comments — and nothing here says the loop works.
- **The reports' own content.** The round exported six files per revision
  and the digests were computed twice and agree; **no one read the
  reports** to say the analysis was right.
- **The two gaps the removal window found in the product.** The removal
  writes no event of its own, and the anchor path is untested. Both are
  recorded in
  [`LC-P4-PILOT-source-removal-2026-11-26.md`](LC-P4-PILOT-source-removal-2026-11-26.md)
  and neither is fixed by this batch. They are the next batch's work.
- **The product's own bookkeeping gaps the round found** — the refusal
  that left no event, and the stage that stayed `blocked` after its
  approval was consumed. Recorded, not fixed.
- **The shard costs of the new files**, which are still `0.0` until a
  runner measures them.

## Where each finding went

| Finding | Where it went |
|---|---|
| The two records name two paths the ledger did not answer for | `1edc528` — the ledger was rebuilt; both are on the disk and are expected to be present |
| The ledger's `read_at` and the reading's date had drifted apart | `f060ede` — the reading now says which is which |
| The shard file's new files carry `0.0` costs | owed to the next runner measurement (`.github/remeasure_shards.py`) |
| The removal writes no event; the anchor path is untested | the next batch |
| A refusal leaves no event; a stage stays `blocked` after its approval was consumed | the next batch |
