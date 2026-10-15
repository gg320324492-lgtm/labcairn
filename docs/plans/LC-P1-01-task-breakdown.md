# LC-P1-01 — Public repository and reproducible engineering baseline

**Plan ID:** LC-P1-01-TB-v1.0
**Work order:** `docs/PHASE_1_WORKORDERS.md` → `LC-P1-01` (Block A, P0, gate G1 first item)
**Date:** 2026-10-15
**Status:** Plan only. Nothing in this document has been implemented.
**Precondition:** LC-P1-00 review passes (G0). This plan is not authorization to start.

---

## 0. How to read this document

This is an execution plan. It says what to build, in what order, and how to know each piece
is finished. It deliberately contains no product code, no CI file contents, and no
substitute for a decision that a human must make. Where the work order, an ADR and the
operating reality disagree, the disagreement is recorded in §11 as a conflict and is **not**
reconciled here.

Every "verification" line is a command or a test name that either passes or fails. If a
subtask cannot state one, the subtask is not ready to be assigned.

---

## 1. Goals and boundaries

### 1.1 What LC-P1-01 must produce (from the work order Build + Acceptance)

1. `src/` Python package with `pyproject.toml`, `uv.lock`, Python 3.12 CI.
2. `web/` React/TS/Vite project with a lockfile.
3. pytest / ruff / mypy, Vitest, GitHub Actions.
4. `.env.example`, `.gitignore`, docs, MIT license *once ownership cleared*; no credentials
   or research private data.
5. A **FakeProvider and deterministic demo fixtures that run without paid APIs**.
6. README that accurately marks incomplete features.
7. **The binding reference-exclusion checklist** from `docs/UPSTREAM_REFERENCES.md`
   §"Binding exclusion checklist (applies from LC-P1-01)" — see §4 of this plan.
8. The operating rule that configuration cannot close: *verify the repository root resolves
   to LabCairn before any Git operation, and treat a `git init` rooted anywhere above it as
   an incident.*

Acceptance is mechanical: fresh clone + documented setup on a CI-supported OS; lint/type/test
pass; quick-start does not claim unimplemented commands; secret scan and lockfile
consistency check included; **reference exclusion is verified, not asserted** —
`tests/test_no_reference_leakage.py` exists, passes, and its CI job runs on every pull
request.

### 1.2 Already done — removed from scope

- **`git init`.** Verified 2026-10-15: `git rev-parse --show-toplevel` in `E:\LabCairn`
  returns `E:/LabCairn`. Branch `main`, zero commits, 12 untracked files
  (`.gitignore`, `README.md`, 5 `docs/*.md`, 4 `docs/adr/*.md`, `scripts/checkout_upstreams.py`).
  This is the correct root — `E:/` holds ~19 further directories including
  `labcairn-upstreams`, `microbubble-agent`, `AI`, `ComfyUI`, `MATLAB`, `sci-software`.
  **No task in this plan runs `git init`, `git add -A`, or any other `git init`-family write
  except the explicit, enumerated commit in T01.**

### 1.3 Explicitly NOT in LC-P1-01

| Excluded | Belongs to | Note |
|---|---|---|
| Typed contracts: `Task`, `Run`, `Stage`, `Operation`, `Approval`, `SourceAnchor`, `EvidenceRecord`, `ArtifactReceipt`, `Checkpoint` | LC-P1-02 | LC-P1-01 ships no domain models. The package skeleton must be empty of them. |
| Real providers, budgets, `ProviderProbe`, capability caching | LC-P1-03 | LC-P1-01 ships only the *fake* and its seam. |
| Workspace roots, path guards, `allow/ask/deny` evaluation | LC-P1-04 | |
| SQLite, SQLAlchemy, Alembic, event store | LC-P1-05 | |
| PDF/CSV/XLSX ingestion fixtures | LC-P1-08 | LC-P1-01's "deterministic demo fixtures" means **scripted provider transcripts**, not scientific materials. See §6.2. |
| Typer CLI (`labcairn init`, `doctor`, …) | LC-P1-12 | Consequence: the README must document **no** `labcairn ...` command in LC-P1-01. See §8. |
| FastAPI / React UI feature screens | LC-P1-12 | LC-P1-01's `web/` is a build-and-test baseline only: a Vite app that renders a static placeholder and a Vitest suite that passes. |
| Playwright | LC-P1-12/13 | README lists Playwright under "Planned architecture"; LC-P1-01 must not install it. |

### 1.4 Adjacent-work-order boundary rules

- **LC-P1-00 continues.** `scripts/checkout_upstreams.py` and `docs/UPSTREAM_REFERENCES.md`
  are **read-only inputs** to LC-P1-01. No subtask edits them. If an exclusion requirement
  appears to need a change in `UPSTREAM_REFERENCES.md`, raise it; do not edit.
- **LC-P1-02/03 need `src/labcairn/core/`.** LC-P1-01 creates the directory tree so the
  explicit package list is real, but populates it only with the FakeProvider.
- **`benchmarks/` and `examples/`** appear in `docs/ARCHITECTURE.md`'s proposed layout and in
  LC-P1-13/14. LC-P1-01 creates neither. Empty directories are not deliverables.

---

## 2. Subtask breakdown

Twelve subtasks. Each states deliverables, dependencies, file ownership, the acceptance
clause it discharges, and its verification.

### File ownership map (this is the parallel contract)

A file with exactly one owner for the duration of LC-P1-01 is what makes parallel work safe.
If a task needs a file it does not own, it does not edit it — it raises the change.

| File / tree | Sole owner | Others |
|---|---|---|
| `.gitignore` | **T01** | read-only for all |
| `pyproject.toml`, `MANIFEST.in`, `.python-version`, `uv.lock`, `ruff`/`mypy`/`pytest` config | **T02** | read-only for all; changes route through T02 |
| `src/labcairn/__init__.py`, `src/labcairn/core/__init__.py` | **T02** | |
| `src/labcairn/core/**` (everything else) | **T08** | |
| `tests/conftest.py`, `tests/fixtures/` scaffolding | **T02** | later tests must be self-contained files |
| `tests/test_no_reference_leakage.py` | **T05** | |
| `tests/test_readme_commands.py` | **T07** | |
| `tests/unit/test_fake_provider_*.py` | **T09** | |
| `.github/workflows/**` | **T06** | T04/T05/T10 supply inputs, never workflow files |
| `.gitleaks.toml` | **T04** | |
| `.vscode/settings.json` | **T03** | |
| `web/**` | **T10** | |
| `README.md` | **T07** | T12's README paragraph folds into T07 |
| `CONTRIBUTING.md`, `scripts/check_repo_root.py` | **T11** | |
| `LICENSE` placeholder artifact | **T12** | |
| `scripts/checkout_upstreams.py`, `docs/UPSTREAM_REFERENCES.md`, `docs/adr/*` | **nobody — read-only** | |

---

### T01 — Repository hygiene, ignore-glob widening, first commit

**Deliverables**
- `.gitignore` widened for the three reference globs in a **case-variant and
  path-depth-robust** form (see §3.6).
- `.gitignore` decision for the leftover `tmp/` directory.
- One commit containing the current 12 files, on branch `main`, message referencing LC-P1-00.

**Depends on:** nothing. **Must run first.**

**Parallel**: none. Everything else lands on top of it.

**Acceptance discharged**
- Work order: *".gitignore, docs, MIT license once ownership cleared; no credentials or
  research private data."*
- `UPSTREAM_REFERENCES.md` §"Two known limits" #2: *".gitignore is weaker than it appears …
  case-sensitive on case-sensitive platforms … Every exclusion above is therefore stated as
  a glob covering the relevant case variants, and must be verified on a case-sensitive
  runner."*
- Work order operating rule: *verify the repository root resolves to LabCairn before any Git
  operation* — partially; T11 completes it.

**Verification**
```
git -C E:/LabCairn rev-parse --show-toplevel      # must print E:/LabCairn
git -C E:/LabCairn ls-files -o --exclude-standard # exactly the 12 known files
git -C E:/LabCairn log --oneline                  # exactly one commit, LC-P1-00 subject
```
Plus a throwaway check that a directory named `_References/` is ignored on this machine
(and note in the commit body that this proves nothing on Linux — T05's job does that).

**Open decision D-1 — `tmp/`.** `tmp/lcprobe/fakerepo/_references/` and
`tmp/lcprobe/fakerepo2/src/` are leftover probe directories from LC-P1-00's ignore-rule
verification. They are empty, so Git does not see them — which means *the hazard is latent*:
the first file anyone drops into `tmp/` becomes a tracked file, and `tmp/lcprobe/fakerepo/_references/`
would then be a reference path inside the repository. Options: (a) delete both probe
directories; (b) add `tmp/` to `.gitignore`. **This plan does not decide**; another agent may
still own that scratch space.

---

### T02 — Python baseline: packaging, toolchain pin, lockfile, test scaffolding

**Deliverables**
- `pyproject.toml`: build backend, explicit package list, **auto-discovery disabled**,
  `requires-python` pinned to 3.12, ruff / mypy / pytest configuration, dev dependency group.
- `MANIFEST.in` with `prune` for each of `_references*`, `.upstreams*`, `labcairn-upstreams*`
  **if and only if** the setuptools backend is chosen (see D-2).
- `.python-version` containing `3.12`.
- `uv.lock`, generated on this machine.
- `src/labcairn/__init__.py`, `src/labcairn/core/__init__.py`. No domain models.
- `tests/conftest.py` — shared fixtures only: repository-root discovery, isolated temp dir,
  frozen clock.
- `pytest` marker declarations, **complete up front**: `unit`, `integration`, `e2e`,
  `reference_exclusion`, `requires_network`, `requires_provider`.

**Depends on**: T01.

**Parallel**: serial. **Exclusive owner of `pyproject.toml` for the whole work order.**

**Acceptance discharged**
- Work order Build: *"`src/` Python package with `pyproject.toml`, `uv.lock`, Python 3.12 CI;
  pytest/ruff/mypy"*.
- Exclusion checklist row 1: *explicit `["src/labcairn"]` package list, auto-discovery
  disabled, sdist/wheel exclusions for the three reference paths*.
- Exclusion checklist row 2: `MANIFEST.in` `prune` if setuptools.

**Verification**
```
uv python install 3.12 && uv python pin 3.12
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --collect-only -q      # must collect 0 tests, exit 0
uv build                            # produces dist/*.whl dist/*.tar.gz
uv run python -c "import labcairn, sys; print(sys.version)"   # 3.12.x
```
Plus: `uv lock --check` exits 0 (lockfile is in sync with `pyproject.toml`).

**Decisions required before starting**

- **D-2 — build backend.** The checklist is written in setuptools vocabulary (`MANIFEST.in
  prune`, explicit package list). Recommendation: **setuptools**, because the checklist's
  rows 1–2 only make literal sense there, and `uv build` drives it. If hatchling is chosen
  instead, `MANIFEST.in` is meaningless and rows 1–2 must be re-expressed as
  `only-include`/`exclude`, which is a deviation from the checklist text and must be recorded.
- **D-3 — `["src/labcairn"]` is ambiguous and, read literally, wrong.** See §11 conflict **C-2**.
  This is the highest-risk item in T02. Do not start T02 until it is settled.
- **D-4 — `requires-python`.** ADR-0002's `type UsageValue = Known[int] | Unknown` is
  PEP-695 syntax valid **only on 3.12+**, so `>=3.12` is a floor, not a preference.
  Open: `<3.13` (literal reading of "Python 3.12") vs `<3.14`. Recommendation: `>=3.12,<3.13`
  for LC-P1-01 so the CI matrix has exactly one interpreter to reason about; revisit at LC-P1-14.

---

### T03 — IDE and indexer configuration

**Deliverables**
- `.vscode/settings.json` with `search.exclude` and `files.exclude` entries for the three
  reference glob families, in both `**/pattern/**` and `**/pattern` form.
- A short section in `CONTRIBUTING.md` **drafted by T03 and merged by T11** (T03 does not
  own `CONTRIBUTING.md`) recording: the indexer ingestion root is `src/` and `docs/` only;
  using the repository root as an ingestion root is prohibited.

**Depends on**: none (can start immediately after T01).

**Parallel**: fully parallel with T02, T04, T08, T10, T11, T12. Touches no file another
task owns.

**Acceptance discharged**
- Exclusion checklist row 8: *"`search.exclude` and `files.exclude` for the reference paths.
  **The ingestion root of any indexer is restricted to `src/` and `docs/`; using the
  repository root as the ingestion root is prohibited.**"*

**Verification**
- `tests/test_no_reference_leakage.py` (T05) reads `.vscode/settings.json` and asserts the
  three globs appear in both keys, case-variant forms included. This is a JSON assertion,
  not a screenshot.
- Human review: `.vscode/settings.json` must not be the *only* record of the ingestion-root
  rule — the rule also lives in `CONTRIBUTING.md`, because `.vscode/` is not committed by
  every contributor.

---

### T04 — Secret scan configuration (git mode only)

**Deliverables**
- `.gitleaks.toml` (or equivalent config for the chosen scanner) at repository root.
- The scan invocation, committed as a **CI job body authored by T06 from T04's parameters**
  — T04 does not write workflow files.
- A written statement of why `--no-git` is prohibited, placed in `CONTRIBUTING.md`
  (drafted by T04, merged by T11).

**Depends on**: T01.

**Parallel**: fully parallel with T02, T03, T08, T10, T12.

**Acceptance discharged**
- Work order Acceptance: *"secret scan and lockfile consistency check included."*
- Exclusion checklist row 6: *"Run in **git mode**, scanning tracked files only. Do **not**
  use `--no-git` whole-disk scanning … Add the reference paths to the scan allowlist while
  keeping LabCairn's own tracked files fully covered."*

**Verification**
- Local dry run must show it scans the working tree's tracked files and nothing else.
- T05 adds a negative assertion: `tests/test_no_reference_leakage.py::test_workflows_do_not_use_no_git_secret_scan`
  parses every workflow and fails if any `run:` step contains `--no-git`.
- A planted canary secret in a scratch commit on a throwaway branch must be caught; the
  canary must be removed before T01's commit or, better, created only on a disposable branch
  that is deleted. **Do not commit a canary on `main`.**

**Note on the allowlist (see §11 conflict C-4).** In git mode the reference clones are not in
the repository at all, so a reference-path allowlist is close to inert — it defends against a
reference directory that *was* committed by mistake, not against the sibling clone. That is
still worth having, but T04 should say so plainly in the config comment rather than implying
the allowlist is what protects the clones. It does not; T11's operating procedure does.

---

### T05 — `tests/test_no_reference_leakage.py` (hard acceptance gate)

**Deliverables** — one file, `tests/test_no_reference_leakage.py`, containing at least:

| Test | Asserts |
|---|---|
| `test_git_ls_files_contains_no_reference_path` | no path from `git ls-files` matches `_references*`, `.upstreams*`, `labcairn-upstreams*` in any case variant |
| `test_built_sdist_contains_no_reference_path` | member names of `dist/*.tar.gz` (and `.zip`) contain none |
| `test_built_wheel_contains_no_reference_path` | member names of `dist/*.whl` contain none |
| `test_wheel_contains_all_subpackages` | **the C-2 regression**: `labcairn/core/` is present in the wheel |
| `test_scripts_not_shipped_in_wheel` | `scripts/checkout_upstreams.py` is not a wheel member |
| `test_vscode_excludes_reference_paths` | T03's config, both keys, case variants |
| `test_workflows_declare_paths_ignore_for_reference_paths` | every workflow's `on.push`/`on.pull_request` carry the globs |
| `test_upload_artifact_and_cache_paths_exclude_reference_paths` | every `actions/upload-artifact` / `actions/cache` `path:` excludes them |
| `test_workflows_do_not_require_upstream_checkouts` | no workflow step references `labcairn-upstreams`, `../labcairn-upstreams`, or `checkout_upstreams.py` outside an exclusion context — **this is the "external contributor has no clone" gate** |
| `test_workflows_do_not_use_no_git_secret_scan` | see T04 |
| `test_checkout_upstreams_script_rejects_in_repo_destination` | exercises the existing guard at `scripts/checkout_upstreams.py:76` (`dest == ROOT or ROOT in dest.parents`) without cloning anything |
| `test_gitignore_ignores_reference_paths_case_variants` | **behavioural**, via `git check-ignore` against paths created in a temp dir inside the repo — never by matching `.gitignore` text |

**Depends on**: T02 (build config exists so `uv build` works). **T05 may be written in
parallel with T06** because the artifact paths, artifact names and job ids are **frozen in
§3 of this plan** — if either side deviates from the frozen contract, they serialize instead.

**Parallel**: parallel with T03, T04, T07, T08, T09. **Not** parallel with T02.

**Acceptance discharged**
- Work order Acceptance, verbatim: *"Reference exclusion is **verified, not asserted**:
  `tests/test_no_reference_leakage.py` exists and passes, checking that both `git ls-files`
  and the member names of the built sdist and wheel contain no reference path, and the CI
  job asserting this runs on every pull request."*
- Exclusion checklist rows 3, 4, 5, 8 (workflow side).

**Verification**
```
uv run pytest tests/test_no_reference_leakage.py -v
# must fail if you deliberately `git add -f _references/probe.txt` in a scratch commit —
# do this on a disposable branch only, never on main.
```

---

### T06 — GitHub Actions

**Deliverables** — `.github/workflows/`, **all files owned solely by T06**:

| File | Jobs | Runner |
|---|---|---|
| `python.yml` | `python-quality` — ruff check, ruff format --check, mypy, pytest | `ubuntu-latest` **and** `windows-latest` |
| `web.yml` | `web-quality` — install, lint, typecheck, vitest run | `ubuntu-latest` |
| `reference-exclusion.yml` | `reference-exclusion` — runs `tests/test_no_reference_leakage.py` after `uv build`; uploads sdist/wheel as artifacts | `ubuntu-latest` |
| `security.yml` | `secret-scan` (gitleaks, **git mode**, `fetch-depth: 0`) | `ubuntu-latest` |
| `lockfiles.yml` | `lockfile-consistency` — `uv lock --check`; `pnpm install --frozen-lockfile` | `ubuntu-latest` |

Every workflow: `on.push.paths-ignore` and `on.pull_request.paths-ignore` for the three
reference glob families (see §11 conflict **C-1** before implementing), and every
`actions/upload-artifact` / `actions/cache` `path:` excludes them.

**Depends on**: T02 (uv), T04 (secret-scan parameters), T05 (job body), T10 (pnpm scripts).

**Parallel**: serial, after its dependencies. **Sole owner of `.github/workflows/**`.**

**Acceptance discharged**
- Work order Build: *"GitHub Actions"*, *"Python 3.12 CI"*.
- Work order Acceptance: *"fresh clone and documented setup on CI-supported OS … secret scan
  and lockfile consistency check included."*
- Exclusion checklist rows 3, 4, 6, 9.

**Verification**
- Push to a scratch branch with a deliberately reference-shaped path and confirm CI is green
  (exclusion works) and that `reference-exclusion` is a **required** status check in branch
  protection.
- Run the whole suite locally with the same commands the workflows use, before pushing.
- Assert no workflow references `E:\labcairn-upstreams` or `../labcairn-upstreams`
  (T05's `test_workflows_do_not_require_upstream_checkouts`).

**Open decision D-5 — the CI OS set.** The work order says "CI-supported OS" without naming
it; `docs/PHASE_1_WORKORDERS.md` §Out of scope defers "Real Windows smoke later in Phase 1"
and `LC-P1-01` Acceptance says *"Real Windows smoke later in Phase 1"* — but the development
machine is Windows, and §5's case-sensitivity finding is *only* reproducible on Linux.
Recommendation: **required** on `ubuntu-latest`; add `windows-latest` to `python-quality` only
as a cheap early signal. Needs sign-off; it is a cost decision, not a technical one.

---

### T07 — README accuracy

**Deliverables**
- `tests/test_readme_commands.py` — the mechanical guarantee (below).
- `README.md` edits, if any. **T07 is the sole owner of `README.md` for LC-P1-01.**
  T12's license paragraph is folded into T07's edit window.
- If a `docs/` page gains commands, the same test covers `docs/*.md`.

**Depends on**: T02 (dev tools must exist for the test to be meaningful); T12 (license text).

**Parallel**: parallel with T03, T04, T05, T08, T09.

**The mechanical rule.** The test parses every fenced code block and every inline code span
in `README.md` and `docs/*.md`, extracts tokens matching a command grammar, and classifies
each one:

| Command shape | Resolved against | Fails if |
|---|---|---|
| `uv run <script>` / `[project.scripts]` name | `pyproject.toml` | not declared, or declared entry point does not import |
| `pytest …` / `ruff …` / `mypy …` / `uv lock …` | `pyproject.toml` dependency group | tool not a declared dev dependency |
| `pnpm <script>` | `web/package.json` `scripts` | script key absent |
| `npm …` | — | **always fails**, no npm in this project |
| `python scripts/<file>.py` | filesystem | file absent |
| anything else | an explicit allowlist in the test file | **fails closed**, printing the unclassified token |

The default is *unclassified ⇒ fail*. Adding a command to the README without adding its
target fails CI.

Current state: `README.md` contains **no** commands and **no** code fences. The test starts
green and is a forward guard. That is the point — it is cheap now and expensive later.

A second assertion in the same file: the README must carry a status marker, and must **not**
contain the words/claims for any LC-P1-12+ surface (`labcairn init`, `labcairn doctor`,
`labcairn task`, FastAPI routes, UI screenshots). LC-P1-01 ships no CLI and no UI.

**Acceptance discharged**
- Work order Acceptance, verbatim: *"quick-start does not claim unimplemented commands"* and
  *"README must accurately mark incomplete features"*.

**Verification**
```
uv run pytest tests/test_readme_commands.py -v
# mutate a copy of README with "pnpm dev" in a fenced block → must fail
```

---

### T08 — FakeProvider: interface boundary + scripted transcripts

**Deliverables**
- `src/labcairn/core/providers/fake.py` — the deterministic fake.
- `src/labcairn/core/providers/__init__.py` — the `ModelProvider` seam ADR-0002 §A3 requires
  ("the contracts below are deliberately shaped so a hand-rolled adapter can be dropped in
  behind `ModelProvider` without changing callers").
- `src/labcairn/core/usage.py` — the **minimal** `UsageValue` / `Known` / `Unknown` /
  `UnknownReason` value types. See §11 conflict **C-3**.
- `tests/fixtures/fake_provider/*.json` — scripted transcripts.

**Depends on**: T02 (directory tree, packaging).

**Parallel**: parallel with T03, T04, T05, T10, T11, T12. **Sole owner of
`src/labcairn/core/**` beyond the two `__init__.py` files T02 created.**

**Acceptance discharged**
- Work order Build, verbatim: *"A FakeProvider and deterministic demo fixtures must run
  without paid APIs."*
- ADR-0002 §"LabCairn's own contracts" items 1 (`UsageValue`) and 4 (`CapabilityOutcome`),
  insofar as LC-P1-01 must *demonstrate* them (see §6).

**Verification** — in T09; T08 ships no tests of its own beyond an import smoke.

---

### T09 — Determinism and truthfulness tests

**Deliverables** — `tests/unit/`:

| Test | Asserts | Guards |
|---|---|---|
| `test_provider_omitting_usage_field_yields_unknown_not_zero` | a transcript whose response has **no** `usage` block ⇒ `Unknown(ProviderOmitted)`; a transcript with `"usage": {}` ⇒ **still** `Unknown`, never `Known(0)`; a transcript with `"usage": {"input_tokens": 0}` ⇒ `Known(0)` | ADR-0002's binding test name, verbatim. The opposite of upstream's `test_usage_unknown_provider` (`tests/test_usage_limits.py:1162`) which asserts an empty extract equals all-zero usage. |
| `test_usage_value_preserves_distinguishes_zero_from_unknown` | `Known(0) != Unknown(...)`; `Unknown` has no `__int__` | ADR-0002 |
| `test_usage_merge_is_not_sum_when_any_unknown` | `merge(Known(5), Unknown(...))` is `Unknown`, not `Known(5)` | ADR-0002 |
| `test_fake_provider_transcript_run_is_byte_identical_across_runs` | run the same transcript twice in one process and in two subprocesses; the recorded transcript digest and all rendered output are byte-identical | §6.3 |
| `test_fake_provider_opens_no_socket` | `socket.socket` monkeypatched to raise; the full transcript still runs | *"without paid APIs"* is an assertion, not a claim |
| `test_fake_provider_makes_no_outbound_request` | `httpx`/`requests` transport constructors patched to raise | same |
| `test_fixtures_are_deterministic_by_construction` | grep-level assertion: no fixture module imports `random`, `uuid`, `secrets`, or calls `datetime.now` / `time.time` outside the injected clock | §6.3 |

**Depends on**: T08.

**Parallel**: after T08, parallel with T05 and T07.

**Acceptance discharged**
- Work order Build: *"run without paid APIs"*.
- ADR-0002 §Contracts "Usage truthfulness" (the first three test names are verbatim from the ADR).
- ADR-0002 §Risk "Probe ≠ production" is *not* in scope for LC-P1-01 — no probes exist yet.

**Verification**
```
uv run pytest tests/unit -v
uv run pytest tests/unit -p no:cacheprovider -q   # twice, compare output hashes
```

---

### T10 — Web baseline

**Deliverables**
- `web/`: Vite + React + TypeScript, `package.json` with `packageManager: "pnpm@9.15.9"`,
  `pnpm-lock.yaml`, `tsconfig.json` (strict), ESLint + Prettier, Vitest config, one passing
  test, one component rendering a static "Phase 1 under construction" placeholder.
- Scripts in `package.json`: `dev`, `build`, `typecheck`, `lint`, `test`.

**Depends on**: none beyond T01.

**Parallel**: fully parallel with T02, T03, T04, T08, T11, T12. **Sole owner of `web/**`.**
It writes `pnpm-lock.yaml`, which nothing else touches, and reads `pyproject.toml` never.

**Acceptance discharged**
- Work order Build: *"`web/` React/TS/Vite project with lockfile … Vitest."*

**Verification**
```
cd web && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm test && pnpm build
git -C E:/LabCairn check-ignore -v web/node_modules web/dist
```
`node_modules/` and `web/dist/` are already in `.gitignore` (verified present, lines 16–17).

**Risk (see §10).** Node v24.16.0 with pnpm 9.15.9 is an unusually new Node against an older
package manager. If `pnpm install` misbehaves, escalate before pinning a different Node —
pinning Node to satisfy pnpm has second-order effects on every later work order.

---

### T11 — Operating procedure: repository-root discipline

**Deliverables**
- `CONTRIBUTING.md`, merging sections drafted by T03 (indexer ingestion root), T04 (secret
  scan git-mode rule) and T06 (release archiving).
- `scripts/check_repo_root.py` — **read-only**; resolves the repository root and exits
  non-zero unless it is the LabCairn root. **It performs no Git write operation of any kind.**
  `subprocess` use, if any, must be limited to `git rev-parse`.

**Depends on**: T01. Sections from T03/T04/T06 arrive later.

**Parallel**: parallel with T02, T03, T04, T08, T10, T12. **Sole owner of
`scripts/check_repo_root.py` and `CONTRIBUTING.md`.** T11 may **not** edit
`.github/workflows/**` even though the CI repo-root assertion duplicates its logic — the
duplication is deliberate and the workflow step must carry a comment pointing here.

**Acceptance discharged**
- Work order, verbatim: *"the operating rule that closes what configuration cannot:
  **verify the repository root resolves to LabCairn before any Git operation, and treat a
  `git init` rooted anywhere above it as an incident.**"*
- `UPSTREAM_REFERENCES.md` §"Two known limits" #1, called there *"the highest-severity
  item … **No in-repository configuration can fix this.**"*

**Verification**
```
python scripts/check_repo_root.py                      # exit 0, prints the root
cd /e && python E:/LabCairn/scripts/check_repo_root.py # must exit non-zero — read-only, safe
```
Plus the CI-side duplicate in `python.yml`:
`test "$(git rev-parse --show-toplevel)" = "$GITHUB_WORKSPACE"` and
`test "$(basename "$(git rev-parse --show-toplevel)")" = "LabCairn"`.

**Deliberately not in this task.** There is no hook that can prevent `git init` in `E:/`.
`.git/hooks/` is local-only and not cloned. Pre-commit hooks are not installed by this plan.
The rule is a documented, auditable procedure plus the CI assertion; stating otherwise would
repeat the failure mode `UPSTREAM_REFERENCES.md` diagnoses.

---

### T12 — LICENSE placeholder

**Deliverables**: see §9. One file whose name cannot be mistaken for a license, plus a
README paragraph (folded into T07's edit).

**Depends on**: none for the file; the README paragraph joins T07.

**Parallel**: parallel with everything except T07 (README).

**Verification**
```
# The artifact must NOT be named LICENSE.
git -C E:/LabCairn ls-files | grep -i '^LICENSE$' && echo "FAIL: a real LICENSE was created"
```

---

## 3. Exclusion checklist → artifact mapping

Every row of `docs/UPSTREAM_REFERENCES.md` §"Binding exclusion checklist (applies from
LC-P1-01)". Reference paths are, per that document, the globs `_references*`, `.upstreams*`,
`labcairn-upstreams*`. All case variants are included everywhere below.

| # | Checklist row | Artifact | Owner | Verification |
|---|---|---|---|---|
| 1 | `pyproject.toml`: explicit `["src/labcairn"]`, **auto-discovery disabled**, sdist+wheel exclusions | `pyproject.toml` (`[tool.setuptools]`, `[tool.setuptools.packages]`, `exclude`/`MANIFEST.in`) | T02 | `tests/test_no_reference_leakage.py::test_built_{sdist,wheel}_contains_no_reference_path`; `test_wheel_contains_all_subpackages` |
| 2 | `MANIFEST.in` `prune` (if setuptools) | `MANIFEST.in` | T02 | T05 asserts its presence iff the backend is setuptools |
| 3 | workflows `paths-ignore` on push **and** pull_request | `.github/workflows/*.yml` | T06 | `test_workflows_declare_paths_ignore_for_reference_paths` |
| 4 | same exclusion on every `upload-artifact` and `cache` `path:` | same | T06 | `test_upload_artifact_and_cache_paths_exclude_reference_paths` |
| 5 | dedicated CI job asserting `git ls-files` has no reference path | `reference-exclusion.yml` | T06 | required status check; T05's first test |
| 6 | secret scan, **git mode**, never `--no-git`, reference allowlist | `.gitleaks.toml` + `security.yml` | T04 → T06 | `test_workflows_do_not_use_no_git_secret_scan`; a planted-canary run on a scratch branch |
| 7 | `tests/test_no_reference_leakage.py` — `git ls-files` **and** sdist/wheel member names | `tests/test_no_reference_leakage.py` | T05 | the file itself |
| 8 | `.vscode/settings.json` `search.exclude` / `files.exclude`; indexer ingestion root = `src/` + `docs/` only | `.vscode/settings.json` + `CONTRIBUTING.md` | T03 → T11 | `test_vscode_excludes_reference_paths`; ingestion-root rule asserted in `CONTRIBUTING.md` prose and reviewed by a human |
| 9 | release archiving via `git archive` or build artifacts only; `zip -r` over the working tree prohibited | `CONTRIBUTING.md` §Release | T11 | `reference-exclusion.yml` produces an archive with `git archive` and asserts its member list contains no reference path; no workflow step contains `zip -r` |

### 3.1 Frozen inter-task contract (this is what allows T05 ∥ T06)

T05 and T06 write different files but must agree on:

- sdist/wheel land in `dist/` at the repository root;
- the exclusion job id is `reference-exclusion`;
- the job uploads artifacts named `sdist` and `wheel`;
- every workflow's exclusion globs use the same three families.

If either task needs to change one of these, **stop and serialize** — do not let them drift.

### 3.2 Glob forms to use, per surface

- **`.gitignore`**: `[_]...`-style case-pair globs. `*` rather than a trailing `/`, because
  `labcairn-upstreams*` (the checklist's own form) also covers a stray *file* of that name.
  Anchor with a leading `/` only if root-only matching is intended — **it is not**, since
  T05's fixtures create reference-shaped directories in subpaths.
- **GitHub Actions `paths-ignore`**: `**/_references*/**`, `**/.upstreams*/**`,
  `**/labcairn-upstreams*/**` — Actions globs need the `**/` prefix to match at depth.
- **`.vscode` `search.exclude`/`files.exclude`**: same `**/` form.
- **`exclude` in packaging**: match on path components, and verify by reading the built
  artifact, not by reading the config.

### 3.3 What the sibling-directory hazard is and is not

`E:/` contains ~19 further directories (verified 2026-10-15: `AI`, `ComfyUI`, `MATLAB`,
`Micro-Nano-Bubble-Technology-Lab`, `microbubble-agent`, `sci-software`, `labcairn-upstreams`,
`workbench-backups`, …). `.gitignore` says nothing about them. If `git init` is ever run at
`E:/`, every one becomes candidate tracked content.

**No repository configuration prevents this.** Three layers, none sufficient alone:
1. **T01** — correct root already established; `.gitignore` widened.
2. **T11** — `scripts/check_repo_root.py` (read-only) + a documented procedure in
   `CONTRIBUTING.md` that treats a wrong-root `git init` as an incident.
3. **T06** — a CI assertion that the checkout root is `LabCairn` and equals the workspace.
4. **T05** — `test_checkout_upstreams_script_rejects_in_repo_destination` keeps the one
   automated guard that does exist (inside the repo) honest.

State the residual risk honestly in `CONTRIBUTING.md`: a local `git init` at `E:/` is
**detected**, not prevented.

### 3.4 Cross-platform case sensitivity

Local `core.ignorecase=true` on Windows; Linux CI runs case-sensitive. A glob matching
`LabCairn-Upstreams/` locally will not match on CI. Consequences:
- Every exclusion glob must be case-variant-complete (see §3.2).
- **The authoritative verification is T05 running on `ubuntu-latest`, not on the Windows
  dev box.** A green local run proves nothing about case behaviour.
- The exclusion test must construct reference-shaped directories in **several case variants**
  (`_references`, `_References`, `_REFERENCES`, `.upstreams`, `.Upstreams`, …) in a temp
  directory inside a disposable clone — not in the real working tree.

---

## 4. Toolchain and environment

### 4.1 Python

- System `python` is **3.10.11** and is not on the critical path. Python **3.12 is not on
  PATH**. uv fetches it: `uv python install 3.12`, then `uv python pin 3.12` writes
  `.python-version`, which **must be committed** (it is not in `.gitignore`).
- `requires-python` in `pyproject.toml` must match `.python-version` exactly (see D-4).
- **Never invoke the system `python` for the project.** Every command goes through
  `uv run` / `uv sync`. A bare `python -m pytest` will silently use 3.10 and fail on
  ADR-0002's PEP-695 `type` statement — which is, conveniently, an early and loud signal.
- `scripts/checkout_upstreams.py` has a `#!/usr/bin/env python3` shebang and uses only the
  stdlib; running it under 3.10 is fine. Do **not** run it from CI.

### 4.2 Lockfiles

| | Python | Frontend |
|---|---|---|
| Generate | `uv lock` | `pnpm install` (writes `pnpm-lock.yaml`) |
| CI check | `uv lock --check` — exits non-zero if the lock is stale | `pnpm install --frozen-lockfile` — fails if `package.json` and the lock disagree |
| Dev check | same command, run locally before pushing | same |
| Platform dependence | uv resolves universally; the same lockfile serves Linux and Windows | pnpm lockfile is platform-independent |

Both checks live in their own job (`lockfiles.yml`) so a stale lockfile names itself in the
CI UI instead of surfacing as an unrelated install failure.

### 4.3 Local vs CI differences that must be verified on **both**

| Concern | Windows (dev) | Linux (CI) | Where |
|---|---|---|---|
| Ignore case behaviour | `core.ignorecase=true` | case-sensitive | T05 on CI is authoritative |
| Path separators in packaging members | `\` | `/` | T05 asserts POSIX `/` in wheel/sdist members — do the member-name check on Linux |
| `.vscode` settings | native | not used | T05 parses the JSON, not the editor |
| Symlink / junction behaviour | junctions | symlinks | *out of LC-P1-01 scope* (LC-P1-04) |
| Line endings | CRLF default | LF | decide explicitly (`.gitattributes`) — **see §11 C-5** |
| `pnpm install` on Node 24 | native | same Node version must be pinned in CI | T10 risk |

Everything in T05 must pass on **both** `ubuntu-latest` and `windows-latest`, because
`python-quality` runs the full pytest suite on both.

---

## 5. FakeProvider and deterministic fixtures

### 5.1 Interface boundary

The fake must satisfy **only what ADR-0002 requires of a provider**, and nothing LC-P1-03
will later have to unpick:

- **Seam, not implementation.** `src/labcairn/core/providers/__init__.py` defines the
  protocol. ADR-0002 §A3: the contracts are *"deliberately shaped so a hand-rolled adapter
  can be dropped in behind `ModelProvider` without changing callers."* LC-P1-01 ships the
  protocol and one fake implementation. It does **not** ship HTTP, retries, or streaming.
- **`UsageValue`, not `int`.** `src/labcairn/core/usage.py`:
  `Known(value) | Unknown(reason)` with `UnknownReason ∈ {ProviderOmitted, ExtractionFailed,
  NotApplicable, Unpriced}` and a `merge()` that returns `Unknown` if either side is unknown.
  `Unknown` deliberately has **no `__int__`**, so `sum()` over a list containing one raises
  `TypeError` at the call site instead of producing a number. This is the friction ADR-0002
  §Risks calls "the entire point of the work order" — keep it.
- **`CapabilityOutcome`-shaped gate.** LC-P1-01 ships the *enum shape only if* §11 C-3 is
  resolved that way; otherwise the fake returns a plain transcript and the capability gate
  arrives with LC-P1-03. **Default recommendation: do not pre-build `ProviderCapabilities`
  in LC-P1-01** — it has no probe to feed it and would be an untested stub.
- **No network, structurally.** The fake reads transcripts from disk. It does not import
  `httpx`, `openai`, `anthropic`, or `requests`.

### 5.2 Determinism rules (make these testable, not aspirational)

| Rule | Mechanism | Enforced by |
|---|---|---|
| No randomness | Prefer no RNG at all. If one is unavoidable, a single seeded `random.Random(<constant>)` per fixture module | `test_fixtures_are_deterministic_by_construction` |
| No wall clock | An injected `Clock` fixture pinned to a constant (e.g. `2026-01-01T00:00:00Z`); `datetime.now()` banned in `src/labcairn/core/` | T05's grep-level test + `ruff` (`DTZ` rules if enabled) |
| No `uuid4()` | UUIDs derive from the transcript, or are a seeded/derived sequence | same |
| No hash-order dependence | Every emitted mapping is built from sorted keys | T09 byte-identity test |
| No ambient environment | Fixtures must not read `$HOME`, locale, or cwd | T09 subprocess test with a scrubbed env |
| Reproducible across processes | Same transcript ⇒ same output bytes in a fresh interpreter | `test_fake_provider_transcript_run_is_byte_identical_across_runs` |
| **Do not add `pytest-randomly`** | A random-order plugin reintroduces nondeterminism for no benefit here | code review at T02 |

### 5.3 Fixture organisation

```
tests/fixtures/fake_provider/
  README.md            # what these are, and that scientific-material fixtures are LC-P1-08's
  usage_present.json   # response WITH a populated usage block      -> Known
  usage_zero.json      # response WITH "usage": {"input_tokens": 0} -> Known(0)
  usage_absent.json    # response with NO usage block at all        -> Unknown(ProviderOmitted)
  usage_empty.json     # response with "usage": {}                  -> Unknown(ProviderOmitted), NOT Known(0)
  tool_call_ok.json
  tool_call_ignored.json   # provider ignores `tools` and answers in prose
  README.md must state: "LC-P1-01 ships provider transcripts only. PDF/CSV/XLSX source
  material, locator fixtures and evidence fixtures belong to LC-P1-08 / LC-P1-09."
```

That last line is a scope boundary, not a placeholder. It stops T10–T14 from "helpfully"
adding scientific fixtures that then look like LC-P1-08 deliverables.

### 5.4 The ADR-0002 demonstration test

`test_provider_omitting_usage_field_yields_unknown_not_zero` is the required demonstration
and it is the sharpest available contrast with upstream:

| Input | Upstream pydantic-ai result | LabCairn required result |
|---|---|---|
| `usage` block absent | `RequestUsage()` — every counter `0` (`tests/test_usage_limits.py:1162`) | `Unknown(ProviderOmitted)` |
| `usage: {}` | all counters `0` | `Unknown(ProviderOmitted)` |
| `usage: {"input_tokens": 0}` | `0` | `Known(0)` — **a zero is a measurement** |
| `usage: {"input_tokens": 12}` | `12` | `Known(12)` |

The third row is the one that makes the test worth writing: it proves the fake is not simply
"absent ⇒ unknown", and it pins ADR-0002's `Known.coerce` contract (*"`0` stays `Known(0)` —
a zero is a measurement"*).

---

## 6. GitHub Actions strategy

### 6.1 Jobs, runners, required-ness

| Job | Workflow | Runner | Required check |
|---|---|---|---|
| `python-quality` | `python.yml` | `ubuntu-latest` + `windows-latest` | yes |
| `web-quality` | `web.yml` | `ubuntu-latest` | yes |
| `reference-exclusion` | `reference-exclusion.yml` | `ubuntu-latest` | **yes — explicitly required by the work order** |
| `secret-scan` | `security.yml` | `ubuntu-latest` | yes |
| `lockfile-consistency` | `lockfiles.yml` | `ubuntu-latest` | yes |

### 6.2 The hard rule: no job may require an upstream clone

**No workflow step may reference `../labcairn-upstreams`, `E:\labcairn-upstreams`,
`scripts/checkout_upstreams.py`, or any path outside `$GITHUB_WORKSPACE`.** An external
contributor who has never cloned anything must get a green run from a bare fork checkout.

Enforced mechanically by
`tests/test_no_reference_leakage.py::test_workflows_do_not_require_upstream_checkouts`, which
parses every workflow, walks every `run:` block and every `uses:`/`with:` value, and fails on
any of those substrings **outside** an exclusion context (`paths-ignore`, `exclude`,
`.gitleaks.toml` allowlist, a test fixture). The test must be able to distinguish "excluded"
from "required" — a naive substring grep would pass a workflow that both excludes and then
clones, so the test checks the *semantic position*, not the presence of the string.

Related: `.gitleaks.toml`'s reference allowlist and every exclusion glob *do* mention
`labcairn-upstreams`. That is not a violation, and the test must encode the distinction.

### 6.3 Quality gates and what each must actually assert

- **lint** — `ruff check` and `ruff format --check`. Not "ruff passes": the ruleset is
  declared in `pyproject.toml` (T02) and reviewed there.
- **type** — `mypy src` at the strictness declared in `pyproject.toml`. Stated as a floor,
  not a target: raising strictness later is a normal, cheap change.
- **test** — `pytest`, on both OSes. `tests/test_no_reference_leakage.py` runs here too, but
  the **dedicated job** (J3) is what the work order requires, because J3 builds the sdist
  and wheel first.
- **frontend** — `pnpm typecheck && pnpm lint && pnpm test`. `tsc --noEmit` is mandatory; a
  Vite build succeeding does not type-check.
- **secret scan** — gitleaks, git mode, `fetch-depth: 0` (git mode needs history).
- **lockfile consistency** — `uv lock --check` and `pnpm install --frozen-lockfile`.
- **release archive** — J3 additionally produces an archive via `git archive` and asserts its
  member list contains no reference path (checklist row 9).

### 6.4 `paths-ignore` — read §11 C-1 before writing these files.

---

## 7. README accuracy

The work order's requirement — *"quick-start does not claim unimplemented commands"* — is
soft as prose and hard as a test. T07's `tests/test_readme_commands.py` is the mechanism
(§2/T07). Three properties make it trustworthy:

1. **Fail-closed classification.** A token that matches no known shape fails the test and
   prints itself. There is no "warn and continue".
2. **Target resolution, not target existence.** `pnpm test` passing because `test` is a real
   script is not enough; the script must exist **and** the command in the README must be the
   form the project actually uses (`pnpm test`, not `pnpm run test` or `npm test`).
3. **Both directions.** It also fails if `pyproject.toml` or `package.json` declares a script
   the README never documents? **No** — that is a different concern (documentation coverage)
   and would create churn. Documented limitation: a script can exist undocumented without
   failing this test.

Additional assertions:
- The README must contain a status line marking Phase 1 as under construction (already
  present at `README.md:5` and `:44`).
- The README must **not** mention any LC-P1-12+ surface. LC-P1-01 ships no CLI and no UI, so
  `labcairn init`, `labcairn doctor`, `localhost:8000`, screenshots and "demo" claims are all
  test failures, not style preferences.

---

## 8. LICENSE handling

**Decision (project lead, recorded here so it is not relitigated):** leave a placeholder;
CI does **not** validate a LICENSE file in LC-P1-01.

- **Placeholder form (recommended).** Do **not** create a file named `LICENSE` — GitHub and
  PyPI both treat that name as a legal grant, and placeholder text under it would be a false
  statement about licensing. Instead: `LICENSE.PENDING.md`, containing (a) the intended MIT
  grant, (b) the two conditions from the work order — *"MIT license once ownership cleared"*
  and *"subject to final ownership and dependency review"* (`README.md:63`) — and (c) the
  trigger for replacement. The README's existing "Open source and attribution" paragraph is
  the human-readable placeholder of record and already says the right thing:
  *"this README is not a substitute for a license."*
- **Why CI does not check.** A LICENSE-presence check in LC-P1-01 would have to be one of:
  (a) *fail until the file exists* — permanent red CI that trains people to ignore it;
  (b) *pass unconditionally* — asserts nothing; (c) *check placeholder text* — locks in a
  fiction. All three are worse than no check. The real gate is **LC-P1-14's
  "license/NOTICE audit"**, which is where ownership is actually cleared.
- **Conditions to close it out.** All four must hold before `LICENSE` is written:
  1. Copyright ownership of all LabCairn source is settled.
  2. The dependency set is final enough that the "dependency review" in `README.md:63` can be
     performed (note: PyMuPDF and any `paper-qa` component remain open license questions —
     `docs/UPSTREAM_REFERENCES.md` §"Verified license boundaries").
  3. ADR-0004's AGPL-3.0 boundary is confirmed un-crossed by the final dependency graph.
  4. `LICENSE.PENDING.md` is deleted in the same commit that adds `LICENSE`.
- **Verification now**: T12's check — no file named `LICENSE` is tracked.

---

## 9. Execution order

Five waves. Within a wave, tasks are fully parallel **only if** they share no file from the
ownership map in §2.

### Wave 0 — must be serial, single owner
| # | Task | Exit checkpoint |
|---|---|---|
| 0.1 | Sign off D-2 (backend), D-3 (package list), D-4 (requires-python), D-5 (CI OS set) | decisions recorded in the PR description or a short ADR note |
| 0.2 | T01 | `git log` shows exactly one commit; `git rev-parse --show-toplevel` is `E:/LabCairn`; 12 files tracked |

### Wave 1 — parallel, 6 tasks
`T02` · `T03` · `T04` · `T08` · `T10` · `T11` · `T12`
(T02 is the critical path; the rest are independent.)

| # | Task | Exit checkpoint |
|---|---|---|
| 1.1 | T02 | `uv build` produces a wheel containing `labcairn/` **and** `labcairn/core/`; `uv lock --check` green; `ruff`/`mypy`/`pytest --collect-only` green |
| 1.2 | T03 | `.vscode/settings.json` parses; both keys carry all three globs in case-variant form |
| 1.3 | T04 | `.gitleaks.toml` present; a local git-mode scan completes and finds nothing in tracked files |
| 1.4 | T08 | `from labcairn.core.providers.fake import FakeProvider` imports; `UsageValue` importable; no network-capable module imported |
| 1.5 | T10 | `pnpm typecheck && pnpm lint && pnpm test && pnpm build` all green |
| 1.6 | T11 | `scripts/check_repo_root.py` exits 0 in the repo and non-zero from `E:/` |
| 1.7 | T12 | no tracked file named `LICENSE`; `LICENSE.PENDING.md` present |

### Wave 2 — parallel, 3 tasks
`T05` · `T09` · `T07`(blocked on T12 for the license paragraph)

| # | Task | Exit checkpoint |
|---|---|---|
| 2.1 | T09 | all six determinism/truthfulness tests green; two runs byte-identical |
| 2.2 | T05 | `pytest tests/test_no_reference_leakage.py -v` green, including the wheel-subpackage test |
| 2.3 | T07 | `pytest tests/test_readme_commands.py -v` green; a deliberately-injected fake command fails |

### Wave 3 — serial (needs Wave 1 + 2 inputs)
`T06`

| # | Task | Exit checkpoint |
|---|---|---|
| 3.1 | T06 | all five workflows green on a scratch branch; `reference-exclusion` set as a required check; the deliberately-reference-shaped path on that branch produces a green run |

### Wave 4 — verification sweep (no new code)

Run, in this order, and record the output:

```
git -C E:/LabCairn rev-parse --show-toplevel
uv sync --frozen && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
uv build && uv run pytest tests/test_no_reference_leakage.py -v
cd web && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm test
git -C E:/LabCairn ls-files | grep -iE '(^|/)(_references|\.upstreams|labcairn-upstreams)' && echo "FAIL"
git -C E:/LabCairn ls-files | grep -i '^LICENSE$' && echo "FAIL"
```
Then: **fresh-clone test.** Clone the branch to a new directory outside `E:/LabCairn`, follow
`README.md` verbatim with **no** `../labcairn-upstreams` present, and confirm every command
succeeds. This is the work order's *"fresh clone and documented setup on CI-supported OS"*,
performed by hand as well as by CI.

---

## 10. Risks and unknowns

| # | Risk / unknown | Assessment |
|---|---|---|
| R-1 | **The literal `["src/labcairn"]` package list silently drops subpackages.** | **Highest implementation risk in the plan.** See §11 C-2. T05's `test_wheel_contains_all_subpackages` is the guard; it must be written *before* the wheel is ever trusted. |
| R-2 | **`paths-ignore` vs "runs on every pull request"** | Genuine contradiction in the checklist. §11 C-1. Needs a decision, not a judgement call at implementation time. |
| R-3 | **FakeProvider scope vs ADR-0002's assignment to LC-P1-03** | §11 C-3. ADR-0002 says the contracts are *"Implemented by LC-P1-03"*, but LC-P1-01 must ship a FakeProvider *and* demonstrate unknown-usage. |
| R-4 | **Node 24 + pnpm 9 compatibility** | Unknown until T10 runs. If broken, escalate — do not silently pin an older Node, which changes every later work order. |
| R-5 | **The reference glob set may grow.** LC-P1-00 defines three; LC-P1-00's own evidence suggests `_references*` / `.upstreams*` / `labcairn-upstreams*` are the operative set. If LC-P1-01 later adopts a fourth layout, **every** artifact in §3 changes. Mitigation: define the glob set in **one** place (a constant in `tests/test_no_reference_leakage.py`) and have the other checks import it — do not copy-paste globs into six files. This plan does not mandate that, but strongly recommends it. |
| R-6 | **Line endings / `.gitattributes`** | No `.gitattributes` exists. On Windows, `ruff format` and `mypy` are fine, but a CRLF/LF difference can make byte-identity assertions flaky (T09). §11 C-5. |
| R-7 | **`docs/acceptance/` is being written concurrently by another agent.** | This plan does not touch `docs/acceptance/`. If that directory later contains commands, T07's test scope (`README.md` + `docs/*.md`, non-recursive) does not cover it — decide deliberately whether it should. |
| R-8 | **The `paths-ignore` globs and the leak test can disagree about depth.** | Actions globs and `.gitignore` globs are different languages. T05's test should assert the *observable outcome* on both, not that the two config strings match. |
| R-9 | **T02 is large.** Packaging + tool config + lockfile + skeleton + conftest + markers is one agent-sized unit at most, and it is on the critical path. | If T02 overruns, split it into T02a (packaging + lock) and T02b (tool config + conftest) — but **both must stay single-owner on `pyproject.toml`**, so they serialize regardless. |
| R-10 | **T06 bundles five workflows.** | Five files, one owner, one reviewer. Plausibly beyond a single reliable pass. Consider splitting by job with the *same* owner agent continuing sequentially, rather than parallelizing (which would violate the ownership map). |
| R-11 | **The secret-scan canary test risks a real secret commit.** | Mitigated by requiring a disposable branch. If the implementer is unsure, skip the canary and say so in the review — a leaked canary on `main` is a worse outcome than an unverified scanner. |
| R-12 | **What "documented setup" means is undefined.** | This plan treats it as: a fresh clone + `README.md` followed verbatim + the §9 Wave 4 commands. Needs sign-off, since LC-P1-14 revisits the quickstart. |

---

## 11. Conflicts and gaps between the work order, the ADRs and reality

Recorded, not resolved. Each needs a human decision.

### C-1 — `paths-ignore` on `pull_request` contradicts "runs on every pull request"

`UPSTREAM_REFERENCES.md` row 3 requires `paths-ignore` on **both** `on: push` and
`on: pull_request`. The work order's Acceptance requires that the exclusion CI job *"runs on
every pull request"*. If a PR touches only a reference-shaped path, `paths-ignore` on
`pull_request` means the job never starts — and if it is a **required** status check, the PR
is blocked forever and cannot be closed. The checklist's stated intent — *"so reference-only
changes neither trigger nor cancel required checks"* — is sound but unachievable with a
required check under `pull_request` filtering.

Options: (a) `paths-ignore` on `push` only, `pull_request` unfiltered — the gate always runs,
and a reference-only PR costs one CI run; (b) keep both filtered and make
`reference-exclusion` non-required, relying on T05's in-suite copy — contradicts the work
order; (c) keep both filtered and add a `workflow_run`/`schedule` backstop — complex, and
still not "every pull request". **Recommendation: (a).** Needs sign-off because it deviates
from the checklist text.

### C-2 — `["src/labcairn"]` is ambiguous, and the obvious reading is wrong

The checklist says *"Set an explicit package list of `["src/labcairn"]` and **disable
auto-discovery**."* Those two clauses are in tension: `["src/labcairn"]` reads as a
`[tool.setuptools.packages.find] where = ["src"]` root, which *is* discovery, and which — with
a `src/` tree containing `core/`, `runtime/`, `db/`, … per `docs/ARCHITECTURE.md` — will
produce a package list that changes as directories are added. Read literally as
`packages = ["labcairn"]`, discovery *is* off, but **only `labcairn/` is packaged and every
subpackage is silently absent from the wheel** — the failure would not surface until an
install in CI-P1-03.

Resolution: list **every** subpackage explicitly and let `test_wheel_contains_all_subpackages`
enforce it; or accept `packages.find` and drop the "disable auto-discovery" clause.
Additionally, `ARCHITECTURE.md` lists 12 subpackages but LC-P1-01 creates ~2 — an explicit
list containing 10 non-existent directories is an error at build time. **This must be decided
before T02 starts** (D-3).

### C-3 — LC-P1-01 must ship a FakeProvider; ADR-0002 assigns its contracts to LC-P1-03

The work order (LC-P1-01) requires *"A FakeProvider and deterministic demo fixtures must run
without paid APIs."* ADR-0002 §Contracts states the `UsageValue` and `CapabilityOutcome`
contracts are *"Implemented by LC-P1-03"*, and its **Work order** line reads
*"LC-P1-02 (module boundaries), LC-P1-03 (providers, budgets, capability detection)"* —
LC-P1-01 is not listed. But LC-P1-01 cannot demonstrate *"unknown ≠ zero"* without `UsageValue`.

Options: (a) LC-P1-01 lands `UsageValue` (≈20 lines, pure value object, no I/O, no
dependency) as a deliberate exception, documented in the commit; (b) LC-P1-01 ships a fake
that returns raw `int | None` and defers the demonstration to LC-P1-03, weakening the
LC-P1-01 acceptance bar to "runs without paid APIs"; (c) amend ADR-0002's work-order line.
**Recommendation: (a)** — ADR-0002 itself says *"`RunBudget` and `UsageValue` are pure value
objects with no I/O"*, so landing it early is cheap and reversible. **But it is a deviation
from ADR-0002's stated ownership and must be recorded, not assumed.** This plan does not ship
`ProviderCapabilities`/`ProviderProbe` at all — those genuinely belong to LC-P1-03.

### C-4 — The secret-scan allowlist is close to inert in git mode

The checklist requires *"Add the reference paths to the scan allowlist"* while also requiring
git mode. In git mode, the sibling clones are not in the repository and therefore cannot be
scanned; the allowlist only covers the case where a reference directory was committed by
mistake. The clause is harmless and worth keeping, but it does not do what its position in the
table implies. T04 should state this in the config comment rather than let a future reader
believe the allowlist protects the clones. It does not; T11's procedure does.

### C-5 — No `.gitattributes` exists, and T09 asserts byte-identity

LC-P1-01 does not mention line endings, but T09's byte-identity test and any future
reproducibility manifest (LC-P1-10) depend on a stable normalisation. Adding `.gitattributes`
is arguably in scope for *"reproducible engineering baseline"* and arguably not in the
work order text. **Recommendation: add a minimal `.gitattributes` (`* text=auto eol=lf`,
binary types declared) inside T02, and record it as a small scope addition.** Needs sign-off.

### C-6 — "CI-supported OS" is never named

The work order says *"fresh clone and documented setup on CI-supported OS"* and, separately,
*"Real Windows smoke later in Phase 1."* Development is on Windows; the authoritative
exclusion verification (§3.4) is only possible on Linux. Running `python-quality` on
`windows-latest` is not "real Windows smoke" — it is a cheap early signal — but the two
sentences read as contradictory. See D-5.

### C-7 — `src/labcairn/core/` is required by T08 but the package list is fixed by T02

If T02 settles the explicit package list before T08 exists, T08 creates files in a directory
that packaging may not pick up. Resolution: **T02 must create `src/labcairn/core/__init__.py`
and list `labcairn.core` in the package list even though T08 has not run yet**, and T05's
`test_wheel_contains_all_subpackages` is what keeps the list honest. Sequencing rule: **T02
pre-creates the directories T08 will populate; T02 must never be re-run after T08 lands.**

### C-8 — `.gitignore` is owned by T01 but verified by T05

T01 widens the globs; T05 asserts the behaviour. If T05 asserted `.gitignore`'s *text*, the
two would contend. **Resolution, frozen here: T05 asserts behaviour via `git check-ignore`
against temp paths, never the file's contents.** Under this rule T01 ∥ T05 is safe.

---

## 12. Definition of done for LC-P1-01

All must be true. Each is checkable.

1. A fresh clone on a CI-supported OS, with **no** `../labcairn-upstreams`, follows `README.md`
   and reaches a green test run.
2. `ruff`, `ruff format --check`, `mypy` and `pytest` pass on `ubuntu-latest` **and**
   `windows-latest`.
3. `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm build` pass.
4. `uv lock --check` and `pnpm install --frozen-lockfile` pass in CI.
5. `tests/test_no_reference_leakage.py` exists, passes, and covers `git ls-files` **and** the
   member names of the built sdist and wheel.
6. The `reference-exclusion` job is a required status check and runs on every pull request
   (subject to C-1's resolution).
7. The secret scan runs in git mode; no workflow contains `--no-git`.
8. `git ls-files` and both build artifacts contain no reference path, in any case variant.
9. `scripts/check_repo_root.py` exits 0 in the repo and non-zero from a parent directory.
10. No file named `LICENSE` is tracked; `LICENSE.PENDING.md` exists.
11. Every command in `README.md` resolves to a real target, or the README test fails.
12. The FakeProvider runs a full transcript with sockets and HTTP transports patched to raise,
    and twice in a row produces byte-identical output.
13. A transcript with no `usage` block yields `Unknown(ProviderOmitted)`; a transcript with
    `"usage": {"input_tokens": 0}` yields `Known(0)`.

---

**End of plan. No work described here has been performed.**
