# Batch 15 review — the CLI's own request, the removal that names itself, the replay, and a name that got out

**Date:** 2026-11-27
**Range reviewed:** `6b8e09f..d3da581` on `main` — pull request #224's
merge, four windows' work, two registrations, one redaction.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.**

| Piece | Commit | What it is |
|---|---|---|
| the CLI's own model request | `d31deb1`, `6328fd2` | `labcairn suggest` — one question about one source, one request, and the consent gate ahead of the spend; thirteen witnesses |
| the report's content checks | `c6c2a3f` | [`LC-P4-PILOT-report-checks-2026-11-26.md`](LC-P4-PILOT-report-checks-2026-11-26.md) — what the five checks and the gate read over the pilot's report |
| the removal that names itself | `b4e5169`, `af0448f` | `source_removed`, carrying the source's id, path, digest and the released tasks; migration `0034`; six witnesses |
| the replay on the pilot workspace | `a399bfb` | [`LC-P4-PILOT-replay-2026-11-26.md`](LC-P4-PILOT-replay-2026-11-26.md) — the round's two gaps, on the real workspace |
| this review's witness | `7fae861` | `tests/test_pilot_records_carry_no_names.py` |

## R1. No witness depends on a build artifact the runner does not have

**Pass.** The CLI's thirteen witnesses use the project's own fakes — **no
real model request was made**, so nothing was spent and no key was
needed. The checks reading ran on copies; the removal's witnesses build
their own store; the replay read the pilot workspace and wrote only what
the product writes.

**The replay is the one that reads the real thing**, and it says so: the
workspace's store moved from revision 0032 to 0034, and its event log
went from 10,305 to 10,401 — **both stated in the record**, because a
window that changes state outside the repository must say what it
changed.

## R2. No witness hard-codes one platform's facts

**Pass.** The new witness files hold no `os.name`, no `sys.platform`, no
drive letter and no backslash path. The records name the machine they
were taken on, which is a fact about a reading.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** None of the new test files contains a `skip`, a `skipif` or an
`xfail`: **no arm of them can pass by not running.**

**And this batch added a guard of a guard — of a guard that was itself
watched in only one direction.** The rule "the pilot's records carry no
name" already existed for the preparation papers
(`tests/test_pilot_decisions.py`), and a second witness already holds the
tree's Chinese budget: `tests/test_no_reference_leakage.py` fails when a
file that carries Chinese was never measured. **The leak was a new file
carrying Chinese, so that witness would have caught it** — and the
measurement records, which existed before it, were none of its business.
What was unwatched was the other direction: **a name written into a
record that was already there**, changing no file's Chinese status.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**This is where the batch failed, and the failure is the reason this
record exists.**

The replay's record named the workspace's own issue key, version id and
file name for the second corpus — `iss-c2-…-15`, `ver-pilot2-…`,
`corpus2-….docx` — and **all three carried a person's name, in Chinese**.
The workspace is allowed to hold them: it is the material's own home.
The tree is not. **A label that carries a name is material too**, and the
rule this repository works by is that the tree keeps desensitised
metadata, digests, counts, ids and timings.

**What was done.** The three identifiers are redacted in place, and the
record says why — the corpus and the root are still there, so a reader
can find the row, and the name is not. The redaction is recorded in the
record itself rather than done silently. **The redaction cleaned the tree
tip only.** `a399bfb` is an ancestor of `origin/claude/delivery-phase5`
and of `refs/pull/225/head`, both public, and fetching
`docs/acceptance/LC-P4-PILOT-replay-2026-11-26.md` at that commit over
plain HTTPS, with no credential, answers **200** with five Han runs in
the body (26 characters); the name is in the published history, and
only a rewrite plus a host-side purge would reach it. That is measured,
with the options costed, in
[LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md](LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md).

**What now watches it.** Two witnesses, in two directions.
`tests/test_no_reference_leakage.py` holds the tree's Chinese budget: a
file that carries Chinese and was never measured fails the build, so **a
new record that copied the corpus in would be caught before it merged**.
`tests/test_pilot_records_carry_no_names.py` holds every pilot record —
the desensitisation measurement, the import, the first real request, the
round, the removal and its witnesses, the report checks, the replay, the
CLI's request, and the reviews of these batches — to three checks: no Han
character run, no fullwidth enumeration comma, and no identifier shape a
real name or affiliation leaves behind (email, phone, grant or project
number, ORCID). **That one is the direction the budget does not cover: a
name written into a record that was already there.** Putting the name
back was checked to turn it red, and the witness writes its patterns as
code points so that it spends none of the budget it protects.

**Why the rule is a Han character and not a name list.** The corpus is
Chinese. A run of Han characters in an English record is not a style
question; it is a transcription. A denylist of known names would find
today's leak and tomorrow's, and would not find the leak nobody wrote
down. **And the rule is a budget, not a ban**: the repository's own
Chinese documents are legitimate, so what is watched is that the tree
carries no more Chinese than it was measured to carry, plus that the
pilot's own records carry none at all.

**What this review did not do.** It did not check the tree for leaks of
the same kind outside the pilot's records — the earlier acceptance
records and the source files carry Chinese too, and whether any of it is
the material's own wording is a question this batch did not answer. It
also did not check the **git history** — and that first reading was
wrong, in a way this review's own record did not catch: the leak was in
a commit that **had been pushed**. `a399bfb` is an ancestor of
`origin/claude/delivery-phase5` and of `refs/pull/225/head`, both
public; an uncredentialed HTTPS fetch of the file at that commit answers
**200**. What the rewrite would cost, and what it would and would not
achieve on a public host, is measured in
[LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md](LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md),
and the choice is the owner's.

## R5. A documented rule and its implementation say the same thing, and both sides are witnessed

**Pass.** The CLI's own record says the gate runs before the approval is
spent, and the witnesses hold the ordering rather than the wording. The
removal's docstring says the event names the row that left, and the
six witnesses check the payload's fields — the id, the path, the digest
and the released tasks — rather than that an event happened.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass, and one window said the uncomfortable thing out loud.** The
removal's record notes that the shared virtualenv's editable install
points at the **main checkout**, so importing `labcairn` in a worktree
without help reads somebody else's code — the defect `CLAUDE.md` records —
and that every run therefore set `PYTHONPATH` to its own tree. **It also
says which of its readings are therefore not evidence for this tree**:
the CLI parameters run was the main checkout's, and it says so rather
than counting it.

**Still owed.** Two new test files carry `0.0` in the shard cost table:
they have never been on a runner, and the next run is what supplies
their numbers.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** The removal's witnesses build a store and then read the events
the product wrote; the CLI's witnesses build a fake endpoint and then
watch what the command does with it. **No witness writes the event it
looks for.** The report-checks window put it the other way round and
found the sharper fact: **there is no route that checks an export that
already exists**, because the gate runs on the model and checking a
rendered file would be a second copy of the content. Seven mutation
probes each broke one check, and each was refused by that check.

## The second reader

**A reader who has never seen the pilot can check every claim in these
records without the material.** The counts, digests, ids, byte counts and
timings all say which command produced them; the material stays outside
the tree; and the paths the records name are answered for by
[`docs/ci/external-paths.json`](../ci/external-paths.json).

**One claim cannot be checked by a reader, and the record says so**: the
replay changed the pilot workspace's store revision and event count, and
no reader can repeat that without changing the workspace again.

## What this review did not cover

- **The suggestion loop** — still not exercisable on a copy without
  comments, and untouched by this batch.
- **Whether the report's checks should say more.** They passed, but the
  record says the checks could have said more than they did, and that
  question was not answered.
- **The redaction's completeness** — the three identifiers are gone from
  the record, but the workspace still holds them, and this review did not
  go looking for the same name in other places in the tree.
- **The git history**, as R4 says.
- **The cost of the two new test files**, which is `0.0` until a runner
  says otherwise.

## Where each finding went

| Finding | Where it went |
|---|---|
| A person's name, in Chinese, reached a record in the tree | `7fae861` — redacted in place, said in the record, and watched by a new witness |
| A name written into a record that was already there was unwatched | `7fae861` — the zero-tolerance witness over the pilot's two record globs; **the Chinese budget does not cover that direction** — it pins the *longest* Han run per file, so a short name in a file that already carries a longer run moves no pinned number. The gap is closed by the per-file Han-total pin, measured and registered in [LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md](LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md) |
| Two witnesses froze the old shape (one event; 32 event types) | `3df9e3a` — moved with the product |
| A record named a temporary directory that is gone next run | `0293a4d` — the parent is the fact |
| Five anchors moved with the new command | `d3da581` — re-pointed with the checker's own word-matching |
| Two new test files were in no manifest and no shard | `d3da581` — filed, with their costs owed to the runner |
