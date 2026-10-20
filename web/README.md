# `web/` — LabCairn local research workbench

> **Status: the local workbench.** This directory holds the React + TypeScript
> application a person opens to see where a task has got to. It reads the
> local API and draws what the API says; it holds no state of its own, so a
> refresh shows the database's state rather than a copy of it.

The skeleton came from work order **LC-P1-01 / T10** (see
`docs/plans/LC-P1-01-task-breakdown.md` → T10) and the workbench from
**LC-P1-12 / T08** (see `docs/plans/LC-P1-11-12-task-breakdown.md` → T08).

## What it shows

Eight views over one task, each read from the API and drawn:

| View               | What it draws                                                                         |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Projects**       | The tasks in the workspace's store, and the one the service is bound to               |
| **Plan**           | The declared workflow, and how far the task has got through it                        |
| **Steps**          | The runtime stages the store holds, with the run and the attempt each belonged to     |
| **Approval**       | The question the task is waiting on a human to answer, and the button that answers it |
| **Source anchors** | The material the task is bound to, its content hash and the key it is addressed by    |
| **Evidence**       | The declared evidence stage's standing, and the runtime stages named `evidence`       |
| **Artefacts**      | The receipts, and a preview of each artefact                                          |
| **Revisions**      | What each path has been through, and which revision is current                        |

The one thing the page changes is a pending approval. Everything else it does
is read.

## The API it talks to

The service is FastAPI, bound to `127.0.0.1`, and it is the only thing this
package talks to. In production the service serves this very bundle, so the
page and the API share one origin — which is what makes the service's origin
check mean what it says.

**The types are not written here.** `src/api/generated.ts` is generated from
the API's OpenAPI document, which is generated from the application layer's own
response models:

```bash
uv run python -m labcairn.api.typescript web/src/api/generated.ts
```

`tests/test_api.py` compares the checked-in file with the models, so a model
that changes without the file being regenerated is a failing test rather than
a stale type. This package imports that file and does not write a second
spelling of the API's shape.

In development the API is reached through Vite's proxy at `/api`, because the
development server is on another port. The proxy strips that prefix and does
**not** rewrite the request's `Origin`, and the service must be started with
the development origin in `extra_origins`:

```python
create_app(context, extra_origins=["http://127.0.0.1:5173"])
```

## The rules it holds to

**No remote host.** The client refuses any path that names one, the shipped
source names none, and the built bundle names only React's own error-message
address and the XML namespace identifiers. `src/api/bundle.test.ts` builds the
artefact that ships and reads it.

**The token in memory only.** The session token is held in a module variable —
not in React state, which is readable from the outside — and presented as
`Authorization: Bearer`. It is never in a URL, a cookie, the DOM, the
browser's storage or a log.

**Nothing from the model is executed.** No `eval`, no `new Function`, no
`dangerouslySetInnerHTML`, no `srcdoc`. The report's text is text.

**A preview cannot run script.** An artefact is previewed as an `<img>` or in
a frame with `sandbox` and nothing else — never as an inlined document,
because an SVG can carry script and an HTML artefact loaded as a document runs
in the service's origin.

**The report is not re-rendered here.** The workbench draws the receipts and
the artefacts' own bytes; it does not compose a wording of the report. A
report is shown with the limit the report itself states.

## What it does not do yet

- **The service's event stream is not read.** The workbench shows the task's
  state and reads it again when something changes.
- **The selected project cannot be switched.** The service is bound to one
  task, and the API has no route to change that.
- **The contract carries no evidence records and no list of anchors.** The
  evidence view draws the evidence stage's standing, and the anchors view
  draws each source's hash and key; both say so on the screen rather than
  implying that the evidence itself is there.
- **The Markdown, DOCX and PDF forms of a report are linked, not shown.** The
  workbench does not compose a fifth wording of the report.

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
  vite.config.ts                 # dev/preview server, pinned to loopback; the /api proxy
  vitest.config.ts               # jsdom env, setup file, v8 coverage
  eslint.config.js               # ESLint 10 flat config
  tsconfig.json                  # solution file (project references)
  tsconfig.app.json              # src/ — strict, jsx: react-jsx
  tsconfig.node.json             # vite/vitest config — strict, types: node
  src/
    api/
      generated.ts               # T07's generated contract — do not edit by hand
      base.ts                    # where the API is, relative to the page
      client.ts                  # the only place that talks to the service
      mount.ts                   # the development mount point, shared with the proxy
      paths.ts                   # the paths the workbench asks for
      session.ts                 # the token, in memory and nowhere else
    app/
      Workbench.tsx              # the shell, and the one change it makes
      useWorkbench.ts            # the read, scheduled by the render
    views/                       # one file per view
    report/firstPassNotice.ts    # the report's own limit, quoted from the renderer
    test/                        # the fake API, at the network boundary
    App.tsx / App.test.tsx
    index.css
    main.tsx
```

## Scope

This package is the workbench and nothing else: the CLI, the application
layer and the service live in the Python tree. The web package draws what the
API returns and asks the API to do one thing.

Do not add a remote host, a font service, an analytics script, or a request to
any absolute URL. A local-first tool that phones home is not local-first, and
the report renders retrieved text — so a remote script would be a remote
script with the user's material in it.

## Licence status

The repository carries no `LICENSE` file yet and no open-source rights have been
granted. Do not add one here.
