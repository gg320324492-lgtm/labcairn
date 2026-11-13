Licence texts shipped with the LabCairn Windows installer
=========================================================

The NSIS installer distributes eight binaries (§2.5 of `NOTICE`). Two of them
carry LGPL-2.1 terms, and the licence text has to travel with the binary it
covers: §1 of LGPL-2.1 requires a distributor to "distribute a copy of this
License along with the Library", and §6 requires the same for a combined work.

This directory holds those texts. They are copied into the installer's own
`$PLUGINSDIR\licenses\` directory by `shell/nsis/licenses.nsh`, so a user who
receives the installer receives the terms next to the binaries they govern.

What each file is, and where it came from
-----------------------------------------

`LGPL-2.1.txt`
    The GNU Lesser General Public License, version 2.1, as published by the
    Free Software Foundation. Fetched on 2026-11-12 from

        https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt

    26,419 bytes, sha256
    `20e50fe7aae3e56378ebf0417d9de904f55a0e61e4df315333e632a4d3555d95`.

    This is the text the obligations are measured against, and the one that
    travels with `StdUtils.dll`. It differs from the copy the upstream
    StdUtils release ships (`LGPL.txt`, sha256
    `1e7e6bae5a5bde32f1ae5a7c37a082d1ab03cf89354f7f936ac40be9e39a6531`)
    only in the FSF's address block and the name in the signature line; the
    operative clauses are identical.

`STDOUTILS-NOTICE.txt`
    The copyright notice and the licence statement of the `StdUtils.dll` that
    the installer carries, together with the terms under which the plug-in may
    be replaced. Written for this repository from the upstream release's own
    `ReadMe.txt` and source headers, so that §1's "appropriate copyright
    notice and disclaimer of warranty" and §4's replaceability condition are
    both discharged by a document that travels with the binary. 4,052 bytes,
    sha256
    `b0680e59c3570fdf7da6222a02e154b69573d5f039b85276c572673fe7f37549`.

`STDOUTILS-LGPL-CLARIFICATION.txt`
    The clarification the StdUtils author adds to LGPL-2.1, copied verbatim
    from the upstream 1.14 release. 2,703 bytes, sha256
    `49287ffa37d51910a8cb595d7ab64ebd2d42525384b16d4322783a0e57a77194`.
    §1 requires that "all the notices that refer to this License" be kept
    intact, and this notice refers to it throughout.

`NSIS7Z-LICENSE.txt`
    The licence document the upstream `Nsis7z_19.00.7z` release ships as
    `Contrib/nsis7z/DOC/License.txt`: the LZMA SDK's public-domain dedication.
    476 bytes, sha256
    `63fcfe54826809b5a9f9df8a8ff53c04330122319ec67a2dd815085586adaf0e`.
    electron-builder's `nsis-bundle-3.13.tar.gz` attributes its
    byte-identical `nsis7z.dll` to this same file.

`7ZIP-LICENSE.txt`
    7-Zip's own licence text, as published by 7-Zip itself. Fetched on
    2026-11-12 from

        https://www.7-zip.org/license.txt

    6,031 bytes, sha256
    `3a184aa13dc8ad30734e28ff901b478ccbcb5b41be52427a5e7609c8fd9e5ddb`.

    It is here because electron-builder's `nsis-bundle-3.13.tar.gz` records
    that `nsis7z.dll` derives from 7-Zip's source, and 7-Zip's terms say
    which of its files carry the unRAR restriction. This document states
    that split, so a reader
    of the installer can see it without going back to 7-Zip.

What this directory does not contain, and why
---------------------------------------------

The four NSIS-distribution binaries the installer carries — `System.dll`,
`nsDialogs.dll`, `nsExec.dll` and `elevate.exe` — are zlib/libpng licensed.
Their terms are the zlib/libpng licence, which §1 of LGPL-2.1 does not
oblige anyone to redistribute, and the notice requirement that does attach to
them is satisfied by the NSIS distribution's own `COPYING`, which travels
with electron-builder's toolset download rather than with this repository.
`NOTICE` §2.5 records where that document is and what its sha256 is.

The same is true of the notices that belong to the plug-ins themselves rather
than to the licence of the whole distribution: electron-builder's
`nsis-bundle-3.13.tar.gz` ships `LICENSES/UAC/License.txt` and
`LICENSES/WinShell/NOTICE-plugin-api.txt` for the `UAC.dll` and
`WinShell.dll` that this installer also carries.
`NOTICE` §2.5 records each one's provenance and sha256.

Neither is copied here, because neither is a condition of the obligations
this repository is discharging, and copying documents that travel with
upstream's own bundles would put second-hand copies of them in this tree.

The source code
---------------

LGPL-2.1 §4 requires the complete corresponding source code, or — for
distribution by offering access to copy from a designated place — equivalent
access to copy that source from the same place. The corresponding source for
the `StdUtils.dll` this installer carries is upstream's own
`StdUtils.2018-10-27.Sources.tar`, inside the upstream
`StdUtils.2018-10-27.zip` release archive. `NOTICE` §2.5.1 records the URL,
the sha256, and the state of that obligation.

About this file
---------------

Written for this repository; the attribution sentences above were corrected
on 2026-11-13 to name the bundle the measurements in `NOTICE` §2.5 name:
electron-builder's `nsis-bundle-3.13.tar.gz` (6,245,626 bytes, sha256
`c18e9ad9684cf4c5bbd7b768cbf1b056d40771d7bd9ae1b513346452decf89d2`), not an
NSIS 3.13 release. This file travels in the installer byte for byte
(`$PLUGINSDIR\licenses\README.txt`, by `shell/nsis/licenses.nsh`); the copy
inside the installer built on 2026-11-12 still carries the earlier wording
(4,971 bytes, sha256
`14f4341f7d7073033631217f09668a64ef75eb7827ca0bd18033ac4ae2e6cf7d`) until the
next rebuild. This copy: 5,812 bytes; its sha256 is printed in `NOTICE` §2.5.2,
which re-measures it whenever the file changes.
