# LC-P3-05 — T08's input policy, T06's update path, and T09's two supply ways

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commits named below; the tree moves. Follow the sentence,
not the number.

Anchors, printed live while this record was written (every value produced by
the command named under it; none carried from another record). §3.3's
installer-wiring batch was added later on the worktree branch
`claude/gifted-lichterman-2953e1`; its values were produced on 2026-11-14
from that tree and name their own commits:

| what | value |
|---|---|
| branch | `claude/distracted-hertz-0c6868` (worktree `distracted-hertz-0c6868`); §3.3's batch on `claude/gifted-lichterman-2953e1` |
| base commit (local `main` at dispatch) | `45167933d422e424466e2e09bc91cbd759071d7f` (`git rev-parse HEAD`, printed) |
| commits this record describes | `0acd146d30b1b4b563ea047adbd2b8063ca19993` (implementation), `7048b20` (floor registration) — full SHAs from `git rev-parse`, not extrapolated |
| §3.3's commits (installer wiring) | `49a0d20f9cf3f9463745ba41967519bc26d41354` (extraResources + input guard + installation-relative cliPath), `6e6b376e01c5d7fec0aa4b07ff5a56f33289812a` (template names the exe file), `0a71e915456bd59709c6fdf7541f0333aa83dabc` (the plugin flag at the spawn path) — full SHAs from `git rev-parse` on `claude/gifted-lichterman-2953e1` |
| Node running the witnesses | v24.16.0 (`node --version`) |
| shell Node cases | 106 declared, 105 pass, 1 fail — the fail is `installer-binaries.test.mjs`'s §6(b) state read, red on this worktree's base `4516793` and fixed on `main` by `72cf219` ("Read the replaceability state in both of its forms"); re-run on `E:\LabCairn` at `87c764f` → 9/9 pass |
| pytest witnesses touched | `tests/test_shell_ci.py` — 19 pass (floors registered for the three new files; import-reader scan clean); `tests/test_no_reference_leakage.py` unchanged, run alongside → 129 passed together |
| installer build | `pnpm --dir shell run dist` exit **0**; `LabCairn Setup 0.0.0.exe` 124,568,971 B, sha256 `618f45b54fe108e1ed43b488ca76239db4aed954e9cf3802132fa1e5b2e6d470`; packaged `resources/` = `app.asar`, `app.asar.unpacked`, `elevate.exe`, `labcairn-shell.cmd`, `shell-env.template.json`, `web-dist` — the template ships, no live `shell-env.json` does |
| run type | **locally measured, dev build + one packaging run**. No CI run was started, no pull request was opened, nothing was pushed (`CLAUDE.md`; `PHASE_3-work-orders.md` §3 rule 7) |
| scratch | `E:\labcairn-local\tmp\t05-dist-check`, `E:\labcairn-local\tmp\t05-hash-drill` — outside the repository; no token value or corpus text in either |

**What this record is.** The implementation record for the four shell work
orders the owner opened on 2026-11-14: T05's packaging gaps, T06's update
path, T08's input handling, and T09's supply of the two remaining packaged-run
environment variables. It claims the mechanisms and their witnesses, **not**
ticket status: the board row for `LC-P3-05` is not moved here, and AC-6's
clean-Windows drill remains the owner's human run (the 20-row checklist of
2026-11-11 stands; this record supplies what its blocked rows were waiting
for).

---

## 1. T08 — input handling: every command-line argument is refused

**The plan's basis.** §4.3's second-instance row ("a second launch focuses
the existing window and does not start a second service") and §5's baseline
("no `file://` and no custom scheme is ever loaded"). The gap the skeleton
left: an installed Windows app receives command-line input for free — a path
dragged onto a shortcut icon, a URL handed to the process — and it arrives
twice: in the first launch's `process.argv` and in the `second-instance`
event's forwarded `argv`. The skeleton ignored both.

**The mechanism** (`shell/src/command-line.mjs`, new): a pure classifier —
`classifyLaunchArguments(argv, { executableCount })` for the first launch
(packaged: 1 runtime entry; dev: 2), `classifySecondInstanceArguments(argv)`
for the forwarded event, and `refusalLine(kind, value)` printing the same
`refused …` shape the navigation guards use. **The policy is total: every
user-supplied argument is refused and printed, none is interpreted, loaded,
or guessed at.** `main.mjs` wires both call sites and prints each refusal;
it decides nothing itself, because a decision inline in `main.mjs` has no
witness (the lesson recorded in the skeleton batch's M2).

**The witness** (`shell/test/command-line.test.mjs`, new, 6 cases): packaged
and dev argument shapes, a `file://` URL as an argument, a second instance
forwarding a workspace path and a `labcairn://` URL, the empty-forward case,
and the line shape.

**Counter-mutation M1** — the policy rewritten to accept everything (both
classifiers return empty refusal lists): 4 of 6 cases redden. Reverted.

## 2. T06 — the update path: an upgrade is a reinstall, and nothing checks the network

**The plan's basis.** The clean-Windows drill is "install → launch → upgrade
→ uninstall → rollback preserving user data" (§7's T09 row); the threat model
records "no telemetry, no update check, no CDN fetch". The update path is
therefore deliberately **not** an auto-updater: it is a newer installer run
over an older installation — the shape the T09 checklist's D12–D18 rows
already drill. What was missing was any witness holding that decision, so a
future `autoUpdater` import or a `publish:` block could arrive silently.

**The mechanism** (`shell/test/update-path.test.mjs`, new, 6 cases):
- no `autoUpdater` / `setFeedURL` / `checkForUpdates` / `electron-updater`
  in any runtime source;
- no `publish:` target and no update-provider setting in
  `electron-builder.yml`;
- the identity fields a reinstall needs are fixed: the manifest name
  `@labcairn/shell` (Electron derives `userData` from it — the T09 probe
  measured `%APPDATA%\@labcairn\shell` from exactly this value), the
  `appId: org.labcairn.shell` (NSIS upgrades in place by it), the
  `productName: LabCairn`, and a comparable semver version;
- `deleteAppDataOnUninstall` absent — the key whose presence makes an
  uninstall (and with it a downgrade rollback) destroy the user data;
- a counter-mutation case: planting each of the three (an updater word in
  `main.mjs`, a `publish:` block, a `deleteAppDataOnUninstall: true`) makes
  the same reads red.

**Why this is T06's whole remaining scope.** AC-2's lifecycle arms landed
with the skeleton and the follow-up batch (M5–M7 caught their removals); the
graceful-ask arm stays the owner's recorded §6.2 gap. What T06 still owed was
the update path's *statement*: the plan defers signing (W28) and names no
feed, so the honest mechanism is "reinstall preserves identity and data",
and now the tree watches that.

**Counter-mutations M3, M4** — `appId` changed to `org.labcairn.shell2`
(upgrade would install a second product): 1 case reddens.
`deleteAppDataOnUninstall: true` added: 1 case reddens. Both reverted.

## 3. T09 — who supplies the packaged run's backend and workspace

**The gap (§17's row, verbatim).** "Who supplies a packaged run's three
environment variables … The bundle's own path was closed on 2026-11-11 — a
packaged run now derives `resources/web-dist` — so only the backend and the
workspace remain to be supplied." The owner listed the decision as open; the
dispatch instructed this window to implement **both** candidate supplies,
drill each, and report a comparison for the owner to decide.

**The mechanism, way 1 — the environment.** `config.mjs` already reads
`LABCAIRN_SHELL_CLI` and `LABCAIRN_SHELL_WORKSPACE` from the environment.
What was missing was a *carrier*: nothing on the machine set them. New
`shell/labcairn-shell.cmd` ships in the package as a launcher template the
operator copies beside `LabCairn.exe`, edits once, and runs instead of the
exe. The environment remains absolute-paths-only (§4.1's no-cwd-guessing
rule, unchanged).

**The mechanism, way 2 — the package's own file.** New
`shell/src/shell-env.mjs` parses `resources/shell-env.json` (template
`shell/shell-env.template.json` ships beside the asar; it becomes live only
when the owner renames it). `config.mjs` reads it when the environment names
nothing. Precedence is explicit-wins: **environment beats file, per
variable** — the file is the package's default, the environment is the
operator's word. The file's `workspace` may be installation-relative
(`"LabCairn-workspace"` means *beside the resources directory, inside the
installation* — the same anchoring `resources/web-dist` already uses, not a
cwd guess); its `cliPath` may be absolute or — since §3.3 wired the frozen
backend into the package — installation-relative (`"backend/labcairn/labcairn.exe"`
means *under the resources directory*), anchored the same way; at this
section's commit it was absolute-only, and the template deliberately
shipped no `cliPath` because the backend's own arrangement (O3: frozen
service / bundled interpreter / sidecar) was still the owner's unmeasured
decision — an unmeasured arrangement must be a startup refusal, not a
guessed default. A broken file, an unknown field, or a `cliPath` that is
neither absolute nor installation-relative is a refusal at startup naming
the field — never silence.

**Dev is untouched.** A dev build reads no `shell-env.json` (witnessed): the
dev checkout keeps its own supply rule — the virtualenv's console script and
a workspace named in the environment.

**The drill** (`shell/scripts/rehearse-packaged-shell-env.mjs`, new): drives
the real `resolveRunConfig(env, { packaged: true, resourcesDir })` over real
files in a scratch root — way 1, way 2, the mixed case (environment covers
one side, file the other), and the two refusals (no supply at all; a broken
file). Measured live at this section's commit: **5 passed, 0 failed**,
refusals printed verbatim; §3.3's batch rewrote the frozen-exe scenarios and
re-measured it at **8 passed, 0 failed** with a real freeze present (the
live frozen-service leg included). This
is the drill the T09 checklist's D10/D11 rows can now run against.

**The witnesses.** `shell/test/shell-env.test.mjs` (new, 9 cases at this
section's commit; 14 after §3.3 added the installation-relative `cliPath`
forms): parse,
unknown-field refusal, relative-CLI refusal, non-string refusal, broken JSON,
installation-relative resolution, absolute pass-through, and the
no-resources-anchor refusal. `shell/test/config.test.mjs` grew 5→9 cases
(→10 after §3.3's shipped-template scenario):
the file read, per-variable precedence both ways, dev-reads-no-file +
packaged-refusal, and the broken-file refusal.

**Counter-mutations M2, M5** — the file read disabled (`read: false`):
3 of 9 config cases redden. The bundle derivation removed: 1 case reddens.
Both reverted.

**The two ways, compared — for the owner's decision:**

| | Way 1: environment via launcher | Way 2: package `shell-env.json` |
|---|---|---|
| What the operator edits | a `.cmd` beside the exe, or a shortcut's target | one JSON file inside `resources/` (or a renamed template before install) |
| Survives a reinstall? | yes (lives outside the app dir) — but a new install puts `LabCairn.exe` in a fresh dir, so the launcher must be re-copied | no — every reinstall resets `resources/`, so the file must be re-edited after each upgrade (the drill's D12 would catch a lost file as a launch refusal) |
| Per-machine values (workspace on D:, CLI on C:) | natural: each machine edits its own launcher | possible but the file sits inside the installation, so re-edits collide with upgrades |
| Discoverability | the refusal names the variable; the operator must know the launcher exists | the file is in the package; the refusal names the file and the field |
| Precedence when both present | wins (per variable) | covers only what the environment names nothing for |
| This window's reading | the **better operator surface** for real machines: outside the app dir, survives reinstalls, one obvious place per machine | the **better default surface**: ships with the package, works with no external step, right for a first install that has not earned a launcher yet |

**Recommendation.** Keep both, with way 2 as the package's default and way 1
as the operator override — which is exactly the precedence implemented. The
decision that still belongs to the owner is not "which file" but **what
`cliPath` names**: the O3 arrangement (frozen service / bundled interpreter /
sidecar) is unmeasured, so no template can name a backend that exists. Until
O3 is decided, a packaged run with the file's `cliPath` left `null` refuses
at startup with a message naming both supplies — the honest state, and the
one the drill demonstrates.

### 3.1 The owner's decisions, 2026-11-14 — the mixed supply, and a frozen backend

**Both open questions were decided on 2026-11-14** (owner's decision material:
`DECISION-BRIEF.md` in the T09/O3 decision folder; the work orders' O3 row in
`PHASE_3-work-orders.md` §17 carried the question). The two decisions and
what landed in this tree because of them:

**Decision 1 — the supply is mixed.** `workspace` is supplied by the
package's own `resources/shell-env.json` in its installation-relative form
(`"workspace": "LabCairn-workspace"`, the same anchoring
`resources/web-dist` already uses — no machine path travels in the file, and
an upgrade does not carry a stale absolute path); `cliPath` is supplied by
the launcher script (way 1) until the packaged backend exists, after which it
joins the file too. **Why the mix wins** (the brief's reasoning, measured not
asserted): the per-variable precedence (environment beats file) was already
implemented and drilled, so the mixed arrangement ran with **zero code
change** — the template edit below is a data change, not a mechanism change;
the installation-relative workspace form is the cleanest upgrade story; and
any `cliPath` written into the template today would name a backend the
package does not carry yet, which is a guess, and §4.1's rule stands: a
guessed default is a refusal, not a value. **What changed in the tree:**
`shell/shell-env.template.json` now ships exactly
`{"workspace": "LabCairn-workspace"}` — the `_comment` field is gone (the
parser refuses any unknown field, and the comment was a field the parser
would have rejected the moment the owner renamed the template live), and
`cliPath` is absent rather than `null` (an absent field is the honest
"nothing names this yet"; a `null` field survives only as a refused-value
placeholder). The parser's own rule — unknown field refused, absent field
skipped — is unchanged, and the witnesses
(`shell/test/shell-env.test.mjs` 9 cases at this section's commit — 14 after
§3.3 —, `shell/test/config.test.mjs` 9 — 10 after §3.3 —, the 7-scenario
drill at this section's commit, 8 after §3.3's
installation-relative scenario rewrote the frozen-exe supply) all pass on
the edited template's shape.

**Decision 2 — the backend is a frozen service.** `labcairn.cli:main` frozen
with PyInstaller into a onedir `labcairn.exe` carried in the installer's
`extraResources`. **Why frozen wins** (the brief's reasoning): the existing
`ServiceSupervisor` spawn path (`command + args`) is unchanged — the command
becomes the frozen entry, every argument the same; the package is smaller
than a bundled interpreter (the venv is 644 MB across 380 packages; the
freeze measured below is a fraction of that); no interpreter bootstrap at
startup; and the upgrade face is a whole-directory replacement, which is
what the existing NSIS overwrite install already does. A sidecar interpreter
is what the installer cannot carry (measured 2026-11-11: the package carries
no Python at all), and a bundled interpreter is the heaviest of the three.
**What landed in this tree** for the decision: the build tool
`shell/scripts/build-backend-freeze.mjs` (§3.2) and the drill's frozen-exe
supply scenario (§3.3), both measured below. **The installer now carries
the freeze**: the `extraResources` wiring, the input guard and the
installation-relative `cliPath` landed in the same record's §3.3, measured
against a real package whose own file names the frozen exe.

### 3.2 The frozen service, measured on this machine

**The build tool** (`shell/scripts/build-backend-freeze.mjs`, new): freezes
`labcairn.cli:main` — the exact function `pyproject.toml`'s console script
names — with PyInstaller into `shell/build/backend-freeze/labcairn/`
(onedir; `.gitignore` excludes `shell/build/`, so the product is
reproducible from the tree and never tracked). The tool refuses to run
without PyInstaller importable from the project virtualenv (it is a
freeze-time tool, installed with `uv pip install pyinstaller`, not a
runtime dependency in `pyproject.toml`), and it sets
`PYDANTIC_DISABLE_PLUGINS=1` for the freeze and the frozen run — the
measured reason is below. It also copies the checkout's `migrations/` tree
into the bundle: inside a frozen exe, `labcairn.db.migrations` resolves its
repository root to the bundle directory, so the schema must live at
`<bundle>/migrations/` exactly as it lives at `<checkout>/migrations/` in a
development run — the same copy the installer's `extraResources` wiring
will make. One measured gap surfaced here and is recorded as found: the
refusal text says "point `LC_MIGRATIONS_DIR` at one", but **no product code
reads `LC_MIGRATIONS_DIR`** (grep across `src/` finds the name only in that
error string) — a named override that does not exist, now visible because
the frozen run genuinely needs an override. Fixing the message or wiring
the variable is backend-side work outside this shell batch; the freeze
tool's bundle copy is what makes the frozen exe work without it.

**The freeze, measured 2026-11-14 on this machine** (PyInstaller 6.22.3,
Node v24.16.0, the project venv's Python 3.12): build exit 0 in **88.3 s**;
the onedir bundle is **226,263,914 B (~216 MB)**, the frozen `labcairn.exe`
itself **45,344,524 B (~43 MB)**; the exact bytes are printed by the tool's
summary line (`bundle`, `exe`, `bytes`, `seconds`), so the next re-measure
reads them from the tool rather than from this sentence.

**The one flag the freeze needs, and why.** Without
`PYDANTIC_DISABLE_PLUGINS=1` the frozen exe dies at import:
`labcairn.api.app` → `fastapi.exceptions` (module-level `create_model`) →
pydantic's plugin machinery → `logfire.integrations.pydantic`
(`_patch_PluggableSchemaValidator`, line 460) → `inspect.getsource` →
`OSError: could not get source code`. A frozen application carries no
source text, and logfire's pydantic plugin — a transitive of
`pydantic-ai`'s `logfire` extra; no product file imports logfire — reads
its target's source text at import time to patch a known pydantic bug.
With the flag set, the same frozen tree prints `frozen import ok: True`
and exits 0. This reproduces, on this tree, the failure the 2026-11-11
selection measurement found (its §5); the flag is now carried by the build
tool so the drill and any later installer work inherit it. **Open, named:**
whether the shipped build should instead drop the `logfire` extra from the
dependency graph (the product never imports logfire) is a dependency
decision that belongs to the owner; the flag is the honest state until
then.

**The frozen exe as `cliPath`, measured.** With a real freeze present, the
drill's live leg drives the frozen exe end to end: `labcairn init`,
`task create`, then `serve --host 127.0.0.1 --port <free> --json` from the
frozen exe — the same spawn shape `ServiceSupervisor` uses. The service
prints its start line, `GET /health` answers 200 (**connected** — the
state `main.mjs` reports as `sendStatus('connected', …)`), the shell would
load the served origin (**loaded** — the `loaded <url>` line `main.mjs`
prints after `loadURL`), and the page's guard probe is **granted** by
sender origin (`guard-request granted origin`, the line `live-guard.mjs`
prints and the live-guard drill reads). The frozen exe's session token is
minted to the workspace like any run's
(`<workspace>/.labcairn/session-token`), and a token-carrying
`POST /task/select` is routed by the real API surface — measured
**422** (the route's own validation answer for a request without a
selectable task, not 401 and not 404), which is the frozen entry proving
it *is* the product's service and not a stub: the route exists, the guard
admitted the token, and the contract layer answered. On a machine with no
freeze, the two parse-level frozen-exe scenarios still run (on the
packaged absolute-path form) and the live leg is skipped with the reason
printed — the supply machinery is witnessed either way.

### 3.3 The frozen backend rides in the package — the O3 wiring, measured 2026-11-14

**The supply decision's second half is now in the tree.** The owner's
decision put the frozen backend inside the package; this batch wired it:

- `electron-builder.yml`'s `extraResources` carries the whole onedir freeze
  at `resources/backend/labcairn` — the exact directory
  `shell/scripts/build-backend-freeze.mjs` produces (exe, `_internal/`,
  `migrations/`), filter `**/*`, nothing else named.
- The packaging guard is now `shell/scripts/require-package-inputs.mjs`
  (renamed from `require-web-dist.mjs`): the `beforeBuild` hook checks both
  inputs and **throws** — so electron-builder stops the run before anything
  is written — when the web bundle is absent/empty/no-index.html, or when
  the frozen backend is absent (the refusal names
  `build-backend-freeze.mjs`, the tool that produces it), not a directory,
  missing its `labcairn.exe`, or missing its `migrations/alembic.ini` (a
  frozen exe without the schema refuses `init`). electron-builder's own
  behaviour — one `file source doesn't exist` warning line per missing
  path, then a successful build — is the failure this guard exists to stop;
  measured on 2026-11-11 with the bundle, re-measured on 2026-11-14 with
  the backend.
- The template now names the backend in the file's installation-relative
  form: `{"cliPath": "backend/labcairn/labcairn.exe", "workspace":
  "LabCairn-workspace"}`. **cliPath semantics, decided and implemented:**
  the parse layer accepts an absolute path *or* an installation-relative
  path (at least one directory step, no `..` escape, never a bare name — a
  bare `labcairn.exe` is a PATH lookup, §4.1's cwd guess, and stays a
  refusal); a relative value is anchored **under the resources directory**
  by the new `resolveShellEnvCliPath`, the same anchoring the
  installation-relative workspace already uses beside it. The environment
  still accepts absolute paths only. The launcher template
  (`labcairn-shell.cmd`) names the packaged backend path in its EDIT-ME
  lines and notes it is the override, not a requirement.
- **The child's plugin flag rides the supervisor's one spawn path.** The
  packaged drill's first live attempts measured two refusals the
  parse-level drill could not see: the frozen exe behind a package whose
  supervisor predated the flag died at import with logfire's pydantic
  plugin reaching for source text (`OSError: could not get source code`),
  and a package whose file named the bundle *directory* instead of the exe
  died with `spawn …\backend\labcairn ENOENT` — the supervisor spawns a
  file, so the installation-relative value names the exe. The fixes:
  `ServiceSupervisor` sets `PYDANTIC_DISABLE_PLUGINS=1` on every child's
  environment (the one spawn path, all run modes, no launcher has to
  remember it), and the template names
  `backend/labcairn/labcairn.exe`.

**The build, measured on this machine** (electron-builder 26.18.0, Node
v24.16.0): three packaging runs, all exit **0**. `pnpm --dir shell run
dist` with `LABCAIRN_SHELL_DIST_DIR` outside the repository; the final run
built `LabCairn Setup 0.0.0.exe` **234,325,233 B (~223.5 MB)**, sha256
`9805be54821ae8af549bb7cd2e3c9924186550127005130004680e4ff5e155c4` — the
2026-11-11 installer without a backend was 124,568,971 B, so the frozen
service is the ~110 MB difference (the freeze itself: 226,476,027 B in
131.7 s per the tool's summary line). Packaged `resources/` now carries
exactly: `app.asar`, `app.asar.unpacked`, **`backend/labcairn/`** (exe
45,344,524 B, `_internal/`, `migrations/`), `elevate.exe`,
`labcairn-shell.cmd`, `shell-env.template.json` (the installation-relative
form above), `web-dist`. Hashed with `shell/scripts/installer-hash.mjs`.

**The packaged-run drill, measured against the real unpacked package**
(`E:\labcairn-local\shell-o3-package\dist3\win-unpacked`, driver
`drill-package-live-dist3.cmd` outside the repository): the template is
renamed live, the environment names nothing, and the packaged
`LabCairn.exe` resolves both variables from its own `shell-env.json` —
`cliPath` anchored under resources, `workspace` anchored beside them. The
package's own frozen exe then runs the startup sequence its supervisor
will (`init`, `task create` — the product refuses an uninitialised
workspace with `workspace_not_initialised` and a serve without a current
task with `task_not_selected`, both measured before the pass). The live
result, verbatim from the drill's captured stdout:

```
status connected: service at http://127.0.0.1:49501
service origin=http://127.0.0.1:49501
child pid=24796
status connected: service at http://127.0.0.1:49501
loaded http://127.0.0.1:49501/
guard-request granted origin http://127.0.0.1:49501
mutation refused: 401 session_required (sender origin http://127.0.0.1:49501)
```

**connected → loaded → granted**, against the backend the package itself
carries: the supply is closed end to end. The trailing `401
session_required` is the page's tokenless probe being refused by the
service's own guard — the expected answer, and the same shape the
live-guard drill measures. What this section does **not** claim: a
signature (W28 stands), a clean-Windows install (AC-6 stays the owner's
human run), or that NSIS's own install/uninstall arms have been driven
(only the unpacked tree has been, which is what T09's supply question
named).



## 4. T05 — packaging: the hash is a tool, the templates ship, the build stays green

**What was already measured** (2026-11-11 build report, referenced not
carried): the minimal unsigned NSIS config builds and exits 0 with and
without the bundle; the `beforeBuild` guard turns a missing `web/dist` into
a build failure. **What this window added:**

- `shell/scripts/installer-hash.mjs` (new): the installer's sha256 — the
  number the T09 checklist's D01 row and every acceptance record quote — is
  now a re-runnable tool printing JSON (`artifacts` + `winUnpacked`, each
  with bytes and sha256), instead of a hand-measured value nobody can re-run.
  Exercised on a scratch dist and on the real build below.
- `electron-builder.yml` ships the two T09 supply templates via
  `extraResources` (`shell-env.template.json`, `labcairn-shell.cmd`). The
  live name `shell-env.json` is **not** shipped — a template is not a
  default — and `packaging-config.test.mjs` watches both facts (case 15).
- **The build re-measured with the templates added**: `pnpm --dir shell run
  dist` → exit **0**; `LabCairn Setup 0.0.0.exe` 124,568,971 B, sha256
  `618f45b5…d470`; packaged `resources/` carries exactly `app.asar`,
  `app.asar.unpacked`, `elevate.exe`, `labcairn-shell.cmd`,
  `shell-env.template.json`, `web-dist`. Hashed with the new tool; raw values
  in §0's table.

## 5. Witnesses, counts, and what watches them

The table below was measured at §3.1–§3.2's commit (`0acd146`); §3.3's
wiring batch re-measured the files it touched (2026-11-14, same machine and
Node): `shell-env.test.mjs` 10 → **14** (the installation-relative `cliPath`
forms), `config.test.mjs` 9 → **10** (the shipped template's shape resolving
against a scratch resources tree), `packaging-config.test.mjs` 15 → **17**
(the frozen backend in `extraResources`, the input guard's two refusals and
its shape), and the full suite **114 pass / 0 fail** (run twice: before the
record edits and after them). `tests/test_shell_ci.py` 19 pass with the
floors re-anchored to this tree (`CASE_FLOORS_MEASURED_AT` =
`49a0d20f9cf3f9463745ba41967519bc26d41354`, full SHA from `git rev-parse`);
`tests/test_no_reference_leakage.py` 110 pass, run alongside.

| file | cases | status |
|---|---|---|
| `shell/test/command-line.test.mjs` (new) | 6 | 6 pass; M1 reddens 4 |
| `shell/test/shell-env.test.mjs` (new) | 9 | 9 pass |
| `shell/test/update-path.test.mjs` (new) | 6 | 6 pass; M3/M4 redden 1 each |
| `shell/test/config.test.mjs` (5 → 9) | 9 | 9 pass; M2 reddens 3, M5 reddens 1 |
| `shell/test/packaging-config.test.mjs` (14 → 15) | 15 | 15 pass |
| full `node --test shell/test/*.test.mjs` | 106 | 105 pass, 1 fail — the known base-lag case (`installer-binaries` §6(b) state read), fixed on `main` by `72cf219`; 9/9 on `E:\LabCairn` at `87c764f` |
| `tests/test_shell_ci.py` (floors re-anchored) | 19 | 19 pass |
| `tests/test_no_reference_leakage.py` (untouched, run alongside) | — | 129 passed together with the shell CI file |

**The floors moved to this tree on purpose.** Three new `shell/test/*.mjs`
files arrived, and `test_shell_ci.py`'s own witness refuses a file with no
recorded floor; `SHELL_CASE_FLOORS` now carries `command-line: 6`,
`shell-env: 9`, `update-path: 6`, and the two raised floors, with
`CASE_FLOORS_MEASURED_AT` re-anchored to `0acd146d30b1b4b563ea047adbd2b8063ca19993`
(full SHA from `git rev-parse`, printed). This is the project's rule — a
value that can change is re-measured, not carried forward — applied to the
counts the ledger cannot read. The floors are **floors with an anchor, not
hard equalities**: a legitimate new case in an existing file does not edit
this file.

**One correction this batch made to its own work.** `update-path.test.mjs`'s
counter-mutation first planted an import-shaped string (`from 'electron'`),
and `tests/test_shell_ci.py`'s static import reader — the one that keeps
`shell.yml` honest about installing no packages — read the witness's own
mutation string as the package `electron` and went red. The plant is now a
bare word, so the reader sees no package and the mutation still reddens the
banned-word check. The lesson is the project's own: a witness must use the
shape the watcher reads, and a string inside a witness is still text the
watcher reads.

**Witness ledger** (`python scripts/witness_ledger.py 4516793 0acd146`):
`3649 test functions` before, `3649` after — **LOST -- none**. Every test
function that existed before still exists; the five new Node files are
counted by the floors, not the ledger, by the contract `test_shell_ci.py`
states in its own header.

## 6. What this record does not claim

- **No AC-6 verdict.** The clean-Windows drill is the owner's human run; the
  2026-11-11 checklist's blocked rows (D11, D12, D13, D18) were blocked on
  exactly the supply this window implemented, and the drill can now proceed
  against a rebuilt package. The board row does not move here.
- **No signed installer, no install/uninstall drive.** §3.3's drill runs the
  unpacked package tree; the NSIS installer is built and hashed but its
  install, upgrade and uninstall arms stay with the owner's checklist. W28
  stands; the build log prints `no code signing certificate configured,
  signing is skipped` four times, and the config carries no signing key
  (witnessed).
- **The backend ships, but its dependency question stays open.** The frozen
  exe needs `PYDANTIC_DISABLE_PLUGINS=1` because logfire's pydantic plugin
  (a transitive of `pydantic-ai`'s `logfire` extra; no product file imports
  logfire) reads source text a frozen application does not carry. Whether
  the shipped build should drop the extra from the dependency graph remains
  the owner's dependency decision; the flag is now set at the supervisor's
  one spawn path, so the packaged run is self-contained either way.
- **No CI run, no pull request, no push.** Local evidence only, per
  `CLAUDE.md` and the owner's batching decisions.

## 7. Left on the machine

- `E:\labcairn-local\tmp\t05-dist-check\` — the built installer (delete
  freely; it is reproducible from the tree).
- `E:\labcairn-local\tmp\t05-hash-drill\` — the hash tool's scratch fixture.
- `E:\labcairn-local\tmp\lc-shell-env-*`, `lc-t09-drill-*`,
  `pytest-shellci*` — witness and pytest scratch, already emptied or
  ephemeral.
- `E:\labcairn-local\shell-o3-package\` (§3.3's drill material): `dist\`,
  `dist2\`, `dist3\` — three packaging runs' outputs (dist3 is the quoted
  one), the drill driver `drill-package-live-dist3.cmd`, and the drill's
  captured logs under `drill\` (`out.log` holds the connected/loaded/granted
  lines quoted above). Delete freely; all reproducible from the tree.
- `E:\labcairn-local\tmp\probe-shell-env.mjs` — the parser's four-shape
  probe used while tuning the installation-relative refusal.
- Nothing was written under `E:\LabCairn` outside this worktree; the main
  checkout was used read-only for the base-lag comparison.
