# Repository Map

**Status:** current index, 2026-11-06. This document classifies the tracked
tree. It does not retire historical records, rewrite frozen acceptance
evidence, or authorise Phase 3 implementation.

## 1. Classification measured on 2026-11-06

The read-only scan measured **727 tracked files** before this map was
added: 448 Python files, 163 Markdown files, 27 JSON files, 24 TSX files, 23
TypeScript files, 13 CSV files, 7 workflow YAML files, and the remaining
configuration, fixture and binary files. It found **0 exact-byte duplicate
groups**, **199 Python test files**, **3,419 declared test functions**, and
**38 fixture files**. This map is one further tracked Markdown file in the
same tidy delivery. Test paths are keys in `.github/ci-shards.json`,
`tests/evaluation/manifest.py` and the witness ledger; they are kept and are
not renamed by a cosmetic tidy.

The twelve names that look historical — `ADR_TEMPLATE.md`, `gold_set`,
`*-draft.md`, `test_scaffolding.py` and similar — all have live references in
acceptance records or CI registrations. They are named records, not stale
copies. A file is deleted only when its own claim is retired and its
references are removed in the same change.

## 2. Product source

| Directory | Holds |
|---|---|
| `src/labcairn/` | The product package: API, CLI, security, storage, material readers, paper chain, version graph, roles, skills, analysis, figures and reports. |
| `migrations/versions/` | Ordered schema migrations. A deployed store keeps every prior migration. |
| `web/src/` | The local workbench: app shell, views, generated API contract and browser tests. |

`pyproject.toml`, `uv.lock`, `.python-version`, `web/package.json` and
`web/pnpm-lock.yaml` are build and dependency pins, not generated debris.
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
| `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/README.md` | Public release record, contribution rules and documentation index. |
| `docs/ROADMAP.md`, `docs/handoff/CURRENT.md` | Current phase, delivery pointer and handoff state. Dated sections below the current pointer are historical snapshots. |
| `docs/PHASE_1_WORKORDERS.md`, `docs/plans/PHASE_2-work-orders.md` | Work-order and gate records. Their old rows are evidence of how a phase was judged. |
| `docs/plans/` | Task breakdowns, ADR impact matrices, scoping pack and design-only records. |
| `docs/adr/` | Architecture decisions. `Proposed`, `Accepted` and archived states are part of the decision record. |
| `docs/acceptance/` | Named-commit acceptance reports and measured gate verdicts. Do not rewrite a frozen verdict to make it look current; add a dated current pointer instead. |
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
`web/dist/`, `.local/`, `.venv/`, `web/node_modules/` and
`.claude/worktrees/` are ignored local artefacts. They are reproducible or
machine-local and must never be staged. `.local/` may hold owner-side records;
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
