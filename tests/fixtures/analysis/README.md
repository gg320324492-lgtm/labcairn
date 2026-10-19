# LC-P1-10's corpus

The tabular material LC-P1-10's operators will be tested against, and the
answers they are supposed to produce.

**Nothing here is imported by any module under `src/`.** These are test
inputs, and the operators that read them are LC-P1-10 T04 and T05, which do
not exist yet. What exists now is the corpus and the check that the corpus
is honest: `tests/test_analysis_fixtures.py`.

## The fixtures

| Fixture | What it is for |
|---|---|
| `basic.csv` | The reference case. Two groups over the values 1..10, every cell a clean quantity, and every statistic closed-form: mean 5.5, median 5.5, population stdev `sqrt(8.25)`, sample stdev `sqrt(82.5/9)`. |
| `groups.csv` | Three groups of **unequal** size (4, 4 and 8) over the values 1..16. The sizes are unequal on purpose: a group boundary that is off by one changes a *mean* and not only a count, and a count is easy to get right by accident. |
| `units.csv` | Unit tokens. Four rows carry `kg`, one carries `g`, one carries none. A selection over the whole file is **refused** for holding two unit tokens, while every group on its own is fine — the refusal is a property of the selection, not of the file. |
| `missing.csv` | The three ways a cell can fail to be a number: present and empty, present and not a number, and absent altogether (the trailing blank row, which has no fields at all). Nothing here is a zero and nothing here is imputed. |
| `holes.csv` | `basic.csv` with the value cell of physical row 4 emptied. Read it beside `holes.xlsx`. |
| `holes.xlsx` | `holes.csv` in the other format, cell for cell, with the same characters. The emptied cell is **absent** rather than empty. |
| `numeric.xlsx` | `basic.csv` in the other format, cell for cell, with the same characters. |
| `single.csv` | Exactly one value. The population standard deviation of one value is `0`, and the sample standard deviation is **undefined**. The difference between those two is the point, and it is ADR-0004 A8: an unknown quantity is not a zero. |
| `typed.csv` | A header that declares a unit: `mass (kg)`. The cells carry no token of their own, so the unit comes from the column name — and the space in that column name is also why the adapter announces that a header with a space in it might be a title row. |
| `declared.csv` | A header that declares a unit, three ways. `mass (kg)` declares `kg` and the cells carry `kg`; `length (cm)` declares `cm` and the cells carry `m`, which is a **conflict** and is refused with both tokens named; `total (see table 2)` declares **nothing**, because prose in parentheses is not a unit, so there is nothing to compare the cells with. |
| `empty.csv` | A header and no rows. Every statistic over an empty selection is undefined rather than `0`, and the file produces no cells at all. |

## The spreadsheets are derived, not committed

`numeric.xlsx` and `holes.xlsx` are **not in this directory**. They are
produced by `analysis_fixtures.build_spreadsheet_fixtures()`, which turns a
CSV fixture into the same table in the other format, and the test asserts
what the result contains.

A `.xlsx` is a binary blob: a reviewer cannot read it, and a reviewer who
cannot read it cannot tell whether it says what the corpus claims. The
generator is the reviewable artefact and the assertion is what makes the
result a fixture rather than a convenience.

**The cells are written as the CSV's own text, not re-typed as numbers.**
That is what makes the two paths comparable. If the spreadsheet held real
numbers, `1` would arrive as the float `1.0` and render as `"1.0"` while the
CSV's cell reads `"1"`, and every difference between the two paths would be
the writer's rather than the adapter's.

## The expected values

Each fixture has a companion `<fixture>.expected.json` — the **whole** file
name, because `holes.csv` and `holes.xlsx` are two fixtures of the same
table and a stem-named file would have one of them overwrite the other.

**No script in this repository regenerates those files.** That is the
property worth keeping: an expectation that lives inside the test can be
corrupted by the same bug that breaks the code under test, and an expectation
that lives in a file beside the data cannot. A change to a fixture fails a
test rather than silently rewriting a golden file.

Each file states:

- the **columns**, and the units the **headers declare**;
- whether the **header row** is a set of addressable cells;
- for every **selection** — a set of rows and columns — which cells are
  `absent`, which are `empty`, which are `not_a_quantity`, the **statistics**
  of the cells that do carry a quantity, and the **unit** they carry;
- the **grouped** aggregates, one per group key, with the rows that made it.

`statistics` is `null` where the selection has no quantity to measure, and
`stdev_sample` is `null` for a single value. Neither is `0`: an unknown
quantity is not a zero, and that is ADR-0004 A8 in the corpus rather than
only in prose.

The numbers in those files were computed with Python's `statistics` module —
an implementation that is **not** LabCairn's — and checked by hand against
the closed forms. The test recomputes them the same way, so the expectation
does not share a bug with the code the operators will be written against.

## The addressing contract

The corpus is format-neutral, so the two adapters have to be brought to a
common address:

- A **cell** is addressed by its **physical row** and its **column's header
  text**.
- The **data rows** of both formats are the physical rows from 2 upwards, so
  "the value column, every data row" means the same thing in each.
- A cell that **does not exist** is not the same as a cell that exists and is
  empty, and the two are counted apart.

## Two differences between the formats, both real

Both are recorded in the expected values rather than smoothed over.

1. **An empty cell.** A CSV keeps it — a row with an empty text, countable
   and addressable. A spreadsheet does not: its adapter does not extract an
   empty cell, so the cell is simply absent. A spreadsheet's rectangular
   extent is therefore **not recoverable from the ledger**, and the count of
   blanks the author left is not recoverable from the ledger. What *is* known in both
   formats is the count of **addresses with no recorded value** — that is what `absent`
   records. What is not knowable for a spreadsheet is **how many of those were blanks
   the author left**, and a range that overshoots the table cannot be told apart from
   a range full of blanks. So `empty` means "cells the ledger holds with empty text",
   which for a spreadsheet is always zero and does **not** mean the author left no
   blanks.
2. **The header row.** A spreadsheet's A1 and B1 are cells like any other and
   are addressable. A CSV's header names the columns and is not itself a set
   of cells. A selection that took "the whole column" would see two extra
   cells in one format and none in the other.

## Adding a fixture

1. Write the CSV here, in the canonical form — `analysis_fixtures.write_table_csv`
   produces it, and the test says so if the file is not in it.
2. Derive the expected values **by hand**, or with a script you do not
   commit. The file has to exist before the test can pass, and nothing in
   this repository may regenerate it.
3. Add the fixture's name to `analysis_fixtures.FIXTURE_NAMES`.

## A gap this corpus found

`empty.csv` — a header and no rows — produces **no disclosure at all**. The
CSV adapter reports `csv_empty` for a file with no records whatsoever, but a
file with a header and nothing under it is neither empty nor disclosed: the
corpus's own fixture for it produced zero cells and no problem record. That
is LC-P1-08's subject rather than this work order's, and it is recorded here
rather than fixed quietly. The corpus does not depend on it — the statistics
over an empty selection are undefined in either case.
