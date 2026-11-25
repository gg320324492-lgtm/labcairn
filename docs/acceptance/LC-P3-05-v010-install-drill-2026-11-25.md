# LC-P3-05 — the v0.1.0 install drill, run on this machine (2026-11-25)

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the commits named below; the tree moves. Follow the sentence,
not the number.

Anchors, printed live while this record was written (every value produced by
the command named under it; none carried from another record):

| what | value |
|---|---|
| drill date | 2026-11-25 (the first reading was taken at 09:16:53 +08:00 and the last restore finished at 09:37:15 +08:00) |
| machine | `DESKTOP-BJJHSDF`, the owner's own workstation. OS: `Microsoft Windows 11 Pro`, version 10.0.26300, build **26300.9711**, 64-bit (`Get-CimInstance Win32_OperatingSystem`; the edition and the build from `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`: `EditionID` `Professional`, `DisplayVersion` 26H2, `CurrentBuild` 26300.9711 — `ProductName` in that key still reads `Windows 10 Pro`, which is that key's long-standing behaviour and is not a claim about this host) |
| the account the drill ran as | `DESKTOP-BJJHSDF\pc` — the account **is** a member of the local `Administrators` group (`net localgroup Administrators` lists `pc`), but **the processes this drill ran in were not elevated**: `[Security.Principal.WindowsPrincipal].IsInRole(Administrator)` returned `False` throughout. The Phase 3 drill of 2026-11-20 ran elevated; this one did not. See §4 |
| the trial installer | `LabCairn Setup 0.0.3.exe`, 354,229,356 B, sha256 `32bca39169e5c21b90c982edd7ad38a7c9be1a68b5961e8383e46ec14ec4a85c`, from `E:\labcairn-local\dist\v0.1.0\` (`sha256sum`, `stat`). The arms script read the same digest off the file it ran, independently (`installer-hash.json` in the arm's run folder): `32BCA39169E5C21B90C982EDD7AD38A7C9BE1A68B5961E8383E46EC14EC4A85C` |
| the FROM installer, arm 2 | `LabCairn Setup 0.0.3.exe`, 354,088,228 B, sha256 `681607c7de0a2963016ff461e8999cef4fda369fa27b896475b70f6466874588`, from `E:\labcairn-local\p308-trial-run\installer-0.0.3\` (`sha256sum`, `stat`; the arms script read `681607C7DE0A2963016FF461E8999CEF4FDA369FA27B896475B70F6466874588` off the file it ran) |
| the FROM installer, arm 3 | `LabCairn Setup 0.0.2.exe`, 354,088,311 B, sha256 `8d38177b5638e7b85f7b505438ab3321586c4320f21258f0b3da5275785cbda1`, from `E:\labcairn-local\p307-nsis-arms\dist-0.0.2\` (`sha256sum`, `stat`; the arms script read `8D38177B5638E7B85F7B505438AB3321586C4320F21258F0B3DA5275785CBDA1`) |
| the version the trial installer declares | **0.0.3** — the installed `LabCairn.exe` reports `ProductVersion 0.0.3.0` and the HKCU row reads `LabCairn 0.0.3` / `DisplayVersion 0.0.3`. The artifact is the v0.1.0 build; its version line is not v0.1.0. See §3.1 |
| where the packages came from | the trial was built on this machine on 2026-11-25 and never transferred (`E:\labcairn-local\dist\v0.1.0\`); **no package was rebuilt here**, so the build provenance is cited from `docs/releases/v0.1.0-artifact.json`, not re-measured. The two FROM packages were on disk already: the 0.0.3 one is the lineage named in `docs/plans/LC-P4-G0-baseline-freeze.md` §3, and its sha256 measured here **is** the one that plan records; the 0.0.2 one is not named in any plan this drill read |
| the tree this record was written on | `ea2a7711bd4523b5f53930a6bbf75e6f4ca77d81` (`git rev-parse HEAD`) |
| the drill folder | `E:\labcairn-local\v010-install-drill-20261125` — outside the repository; the evidence, the backup and the scripts live there |
| the evidence runs | **17** run folders under `evidence\`, from `run-20261125-091815` to `run-20261125-093700`, each with its own `RUN-SUMMARY.txt` |
| the machine-wide diff | `machinewide-before.txt` and `machinewide-after.txt`, 525 lines each. On the 520 state lines — the header is the snapshot's own label and timestamp — **`diff` reports no difference at all** |
| the restore | the userData tree is **identical byte for byte**: 141 files, 0 missing, 0 differing in size, 0 differing in content, 0 extra (`verify-the-restore.py`, which compares sha256 per file). The install tree was absent before the drill and is absent again |
| run type | **locally measured, on the owner's own machine, on a cleaned baseline**. No CI run was started, no pull request was opened, nothing was pushed (`CLAUDE.md`) |

**What this record is.** The record of the installation drill of the **real
v0.1.0 Windows installer** — the one Phase 4 produced and this repository
had never installed — run on 2026-11-25 with the Phase 3 arms script and the
three installers on disk. It claims what the drill measured and what it did
not, and it does **not** close a gate: the HUMAN-CHECK rows the drill's
tick-sheet reserves for a person are listed in §7, one of them is still
open, and no board row is moved here.

---

## 1. The baseline — the four readings, before and after the clean

The drill's card S01 asks four questions, and all four are asked **per
user**. On this machine the answer before the drill was "half dirty": the
application was not installed, but the userData held the owner's own
workspace.

| reading | before | after the clean | after the restore |
|---|---|---|---|
| 1 — a `LabCairn` process running | none | none | none of the drill's own (see below) |
| 2 — `%LOCALAPPDATA%\Programs\LabCairn` | **absent** | absent | absent |
| 3 — a `LabCairn` row under HKCU's uninstall key | **0 rows** | 0 rows | 0 rows |
| 4 — `%APPDATA%\@labcairn` | **present** (141 files, 22,567,631 B — the owner's workspace) | present (57 files, 7,187,264 B — Chromium caches only) | present (141 files, 22,567,631 B) |

The clean was preceded by a backup, so nothing of the owner's was lost: the
userData tree was copied to `E:\labcairn-local\v010-install-drill-20261125\backup\userdata`
(141 files, 21.5 MB) before anything was removed. The install tree was
**already absent**, so the backup of it holds no files — and the restore puts
it back as absent rather than as an empty directory.

There was **no registry row to back up**: the baseline had none, so
`Backup-And-Clean.ps1` recorded "none". This drill's backup script does
export a row when one exists (the Phase 3 script's export silently failed —
§5), but that path was **not exercised here**, and this record does not
claim it works.

**The clean was a direct removal**, not the product's uninstaller: there was
no uninstaller on the machine, because there was no installation. The
userData tree was removed with `Remove-Item -Recurse -Force`.

**One observation the drill did not expect, and the Phase 3 drill saw
first.** Immediately after the removal, `%APPDATA%\@labcairn` was **back**,
holding 57 files that are all Chromium caches (`shell\Cache`, `shell\Code
Cache`, `shell\GPUCache`, `shell\DawnGraphiteCache`, `shell\Extension State`,
…). The 2026-11-20 drill found the same thing with 53 files and did not
establish which process recreates the directory; **this drill did not
establish it either**, and does not claim to. The owner's workspace — the
part that is not a cache — was in the backup the whole time and came back
byte for byte.

**The machine was put back** after the drill: the userData tree was
mirrored back from the backup (`robocopy /MIR`), the readings are back to
"half dirty" (§1's table, right-hand column), and the two trees are
identical byte for byte (§8).

**One process was running when the drill finished, and it was not the
drill's.** The final reading of "is a `LabCairn` process running" answered
*1*. That process was `labcairn.exe` at `E:\LabCairn\.venv\Scripts\labcairn.exe`
— the **development virtualenv's** CLI, not anything the installer wrote —
and its pid changed between two consecutive readings taken seconds apart,
which is the signature of a short-lived command from a concurrent session
rather than of a resident service. No process with an executable under
`%LOCALAPPDATA%\Programs\LabCairn` existed at any point after the restore
(`Win32_Process` filtered on that path: none). The drill's own processes are
gone; the owner's concurrent work is not the drill's to stop.

---

## 2. The arms, and what each one read

Five arms ran, all on this machine, as this account, with the **Phase 3
arms script** (`E:\labcairn-local\p307-nsis-arms\run-arms.ps1`, used
unchanged). The arms are separated by the product's own uninstaller, so one
arm's residue cannot be another arm's baseline.

| arm | what it did | the result |
|---|---|---|
| 1 | the v0.1.0 build alone: install → launch → same-version reinstall over the live install → uninstall → reinstall onto the cleaned path | every automated check green |
| 2 | the Phase 4 baseline (0.0.3) installed, then the v0.1.0 installer run over it | every automated check green |
| 3 | the 0.0.2 baseline installed, then the v0.1.0 installer run over it | every automated check green |
| 4 | the content proof: the installed backend tree measured at three points, and the installed `labcairn.exe` measured by name | the installed bytes match what the artifact record publishes |
| 5 | the rollback: the v0.1.0 build installed, then the **older** 0.0.3 installer run over it | the rollback works, and the bytes came back to the baseline's |

### 2.1 Arm 1 — the v0.1.0 build on a clean machine

Every automated check passed (`evidence\run-20261125-091815`,
`RUN-SUMMARY.txt`). What it read, in the order it read it:

- the silent install exited 0, the install directory appeared, and the HKCU
  uninstall entry appeared: `DisplayName=LabCairn 0.0.3`,
  `DisplayVersion=0.0.3`, and the installed `LabCairn.exe` reports
  `ProductVersion 0.0.3.0`;
- the resources inventory is complete: `app.asar`, `app.asar.unpacked`,
  `elevate.exe`, `labcairn-shell.cmd`, `shell-env.template.json`, `web-dist`;
- the frozen backend ships and carries its migrations, and **the live
  `resources\shell-env.json` is the template, copied by the installer** —
  the Phase 3 drill's finding §3.2 does not apply to this build;
- `web-dist` carries the bundle (4 files);
- the installer read its own digest off the file it ran:
  `32BCA39169E5C21B90C982EDD7AD38A7C9BE1A68B5961E8383E46EC14EC4A85C`;
- the launch reached the service's origin line, the service listened on
  **port 63900**, `GET /health` answered `ok` and named the current task,
  `GET /` served the web bundle (200), `POST /task/select` with the token
  answered 200 (granted), a second instance exited 0 without starting a
  second service, the shell was still running before the stop, the shell
  exited on the graceful stop (WM_CLOSE), and **no orphaned service child
  was left after the stop**;
- the same-version reinstall over the live install exited 0, the install
  directory survived the overwrite, the reinstalled tree was identical to
  the installed tree, the registry version was unchanged (`0.0.3 -> 0.0.3`)
  and exactly one `LabCairn` directory remained;
- the silent uninstall exited 0, the install directory was gone (D15), the
  HKCU entry was gone (D15), and **the userData was retained** (D16: no
  `deleteAppDataOnUninstall`) — 75 files;
- the reinstall onto the cleaned path exited 0 and produced a tree identical
  to the first install.

### 2.2 Arm 2 — the Phase 4 baseline, then v0.1.0 over it

The 0.0.3 baseline installed cleanly (14 checks green,
`evidence\run-20261125-092143`) and registered itself as
`LabCairn 0.0.3` / `DisplayVersion 0.0.3` with `ProductVersion 0.0.3.0`.

The v0.1.0 installer then ran over the live installation and every check
passed (`evidence\run-20261125-092232`). The arms script printed the
version transition as it saw it:

```
[PASS] DisplayVersion is now 0.0.3 (was 0.0.3, read 0.0.3)
[INFO] registry: DisplayName=LabCairn 0.0.3 DisplayVersion=0.0.3
[PASS] installed exe ProductVersion starts with 0.0.3 (read 0.0.3.0)
[PASS] exactly one LabCairn directory (1)
[PASS] userData survives the upgrade
[INFO] userData file count: 75 -> 75
```

**The version did not move.** Both installers declare 0.0.3, so the upgrade
is a same-declared-version overwrite. Whether the overwrite replaced the
*content* is a question about bytes, and §2.4 answers it: it did.

### 2.3 Arm 3 — the 0.0.2 baseline, then v0.1.0 over it

The 0.0.2 baseline installed cleanly (14 checks green,
`evidence\run-20261125-092409`), registering `LabCairn 0.0.2` /
`DisplayVersion 0.0.2` with `ProductVersion 0.0.2.0`. The v0.1.0
installer then ran over it, and every check passed
(`evidence\run-20261125-092459`):

```
[PASS] DisplayVersion is now 0.0.3 (was 0.0.2, read 0.0.3)
[PASS] installed exe ProductVersion starts with 0.0.3 (read 0.0.3.0)
[PASS] exactly one LabCairn directory (1)
[PASS] userData survives the upgrade
```

This is the **real version bump**, and it works: 0.0.2 → 0.0.3, one
install directory, the userData untouched.

### 2.4 Arm 4 — the content proof: what actually landed on the machine

The arms prove that the installer runs and that the service answers. They
do not prove that the bytes on the machine are the bytes the artifact
record says the installer carries. This arm measures that, with the
artifact record's own procedure — sha256 over a canonical listing of the
tree, one line per file, sorted by POSIX relative path, each line
`<file sha256>  <file bytes>  <relative path>` — and the procedure was
**validated against a known answer first**: the packaging output at
`E:\labcairn-local\dist\v0.1.0\win-unpacked\resources\backend\labcairn`
measured `1e565565bf32d54640ef927d2491e5fd38ac4257765cf75f9f319d359c5b461d`
over 2,845 files and 225,604,696 bytes, which is exactly what
`docs/releases/v0.1.0-artifact.json` publishes.

Measured on the **installed** tree, `resources\backend\labcairn`:

| point | what was installed | tree sha256 | files | bytes |
|---|---|---|---|---|
| A | the 0.0.3 baseline alone | `57cb8a153ea0b3d3dc05d83605143c76cacfa2204a65f7a5c45dcf4ae8ae13f6` | 2,873 | 225,660,513 |
| B | v0.1.0 over the 0.0.3 baseline | `1e565565bf32d54640ef927d2491e5fd38ac4257765cf75f9f319d359c5b461d` | 2,845 | 225,604,696 |
| C | v0.1.0 onto a clean path | `1e565565bf32d54640ef927d2491e5fd38ac4257765cf75f9f319d359c5b461d` | 2,845 | 225,604,696 |

**B and C are the digest the artifact record publishes**, so the tree the
installer put on this machine is the tree the record describes. And
**A ≠ B**, which is the answer the arms could not give: the same-declared-
version overwrite really did replace the content — 28 files fewer and
55,817 bytes fewer on the machine than the baseline had put there.

Separately, the installed `resources\backend\labcairn\labcairn.exe` measured
**sha256 `f5d2786de2ab28a54ef5c97c37e8910ea6213f10de0819e03708c0539476bdbf`,
44,534,312 B** (`Get-FileHash`), which is the `exe_sha256` and `exe_bytes`
the artifact record publishes. The tree digest and the entry point agree.

### 2.5 Arm 5 — the rollback: the other direction

The arms so far only went forward. Rollback is the direction an operator
reaches for when a new build is wrong, so it was measured too: v0.1.0 was
installed, then the **older** 0.0.3 installer was run over the live
installation (`evidence\run-20261125-093453` and `-093700`).

| point | tree sha256 | files | bytes |
|---|---|---|---|
| before the rollback (v0.1.0 installed) | `1e565565bf32d54640ef927d2491e5fd38ac4257765cf75f9f319d359c5b461d` | 2,845 | 225,604,696 |
| after the rollback (the 0.0.3 baseline installed) | `57cb8a153ea0b3d3dc05d83605143c76cacfa2204a65f7a5c45dcf4ae8ae13f6` | 2,873 | 225,660,513 |

The older installer exited 0, the registry row still reads `LabCairn 0.0.3`
/ `DisplayVersion 0.0.3`, the installed `LabCairn.exe` still reports
`ProductVersion 0.0.3.0` — and the bytes came back to the baseline's
exactly. **The rollback works, and the registry cannot tell you it
happened**, because the two builds declare the same version.

---

## 3. The findings

### 3.1 The v0.1.0 installer declares itself 0.0.3

The artifact Phase 4 produced is the v0.1.0 build. Its file is named
`LabCairn Setup 0.0.3.exe`, its `shell/package.json` says `0.0.3`, the
installed executable reports `ProductVersion 0.0.3.0`, and the uninstall
row it writes reads `LabCairn 0.0.3` / `DisplayVersion 0.0.3`. Every
reading agrees; there is no disagreement to resolve.

The consequence is not cosmetic, and §2.2 and §2.5 measure it: **an
operator cannot tell a v0.1.0 installation from a 0.0.3 installation by
looking at the machine.** The registry, the file name, the executable's
version resource and the uninstall row all say 0.0.3, and the only thing
that distinguishes them is the bytes of the backend tree. A support
question of the form "which version is installed?" is unanswerable from
the machine's own bookkeeping.

This drill does not propose a version line, and does not change one: the
version is read from `shell/package.json`, which is another window's file.
The owner decides. See the closing note.

### 3.2 The same-declared-version overwrite does replace the content

This is worth stating separately, because it is the one thing the arms
could not have shown: **the overwrite was not a no-op.** Installing v0.1.0
over a live 0.0.3 installation replaced the tree (digest A → digest B),
and installing 0.0.3 back over that replaced it again (digest B → digest
A). Both directions exited 0, and both left exactly one install
directory and one registry row.

So the version line does not break the mechanism — it breaks the
**bookkeeping**, and it breaks the *rollback audit*: the operator who
rolls back has no way to tell from the machine that they did.

### 3.3 The backend v0.1.0 carries is newer than the baseline's, and carries no `__pycache__`

The two trees were compared file by file (the full listing is in the
evidence index, §8):

- **9 files in v0.1.0 that the baseline does not have**: the
  `material/meetingtext.py` and `material/pptx.py` modules and the
  migrations `0024` … `0030`;
- **37 files in the baseline that v0.1.0 does not have**, and **every one
  of them is a `__pycache__` `.pyc`**;
- **4 files present in both at different sizes**: three `material/*.py`
  modules are larger in v0.1.0, and `labcairn.exe` is 44,572,363 B in the
  baseline against 44,534,312 B in v0.1.0.

So v0.1.0 carries the **newer** backend, and it carries it **without the
byte-code caches**. That matches the artifact record's own scope note —
the tree it publishes "carries no `__pycache__` (checked)" — and it is
measured here on the installed copy rather than taken on trust.

The `__pycache__` difference also has a practical reading: the baseline
installer shipped 37 stale `.pyc` files, so the baseline's tree is not
byte-identical to a fresh freeze of the same source. **A tree digest
computed over a tree that contains `__pycache__` is not reproducible from
the source alone.** This drill does not claim the caches are harmful — it
claims they are a difference, and that the artifact record's published
digest is the one that does not have them.

### 3.4 The userData tree comes back after the uninstall — as on 2026-11-20

Removing the userData tree, and then finding it back with Chromium caches
in it, happened on this machine on 2026-11-20 and happened again on
2026-11-25 (57 files this time, 53 then). Neither drill established which
process recreates it, and this record does not claim to. The consequence
for an operator is the same in both: **"the userData is gone" is not a
state the uninstaller produces**, and any check for "the uninstall left
nothing behind" must look at what is in the tree, not at whether the tree
exists.

---

## 4. "The installer stayed inside the per-user paths"

On this machine the claim can be argued from the account's privileges
**and** from a difference.

The Phase 3 drill of 2026-11-20 ran elevated, so it could only argue from
the difference. This drill ran in **non-elevated** processes
(`IsInRole(Administrator)` → `False`), so an installer that reached
outside the per-user paths would have had to ask for elevation and would
have failed. It did not fail.

The difference is also there. The machine-wide state was listed before the
drill and after it: the HKLM uninstall keys (both hives), the HKCU
uninstall key, `C:\Program Files`, `C:\Program Files (x86)` and
`C:\ProgramData`. Both listings are 525 lines. The header is the
snapshot's own label and timestamp — it differs by definition and says
nothing about the machine — so the comparison is made on the **520 state
lines**, and **`diff` reports no difference at all**.

Nothing outside the per-user paths changed, and nothing inside the machine
as a whole changed that the listing covers.

---

## 5. The deviations from the Phase 3 drill's design, and why

1. **The registry export was fixed, and the fix was not exercised.** The
   Phase 3 backup script replaced a leading `HKCU:\` on the key's `PSPath`
   before handing it to `reg.exe export`, but PowerShell's `PSPath` is
   prefixed `Microsoft.PowerShell.Core\Registry::`, so the replacement
   never fired, the export failed, and the original row could not be
   restored from a file. The Phase 3 record says so honestly and its
   restore left the row as the product's installer had written it. This
   drill's scripts build the `HKEY_CURRENT_USER` path from the key's own
   name and import it back. **This drill's baseline had no row to export,
   so the corrected path did not run.** It is a fix in the script, not a
   property this drill measured.
2. **A tree that was absent before the drill is restored as absent.** The
   Phase 3 baseline had an installed application, so its restore always
   mirrored. This baseline had none: mirroring an empty backup would have
   left an empty `Programs\LabCairn` directory behind, which is a
   difference from the baseline and the diff would correctly have
   reported it. The restore removes the tree instead.
3. **The machine-wide diff is made on the state lines.** The two
   snapshots carry a four-line header (label, timestamp, host, elevation),
   so a diff of the full files reports four differing lines that say
   nothing about the machine. The comparison is made on the 520 state
   lines, and this record says so rather than claiming a difference of
   zero over files that do differ.
4. **The arms script was used unchanged.** `E:\labcairn-local\p307-nsis-arms\run-arms.ps1`
   is the Phase 3 script, read and run as it stands. Two scripts in this
   drill's folder had to be written (the driver that sequences the arms,
   and the tree-digest tool), and they do not assert anything about the
   product: the tree digest tool is the artifact record's own procedure,
   and the driver only sequences calls.
5. **Two arms the Phase 3 drill had are not repeated here**: the `build`
   arm (the artifact was already built and this drill installs it; nothing
   was rebuilt) and the D17 half (the workbench screenshot — §7).
6. **Everything ran silently.** Every install and uninstall was `/S`. The
   assisted installer's interactive path — the buttons a person sees, and
   the "keep or remove the old version" question a person would be asked —
   was not exercised at all.

---

## 6. What the drill does not claim

- **It does not claim the workbench renders.** The Phase 3 drill's finding
  §3.3 was a blank workbench body whose cause it did not establish. This
  drill took no screenshot and made no judgement about what the window
  shows. It claims the service answered, the bundle was served (200) and
  the shell started and stopped cleanly; it does not claim the window
  looked right.
- **It does not claim the installer's interactive path works.** Every
  install and uninstall was silent. Nothing here says what a person sees,
  what the buttons do, or whether a downgrade prompt appears.
- **It does not claim anything about SmartScreen.** The installers carry
  no Mark-of-the-Web (no `Zone.Identifier` stream on any of the three —
  they were built on this machine and never transferred), so **no
  SmartScreen prompt was raised and none was observed**. The behaviour of
  a downloaded installer is outside this drill.
- **It does not claim the installer is signed.** `Get-AuthenticodeSignature`
  returned `NotSigned`, with no signer certificate — unsigned by decision
  (W28).
- **It does not claim the data in the owner's workspace survived the
  drill intact.** The workspace was removed for the duration of the drill
  (it was in the backup) and the file **count** and the **userData
  survival** were measured across the arms; the **content** of the
  workspace was not read, not diffed against anything, and not exercised
  by any of the arms.
- **It does not claim that the drill exercised the migration path.** The
  backend tree's migrations were checked for *presence*; no arm ran a
  workspace through a schema upgrade.
- **It does not claim a clean-machine install.** The baseline had the
  owner's userData present (though no application and no registry row).
  A genuinely empty machine was not drilled.
- **It does not claim the rollback is a supported operation.** It was
  measured and it worked, but the installer was run over a live tree by
  hand, in silent mode, as an administrator-group member without
  elevation. Nothing here says the product offers a rollback.
- **It does not claim anything about the version line, and it did not
  change one.** See §3.1 and the note below.
- **It does not close a gate.** No board row is moved, no CI run was
  started, no pull request was opened, and nothing was pushed.

---

## 7. The HUMAN-CHECK rows, and the ones still owed

The Phase 3 drill's tick-sheet
(`E:\labcairn-local\p307-nsis-arms\checklist.md`) reserves these for a
person. The readings this record can supply are in the brackets.

| row | what it asks | where it stands |
|---|---|---|
| A3 | the OS build, how the exe reached this machine (SmartScreen/MOTW), and any dialog seen | [build 26300.9711, `DisplayVersion` 26H2, built here on 2026-11-25, no transfer, **no Mark-of-the-Web on any of the three installers** (`Get-Content -Stream Zone.Identifier`: absent), silent installs, no dialog] |
| B9 | the workbench renders in the window (not the diagnostic page); a screenshot | **[OPEN] — not attempted.** No screenshot was taken and no judgement about the window was made. The Phase 3 drill's §3.3 finding stands unresolved, and this drill neither confirms nor contradicts it |
| F2 | the signing status | [unsigned by decision — `Get-AuthenticodeSignature` → `NotSigned` (W28)] |
| F3 | the support limits | [to be recorded by the owner] |
| F4 | the attestation that no COM/ProgID/macros/sendkeys/GUI-UI automation was used to open any document | [the drill opened no document; the shell was started and stopped by the product's own paths, and every interaction was a command against the local HTTP service] |
| F5/F6 | the record itself | this file |

---

## 8. The evidence index (outside the repository)

`E:\labcairn-local\v010-install-drill-20261125\`

| what | where |
|---|---|
| the 17 run folders and their summaries | `evidence\run-20261125-091815` … `-093700`, each with `RUN-SUMMARY.txt` (and the launch arm's `shell-stdout.log`, `shell-stderr.log`, `service.log`, `health.json`, `workspace-init.log`) |
| the tree and userData snapshots the arms took | `evidence\snapshots\tree-first-install.txt`, `tree-reinstall.txt`, `tree-after-same-reinstall.txt`, `userdata-before-install.csv`, `userdata-before-uninstall.csv`, `userdata-after-uninstall.csv` |
| the machine-wide listings | `machinewide-before.txt`, `machinewide-after.txt` (525 lines each), and the state lines on their own in `machinewide-before.state.txt`, `machinewide-after.state.txt` |
| the content proof | `content-proof.txt` (the three tree digests), `exe-proof.txt` (the installed `labcairn.exe` digest) |
| the rollback | `rollback-proof.txt` (the digest before and after) |
| the backend tree difference, file by file | `backend-tree-difference.txt` |
| the backup of what was removed | `backup\userdata\` (141 files, 21.5 MB); `backup\install\` is empty because the install tree was absent at the baseline |
| the scripts | `Snapshot-Machine.ps1`, `Backup-And-Clean.ps1`, `Restore-The-Machine.ps1`, `run-the-arms.ps1`, `phase1-baseline-and-clean.ps1`, `phase2-restore-and-verify.ps1`, `phase2b-machinewide-diff.ps1`, `phase3-content-proof.ps1`, `phase4-exe-proof.ps1`, `phase5-rollback.ps1`, `measure-tree.py`, `verify-the-restore.py` |
| the log | `cleanup.log` (the backup, the clean and the restore, in order), `arms-console.txt`, `arms-results.txt` |

**The arms script itself** is not in this folder: it is the Phase 3
script, at `E:\labcairn-local\p307-nsis-arms\run-arms.ps1`, used unchanged.
