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
