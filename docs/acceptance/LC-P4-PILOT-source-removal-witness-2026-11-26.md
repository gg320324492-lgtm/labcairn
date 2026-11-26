# LC-P4-PILOT — the removal's aftermath, held still

**Ticket:** LC-P4-PILOT (the source removal's own witnesses)
**Date:** 2026-11-26
**Tree:** `32d42c4`, branch `claude/gracious-neumann-64dfef`, based on
`main` @ `dde1f0e`. Windows 11 Pro (10.0.26300 x64, AMD64), Python
3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Origin record:**
[`LC-P4-PILOT-source-removal-2026-11-26.md`](LC-P4-PILOT-source-removal-2026-11-26.md).

**What was measured.** The removal's record ended with two paths it said
were untested and a table of counts that a reader could take as a rule.
This record measures those paths, and **corrects the record where the
measurement did not agree with it**.

**Material.** **None was read.** The witnesses build a workspace in their
own temporary directory, from the product's own APIs, and make the shape
the record describes: a material that is **moved** and then ingested
again, so the ledger holds one row naming a path that is no longer there
and one row naming where the material is now. Nothing under
`E:/labcairn-local/` is opened, and no document text, digest of a
document or key appears in this record.

## The twelve witnesses

| # | what it holds still | the shape it needs |
| --- | --- | --- |
| 1 | the stale row goes and the survivor stays — **by id, not by digest** | a moved material, ingested twice |
| 2 | the text stays, indexed by hash, read back through `current_texts` | a source with text |
| 3 | the address stays, and the address still resolves to the text | a source with `source_anchors` |
| 4 | **an address that survives names a source the ledger no longer holds** | the same, and the id checked afterwards |
| 5 | the evidence record that cites that address survives | an evidence record over the address |
| 6 | **the removed row's own disclosures go with it; another source's stay** | a source with disclosures of its own |
| 7 | a row with no disclosure of its own leaves the count where it was | the shape the removal record measured (113 → 113) |
| 8 | the version that pointed at the removed row points at the survivor | a version over the stale id |
| 9 | **no** version is lost, added, or has its digest changed | the whole `paper_versions` table, before and after |
| 10 | a second removal of the same id refuses and changes nothing | the first refusal, applied to the id just removed |
| 11 | a material whose bytes cannot be found is refused | the second refusal |
| 12 | the removal writes one event — the task's revision | the binding's release and the log |

## What the measurement changed

**Two of the removal record's statements did not survive being measured.**

1. **The `source_problems` count is a shape, not a rule.** The record's
   table says `source_problems` went **113 → 113**, and read as a rule it
   says the count does not move. **It moves.** It did not move here
   because the row that left carried **no disclosure of its own** — the
   command itself reported `removed_problem_count: 0`. On a ledger built
   to hold the shape, a source carrying two disclosures of its own and
   another source carrying one went **4 → 2**, with
   `removed_problem_count` of 2, and the other source's disclosure
   stayed. **The rule is "a disclosure belongs to the source it was
   found on"**, and the count moves by exactly the disclosures that left.
   The removal record now says so, in §4 and in §9.7.

2. **The path the record called untested has an answer, and the answer is
   a dangling id.** The record said that if a row holding addresses were
   taken back, the address rows would stay and their `source_id` would
   name a source the ledger does not hold — "nothing in this run shows
   what happens, the path is untested here". **Measured: the address rows
   stayed, the address still resolves to the text, and the `source_id`
   they carry points at a source that is not in the ledger any more.** A
   dangling id, not a lost row. The record now says that instead of
   saying the path is untested.

**Neither finding is a defect this work fixed**, and neither is claimed to
be one. They are the product's behaviour, measured.

## The mutations

**Ten mutations were applied and each turned the witness that watches it
red**, with the file's own tests green again when the script was
restored: the text taken away, the address taken away, the address
re-pointed at the survivor, the removed row's disclosure left behind, the
whole ledger's disclosures removed, the version not re-pointed, a
version's digest rewritten, an id that is not held not refused, a
material whose bytes cannot be found removed anyway, and the task left
holding the material.

**Two mutations were not caught on the first attempt, and were fixed
rather than waved through.** Re-pointing the address was a no-op because
the ledger held no version, so the mutation changed nothing to be
noticed; and removing the ledger's disclosures was invisible because the
ledger held none. The second changed a witness: the ledger now carries a
material **with a disclosure of its own**, so "the count did not move" has
something to be true about.

## Evidence

| # | what | how | result |
| --- | --- | --- | --- |
| E1 | the shape under test | a material moved and ingested again, in the test's own temporary workspace | one row naming a path that is gone, one naming where it is now |
| E2 | the twelve witnesses | `tests/test_source_removal.py` | twelve witnesses, each with a docstring saying what would make it red |
| E3 | the ten mutations | each applied, the witness watched red, the script restored | all ten red, and the file green again |
| E4 | the two corrections | the removal record's §4 and §9 read against E1 and E3 | both corrected, with the measurement cited |

## What this record does not say

- **It does not say the pilot's own removal behaved this way.** The
  witnesses build their own ledger; the pilot's ledger was read once, by
  the removal record, and its two paths had the shapes that record
  described — no addresses, no disclosures of its own. **The general rule
  and the pilot's instance are two different claims**, and only the first
  is measured here.
- **It does not say a dangling id is right.** It says what happens. The
  schema has no foreign key on `source_anchors.source_id`, and nothing
  keeps the id honest; whether that should change is a decision, not a
  measurement.
- **It does not cover the removal's missing event.** The removal writes
  the task's revision and nothing that names the source it released
  (the record's §7 and §9.1). That is unchanged by this work.

## Where the code and the material are

The witnesses are in
[`tests/test_source_removal.py`](../../tests/test_source_removal.py). The
product's own removal lives in
`src/labcairn/cli/commands.py` and
`src/labcairn/application/material_ingestion.py`; **nothing in `src/` was
changed by this work.** The pilot workspace, the real material and the
database copies stay outside this repository, under `E:/labcairn-local/`,
which [`docs/ci/external-paths.json`](../ci/external-paths.json) answers
for.
