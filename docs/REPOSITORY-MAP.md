# Repository Map

**Status:** current index, 2026-11-10 (classification measured 2026-11-07).
This document classifies the tracked tree. It does not retire historical
records, rewrite frozen acceptance evidence, or authorise Phase 3
implementation.

**Read 2026-11-10 (re-measurement):** the 733-file figure in §1 is the scan at
`7029bc28500f2d676a01b9586f04c17419dc0493`, a historical measurement that is
left as written. At the follow-up branch's measured code head
`6c0007e547711c0637edfaf518eaca70b33205c5`, and again at its documentation-only
delivery head `6a53644eff8ed1b2edd6c0bb251a6c00689b1ef5`, the count was **821
tracked files**. After the real-sample machine half landed, re-measured at
`e3aed01a18a56036d64a8e1bc93d4fa0041b16d8`, `git ls-files | wc -l` prints
**823 tracked files**: 481 `.py`, 192 `.md`, 29 `.json`, 27 `.mjs`, 26
`.tsx`, 23 `.ts`, 13 `.csv`, 7 `.yml`, 3 `.pdf`, and the remaining
configuration, fixture and binary files. The two added files are the dated
real-sample Markdown record and its JSON summary. The 27 `.mjs` files are the
`shell/` witnesses and rehearsals recorded in §2 below. No witness in
`tests/` watches this document's file count; it is a dated measurement, not a
claim the CI gate holds.

**Read 2026-11-11 (re-measurement after the CHANGELOG split):** at
`9dee4ed6a9e4e00a92f28d792a7b72f3e1a16d92` the three phase archives had
raised the dated count to **826 tracked files** and **195 Markdown files**.
After the shell CI workflow and the T08 packaging configuration merged,
`6cdbfb56ce29dd19e4f56dae549b4d476d998d1e` printed **831 tracked files**.
After the full NOTICE dependency surface landed, the live measurement at
`bf2f6f450c93104b34fac38d4f853880dca53872` prints **833 tracked files**:
483 `.py`, 195 `.md`, 29 `.json`, 30 `.mjs`, 26 `.tsx`, 23 `.ts`, 13
`.csv`, 9 `.yml`, 3 `.pdf`, and the remaining configuration, fixture and
binary files. The 823 / 192, 826 / 195 and 831 / 195 figures are named
earlier measurements, not current totals.

## 1. Classification measured on 2026-11-07

The read-only scan measured **733 tracked files** at
`7029bc28500f2d676a01b9586f04c17419dc0493`; the 2026-11-06 figure was **727**
before this map was added, and the six files since are this map and five
Phase 3 planning and decision records: 448 Python files, 169 Markdown
files, 27 JSON files, 24 TSX files, 23 TypeScript files, 13 CSV files, 7
workflow YAML files, and the remaining configuration, fixture and binary
files. It found **0 exact-byte duplicate groups**, **199 Python test files**,
**3,419 declared test functions**, and **38 fixture files**; all four were
re-measured on 2026-11-07 and none of them moved. **Read 2026-11-08:** those
figures are the scan at the commit named, not a running total — the Phase 3 G1
work-order board `docs/plans/PHASE_3-work-orders.md` joined the tree on
2026-11-08 and moves the Markdown count by one whenever the scan next runs. **Read 2026-11-09:** the Phase 3 G1 batch adds seventeen files to the tree — nine under `src/labcairn/editing/`, three documents (`docs/adr/ADR-0021-manuscript-editing-rewrite.md`, `docs/acceptance/LC-P3-02-support-matrix.md`, `docs/acceptance/LC-P3-02-substitute-run-2026-11-08.md`) and five test-side files, one of which is not a `test_*.py` and so carries no shard entry — and every figure above is the scan at the commit named, not this total. The re-scan is a dated follow-up, not a merge-time claim. Test paths are keys in
`.github/ci-shards.json`, `tests/evaluation/manifest.py` and the witness
ledger; they are kept and are not renamed by a cosmetic tidy.

The twelve names that look historical — `ADR_TEMPLATE.md`, `gold_set`,
`*-draft.md`, `test_scaffolding.py` and similar — all have live references in
acceptance records or CI registrations. They are named records, not stale
copies. A file is deleted only when its own claim is retired and its
references are removed in the same change.

## 2. Product source

| Directory | Holds |
|---|---|
| `src/labcairn/` | The product package: API, CLI, security, storage, material readers, paper chain, version graph, roles, skills, analysis, figures, reports and the manuscript editing seam. |
| `migrations/versions/` | Ordered schema migrations. A deployed store keeps every prior migration. |
| `web/src/` | The local workbench: app shell, views, generated API contract and browser tests. |
| `shell/src/` | The Electron desktop shell's main process, service supervisor, window factory, sandboxed preload and live session-guard IPC decisions. |
| `shell/test/`, `shell/scripts/` | The shell's Node witnesses (drain, run modes, security baseline, live guard, dependency surface, native surface) and its real-window rehearsals. These are `mjs` files, not pytest files, and carry no shard entry. |

`pyproject.toml`, `uv.lock`, `.python-version`, `web/package.json`,
`web/pnpm-lock.yaml`, `shell/package.json` and `shell/pnpm-lock.yaml` are build
and dependency pins, not generated debris.
`LICENSE` is the single MIT grant; `NOTICE` records third-party terms.

## 3. Tests and measurement machinery

| Directory or file | Holds |
|---|---|
| `tests/test_*.py` | Product witnesses. Each claim about behaviour needs one; a green tree with a deleted witness is not evidence. |
| `tests/evaluation/` | Evaluation harness, aggregate, report, manifest and JUnit interpretation. |
| `tests/fixtures/public/` | Public synthetic fixtures. Their notice points to the root MIT grant. |
| `tests/fixtures/papers/` | Public paper-shaped fixtures; material words from the owner's pilot corpus stay outside this repository. |
| `tests/docx_corpus.py`, `tests/gold_set_fixtures.py` | Fixture builders and corpus helpers, not duplicate datasets. |
| `conftest.py` | Pytest's shared temporary-root rules. |
| `.github/ci-shards.json` | Runner-measured per-file costs and the five-shard partition. A new test file must be registered here. |
| `scripts/witness_ledger.py` | Compares test-function names across two revisions after a merge. |
| `scripts/cjk_ceilings.py` | Measures the longest Han run per tracked file; the pin watches material leakage. |

`tests/test_ci_shard_coverage.py`, `tests/test_no_reference_leakage.py`,
`tests/test_status_consistency.py`, `tests/test_scaffolding.py` and
`tests/test_readme_accuracy.py` are guards of the measurement machinery
itself. Their historical-looking names are not permission to prune them.

## 4. Documentation and records

| Directory | Holds |
|---|---|
| `README.md`, `README.zh-CN.md` | Public current-state entry points and the status banner. |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/README.md` | Public release record, contribution rules and documentation index. The changelog's dated record lives in the phase archives below. |
| `docs/changelog/` | The phase archives of the changelog: `phase-1.md` (gates G0 to G5), `phase-2.md`, `phase-3.md`. A dated entry joins the archive of its phase. Split 2026-11-11; see the changelog's own entry. |
| `docs/ROADMAP.md`, `docs/handoff/CURRENT.md` | Current phase, delivery pointer and handoff state. Dated sections below the current pointer are historical snapshots. |
| `docs/PHASE_1_WORKORDERS.md`, `docs/plans/PHASE_2-work-orders.md`, `docs/plans/PHASE_3-work-orders.md` | Work-order and gate records. Their old rows are evidence of how a phase was judged. |
| `docs/plans/` | Task breakdowns, ADR impact matrices, the dated Phase 3 scoping pack, the English Phase 3 planning proposal and its execution plan, the Q1–Q96 design traceability, the multisource research-learning supplement of 2026-11-07, the Phase 3 G1 work orders issued 2026-11-08 and other design-only records. |
| `docs/adr/` | Architecture decisions. `Proposed`, `Accepted` and archived states are part of the decision record. |
| `docs/acceptance/` | Named-commit acceptance reports, measured gate verdicts and dated owner decision records. Do not rewrite a frozen verdict to make it look current; add a dated current pointer instead. |
| `docs/research/`, `docs/UPSTREAM_REFERENCES.md` | Upstream source study and binding exclusion checklist. |
| `docs/EVALUATION.md`, `docs/THREAT-MODEL.md`, `docs/RELEASE-NOTES.md`, `docs/REVIEW-DOSSIER.md` | Evaluation protocol, threat model, release record and review dossier. |

A stale sentence in a dated acceptance snapshot is a historical fact. A stale
sentence in a current pointer is a defect. The two cases are handled
differently.

## 5. CI, release and operational files

`.github/workflows/` holds seven workflows: `python.yml`, `web.yml`,
`reference-exclusion.yml`, `lockfiles.yml`, `release.yml`, `security.yml` and
`provider-smoke.yml`. The first six are required checks or their supporting
gates; `provider-smoke.yml` is schedule / manual dispatch only because it
spends the owner's money. `.github/remeasure_shards.py` and
`.github/make_ci_shards.py` maintain the measured shard partition from a
runner log.

`.gitleaks.toml`, `.gitattributes`, `.gitignore`, `.env.example`,
`.python-version`, `web/.npmrc` and the editor configuration files are
configuration, not scratch files.

## 6. Generated and ignored files

`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`,
`web/dist/`, `.local/`, `.venv/`, `web/node_modules/`,
`shell/node_modules/` and `.claude/worktrees/` are ignored local artefacts.
They are reproducible or machine-local and must never be staged. `.local/` may hold owner-side records;
it is not a second source tree. Runtime test temporary directories belong
outside the checkout.

The 2026-11-06 tidy removed the disposable caches and build output but kept
the virtual environment, local workspace and installed web dependencies.

## 7. Historical records and naming

Names that carry `draft`, `gold_set`, `snapshot`, `evidence`, `acceptance` or
`TEMPLATE` are retained where a live record cites them. Renaming one is a
three-register change: the reference, the CI shard list and the evaluation
manifest must move with it, and runner-measured costs must be re-measured.
No such rename is part of this tidy.

## 8. What this map does not do

It does not delete a witness, accept a model-proposal edge, rewrite a gate
verdict, change a credential, start Phase 3 implementation, publish a
release, or replace the records it classifies.
