# Batch 21 review — the three cards, audited after they landed

**Ticket:** the three cards the owner started on 2026-11-28 — the status the
product cannot reach, a witness for the hashes the records cite, and the
gate's verdict on the command line.
**Date:** 2026-11-28.
**Tree:** `b56f999` (`main`, and `origin/claude/delivery-phase5`).
**Status:** local evidence and one CI run. The checklist is
`docs/review-checklist-2026-11-14.md` (R1–R6); R7 is this batch's own.
**The windows.** Two of the three were finished by sessions the owner
started, and both were merged into the local `main` before this review. The
third session was killed by the provider's daily limit after 113 turns; it
left one file uncommitted, and this session finished it and merged it with
the other two.

## What each window did

- **The status the product cannot reach** (`aa920a9`, from `db99028`).
  `store.advance` is the only writer of `verified_by_rule`, and **nothing in
  `src/` calls it**: the six surfaces produce `planned`, `extracted` and
  `user_attested`, so the reachable state machine is **three states wide** —
  `conflicted`, `unsupported` and every fallback belong to `advance` too.
  The record names the three options with their costs and **does not choose
  for the owner**. The witness (`tests/test_surface_status_reach.py`) reads
  `src/` with `ast`, so the gap is watched rather than described.
- **The gate's verdict on the command line** (`4145ad3`, `9eb017a`,
  `d094802`). `labcairn task report` now draws the gate's verdict beside the
  receipt: the verdict, the ids it judged, the ids it did not judge, and the
  findings count. Seven witnesses and an acceptance record.
- **A witness for the hashes the records cite** (`94bf9b6`). The
  delivery-line rewrite re-pointed seventy-two citations in eighteen files
  with a script of its own, and **no witness in the tree could tell a right
  commit from a wrong one** — both are ancestors of a branch, and only
  existence is checkable. `tests/test_record_citations.py` is that witness.

## R1. No witness depends on a build artifact the runner does not have

The CLI's witness runs the console script through the tree's shared rig
(`tests/test_cli_support.py`), the way every other CLI test does, and names
no path to a binary of its own. The status-reach witness reads
`src/labcairn` as text and parses it; it builds nothing and needs no
interpreter state. The citation witness reads the tree's documents and asks
git for the objects it names.

**The runner found the one that was there.** The Chinese run classes'
witness builds a scratch repository, commits a seed file into it and then
replaces a run in it — and the commit took **the host's global git
identity**. The runner has none, so git refused the commit with exit 128
and the two tests that mutate a run **never ran**: the tree was green for a
reason that had nothing to do with the property under test. The scratch
repository now declares its own identity, and the witness depends on
nothing from the host.

## R2. No witness hard-codes one platform's facts

The CLI's witness goes through the shared rig, where `COLUMNS` is two
hundred and the encoding is pinned, and it asserts on phrases and ids
rather than on whole lines. The status-reach witness's shape is
platform-free — an AST scan and a list of names. The citation witness's
rules are about token widths and git's own vocabulary, and it reads the
catalogue for the foreign projects' names rather than hard-coding them.

The git identity above is the one platform-shaped thing the runner found,
and it was in a witness's environment rather than in the code under test.

## R3. A guard of a guard needs its own witness, and a skipped arm proves nothing

The citation witness carries an arm for each of its mechanisms: a token that
names nothing is a finding; a foreign revision is not; a 64-character digest
is not a commit; a tree named as a tree is green and the same tree named as
a commit is a finding; a declared absence is green and one without a reason
is not; a commit no branch reaches is a finding; a repository whose branch
was deleted is seen by the reachability scan.

**One arm was missing, and the first run showed it.** The rule that skips a
**quoted** line — a blockquote in these records is the owner's words, a
command's output or a finding a review reported, and a hash in one is
quoted rather than claimed — had no arm, and the g5 review record's
quotation of a deliberately corrupted upstream sha was reported as a
finding. The rule is now stated, and it has an arm of its own: the same
token in prose **is** a finding, so the exclusion cannot become a
tolerance.

The CLI's witness compares the human rendering and the `--json` rendering
**as facts and not as bytes** — the two are not the same text — and reads
every fact the picture carries back out of the model the same command
printed. Its refusal arm asserts that the refusal path is unchanged: a
report the gate refused was never written, so there is nothing to draw.

The status-reach witness's own arms are the tree's text mentioning
`advance` and the tests' legitimate use of it, which stay green; the
window's record reports six mutation checks, three wiring shapes and the
status naming.

## R4. External material is paraphrased in English with provenance, never quoted in the original

`render_report_gate` reads the gate's considered ids, the unjudged ids and
the findings count, and **never a record's text** — a record's words are
the material, and the tree's rule is that material does not enter the
repository and does not travel in a rendering either. What travels is the
id, so a reader can look the record up in the ledger. The status-reach
record quotes no corpus text, and the citation witness reads ids and
paths, never prose.

## R5. A documented rule and its implementation say the same thing, and both sides need a witness

The status-reach record names the three options and their costs, and its
witness turns red **on the commit that closes the gap**. The record says
what a red means: it is the witness working, it is a prompt to read or
update the record, and it is never a reason to revert a deliberate
decision. The implementation side — `advance` has no caller — is the
property the witness holds, and the record is the property the reader
holds.

The CLI's record names the refusal path as untouched, and the witness
asserts that the refusal still names the objection.

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

The status-reach record anchors its measurement to a commit — and **that
hash had moved once**: the delivery-line rewrite re-hashed the commit the
batch started from, and the record was written after the rewrite, so the
rewrite's own re-pointing never saw it. **The citation witness found it**,
which is the first time that class of error had a witness. The record now
names the hash the tree has and says that the hash moved.

The three new test files' shard costs are `0.0` until a runner measures
them; that is filed, not guessed.

## R7. A witness that constructs what it watches cannot notice its absence

The status-reach witness's property is universal — *no* code path writes the
status — so its behavioural form would have to drive every surface that
exists or ever will exist, and a new surface would escape it silently. The
honest mechanical form is **the view the interpreter itself loads**: imports
and calls as `ast` sees them, not a regex over text, so a docstring that
mentions `advance`, a comment and the tests' own use of it stay green.

The citation witness constructs nothing either: it reads the tree's
documents, asks git which objects exist and which are reachable, and
compares. Its arms are synthetic documents and synthetic worlds, so each
mechanism is exercised without a real tree.

## What the runner found, and what it cost

One CI run on the batch's merged work, and it was red in five shards.
**Every failure was one of three things**, and none of them was the
delivery's own fix:

| The failure | What it was | The fix |
|---|---|---|
| `test_chinese_run_classes.py` (2) | the scratch repository's commit took the host's git identity, and the runner has none | the scratch repository declares its own |
| `test_status_consistency.py` (2) | the command line's change added lines to `src/labcairn/cli/commands.py`, and **four records' line anchors** — cited by line *and* by the words on that line — were left pointing at the old lines | the witness says where the words are now; the four pointers follow them |
| `test_external_path_references.py` (1) | the ledger's builder found a scratch probe on disk and filed it as material that is **present**, which is a claim about a volatile temp directory that a fresh runner would refuse | it is a scratch path and it is gone; the ledger says so and the file is removed |

Measured locally after the fixes: **611 passed** over the three files, and
**110 passed** over the three new witnesses and the evaluation harness.

## The session that did not finish

The third card's session was rejected with HTTP 429
(`daily_usage_exceeded`) after 113 turns — the provider's daily limit, not
anything the work did. It left **one file uncommitted**: an 802-line
witness with its arms, its scope and its exception list, unfinished. The
work here finished it, added the missing arm, and merged it; and the
witness's first run found the one citation the rewrite had missed.

**What the hung run cost, and who caused it.** The delivery's reviewer-mode
walk runs the whole suite in its clone. It was started at 05:03 and **four
pytest runs were then measured beside it**, every one against the same
`TEMP` — what `CLAUDE.md` forbids. **The walk hung the same way the
earlier one did**: the clone's interpreter at zero CPU, blocked on a child
that never signalled, killed at fifty minutes with no result. The lesson
recorded by the earlier window is not advice; it is a mechanism that holds
only while the session obeys it, and **the session that broke it was the one
integrating the batch**.

## Where each finding went

| Finding | Where it went |
| --- | --- |
| A scratch repository that needed the host's git identity | closed — the repository declares its own, and the witness depends on nothing from the host |
| Four records' line anchors moved by the command line's own change | closed — the anchors follow the words, and the witness says where they are |
| The external path ledger filed a scratch probe as present | closed — it is a scratch path and it is gone; the ledger says so |
| The quoted-hash rule had no arm, and the first run reported a quotation | closed — the rule is stated and its arm proves the same token in prose is a finding |
| A citation the rewrite missed, in a record written after the rewrite | closed — the citation is re-pointed, the record says the hash moved, and the witness that found it is in the tree |
| The status the product cannot reach | measured and filed; the three options and their costs are the owner's to take |
| The CLI's human rendering shows neither list | closed — the gate's verdict, the judged ids, the unjudged ids and the findings count are drawn |
| A whole-suite run hung on a shared `TEMP` | closed by re-running alone, and recorded twice — the rule and the repeat |
