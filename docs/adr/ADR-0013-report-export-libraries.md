# ADR-0013: The libraries the report's four exporters will use

**Status:** Accepted
**Work order:** LC-P1-11 (report assembly and export) — T00, the
dependency decision — with LC-P1-12 (the CLI and the local Web workbench)
**Date:** 2026-10-20

> **Scope note.** This ADR decides the **libraries** the four exporters use
> and the **obligations the libraries bring**, and nothing else. It does not
> decide what a report contains, how a report model is shaped, how the
> artefact manifest is built, or what the report says — those are
> LC-P1-11's, and §2.2 and §2.3 of the LC-P1-11-12 breakdown already fix
> most of them. What it settles here is: which library for each export form,
> under what licence obligations, at what install cost, and what the
> determinism of each form actually is.
>
> **This ADR did not add the dependencies.** `python-docx` and `reportlab`
> are named here; the subtask that implemented the exporters added them —
> `python-docx>=1.2,<2` and `reportlab>=4.0,<6` — pinned them in `uv.lock`,
> and wrote the dependency comment in the style of ADR-0012's. A dependency that appears in
> an ADR without appearing in the lockfile is a decision, not a dependency;
> the two must not be confused, and the lockfile is where the second one
> lives.
>
> **The determinism claims below are the exporters', not LabCairn's.** The
> owner decided on 2026-10-20 that **the report's reproducible form is
> Markdown and HTML**; DOCX and PDF are exports whose bytes are recorded but
> not claimed reproducible (the breakdown's §1.4.3, Option A). What was
> measured here is therefore *not* a claim — it is the finding that the
> decision rests on, and it is reported whatever it says, including the
> parts that make the PDF and DOCX forms weaker than a reader might assume.

## Context and concrete problem

`docs/PHASE_1_WORKORDERS.md` names the forms but not the libraries:

> **LC-P1-11 — Build:** Markdown/HTML preview + basic editable DOCX and PDF,
> evidence citations and stable artefact manifest…

So unlike LC-P1-10's chart decision, this one is open. It is not open in the
way it looks, though: **two of the four forms do not need a library at all**,
and the two that do have a small set of candidates whose licences differ
enough to decide the question on their own.

The four forms and how the breakdown says they are produced (§2.3):

| Form | What it is | How it is produced | Byte-reproducible? |
|---|---|---|---|
| **Markdown** | the reference form | the model's own writer | yes — it is text with a declared encoding |
| **HTML** | the preview form | the model's own writer, in one self-contained file | yes — same reason |
| **DOCX** | the editable form | a document writer over the model | only if the container metadata is pinned |
| **PDF** | the fixed form | a document writer over the model, or the HTML through a converter | only if the creation date and the font subsetting are pinned |

Two properties of that table decide the shape of this ADR.

**First, the direction for Markdown is model → Markdown, and no mainstream
library does that.** `markdown-it-py` and `mistune` are *parsers*: they take
Markdown and produce HTML. The report needs the other direction, and a
parser cannot be turned around by wishing — its whole data model is
Markdown-shaped tokens on the way in and HTML on the way out. The brief for
this task asked for the parsers to be measured anyway, and they were; §
"Alternatives" records what they are and why they do not fit.

**Second, the report renders retrieved text.** Retrieved text is data and
never instructions, so the escaping of it is not a detail of the HTML writer
— it is the difference between a preview and an injection. The choice
between an own writer and a template engine therefore turns on **where the
escaping is decided**, not on which produces prettier output. That is
measured below, on a string that a retrieved source can genuinely contain.

## What was measured, and how

**A scratch virtual environment outside the repository**
(`%TEMP%\adr13-scratch`, one environment per candidate, Python 3.12.13
CPython, `uv` 0.11.21), because the candidates must be measured *as
installed* and the repository's own environment must not be disturbed. The
repository was not modified: `pyproject.toml` and `uv.lock` are untouched
and no candidate was added to the project.

**Every licence below was read from the distribution's own files** — the
`LICENSE` file inside the installed wheel — and not from the
`License-Expression` field in the package metadata, for the reason
ADR-0012 gives: the metadata field is a summary, and the obligation is in
the text. Where the two disagreed, the text won. Where a wheel shipped **no
licence file at all**, that is recorded as a finding rather than filled in
from the metadata.

**Sizes** are the bytes of the files each distribution owns, read from each
installed distribution's own `RECORD`. Two numbers are given for each
candidate: its **total** installed size, and its **marginal** size — the
bytes it would add to a tree that already has the repository's current 174
packages (375.33 MB installed). The marginal number is the one a user
pays, because the repository already carries `pillow` and `fonttools`
through `pdfplumber` and `matplotlib`.

**Determinism** was measured by rendering the same input twice and comparing
the bytes, and then — because two renders inside one second agree trivially
— again across a **2.2-second gap**, and for the PDF again in a **second
interpreter**. A determinism result that was only ever measured within one
second is not a determinism result.

## Alternatives

Fifteen candidate distributions were installed and measured — each in its
own bare virtual environment, so that "what it brings with it" is the
resolver's answer and not a guess — and borb 3.0.9 was attempted and
refused to install. The table below adds the two options that are *not* a
package, because "no dependency" is a real option and is measured too.

| Option | Licence, read from the wheel's own file | Verdict |
|---|---|---|
| **own writer, standard library only** (Markdown and HTML) | none — `html.escape` is CPython's | **Chosen** for Markdown and HTML. Zero install cost, and the escaping is decided in one place |
| **python-docx 1.2.0** | MIT, from `python_docx-1.2.0.dist-info/licenses/LICENSE` — "The MIT License (MIT) / Copyright (c) 2013 Steve Canny" | **Chosen** for DOCX. The only maintained DOCX writer measured — the other DOCX writer measured, `docx` 0.2.4, is its unmaintained ancestor. MIT; no font obligation |
| **reportlab 5.0.1** | BSD 3-clause, from `reportlab-5.0.1.dist-info/licenses/LICENSE` — "Copyright (c) 2000-2024, ReportLab Inc." | **Chosen** for PDF. Permissive, needs no system library and no external binary — it ran in a bare venv — 4.65 MB marginal, and a determinism switch exists |
| Jinja2 3.1.6 | BSD 3-clause, from `jinja2-3.1.6.dist-info/licenses/LICENSE.txt` — "Copyright 2007 Pallets" | Rejected for the HTML form: it is a template *language* for a report with four fixed shapes, and its `autoescape` is **off by default** — the safety is a flag the author must remember, which is the improvisation the task warns about |
| Mako 1.4.3 | MIT, from `mako-1.4.3.dist-info/licenses/LICENSE` — "Copyright 2006-2026 the Mako authors and contributors" | Rejected, and it is the closest call here: it is **already in the tree** (via `alembic`, a declared dependency) at **zero** marginal cost. But it does not escape by default either — `${v}` emits retrieved text raw, and the fix is a per-expression `\| h` or a template-wide `default_filters=["h"]`, the latter of which would also escape the report's own structure where that structure is interpolated rather than written literally |
| markdown-it-py 4.2.0 | MIT, from `markdown_it_py-4.2.0.dist-info/licenses/LICENSE` and `LICENSE.markdown-it` | Rejected on direction: `MarkdownIt.render()` takes Markdown and returns HTML. It is also already in the tree (via `rich`) at zero marginal cost, so the cost was never the problem |
| mistune 3.4.0 | MIT, from `mistune-3.4.0.dist-info/licenses/LICENSE` — "Copyright (c) 2014, Hsiaoming Yang" | Rejected on direction: `create_markdown().render()` is Markdown → HTML, the same wrong way round |
| mdformat 1.0.0 | MIT, from `mdformat-1.0.0.dist-info/licenses/LICENSE` — "Copyright (c) 2021 Taneli Hukkinen" | Rejected on direction: `mdformat.text()` is Markdown → Markdown, a *formatter*. It reformats Markdown that already exists; it does not produce Markdown from a model |
| **fpdf2 2.8.9** | **GNU LGPL v3**, from `fpdf2-2.8.9.dist-info/licenses/LICENSE` — "GNU LESSER GENERAL PUBLIC LICENSE Version 3, 29 June 2007" | Rejected on licence posture. It is the smallest pure-Python PDF writer measured (1.54 MB marginal) and it works — but ADR-0012 rejected pygal 3.1.3 (LGPL-3.0-or-later) on exactly this ground, and `LICENSE.PENDING.md` §5 requires the dependency set to be final enough for a real dependency review before an MIT release |
| weasyprint 70.0 | BSD 3-clause, from `weasyprint-70.0.dist-info/licenses/LICENSE` | Rejected: it **does not run without the GTK/Pango/Cairo system libraries**, which are not pip-installable. The import fails on this machine with `OSError: cannot load library '…libgobject-2.0-0.dll'`. It also brings `pyphen`, whose own `LICENSE` records *"Pyphen is released under the GPL 2.0+/LGPL 2.1+/MPL 1.1 tri-license"* and whose dictionaries come from LibreOffice under GPL/LGPL/MPL |
| xhtml2pdf 0.2.26 | Apache-2.0, from `xhtml2pdf-0.2.26.dist-info/licenses/LICENSE.txt` | Rejected: the root licence is Apache-2.0, but it brings **svglib 2.3.0, whose own `LICENSE.txt` is the GNU LGPL v3** — copyleft in the tree, hidden behind a permissive root line, which is precisely the ADR-0004 paper-qa failure mode. It also brings `reportlab` and its fonts anyway, and costs 17.50 MB marginal |
| **borb 2.1.25** | **AGPL-3.0-or-later or commercial**, from `borb-2.1.25.dist-info/LICENSE.md` — *"This program is offered under a commercial and under the AGPL license"* | Rejected on four independent grounds: it is **AGPL**, which `LICENSE.PENDING.md` §5.4 and §6 name as the boundary that must not be crossed; it ships `borb/license/async_usage_statistics.py`, which is **enabled by default** (`_ENABLED: bool = True`), posts events with `requests.post` to an external AWS Lambda endpoint, and registers an `atexit` flush — a network call in a local-first offline tool; its 3.0.9 wheel **does not install** (*"ZIP file contains multiple entries with different contents"*); and it costs 46.59 MB marginal |
| pypandoc 1.17 | MIT, from `pypandoc-1.17.dist-info/licenses/LICENSE` | Rejected: it needs the **pandoc binary** installed separately — the same external-binary dependency ADR-0012 refused for kaleido's Chrome |
| pdfkit 1.0.0 | MIT, from `pdfkit-1.0.0.dist-info/LICENSE` | Rejected for the same reason: it needs **wkhtmltopdf** installed separately |
| docx 0.2.4 | **no licence file in the wheel** — the `dist-info` contains no `LICENSE` at all | Rejected: unmaintained since 2015, it is the pre-1.0 ancestor of `python-docx`, and it ships **no licence text**, so its terms would have to be taken from metadata rather than from the distribution's own files |
| odfpy 1.4.1 | **no licence file in the wheel** | Rejected on format: it writes **ODF (`.odt`)**, not DOCX. The work order names DOCX, and a `.odt` is a different artefact with a different consumer |
| hand-written PDF writer | — | Rejected: a PDF with selectable text requires embedding a subsetted TrueType font, which is a large and under-tested surface, and it buys nothing the library does not — the PDF form is explicitly **not** claimed reproducible, so there is no determinism prize to win it |

**The "no dependency" option was real and was partly taken.** For two of the
four forms it is the *whole* answer: the Markdown and HTML writers are
LabCairn's own code, and the measurement below shows that owning them costs
nothing and puts the escaping in one auditable place. It was not taken for
DOCX or PDF, because a DOCX is an OOXML package with a styles part, a
numbering part and a relationships graph, and a PDF is a cross-reference
table with a font program in it — neither is a surface to improvise, and
the work order's own words are *"basic editable DOCX"*, not *basic DOCX*.

## Decision

**LC-P1-11 will add exactly two runtime dependencies, `python-docx` and
`reportlab`, and will write the Markdown and the HTML itself, with the
standard library.**

| Form | Library | Version measured | Marginal install |
|---|---|---|---|
| Markdown | none — LabCairn's own writer | — | **0.00 MB** |
| HTML | none — LabCairn's own writer | — | **0.00 MB** |
| DOCX | `python-docx` | 1.2.0 | **10.48 MB** (python-docx 1.54 MB + lxml 8.94 MB) |
| PDF | `reportlab` | 5.0.1 | **4.65 MB** (reportlab itself; pillow and charset-normalizer are already installed) |

**15.13 MB marginal in total**, against a repository that already installs
375.33 MB. The version floor is `>=4.0,<6` for reportlab and `>=1.2,<2` for
python-docx, and it is a judgement rather than a measurement, in the same
way ADR-0012's was: only 5.0.1 and 1.2.0 were installed and measured, and
no earlier version of either was exercised.

### The two writers LabCairn owns, and the escaping

**Markdown and HTML come from one model walk, not from each other.** The
HTML is *not* produced by parsing the Markdown. That would need a parser —
the wrong direction the candidates above were rejected for — and it would
make the HTML a rendering of a rendering, with two escaping layers.

**HTML escaping uses `html.escape` from the standard library, at every
interpolation, with no exceptions.** Measured on the string
`CPU <script>alert("xss")</script> & "quotes" 'apos'`:

| Route | Output |
|---|---|
| `html.escape` (standard library) | `CPU &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; &quot;quotes&quot; &#x27;apos&#x27;` |
| Jinja2, `autoescape=True` | `CPU &lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt; &amp; &#34;quotes&#34; &#39;apos&#39;` |
| Jinja2, default | `CPU <script>alert("xss")</script> & "quotes" 'apos'` — **unescaped** |
| Mako, default | `CPU <script>alert("xss")</script> & "quotes" 'apos'` — **unescaped** |
| Mako, `${v \| h}` | `CPU &lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt; &amp; &#34;quotes&#34; &#39;apos&#39;` |

All three escaping routes are correct when configured. The difference is
**where the decision is made**: `html.escape` is called at the point where a
text value enters the document, and a writer that emits structure and text
from different branches cannot forget it, because the text branch *is* the
escaping branch. A template engine puts the decision at each interpolation
site, and both template engines tested escape **nothing** by default — so a
report whose author forgets one site ships an injection, and the failure is
silent. That is the improvisation this task was told to avoid, and it is
the whole reason the HTML form does not get a template engine despite
Jinja2 costing only 0.49 MB.

**Markdown escaping is a table, not a regex, and it must be tested.** No
small, maintained library was found for it: `markdown-escape`, `mdescape`,
`markdown-escape-py` and `pymarkdown-escape` do not exist on PyPI, and the
escaping helpers that do exist (`markdown_it.common.utils.escapeHtml`,
`mistune.util.escape`) are HTML escapers living inside parser packages —
using them would mean depending on a parser for one function, in the wrong
direction. The set to escape is CommonMark's own: the ASCII punctuation
characters that can open a span or a block, plus `&`, `<` and `>` so the
Markdown is also safe when embedded in HTML. **The set is one table in one
module, and a test must cover it** — that test, not this paragraph, is what
keeps it honest, in the same spirit as ADR-0012's `tests/test_analysis_dependency.py`.

### The DOCX: python-docx 1.2.0

**Licence.** MIT, read from `python_docx-1.2.0.dist-info/licenses/LICENSE`:
*"The MIT License (MIT) / Copyright (c) 2013 Steve Canny"*, and the grant is
the standard one — the notice must be included in all copies. The notice
travels inside the wheel. The only other new package is `lxml` 6.1.3, whose
`dist-info/licenses/LICENSE.txt` is the BSD 3-Clause text and whose
`LICENSES.txt` records the bundled libxml2 and libxslt notices; both are
permissive. **No copyleft anywhere in the DOCX path.**

**Size.** 10.66 MB total, **10.48 MB marginal** — `python-docx` itself is
1.54 MB and `lxml` is 8.94 MB. `typing_extensions` 4.16.0 is already
installed. lxml is a compiled extension, so the cost is a platform-specific
wheel as well as the bytes.

**Fonts: none.** The DOCX embeds **no** font file — the produced package has
no `word/fonts/` part and no embedded `.odttf`. `word/fontTable.xml` names
faces (Calibri and the Office defaults) and the reader's system supplies
them. So the DOCX path adds **no font obligation**, and the report's
appearance in Word depends on the reader's installed fonts — a portability
fact worth knowing, and not a licence one.

### The PDF: reportlab 5.0.1

**Licence.** BSD 3-clause, read from `reportlab-5.0.1.dist-info/licenses/LICENSE`:
*"Copyright (c) 2000-2024, ReportLab Inc."*, granting redistribution in
source and binary form provided the notice, the conditions and the
disclaimer are retained, and provided neither the company nor the
contributors are used to endorse. The notice travels inside the wheel.

**Size.** 20.14 MB total, **4.65 MB marginal** — reportlab itself, because
`pillow` 13.0.0 (14.88 MB) and `charset-normalizer` 3.5.2 (0.62 MB) are
already installed through `pdfplumber`. Of reportlab's own 4.65 MB,
1.66 MB is the bundled font directory.

**Fonts: this is the obligation, and it has two parts.**

reportlab's wheel installs **24 font files** in `reportlab/fonts/` — 18
`.pfb`, 5 `.ttf`, 1 `.sfd` — under six licence text files. Two of them
matter:

1. **Bitstream Vera.** `Vera.ttf`, `VeraBd.ttf`, `VeraBI.ttf`, `VeraIt.ttf`,
   under `bitstream-vera-license.txt`: *"The fonts have a generous
   copyright, allowing derivative works (as long as 'Bitstream' or 'Vera'
   are not in the names), and full redistribution (so long as they are not
   sold by themselves)."* This is **the same obligation ADR-0012 recorded for
   matplotlib's DejaVu fonts** — a font licence under the root licence
   line, which the G5 audit must cover and not the root line alone.
2. **DarkGarden.** `DarkGarden.sfd` and `DarkGardenMK.pfb`, under
   `DarkGarden-copying.txt`: *"This font is free software; you can
   redistribute it and/or modify it under the terms of the GNU General
   Public License … either version 2 of the License, or (at your option)
   any later version."* — **GPL-2.0-or-later**, with the standard **font
   exception**: *"if you create a document which uses this font, and embed
   this font or unaltered portions of this font into the document, this font
   does not by itself cause the resulting document to be covered by the GNU
   General Public License."* `DarkGarden-copying-gpl.txt` carries the GPL-2
   text itself.

**What was measured about the fonts, in the wheel and in the output:**

- **Neither Vera nor DarkGarden is registered by default.**
  `canvas.setFont("Vera", 12)` raises `KeyError: 'Vera'`, and
  `setFont("DarkGarden", 12)` raises `KeyError: 'DarkGarden'`.
  `reportlab.pdfmetrics.standardFonts` is exactly the 14 core faces.
- **The default output embeds no font file.** A PDF built with Helvetica,
  Times-Roman and Courier contains **zero** `/FontFile` entries — the faces
  are *referenced by name* and the reader's viewer substitutes them. The
  same PDF carries `/BaseFont /Helvetica` and `/BaseFont /Times-Roman`.
- **A TrueType font, once registered, is embedded** — registering
  `reportlab/fonts/Vera.ttf` and rendering with it produces one `/FontFile`
  entry, and that embedded font carries its licence into the output.

So the obligation is **on the tree, not on the produced PDF**: the wheel
installs a GPL-2.0-or-later font file, and LabCairn's distribution inherits
whatever obligation that file carries if LabCairn ever ships a bundled or
frozen build. The ordinary install — pip fetching reportlab from PyPI — is
reportlab's redistribution, not LabCairn's. **G5's licence audit must cover
`reportlab/fonts/` and not reportlab's root licence line alone**, exactly
as it must cover matplotlib's `mpl-data/fonts/ttf/`.

**Determinism: reportlab can be byte-reproducible, and by default is not.**

| Configuration | Two renders identical? |
|---|---|
| `canvas.Canvas(buf, invariant=0)` — the default | **No** |
| `canvas.Canvas(buf, invariant=1)` | **Yes** |
| `rl_config.invariant = 1`, through the Platypus document path | **Yes** |

Measured in detail:

- **Default: not reproducible.** `/CreationDate` is the current time —
  `D:20261020134009+08'00'` in one render and `D:20261020134012+08'00'` in
  the next, 3 seconds apart — and the file's `/ID` changes with every
  render, so the two renders differ in two places, not one.
- **`invariant=1`: reproducible.** `/CreationDate` becomes the fixed
  `D:20000101000000+00'00'`, and the `/ID` becomes a content fingerprint
  that repeats. Two renders 2.2 seconds apart are byte-identical, and two
  renders in **two separate interpreters** are byte-identical — both
  `ac0805d8ed7265a1eb862254a3baa6b95ca9aee718c962b69b58f7db8d6b2aa1`.
  The same holds through Platypus (`SimpleDocTemplate`, a heading, a
  paragraph, a styled table, and an embedded PNG figure): byte-identical
  across a 2.2-second gap, `/CreationDate` fixed, zero `/FontFile` entries,
  and the figure present as an image XObject.
- **A PDF with a fixed creation date is lying about when it was made** —
  which is the objection the owner's §1.4.3 Option B recorded, and the
  reason Option A was taken. So the switch is recorded here as a
  **capability**, and it is **not** claimed: the PDF's bytes are recorded in
  the manifest, and the report says which of its forms are reproducible.

### The DOCX: it is not reproducible either, and the reason is precise

python-docx 1.2.0, same document saved twice:

| | Result |
|---|---|
| Two saves in the same second | byte-identical |
| Two saves **2.2 seconds apart** | **differ** |
| ZIP entries whose `date_time` differs | **17 of 17** |
| `docProps/core.xml` | **does not vary** |

The finding is sharper than "a DOCX is a ZIP and the timestamps move".
**`docProps/core.xml` does not vary at all**: python-docx copies its
template's fixed `dcterms:created` and `dcterms:modified` of
`2013-12-23T23:15:00Z`, with `<dc:creator>python-docx</dc:creator>` and
`<dc:description>generated by python-docx</dc:description>`. So in the
*default* output the **only** source of variation is the seventeen ZIP
entry timestamps, and pinning them — Option B's "a fixed timestamp in the
DOCX's ZIP entries" — would make the DOCX byte-reproducible without
touching anything else. That is exactly the cost Option B was declined for,
and it is now measured rather than asserted.

One consequence of the template's fixed core properties is worth flagging
because it is a false statement in the artefact: the default DOCX says its
author is **`python-docx`** and its description is **`generated by
python-docx`**, and its creation date is **2013**. The exporter must set
those properties, and setting `created`/`modified` puts a real timestamp
into `core.xml` — which is a second, separate clock from the ZIP entries,
and one the owner has already declined to pin.

## Constraints this places on LC-P1-11

1. **The exporters add the two dependencies themselves.** `python-docx` and
   `reportlab` enter `pyproject.toml` and `uv.lock` in the implementing
   subtask, with a comment in the style of ADR-0012's, naming this ADR and
   recording the font obligation. This ADR adds nothing to the lockfile.
2. **Both libraries must be imported lazily**, like `pdfplumber`,
   `openpyxl` and `matplotlib` already are, so that the Markdown and HTML
   paths — the two the owner called the reproducible forms — do not pay for
   lxml or reportlab. A report exported only as Markdown must not load a
   DOCX or PDF library.
3. **The HTML writer must escape every text value with `html.escape`, and
   must not have a path that emits text unescaped.** A retrieved excerpt
   containing `<script>` must reach the output as text. This is a test, not
   a code review.
4. **The Markdown writer's escape set is one table, in one module, covered
   by a test.** It must escape CommonMark's ASCII punctuation that can open
   a span or a block, plus `&`, `<` and `>`.
5. **The HTML export must be one self-contained file** — no external
   assets, no scripts, no network references — because §2.3 says so and
   because a preview that fetches anything is not a local-first preview.
   An own writer makes this a property of the code rather than a
   configuration to remember.
6. **The DOCX exporter must set `core_properties.author`, `title` and
   `description` explicitly**, because the default says `python-docx`.
   Leaving the library's name in the artefact's author field is a false
   statement about who produced the report.
7. **The PDF exporter must not set `invariant=1`**, because a PDF with a
   fixed creation date misstates when it was produced, and the owner has
   declined to claim PDF reproducibility. The switch is available and is
   recorded; it is not to be used, and if a later decision wants it, that
   decision must say so out loud rather than let a flag appear silently.
8. **The PDF exporter must not register a TrueType font** unless it means
   to embed one, because a registered TTF is embedded in the output and
   carries its licence into the artefact. The 14 core Type 1 faces are
   referenced, not embedded, and are sufficient for a first-pass report.
9. **The exporters must draw, not decide.** A number in a report comes from
   the model and is checked against the ledger; a renderer that computes a
   value is a renderer that can disagree with the ledger. This is the
   breakdown's own rule, and choosing a library does not relax it.
10. **The PDF exporter must pass only local paths to reportlab.**
    reportlab ships a URL reader (`reportlab.lib.utils.rlUrlRead`) that can
    fetch a figure over HTTP. It is **default-deny** as shipped —
    `rl_config.trustedHosts` is `None` and a read raises `OSError: Cannot
    open resource` — and LabCairn must not populate it. A local-first tool
    that fetches a figure from the network is not local-first.
11. **The DOCX and PDF exporters must record the bytes they wrote** in the
    artefact manifest, and the report must state which of its four forms are
    reproducible, because two of them are not.

## What this ADR does not decide

- **Whether a report is Markdown-first.** §2.3 calls Markdown the reference
  form and the breakdown's own writer produced both; this ADR fixes the
  libraries, and the shared-model walk is the implementer's design.
- **What a report contains**, what a claim is, or what the manifest holds.
  §2.2 of the breakdown and ADR-0004's manifest contract already fix the
  last of them.
- **The DOCX's and PDF's internal layout** — styles, page geometry, figure
  sizing, table rules. The library is chosen; the drawing is LC-P1-11's.
- **Whether a DOCX or PDF may be compared by hash.** It may not, unless the
  container metadata is pinned, and the owner has declined to pin it. This
  ADR does not reopen §1.4.3.
- **Whether the PDF's appearance is portable.** It is not: with the core
  Type 1 faces referenced rather than embedded, the PDF's rendering depends
  on the reader's system fonts. That is a property of the format and the
  choice, and it is recorded rather than solved.

## Known gaps

- **This ADR and its review are the same party.** ADR-0008 records that its
  licence reading was *"independently re-derived by a reviewer who was not
  the author"*. That did not happen here, so the project board's rule — a
  row is marked done only when an **independent** review at a named commit
  says so — is **not discharged** for T00.
- **The licence reading was done on one platform.** The wheels for Windows,
  Linux and macOS were not compared, and a platform-specific wheel carrying
  additional third-party components would not have been seen. lxml in
  particular ships platform-specific compiled wheels.
- **WeasyPrint was not measured for determinism, because it does not run
  here.** Its rejection rests on the missing GTK/Pango/Cairo system
  libraries, on `pyphen`'s GPL/LGPL/MPL dictionaries, and on the
  external-system-dependency shape ADR-0012 refused — not on a determinism
  measurement, because none was possible.
- **fpdf2 and xhtml2pdf were measured for licence and cost, and fpdf2 was
  measured for determinism** (not reproducible by default: `/CreationDate`
  is the current time). xhtml2pdf was measured for determinism too, and is
  likewise not reproducible by default. Both were rejected on licence
  posture before either could be chosen, so neither was measured as deeply
  as reportlab was.
- **The borb 3.x line was not measured at all** beyond the fact that its
  3.0.9 wheel does not install; the 2.1.25 measurement is what is reported.
  A future borb release that fixes the packaging would still be AGPL. What
  was measured about borb's telemetry is the module itself — enabled by
  default, posting to an external endpoint, registering an `atexit` flush —
  and **the call path from borb's document writer into that module was not
  traced**, so no claim is made about how often a rendered document is
  reported. The rejection rests on the AGPL licence, not on the telemetry.
- **The version floors are judgements, not measurements.** Only reportlab
  5.0.1 and python-docx 1.2.0 were installed and measured.
- **The sizes are measured as installed bytes on one platform.** The wheel
  sizes differ per platform, and a Linux install of the same tree is not
  the same number of bytes.
- **The reportlab font obligation was reasoned from the licence texts, not
  from a legal opinion.** Whether installing a GPL-2.0-or-later font file
  into the tree constrains LabCairn's own intended MIT grant is a question
  for the G5 review and for whoever settles copyright ownership. This ADR
  records the fact and the text; it does not decide the legal question.
- **The Markdown escape table is this ADR's business only in shape.** The
  implementing subtask owns the table and its test; the table is written —
  **nineteen characters, one table, pinned by a test of its own** — and this
  ADR fixes only that it must be one table and must be tested.
- **A report has been exported since this ADR was written.** Everything above
  says the libraries can produce the four forms; the first real export was
  LC-P1-11's, and it is in `main`.

## Re-evaluation trigger

Re-open if any of the following happens.

1. **A reportlab or python-docx release changes the output.** The version
   is in the manifest's environment fingerprint, so the change is visible in
   the record rather than silent.
2. **The G5 licence audit finds that the GPL-2.0 DarkGarden font in
   `reportlab/fonts/` constrains LabCairn's intended MIT grant.** That is
   the one open question in this ADR, and it is the audit's to answer. If
   the answer is yes, note what is *not* waiting as an escape: no
   copyleft-free pure-Python PDF writer was found among the fifteen
   candidates measured. fpdf2 is LGPL-3.0 and was rejected on the same
   ground ADR-0012 used for pygal; weasyprint is BSD but needs the GTK
   system libraries; and hand-writing the PDF is the surface §"Alternatives"
   already refused. The honest fallback would be to drop the PDF form from
   §2.3, which is a scope decision, not a dependency one.
3. **A DOCX or a PDF is found to be needed byte-reproducibly.** The
   measurements say what has to be pinned: the seventeen ZIP entry
   timestamps for the DOCX, and the creation date and `/ID` for the PDF.
   That is the owner's §1.4.3 Option B, and taking it is a decision, not a
   bug fix.
4. **The report's HTML is ever rendered by something other than LabCairn's
   own writer** — a Markdown renderer in the web workbench, say. That would
   make a Markdown *parser* a dependency after all, and the direction
   argument above would have to be reopened for the web path, not for the
   export path.
5. **The install weight becomes a problem** — a user refusing to install,
   or a packaging decision that 15.13 MB of lxml and reportlab is too much
   for a local-first tool. The DOCX and PDF forms are the only candidates
   with a weight, and dropping them is a scope decision about §2.3's four
   forms, not a dependency decision.
