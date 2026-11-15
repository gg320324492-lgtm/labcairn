; The two NSIS fragments the drill's build carries, inlined for electron-builder.
;
; Why this file exists. electron-builder 26.18.0 types `nsis.include` as a
; single path (`string | null`), but the drill's configuration names two
; fragments: `nsis/licenses.nsh` (the LGPL licence texts that must travel in
; the installer's $PLUGINSDIR, §1 of LGPL-2.1) and `nsis/materialize-shell-env.nsh`
; (O3's decision C of 2026-11-15: the install is the act that turns the
; shipped template into the package's own `resources/shell-env.json`). A list
; is a schema error the build refuses, so this generated include carries both
; fragments in the order the drill's configuration names them. The witness in
; `test/packaging-config.test.mjs` reads the fragments' contents through this
; file's sources, so the two-file arrangement the tests assert stays the
; arrangement the build carries.
; The licence texts the installer carries.
;
; Why this file exists. The NSIS installer distributes eight binaries (§2.5 of
; NOTICE). Two of them carry LGPL-2.1 terms, and the licence text has to
; travel with the binary it covers: §1 of LGPL-2.1 requires a distributor to
; "distribute a copy of this License along with the Library", and §6 requires
; the same for a combined work. The plug-ins are not installed as files of
; their own — the installer extracts them to $PLUGINSDIR and calls them
; there — so the texts have to be in the installer's own $PLUGINSDIR, beside
; the binaries they govern, and nowhere else.
;
; How the texts get into the installer. electron-builder inserts this file
; into the generated script through its `nsis.include` option, and the
; `customInit` macro this file declares is expanded inside the installer's
; .onInit function — the same place electron-builder expands its own
; `addLicenseFiles` macro when a licence page is configured. The macro name
; is deliberately not `addLicenseFiles`: electron-builder defines that macro
; itself when `nsis.license` names an .html file, and a second definition of
; the same name is a compile error.
;
; The paths are absolute on purpose. electron-builder passes the project's
; directory as the PROJECT_DIR define, and a relative path in a File command
; resolves against the directory of the generated script — which is a
; temporary directory, not this repository's — so the absolute form is what
; keeps the build independent of where it runs from.
;
; What each file covers, and why it is here:
;
;   LGPL-2.1.txt                  The Licence itself, in the words the FSF
;                                  publishes. §1 requires "a copy of this
;                                  License along with the Library".
;
;   STDOUTILS-NOTICE.txt           The copyright notice, the licence
;                                  statement and the replaceability terms
;                                  for StdUtils.dll. §1 requires an
;                                  "appropriate copyright notice and
;                                  disclaimer of warranty", and §2 requires
;                                  that nothing restricts modification.
;
;   STDOUTILS-LGPL-CLARIFICATION.txt
;                                  The upstream author's own clarification.
;                                  §1 requires that "all the notices that
;                                  refer to this License" be kept intact,
;                                  and this notice refers to it throughout.
;
;   NSIS7Z-LICENSE.txt             The licence document the upstream
;                                  Nsis7z_19.00.7z release ships for the
;                                  plug-in: the LZMA SDK's public-domain
;                                  dedication.
;
;   7ZIP-LICENSE.txt               7-Zip's own licence text, which states
;                                  which of its files carry the unRAR
;                                  restriction. The upstream NSIS bundle
;                                  records that nsis7z.dll derives from
;                                  7-Zip's source, so the split belongs
;                                  with the binary.
;
;   README.txt                     What this directory holds, where each
;                                  file came from, and which terms are not
;                                  here and why.

!macro customInit
  InitPluginsDir
  CreateDirectory "$PLUGINSDIR\licenses"
  File /oname=$PLUGINSDIR\licenses\LGPL-2.1.txt "${PROJECT_DIR}\licenses\LGPL-2.1.txt"
  File /oname=$PLUGINSDIR\licenses\STDOUTILS-NOTICE.txt "${PROJECT_DIR}\licenses\STDOUTILS-NOTICE.txt"
  File /oname=$PLUGINSDIR\licenses\STDOUTILS-LGPL-CLARIFICATION.txt "${PROJECT_DIR}\licenses\STDOUTILS-LGPL-CLARIFICATION.txt"
  File /oname=$PLUGINSDIR\licenses\NSIS7Z-LICENSE.txt "${PROJECT_DIR}\licenses\NSIS7Z-LICENSE.txt"
  File /oname=$PLUGINSDIR\licenses\7ZIP-LICENSE.txt "${PROJECT_DIR}\licenses\7ZIP-LICENSE.txt"
  File /oname=$PLUGINSDIR\licenses\README.txt "${PROJECT_DIR}\licenses\README.txt"
!macroend

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
  CopyFiles /SILENT "$INSTDIR\resources\shell-env.template.json" "$INSTDIR\resources\shell-env.json"
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
