# LC-P1-14 — The release's own contents

**Work order:** LC-P1-14 (public alpha handoff) · **Subtask:** T07 ·
**Status:** the three deliverables are written; the licence of the project
itself is **not** settled and is not settled here.

**What this work order had to produce.** The
[font audit](LC-P1-14-font-licence-audit.md) §5 named four items still open,
and two of them are this subtask's:

> | 2 | Write the **NOTICE** that says which third-party notices travel with a distribution, and which fonts are named in it | LC-P1-14 |
> | 4 | The `reference-exclusion` gate's own sdist/wheel member lists, so the release's contents are checked the way the reference tree's are | LC-P1-14 |

**The files written, and only these:**

| File | What it is |
|---|---|
| `NOTICE` | the third-party notices that travel with a distribution |
| `.github/workflows/release.yml` | the checks a release runs |
| `docs/acceptance/LC-P1-14-release-contents.md` | this record |

**Every number below was measured.** The commands are given with their real
output, so a reviewer can re-run them and expect to see the same thing. Where
this record disagrees with another record in the repository, the measurement
wins and the difference is stated rather than smoothed over (§7).

---

## 1. How the measurements were taken

```bash
# The artefacts.
uv build

# The source distribution's member list, and the committed tree's.
tar -tzf dist/labcairn-0.1.0.tar.gz | grep -v '/$' | sed 's|^labcairn-0.1.0/||' | LC_ALL=C sort
git ls-tree -r --name-only HEAD | LC_ALL=C sort

# The wheel's member list.
python -c "import zipfile;print('\n'.join(sorted(zipfile.ZipFile('dist/labcairn-0.1.0-py3-none-any.whl').namelist())))"

# The runtime closure the lockfile names.
uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements.txt
```

**The licence of every dependency was read out of the installed
distribution**, not out of memory and not off a badge: its own
`License-Expression` metadata, else its own trove classifier, else the text of
the licence file inside its own `dist-info`. The rule and the code are in
§6.

---

## 2. What a LabCairn distribution contains

### 2.1 The source distribution

**443 committed files + `PKG-INFO` = 444 members**, and the equality is exact:
the member list is the committed tree's file list plus the one file the build
backend adds. Nothing is missing and nothing is extra.

| Group | Members |
|---|---|
| root files | 14 |
| `.github/` | 9 |
| `.vscode/` | 1 |
| `docs/` | 46 |
| `examples/` | 7 |
| `migrations/` | 11 |
| `scripts/` | 5 |
| `src/` | 147 |
| `tests/` | 156 |
| `web/` | 48 |

The fourteen root files are `.env.example`, `.gitattributes`, `.gitignore`,
`.gitleaks.toml`, `.python-version`, `CLAUDE.md`, `CONTRIBUTING.md`,
`LICENSE.PENDING.md`, `NOTICE`, `PKG-INFO`, `README.md`, `conftest.py`,
`pyproject.toml`, `uv.lock`.

**There is no third-party source code in it.** Every member is a file of this
repository. The only third-party *material* in the distribution is the three
papers of §5, and they are named.

### 2.2 The wheel

**153 members**: the 147 files under `src/labcairn` (146 `.py` and one
`py.typed`), and six metadata members:

```
labcairn-0.1.0.dist-info/METADATA
labcairn-0.1.0.dist-info/RECORD
labcairn-0.1.0.dist-info/WHEEL
labcairn-0.1.0.dist-info/entry_points.txt
labcairn-0.1.0.dist-info/licenses/LICENSE.PENDING.md
labcairn-0.1.0.dist-info/licenses/NOTICE
```

**The wheel carries no binary at all** — every package member is Python
source or the type marker. So no font, no image and no archive can reach a
user through it.

**The NOTICE travels with both artefacts.** It is a root member of the source
distribution and `dist-info/licenses/NOTICE` in the wheel. That is the build
backend's own doing: hatchling collects `NOTICE*` alongside `LICEN[CS]E*` into
the wheel's licence directory, and the wheel's metadata records it as
`License-File: NOTICE`.

### 2.3 A property of the packaging nobody had written down

**The build backend's source-distribution target does not read `.gitignore`.**
Measured, by planting files and building:

```bash
mkdir -p web/node_modules/fakepkg build/x .venv/y pkg/__pycache__
echo x > web/node_modules/fakepkg/index.js
echo x > build/x/f.txt
echo x > .venv/y/f.txt
echo x > probe.db
echo x > probe.pyc
echo x > pkg/__pycache__/m.cpython-312.pyc
uv build
tar -tzf dist/labcairn-0.1.0.tar.gz | grep -E "node_modules|build/|\.venv/|__pycache__|probe"
```

Actual output:

```
labcairn-0.1.0/build/x/f.txt
labcairn-0.1.0/probe.db
labcairn-0.1.0/web/node_modules/fakepkg/index.js
```

`.venv/`, `__pycache__/` and `*.pyc` are in none of it — those three **are**
excluded by default. `build/`, `node_modules/` and `*.db` are not.

Both are ignored by git (`*.db` and `node_modules/` in `.gitignore`) and
**both are in the distribution anyway**. The default exclusions are a short
fixed list — `dist/`, `.venv/`, `__pycache__/` and `*.pyc` were excluded when
the same files were planted — and `probe.db` and `web/node_modules/` are not
in it. **`build/` is not in it either**: a planted `build/x/f.txt` landed in
the distribution as well, and `.gitignore` ignores `build/` too.

**Why this matters for the release, and it is not a theoretical concern:**
`pnpm install --frozen-lockfile` writes `web/node_modules/` into the working
tree. A release built after that step would ship the installed packages. The
`reference-exclusion` gate never sees it, because its member-list assertions
are about the *reference* families and an installed package is not one.

So `.github/workflows/release.yml` **builds before anything writes into the
working tree**, and its member-list check compares the artefacts against
`git ls-tree HEAD`. If a step is ever moved above the build, the check fails
and says why. That is the whole reason the check compares two lists rather
than reading a manifest.

---

## 3. The dependency closure's licences

### 3.1 What the lockfile names

`uv export --frozen --no-dev` over the lockfile at `dd08573` resolves **171**
requirement lines. **The closure is platform-dependent**, and the difference
is the platform-conditional packages:

| Platform | Distributions |
|---|---|
| Linux | 167 |
| macOS | 165 |
| Windows | 168 |

`pywin32`, `pywin32-ctypes` and `colorama` are Windows-only; `jeepney` and
`secretstorage` are Linux-only. **The union of the three is 170**, and the one
distribution left over — `httpx2-jsfetch` — installs on **no supported
platform at all**: its marker is `sys_platform == 'emscripten'`. It is under
BSD-3-Clause, and it is the only member of the closure no CI job can install.

**All 171 were installed and read**, and every one resolved to a licence from
the distribution itself. **Sixteen distinct licences**, and no distribution
was left unresolved:

| Licence | Distributions |
|---|---|
| MIT | 74 |
| Apache-2.0 | 46 |
| BSD-3-Clause | 29 |
| PSF-2.0 | 4 |
| BSD-2-Clause | 3 |
| ISC | 3 |
| MPL-2.0 | 2 |
| BSD-3-Clause+Apache-2.0 | 2 |
| Apache-2.0 AND CNRI-Python | 1 |
| Apache-2.0 AND MIT | 1 |
| Apache-2.0 OR BSD-3-Clause | 1 |
| Apache-2.0+BSD-3-Clause | 1 |
| BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 1 |
| MIT-0 | 1 |
| MIT-CMU | 1 |
| Unlicense | 1 |

### 3.2 The thirteen LabCairn names, and where their licence text lives

Read from each distribution's own installed metadata and licence file:

| Distribution | Version | Licence | The licence text is at |
|---|---|---|---|
| alembic | 1.20.0 | MIT | `alembic-1.20.0.dist-info/licenses/LICENSE` |
| fastapi | 0.151.0 | MIT | `fastapi-0.151.0.dist-info/licenses/LICENSE` |
| matplotlib | 3.11.2 | matplotlib Licence Agreement (PSF-style; the trove classifier reads "Python Software Foundation License") | `matplotlib-3.11.2.dist-info/LICENSE` |
| openpyxl | 3.1.5 | MIT | `openpyxl-3.1.5.dist-info/LICENCE.rst` |
| pdfplumber | 0.11.10 | MIT | `pdfplumber-0.11.10.dist-info/licenses/LICENSE.txt` |
| pydantic | 2.14.1 | MIT | `pydantic-2.14.1.dist-info/licenses/LICENSE` |
| pydantic-ai | 1.107.7 | MIT | `pydantic_ai-1.107.7.dist-info/licenses/LICENSE` |
| python-docx | 1.2.0 | MIT | `python_docx-1.2.0.dist-info/licenses/LICENSE` |
| reportlab | 5.0.1 | BSD-3-Clause | `reportlab-5.0.1.dist-info/licenses/LICENSE` |
| rich | 15.0.0 | MIT | `rich-15.0.0.dist-info/licenses/LICENSE` |
| SQLAlchemy | 2.1.4 | MIT | `sqlalchemy-2.1.4.dist-info/licenses/LICENSE` |
| typer | 0.25.1 | MIT | `typer-0.25.1.dist-info/licenses/LICENSE` |
| uvicorn | 0.54.0 | BSD-3-Clause | `uvicorn-0.54.0.dist-info/licenses/LICENSE.md` |

### 3.3 The four that carry a condition — the paper-qa failure mode, again

The lesson this repository keeps meeting is that **a distribution's root
licence line is not a statement about everything inside it**. paper-qa's
AGPL-3.0 subpackage was invisible to a root-level check. The same is true
here, in four places, each measured:

1. **certifi** (MPL-2.0) and **tqdm** (MPL-2.0 AND MIT, so MIT is available
   too). MPL 2.0 is file-level copyleft: a distributor of a *modified* copy
   of a covered file must offer that file under MPL 2.0. Neither package is
   modified by LabCairn and neither is redistributed by it.

2. **numpy 2.5.4** — its licence file carries the **GCC Runtime Library
   Exception 3.1** for the OpenBLAS build statically linked into
   `numpy.libs`, stated as `GPL-3.0-or-later WITH GCC-exception-3.1`. The
   exception is what makes the GPL terms compatible with distribution under
   other terms. Without it, numpy would be the release's first GPL-3
   dependency.

3. **Pillow 13.0.0** — its licence file carries the **FreeType licences** for
   the bundled FreeType 2.14.3: *"the FreeType License … or the GNU General
   Public License version 2"*, offered as two mutually exclusive choices, plus
   the brotli 1.2.0 and zlib licences.

4. **pywin32 312** — Windows-only. Its licence directory carries an **LGPL**
   notice for the bundled `adodbapi` module and the **Scintilla** licence for
   the bundled Scintilla sources, beside the PSF-licensed pywin32 code
   itself.

---

## 4. Fonts — the two kinds, kept apart

The [font audit](LC-P1-14-font-licence-audit.md) settled what reaches a
*user*. This work order has to say what travels with a *distribution*, and
there are two different answers, so the NOTICE keeps them apart.

### 4.1 Inside two dependency wheels — this is where font files actually are

**matplotlib 3.11.2** — `matplotlib/mpl-data/fonts/` holds **101 font files**
in three directories, and matplotlib's own licence file carries a
per-component inventory naming the terms for each:

| Files | Count | The terms, as matplotlib's own `LICENSE` states them |
|---|---|---|
| `ttf/DejaVu*` | 14 | `ttf/LICENSE_DEJAVU` (4,816 bytes): "Fonts are (c) Bitstream (see below). DejaVu changes are in public domain." |
| `ttf/STIX*` | 17 | `ttf/LICENSE_STIX` (5,476 bytes): the STIX Font License, 24 May 2010, STI Pub Companies — OFL-1.1. The `LICENSE` inventory names the component "Stix fonts", licence "OFL-1.1". |
| `ttf/cm*.ttf` | 8 | the inventory names the component "BaKoMa Fonts", licence "BaKoMa Fonts Licence" — "Copyright (C) 1994, 1995, Basil K. Malyshev. All Rights Reserved. Permission to copy and distribute these fonts for any purpose is hereby granted without fee, provided that the above copyright notice, author statement and this permission notice appear in all copies of these fonts and related documentation." |
| `ttf/LastResortHE-Regular.ttf` | 1 | the inventory names the component "Last Resort fonts", licence "OFL-1.1" |
| `pdfcorefonts/*.afm` | 14 | Adobe's PDF core fonts, **metrics only**. The inventory carries **no entry** for this directory. |
| `afm/*.afm` | 47 | metrics only. The `cm*.afm` among them are covered by the BaKoMa entry; the inventory carries **no entry** for the rest. |

**reportlab 5.0.1** — `reportlab/fonts/` holds **25 font files** (18 `.pfb`,
2 `.afm`, 5 `.ttf`) and three notice files:

- `bitstream-vera-license.txt` (5,954 bytes) — the Bitstream Vera licence,
  for the Vera faces. Its own words: "The fonts have a generous copyright,
  allowing derivative works (as long as 'Bitstream' or 'Vera' are not in the
  names), and full …".
- `DarkGarden-copying.txt` (1,318 bytes) — the GPL font's own notice:
  "Copyright (C) 1999, 2000, 2004 Michal Kosmulski … This font is free
  software; you can redistribute it and/or modify it under the terms of the
  GNU General Public License … either version 2 of the License, or (at your
  option) any later version." It carries the font's own exception: *"As a
  special exception, if you create a document which uses this font, and embed
  this font or unaltered portions of this font into the document, this font
  does not by itself cause the resulting document to be covered by the GNU
  General Public License."*
- `DarkGarden-copying-gpl.txt` (17,976 bytes, 344 lines) — the full text of
  the GNU General Public License version 2. **It travels inside the reportlab
  distribution itself**, so the GPL terms of the DarkGarden font reach anyone
  who installs reportlab without anything in LabCairn adding to them.

The DarkGarden font files are `DarkGardenMK.afm` and `DarkGardenMK.pfb`;
`DarkGarden.sfd`, `DarkGarden-readme.txt` and `DarkGarden-changelog.txt`
travel with them.

### 4.2 Inside LabCairn's own artefacts — this is where font *binaries* are

**The wheel carries none.** Every one of its 153 members is Python source, the
type marker, or metadata.

**The source distribution carries three members with font binaries in them**,
and they are the three fixture papers of §5. Not one file in either artefact
has a font file's *name*.

The papers each embed font programs, and the counts were read out of the font
programs themselves, from the copyright header each one carries:

| Paper | Embedded font programs |
|---|---|
| `arx-2610.09396.pdf` | 17 |
| `arx-2610.10596.pdf` | 19 |
| `arx-2610.12393.pdf` | 33 |
| **total** | **69** |

| Count | Family | The terms, from the embedded font program's own header |
|---|---|---|
| 57 | AMS Computer Modern (CMR, CMMI, CMSY, CMEX, MSAM) | "Copyright (c) 1997, 2009 American Mathematical Society (http://www.ams.org), with Reserved Font Name … This Font Software is licensed under the SIL Open Font License, Version 1.1." |
| 8 | URW++ Nimbus Roman | "% Copyright (URW)++,Copyright 1999 by (URW)++ Design & Development. % See the file COPYING (GNU General Public License) for license conditions. % As a special exception, permission is granted to include this font program in a Postscript or PDF file that consists of a document that contains text to be displayed or printed using this font, regardless of the conditions or license applying to the document itself." |
| 1 | Inconsolata Regular | "Copyright: Licensed under SIL font license." |
| 1 | Inconsolata Bold | "Released under the Apache 2 license." |
| 1 | SFTT1000 (Computer Modern Typewriter, by Vladimir Volovich) | "% Copyright (c) 2001 Vladimir Volovich <vvv@vsu.ru>. % See the file COPYING (GNU General Public License) for license conditions." |
| 1 | dsrom10 | "Generated from MetaFont bitmap by pktrace". **No licence statement in the bytes** — a Computer Modern derivative, reproduced inside the paper that carries it. |

The URW++ exception is the font's own and it covers exactly this use: an
embedding into a PDF that displays text with it, whatever the document's own
licence is.

### 4.3 What the reports themselves carry

No font file, and this is **watched, not asserted**:

- `tests/test_analysis_report_render.py::test_the_pdf_embeds_no_font` —
  `/FontFile`, `/FontFile2` and `/FontFile3` are absent and `/FontDescriptor`
  appears zero times. The fonts are *referenced* (`/BaseFont /Helvetica`),
  not embedded.
- `tests/test_analysis_report_render.py::test_the_docx_embeds_no_font` — no
  part under `word/fonts/`; the fonts are named in `word/fontTable.xml` and
  carried by the reader.
- The figure is a raster, so its text is pixels.

The font audit already recorded that the DOCX side was unwatched and is now
watched. This work order did not add to that; it re-measured the property and
found the witnesses still hold.

---

## 5. The third-party material in the source distribution

**Three papers, each CC BY 4.0**, verified per paper from the arXiv abstract
page and **not** assumed from the venue. `tests/fixtures/papers/MANIFEST.md`
carries the attribution CC BY 4.0 §3(a) asks for — title, all authors, source,
licence and SHA-256 for each — and the files are verbatim copies.

| Paper | Licence | SHA-256 |
|---|---|---|
| `arx-2610.10596.pdf` — Dijkstra Is NOT Greedy | CC BY 4.0 | `6da9f8057e8cc7bafcf76316d660276f40c2e4a87230fa418e28cde51143d700` |
| `arx-2610.12393.pdf` — HRIL | CC BY 4.0 | `2429674e16c9b9dc2bb584d71e307285853fca11e356847d7e84508538799b9d` |
| `arx-2610.09396.pdf` — ARCS | CC BY 4.0 | `292eae176b6ea072cb23b163f861954bab2fd7e1f973d8f8fcd2575aa1338520` |

**LabCairn modifies none of them and adds no condition to them.** The NOTICE
names them and points at the manifest.

---

## 6. What the release workflow checks, and why it does not conflict

`.github/workflows/release.yml` runs on a `v*` tag, on every pull request
(unfiltered — a filtered required check is reported as *expected* rather than
*passed*), and on demand. It has **two jobs**, and the second one runs on two
platforms.

### 6.1 `release-contents` (ubuntu-latest)

**It re-uses the existing gates rather than re-deciding them:**

| Check | The existing gate it matches |
|---|---|
| `uv run pytest tests/test_no_reference_leakage.py` | the `reference-exclusion` gate, run **verbatim** — the same file the required check runs |
| `uv lock --check` | `lockfiles.yml` |
| `pnpm install --frozen-lockfile` | `lockfiles.yml` |
| `gitleaks git --config .gitleaks.toml --redact --exit-code 1 .` | `security.yml`, same pinned version and checksum, same git mode |

**It adds three checks of its own:**

1. **The release's member lists.** The source distribution's members must
   equal `git ls-tree -r HEAD` plus `PKG-INFO`; the wheel's package members
   must equal the files under `src/labcairn`, with no member that is not in
   the source tree; the wheel's metadata members must be exactly the six
   declared. **Neither missing nor extra**, the way the reference gate holds
   its own lists.
2. **The NOTICE travels with both artefacts**, and neither artefact carries a
   font file or a non-source package member.
3. **The wheel carries no binary at all** — every package member is Python
   source or the type marker.

### 6.2 `release-dependency-licences` (ubuntu-latest **and** windows-latest)

**Why two platforms.** The closure is platform-dependent, so a single-platform
audit never reads the four distributions that differ. The two runners cover
**170 of the 171**; the one left over installs on no supported platform and
its licence is recorded in NOTICE.

**What it checks:**

1. **Every dependency's licence is read from the distribution itself** — its
   own `License-Expression`, else its own trove classifier, else the text of
   the licence file inside its own `dist-info`. A licence nobody recorded
   fails the release. The permissive set and the named exceptions sit in the
   workflow next to the check, so a person has to read a licence and add it.
2. **The closure is the lockfile's.** The installed set must equal the
   marker-evaluated export, at the pinned versions — so a distribution that
   failed to install, or one that appeared from nowhere, is caught.

**The job's name carries the matrix leg.** Two jobs sharing a name are one
check as far as branch protection is concerned, so the platform has to be in
the name — the same reason `python.yml`'s name mentions `matrix.os`.

### 6.3 The workflow is checked against the repository's own CI rules

`tests/test_no_reference_leakage.py` enforces, for every workflow file: no
trigger filters `pull_request`, no whole-disk secret scan, no artifact path
that sweeps the working tree, and no reference to a study clone. The new
workflow was run against all of them — **24 workflow assertions, all
passing**, and then the whole file: **99 tests, all passing**.

### 6.4 The two python programs were run, not merely written

The workflow's two checks are python programs embedded in YAML. Reading them
is not evidence that they work, so they were **extracted from the parsed YAML
and executed against the artefacts this repository builds**:

```
source distribution: 444 members (= the committed tree plus PKG-INFO)
wheel:              153 members (147 package, 6 metadata)
the release's member lists hold: neither missing nor extra
exit: 0
...
platform: win32
every one of the 168 installed distributions carries a licence the release records
exit: 0
```

**And running them found a bug in them.** The first run of the licence audit
failed with:

```
::error::the lockfile names these distributions and they are not installed: ['jaraco-classes', 'jaraco-context', 'jaraco-functools', 'pdfminer-six']
::error::these distributions are installed and the lockfile does not name them: ['jaraco.classes', 'jaraco.context', 'jaraco.functools', 'pdfminer.six']
```

The audit compared the PyPI name against the installed name without applying
**PEP 503** normalisation, and four distributions have names that differ in
punctuation (`jaraco-classes` installs as `jaraco.classes`). The fix is the
normalisation, and it is in the workflow now. **A check that had never been
run would have reported four distributions as missing and four as unexpected**,
on every release, for ever.

---

## 7. Where this record differs from another one, and why

**The font audit says the Computer Modern fonts are under "the Knuth
licence". matplotlib's own licence file says they are under the **BaKoMa
Fonts Licence** — it names the component "BaKoMa Fonts", the files
`matplotlib/mpl-data/fonts/ttf/cm*.ttf`, and the licence "BaKoMa Fonts
Licence".** The measurement wins, and the NOTICE states what the licence file
that actually travels says. The audit's own file is not edited here — it is
another subtask's file — so the difference is recorded here instead.

**The font audit counted 40 TrueType files in matplotlib and 7 DarkGarden
files in reportlab.** Both counts are right for what they counted, and both
need their object stated:

- matplotlib's `mpl-data/fonts/` holds **101** font files, not 40: the 40
  TrueType files the audit counted, plus **61 AFM metric files** (14 under
  `pdfcorefonts/`, 47 under `afm/`). The audit counted the TrueType files and
  mentioned the core-font metrics separately; the NOTICE counts everything
  that is a font file.
- reportlab's `DarkGarden*` files are **seven**: two font files
  (`DarkGardenMK.afm`, `DarkGardenMK.pfb`), the font's source
  (`DarkGarden.sfd`), and four notices (`DarkGarden-copying.txt`,
  `DarkGarden-copying-gpl.txt`, `DarkGarden-readme.txt`,
  `DarkGarden-changelog.txt`). The NOTICE separates the font files from the
  notices.

**Nothing here contradicts the audit's central finding**, which stands and was
re-measured: **no third-party font file reaches any LabCairn artefact.**

---

## 8. Which claims have a machine-checkable witness

| Claim | The witness | Type |
|---|---|---|
| The source distribution holds the committed tree and nothing else | `release.yml` → "the release's own member lists" | CI job |
| The wheel holds every file under `src/labcairn` and nothing else | the same job | CI job |
| The wheel's metadata members are exactly the six declared | the same job | CI job |
| The NOTICE travels with both artefacts | the same job | CI job |
| Neither artefact carries a font file | the same job | CI job |
| The wheel carries no binary at all | the same job | CI job |
| Every dependency's licence is read from the distribution and is recorded | `release.yml` → `release-dependency-licences`, on **ubuntu-latest and windows-latest** | CI job |
| The installed closure is the lockfile's, at the pinned versions | the same job | CI job |
| The dependency lockfiles are consistent | `lockfiles.yml` | CI job |
| No secret is in the tracked history | `security.yml` | CI job |
| No reference-study material is packaged | `tests/test_no_reference_leakage.py` | CI job |
| A report's PDF embeds no font | `tests/test_analysis_report_render.py::test_the_pdf_embeds_no_font` | test |
| A report's DOCX embeds no font | `tests/test_analysis_report_render.py::test_the_docx_embeds_no_font` | test |
| The three fixture papers are the ones that were recorded | `tests/test_paper_fixtures.py` | test |

**The claims in this record with no witness of their own**, and what stands in
for them:

- **The dependency licence census in §3** — the numbers were measured by
  reading the installed distributions, and the *check* in `release.yml`
  re-measures the same thing on every run. But the census's arithmetic (the
  171, the sixteen labels, the counts) is not asserted anywhere: a
  distribution that changed its licence without changing its version would
  change the census and the check would follow it, silently. The census in
  the NOTICE and in §3 is therefore a **snapshot of release 0.1.0**, and the
  check is what keeps it from going stale.
- **The 69 embedded font programs and their headers** — measured, reproducible
  by the commands in §1, and not watched by anything. Replacing a fixture
  paper would change them, and `tests/test_paper_fixtures.py` watches the
  papers' SHA-256 — which is why the count cannot drift without the paper
  changing.
- **The three papers' CC BY 4.0 status** — verified per paper from the arXiv
  abstract page by the fixtures' own subtask and recorded in
  `tests/fixtures/papers/MANIFEST.md`. Not re-verified here, because
  re-verifying it means reading arXiv's live pages, which this round did not
  do.

---

## 9. What this round did **not** establish

Stated without softening.

| Item | Status |
|---|---|
| **The licence of LabCairn itself** | **Not established, and not establishable here.** `LICENSE.PENDING.md` says in its first line that it is not a licence. The NOTICE says so too and grants nothing: **no open-source claim is made anywhere in it.** The copyright and the root licence are the owner's to settle. |
| **The licence of `dsrom10`**, the one embedded font whose program carries no licence statement | **Undetermined.** It is a Computer Modern derivative generated from a MetaFont bitmap, and the bytes do not say. It travels inside a CC BY 4.0 paper, which is reproduced verbatim. |
| **The `pdfcorefonts/` and `afm/` metric files' terms** | **Not stated by matplotlib.** Its licence inventory has no entry for either directory. The metrics carry no glyph outlines, and the NOTICE says what the inventory does and does not say rather than inventing a term. |
| **The licences of the 171 distributions under their own licences' *terms*** | **Read, not assessed.** The licences are file-reading results; whether a term is satisfied in a given use is a legal question, and this record does not make one. |
| **Whether the release workflow passes on GitHub** | **Unverified.** The two python programs it carries were extracted from the parsed YAML and **run against the artefacts this repository builds**, and they pass (§6.4). The workflow itself has **not** run on a runner, and the shell around the programs — the `uv` invocations, the pnpm install, the gitleaks download — has **not** been executed here. |
| **A platform the closure was not installed on** | The closure was installed and read on **Windows** (168 distributions), and the **union of all 171** was installed and read on this machine. The **Linux** and **macOS** counts in §3.1 are the marker evaluation of the same export, **not** an install on those platforms. The licences do not vary by platform, but the *installed set* was measured on one platform only; the workflow's two legs close that on CI. |
| **The one distribution no CI job can install** | `httpx2-jsfetch` is under BSD-3-Clause and installs on no supported platform. It is recorded in NOTICE and read here, but **no CI job can re-read it**, because no runner can install it. |
