# PR #1 — Independent technical re-review

**Verdict:** Approve with the corrections applied here. No C-1/C-2/R-01/R-02 finding was refuted; all four were reproduced from primary evidence before being accepted.
**Reviewer:** Claude (Opus), reviewing a prior review produced by a different model.
**Date:** 2026-10-15
**Subject:** PR #1 @ `356401f1` (`docs/lc-p1-00-review-p1-01-decisions`), base `main` @ `623e3ca`
**Reviewed artifacts:** all 18 tracked files — the full PR diff (4 new files), plus `PHASE_1_WORKORDERS.md`, `UPSTREAM_REFERENCES.md`, `ARCHITECTURE.md`, ADR-0002/0003/0004, `LC-P1-01-task-breakdown.md`, `README.md`, `acceptance/LC-P1-00-evidence.md`.

## Why this re-review exists

The instruction was explicit: the C-1/C-2/R-01/R-02 conclusions came from another model's review and must not be accepted on the strength of their being stated. So each was treated as a falsifiable claim and either reproduced from primary evidence or refuted. **Nothing was confirmed by reading the review's own reasoning.**

No product code, test suite or CI exists in this repository, so no runtime behaviour could be tested. Every verdict below rests on one of three evidence types, always named:

| Type | What it means |
|---|---|
| **Code read** | A claim about a file in this repository, confirmed by opening it |
| **Reproduced** | A claim about packaging/runtime behaviour, confirmed by actually running it |
| **External clone read** | A claim about an upstream pinned commit, confirmed at `E:\labcairn-upstreams` |

## Rulings verified

### R-01 — ADR-0003 conflates SQLite `AUTOINCREMENT` with per-Task gapless `seq` — **CONFIRMED (code read + reproduced)**

*Code read.* ADR-0003's `C1 — Event vocabulary` table specified, in one row:

> `seq` | `INTEGER PRIMARY KEY AUTOINCREMENT`-style gapless allocation **inside** the transaction; `UNIQUE(task_id, seq)`

Those two clauses are mutually exclusive. In SQLite an `INTEGER PRIMARY KEY` column *is* the rowid: unique across the whole table by construction, so values are handed out across Tasks rather than restarted per Task.

*Reproduced.* Allocating a counter per Task under `BEGIN IMMEDIATE`, with a separate `INTEGER PRIMARY KEY AUTOINCREMENT` for table identity:

```
events (id=全局行号, seq=每任务序列):
  id=1  task_id=1  seq=1        task 1 by seq: [1, 2, 3]   <- contiguous
  id=2  task_id=1  seq=2        task 2 by seq: [1, 2]      <- contiguous
  id=3  task_id=2  seq=1        rollback test: task 1 stays [1,2,3], no gap
  id=4  task_id=2  seq=2
  id=5  task_id=1  seq=3
```

The global `id` for Task 1 is `1, 2, 5` — not contiguous. Only the separate `seq` column gives the per-Task tail that `after_seq=<last_seen>` resumption (ADR-0003, case 3) depends on. This also confirms the rest of the ruling: rollback consumes no sequence number, so fault-injection cannot leave a hole.

**Correction applied:** `seq` is now `INTEGER NOT NULL` with a new sibling `id` column for table-wide identity, plus an inline paragraph titled *Why `seq` cannot be the rowid* that states the incompatibility explicitly so it is not reintroduced.

### R-02 — `task_created` / `task_revised` cannot require a `run_id` — **CONFIRMED (code read)**

*Code read.* Seven lines apart in the same contract table, ADR-0003 asserted:

> `task_id`, `run_id` | always non-null; an event belongs to exactly one attempt

…while the closed enum immediately below it contains `task_created` and `task_revised`. A Task exists *before* its first Run and can be revised *between* Runs, so under `run_id NOT NULL` those two event types cannot be inserted at all. The contradiction is internal to one document and is not a matter of judgement.

**Correction applied:** `run_id` is now nullable, required only for `run.*` / `stage.*` / `operation.*` / `approval.*` / `checkpoint.*`, with validation stated as per-event-type rather than per-column.

### C-1 — required `pull_request` checks must not be filtered by `paths-ignore` — **CONFIRMED**

*Code read.* `UPSTREAM_REFERENCES.md` required `paths-ignore` on **both** `on: push` and `on: pull_request`, while `PHASE_1_WORKORDERS.md` (LC-P1-01 Acceptance) required the exclusion job to "run on every pull request". These cannot both hold. GitHub reports a filtered workflow as *expected* rather than passing, so a required check that is filtered leaves a reference-only PR permanently unmergeable — the filter does not make the job skippable, it makes it a deadlock.

**Correction applied:** the checklist row and the LC-P1-01 Build section now forbid filtering on any workflow GitHub reports as a required status check, and restrict filtering to optional/push workflows. The artifact/cache `path:` exclusion is unaffected and was retained.

### C-2 — `packages = ["src/labcairn"]` is only correct under Hatchling — **CONFIRMED (reproduced, both directions)**

This was the finding most likely to be wrong, because it hinges on backend-specific behaviour. It was tested rather than recalled.

*Hatchling*, `packages = ["src/demo_pkg"]` with a `demo_pkg/core/` subpackage:

```
demo_pkg/__init__.py
demo_pkg/core/__init__.py     <- subpackage INCLUDED
```

*setuptools*, `packages = ["demo_pkg"]`, identical tree:

```
demo_pkg/__init__.py           <- subpackage SILENTLY DROPPED
Successfully built ... .whl    <- build reports SUCCESS, no warning
```

So the amendment is right on both counts: the literal is correct under Hatchling as a recursive root, and under setuptools it fails **silently** — the wheel builds, the import of `labcairn.core` fails later at install/runtime. `MANIFEST.in` is also setuptools-only and must not be introduced.

**Correction applied:** Hatchling named explicitly with the verified semantics, `MANIFEST.in` row replaced with Hatchling sdist exclusions, and the silent-drop failure mode documented so a future editor does not "simplify" it back.

## R-05 — two real defects in `scripts/checkout_upstreams.py` — **CONFIRMED (both reproduced, both fixed)**

Neither was in the review's blocking list, but both were reproduced here and are fixed.

**(a) Non-dict `snapshot.json` raises `AttributeError`.** `load_snapshot` guards with `not isinstance(previous, dict) or ...`, then formats `previous.get('manifest_version')` inside the error message. For a JSON array the guard short-circuits correctly but the message still calls `.get` on a `list`. Observed:

```
AttributeError: 'list' object has no attribute 'get'
```

A traceback instead of the intended refusal. Now: `ERROR: ... declares manifest_version None but this script writes 1. Refusing to overwrite`, exit 1, snapshot left untouched.

**(b) `rev-parse HEAD` does not prove the checkout root.** `git -C <path> rev-parse HEAD` walks *upward*. A plain directory nested inside an unrelated repository reports **that** repository's HEAD. Reproduced by nesting an empty `openhands-sdk/` inside a throwaway repo with one commit:

```
recorded : 17772ccad309a2673c0ae5e2ac6efb61b47d5aa1
expected : the openhands-sdk clone's actual commit
MATCH    : True   <- the outer repo's commit was pinned as openhands-sdk's
```

This is the worst failure mode in this project: a **fabricated provenance record**, in a document whose entire purpose is that every SHA is real. Now guarded with `rev-parse --show-toplevel`, which exits 1 with an explanation instead of recording it. Both fixes were regression-tested, and the five real reference clones still report their original SHAs unchanged.

## Findings checked and confirmed without change

| Finding | Basis | Outcome |
|---|---|---|
| R-03 (resolve C-1/C-2) | code read | Correct; both resolved as above |
| R-04 (PyMuPDF AGPL/commercial) | code read | Correct. Still an open dependency decision, now stated in README and LC-P1-01 |
| R-06 (stale checklist / README license / T01) | code read | Correct — README told the reader to add a LICENSE "when creating the GitHub repository", but the repository exists and deliberately has none |
| R-07 (no broad gitleaks allowlist) | code read | Correct, and consistent with an independent finding made earlier in this project's history: an allowlist would hide the exact `git add -f` mistake it should surface |
| "All five pinned SHAs resolve on GitHub" | not reproducible here | Accepted as the reviewer's own network observation; **not** re-verified. Stated below as unverified rather than endorsed |

## Documents synchronized

The instruction was to leave no two conflicting sets of implementation requirements. Conflicting text was found in four places beyond the two the PR body named, and all were corrected:

| File | Conflict removed |
|---|---|
| `UPSTREAM_REFERENCES.md` | Packaging row + `MANIFEST.in` row (C-2); `paths-ignore` row (C-1); secret-scan allowlist (C-4); LC-P1-00 acceptance checklist brought current (R-06) |
| `PHASE_1_WORKORDERS.md` | LC-P1-01 Build: `MANIFEST.in`, `paths-ignore`-on-PR, secret-scan allowlist, "MIT license once ownership cleared", and the implied first-commit step. Acceptance: Ubuntu+Windows, unconditional PR job, license honesty |
| `plans/LC-P1-01-task-breakdown.md` | 1036 lines of task bodies still instruct the superseded behavior. A supersession banner now states each conflict, the ruling, and the affected task IDs — **the task bodies were deliberately left unedited** so the plan's own reasoning stays auditable |
| `ADR-0002` | Assigned every contract to LC-P1-03 while LC-P1-01 requires a FakeProvider (C-3); scope correction added |
| `README.md` | License paragraph replaced with the true status: no rights granted, placeholder grants nothing, PyMuPDF unresolved |

## Consistency check

| Check | Result |
|---|---|
| README → document links | Resolves; README license status now matches the repo's actual state |
| `docs/README.md` index | Covers every document via `adr/`, `plans/`, `acceptance/`, `handoff/` |
| `acceptance/LC-P1-00-evidence.md` | Still accurate; its recorded disk-measurement drift was resolved before `623e3ca` and the note says so |
| `handoff/CURRENT.md` | Updated — it previously listed "synchronize older documents" as next, which is now done |
| Upstream clones vs. repository | 693 MB sibling directory; repository is 14 authored files; no submodule, no vendored source, no third-party LICENSE |
| LC-P1-01 | **Not started.** No `pyproject.toml`, `src/`, `web/`, `tests/` or `.github/` exists. Nothing in this review implements it |

## Open items — not resolved by this review

1. **PyMuPDF licensing is unresolved (R-04).** LC-P1-08 names it; it is AGPL/commercial dual-licensed. Adopting it constrains a future MIT release. Needs a decision before LC-P1-08, not before LC-P1-01.
2. **Copyright ownership is still unclear.** No `LICENSE` file, by deliberate decision. Placeholder text must never be read as a grant.
3. **`tests/test_no_reference_leakage.py` does not exist.** The isolation promises remain prose until LC-P1-01 lands it. The LC-P1-00 checklist marks that item **partial**, not passed — the negative half (no dependency) holds, the positive half ("an external contributor can build") is untestable with no package.
4. **The LC-P1-00 dossier item belongs to LC-P1-14** and is unreachable now.
5. **"Concise" ADRs are disputed and left open.** The three ADRs total ~1,270 lines. The substantive bar is met — upstream claims pinned to `file:line`, rejected options recorded — but the length was flagged and deliberately not resolved by shortening.
6. **GitHub-side remote retention of the five pinned SHAs was not verified** by this review. A shallow single-branch clone pins SHAs that exist only in the local object store; upstream force-push or GC can invalidate them.
7. **`docs/acceptance/LC-P1-00-review-623e3ca.md` is this review's input, not its output.** If any ruling here is later contradicted, that file is the wrong place to look for the correction.

## What was deliberately not done

- LC-P1-01 was not started, partially or as a scaffold.
- PR #1 was not merged and no settings changed.
- No upstream code was executed, and no reference clone was moved or re-cloned.
