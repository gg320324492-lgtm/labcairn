# LC-P3-05 — the installed-shell drill: install, launch, uninstall, reinstall

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commit named below; the tree moves. Follow the sentence,
not the number.

**Anchors, printed live while this record was written** — every value below
was produced on 2026-11-14 by the command named under it or beside it, on
this machine, from the artifacts named in §7; none was carried from another
record.

| what | value |
|---|---|
| tree the drill started from | `main` at `7a44f569ceafb4c5c284c183e764f53b8f6ad1af` (`git rev-parse HEAD`, printed) — the commit that wired the frozen backend into the installer (PR #166) |
| installer drilled | `E:\labcairn-local\shell-o3-package\dist3\LabCairn Setup 0.0.0.exe`, 234,325,233 B, sha256 `9805be54821ae8af549bb7cd2e3c9924186550127005130004680e4ff5e155c4` (`Get-FileHash -Algorithm SHA256`, printed; matches the value recorded in `LC-P3-05-input-update-supply-2026-11-14.md` §3.3) |
| Node | v24.16.0 (`node --version`) |
| install mode | NSIS `/S`, per-user (`perMachine: false`), no UAC prompt, installer exit **0** |
| install directory | `C:\Users\pc\AppData\Local\Programs\LabCairn` (read from the HKCU uninstall entry's `UninstallString` and from the directory itself) |
| registry uninstall entry | `HKCU\...\Uninstall\{guid}`: `DisplayName: LabCairn 0.0.0`, `DisplayVersion: 0.0.0` (read live, printed) |
| installed `resources/` | `app.asar` (1,926,082 B), `app.asar.unpacked/`, `backend/labcairn/` (`labcairn.exe` 45,344,524 B, `_internal/`, `migrations/`), `elevate.exe` (107,520 B), `labcairn-shell.cmd` (1,174 B), `shell-env.template.json` (86 B), `web-dist/` — counted with `ls -la` and `du -sb`, tree captured to `installed-tree.txt` (4,077 entries) |
| live `shell-env.json` in the installed package | **absent** — the installer ships the template only, exactly as the build record says (`ls resources/shell-env.json` → ENOENT, printed) |
| uninstaller | `Uninstall LabCairn.exe /S`, exit **0**, install directory and HKCU entry removed, `%APPDATA%\@labcairn\shell` retained (§4) |
| reinstall | same installer, exit **0**, byte-identical tree (4,077 entries, `diff installed-tree.txt installed-tree-reinstall.txt` → empty), `%APPDATA%\@labcairn\shell` retained (§6) |

## 1. What was drilled, and what the owner authorized

The 2026-11-14 acceptance record for T09's supply work
(`LC-P3-05-input-update-supply-2026-11-14.md`) ended with the packaging
drill run against the **unpacked** tree (`win-unpacked`). This record
closes the next gap: the **installed** experience — the NSIS installer run
for real, the shell started from `C:\Users\pc\AppData\Local\Programs\LabCairn`,
the frozen backend reached through the installation-relative supply, the
uninstaller run, and the same installer run again over the cleaned path.
The owner authorized this machine-local install/uninstall drill through the
decision dialog of 2026-11-14. Everything here is local evidence; no CI run
was started, no pull request was opened, and nothing outside the install
directory, the user data directory, and `docs/**` in this worktree was
touched.

The drill was driven as plain commands (PowerShell `Start-Process`, `curl`,
`node`) rather than through the T09 checklist's snapshot scripts, because
the checklist's own tooling targets a clean machine that this development
machine is not; where a checklist row is answered here it is named (D10,
D11, D14–D17). The row verdicts below are this drill's readings, not a
re-write of the checklist's verdicts.

## 2. Install (D-rows D01–D03 territory)

`LabCairn Setup 0.0.0.exe /S` exited **0** with no UAC prompt. The product
installed per-user to `C:\Users\pc\AppData\Local\Programs\LabCairn`
(`oneClick: false` + `/S` = silent default-location install; `perMachine:
false` in `shell/electron-builder.yml` — the config's own witness,
`shell/test/packaging-config.test.mjs`, asserts that setting). The HKCU
uninstall entry appeared with `DisplayName: LabCairn 0.0.0`.

The installed `resources/` carries exactly what the build record §3.3
lists (see the anchor table). The **template ships; no live
`shell-env.json` does** — `packaging-config.test.mjs` asserts the build
must not ship a live one ("a live shell-env.json must not be shipped by the
build"), and the installer honours that. The consequence is measured in §3.

## 3. Launch (D-rows D10, D11) — the headline finding

**The installed package does not start as-installed.** Running
`C:\Users\pc\AppData\Local\Programs\LabCairn\LabCairn.exe` with a clean
environment exits **1 in ~1.1 s** with the refusal

```
the shell failed: Error: LABCAIRN_SHELL_CLI must name the labcairn entry
point by absolute path (in a dev checkout, the virtualenv's console script;
in a packaged build, the environment or shell-env.json's "cliPath",
absolute or installation-relative such as "backend/labcairn").
```

(`launch-refusal-way2-absent.log`, captured twice: once through
`Start-Process` and once with the three supply variables explicitly
removed from the environment — identical refusal.) The asar was unpacked
and the installed `src/config.mjs` and `src/main.mjs` were diffed against
this tree at `7a44f56`: **byte-identical** (the only differences are a
leading blank line and a missing final newline — asar padding, not code).
The installed resolver does read `resources/shell-env.json`
(`packagedShellEnvPath` joins `resourcesDir` with `shell-env.json`, and
`readPackagedShellEnv` returns `{read: false}` only when the file is
absent). The refusal happens because **the file the resolver wants is not
there**: the build ships the template under its own name, and nothing in
the install path renames it. This is the T09 decision-pack's finding 1
("rename the template to shell-env.json as documented fails") resurfacing
one layer later: the decision removed the `_comment` field so a renamed
template would parse, but the installer does not perform the rename, so
the way-2 file supply is absent on the installed machine.

The refusal is the *designed* behaviour — §4.1's "a guessed default is a
refusal, not a value" — and it is honest: the package names no backend by
default, so the shell refuses rather than guessing. But it means the
installed product needs one operator action (or an installer change) before
its first launch. Both supply ways were then drilled on the installed
package:

- **Way 1 (environment), via the shipped launcher template's values.**
  `LABCAIRN_SHELL_CLI=C:\Users\pc\AppData\Local\Programs\LabCairn\resources\backend\labcairn\labcairn.exe`
  and
  `LABCAIRN_SHELL_WORKSPACE=C:\Users\pc\AppData\Local\Programs\LabCairn\LabCairn-workspace`
  set, `LabCairn.exe` launched: `ServiceStarting` in the drained log
  (`LABCAIRN_SHELL_LOG` pointed at the drill folder) after **2.3 s**, and
  the supervisor's readiness (start line **and** `GET /health` 200) held.
  The spawn was verified from the process table: the shell (pid 28100)
  parented the frozen exe with `--workspace …\LabCairn\LabCairn-workspace
  serve --host 127.0.0.1 --port 62564 --json --static-dir
  …\resources\web-dist` — the resolved values the record's supply decision
  intended. The page origin answered `/health` 200 and served the web
  bundle at `/` (200), and the granted probe
  (`POST /task/select` with the workspace's session token) answered **200**
  — connected → loaded → granted, the rehearsal's judgement sequence, on
  the installed package.
- **Way 2 (file), drilled honestly by materializing the file.** Copying
  `shell-env.template.json` to `resources/shell-env.json` (86 B, contents
  `{"cliPath": "backend/labcairn/labcairn.exe", "workspace":
  "LabCairn-workspace"}`) and launching with the three supply variables
  **removed** from the environment: `ServiceStarting` after **3.2 s**,
  `/health` 200, page 200, granted probe 200. The child's command line
  named the same resolved paths as way 1 — the installation-relative
  `cliPath` anchored under the installed `resources/`, the
  installation-relative `workspace` anchored beside it. The file was then
  removed again; the tree left behind is the as-built one (§7).

Two readiness behaviours were measured on the way that matter to the
checklist's diagnosis rows. First, with the workspace not yet initialized
(`labcairn init` had not run there), the shell did **not** crash: the
child refused with `workspace_not_initialised` in the drained log, the
supervisor surfaced the failure, and the window showed the diagnostic page
while the shell process stayed alive — the §4.3 "crash-before-ready" row's
visible-failure behaviour, observed rather than asserted. After
`init` + `task create` on the workspace (driven with the frozen exe, which
needs `PYDANTIC_DISABLE_PLUGINS=1` outside the supervisor — set by the
supervisor itself on the spawn path since `6e6b376`/`0a71e91`), the same
launch reached readiness. Second, a second-instance probe
(`/SECOND-INSTANCE-PROBE` argv, single-instance lock held by the first
shell) exited **0 in 6.2 s** with no second window — the T08 argv refusal
and the single-instance lock behaving as witnessed in the shell suite.

**Verdict for the checklist:** D10 (no-supply launch) now ends in the
designed refusal rather than the 2026-11-11 "no backend at all" gap — the
package carries the backend, and the refusal names the supply it is
missing. D11 (supply and launch) **passes on this machine** by way 1 and,
with the file materialized, by way 2. **The open product question is
narrower than it was:** the installer ships everything the resolver reads
except the renamed file itself. Whether the installer should write the
live `shell-env.json` at install time (and with which values) is an owner
decision on the supply design — this drill changes the evidence, not the
decision.

## 4. Uninstall (D-rows D14–D16)

`Uninstall LabCairn.exe /S` exited **0**. Measured afterwards:

- the install directory is gone (`Test-Path` → False);
- the HKCU uninstall entry is gone (enumerated the Uninstall keys, no
  LabCairn match);
- `%APPDATA%\@labcairn\shell` is **retained** — 110 files before the
  uninstall (the running shell's snapshot), 110 after, the only file-list
  difference being the transient `lockfile` the running shell held
  (Chrome's singleton lock; released by the exit, correctly absent after).
  This matches the T09 checklist's D16 expectation: the config sets no
  `deleteAppDataOnUninstall` (`shell/electron-builder.yml` carries no such
  key — grep clean), so user data survives uninstall by design.

D14/D15/D16: **pass on this machine.**

One honest note: the workspace lived **inside the install directory**
(`LabCairn-workspace` beside `resources/`, the installation-relative
anchoring the supply decision chose). Uninstall removed it with the
directory. That is the supply decision's own semantics — the workspace
anchor is the installation root — and it is recorded here so the D13/D16
"userData preserved" rows are read precisely: **Electron's `%APPDATA%`
userData survives; the LabCairn workspace inside the install tree does
not.** Whether the installed workspace belongs inside the install
directory is part of the same owner supply decision (an absolute workspace
path outside the install tree would survive uninstall; the
installation-relative form ties it to the product's lifetime).

## 5. userData across the launch (D-row D03/D13 substrate)

Snapshots (file lists + sizes, in the drill folder):
`userdata-snapshot-before-install-launch` (106 files, 14,816,716 B —
left over from the 2026-11-11 `win-unpacked` drills on this machine),
`userdata-snapshot-after-launch` (110 files, 15,356,680 B), and
`userdata-snapshot-after-uninstall` (110 files, 15,377,160 B). The launch
added only run-time cache material (HTTP cache entries, two preload code
cache blobs, the lockfile) and the uninstall removed only that lockfile.
No product data was deleted by either operation.

## 6. Reinstall over the cleaned path (D-row D17)

The same installer ran again (`/S`, exit **0**) onto the now-absent
directory. The reinstalled tree is **byte-identical** to the first
install's snapshot (4,077 entries; `diff` empty — same 4,077 relative paths
with the same lengths). The registry entry returned
(`LabCairn 0.0.0`). `%APPDATA%\@labcairn\shell` was retained (110 files;
vs. the running-shell snapshot the only differences are the transient
`Network/Cookies` journal pair and the lockfile — both live-state files,
not data loss). The reinstall launch reached `ServiceStarting` in **3.2 s**
after the workspace was re-initialized (`init` + `task create`), with
`/health` 200, page 200, and the granted probe 200.

D17's directory-and-userData halves **pass**; its "runtime state
continuity" half **fails as designed for this supply form**: the reinstall
wiped the install-directory workspace (it is inside the uninstalled tree),
so the first post-reinstall launch refused with `workspace_not_initialised`
until `init` ran again. That is the same finding as §4, seen from the
rollback direction: with an installation-relative workspace, "reinstall
preserves user data" is true for `%APPDATA%` and false for the workspace.
The checklist's D17 wording ("`userData` 与 workspace 完好") is only
satisfiable together when the workspace lives outside the install tree —
the owner's supply decision owns that placement.

## 7. Left on the machine

- `E:\labcairn-local\shell-o3-install-drill\` — this drill's evidence:
  the two refusal captures (`launch-refusal-way2-absent.log`,
  `service-log-way2-refusal.log`), the three `ServiceStarting` lines
  (`service-starting-line.txt` way 1, `service-starting-file-way.txt`
  way 2, `service-starting-reinstall.txt` reinstall), the three granted
  probe bodies, the two full install-tree snapshots (byte-identical),
  the three userData snapshots, the asar-extracted `config.mjs`/`main.mjs`
  used for the byte-diff, and the template-resolution probe
  (`probe-template.mjs`). Delete freely; every claim above re-runs from
  the installer plus these scripts.
- The installed product was **uninstalled after the drill** (final
  uninstall exit 0, directory gone, registry gone). `%APPDATA%\@labcairn\shell`
  remains, as designed.
- Nothing was written under `E:\LabCairn` outside this worktree's
  `docs/**`; the main checkout was not touched.

## 8. What this record does not claim

- **Not a clean-machine verdict.** This development machine carries the
  project venv, prior drill residue, and the 2026-11-11 userData history.
  The T09 checklist's clean-Windows rows stay `PENDING-HUMAN`; this record
  answers the machine-local install lifecycle the owner authorized.
- **No signature verification, no updater, no multi-user, no
  non-default install path.** `allowToChangeInstallationDirectory: true`
  means a user-chosen directory is possible; this drill used the default.
  The update path remains "reinstall" (T06), and the reinstall leg above
  is its first machine-local evidence.
- **The live-`shell-env.json` question is open, not resolved here.** The
  drill measured that the as-built installer starts only after an operator
  supplies the two values (way 1) or materializes the file (way 2). The
  product decision — installer writes the file, template renamed at build
  time, or launcher-only — belongs to the owner.
