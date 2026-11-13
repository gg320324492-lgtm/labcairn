# LC-P3-05 — T08's input policy, T06's update path, and T09's two supply ways

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commits named below; the tree moves. Follow the sentence,
not the number.

Anchors, printed live while this record was written (every value produced by
the command named under it; none carried from another record):

| what | value |
|---|---|
| branch | `claude/distracted-hertz-0c6868` (worktree `distracted-hertz-0c6868`) |
| base commit (local `main` at dispatch) | `45167933d422e424466e2e09bc91cbd759071d7f` (`git rev-parse HEAD`, printed) |
| commits this record describes | `0acd146d30b1b4b563ea047adbd2b8063ca19993` (implementation), `7048b20` (floor registration) — full SHAs from `git rev-parse`, not extrapolated |
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
cwd guess); its `cliPath` must be absolute, and the template deliberately
ships `cliPath: null` because the backend's own arrangement (O3: frozen
service / bundled interpreter / sidecar) is still the owner's unmeasured
decision — an unmeasured arrangement must be a startup refusal, not a
guessed default. A broken file, an unknown field, or a relative `cliPath` is
a refusal at startup naming the field — never silence.

**Dev is untouched.** A dev build reads no `shell-env.json` (witnessed): the
dev checkout keeps its own supply rule — the virtualenv's console script and
a workspace named in the environment.

**The drill** (`shell/scripts/rehearse-packaged-shell-env.mjs`, new): drives
the real `resolveRunConfig(env, { packaged: true, resourcesDir })` over real
files in a scratch root — way 1, way 2, the mixed case (environment covers
one side, file the other), and the two refusals (no supply at all; a broken
file). Measured live: **5 passed, 0 failed**, refusals printed verbatim. This
is the drill the T09 checklist's D10/D11 rows can now run against.

**The witnesses.** `shell/test/shell-env.test.mjs` (new, 9 cases): parse,
unknown-field refusal, relative-CLI refusal, non-string refusal, broken JSON,
installation-relative resolution, absolute pass-through, and the
no-resources-anchor refusal. `shell/test/config.test.mjs` grew 5→9 cases:
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
- **No backend in the package.** The installer still carries no Python; O3
  (frozen service / bundled interpreter / sidecar) remains the owner's
  unmeasured decision, and `shell-env.template.json` deliberately names no
  `cliPath`.
- **No signature.** `W28` stands; the build log prints `no code signing
  certificate configured, signing is skipped` four times, and the config
  carries no signing key (witnessed).
- **No CI run, no pull request, no push.** Local evidence only, per
  `CLAUDE.md` and the owner's batching decisions.

## 7. Left on the machine

- `E:\labcairn-local\tmp\t05-dist-check\` — the built installer (delete
  freely; it is reproducible from the tree).
- `E:\labcairn-local\tmp\t05-hash-drill\` — the hash tool's scratch fixture.
- `E:\labcairn-local\tmp\lc-shell-env-*`, `lc-t09-drill-*`,
  `pytest-shellci*` — witness and pytest scratch, already emptied or
  ephemeral.
- Nothing was written under `E:\LabCairn` outside this worktree; the main
  checkout was used read-only for the base-lag comparison.
