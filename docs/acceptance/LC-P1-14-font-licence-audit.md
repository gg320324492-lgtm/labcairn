# The font audit — what actually reaches a user, measured

**Work order:** LC-P1-14 (public alpha handoff) · **Status:** the factual half is
done; **the licence itself is the owner's decision and is not taken here.**
**Measured:** 2026-10-25, on the tree at `f4db1e8`, against the virtualenv's own
installed wheels.

**Why this is written down now.** The carried-forward table names the obligation
this discharges: *"matplotlib's bundled fonts bring a licence obligation that the
root licence line does not cover, and G5's audit has to cover the fonts rather
than the root licence line alone."* The hand-off record says the same thing more
sharply: *"The licence audit is not optional and not deferred."*

**And it names the part that is a decision and the part that is a fact.** The
bundled fonts turn out to be the *easy* half. The hard half — **who owns the
copyright and under what terms the work is released** — is not a question this
repository can answer, and `LICENSE.PENDING.md` says so in its own first line:
*"This file is not a license. It is a notice that no license has been granted."*

---

## 1. What the wheels bundle

Measured in the virtualenv the project actually runs in.

| Wheel | What it bundles | Under what terms |
|---|---|---|
| **matplotlib** | **40 TrueType files** in `mpl-data/fonts/ttf/`: the DejaVu family (**14** faces), the STIX family (**17**), the Computer Modern faces (**8**, `cm*.ttf`), and `LastResortHE` (**1**) | DejaVu: **Bitstream Vera copyright, DejaVu's own changes in the public domain** (`LICENSE_DEJAVU`) · STIX: **SIL OFL** (`LICENSE_STIX`) · Computer Modern: the **Knuth** licence |
| **matplotlib** | the **14 PDF core fonts' metrics** (`pdfcorefonts/`, AFM files) | Adobe's own terms: *"may be used, copied, and distributed for any purpose and without charge … provided that all copyright notices are retained"* — **a condition, not a prohibition** |
| **reportlab** | `Vera*.ttf` / `Vera*.afm` | Bitstream Vera — permissive |
| **reportlab** | **`DarkGarden*` — 7 files**: `DarkGarden.sfd`, `DarkGardenMK.afm`, `DarkGardenMK.pfb` and their notices | **GNU General Public License, version 2 or later** (`DarkGarden-copying.txt`, `DarkGarden-copying-gpl.txt`) — **the one bundled font that is not permissive** |

**The finding that matters is not what is bundled. It is what leaves.**

## 2. What reaches a user, measured

**The report's four forms, produced and inspected.** Not read off a docstring:
the artefacts were rendered and their bytes examined.

| Form | A font file in the artefact? | Measured |
|---|---|---|
| **Markdown** | no — the format does not carry fonts | the rendered Markdown mentions no font at all |
| **PDF** | **no** | `/FontFile`, `/FontFile2` and `/FontFile3` are all **absent**; `/FontDescriptor` appears **zero** times. The fonts are **referenced**, not embedded: `/BaseFont /Helvetica` and `/Helvetica-Bold`, which are the fourteen Type 1 core faces a reader supplies |
| **DOCX** | **no** | the package has a `word/fontTable.xml` — a **table** naming the fonts the styles ask for, which the reader resolves — and **no part under `word/fonts/`**, and no `/FontFile` anywhere in the bytes |
| **The figure** | **no** | the figure is a raster, so its text is **pixels**; a rasterised glyph is not a font file and carries no licence obligation |

**So the DarkGarden GPL font does not reach a user.** reportlab bundles it, and
LabCairn never embeds it: the PDF references the core Type 1 faces and embeds
nothing, and the DOCX names fonts in a table and carries none. **The GPL
obligation that a wheel's contents might suggest does not attach to the
artefact.**

## 3. What this does and does not settle

**It settles this:** if the owner grants a permissive root licence, **the
bundled fonts do not stand in the way.** Nothing third-party is redistributed
in any artefact, and the only permissive fonts the wheels carry (Bitstream Vera
/ DejaVu, OFL, Knuth) are permissive under terms an MIT release is compatible
with. **The audit's factual half is that simple.**

**It does not settle this, and nothing here tries to:**

- **Who owns the copyright.** Unresolved, and it is the owner's to resolve.
  `LICENSE.PENDING.md` is a notice that no rights have been granted, and it
  says so on its own face. **No open-source claim may be made until it is
  replaced by an actual licence.**
- **Which licence.** The repository's own language has been "intended to be
  released as open source once the copyright position is settled", and the
  PyMuPDF decision (ADR-0008) was made *on the assumption* of a permissive
  root licence. That assumption has not yet been discharged.
- **The bundled fonts' attribution.** Even with no artefact carrying a font, a
  distribution of the *wheels* ships their notices, and a release's NOTICE
  should say which notices travel with it. This is a small, mechanical part of
  LC-P1-14 and it is not done.

## 4. The witness

**The property is watched, on both sides that can carry a font.** The PDF side
was watched already — `tests/test_analysis_report_render.py::
test_the_pdf_embeds_no_font` asserts the artefact carries no `/FontFile`, and
its own docstring gives the reason: *"a registered TrueType font would be
embedded — which would carry its licence into the artefact."*

**The DOCX side was not.** `src/labcairn/reports/render/docx.py` states the
same property — *"it embeds no font, so the report's appearance in Word
depends on the reader's installed fonts and on nothing else"* — and **nothing
watched it.** That is the shape this repository keeps finding: the property was
stated, the statement was true, and nothing would have said so if it stopped
being true. It is the same shape as F30, where the mechanism that did the
watching was itself unwatched.

`tests/test_analysis_report_render.py::test_the_docx_embeds_no_font` now
watches it. **It is checked on the parts, not on a string**: a font file is a
part under `word/fonts/`, and a part that is not there cannot have been
embedded.

**Verified by mutation, not by assertion.** The exporter was changed to embed
a font part — what a registered TrueType font would produce — and the witness
went red with the artefact named:

> `the DOCX carries font files, and a font file carries its licence into the
> artefact: ['word/fonts/DejaVuSans.ttf']`

and green again once the exporter was restored.

## 5. What is left, and for whom

| # | What | Whose |
|---|---|---|
| 1 | **Resolve the copyright ownership and choose the root licence**, and replace `LICENSE.PENDING.md` with the licence itself | **the owner's** — this is a legal position, not an engineering one |
| 2 | Write the **NOTICE** that says which third-party notices travel with a distribution, and which fonts are named in it | LC-P1-14 |
| 3 | Record the audit in the work-order board when LC-P1-14 starts | LC-P1-14 |
| 4 | The `reference-exclusion` gate's own sdist/wheel member lists, so the release's contents are checked the way the reference tree's are | LC-P1-14 |

**Item 1 blocks any claim of open-source licensing and is not a judgement
call this repository may make.** The other three are engineering, and are
LC-P1-14's.
