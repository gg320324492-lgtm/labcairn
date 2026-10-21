# ADR-0012: The chart library LC-P1-10 will draw with, and the two settings its determinism needs

**Status:** Accepted
**Work order:** LC-P1-10 (bounded scientific analysis and plots) — T00, the
dependency decision
**Date:** 2026-10-19

> **Scope note.** This ADR decides the **library** and the **obligations the
> library brings**, and nothing else. It does not decide what a chart recipe
> contains, how a figure is drawn, or what a manifest holds — those are T06,
> T07 and T08, and ADR-0004's manifest contract already fixes the last of
> them. What it settles here is: which library, at what version, under what
> licence obligations, and which of the library's behaviours LC-P1-10 has to
> control for its determinism claim to be true.
>
> **The determinism controls below are matplotlib's, not LabCairn's.** They
> were found by measurement, and they are kept honest by a test rather than by
> this document: `tests/test_analysis_dependency.py` fails if either control is
> removed, and the two are **not interchangeable** — one of them governs
> renders within a process and the other governs renders across processes.
> A reader who wants to know whether the claim still holds should run that
> file, not believe this paragraph.

## Context and concrete problem

`docs/PHASE_1_WORKORDERS.md` names the library, and unlike LC-P1-08's PDF
case it names it without naming a library this project cannot use:

> **Build:** … deterministic Matplotlib figure with editable source.

So the decision here is not "is this library admissible" — it is admissible,
and §"Licence obligations" records what it costs. The decision is:

1. **which version**, and what a version bump does to a figure's hash;
2. **which of matplotlib's outputs are stable** and which are not, because
   "deterministic" is the acceptance clause and a figure whose bytes change
   every second is not one;
3. **what the dependency brings with it** — licences, weight, and typing —
   because a dependency is a commitment and the G5 licence audit is the thing
   that will have to honour it.

There is one prior decision that this ADR must not contradict. LC-P1-10's
work order also says *"Explicitly no general-purpose model-authored code
execution"*, and `docs/ARCHITECTURE.md:27` says the same in stronger terms.
**matplotlib is a renderer, not a runtime**: the LC-P1-10 breakdown gives a
figure a declarative JSON recipe and a catalogue of registered operators, so
nothing a model or a person writes is ever executed. Choosing a plotting
library does not open that door, and this ADR does not open it either.

## Alternatives

| Option | Licence | Verdict |
|---|---|---|
| **matplotlib 3.11.2** | PSF-style permissive; **bundles fonts under two further licences** | **Chosen** — named by the work order, and its determinism controls are two settings rather than a browser |
| bokeh 3.10.1 | BSD-3-Clause (Anaconda, Inc. and Bokeh Contributors), read from the wheel's `LICENSE.txt` | Rejected: it is a whole layout engine with its own HTML/SVG output, and it brings `jinja2`, `tornado` and `pyyaml` to draw a static figure. It would be a second layout engine beside the one the work order names |
| plotly 7.1.0 | MIT, read from the wheel's `dist-info/licenses/LICENSE.txt` | Rejected: its static-image path is not pure Python. It goes through `kaleido`, which is either a large self-contained Chromium build (kaleido 0.2.x) or a **user-installed Chrome** (kaleido 1.x). A figure that depends on a browser binary is a worse determinism story and a worse supply-chain story than one that does not |
| pygal 3.1.3 | **LGPL-3.0-or-later** | Rejected on licence posture: it is the only copyleft option here, and this project is being built toward an MIT release |
| svgwrite 1.4.3 | MIT | Rejected: it writes SVG primitives, not charts. Axis layout, tick placement, text metrics and a legend would all have to be built, which is a large and under-tested surface — and the kind of thing that produces a figure nobody can check against its data |
| **pandas + matplotlib** | — | **pandas rejected**: a DataFrame is a second, larger object model beside the closed and typed operator argument models LC-P1-10 already has, and the values the operators manipulate are lists of `(position, value, unit)` triples. A list is enough |

**The "no dependency" option was real and was not skipped.** Drawing the SVG
by hand would give LabCairn total control over the bytes and no install
weight. It was rejected because the work order asks for a *Matplotlib* figure
and because reimplementing chart layout is precisely the kind of surface that
produces a figure which looks right and does not match its data — the failure
LC-P1-08's two-column detector exists to prevent.

## Decision

**LC-P1-10 will depend on `matplotlib>=3.9,<4` (locked at 3.11.2), and the
figure renderer must set two rcParams before it draws anything.**

The declaration, the comment beside it and the lock are all in
`pyproject.toml` and `uv.lock`. The lockfile change is **purely additive**:
seven new packages, 130 inserted lines, no existing version moved.

### What the dependency brings

Resolved with `uv lock` and read from the **installed** distributions, not
from the package index.

| Package | Version | Licence, as declared by the distribution | New? |
|---|---|---|---|
| matplotlib | 3.11.2 | "License agreement for matplotlib versions 1.3.0 and later" (PSF-style; notice must be retained) | yes |
| numpy | 2.5.4 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` (PEP 639 expression; 19 licence files in the wheel) | yes |
| fonttools | 4.67.0 | MIT, plus `LICENSE.external` for the fonts it bundles for testing | yes |
| contourpy | 1.4.0 | BSD-3-Clause | yes |
| pyparsing | 3.3.3 | MIT | yes |
| kiwisolver | 1.5.1 | Modified BSD | yes |
| cycler | 0.12.1 | BSD-3-Clause (matplotlib project) | yes |
| pillow | 13.0.0 | MIT-CMU (attribution required) | already present via pdfplumber |
| packaging | 25.0 | Apache-2.0 OR BSD-2-Clause | already present |
| python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause | already present |

**No strong copyleft anywhere in the tree.** The obligations that do exist are
attribution, and both were already carried by ADR-0008 (Pillow) or are new and
recorded below (the fonts).

**Weight: 78.7 MB added to every install**, measured as the bytes of the files
each distribution owns — numpy 42.0 MB, matplotlib 23.3 MB, fonttools 12.1 MB,
the rest under 1 MB each. That is paid by every user and every CI run whether
or not they draw a figure, and it is the price of a library that draws the
figure rather than one that writes SVG primitives.

**Typing: matplotlib ships `py.typed`**, so `mypy --strict` checks LabCairn's
calls into it. That is a benefit — it is why this ADR does not need the
`[[tool.mypy.overrides]]` escape hatch that `pdfplumber` requires — and it is
a cost in the sense that matplotlib's inline annotations are partial, so some
of its surface will read as untyped to a strict checker.

### Licence obligations

Three, and all three are checkable rather than asserted.

1. **matplotlib's own licence is permissive and requires its notice.**
   Read from `matplotlib-3.11.2.dist-info/LICENSE` (63,442 bytes), the
   granting clause is: MDT grants a *"nonexclusive, royalty-free, world-wide
   license"* to use, modify and distribute matplotlib *"provided, however,
   that MDT's License Agreement and its notice of copyright … are retained"*.
   Retaining the notice is the whole obligation, and the file travels inside
   the wheel.

2. **matplotlib redistributes forty TrueType fonts under two further
   licences**, and this is the obligation that a root-level licence line
   would hide:
   - `matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU` — the **Bitstream Vera**
     licence: permissive, **the notice must be included in all copies**, and
     *modification requires renaming away from "Bitstream" and "Vera"*.
   - `matplotlib/mpl-data/fonts/ttf/LICENSE_STIX` — the **SIL Open Font
     License 1.1**, which permits redistribution unmodified and requires
     renaming away from the reserved font names after modification.

   matplotlib ships the fonts **unmodified as to the Bitstream requirement**
   (they are named `DejaVu*`, not `Vera*`), and for STIX it *did* modify them
   — the licence file says so in its own words: *"The STIX fonts distributed
   with matplotlib have been modified from their canonical form. They have
   been converted from OTF to TTF format"* — and it renamed them accordingly,
   so that none of the shipped files carries the reserved name "STIX Fonts".
   **The obligation was met, and the wheel documents the modification rather
   than concealing it.**

   So the G5 licence audit must cover **the bundled fonts and not the root
   licence line alone**. That is precisely the failure ADR-0004 recorded for
   paper-qa, where *"the root license line in that catalog's table is accurate
   for the root and misleading for one subdirectory."*

3. **numpy redistributes components under several further licences.** Its
   PEP 639 expression is `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`,
   and the wheel carries nineteen licence files — LAPACK (`numpy/linalg/
   lapack_lite/LICENSE.txt`), Highway (Apache-2.0), x86-simd-sort, pocketfft,
   Intel SVML, the Mersenne Twister, libdivide, pythoncapi-compat, and
   others. Every one is permissive, and every notice is inside the wheel.

`tests/test_analysis_dependency.py` asserts that the fonts are present **and
that a licence file sits beside them**, and that matplotlib's own licence file
is present in its `dist-info`. A matplotlib that dropped the fonts, or the
notices, would fail the test rather than quietly narrow an obligation.

### What was measured

Two claims about matplotlib's output, both measured rather than assumed, and
both of which the acceptance clause depends on.

**1. A figure's bytes are not stable by default, and the reason is not the
one you would guess.** Two SVG renders of the same data, in one process:

| Configuration | Two renders identical? |
|---|---|
| matplotlib defaults | **No** |
| `svg.hashsalt` fixed | **No** |
| `svg.hashsalt` fixed **and** `metadata={"Date": None}` | **Yes** |

**Fixing the salt alone is not enough.** matplotlib writes a **creation date
into the SVG metadata**, and two renders a second apart get different ones. A
renderer that set the salt and stopped there would produce different bytes on
every run while looking entirely deterministic.

**2. The two controls govern different things, and neither is sufficient
alone.**

- The **date** is the within-process control. Suppressing it is what makes
  two renders in one process identical.
- The **salt** is the cross-process control. Left unset, matplotlib generates
  a **fresh random salt per process**, so the element ids in an SVG differ
  between interpreters and the bytes differ even with the date suppressed.

This is why the test file has two separate assertions and why the
cross-process one spawns a second interpreter: **within a single process the
default salt is constant**, so a test that rendered twice in one process would
pass with the salt removed. That is a test that looks like a test and is not
one.

**3. PNG needs neither control.** Two default PNG renders are already
byte-identical, and two PNG renders in two separate processes are identical
too. matplotlib's PNG metadata carries a constant `Software` string and no
date. The two formats therefore have **different** determinism requirements,
and a renderer that assumed one rule for both would be wrong about one of
them.

**4. Cross-process, with both controls, the bytes match.** Measured by
running the same render in two separate interpreters:

```
  SVG  59216e51b733e0a879de6c793f507fc481892c5b3f5e8dd803cc1d659d3858a5  (both processes)
  PNG  a96dfc34408de2731f72ce583e9fb2bea41b6d5c1e75e0de467192a3346e1cc8  (both processes)
```

**What was not measured, and is not claimed:** byte-identity **across
machines**. Two machines may have different font files, and matplotlib
resolves fonts from the system before its own bundled set. The determinism
claim LC-P1-10 makes is the one its owner chose — *byte-identity inside one
recorded environment* — and the environment fingerprint in the manifest is
what makes "identical inputs" mean something.

## Constraints this places on LC-P1-10

1. **The renderer must set `svg.hashsalt` to a fixed value and must suppress
   the SVG creation date.** Both, always. T07 owns this; the test above is
   what proves the recipe works.
2. **The renderer must select the `Agg` backend explicitly** rather than
   inherit one. `matplotlib.use("Agg")` after the import, and `MPLBACKEND=Agg`
   before it, because a session where something else imported pyplot first
   may already have a backend.
3. **`MPLCONFIGDIR` must be pinned**, and the font cache built once.
   matplotlib writes a font cache on first use, and its location is part of
   what makes a render environment-dependent.
4. **`rcParams` must come from a declared, hashed defaults file**, not from
   whatever the ambient `matplotlibrc` says. An ambient configuration is an
   input nobody put in the manifest, and an unrecorded input is an input the
   reproducibility claim cannot cover.
5. **matplotlib must be imported lazily**, like `pdfplumber` and `openpyxl`
   already are, so that the text, Markdown, CSV and XLSX paths do not pay for
   it. This is a requirement on T07's module, not a fact about the code — the
   renderer did not exist when this ADR was written, and the module that
   draws the figure now imports matplotlib inside the function that draws it.
6. **The figure's hash is environment-scoped**, and the manifest must record
   the environment. A matplotlib upgrade changes every figure hash, and the
   fingerprint is what makes the change visible rather than silent.

## What this ADR does not decide

- **Whether a figure is a PNG or an SVG.** T07's, and the two have different
  determinism requirements, as measured above.
- **What a chart recipe contains**, and whether a caption may carry an
  interpretation. T06's.
- **What the manifest holds.** ADR-0004's contract already fixes the six
  fields, and §2.2 of the LC-P1-10 breakdown maps them.
- **Whether the recipe is executed.** It is not, and this ADR does not change
  that: the recipe is declarative data consumed by a registered operator.
- **Whether the figure's numbers are re-checked by the cite-support checks.**
  They are not, and that is §1.4.4 of the LC-P1-10 breakdown, which
  establishes it as a structural consequence of `source_anchors` being
  constrained to the four extractable locator kinds.

## Known gaps

- **This ADR and the test that checks it are the same party.** ADR-0008
  records that its licence reading was *"independently re-derived by a
  reviewer who was not the author"*. That did not happen here, and the
  project board's rule — a row is marked done only when an **independent**
  review at a named commit says so — is therefore **not discharged** for
  T00 either. The same caveat is on LC-P1-08 and LC-P1-09.
- **The licence reading was done on one platform.** The wheels for Windows,
  Linux and macOS were not compared. A platform-specific wheel carrying
  additional third-party components would not have been seen.
- **The version floor is a judgement, not a measurement.** `>=3.9` was
  chosen because it is the first release series with full Python 3.12
  support, and because the determinism controls above predate it. It was not
  chosen by rendering a figure on every version from 3.9 to 3.11.
- **The 78.7 MB is measured as installed bytes on one platform.** The wheel
  sizes differ per platform, and a Linux install of the same tree is not the
  same number of bytes.
- **The ambient-`matplotlibrc` risk is designed against, and has since been
  measured.** The constraint is that rcParams come from a declared file; the
  measurement this ADR left open was made by T07, which renders with a
  hostile `matplotlibrc` in place — changing the size, the font, the
  resolution, the save box and the salt — and the declared values win.
- **A figure has been produced since this ADR was written.** Everything above
  says the library can produce a deterministic figure; the first real one was
  T07's, and it is in `main`.

## Re-evaluation trigger

Re-open if any of the following happens.

1. **A matplotlib release changes the output.** The version is in the
   manifest's environment fingerprint, so a change is visible in the record
   rather than silent. What would need re-deciding is whether the two
   controls are still exactly two, and the test file answers that by failing.
2. **A figure's hash is found to differ between two runs on the same
   machine.** That is the determinism claim breaking, and the first thing to
   check is whether `rcParams` came from the declared file or from an ambient
   configuration.
3. **The install weight becomes a problem** — a user refusing to install, or
   a distribution decision that matplotlib's footprint is too large. The
   alternative in that case is the one §"Alternatives" rejected: hand-written
   SVG. That is a real option, not a rhetorical one, and this ADR would have
   to be superseded rather than amended.
4. **The G5 licence audit finds an obligation the wheel does not satisfy.**
   The audit is the place where the fonts are actually looked at, and this
   ADR's reading is a reading and not the audit.
