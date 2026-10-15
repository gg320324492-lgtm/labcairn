# LC-P1-01 — Acceptance evidence

**Verdict requested:** `PASS` / `PASS WITH NOTES` / `BLOCKED` / `FAIL`  
**Branch:** `feat/lc-p1-01-baseline` · **PR:** [#2](https://github.com/gg320324492-lgtm/labcairn/pull/2) — read the subject SHA from the PR itself  
**Base:** `main` @ `b526749` · **Date:** 2026-10-15  
**Scope:** LC-P1-01 as written in `docs/PHASE_1_WORKORDERS.md`, with the eight binding rulings in `docs/plans/LC-P1-01-approved-amendments.md`.

**This is an engineering baseline, not a product.** There is no CLI, no server, no database and no research feature. The Phase 1 deliverable — a researcher running a real task — remains entirely unbuilt, as it should at G1's first work order.

## Acceptance checklist

| Clause | Status | Evidence |
|---|---|---|
| Fresh clone, documented setup, on CI-supported OS | **PASS** | CI green on `ubuntu-latest` and `windows-latest`; run links below |
| Lint / type / test pass | **PASS** | ruff, ruff format, `mypy` strict, 174 pytest — locally and in CI |
| Quick-start claims no unimplemented command | **PASS** | `tests/test_readme_accuracy.py`, 17 tests, fail-closed both directions |
| Secret scan included | **PASS** | `.gitleaks.toml` + `security.yml`, git mode, green in CI |
| Lockfile consistency check included | **PASS** | `lockfiles.yml` green in CI |
| FakeProvider and fixtures run without paid APIs | **PASS** | 48 tests; socket and httpx patched to raise; suite passes under `env -u` with credential-shaped variables removed |
| Reference exclusion **verified, not asserted** | **PASS** | 99 tests. They run on **both** platforms via `python-quality` (which runs the whole pytest suite), but the dedicated `reference-exclusion` job — build, clean-venv install, archive validation — is **Ubuntu-only**. See the platform matrix below. |
| No third-party source committed | **PASS** | 0 submodules; the sibling `labcairn-upstreams` is outside the tree and never referenced by CI |

## Commands and their actual results

Run locally on Windows 11, Python 3.12.13, uv 0.11.21, Node 24.16.0, pnpm 9.15.9.

```
uv sync --frozen              Checked 160 packages
uv run ruff check .           All checks passed!
uv run ruff format --check .  18 files already formatted
uv run mypy                   Success: no issues found in 17 source files
uv run pytest                 174 passed in 11.57s      (0 skipped)
uv lock --check               Resolved 163 packages
uv build                      wheel 11 members, sdist clean of reference paths
uv lock --check               exit 0 after [tool.uv] required-version added

cd web
pnpm install --frozen-lockfile    Lockfile is up to date
pnpm run typecheck                exit 0
pnpm run lint                     exit 0
pnpm run test                     Test Files 2 passed, Tests 7 passed
pnpm run build                    built in 77ms

gitleaks git --config .gitleaks.toml --redact
  24 commits scanned, ~1.14 MB, no leaks, exit 0
  (run locally at HEAD ce15692; an earlier commit scanned 11 commits / 436 KB.
  The scan covers the whole history, so the figure grows with the branch —
  stated as a past measurement at a named commit rather than as "current".)
```

The two `skip`s that existed after T05 are **gone**: `test_no_workflow_requires_an_upstream_checkout` and `test_upload_artifact_and_cache_steps_exclude_reference_paths` both pass now that `.github/workflows/` exists. They previously reported the CI half of the gate as *inert*, not passing.

## CI runs

Six distinct jobs, all green. **Correction to an earlier statement in this document: the count is 6 jobs, not 8.** Each workflow triggers on both `push` and `pull_request`, so each job appears twice in `gh pr checks`; an earlier draft deduplicated them inconsistently and reported eight. The correct basis is **6 distinct jobs, 12 check entries across two triggers**.

**Only `python-quality` is cross-platform.** It is the sole workflow with a matrix; `web-quality`, `reference-exclusion`, `secret-scan` and `lockfile-consistency` all run on `ubuntu-latest` only.

**Each workflow is dispatched separately, so a single push produces one run per workflow, not one shared run.** The five workflows below therefore carry five distinct run ids; only the two `python-quality` legs share a run id, because they are two jobs of a single matrix run. Each link below points at the individual job page for HEAD `ce15692`.

| Job | Run |
|---|---|
| ~~all six from the same push run~~ | ~~[38727513778](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38727513778)~~ |
| `python-quality (ubuntu-latest)` | [python-quality ubuntu](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992065/job/116405118826) |
| `python-quality (windows-latest)` | [python-quality windows](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992065/job/116405119494) |
| `web-quality` | [web-quality](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992050/job/116405118499) |
| `reference-exclusion` | [reference-exclusion](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992014/job/116405118739) |
| `secret-scan` | [secret-scan](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992056/job/116405118937) |
| `lockfile-consistency` | [lockfile-consistency](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38729992018/job/116405118723) |

**Build artifacts** produced by the `reference-exclusion` run for HEAD `ce15692`: `sdist` 354,565 B · `wheel` 27,243 B · `source-archive` 354,425 B.

Artifact sizes move on every commit, so they are recorded against the SHA that produced them rather than described as "current" — ~~`350,472 / 27,243 / 350,651`~~ was the previous commit's `reference-exclusion` run, not this one.

## Platform matrix — verified, not assumed

Read directly from the workflow YAML rather than inferred from the check list:

| Workflow | Job | `runs-on` | Matrix |
|---|---|---|---|
| `python.yml` | `python-quality` | `${{ matrix.os }}` | `ubuntu-latest`, `windows-latest` |
| `web.yml` | `web-quality` | `ubuntu-latest` | none |
| `reference-exclusion.yml` | `reference-exclusion` | `ubuntu-latest` | none |
| `security.yml` | `secret-scan` | `ubuntu-latest` | none |
| `lockfiles.yml` | `lockfile-consistency` | `ubuntu-latest` | none |

**What this means for the isolation gate.** The leakage tests themselves are
platform-independent and do run on Windows, because `python-quality` executes the whole
pytest suite. That is how the two Linux-only defects in this phase were caught: the case
variant that Windows could not reveal, and the `tar -tf` path handling that only Windows
exercises. But the **dedicated** `reference-exclusion` job — the one that builds the
wheel and sdist, installs into a clean environment, imports, and validates the release
archive — runs on **Ubuntu only**. On Windows, `python-quality` would still fail if a
leak were tracked, because `test_no_reference_leakage.py` is part of that suite; but the
packaging half of the gate is single-platform. Recorded here rather than presented as
two-platform coverage.

## Required status checks — the C-1 verification

The branch-protection configuration, verbatim from the API:

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "python-quality (ubuntu-latest)",
      "python-quality (windows-latest)",
      "web-quality",
      "reference-exclusion",
      "secret-scan",
      "lockfile-consistency"
    ]
  },
  "enforce_admins": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

`strict: true` means a required check that never reports — the state a `paths-ignore`
filter produces — blocks the merge rather than being skipped. That is the mechanism C-1
describes, and it is configured.

**How a reviewer can read this.** `GET /repos/{owner}/{repo}/branches/main/protection`.
It requires admin on the repository; a session or token without that scope returns 403,
which is the likeliest reason the check could not be read independently.

**A runtime demonstration was attempted and is reported as inconclusive.** `git push
--dry-run origin HEAD:main` returned exit 0. That is not evidence the protection is
absent: GitHub cannot evaluate required status checks for a commit that has not been
pushed, because the checks have not run. No honest live proof is available from a client
that cannot merge, so the API configuration above is offered as the evidence rather than
a demonstration that would prove nothing. `gh pr merge --dry-run` does not exist.

C-1's claim that a required check cannot be skipped by `paths-ignore` depends on a repository setting, not a file, so it could not be verified from the tree. It was verified here by applying branch protection:

```
required_status_checks.contexts = [
  "python-quality (ubuntu-latest)", "python-quality (windows-latest)",
  "web-quality", "reference-exclusion", "secret-scan", "lockfile-consistency" ]
strict = true          # must be up to date with main before merging
enforce_admins = true
allow_force_pushes = false
allow_deletions  = false
```

Independently, no workflow uses `paths-ignore` on `pull_request`; the only occurrences of that string are in comments explaining why it is absent. This is now the property that makes C-1 true, and it is enforced by GitHub rather than by prose.

**Required *approving reviews* is deliberately not enabled.** With one account on the repository it would make the owner unable to merge anything. The no-self-merge rule is a process rule recorded in `docs/README.md`, not a technical gate. Enable it if a second reviewer joins.

## The two defects only a real runner could find

Both were invisible locally and both would have shipped a broken gate.

**1. `astral-sh/setup-uv@v10` does not exist.** Every job provisioning uv failed in 2–4 seconds with `Unable to resolve action ... unable to find version 'v10'`. The published tags are `v10.3.0`, `v10.2.0`, `v10.1.0`, `v10.0.1`, `v10.0.0`, then `v9.0.0` — there is no floating `v10`. The T06 verification had confirmed `v10.3.0` exists while the workflow referenced `v10`. Pinned to `v10.3.0`; all six action references were then re-checked against the GitHub API and resolve.

**2. Two case variants were missing from the packaging exclusions.** Linux failed a test Windows passed:

```
AssertionError: labcairn-0.1.0.tar.gz packages reference-study material:
  LabCairn-upstreams-t05probe/LEAK.md
  labcairn-Upstreams-t05probe/LEAK.md
```

The sdist and wheel exclude lists carried three case variants of the `labcairn-upstreams` family and missed two. `.gitignore` matching is case-insensitive on Windows, so the omission was invisible here — the probes were excluded before packaging saw them. On Linux, case-sensitive matching let both into the sdist. The comment above the list already asserted "case-variant-complete", so the code contradicted its own stated intent. Both lists now cover all eleven stems, verified with `fnmatch` under case-sensitive matching.

This is the exact failure C-8 and the exclusion checklist both predict will only appear on a real runner. **Correction to an earlier claim in this document:** `reference-exclusion` does **not** run on both platforms — it is Ubuntu-only, as the platform matrix above records. The leakage *tests* reach Windows through `python-quality`, which runs the whole suite. That is what surfaced these two defects: the case variant is invisible to Windows, and `tar -tf` is only exercised there.

## Deviations from the plan, and why

| Deviation | Reason |
|---|---|
| `src/labcairn/core/providers/` not `src/labcairn/providers/` | `ARCHITECTURE.md` defines `core/` as "config, provider adapters, typed model/tool output". The T08 agent was given the wrong ownership by the coordinator; the move broke the AST gate, which refused to pass with "the sweep proved nothing" |
| Transcripts ship in the package as `canonical_json`, not `tests/fixtures/*.json` | The plan's location is not shipped, so LC-P1-03 and LC-P1-13 could not reuse them. Shipping also makes them hashable and byte-comparable and exercises a real `json.loads` path |
| Artifact paths are narrow (`dist/*.whl`), not negative globs | Satisfies the checklist's intent more strongly — only build outputs leave the runner — and the test accepts either form |
| A third artifact `source-archive` | Exercises the `git archive` row of the checklist. Extends the frozen contract rather than changing it |
| `scripts/*` exempt from T201 and UP017 | A CLI prints to the terminal; that is the correct mechanism. `datetime.UTC` needs 3.11+ and developer tooling must not break under whatever `python` is first on PATH. Confirmed by planting a probe in `src/` — both rules still fire there |
| `requires-python = ">=3.12,<3.13"` | Narrow for a library, correct for a pinned application with a 3.12 × 2 OS matrix |

## Not verified

These are declared, not assumed:

- **gitleaks' non-zero exit on a real leak.** No canary was planted, because that needs a branch. The configuration and its parsing are verified; the failure path is not.
- ~~The Linux gitleaks binary was never executed.~~ **RESOLVED since the first CI run.** `secret-scan` runs on `ubuntu-latest` and the log shows the Linux binary executing: `24 commits scanned, ~1.14 MB, no leaks found` on the `secret-scan` run for HEAD `ce15692`. (The previous commit's run scanned `23 commits, ~1.12 MB` — the scan covers the whole history, so these figures grow as the branch grows.) The SHA256 is still verified before execution. It remains true that the binary cannot run on the Windows developer machine.
- **Real browser rendering.** jsdom assertions are not a screenshot. Two distinct
  claims are often collapsed here, and they do not stand or fall together:
  - **The web quality gate on Ubuntu** — **verified.** `web-quality` runs on
    `ubuntu-latest`, installs dependencies, and passes typecheck, lint, test and build.
  - **Real browser rendering** — **still not verified.** No screenshot-level visual
    check has been performed; the suite asserts against jsdom, which is not a browser.
  - **A real browser smoke test on Windows** — **still not verified.** C-6 explicitly
    places this outside the scope of this work order.

  ~~Any platform other than Windows for the web baseline.~~ **Superseded as written.**
  The blanket statement was inaccurate once `web-quality` went green on Ubuntu: the
  web baseline *is* exercised on a non-Windows platform today. What remains unverified
  is narrower and is listed above — rendering fidelity, and the Windows browser smoke
  test — not "every non-Windows platform".
- **`gitleaks git` does not read the index**, so an uncommitted `git add -f` is not scanned. The window closes at commit; `--staged` closes it locally. Recorded in `CONTRIBUTING.md` §5.

## Open items carried forward

| Item | Blocks | Owner |
|---|---|---|
| Copyright ownership unresolved; **no `LICENSE` file and no rights granted** | Any claim of open-source licensing; LC-P1-14 | Project lead |
| `PyMuPDF` is AGPL/commercial dual-licensed and named by LC-P1-08 | LC-P1-08, and a future MIT release | Project lead |
| Five pnpm commands in the README suite skip rather than fail when Node is absent | Nothing on the current CI, where `web-quality` installs dependencies first | LC-P1-12 |

## Independent cross-review

An agent that had not participated in the implementation reviewed this branch under an
instruction to assume the work was wrong. It ran the full suite, then attacked it
with destructive verification in a copy outside the repository. It found **two blocking
issues, both of the same kind: work declared done that was not done.** Both are fixed
below. Its other findings are recorded whether fixed or not.

### B-1 — C-5 was not implemented, and the omission was not declared

C-5 is one of the eight binding rulings and requires `.gitattributes`. The file did not
exist, was not tracked, and was absent from the sdist. Three comments in the repository
described it as non-existent, and `CONTRIBUTY.md:40` was among them. **This evidence
document previously concluded "acceptance clauses are met" without mentioning C-5** —
the exact failure mode the project exists to prevent.

Added `.gitattributes`: `* text=auto eol=lf` with binary declarations, explicit
`*.ps1`/`*.cmd`/`*.bat` CRLF exceptions with the Windows PowerShell parser as the
reason, and lockfiles pinned to LF so a Windows checkout cannot manufacture apparent
`pnpm` or `uv` drift.

### B-2 — `.env.example` is a named Build deliverable and did not exist

`PHASE_1_WORKORDERS.md` LC-P1-01 lists it. The file was absent while `.gitignore`
carried an explicit `!.env.example` rule anticipating it. Written: it states plainly
that **Phase 1 reads no environment variable**, so the suite passes with none of them
set, and documents the names LC-P1-03 will introduce so they are settled before code
depends on them.

### D-1 — C-1 had only a proxy gate

The existing check flagged `paths-ignore` only when it mentioned a reference family.
Injecting `paths-ignore: ['**/*.md', 'docs/**']` into `python.yml` passed every test —
yet that is precisely the deadlock C-1 describes: GitHub reports a filtered check as
*expected*, not passed, so a documentation-only PR could never merge.

Added `test_no_workflow_filters_pull_request_at_all`, which parses the workflow YAML
structurally and forbids **any** `paths`/`paths-ignore`/`pull_request_target` filter.
All six jobs are required checks, so none may filter; a genuinely optional workflow must
be added to an explicit exemption list rather than relying on a filter looking harmless.

A related defect in the same area: `_lines_outside_exclusion_contexts` tested
`"exclude" in stripped`, but `"exclude" in "paths-ignore:"` is False, so the branch its
comment describes never ran.

### D-2 — C-4's negative assertion did not exist

`.gitleaks.toml` states that "the negative assertion lives in
tests/test_no_reference_leakage.py". It did not: `test_workflows_do_not_use_no_git_secret_scan`
reads the **workflow files**, never the configuration. Appending
`disabledRules = ["generic-api-key", "private-key"]` plus a blanket
`[[allowlists]] paths = ['_references.*', ...]` left **165 tests passing with zero
warnings** — reference source forced into the index would have been invisible to the
secret scan *and* to the path assertions. Doubly hidden, which is the one outcome C-4
exists to prevent.

Added `test_gitleaks_config_declares_no_path_allowlist`, which reads the config and
rejects any `[[allowlists]]` block or any non-comment line pairing a path key with a
reference family.

### D-3 — the cross-process determinism test varied nothing

`_replay_in_subprocess` launched the child with `-I`, which implies `-E` and therefore
ignores every `PYTHON*` variable — including the `PYTHONHASHSEED` the function exists
to vary and the `PYTHONIOENCODING` that makes byte comparison meaningful. Measured:

```
-I:  seed 0 -> hash 1472225801280241200   seed 0 again -> hash -3399221637839268906
     same-seed stable: False          enc: gbk
-s:  seed 0 -> hash -3368204716105132637  seed 0 again -> identical
     same-seed stable: True           enc: utf-8
```

Changed to `-s`, which still drops user site-packages. The conclusion that replay is
hash-seed independent now rests on a mechanism that actually varies. `SYSTEMROOT` was
also hardcoded to `C:\Windows` inside a test that runs on Ubuntu; it is now set
conditionally.

### D-4 — the `UnknownReason` closed set could be bypassed

`Unknown("unpriced")` constructed successfully, compared **equal** to
`Unknown(UnknownReason.UNPRICED)` with an equal hash, and then raised
`AttributeError` at serialisation. Every product construction site passes an enum
member, so nothing can reach it today — which is the argument for closing it now rather
than after LC-P1-03 builds budgets on top. `__post_init__` validation added, with a
test that also covers `None`, `0`, `1.0` and `object()`.

### Verified as sound, recorded so it is not re-litigated

- **Unknown cannot be folded to zero.** Attacked directly: `int`, `float`, `iter`, `len`,
  `json.dumps` all raise; `bool(Unknown)` is True so `u or 0` yields itself; `Known(0) ==
  Unknown` is False with different hashes; `usage_from_wire({"known": True})` yields
  Unknown rather than treating the bool as 1; `merge(Known(0), Unknown)` yields Unknown.
  This is the strongest part of the delivery.
- **C-2's gate is live.** Destructive checks: `packages` narrowed to
  `["src/labcairn/core"]` turns four tests red; deleting the `packages` line turns the
  build-backend test red; deleting either exclude list turns the sdist test red. The
  recursive-root contract holds and survives new subpackages.
- **Isolation asserts behaviour, not text** (C-8), and the positive controls are real:
  when a control file is absent four assertions go inert, and the scanners are
  self-tested.
- **The AST gate caught a real regression.** Moving `providers/` under `core/` broke its
  target path and it refused to pass with "the sweep proved nothing" — the anti-vacuous
  behaviour it was built for.
- All six action tags resolve on the GitHub API; the gitleaks SHA256 matches the
  published checksum for 8.30.1.

## Still open — not fixed, and not claimed as fixed

Resolved since the first draft of this document: the README's "open source" wording has been corrected to "under development, open-source licensing pending", the GitHub description and topics were updated to match, and the Linux gitleaks binary is now exercised by CI.

| Finding | Why it is open |
|---|---|
| The T07 overclaim detector has real holes: passive voice ("PDF parsing **is supported by** LabCairn"), "is capable of", "handles", "can", "has a built-in", "comes with", and Chinese "可以 / 能 / 用于 / 现可使用". `_QUALIFIER_RE` exempts a whole sentence when it contains `target`, `intended`, `future`, `目标`, `拟`, `将(?:会\|要)?`, so a qualifier can whitewash a claim. The 6 cases in `test_claim_detector_has_teeth` are all forms the regex already covered | A reliable bilingual capability-claim detector is a project in itself. Recording the holes is more useful than pretending the suite catches overclaims; the README suite is a floor, not a guarantee |
| `test_wheel_contains_no_reference_path` cannot currently fail: deleting the whole wheel exclude list leaves the suite green | The wheel is built from one package root, so the case is structurally unreachable today. The comment says "defensive only", which is honest |
| `test_upload_artifact_and_cache_steps_exclude_reference_paths` accepts any narrow path, while the checklist row says the exclusion applies "regardless" | Narrow paths satisfy the intent more strongly; recorded as a deviation, not a silent reinterpretation |
| `gitleaks git` does not read the index | Tool behaviour, not configuration. Window closes at commit |

## What is verified, and by whom

These are kept apart on purpose, because the first is not evidence for the second.

**Verified by the implementer, reproducible from this document.** Every command in
"Commands and their actual results" was run, and its output is quoted rather than
described. Every claim in "The two defects only a real runner could find" is backed by
a CI log. The destructive checks listed under the cross-review — narrowing the Hatchling
package root, deleting exclude lists, injecting a blanket gitleaks allowlist, injecting a
`paths-ignore` — each produced the failure it was supposed to. This establishes that the
gates fire.

**Verified independently.** The project-lead review read the repository and the CI runs
directly and returned CHANGES REQUESTED. At the commit it reviewed (`4658041`) it
independently confirmed 169 pytest on both platforms, 7 web tests, the artifact sizes and
the absence of a `LICENSE` file — that count is what was true then, not a current figure.
It found two blocking omissions and four stale documents the implementer had missed. Two
further review rounds followed, the second of which also found blocking omissions and
stale evidence links. All are recorded above with what was done about them.

**Not established by either.** That the isolation gate cannot be defeated by a future
edit — only that it is live today. That branch protection is enforced — the API
configuration is quoted, but no runtime proof is obtainable from a client that cannot
merge. That the README overclaim detector catches capability claims in general; it has
known holes, listed above.

## Verdict

No verdict is claimed here. The work order's acceptance clauses are met against the
evidence above, and the independent reviews that have run returned findings which are
all recorded and addressed or declared open. The decision to accept LC-P1-01 is the
project lead's, and the status board continues to read IN PROGRESS until they make it.

No runtime capability, licence grant or scientific validation is claimed by this work.
