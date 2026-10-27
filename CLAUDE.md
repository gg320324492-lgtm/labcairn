# Working in this repository

## Language

**Reason and think in Chinese.** The reasoning that appears in the conversation
is written in Chinese.

**The repository stays in English.** Code, identifiers, docstrings, comments,
commit messages, test names, record files and every document committed here
are in English. The two are different surfaces and they do not mix: Chinese
for the thinking, English for everything that lands in the tree.

## Branches and checkouts

**One long-lived branch: `main`.** The repository keeps no standing branch
per gate, per piece or per agent. A branch exists only while the work it
carries is unpublished, and it is deleted — locally and on the remote — as
soon as that work has landed. **The owner decided this on 2026-10-27**, after
the gate's parallel work had left twenty-four local and seven remote branches
whose contents had every one of them already landed: **a branch that outlives
its work is a second place to look for the same code, and a promise nothing
keeps.**

**A worktree is isolation, not a branch.** When more than one agent writes
code, each one still gets its own worktree (`isolation: "worktree"` on the
agent call), because **one checkout holds one branch at a time** and two
agents switching branches in one checkout land each other's commits on the
wrong branch. What changes is the branch's lifetime: the worktree's branch is
a scratch ref, its files are reviewed and merged, and then the ref goes.

**A push is not a local action.** Ask before pushing to a shared branch, and
never force-push to `main`.

## How parallel work is landed: no branch per piece, one pull request at the end

**The owner decided this on 2026-10-25.** The arrangement:

1. **Parallel windows each modify their own files, and those files do not
   overlap.** The plan's file-ownership map is the contract; a window that
   needs another's file says so rather than reaching for it.
2. **They do not open pull requests, and they do not push to start a run.**
3. **The work is reviewed and merged into `main` locally**, and the review
   is the gate: the claims are measured, the witnesses are mutation-checked,
   and the pieces that turned out to be one piece are one piece.
4. **Then one pull request and one run**, for everything — and every branch
   the work was carried on, the delivery branch included, is deleted once the
   merge lands.

**Why.** A pull request per piece means a run per piece, and a run is the
most expensive thing this project does — it is the gate, and it should be
spent on the whole of a body of work rather than on each piece of it.

**What it does not change.** `main` is a protected branch, so a pull
request is how anything reaches it, and the sixteen required checks have to
pass on it. **The reduction is in the number of pull requests and runs, not
in whether they happen.**

## Running the suite

**`--basetemp` goes outside the repository.** The default base temp directory
fails on this machine with `WinError 5`, and a base temp directory *inside*
the repository makes two tests fail for a reason that has nothing to do with
the property under test.

**The CLI renders its refusals through Rich, which wraps at `COLUMNS=200`.** A
wrap that falls *inside* a phrase truncates it, so an assertion about that
phrase fails for a reason that has nothing to do with the property under
test.

**Length is not the test — where the wrap falls is.** Measured on
2026-10-23: a thirteen-character `--basetemp` landed in the wrong place and
failed, while a forty-five-character one was safe. "Use a short path" is the
wrong rule; the right one is that **a run showing this failure is re-measured
with another path before it is believed**, and the path is recorded alongside
the number.

**Two pytest runs must not share one `--basetemp`** — pytest clears it on the
way in, and two runs sharing one destroy each other's test tree.

**The temp directory must be outside the repository, not merely off the C
drive.** Two tests enforce this and they are right: a workspace inside the
checkout makes the run depend on the tree it runs in and leaves the checkout
dirty. The demonstration's own workspace is asserted to be outside the
repository, and the repository-root guard expects a directory that is not in
a repository at all. So `TEMP` and `TMP` point at `E:\labcairn-local\tmp` —
on the E drive, and **outside** `E:\LabCairn`. The project's own files live
under `E:\LabCairn\.local\` (which carries its own `.gitignore`), but the
runtime temp does not, and moving it inside the repository broke two tests
on 2026-10-24.

**A copied virtualenv is not a virtualenv of its own.** This project's tests
drive the CLI through the installed console script, and that script is a
compiled launcher with an interpreter's path burned into it. A virtualenv
copied with **hard links** shares that launcher — and shares the `.pth` that
names its editable install's source tree — so **every copy runs the same
code**, and a measurement of one tree is a measurement of another. Two
measurements were lost to this on 2026-10-23, and neither announced itself:
the tree was green, and the number was wrong.

So a copy gets **its own** launcher and **its own** `.pth`, and the launcher
is repointed by an **equal-length** replacement — a longer path does not fit
in place and the launcher simply stops working.

**The check that settles it:** apply a mutation that only the console script
can reach, and see whether the witness fails. If it stays green, the copy is
running somebody else's code.

**Parallel runs each need their own `TEMP`.** `MPLCONFIGDIR` is pinned under
the temp directory, so two runs sharing one temp directory fight over it.
Whole-suite runs go one at a time.

## Status is read from the command, not from a pipe

**`cmd | tail` returns tail's exit code.** A pipeline hides the status of the
command that mattered, and it has been read as "green" when the command under
it failed. Run the command, then read its status separately.

## CI is not started unless it is necessary, and no pull request is opened

**The owner decided this on 2026-10-24**, and it is recorded in
`docs/plans/LC-P1-11-12-task-breakdown.md` §1.5.

- **Do not push to start a run.** The suite is six shards per platform, so a
  push starts twelve python jobs; that is the owner's call, not the
  session's.
- **Do not open a pull request.** Not for a finished piece of work, not for
  a document, not for a commit that is "ready to be reviewed". The work
  lands in the tree, the record says what it is, and the pull request waits
  for the owner.
- **Measure locally and say so.** The local run is the evidence until a
  runner says otherwise, and the report says which it was.

**What this does not change.** C-1 still holds — a required `pull_request`
workflow runs unfiltered, and `tests/test_no_reference_leakage.py` watches
that. This is about **when a session starts a run**, not about what the gate
checks.

## The CI runs in shards, and the shard list is a hand-edited file

**Changing a test file means re-measuring the shard costs.** The shard file
records the commit its costs were measured at, and a witness checks that
nothing the costs are about has changed since — so a change under `src/` or
`tests/` makes the witness fail with *"the shard costs were measured at ... and
these files have changed since"*. That is not an obstacle; it is the project's
own rule (*a value that can change is re-measured, not carried forward*) and
the fix is one command:

```
python .github/remeasure_shards.py <run-id>
```

It reads the per-file seconds out of a CI run's log — where pytest's
`--durations=0` puts them — writes the costs and the commit they were
measured at, and rebuilds the partition. **The numbers must come from a
runner**: a development machine gives a different answer, not only a different
total but a different *order*, which is why the partition is one per platform.

**The suite is split into six shards per platform, and each shard runs in its
own job on its own runner.** The reason is measured: the Windows job spent
34.5 minutes and the Ubuntu job 17.5, and every other required check
together came to under two minutes, so the suite was the whole of the wait.
One runner doing everything is the worst possible arrangement for a suite
whose cost is spread unevenly.

**Adding a test file means adding it to the shard list**, and
`tests/test_ci_shard_coverage.py` is what says so: it fails if a test file
is in no shard, in two shards, if a shard names a file that does not exist,
if the shard count disagrees with the workflow's matrix, if a cost is
missing, or if the shards have drifted out of balance. **A file in no shard
is a test CI never runs**, and every other check would stay green while it
went. The fix is `python .github/make_ci_shards.py`, which refuses to guess
a cost it has not measured.

**The costs are measured on the runner, and the two platforms get their own
partition.** One file took 383 seconds on Windows and 45 on Ubuntu; another
took 153 on Ubuntu and 288 on Windows — not the same total, a different
*order*. A partition balanced for one platform is lopsided on the other. The
per-file seconds come out of the CI log, which is why the pytest step runs
with `--durations=0`.

**Do not add `-n` to the CI pytest step.** The workers were measured and
they lost: eight workers made the whole-suite Ubuntu job 2.15 times faster
and the Windows job *slower* than one, and inside a shard they lost again —
the Windows shard that took 741s with one worker took 961s with four. The
parallelism that is left is the parallelism between the jobs.

**A job's name is the gate, so it must say which job it is.** GitHub
identifies a check by its name, so several jobs sharing a name are *one*
check as far as branch protection is concerned, and a required check naming
one of them is satisfied by whichever reports first. The names carry the
platform and the shard, and a test watches that they do.

## Claims are measured, not asserted

**A property that is stated and not watched is not held.** Every claim about
the product's behaviour needs a witness: a test that fails when the property
is broken. That includes the mechanisms that do the watching — a rule that
reads the tests is a mechanism, and it needs a test of its own, or it can be
neutered and the whole tree stays green.

**The witness must fail for the property.** A test that fails because of the
project's own lint, or because of an unrelated encoding or line-length
matter, is not a witness of that property. When a test goes red, ask what
made it red before believing that it caught something.

**A value that can change is re-measured, not carried forward.** Numbers in a
record are anchored to the commit they were measured at, and a claim about
one commit does not carry to another unless the bytes it depends on did not
change.

**A record is not evidence.** The record says what was decided; the
measurement says what is true. Where they differ, the measurement wins and
the record is corrected.

## After a merge

**Run the witness ledger.** A merge that resolves conflicts can keep a
*deletion* as well as a change, and a witness can disappear silently while
every test still passes:

```
python C:\Users\pc\labcairn-g4\recover\witness_ledger.py <before> <after>
```
