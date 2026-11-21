# LC-P3-05 — AC-6's clean-Windows drill, run on this machine (2026-11-20)

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commits named below; the tree moves. Follow the sentence,
not the number.

Anchors, printed live while this record was written (every value produced by
the command named under it; none carried from another record):

| what | value |
|---|---|
| drill date | 2026-11-20 (the run started at 00:35 +08:00 and the last arm finished at 00:43 +08:00) |
| machine | `DESKTOP-BJJHSDF`, the owner's own workstation. OS: `Microsoft Windows 11 专业版` (Windows 11 Pro), version 10.0.26300, build **26300.9711**, `DisplayVersion` 26H2, 64-bit (`Get-CimInstance Win32_OperatingSystem`; `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`) |
| the account the drill ran as | `DESKTOP-BJJHSDF\pc` — **an administrator** (`[Security.Principal.WindowsPrincipal].IsInRole(Administrator)` → `True`). The drill did not use a separate account: see §6 |
| FROM installer | `LabCairn Setup 0.0.0.exe`, 234,325,233 B, sha256 `9805be54821ae8af549bb7cd2e3c9924186550127005130004680e4ff5e155c4`, from `E:\labcairn-local\shell-o3-package\dist3\` (`sha256sum`, `stat`) |
| TO installer (the trial) | `LabCairn Setup 0.0.1.exe`, 234,466,054 B, sha256 `79b7f0bd21b741243dfd59f86419ccacabd279a0c943b0ac55213c1654764ed3`, from `E:\labcairn-local\p308-trial-run\installer\` (`sha256sum`, `stat`) |
| where the two packages came from | both **built on this machine, no transfer, no Mark-of-the-Web** — the SOP's note (`E:\labcairn-local\p307-nsis-arms\SOP.md` §0) names the trial package as the LC-P3-08 one, rebuilt 2026-11-16 from `main` `da433d5`; the 0.0.0 baseline was built 2026-11-14 and the drill's own checklist records its commit. **No package was rebuilt here**, so those provenance statements are cited, not re-measured |
| the tree this record was written on | `43a2b87ad9c74bde8d9fe32e6a643cc4d3824eb1` (`git rev-parse HEAD`) |
| the drill folder | `E:\labcairn-local\ac6-host-drill-20261120` — outside the repository; the evidence, the backup and the scripts live there |
| the evidence runs | `evidence\run-20261120-003558` (the FROM package, all arms), `evidence\run-20261120-003907` (the cross-version upgrade), `evidence\run-20261120-004128` (the trial package, all arms), `evidence\run-20261120-004310` (the D17 launch half over the reinstalled trial tree), `evidence\run-20261120-005718` (the install arm again, with the corrected check of §3.2) — each with its own `RUN-SUMMARY.txt` |
| the machine-wide diff | `machinewide-before.txt` and `machinewide-after.txt`, **483 lines each, `diff` reports no difference** (`diff` exit code 0) |
| the restore | the two trees are **identical byte for byte**: the install tree 2,989 files and the userData tree 124 files, with 0 missing, 0 differing in size, 0 differing in content and 0 extra on both sides (`verify-the-restore.py`, which compares sha256 per file) |
| run type | **locally measured, on the owner's own machine, on a cleaned baseline**. No CI run was started, no pull request was opened, nothing was pushed (`CLAUDE.md`; `PHASE_3-work-orders.md` §3 rule 7) |

**What this record is.** The record of AC-6's clean-Windows drill, run on
2026-11-20 with `E:\labcairn-local\p307-nsis-arms\run-arms.ps1` and the
trial package the trial distributes. It claims what the drill measured and
what it did not, and it does **not** close a gate: the HUMAN-CHECK rows the
drill's tick-sheet reserves for a person are listed in §7, one of them is
still open, and the board row for `LC-P3-05` is not moved here.

---

## 1. The baseline — the four readings, before and after the clean

The drill's card S01 asks four questions, and all four are asked **per
user**. On this machine the answer was "dirty" before the drill: the
application was installed for this account and its userData held the
owner's own workspace.

| reading | before | after the clean |
|---|---|---|
| 1 — a `LabCairn` process running | none | none |
| 2 — `%LOCALAPPDATA%\Programs\LabCairn` | **present** (2,989 files, 582.7 MB) | absent |
| 3 — a `LabCairn` row under HKCU's uninstall key | **1 row** (`LabCairn 0.0.1`, DisplayVersion 0.0.1) | 0 rows |
| 4 — `%APPDATA%\@labcairn` | **present** (124 files, 17.3 MB — the owner's workspace) | absent |

The clean was preceded by a backup, so nothing of the owner's was lost:
both trees were copied to `E:\labcairn-local\ac6-host-drill-20261120\backup\`
(2,989 files / 582.7 MB and 124 files / 17.3 MB) and the registry row's
subkey name was recorded (`662f27fd-e6bf-5483-90f8-f0edb03d7828`).

**The clean was the product's own uninstaller**, run silently
(`Uninstall LabCairn.exe /S`, exit code 0), followed by the removal of the
install tree, the userData tree and the registry row.

**One observation the drill did not expect.** Immediately after the
uninstaller finished, `%APPDATA%\@labcairn` was **back**, holding 53 files
that are all Chromium caches (`shell\Cache`, `shell\Code Cache`,
`shell\GPUCache`, `shell\blob_storage`, …). A second removal with no
`LabCairn` process running left it gone for 30 seconds of watching, so
something in the uninstall path recreates the cache directory; **which
process did it was not established**, and the drill does not claim it did.
The drill's own D16 reading (the userData survives the uninstall) passed
with the userData at 61 files.

**The machine was put back** after the drill: the install tree and the
userData tree were mirrored back from the backup (`robocopy /MIR`), the
readings are back to "dirty" (§1's table), and the two trees are identical
to the backup **byte for byte** (0 missing, 0 differing in size, 0 differing
in content, 0 extra). The registry row is the row the product's own
installer wrote, naming the same DisplayName (`LabCairn 0.0.1`), the same
DisplayVersion (`0.0.1`) and the same uninstall path inside the restored
directory. The original row was **not** exported — `reg.exe export` was
called with a rewritten path and produced no file — so the registry is
restored to an equivalent row, not to a byte-identical one. That
difference is stated rather than hidden.

---

## 2. The arms, and what each one read

`run-arms.ps1` prints `[PASS]` / `[FAIL]` / `[HUMAN-CHECK]` lines and leaves
evidence per run. The verdicts below are quoted from the four
`RUN-SUMMARY.txt` files named in the anchors table.

### 2.1 The FROM package on a clean machine — two failures, one cause

`run-20261120-003558`, `LabCairn Setup 0.0.0.exe` (sha `9805be54…`):

| check | verdict |
|---|---|
| silent install (exit 0), install directory appears, HKCU uninstall entry appears | PASS |
| `resources\app.asar`, `app.asar.unpacked`, `elevate.exe`, `labcairn-shell.cmd`, `shell-env.template.json`, `web-dist` present | PASS |
| frozen backend ships and carries its migrations | PASS |
| **no live `shell-env.json` ships (template only)** | PASS |
| web-dist carries the bundle (4 files), uninstaller present | PASS |
| as-installed launch refuses (exit 1) and the refusal names `LABCAIRN_SHELL_CLI` | PASS |
| **the materialized `shell-env.json` workspace resolves to the `%APPDATA%` workspace this arm drives** | **FAIL** — *file said: `LabCairn-workspace`; arm uses: `C:\Users\pc\AppData\Roaming\@labcairn\workspace`* |
| workspace init + task create (exit 0, current_task bound) | PASS |
| **launch reaches the service origin line** | **FAIL** — the child said `{"reason":"workspace_not_initialised","message":"…\LabCairn-workspace is not a LabCairn workspace: there is no …\.labcairn\workspace.json…"}` |
| upgradeSame (reinstall over the live install), uninstall (install tree gone, HKCU row gone, **userData retained**), reinstall (tree identical) | PASS |

### 2.2 The cross-version upgrade — all green

`run-20261120-003907`, the FROM package over the trial package:
**ALL AUTOMATED CHECKS PASSED** — the 0.0.1 installer over the 0.0.0
install (exit 0), the HKCU entry reading `LabCairn 0.0.1` / DisplayVersion
`0.0.1`, the installed `LabCairn.exe` ProductVersion `0.0.1.0`, exactly one
LabCairn directory, and the userData surviving the upgrade with its file
count unchanged.

### 2.3 The trial package on a clean machine — one failure, and it is the arm's

`run-20261120-004128`, `LabCairn Setup 0.0.1.exe` (sha `79b7f0bd…`):

| check | verdict |
|---|---|
| silent install, install directory appears, HKCU entry appears, `registry: DisplayName=LabCairn 0.0.1 DisplayVersion=0.0.1`, `ProductVersion 0.0.1.0` | PASS |
| the six `resources\` entries, the frozen backend and its migrations, web-dist (4 files), the uninstaller | PASS |
| **no live `shell-env.json` ships (template only)** | **FAIL** — see §3.2; the check was corrected after this run, and the corrected check passes (`run-20261120-005718`) |
| **`shell-env.json` workspace resolves to the `%APPDATA%` workspace this arm drives** | **PASS** |
| workspace init + task create (exit 0, current_task bound) | PASS |
| **launch reaches the service origin line** — service port 62912 | **PASS** |
| `GET /health` answers ok; health names the current task; `GET /` serves the web bundle (200); `POST /task/select` with the token answers 200 (granted) | PASS |
| second instance exits 0 without starting a second service | PASS |
| the shell is still running before the stop; it exits on the graceful stop (WM_CLOSE); **no orphaned service child after the stop** | PASS |
| upgradeSame over the live install, uninstall (install tree gone, HKCU row gone, **userData retained**), reinstall (tree identical to the first install, userData retained through it) | PASS |

### 2.4 The D17 half, over the reinstalled trial tree

`run-20261120-004310`: the launch arm again, over the tree the reinstall
left behind and over the `%APPDATA%` workspace that survived it. Every
automated check PASSed — the workspace was already initialised and already
had a current task, so no re-init was needed, and the service came up on
the same terms as the first launch. **All automated checks passed.**

---

## 3. The two findings

### 3.1 The 2026-11-14 baseline package cannot launch on a clean machine

The FROM package ships a **pre-O3 template**: its
`resources\shell-env.template.json` names the workspace `LabCairn-workspace`,
which is relative to the installation, and it does not materialise the live
config itself. On a machine that has never held the application, the service
child therefore refuses to start (`workspace_not_initialised`) and the shell
never reaches its origin line.

The repository's template is **not** like that — `shell/shell-env.template.json`
in this tree names `%APPDATA%\@labcairn\workspace`, which is O3's decision B
(2026-11-15): the workspace lives outside the installation, so the uninstall
leaves it behind. The trial package ships that corrected template, and its
installed `resources\shell-env.json` was read back to confirm it
(`{"cliPath":"backend/labcairn/labcairn.exe","workspace":"%APPDATA%\\@labcairn\\workspace"}`).

**So the defect is in the 2026-11-14 package, not in the delivered one.** It
does not affect the trial: the trial package installs, launches, upgrades,
uninstalls and reinstalls correctly on this machine, and the cross-version
upgrade from the old package to the trial one passes. It matters for two
reasons: the drill's upgrade arm *starts* from that package, so the baseline
of that arm is a package that cannot start on its own; and anyone still
holding the 0.0.0 build gets an application that does not run on a clean
machine.

### 3.2 The arm's "no live `shell-env.json` ships" check is out of date

The single failure in the trial run is the arm's check, not the artefact.
The current packaging design has the **installer** copy the template to the
live name, and the repository witnesses exactly that:

```
shell/test/packaging-config.test.mjs:394
  assert.match(include, /CopyFiles \/SOFT "\$INSTDIR\\resources\\shell-env\.template\.json" "\$INSTDIR\\resources\\shell-env\.json"/)
```

A package that ships only the template and has the installer materialise it
is what the tree requires; the check in `run-arms.ps1` was written for the
2026-11-14 packages, which predates that include, and it is red on every
package built from the current tree. **The drill's tooling has been
corrected, and the correction was run.** The check now reads the live
`shell-env.json` against the template and requires them to be **identical**
— which is what the installer's copy produces, and what forbids a
pre-edited configuration from being shipped in the package — and it stays
informative for the older packages, which carry no live file at all. The
premise was verified before the run, on an installed tree (the live file's
sha256 `B947A584…` is the template's sha256, so the corrected check reads
true), and the corrected script parses clean. The install arm then ran
again (`run-20261120-005718`) and read `[PASS] the live shell-env.json is
the template, copied by the installer`.

### 3.3 The workbench body was blank — cause not established

The trial run's HUMAN-CHECK row B9 asks whether the workbench renders in
the window, and not as the diagnostic page. Two screenshots were taken, 3
seconds and 8 seconds after the window appeared
(`E:\labcairn-local\ac6-host-drill-20261120\workbench-03000ms.png` and
`workbench-08000ms.png`, byte-identical). What they show:

- the window's chrome and its menu bar;
- the status strip reading **`LabCairn — connected   service at
  http://127.0.0.1:64688`** and **`session guard: 401 session_required`**;
- **an empty body** — neither the workbench nor the diagnostic page.

The `401 session_required` is the **designed** state and not a symptom: the
session guard refuses a mutation that carries no session token
(`shell/src/live-guard.mjs`), and the shell's own rehearsal asserts exactly
this pair of readings (`shell/scripts/rehearse-live-guard.mjs`: the strip
reads `connected` and the guard reads `401 session_required`).

The service side was healthy throughout: every API check in §2.3 passed,
the renderer loaded the document (the shell's own log: `loaded
http://127.0.0.1:62912/`), and the two files the document points at were
fetched by hand and both answer **200** (`/assets/index-DiUa8QSL.js`,
273,002 B; `/assets/index-Dl0e36iw.css`, 3,923 B). **The drill did not
establish why the body was blank**, and this record does not claim it did.
It is a question about the product, not about the drill.

---

## 4. "The installer stayed inside the per-user paths"

On a clean machine with a **non-administrator** account, this claim follows
from the account's privileges: an installer that reached outside the
per-user paths would have had to ask for elevation and would have failed.
This machine's account is an administrator, so the claim was made the other
way round — by **difference**.

The machine-wide state was listed before the drill and after it: the HKLM
uninstall keys (both hives), `C:\Program Files`, `C:\Program Files (x86)`
and `C:\ProgramData`. Both listings are 483 lines and **`diff` reports no
difference at all**. Nothing outside the per-user paths changed.

---

## 5. The deviations from the SOP's design, and why

| the SOP says | what happened | why |
|---|---|---|
| a **clean Windows VM** (the drill's own checklist: "owner, clean Windows VM") | the drill ran on **this machine**, on this account, after its footprint was removed and backed up | the owner directed it, and the four S01 readings are per user, so a cleaned per-user profile is a clean baseline by construction. The machine-wide state was left untouched (§4), and the machine was put back byte for byte (§1) |
| the account is **not** an administrator (§3.2 of the clean checklist) | the drill ran as `pc`, **an administrator** | the claim it would have carried is made by difference instead (§4). The account that would have carried it — a separate local account — was created on this machine (`drill`, non-administrator, in the Users group) but could not be used to run a process: `Start-Process -Credential` answers *拒绝访问* from both a filtered and an elevated token on this machine, while `LogonUser` succeeds — the logon works and the process creation does not. **The account was removed again after the drill, with its profile** (whose ACL named only the deleted account's SID, so removing it needed the ownership taken first), so the machine carries nothing of the attempt |
| the exes reach the drill machine by transfer, with a Mark-of-the-Web | both packages were **built here**, no transfer, no MOTW | they were built on this machine for the earlier drill; no package was rebuilt for this run, so no SmartScreen prompt is expected — which is what the HUMAN-CHECK row A3 asks the owner to record |
| a snapshot before the drill, so it can be repeated | the repeatability came from the **backup and restore** instead: the baseline is re-created by removing the footprint, and the machine is put back byte for byte | a snapshot of a per-user profile is not a thing; the backup is |

---

## 6. What the drill does not claim

- **No gate is closed by this record.** The HUMAN-CHECK rows of §7 are the
  owner's, and one of them (§7's B9) has an open question behind it.
- **No package was rebuilt**, and no package's provenance was re-measured;
  §2's package identities are the bytes that were on disk.
- **The drill's tooling has a stale check** (§3.2) that must be fixed
  before the next run is read as green.
- **The blank workbench body is unexplained** (§3.3).
- **The registry row was restored to an equivalent row, not a byte-identical
  one** (§1), because the original export failed.
- The host's Hyper-V guest was **not** used. It is a separate machine with
  its own problems — an evaluation licence whose period had expired, which
  made Windows shut it down every hour, and a clock 16 hours ahead of the
  host's — and the drill did not need it once the vehicle was the owner's
  own machine.

---

## 7. The HUMAN-CHECK rows, and the ones still owed

The drill's tick-sheet (`E:\labcairn-local\p307-nsis-arms\checklist.md`)
reserves these for a person. The readings this record can supply are in
the brackets.

| row | what it asks | where it stands |
|---|---|---|
| A3 | the OS build, how the exe reached this machine (SmartScreen/MOTW), and any dialog seen | [build 26300.9711, built here, no transfer, no MOTW, silent installs, no dialog] |
| B9 | the workbench renders in the window (not the diagnostic page); a screenshot | [two screenshots taken; the chrome and the strip render, the body is blank — §3.3. The owner's judgement, and the question behind it] |
| F2 | the signing status | [unsigned by decision — W28] |
| F3 | the support limits | [to be recorded by the owner] |
| F4 | the attestation that no COM/ProgID/macros/sendkeys/GUI-UI automation was used to open any document | [the drill opened no document; the screens were captured by a screen-region grab, and the shell was started and stopped by the product's own paths] |
| F5/F6 | the record itself | this file |

---

## 8. The evidence index (outside the repository)

`E:\labcairn-local\ac6-host-drill-20261120\`

| what | where |
|---|---|
| the four run folders and their summaries | `evidence\run-20261120-003558`, `-003907`, `-004128`, `-004310`, each with `RUN-SUMMARY.txt` |
| the userData snapshots the uninstall arm took | `evidence\snapshots\userdata-before-install.csv`, `-before-uninstall.csv`, `-after-uninstall.csv` |
| the machine-wide listings | `machinewide-before.txt`, `machinewide-after.txt` |
| the workbench screenshots | `workbench-03000ms.png`, `workbench-08000ms.png` |
| the backup of what was removed | `backup\install\` (2,989 files), `backup\userdata\` (124 files) |
| the scripts that prepared, ran and restored the drill | `Backup-And-Clean.ps1`, `Remove-UserData-Again.ps1`, `Run-The-Arms.ps1`, `Run-The-Arms-Trial.ps1`, `Capture-The-Workbench.ps1`, `Check-The-Bundle.ps1`, `Restore-The-Machine.ps1`, `verify-the-restore.py` |

Nothing in this record's evidence is inside the repository, and no document
was opened by any of it.

## Read 2026-11-21 — the B9 finding's disposition

The blank-workbench finding has a cause and a fix. The shell's preload
appended the status strip to `document.documentElement` at document-start,
which replaced the parser's position before `head` and `body` could be
placed; Chromium discarded the rest of the document silently, so `#root`
never existed and the workbench never mounted, while the idempotently
rebuilt strip kept reading connected (root cause reproduced and read
through CDP; see the `b9-root-cause-2026-11-21` hand-over note). The fix
landed on `main` as commit `eeb2eb7`: the strip mounts on `body`
(`documentElement` remains only the `about:blank` fallback) and the first
injection waits for `DOMContentLoaded`, and the rehearsal now asserts the
page itself — `hasBody`, `hasDoctype`, `hasRoot` and `#root`'s child count.
On this machine a clean one-shot run of the fixed preload renders the
workbench (`hasBody`/`hasDoctype`/`hasRoot` true, one root child). **B9's
formal closure still waits for the owner's re-run of the row on the target
VM, per the SOP.**
