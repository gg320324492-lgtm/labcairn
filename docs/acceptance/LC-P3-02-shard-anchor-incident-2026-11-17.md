# LC-P3-02 — the shard costs' anchor named a revision the squash merge rewrote away (2026-11-17)

**Date:** 2026-11-17. **Type:** dated incident record for the CI shard-cost
anchor. It records an accident that turned `main` and the open pull requests
red in one go, the mechanism behind it, the two repairs that landed, and the
steps that reproduce it. It carries no DOCX material, no reviewer text and
nothing read out of the corpus.

## Final status sentence

**A squash merge rewrote the revision the shard costs were anchored to; the
cost witness could not find that revision, so `main` and the open pull
requests went red until the costs were re-measured on the merged tree and
re-anchored. Repaired by PR #197, guarded by PR #199.**

## The revisions, as they stand

| what | value |
|---|---|
| the branch commit the costs were measured on | `d74ac7aa98069d647c4bbdfd3299280d12d24954` |
| the run that measured it | `44081024354`, head `d74ac7aa98069d647c4bbdfd3299280d12d24954`, conclusion `success` |
| the tree that branch commit carries | `ec260b551655eac6dfc023eb93befa853084d608` |
| the squash merge that landed the work | `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8` |
| the tree the squash merge carries | `340083a0f42602caae52427712a63f40587d6c86` |
| the run that went red on `main` | `44092424276`, head `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8`, conclusion `failure` |
| the run the re-anchor measured from | `44087676811`, head `e16d82d3ce49d6859ff4c34b18e1880dc7ae417d`, conclusion `success` |
| the tree that run's head carries | `340083a0f42602caae52427712a63f40587d6c86` |
| the re-anchor (PR #197) | `7ab658f4834c3b1449222a794d22427353535a11` |
| the ancestor witness (PR #199) | `a72a1ef7ae469e3452a99fb7d21f158b927ebe68` |
| the shard file's `measured_at` now | `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8` |

Two of those rows are one tree: `git rev-parse b2e3661^{tree}` and
`git rev-parse e16d82d^{tree}` both print
`340083a0f42602caae52427712a63f40587d6c86`. That is why run `44087676811`
could stand in for the merged tree when the costs were re-measured, and why
its numbers were worth carrying into the shard file unchanged.

## 1. What happened, in order

Every time below is UTC, read from the runs' own `created_at` and from the
runners' log timestamps.

| when | what |
|---|---|
| 2026-11-17 12:12:23 | PR #195's branch commits `d74ac7a…` — the text-box repair and sample 08's declared image. |
| 2026-11-17 12:12:49 | Run `44081024354` measures that branch head and succeeds. The re-measurement writes `measured_at: d74ac7aa98069d647c4bbdfd3299280d12d24954` into `.github/ci-shards.json` — the branch commit, because that is the run's head. |
| 2026-11-17 12:55:11 | The branch takes `main` in and lands on `e16d82d…`, whose tree is byte-for-byte the tree the merge will produce. |
| 2026-11-17 13:24:29 | PR #195 is merged by **squash**. The work lands as `b2e3661…`, a commit with one parent, `c9aa38bf808821a95262c2045c1c39093b11aacd`. The branch commit `d74ac7a…` is now in no history that `main` has. |
| 2026-11-17 13:24:32 | The push run on `main` starts: `44092424276`. The shard file it checks out still says `measured_at: d74ac7a…`. |
| 2026-11-17 13:31:38 | `python-quality (ubuntu-latest, shard 2)` fails: the witness cannot find the anchor. |
| 2026-11-17 13:43:27 | PR #194's run `44095579632` starts on head `0582cc533a8a52fe8df0e5399c703bf053427925`. |
| 2026-11-17 13:47:25 | `python-quality (windows-latest, shard 5)` fails, the same way. |
| 2026-11-17 13:49:25 | PR #194's run fails, with the same sentence. |
| 2026-11-17 13:55:30 | PR #197 opens: re-measure on the merged tree, re-anchor to the commit `main` carries. |
| 2026-11-17 14:24:52 | PR #197 merges as `7ab658f…`. The push run on `main` (`44102846382`) succeeds. |
| 2026-11-17 16:22:32 | PR #199 merges as `a72a1ef…`: the anchor has to be an ancestor of `HEAD`, not merely a revision the checkout happens to hold. |

The failure message, verbatim from the runner's log of
`python-quality (ubuntu-latest, shard 2)` in run `44092424276`:

```
E  Failed: the commit d74ac7aa98069d647c4bbdfd3299280d12d24954 is not in this
checkout, so the costs cannot be checked. The shard file's measured_at must
name a commit the checkout contains -- a run id, for instance, is not one.
```

The same sentence is in the log of `python-quality (windows-latest, shard 5)`
in that run, and in both failing jobs of PR #194's run `44095579632`.

Only two of the twelve shard jobs went red, and that is the shape of the
mechanism rather than a coincidence of timing: the witness lives in one
file, `tests/test_ci_shard_coverage.py`, and at `b2e3661` the partition
carried that file in ubuntu shard 2 and windows shard 5 — which are exactly
the two jobs that failed. The shards that do not run that file stayed green.

## 2. The root cause

The re-measurement tool, `.github/remeasure_shards.py`, records two things
in the shard file: the per-file costs, and **the commit those costs were
measured at**. The second one is not decoration — it is the *identity of the
measurement*. The rule the project already states is that a number is
anchored to the commit it was taken on, so that a reader can tell whether
the number still describes the tree in front of them.

The tool's default was to take that commit from **the run's head SHA**
(`_run_head_sha`), and the tool's `--measured-at` option was there to
override it. On a pull request the run's head is a **branch commit**, so the
default wrote a revision whose place in history is decided *after* the
measurement is taken, by whatever the merge turns out to be.

A squash merge decides it by rewriting. `d74ac7a…` became `b2e3661…`, a
new commit with one parent, and the branch commit entered no history at all.
So the recorded anchor and the identity of the tree the work landed in came
apart: the anchor was a revision **no clone of `main` contains**.

Two things then followed, and both are visible in the tree today:

- `.github/ci-shards.json` at `b2e3661` carries
  `"measured_at": "d74ac7aa98069d647c4bbdfd3299280d12d24954"` — read it with
  `git show b2e3661:.github/ci-shards.json`. The bad anchor is in the merged
  commit itself, not in some later mistake.
- The witness, `test_the_costs_belong_to_the_tree_they_were_measured_on`,
  runs `git diff --name-only <anchor>..HEAD -- src/ tests/`. With an anchor
  git cannot resolve, that command exits non-zero and the witness fails
  with the message quoted above.

The deeper defect is in the default, not in the option: **a tool that
records the identity of a measurement should not default to a revision whose
identity is still provisional.** A pull-request run's head is provisional by
construction.

## 3. What the witness did right

The witness's own docstring says the failure is not hypothetical — the
re-measure command once recorded the *run id* as the commit, and `git diff`
refused it, the changed-path list came back with no file in it, and every
file's cost was read as zero, so the check **passed without having looked at
anything**. That shape is what this accident walked into from the other
side: the anchor was unresolvable, and instead of reading "nothing
changed", the witness said **it could not look, and therefore it does not
know**.

That is the property the project already asks for: *a measurement that
cannot be located is not a measurement that says the costs are still good; it
is a measurement that says nothing, and a witness that says nothing is a
witness that has been turned off.* The witness went red rather than green
because the anchor was missing. **It failed for the right reason, and that
is the only reason the red was useful.**

## 4. The repairs

**PR #197 — `7ab658f4834c3b1449222a794d22427353535a11`.** The costs were
re-measured from run `44087676811`, whose head `e16d82d…` carries the tree
`340083a0…` — the same tree `b2e3661…` carries — and the anchor was moved
to the commit `main` actually holds. The three documents that print the
anchor and the figures moved with it: `.github/CI.md`,
`.github/workflows/python.yml` and `docs/plans/LC-P1-13-evaluation-ci.md`.

**PR #199 — `a72a1ef7ae469e3452a99fb7d21f158b927ebe68`.** A new witness,
`test_the_costs_were_measured_on_an_ancestor_of_this_tree`, requires
`measured_at` to satisfy `git merge-base --is-ancestor <measured_at> HEAD`,
and it distinguishes the two accidents by git's own exit status:

| exit status | what git is saying | what the witness reports |
|---|---|---|
| 0 | the revision is an ancestor of `HEAD` | the anchor is good |
| 1 | the revision is in this checkout, but `HEAD` did not grow out of it | *a revision was rewritten away* |
| 128 | the revision does not resolve here at all | *the revision was never here* |

**The tool convention that came out of it.** When the run being measured is a
pull-request run, the anchor is given explicitly with `--measured-at`, naming
a commit that is already in `main`'s history:

```
python .github/remeasure_shards.py 44087676811 --measured-at b2e3661a8988bd36d3fc1d63348ac9dcb34473d8
```

The tool already had the option (`8de1e24`, 2026-10-25) and already had the
run-head default (`9b398fe`, 2026-10-25). What the accident changed is which
one is used when.

## 5. The lesson

**A merge rewrote a revision that a witness was anchored to, and that
revision was the recorded identity of a measurement.** The anchor was not a
label on the measurement; it was what made the measurement *about* this
tree. Rewriting it made the measurement about a tree that does not exist.

This is the same lesson the repository already carries as *composition can
delete witnesses* — a merge that keeps a change can also keep a **deletion**,
and a witness can disappear while every test still passes. It recurred here
one level up: the merge did not delete a witness, it deleted the thing the
witness was anchored to, and the witness correctly reported that it could no
longer see what it was watching.

Three consequences follow, each of which is a mechanism rather than a
precaution:

1. **An anchor is an identity, and identities that a merge can decide must
   not be recorded provisionally.** The tool's default was the run's head;
   the convention is now `--measured-at` with a commit already in `main`.
2. **"The revision is in this checkout" is a weaker property than "this tree
   grew out of it", and only the second one survives a rewrite.** Measured
   below: in a checkout that still holds the pre-squash object as a dangling
   object, the old witness **passes** — `git diff` compares two unrelated
   trees and finds nothing heavy enough to complain about — and only the
   ancestor witness of PR #199 catches it. The guard that survives the
   accident is the one that asks about *history*, not about the object
   store.
3. **A witness that cannot look must say so.** The failure message names the
   revision, says the costs cannot be checked, and says what to do. A
   witness that degrades to "nothing changed" when its input disappears is
   the accident this one nearly was.

## 6. How to reproduce it

The reproduction needs **a clone that holds only what `main` holds**. That
matters, and it is the one step people get wrong: a clone made from a local
path with `git clone <path>` hard-links the source's whole object store, so
it still holds the pre-squash commit as a dangling object and the failure
does not appear. `--no-local` forces the transport and copies only reachable
objects; a clone from GitHub does the same by construction.

The steps below were run on 2026-11-18 and their output is quoted as it
came.

```bash
# 1. a clone that holds only what main holds
git clone --no-local https://github.com/gg320324492-lgtm/labcairn.git clean-clone
cd clean-clone
git log -1 --oneline

# 2. the accident's shape: anchor the costs at the pre-squash commit
python - <<'PY'
from pathlib import Path
p = Path('.github/ci-shards.json')
b = p.read_bytes()
p.write_bytes(b.replace(
    b'b2e3661a8988bd36d3fc1d63348ac9dcb34473d8',
    b'd74ac7aa98069d647c4bbdfd3299280d12d24954'))
PY

# 3. the witness
python -m pytest tests/test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on
```

Step 3 fails, with

```
E  Failed: the commit d74ac7aa98069d647c4bbdfd3299280d12d24954 is not in this checkout, so the costs cannot be checked. The shard file's measured_at must name a commit the checkout contains and that HEAD grew out of -- a run id, for instance, is neither.
```

(The wording now reads "and that HEAD grew out of"; on the day it read
"...must name a commit the checkout contains -- a run id, for instance, is
not one." PR #199 extended the sentence when it added the second witness.)

Replace `d74ac7a…` with `b2e3661a8988bd36d3fc1d63348ac9dcb34473d8` in the
shard file and run the same command again: it passes, together with
`test_the_costs_were_measured_on_an_ancestor_of_this_tree`.

**The second experiment, which is why PR #199 exists.** Make the clone
*keep* the dangling object (`git clone <path>` without `--no-local`, or
`git fetch origin refs/pull/195/head` into a scratch ref), anchor the costs
at `d74ac7a…` again, and run **both** witnesses. Measured on 2026-11-18:

```
1 failed, 1 passed
```

- `test_the_costs_belong_to_the_tree_they_were_measured_on` **passes**. The
  revision resolves, so `git diff` runs, and the two trees it compares differ
  in `src/labcairn/editing/samples.py` and `tests/test_docx_edit_samples.py`
  — changes the partition has slack for, so the witness has nothing to
  complain about. The old witness is blind in this checkout.
- `test_the_costs_were_measured_on_an_ancestor_of_this_tree` **fails**, with
  the accident named exactly:

  ```
  E  AssertionError: the shard file's measured_at is d74ac7aa98069d647c4bbdfd3299280d12d24954, and it is in this checkout but HEAD did not grow out of it.
  ```

  The same three-way distinction can be read by hand:

  ```
  git merge-base --is-ancestor d74ac7aa98069d647c4bbdfd3299280d12d24954 HEAD ; echo $?
  ```

  `0` ancestor, `1` present but not an ancestor, `128` not resolvable here.

## 7. What this record does not do

- It does not say the shard costs were wrong. They were right; what was
  wrong was the revision they were anchored to, and the numbers came back
  unchanged when they were re-measured on the merged tree.
- It does not say the witness was wrong or too strict. It failed because it
  could not look, and it said so.
- It does not claim that every pull request was red for this reason. What is
  measured here is `main`'s run `44092424276` and PR #194's run
  `44095579632`, both with the same message. PR #196 was open at the time
  and was red too, but for an unrelated reason that predates this accident:
  a record's printed figures lagged its subject
  (`tests/test_docx_edit_records.py::test_the_run_record_reports_the_options_and_what_each_cost`).
  PR #176 was open and had no run in this window.
- It does not propose a new tool, a new workflow or a new gate. The two
  repairs are landed; this record exists so that the next person who sees a
  `measured_at` pointing at a branch commit knows what it costs.
