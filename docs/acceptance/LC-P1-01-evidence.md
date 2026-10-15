# LC-P1-01 — Acceptance evidence

**Verdict requested:** `PASS` / `PASS WITH NOTES` / `BLOCKED` / `FAIL`  
**Branch:** `feat/lc-p1-01-baseline` · **Head:** `7408720` · **PR:** [#2](https://github.com/gg320324492-lgtm/labcairn/pull/2)  
**Base:** `main` @ `b526749` · **Date:** 2026-10-15  
**Scope:** LC-P1-01 as written in `docs/PHASE_1_WORKORDERS.md`, with the eight binding rulings in `docs/plans/LC-P1-01-approved-amendments.md`.

**This is an engineering baseline, not a product.** There is no CLI, no server, no database and no research feature. The Phase 1 deliverable — a researcher running a real task — remains entirely unbuilt, as it should at G1's first work order.

## Acceptance checklist

| Clause | Status | Evidence |
|---|---|---|
| Fresh clone, documented setup, on CI-supported OS | **PASS** | CI green on `ubuntu-latest` and `windows-latest`; run links below |
| Lint / type / test pass | **PASS** | ruff, ruff format, `mypy` strict, 166 pytest — locally and in CI |
| Quick-start claims no unimplemented command | **PASS** | `tests/test_readme_accuracy.py`, 17 tests, fail-closed both directions |
| Secret scan included | **PASS** | `.gitleaks.toml` + `security.yml`, git mode, green in CI |
| Lockfile consistency check included | **PASS** | `lockfiles.yml` green in CI |
| FakeProvider and fixtures run without paid APIs | **PASS** | 48 tests; socket and httpx patched to raise; suite passes under `env -u` with credential-shaped variables removed |
| Reference exclusion **verified, not asserted** | **PASS** | 97 tests; CI job `reference-exclusion` green on both platforms |
| No third-party source committed | **PASS** | 0 submodules; the sibling `labcairn-upstreams` is outside the tree and never referenced by CI |

## Commands and their actual results

Run locally on Windows 11, Python 3.12.13, uv 0.11.21, Node 24.16.0, pnpm 9.15.9.

```
uv sync --frozen              Checked 160 packages
uv run ruff check .           All checks passed!
uv run ruff format --check .  16 files already formatted
uv run mypy                   Success: no issues found in 16 source files
uv run pytest                 166 passed in 10.28s          (0 skipped)
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
  11 commits scanned, ~436 KB, no leaks, exit 0
```

The two `skip`s that existed after T05 are **gone**: `test_no_workflow_requires_an_upstream_checkout` and `test_upload_artifact_and_cache_steps_exclude_reference_paths` both pass now that `.github/workflows/` exists. They previously reported the CI half of the gate as *inert*, not passing.

## CI runs

All six required checks green. Six runs exist because each workflow triggers on both `push` and `pull_request`.

| Job | Run |
|---|---|
| `python-quality (ubuntu-latest)` | [38700736518/116308019833](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736518/job/116308019833) |
| `python-quality (windows-latest)` | [38700736518/116308020349](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736518/job/116308020349) |
| `web-quality` | [38700736662/116308020781](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736662/job/116308020781) |
| `reference-exclusion` | [38700736713/116308020795](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736713/job/116308020795) |
| `secret-scan` | [38700736775/116308020947](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736775/job/116308020947) |
| `lockfile-consistency` | [38700736685/116308020534](https://github.com/gg320324492-lgtm/labcairn/actions/runs/38700736685/job/116308020534) |

**Build artifacts** produced by `reference-exclusion`: `sdist` 337,972 B · `wheel` 26,684 B · `source-archive` 338,002 B.

## Required status checks — the C-1 verification

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

This is the exact failure C-8 and the exclusion checklist both predict will only appear on a real runner, and it is why `reference-exclusion` runs on both platforms rather than one.

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
- **The Linux gitleaks binary was never executed.** Downloaded, SHA256-verified, unpacked — it is a Linux ELF and cannot run on Windows.
- **Real browser rendering.** jsdom assertions are not a screenshot.
- **Any platform other than Windows for the web baseline.**
- **`gitleaks git` does not read the index**, so an uncommitted `git add -f` is not scanned. The window closes at commit; `--staged` closes it locally. Recorded in `CONTRIBUTING.md` §5.

## Open items carried forward

| Item | Blocks | Owner |
|---|---|---|
| Copyright ownership unresolved; **no `LICENSE` file and no rights granted** | Any claim of open-source licensing; LC-P1-14 | Project lead |
| `PyMuPDF` is AGPL/commercial dual-licensed and named by LC-P1-08 | LC-P1-08, and a future MIT release | Project lead |
| README calls the project "open source" in three places while stating no rights are granted | Nothing technically; it is a positioning judgement | Project lead |
| Five pnpm commands in the README suite skip rather than fail when Node is absent | Nothing on the current CI, where `web-quality` installs dependencies first | LC-P1-12 |

## Verdict

LC-P1-01's acceptance clauses are met, with two real defects found and fixed after the first CI run. The isolation promise is now enforced by tests and by GitHub rather than by a document. No runtime capability, licence grant or scientific validation is claimed by this work.
