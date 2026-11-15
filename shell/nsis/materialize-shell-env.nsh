; The installer materializes the package's own configuration file.
;
; Why this file exists. O3's decision C (owner, 2026-11-15): the build ships
; `resources/shell-env.template.json` and never the live name — a template is
; not a default, and `shell/test/packaging-config.test.mjs` watches that rule —
; but an installed shell that carries only the template refuses its first
; launch (`LABCAIRN_SHELL_CLI must name the labcairn entry point …`, measured
; twice on 2026-11-11 and 2026-11-14: the installer carried no live
; `shell-env.json` and nothing else supplied the variable). The install is the
; act that turns the template into the live file: the installer copies the
; template to `resources/shell-env.json`, whose contents the package's own
; resolver reads when the environment names nothing (environment beats file;
; the parse layer is `shell/src/shell-env.mjs`).
;
; Why the template must exist at install time. The copy is from the installed
; tree: if the build shipped no template, the honest failure is here — a loud
; install-time abort — not a first launch that refuses far from the cause.
; `scripts/require-package-inputs.mjs` already refuses a build without the
; frozen backend; this macro refuses an install whose package lost the
; template. A silent skip would recreate the measured refusal.
;
; Why a macro and not a section. electron-builder generates the installer
; script and expands its `customInstall` / `customUnInstall` macros inside its
; own install / uninstall sections; `nsis.include` (a list here, see
; `electron-builder.yml`) carries the file that defines them. `customInit` is
; already taken by `nsis/licenses.nsh`; this file must not define it again —
; a second definition is a compile error.
;
; The workspace is not touched here beyond the file. The template's
; `workspace` value names `%APPDATA%\@labcairn\workspace` (O3's decision B,
; 2026-11-15): a directory outside the installation, expanded per user at
; resolution time. The installer creates nothing there — the workspace is the
; service's own act (its `init` command) — and the uninstaller must leave it
; behind: the install drill's D17 finding was that an installation-relative
; workspace died with the install directory, which made "reinstall preserves
; user data" false for the one directory the product writes its records into.

; `${ifNot}` / `${FileExists}` / `${if} ${Errors}` are LogicLib: the generated
; script does not promise to have included it, and a double include is
; guarded inside LogicLib itself.
!include "LogicLib.nsh"

!macro customInstall
  ; The template the build ships is the only source for the live file.
  ${ifNot} ${FileExists} "$INSTDIR\resources\shell-env.template.json"
    DetailPrint "LabCairn: resources\shell-env.template.json is missing from the package; the shell's own configuration cannot be materialized."
    Abort "LabCairn installation failed: resources\shell-env.template.json is missing from the package."
  ${endIf}
  ClearErrors
  CopyFiles /SOFT "$INSTDIR\resources\shell-env.template.json" "$INSTDIR\resources\shell-env.json"
  ${if} ${Errors}
    DetailPrint "LabCairn: could not write resources\shell-env.json; the installed shell would refuse its first launch."
    Abort "LabCairn installation failed: could not write resources\shell-env.json."
  ${endIf}
!macroend

!macro customUnInstall
  ; Deliberately empty of data removal. electron-builder's uninstaller removes
  ; the installation (including the materialized resources\shell-env.json —
  ; the package's default dies with the package) and, because
  ; `deleteAppDataOnUninstall` is not set, leaves the user's profile directory
  ; alone: the userData directory and the workspace the template names
  ; (decision B, outside the install tree) survive uninstall and reinstall by
  ; design. No directory or file removal belongs in this macro.
!macroend
