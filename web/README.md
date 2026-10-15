# `web/` — LabCairn local workbench UI

> **Status: engineering baseline, no product features.** This directory contains a
> buildable, type-checked and unit-tested React + TypeScript skeleton and nothing else.
> The research workspace described in the repository README is a **plan**, not shipped
> software. The only component here is a static placeholder that says so on screen.

Produced by work order **LC-P1-01 / T10** (see
`docs/plans/LC-P1-01-task-breakdown.md` → T10).

## Pinned toolchain

CI must pin these exactly. `package.json` carries both pins: `packageManager`
(enforced by Corepack) and `engines`.

| Tool | Version                           | Enforced by                                                     |
| ---- | --------------------------------- | --------------------------------------------------------------- |
| Node | `24.16.0` (range `>=24.16.0 <25`) | `.github/workflows/*.yml` → `actions/setup-node` `node-version` |
| pnpm | `9.15.9` (range `>=9.15.9 <10`)   | `packageManager` field + Corepack                               |

`.npmrc` sets `engine-strict=true`, so a mismatched Node or pnpm fails at install
time instead of silently resolving something else. Changing either pin is a
deliberate escalation (LC-P1-01 §10, risk R-4), not a routine dependency bump.

## Scripts

Run all of them from `web/`.

| Script                  | Command                | What it does                                                 |
| ----------------------- | ---------------------- | ------------------------------------------------------------ |
| `pnpm run dev`          | `vite`                 | Dev server on `http://127.0.0.1:5173`                        |
| `pnpm run build`        | `tsc -b && vite build` | Type-check, then emit `dist/`                                |
| `pnpm run preview`      | `vite preview`         | Serve `dist/` on `http://127.0.0.1:4173`                     |
| `pnpm run test`         | `vitest run`           | Unit tests once (jsdom + Testing Library)                    |
| `pnpm run test:watch`   | `vitest`               | Unit tests in watch mode                                     |
| `pnpm run typecheck`    | `tsc -b --force`       | Strict type-check of app + tooling, no emit                  |
| `pnpm run lint`         | `eslint .`             | ESLint 10 flat config, type-aware (`recommendedTypeChecked`) |
| `pnpm run format`       | `prettier --write .`   | Apply Prettier                                               |
| `pnpm run format:check` | `prettier --check .`   | Formatting gate                                              |

`build` already runs `tsc -b`, so a CI job may run `build` alone or keep `typecheck`
as a separate, faster-failing step. Running both is harmless.

## Dependency resolution

`pnpm-lock.yaml` is committed and is the sole resolution authority; every version in
`package.json` is pinned exactly (no `^`/`~`), so the manifest is readable on its own.

CI must install with the lockfile enforced:

```bash
cd web
pnpm install --frozen-lockfile
```

`--frozen-lockfile` exits non-zero with `ERR_PNPM_OUTDATED_LOCKFILE` whenever
`package.json` and `pnpm-lock.yaml` disagree, which is what makes the lockfile a
real gate rather than a hint. It is also the pnpm default inside CI.

Do **not** add `package-lock.json`, `yarn.lock` or a second lockfile.

## Layout

```text
web/
  index.html                     # Vite entry; loads no remote asset
  vite.config.ts                 # dev/preview server, pinned to loopback
  vitest.config.ts               # jsdom env, setup file, v8 coverage
  eslint.config.js               # ESLint 10 flat config
  tsconfig.json                  # solution file (project references)
  tsconfig.app.json              # src/ — strict, jsx: react-jsx
  tsconfig.node.json             # vite/vitest config — strict, types: node
  src/
    baseline.ts                  # single source of truth for placeholder copy
    baseline.test.ts
    App.tsx / App.test.tsx
    components/PhaseOneBaselineNotice.tsx
    index.css
    main.tsx
    test/setup.ts
```

## Scope boundary

This baseline deliberately contains **no** API client, no research/task/evidence/
artifact views, no model calls and no fixture data. Adding any of those belongs to the
Phase 1 work orders that follow LC-P1-01, not to this skeleton. In particular: do not
add a dev-server proxy to a Python backend — no such backend is running yet, and
configuring one would imply a capability that does not exist.

## Licence status

The repository carries no `LICENSE` file yet and no open-source rights have been
granted. Do not add one here.
