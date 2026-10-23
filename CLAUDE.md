# Working in this repository

## Language

**Reason and think in Chinese.** The reasoning that appears in the conversation
is written in Chinese.

**The repository stays in English.** Code, identifiers, docstrings, comments,
commit messages, test names, record files and every document committed here
are in English. The two are different surfaces and they do not mix: Chinese
for the thinking, English for everything that lands in the tree.

## Branches and checkouts

**One checkout holds one branch at a time.** Two agents working in the same
checkout switch branches under each other and their commits land on someone
else's branch. When more than one agent writes code, each one gets its own
worktree (`isolation: "worktree"` on the agent call) and its own branch.

**A push is not a local action.** Ask before pushing to a shared branch, and
never force-push to `main`.

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
