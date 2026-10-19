# LC-P1-10 — Bounded scientific analysis and plots: task breakdown

**Status:** ready to implement. Detailed decomposition only — nothing here is
implemented, and this document does not authorise starting without the owner's
go-ahead.
**Subject when written:** `main` @ `a7a2f48`
**Date:** 2026-10-19
**Gate:** G3. LC-P1-10 is the last of the three work orders G3 contains.
**Preceded by:** [LC-P1-09 acceptance](../acceptance/LC-P1-09-acceptance.md) —
PASS WITH NOTES, merged `a7a2f48`.

## 0. How to read this document

Section 1 fixes what is in and out. Section 2 describes the shape of the thing
being built, because four separate decisions in it are load-bearing and easier
to reason about in one place than spread across eleven subtasks. Section 3 is
the work, in dependency order, with a file-ownership map so parallel agents do
not collide. Section 4 maps the work order's acceptance clauses and the ADR
conditions it touches onto the subtask and test that carry each one. Section 5
records what this work order cannot deliver and why.

Every claim about what "cannot" happen is a refusal or a state, never an
absence. That is the project's standing rule, and in this work order it has a
specific consequence: several things here are refused **structurally** — the
schema will not hold them — rather than by a policy that the next writer could
relax. Those are marked.

## 1. Goals and boundaries

### 1.1 What LC-P1-10 must produce

From the work order: *typed vetted analysis operations (descriptive statistics,
grouped aggregates, charts) on consented CSV/XLSX; reproducibility manifest
(input file hash, selection, operator version, parameters, script/recipe,
output hash); deterministic Matplotlib figure with editable source. Explicitly
no general-purpose model-authored code execution.*

Concretely, by the end:

1. A **catalogue of vetted operators**, statically registered, each with a
   closed argument model and a version, and **no registration path that accepts
   code**.
2. A **typed selection** over a consented CSV or XLSX source — which columns,
   which rows, and what to do about missing and invalid cells — that yields
   values each of which is still individually addressable to a cell.
3. **Descriptive statistics and grouped aggregates** that recompute from the
   ingested representation of the source and report what they did with cells
   they could not use.
4. A **reproducibility manifest** carrying the six fields the work order names,
   recorded as an artifact, sharing one hash lineage with the ledger.
5. A **deterministic figure** with a **declarative, editable source** and a
   caption that says what is plotted, and that marks any interpretation as not
   machine-verified.

### 1.2 Already done — removed from scope

The contracts this work order implements against are frozen and typed, and in
one case they are *already written for this work order specifically*.

- **`analysis.run` is a registered capability** (`security/capabilities.py:76`)
  with a closed argument model, `AnalysisRunArgs` (`:229`), carrying `path`,
  `operator_id` and `parameters`. Its own docstring says there is **no field
  for a code fragment, an expression, a module path or anything else that could
  be evaluated**. The consent surface already exists and is the right one.
- **`ArtifactReceipt` already reserves LC-P1-10's outputs.**
  `ArtifactKind.FIGURE` is documented as *"A figure with its deterministic data
  source. LC-P1-10's concern."*, `ArtifactKind.MANIFEST` as *"A
  reproducibility manifest"*, and `ArtifactProducerKind.ANALYSIS_OPERATOR` as
  *"A vetted analysis operator (LC-P1-10)"* — with the example spelling
  `labcairn.analysis.mean@1.2.0` already in the class docstring
  (`reports/receipt.py:74`, `:81`, `:96`).
- **The `artifacts` table exists** (`db/models.py:490`) and mirrors that receipt
  field for field. **The manifest needs no migration.**
- **`ComputationLocator` already exists and is already specified**
  (`sources/locators.py:184`): *"A derived number → input hashes + operator +
  parameters. This is the locator for the claim '3.14 came out of this', and
  it is the reason LC-P1-10's reproducibility manifest and ADR-0004's evidence
  model can share one hash lineage (ADR-0004 'Re-evaluation trigger' 3)."* It
  requires non-empty, **sorted**, duplicate-free `input_hashes` and canonical
  `parameters`, and `describe_locator` already renders it.
- **Every cell that carries text is individually addressable.** `CsvAdapter` is
  documented as *"One unit per cell, addressed by row number and header name"*
  (`material/delimited.py:123`), and `CsvLocator.column` is the **header text**,
  not an index — *"a ledger that cites 'column 4' is unreadable to the person
  who has to check it"*. The XLSX adapter addresses one unit per **non-empty**
  cell, so an empty spreadsheet cell has no address at all — see T03, where
  that asymmetry turns out to matter.
- **The locator key grammar is canonical** and has one producer,
  `render_locator_key` (`material/addressing.py:112`).
- **A quantity reader already exists and is strict.** `read_number`
  (`evidence/checks/c3.py:107`) accepts *one number and at most one token*,
  refusing prose, two figures and thousands separators, for a measured reason
  recorded in its docstring.
- **The unit discipline is already decided.** C3 compares unit *tokens as
  written* and never converts (`c3.py:308`): `kg` against `g` fails, and so does
  `kg` against `kilograms`, with the detail naming both tokens.

### 1.3 Explicitly NOT in LC-P1-10

- **Any model call.** The operators are deterministic. A model may *propose* a
  selection — that is LC-P1-07's `propose` stage — but nothing here asks a
  model anything.
- **Report rendering.** LC-P1-11. A figure and its manifest are produced here;
  neither is placed in a document here.
- **Unit conversion.** Decided, §1.4.1.
- **Inferential statistics** — no p-values, no confidence intervals, no
  hypothesis tests, no regression fits. A p-value is a claim about a
  *population*, which is C4's subject: the system cannot check it and must not
  imply it. Descriptive statistics and grouped aggregates are claims about *the
  data that was there*, which is a different kind of claim and one the manifest
  can support.
- **Putting an aggregate in the evidence ledger.** Decided, §1.4.4, and
  refused structurally.
- **Cross-environment byte-identical figures.** Decided, §1.4.3.
- **An editor for the recipe.** The recipe is edited in a text editor.
  LC-P1-12's UI may offer one; Phase 1 does not.
- **A spreadsheet in the corpus with two-column detection.** LC-P1-08's
  limitation, unchanged.
- **Anything that reads a source file directly.** The analysis layer reads the
  ingested representation (§2.3).

### 1.4 Four decisions the owner took, and what each one costs

Recorded here rather than in the ADR, because they are the owner's and they
shape the subtasks. Each is dated 2026-10-19.

#### 1.4.1 Units are compared as written and never converted

The analysis layer inherits C3's discipline. A selection whose cells carry
different unit tokens is **refused**, not converted; a cell with no token
leaves the declared unit unverified.

*Cost:* `kg` and `kilograms` are one unit spelled two ways, and a selection
containing both is refused. This is a false negative, which is exactly what
ADR-0004 R2 warns about, and the refusal names both tokens so the reader can
see what the check did not do.

*Why not a conversion table:* a conversion table is a unit algebra, and the
arithmetic of that algebra would need the evidence standard this ledger
enforces. Phase 1 has no such standard. C3 already declined to build one, and
two layers of the same product answering unit questions differently would be
worse than one layer refusing.

#### 1.4.2 The editable source of a figure is a declarative chart recipe

A JSON document — operator, selection, encoding, output — that a person edits
by hand and that a vetted chart operator renders. **There is no code
execution surface**, which is what makes the work order's *"Explicitly no
general-purpose model-authored code execution"* satisfiable rather than
aspirational.

*Cost:* the recipe is not Python, so a reader who wants to see "how the figure
was drawn" reads a schema, not a script. That is the price of not having an
execution surface, and it is cheaper than the alternative.

*Why this and not a Python script:* a human-editable script that is then
executed is code execution, and Phase 1 explicitly does not promise an OS-level
sandbox (`ARCHITECTURE.md:27`, `:88`). A restricted runner is a new escape
surface, and this project has already had a boundary that was meant to be
structural turn out to be a convention — LC-P1-08's two-column PDF stored
sentences the author never wrote and marked them citable, because the refusal
was written down and not enforced.

#### 1.4.3 The determinism claim is byte-identity within one recorded environment

The manifest records an environment fingerprint — matplotlib version,
`svg.hashsalt`, font policy, platform — and the test renders twice in one
environment and compares bytes. Across environments the claim is **semantic
only**: the same marks, the same values, not the same bytes.

*Cost:* the figure's `content_sha256` is environment-scoped, so the same input
on another machine yields a different hash. That is a fact about rendering
rather than a defect, and the manifest says so instead of implying a
portability it does not have.

*Why not byte-identity across environments:* that requires pinning the font
files and shipping them (a redistribution and licensing question), and pins
the project to one matplotlib version — a matplotlib upgrade would invalidate
every figure hash. The honest, cheaper claim is the one above.

#### 1.4.4 An aggregate is an artifact, and is not in the evidence ledger

The aggregated number is recorded as a manifest and a figure, both
`ArtifactReceipt` rows. It is **not** an `EvidenceRecord`.

This was not a free choice — the schema had already decided it. `EvidenceRecord`
cites `anchor_ids`, which name rows in `source_anchors`; that table's
`locator_key` is CHECK-constrained to the four *extractable* kinds
(`db/models.py:1085`, `source_anchors_locator_key_vocabulary`), and
`render_locator_key` **raises** for `LocatorKind.COMPUTATION` because a derived
number has no address in `source_texts` (`material/addressing.py:103`). A
computation is therefore **not citable through the ledger, structurally**.

*Cost, stated plainly:* **a figure's numbers are traceable to the input file
but are not re-checked by C1, C2 or C3.** The manifest is their audit trail
instead. The ledger keeps doing what it is good at — statements about located
cells — and the derivation keeps its own manifest. §5 states this as a
limitation rather than closing it.

## 2. The shape of the thing

### 2.1 The path from a file to a figure

```text
  runs/exp1.csv
        │
        │  ingest (LC-P1-08, done)
        ▼
  sources row (content_sha256 = H)  ·  source_texts row per cell
        │                            (locator_key = k=3:csv|r=2:12|c=4:mean)
        │  analysis.run  (capability, consent = approval digest)
        ▼
  selection  ── which columns, which rows, what to do with a cell
        │      that is empty or not a number
        ▼
  operator  ── labcairn.analysis.mean@1.0.0
        │      (registered; the catalogue is a module constant)
        ▼
  result  ── value, n_used, n_missing (tri-state), n_invalid, unit
        │
        ├─► ComputationLocator(operator_id, operator_version,
        │                     parameters={selection, ...},
        │                     input_hashes=(H,))
        ▼
  manifest  ── the six fields + the environment fingerprint
        │      (canonical JSON; hashed; an ArtifactReceipt, kind=MANIFEST)
        │      ← the manifest is written FIRST; it hashes the result,
        │        not the figure
        ▼
  figure  ── recipe → matplotlib → figure.svg
             (an ArtifactReceipt, kind=FIGURE,
              derived_from = [manifest, material file])
```

**The order matters, and the alternative is circular.** The work order asks the
manifest for an *"output hash"*. If that were the **figure's** hash, the
manifest would have to be written after the figure — while the figure's
`derived_from` names the manifest. One of the two would be hashing a
document that does not exist yet.

So the manifest's *output hash* is the hash of the **result** — the operator's
output, in canonical JSON — and the figure's own hash is the figure artifact's
`content_sha256`, written when the figure is recorded. The chain is linear:

```text
  file (H) ──► result ──► manifest ──► figure
             (hashed)   (hashed)    (hashed)
```

Each link names the one before it, and nothing names something that has not
been written.

### 2.2 The manifest, and the six fields the work order names

| The work order says | Where it lives | Why there |
|---|---|---|
| input file hash | `ComputationLocator.input_hashes` — the source's `content_sha256` | one value, four views (§2.3) |
| selection | `ComputationLocator.parameters["selection"]` | canonical JSON; sortable; comparable |
| operator version | `ComputationLocator.operator_version` + the catalogue's entry | a version is a fact about the code that ran |
| parameters | the rest of `ComputationLocator.parameters` | canonical, no timestamps or counters — `ComputationLocator`'s own rule, for `ComputationLocator`'s own reason |
| script/recipe | the recipe file's path and hash | the recipe **is** the script, in the only form Phase 1 allows: declarative, editable, non-executable |
| output hash | the **result's** hash — the operator's output in canonical JSON, written into the manifest | the figure's own hash is the figure artifact's `content_sha256`, recorded when the figure is written. Hashing the figure *inside* the manifest would be circular (§2.1) |

### 2.3 One hash lineage, four views

ADR-0004's re-evaluation trigger 3 asks that the manifest and `EvidenceRecord`
share a single hash lineage, and notes that the alignment *"may change
`source_content_hash`'s definition"*. It does not have to, and here it does
not:

```text
  H = sha256(file bytes), lowercase hex
      │
      ├── sources.content_sha256                  (the material as ingested)
      ├── source_anchors.bound_source_sha256       (the address a record is bound to)
      ├── evidence_records.source_content_hash     (a fact, as read at extraction)
      ├── ComputationLocator.input_hashes          (a derivation, over its inputs)
      └── manifest DerivationRef.content_sha256    (the artifact's chain)
```

**Two implementations of this definition already exist** —
`security/approval.py::content_hash(path)` (`:110`) and
`material/ingest.py::_content_hash(data)` (`:158`) — and both are SHA-256 of
the raw bytes in lowercase hex. They are the same definition. **LC-P1-10 must
not add a third.** The manifest's input hash reuses one of them, and T08
asserts that the value it writes is byte-identical to
`sources.content_sha256` for the same file.

`source_content_hash`'s definition is therefore **unchanged**, which is the
better outcome: the trigger anticipated a change and the measurement says none
is needed.

### 2.4 What a derived number is

A derived number is a `ComputationLocator`: an operator id, a version, the
parameters, and the sorted input hashes. It is not a source anchor, it has no
address in `source_texts`, and it is **not** citable through the evidence
ledger. The manifest carries it; the figure's `derived_from` carries the
manifest; the receipt chain carries the file.

This is the shape ADR-0004's trigger 3 was reaching for, and it was written
into the locator contract before this work order existed.

## 3. Subtask breakdown

### File ownership map (this is the parallel contract)

Two agents may work in parallel only if their file sets are disjoint. Claim a
file before editing it; if a subtask needs a file another subtask owns, say so
in the PR rather than editing it.

| Subtask | Owns exclusively |
|---|---|
| T00 | `pyproject.toml`, `uv.lock`, `docs/adr/ADR-0012-*.md` (the dependency decision) |
| T01 | `tests/fixtures/analysis/**`, `tests/test_analysis_fixtures.py` |
| T02 | `src/labcairn/analysis/__init__.py`, `src/labcairn/analysis/operators/__init__.py`, `tests/test_analysis_operator_contract.py` — **the catalogue lands with T04**, §3b |
| T03 | `src/labcairn/analysis/selection.py`, `src/labcairn/analysis/values.py`, `src/labcairn/sources/quantity.py`, `src/labcairn/evidence/checks/c3.py` (**the quantity reader only**), `tests/test_analysis_selection.py`, and `tests/analysis_fixtures.py` (**the corpus reader and row vocabulary**, which T01's test now shares) |
| T04 | `src/labcairn/analysis/operators/descriptive.py`, `src/labcairn/analysis/units.py`, `src/labcairn/analysis/catalog.py` (**the catalogue**, which cannot exist before the operators it registers — §3b), `tests/test_analysis_descriptive.py`, `tests/test_analysis_catalog.py` |
| T05 | `src/labcairn/analysis/operators/grouped.py`, `tests/test_analysis_grouped.py`, and `tests/test_analysis_catalog.py` (**one line** — the catalogue test is T04's and had to learn about the eighth operator) |
| T06 | `src/labcairn/analysis/chart/__init__.py`, `src/labcairn/analysis/chart/recipe.py`, `tests/test_analysis_recipe.py` |
| T07 | `src/labcairn/analysis/chart/render.py`, `tests/test_analysis_render.py` |
| T08 | `src/labcairn/analysis/manifest.py`, `tests/test_analysis_manifest.py` |
| T09 | `src/labcairn/analysis/service.py`, `tests/test_analysis_service.py` |
| T10 | `examples/analysis_demo.py` |

**One deliberate cross-ownership:** T03 edits `evidence/checks/c3.py`, which
LC-P1-09 owned. It is sequenced after LC-P1-09's merge and it edits exactly one
thing — the *location* of the quantity reader — and the obligation is that
**C3's existing tests pass unmodified**. That is the proof the move changed no
behaviour, and it is why T03 is not parallel with anything that touches the
evidence package.

**T02, T06 and T08 all read the catalogue**, so it is written first and
frozen. T04 and T05 both read the selection, so T03 precedes them.

### T00 — the dependency decision

matplotlib is not a dependency today. `pyproject.toml` declares pydantic,
pydantic-ai, sqlalchemy, openpyxl, pdfplumber and alembic — and **no numpy, no
pandas, no matplotlib**. LC-P1-10 needs matplotlib because the work order
names it.

**The licence is verified from the distribution, not from metadata.** Measured
on 2026-10-19 against the `matplotlib-3.11.2` wheel (the latest on PyPI that
day), reading the files inside the wheel rather than the package index:

- `matplotlib-3.11.2.dist-info/LICENSE` — *"License agreement for matplotlib
  versions 1.3.0 and later"*: a PSF-derived, permissive licence. It grants
  redistribution provided MDT's notice is retained.
- `matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU` — the Bitstream Vera licence
  (permissive; the notice must travel with the fonts; **modification triggers
  a rename requirement**; the DejaVu changes are in the public domain).
- `matplotlib/mpl-data/fonts/ttf/LICENSE_STIX` — **SIL Open Font License 1.1**.

All three permit redistribution of LabCairn under MIT, **provided the fonts
travel unmodified with their licence files**, which is what the wheel does.
The obligation for G5 is therefore explicit: the licence audit must cover **the
bundled fonts**, not the root licence line alone. That is precisely the failure
ADR-0004 recorded for paper-qa, where *"the root license line in that
catalog's table is accurate for the root and misleading for one subdirectory."*

Other decisions this subtask makes:

- matplotlib is **loaded lazily**, like `pdfplumber` and `openpyxl` already are,
  so the text and Markdown paths do not pay for it.
- `MPLBACKEND=Agg` is set **explicitly** rather than inherited, and
  `MPLCONFIGDIR` is pinned — matplotlib's font cache is written on first use
  and its location is part of what makes a render environment-dependent.
- numpy arrives as matplotlib's dependency and is pinned in `uv.lock` like
  everything else.
- **pandas is not taken.** A DataFrame is a second, larger object model, and
  the operators' argument models are already closed and typed. The values this
  work order manipulates are lists of `(position, value, unit)` triples, and a
  list is enough.

The ADR for the dependency follows ADR-0008's shape: it decides the
**library** and nothing else.

### T01 — the fixture corpus

**Measured: the repository contains no CSV and no XLSX file at all.**
`tests/fixtures/` holds `papers/` and `retrieval/`; a repository-wide search
for `*.csv` and `*.xlsx` returns nothing. Every C3 case in LC-P1-09 is a row
written by a test, and the LC-P1-09 acceptance review says so in as many
words: *"There is no spreadsheet in the fixture corpus, so every C3 case is a
row written by a test."*

So the corpus is a **deliverable of this work order**, not an input to it. The
acceptance clause *"numerics recalculated from source with controlled
fixtures"* cannot be discharged without one, and no amount of testing against
rows synthesised inside a test function is a fixture.

The corpus is controlled **by construction**: the numbers are chosen so their
statistics are closed-form and checkable by hand and by any independent tool.

| Fixture | Contents | What it is for |
|---|---|---|
| `basic.csv` | `value` = 1..10, `group` alternating A/B | the reference case. mean 5.5, median 5.5, population stdev √8.25 = 2.8722813232690143, sample stdev √(82.5/9) = 3.0276503540974917; group A mean 5, group B mean 6, counts 5 and 5, sums 25 and 30 |
| `groups.csv` | three groups of unequal size | a group boundary that is off by one shows up as a wrong **mean**, not merely a wrong count |
| `units.csv` | cells carrying a unit token (`3.5 kg`), and one row whose unit differs | the mixed-unit conflict, and the cell that carries no token |
| `missing.csv` | an empty cell, a non-numeric cell in a numeric column, a trailing blank row | "reported, not silently imputed" |
| `typed.csv` | a header that declares a unit (`mass (kg)`) | the header-declared unit path |
| `single.csv` | exactly one value | a sample stdev that is **undefined**, and must not be 0 (ADR-0004 A8) |
| `empty.csv` | a header and no rows | an empty selection, and a mean that is undefined rather than 0 |
| `numeric.xlsx` | the same numbers as `basic.csv` | the CSV and XLSX paths must agree |
| `holes.xlsx` | `basic.csv`'s numbers with one **interior** cell empty | the format asymmetry, measured rather than assumed: CSV emits an empty cell, XLSX leaves no row for one (T03), so the missing count is knowable in one format and unknown in the other |

Two properties make this corpus usable rather than decorative:

- **The expected values live beside the data, not inside the test.** Each
  fixture has a companion expected-values file written by hand. The test
  compares the operator's output against those values, so a bug in the operator
  cannot produce the expectation it is checked against.
- **The XLSX fixture is generated by a script in the corpus directory** and its
  content asserted to equal `basic.csv`. A binary blob committed to the
  repository cannot be reviewed; a generator can, and the assertion is what
  makes it a fixture rather than a convenience.

**The corpus needs a shared fixture writer, and none exists.** Every test
file that touches a CSV today writes it inline — `(sources / "data.csv").
write_text("trial,mean\nalpha,3.5\n", encoding="utf-8")` — and every test file
that touches an XLSX builds its own `openpyxl` workbook in memory. There is no
shared helper, and LC-P1-10 needs one for two reasons: the corpus has to be
**written the same way** every time, or the CSV and XLSX paths are not
comparable; and a corpus whose expected values are written by a script needs
that script to be the one thing that produces the file, not one of several.

The helper belongs to T01 and is the only file T01 adds to `tests/` besides the
corpus itself.

**The corpus is checked by the same rules as the code.** The expected-value
files are hand-written, so a change to the operators that alters a result
fails a test rather than silently updating a golden file.


### T02 — the operator catalogue

The pattern is `evidence/catalog.py`'s, and it is copied rather than invented:
`RULE_CHECKER_IDS` is a frozenset **built from the check modules' own id
constants**, so one id has one spelling and there is no runtime registration
path. LC-P1-10's catalogue does the same.

Each entry carries:

- `operator_id` — `labcairn.analysis.mean`
- `operator_version` — `1.0.0`
- `args_model` — a **closed, frozen** Pydantic model (`extra="forbid"`, like
  `security/capabilities.py::_Args`), so a typo in a parameter is an error
  rather than a silently ignored key
- `result_model` — what the operator returns
- `accepted_locator_kinds` — `csv` and `xlsx`, and nothing else
- `summary` — one line, for a human reading an approval prompt

**The operator reference has exactly one spelling:**
`"labcairn.analysis.mean@1.0.0"`, split at the **last** `@` into
`ComputationLocator.operator_id` and `.operator_version`. That is the spelling
`reports/receipt.py`'s own docstring uses, and a second spelling would be a
second way for two runs to compare unequal.

**The catalogue is a module-level constant.** That is the structural half of
*"no general-purpose model-authored code execution"*: an operator id that is
not in the constant cannot be run, because there is no code path that could run
it. The `analysis.run` argument model has no field that could carry code
either (`security/capabilities.py:229`), so the two halves agree.

The catalogue also holds the **version** of each operator, and a version bump
is a code change that changes the manifest. That is what makes "operator
version" in the manifest a fact about the code that ran rather than a label.

### T03 — the selection, and the quantity reader

**A selection is a typed, closed description of which cells to use.** It
names:

- the **source**, by `source_id` and its content hash;
- the **columns**, by header text — never by index, because `CsvLocator.column`
  is the header text deliberately;
- the **rows**, as a contiguous range, a set of row numbers, or a filter over
  one column;
- the **policy for cells that cannot be used** — `exclude` or `refuse` — which
  is **declared, not defaulted**, because a default is a silent decision about
  the data.

**A filter is a closed structure**, not an expression:
`{"column": "value", "op": ">", "value": 0}`, with a fixed set of operators
and a fixed set of value types. There is no expression language, because an
expression language is a program and §1.4.2 rules those out.

**Where the values come from.** The values are read from `source_texts` through
the anchor registry, **not** by re-opening the file. That is what
`locate_anchor` does (`evidence/index.py:544`): it reads the stored text for
the anchor's `locator_key` and joins `sources` for the `readability`.

This is worth being precise about, because the work order's phrase *"numerics
recalculated from source"* can be read two ways. What LC-P1-10 guarantees is
narrower and stronger than "re-read the file":

> The numbers are recomputed from the **ingested representation** of the
> source, and that representation is **bound to the file's hash**. If the file
> changes, the hash no longer matches and the derivation is stale (ADR-0004
> I4) — it is not silently re-run against new bytes.

Re-reading the file at analysis time would make the result depend on a file
the ledger has not seen, which is the drift I4 exists to prevent.

**The quantity reader is C3's, and there is only one.** `read_number`
(`evidence/checks/c3.py:107`) already implements the strict rule — one number
and at most one token — for a measured reason: in the corpus, half the words
that follow a number are prose, so a rule that reads the next word as a unit
invents units that do not exist.

The analysis layer must use **the same definition** of "a quantity". Two
definitions would mean the ledger and the analysis disagreed about what a
number is, and the disagreement would be invisible until they were compared.
So the reader moves to a shared home — `labcairn/sources/quantity.py` — and
C3 re-points at it.

*Obligation:* **C3's existing tests pass unmodified.** That is the proof the
move changed no behaviour, and it is why this is an owned, sequenced edit
rather than a convenience. A reader who wants to be sure can read the diff and
see that the only change is where the function lives.

**Units.** The analysis layer inherits C3's discipline, with three rules:

- a cell that carries a unit token must carry the **same token** as every other
  cell in the selection, or the operator refuses and names both;
- a column header of the form `name (unit)` may declare a unit for that column,
  and the recipe's declared unit must match it — **but only if the
  parenthesised token looks like a unit at all**: letters, digits and symbols
  only, no spaces. A header like `result (see table 2)` declares **nothing**,
  because treating the words after a number as a unit is the exact mistake
  C3's docstring refuses to make — half the words that follow a number in a
  real corpus are prose. A header that declares a unit and a recipe that
  declares a different one is a **conflict**, reported with both tokens, not
  something either side silently wins;
- a cell with **no** token leaves the declared unit **unverified** — the same
  asymmetry C3 keeps, where a bare numeric cell has no unit to contradict and
  the record's declared unit is left standing.

The header rule matters because a real table almost never puts units in its
cells: `mass_kg` or `mass (kg)` is the convention, and a check that only ever
looked at cell text would find no unit to check and pass vacuously. That
would be a check that looks like a check and is not one — the failure ADR-0004
R2 names, where a check whose aggressiveness is invisible generates false
confidence.

**Used, missing and invalid are three different facts — and "missing" has two
causes.** The result carries `n_used`, `n_missing` and `n_invalid`, and the
policy that produced them is in the selection, so the manifest records it.
**A blank cell is never 0** — it is counted and reported.

The two causes of *missing* are worth separating, because they are not the same
event and the adapter already tells them apart:

- **The cell exists and is empty.** It is a `source_texts` row whose `text` is
  the empty string. The author put a cell there and left it blank.
- **The cell does not exist.** A ragged CSV row, a cell beyond the header, a
  duplicate or blank header — the adapter records these as
  `ExtractionProblem` rows and **never pads** them, in its own words because
  *"an invented empty cell is indistinguishable from a measured one"*
  (`material/delimited.py`). There is no text to read, so there is nothing to
  count as a value.

Collapsing the two would let "the row was short" read as "the value was
zero", which is the imputation the acceptance clause forbids.

A third case is a cell that is **not a number at all** in a numeric column: a
word, a date, a stray symbol. That is `n_invalid`, not `n_missing` — the data
is present and it is not usable, which is a different fact from the data not
being there.

**An XLSX formula with no cached value is not a number.** The spreadsheet
adapter records it as a problem and **invents no value**
(`material/spreadsheet.py:175`, `xlsx_formula_without_cached_value`). Such a
cell is `n_invalid` for the same reason, and the selection must not evaluate
the formula.

**And the two formats do not agree about what an empty cell is.** This was
measured against the adapters, not assumed, and it is the acceptance clause
biting in a place nobody expected:

- **CSV emits an empty cell.** A field present in a well-formed row becomes a
  `source_texts` row whose `text` is `""`, with a locator. An empty CSV cell
  is therefore *observable*: countable and addressable.
- **XLSX does not.** The spreadsheet adapter **skips** a cell whose value is
  `None` or blank (`material/spreadsheet.py:192`), so an empty XLSX cell
  leaves **no row at all**. The ledger holds the cells that carry text and
  nothing else.

The consequence is exact. For the same table, a CSV selection can count its
empty cells and an XLSX selection **cannot** — and an empty XLSX cell is
indistinguishable from a cell beyond the sheet's used range. **The table's
rectangular extent is not recoverable from the ledger for XLSX.**

So the missing count is **tri-state**, modelled on `Known`/`Unknown`
(`core/providers/usage.py:114`, `:159`): a measured count, or an explicit
*unknown* with a reason. **Never `0` to mean "unknown"** — that is ADR-0004
A8, and it is the same rule that keeps `Known(0)` and `Unknown` from comparing
equal.

The reason vocabulary is **analysis-local**, not `UnknownReason`.
`UnknownReason` is a closed set about *provider telemetry* —
`PROVIDER_OMITTED`, `EXTRACTION_FAILED`, `UNPRICED`, `NOT_APPLICABLE` — with a
precedence order ADR-0002 fixed, and *"this sheet's extent is not
observable"* is not one of those things. The **pattern** is reused; the
vocabulary is local, and the reason is the same reason the unit discipline is
not shared with a conversion table: two layers answering one question in two
vocabularies is how a disagreement becomes invisible.

**Why the analysis layer does not re-read the file to get the extent.** It
could, and the file is the source. But the ledger is the app-owned authority
and the file may move, and a selection that took its *shape* from the file and
its *values* from the ledger would be assembled from two places that could
disagree. The analysis stays inside the ledger, and the gap is disclosed
rather than papered over by a second read.


**An unreadable source is refused.** `locate_anchor` returns `UNADDRESSABLE`
for a source whose `readability` is not `readable`, which is ADR-0004 A7's
distinction between *unreadable* and *no results*. The selection must refuse
it rather than analyse nothing and report a mean of zero rows.

**Naming.** `src/labcairn/analysis/units.py` would collide in spirit with
`src/labcairn/material/units.py`, which is about *extracted text units*, not
units of measurement. The analysis module is named `units.py` in a different
package and its docstring must say which sense it uses — the collision is the
kind of thing a reader resolves wrongly.

### T04 — descriptive statistics

Seven operators, each registered, each with a closed argument model:

| Operator | Result | Notes |
|---|---|---|
| `count` | integer | of the values **used**, not of the cells selected — the two differ exactly when the missing-value policy fired |
| `sum` | number | |
| `min`, `max` | number | |
| `mean` | number | |
| `median` | number | |
| `stdev` | number | takes a **required** `ddof`: 1 (sample) or 0 (population) |

**`stdev`'s `ddof` is required, not defaulted.** An absent choice is not a
choice, and a default would be a silent claim about which population was
meant — the same reasoning that keeps `tolerance` from defaulting to `0.0` in
C3. The result records which was used.

**Undefined is not zero.** The mean of an empty selection and the sample
stdev of a single value are **undefined**, and the result says so — never
`0.0`. This is ADR-0004 A8 (*"unknown is not zero"*) applied to statistics,
and `single.csv` and `empty.csv` exist to hold it in place.

**The value and the counts are shaped differently, and the difference is
deliberate.** A statistic's value has no meaningful zero — `0` is a real mean
— so the value is `float | None` with a **paired** reason, enforced by a
validator, in the style `EvidenceRecord` already uses for its own optional
fields. A *count* does have a meaningful zero — *zero cells were missing* is a
fact — so a count cannot be a bare `int` with `None` meaning "unknown" without
the two being confusable, and it is tri-state instead (T03). One is
`None`-with-a-reason, the other is `Known`/`Unknown`, and the reason they
differ is that **one of them has a real zero and the other does not**.


**Values only.** The argument model requires a numeric column. Strings are not
analysed in Phase 1: a categorical column's "mean" has no meaning, and the
operator that refused it is more useful than the operator that computed
something.

**Every result is a derivation, not a fact about a cell.** It carries the
selection it came from, and the selection — not the cell list — is what makes
it re-derivable. The cell list is recoverable from (source hash + selection);
storing it would be a second copy of a fact with its own staleness.

### T05 — grouped aggregates

**One operator**, `labcairn.analysis.grouped_aggregate`, whose `aggregate`
parameter **must name a registered descriptive operator**:

```json
{
  "operator": "labcairn.analysis.grouped_aggregate@1.0.0",
  "parameters": {
    "aggregate": "labcairn.analysis.mean@1.0.0",
    "by": "group",
    "of": "value"
  }
}
```

The grouped operator therefore **composes vetted operators** instead of
reimplementing the arithmetic. There is exactly one implementation of "mean"
in the codebase, and it is the same one the scalar operator uses. This is the
same discipline as `evidence/catalog.py`: the catalogue is built from the
implementations' own constants rather than a second list.

**Group keys are compared as written** and the group list is **sorted**, so
two runs over the same rows produce the same table in the same order. A group
key that is empty string is a group, and the result says so rather than
dropping it.

**An empty group is not representable.** A group exists because a row put it
there, so a filter that removes every row of a group removes the group. The
result's group list is complete and sorted, and the result reports how many
rows the filter removed and how many the missing-value policy removed — the
same disclosure the scalar operators carry.

**The result is a table**, not a scalar: a list of `(key, value, n_used)`
rows. A grouped aggregate that returned one number would have thrown away the
very thing that makes it grouped.

### T06 — the chart recipe

The recipe is the editable source, and its schema is the whole language:

```json
{
  "data": {
    "operator": "labcairn.analysis.grouped_aggregate@1.0.0",
    "parameters": {"aggregate": "labcairn.analysis.mean@1.0.0",
                   "by": "group", "of": "value"},
    "selection": {"source": "runs/exp1.csv", "columns": ["group", "value"]}
  },
  "encoding": {
    "mark": "bar",
    "x": "group",
    "y": "value",
    "title": "Mean by group",
    "x_label": "group",
    "y_label": "mean (kg)",
    "caption": "Group means over 10 rows.",
    "interpretation": null
  },
  "output": {"format": "svg", "dpi": 200}
}
```

**The chart's data is itself a vetted operator's output.** The recipe nests a
data recipe, so the figure's numbers are a descriptive or grouped operator's
result object — not a second reading of the file. That is what makes "charts
match data" a property of the code rather than a coincidence of two readers
agreeing.

**The caption and the interpretation are different fields, and the difference
is structural.** `caption` states what is plotted. `interpretation` states a
claim about what it means. ADR-0004 A10 says interpretation is never
machine-verified, so an interpretation rendered into a figure must carry the
marker — and the marker is the **renderer's** job, not the author's, so it
cannot be left out by forgetting:

- the recipe has a separate `interpretation` field;
- the renderer emits the interpretation with an explicit
  *"interpretation not machine-verified"* marker;
- a recipe with no interpretation carries no marker, because a caption that
  says what is plotted is not an interpretation.

This is the first place in the project where A10's marker is rendered rather
than merely prepared for, and it is A10's clause being discharged early
because the figure owns its own text.

**A recipe is frozen and canonical on write** — `frozen=True`,
`extra="forbid"` — and serialised as canonical JSON (sorted keys, UTF-8, no
whitespace variance), because the recipe's bytes are hashed into the manifest
and a recipe that serialises two ways cannot be compared.

**A recipe is not a program.** There is no expression, no template, no
reference to anything outside the workspace, and no way to name anything that
is not a registered operator, a declared column, or a literal value.

### T07 — the deterministic renderer

matplotlib, `Agg` backend, set explicitly.

The determinism controls, and why each one is needed:

| Control | Why |
|---|---|
| `svg.hashsalt` fixed | matplotlib generates element ids for SVG; without a fixed salt they differ per run |
| `metadata={"Date": None}` | matplotlib writes a creation date into SVG and PNG metadata by default, which alone makes every render differ |
| `savefig` with a fixed `dpi`, a fixed `figure.figsize`, and `bbox_inches` unset | the other three knobs that change the bytes |
| `MPLCONFIGDIR` pinned, font cache built once | the font cache is part of what makes a render environment-dependent |
| `rcParams` set from a **declared, hashed** defaults file | an ambient `matplotlibrc` is an input nobody put in the manifest, and an unrecorded input is an input the reproducibility claim cannot cover |

**The claim is byte-identity inside one recorded environment.** The manifest
records the environment fingerprint (§1.4.3), and the test renders twice in one
environment and compares the bytes. Across environments the claim is semantic
only, and the manifest says so.

**Untrusted text in a figure is data.** A group name or a cell value is
imported text and ends up in the SVG. matplotlib escapes `<`, `>` and `&` in
text, and the test **asserts** it: a group name of `<script>alert(1)</script>`
renders escaped, and the SVG contains no `<script` element. This matters
because an SVG embedded in an HTML report is a script context — LC-P1-11's
problem to handle, and it is only safe if the escaping holds at the source.

**The chart's numbers are the operator's numbers.** The renderer receives the
data operator's result object and plots it. It does not re-read the file, and
it does not re-implement the aggregate. If the two ever disagreed, the figure
would be showing something the operator did not produce.

### T08 — the reproducibility manifest

The manifest is **an `ArtifactReceipt` with `kind=MANIFEST`**, stored in the
existing `artifacts` table (`db/models.py:490`). **No migration is needed.**

- `produced_by = ANALYSIS_OPERATOR`
- `producer_id = "labcairn.analysis.chart.bar@1.0.0"` — the spelling
  `receipt.py`'s own docstring uses
- `derived_from = [DerivationRef(target_kind=MATERIAL_FILE, content_sha256=H)]`
  — `MATERIAL_FILE` and `ARTIFACT` are the two kinds that **must** carry a
  hash (`receipt.py:122`), and a chain link with no hash is a link nothing can
  invalidate
- `content_sha256` — the hash of the manifest document's own bytes

The figure is a second receipt, `kind=FIGURE`, whose `derived_from` is the
manifest artifact (with its hash) and the material file (with its hash).

**The manifest is canonical JSON**, and it uses the convention the project
already has rather than a second one: `LabCairnModel.json_canonical()`
(`core/schema.py:106`) — sorted keys, no incidental whitespace, `ensure_ascii=
False` — digested with the algorithm already named in the Skill's ledger,
`"sha256/canonical-json/v1"` (`skills/ledger.py:59`). Its hash is the hash of
those bytes. Two runs over the same inputs produce byte-identical manifests —
which is what lets a receipt be **compared** rather than eyeballed, and is the
same reason `ComputationLocator` requires sorted, duplicate-free input hashes.

**The file is written through the workspace writer.** `workspace/outputs.py` is
the only thing in the codebase that writes a file: atomic (a temp file in the
same directory, `fsync`, `os.replace`), output-root-only, and it reports
`CREATED` or `REPLACED`. An analysis that opened its own file would bypass all
four of those.

**The chain is checked by the contract, not by the schema.** `artifacts.
derived_from` is an untyped JSON column (`db/models.py:520`), so nothing in
the database refuses a manifest whose chain is wrong. The assertion that the
figure names the manifest's hash, and the manifest names the file's hash, is a
**test's** job — and §4.1 lists it as one.

**Two senses of "manifest" now exist, and they are not the same thing.** The
Skill's delivery artifact already has one: `DeliveredManifestEntry` is
`{relative_path, content_sha256}` — a *listing* of what a delivered report
contains (`skills/artifacts.py:584`). LC-P1-10's manifest is a *recipe for
reproducing a derivation*. They are different documents with different
readers, and the name collision is recorded here so the next writer does not
assume they are the same thing. LC-P1-11 owns the delivery listing.

**The environment fingerprint is part of the manifest** (§2.2). Without it,
*"identical inputs"* is undefined and the output hash is a number whose
meaning depends on a machine nobody recorded.

**The manifest asserts the lineage.** A test writes a manifest for a known
file and asserts that its input hash is byte-identical to
`sources.content_sha256` for that file, and that the figure's
`derived_from` names the manifest's own hash. If a third hash implementation
ever appears, that test fails.

### T09 — the run path

`analysis.run` already exists as a capability with the right argument model
(§1.2). This subtask builds the path that uses it:

```text
  resolve the source (readability, content hash)
      → build the selection (columns, rows, policy)
          → evaluate the operator (refusals are refusals)
              → write the manifest  (it hashes the *result*)
                  → render, if the operator is a chart
                      → write the figure
                          → record the receipts
```

The order is the one §2.1 fixes, and it is not incidental: the manifest
hashes the result, and the figure names the manifest, so writing the figure
first would make one of the two hash a document that does not exist.

**Consent is the existing approval machinery.** The `analysis.run` approval is
bound to the capability, the resource key and the arguments digest
(ADR-0003 §C4). A different selection is a different digest, so an approval to
analyse one selection does not authorise another.

**"Consented CSV/XLSX" has no code-side entity, and this subtask says which
one it means.** There is no `Consent` record, no per-file consent table, and no
`consented` flag on `sources`; the codebase's nearest neighbours are the
`Approval` (single-use, digest-bound, `runtime/operation.py:47`) and
`ResearchObjective.declared_materials` (material the researcher has declared
the task to be about, bound by content hash, `skills/artifacts.py:161`).

LC-P1-10 uses the **approval**, and the reading is worth stating because the
work order says *"consented"* and a reader will look for something that is not
there:

> A CSV or XLSX is *consented* when it lives inside an explicitly selected
> **source root** (read-only by construction — `ARCHITECTURE.md:85`) and the
> run is carried out under an `analysis.run` **approval** whose digest covers
> the path, the operator and the parameters. Both halves are already
> enforced: the root kind is checked before any rule matches, and a digest that
> does not match is a refusal.

What this does **not** claim: that the researcher gave a distinct "yes, analyse
this file" at the moment of the run. It is the *same* consent shape the rest of
the product uses for a local read — an approval bound to the arguments — and
naming it as something else would invent a mechanism that does not exist.


**Bounded resources.** `ARCHITECTURE.md:88` requires size and row limits and
timeouts *"where enforceable"*. A row limit and a cell-count limit **are**
enforceable in-process; a wall-clock timeout on an in-process numeric loop is
not. The limits that are enforceable are enforced, and the one that is not is
named as unenforced rather than shipped as a timeout that does not fire.

**Where the analysis runs in the workflow, and the gap that creates.** The
`research-report` Skill's stages are `intake → inventory → retrieve →
evidence → propose → draft → validate → deliver` (`skills/artifacts.py:66`) and
**none of them is "analyse"**. The operators therefore have no home in the
stage sequence as it stands.

This subtask does not add a stage — the Skill contract is LC-P1-07's, and
changing the stage list is a contract change rather than a wiring detail.
What it does is make the **run path callable from a stage boundary**: the
`evidence` stage produces the evidence ledger, and a figure plus its manifest
are the outputs of an analysis run, so the analysis belongs at the tail of
`evidence` or between `evidence` and `propose`, where the ledger already
exists. The concrete placement is LC-P1-11's and LC-P1-07's to make; the
requirement recorded here is that **the operators are callable at a stage
boundary at all**, rather than only from a test.

### T10 — the exit demonstration

`examples/analysis_demo.py`, in the shape of `examples/g2_exit_demo.py`:

1. ingest the controlled CSV;
2. run a grouped aggregate, and print the value **and the cells it came from**;
3. render a figure from the recipe;
4. write the manifest and print its six fields and both hashes;
5. render the figure twice and assert the bytes are identical;
6. **change the input file**, and show the manifest's input hash no longer
   matches — the figure is now stale, and the system says so rather than
   quietly re-running against the new bytes.

G3's exit test is *"correct source/cell locators, ledger, **deterministic
plot**"*. Step 6 is the part that would otherwise be untested: a plot that is
deterministic but does not notice its input changed is not an evidence
product.

## 3a. What T02 and T03 changed, and one claim they corrected

T02 and T03 are merged. Two things about them are not what the breakdown
above said, and one published claim was corrected.

**The catalogue lands with the operators, not with the contract.** The map
gives T02 `analysis/catalog.py`, and the contract is there — but the
**catalogue** cannot exist before the operators do, because it has to be
built from their own id constants for the same reason
``labcairn.evidence.catalog`` is: *one id, one spelling*. A catalogue
written out beside the implementations would be a second spelling of a
closed set, which is exactly what ADR-0009's canonical ``locator_key`` was
written to stop. LC-P1-09 has the precedent: the evidence catalogue was
created in T08, **after** the checks it registers existed.

So T02 delivers the *contract* — the id grammar, the one reference spelling,
the closed argument model — and T04 delivers the catalogue and the
operators together.

**The quantity reader moved, and C3's tests did not.** ``read_number`` and
``NumericReading`` now live in ``labcairn/sources/quantity.py`` and are
re-exported from ``evidence/checks/c3.py``, so both import paths still work
and **C3's existing tests pass unmodified**. The move was for one reason:
the ledger asks "is this a number" and the analysis layer asks the same
question of the same text, and two readers of that question would be two
answers to it.

**A published claim was corrected.** The corpus, the status board and this
document all said that for a spreadsheet "the count of missing cells is
unknown with a reason". That was imprecise, and the corpus's own data said
so: ``holes.xlsx`` records one **absent** cell, which is a number. The
precise statement is:

* the count of **addresses with no recorded value** is known in both formats;
* what is **not** knowable for a spreadsheet is **how many of those were
  blanks the author left**, because a cell that holds nothing and a cell
  that was never there are the same observation — and a range that
  overshoots the table cannot be told apart from a range full of blanks.

The corrected wording is in the corpus README, the status board, the handoff
and §5 below. The corpus's **data** was already right; only the prose was
loose.

## 3b. What T04, T05, T06 and T08 decided, and two errors in this document

T04, T05, T06 and T08 are implemented. Two of the examples in §3 were
**wrong**, and the implementations are right:

**The operator id is `labcairn.analysis.grouped_aggregate`, not
`labcairn.analysis.grouped.aggregate`.** The id grammar frozen in T02 admits
**one** segment after `labcairn.analysis.` — a dot is not in it — so the
plan's spelling was refused by `Operator.__post_init__` and by
`parse_operator_reference`. The repository's own examples already spell it
the other way (`tests/test_evidence_contracts.py`,
`tests/test_source_contracts.py`), so the plan's example was the odd one
out. The grammar is unchanged; the examples were corrected.

**A chart recipe has three parts, not four.** The prose above says data,
encoding and output, and the JSON example gave a fourth: a top-level
chart-operator reference. The chart operator is **not in the catalogue** —
it belongs to T07 — and a recipe that named an operator this build does not
implement would be refused for a reason that has nothing to do with the
recipe. The example now matches the prose.

Two decisions the implementations made that this document did not say:

- **The catalogue and the operators it registers are one thing.** The
  catalogue is built from the operator modules' own constants, so it cannot
  exist before them — the same reason `evidence/catalog.py` was created in
  T08 of LC-P1-09, after the checks it registers existed. T02 therefore
  delivers the *contract* and T04 the *catalogue*, and the file map in §3 is
  out of date in that one row.
- **A group with no quantity has no statistic, and its reason names the
  group.** The aggregate's own reason says "the selection holds no value",
  which in a table of groups is the wrong thing to blame: it is *that
  group* that holds no value, and the other groups may hold plenty.

## 4. Acceptance mapping

### 4.1 The work order's own acceptance clause

| # | Clause | Carried by | The test that proves it |
|---|---|---|---|
| 1 | numerics recalculated from source with controlled fixtures | T01, T03, T04, T05 | the operator's output is compared against **hand-written expected values** beside each fixture, not against a value the operator produced; and the values are read from the ingested representation bound to the file's hash |
| 2 | dimensions/units checked | T03, T04, T05 | a selection with two unit tokens is refused and names both; a header-declared unit that disagrees with the recipe's is refused; a cell with no token leaves the declared unit unverified |
| 3 | charts match data and captions | T07 | the renderer plots the operator's result object, so the plotted values **are** the operator's values; a caption that states a number the data does not contain is refused |
| 4 | missing/invalid data reported, not silently imputed | T03, T04, T05 | the result carries `n_used`, `n_missing` and `n_invalid`; a blank cell is never 0; the mean of an empty selection is undefined, not 0; and a count of zero is never used to mean "unknown" (A8) |
| 5 | Deterministic output on identical inputs as applicable | T07, T08 | two renders in one environment produce byte-identical files; the manifest records the environment fingerprint that makes "identical inputs" mean something |

**And three assertions that are not clauses but are the work order's
substance.** The acceptance clause names the properties; these are the ones
whose absence would leave the clause satisfied in form and empty in fact.

| Assertion | Carried by | The test that proves it |
|---|---|---|
| The manifest's input hash **is** the source's content hash — one lineage, not two | T08 | the manifest's input hash is byte-identical to `sources.content_sha256` for the same file, and the figure's `derived_from` names the manifest's own hash |
| The figure's numbers **are** the operator's numbers | T07 | the renderer receives the operator's result object; a caption stating a number the data does not contain is refused |
| A changed input makes the derivation **stale**, and the system says so | T08, T10 | the exit demonstration changes the file and shows the mismatch; the figure's receipt carries `staleness=STALE` with a reason, which `ArtifactReceipt` requires as a pair (`receipt.py:211`) |


### 4.2 The ADR-0004 conditions LC-P1-10 touches

| # | Condition | Verdict here |
|---|---|---|
| A2 | Hash drift → `fail`, derived artifacts stale | **PARTLY DISCHARGED, and this is where the part is.** The manifest carries the input hash and the figure's `derived_from` names the file; a changed file makes the hash mismatch. What is *not* discharged is the general "every derived artifact is marked stale" — that is an artifact-graph walk over the `artifacts` table, and LC-P1-10 marks **its own** outputs, not the whole graph |
| A5 | Conflicting numbers → both `conflicted` | **NOT TOUCHED.** The grouped aggregate is not a ledger record, so it cannot be `conflicted`. Two different analyses of the same cells are two different derivations with two different manifests, and the disagreement between them is visible in the manifests — not in the state machine |
| A7 | Unreadable source excluded and uncitable | **DISCHARGED for analysis.** A source whose `readability` is not `readable` is refused by the selection, so it can be neither analysed nor cited |
| A8 | Unknown is not zero | **DISCHARGED for statistics.** An undefined mean and an undefined stdev are `None` with a paired reason, never `0.0`; a *count* that the format does not permit is `Unknown` with a reason, never `0`; and an unmeasured unit is absent rather than blank. The counts and the value are shaped differently precisely because a count has a real zero and a statistic's value does not (T04) |
| A10 | Interpretation always unverified | **DISCHARGED for figures.** The recipe separates `caption` from `interpretation`, and the renderer marks the interpretation. The *report*'s marker for ledger records is still LC-P1-11's |
| A11 | Retrieved text is data | **DISCHARGED for figures.** Untrusted cell text is escaped in the SVG, asserted by a test with an instruction-shaped and a script-shaped value. The stronger half — that a model does not *read* it as instruction — is not claimed, for the same reason LC-P1-09 did not claim it |
| A12 | Fabricated source fails | **NOT TOUCHED**, and unchanged from LC-P1-09's note: a fabricated **DOI** still has no implementation, and nothing in LC-P1-10 makes it closer |

### 4.3 ADR-0004's re-evaluation trigger 3

*"LC-P1-10's reproducibility manifest is designed — the manifest and
`EvidenceRecord` must share a single hash lineage, and that alignment may
change `source_content_hash`'s definition."*

**The alignment exists and the definition does not change** (§2.3): the
manifest's input hash, the figure's `derived_from` hash, the anchor's
`bound_source_sha256` and the ledger's `source_content_hash` are the same
value, computed by one of the two functions that already implement it. The
trigger's "may change" is not exercised, and the reason is measured rather
than assumed.

## 5. What this work order cannot deliver

Named now so they are not discovered as surprises.

- **A figure's numbers are not re-checked by the cite-support checks.** C1, C2
  and C3 verify statements about located cells; an aggregate is a derivation,
  and §1.4.4 refuses it structurally. The manifest is the audit trail, and a
  report that cites a figure cites the manifest, not a verified-by-rule
  evidence record. **This is the most important limitation in this work
  order** and it is a narrowing of the product's central promise.
- **The gate cannot re-derive an aggregate.** Nothing recomputes a figure's
  numbers at gate time. The reproducibility claim is that the recipe and the
  inputs *can* reproduce them, demonstrated by the exit demonstration and by
  the byte-identity test — not that anything re-checks them unprompted.
- **"Source provenance preserved through report generation"** — LC-P1-11's.
  Unchanged from LC-P1-09's note, and still not discharged.
- **The "fabricated DOI" half of LC-P1-09's clause** — still not discharged,
  and still not LC-P1-10's. Nothing here makes it closer, and pretending
  otherwise would be the worst kind of gloss.
- **Cross-environment byte-identical figures.** §1.4.3, and the cost is
  recorded there.
- **A unit algebra.** §1.4.1. `kg` and `kilograms` are one unit spelled two
  ways and a selection containing both is refused.
- **Inferential statistics.** No p-value, no confidence interval, no
  hypothesis test, no regression. A p-value is a claim about a population, and
  C4 says this system cannot check such a claim — so it must not produce one.
- **A general-purpose model-authored code execution.** The recipe is
  declarative and the catalogue is a constant; a figure is reproducible by
  re-running a registered operator, not by running code a person wrote.
- **The two-column and rotated-text gaps** — LC-P1-08's, unchanged, and
  nothing here depends on them.
- **The table's extent is not always observable.** Measured against the two
  adapters: a **CSV** emits a `source_texts` row for an empty cell, so the
  empty cells in a selection can be counted; an **XLSX** emits no row for one,
  so the same table's extent is not recoverable from the ledger and the missing
  blanks the author left is not recoverable from the ledger — a cell that holds
  nothing and a cell that was never there are the same observation. The count of
  *addresses with no recorded value* is known in both formats; what is not knowable
  for a spreadsheet is how many of them were blanks the author left, and a range that
  overshoots the table cannot be told apart from a range full of blanks. The analysis sees
  the cells that carry text, and says so. This is a narrowing of *"dimensions
  checked"*: for XLSX, the dimension is the extent of the non-empty region,
  not of the sheet.
- **A corpus that establishes anything about real data.** The fixtures are
  small, synthetic and chosen for closed-form answers. They establish that the
  operators compute what they claim on data whose answers are known. They
  establish **nothing** about whether a real research dataset is analysable.
- **A regression suite for matplotlib upgrades.** The figure hashes are
  environment-scoped; a matplotlib upgrade changes them. The environment
  fingerprint is in the manifest, so the change is *visible*, but no test
  asserts a figure is unchanged across matplotlib versions, and none should.

## 6. Dependency order

```text
  T00 (dependency) ──────────────────────────────► T07 (renderer)
        │
        ▼
  T01 (corpus) ──┐
                  ├──► T03 (selection) ──► T04 (descriptive) ──► T05 (grouped)
  T02 (catalogue)─┘         │                                            │
                             │                                            │
                             ├──► T06 (recipe) ──────────────────────────┤
                             │                                            │
                             │                    T07 (renderer) ◄────────┤
                             │                          │                │
                             └──────────► T08 (manifest) ◄────────────────┘
                                              │
                                              ▼
                                        T09 (run path)
                                              │
                                              ▼
                                        T10 (demonstration)
```

T00, T01 and T02 are independent and can run in parallel, and T00 must land
before T07, which is the only subtask that imports matplotlib. T03 follows T02
(the catalogue defines the selection's shape) and T01 (the corpus's columns
are the ones the selection is designed against). T04 follows T03; T05 follows
T04; T06 follows T03 and T02; T07 follows T06 and T05; T08 follows T02 and
T06; T09 follows everything; T10 follows T09.

**T03 edits LC-P1-09's `c3.py`** and is therefore sequenced after the merge of
`a7a2f48` and not in parallel with anything that touches the evidence package.
