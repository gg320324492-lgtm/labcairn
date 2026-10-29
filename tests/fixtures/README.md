# The synthetic DOCX corpus

**What this is.** Twenty-eight `.docx` files, each generated, each carrying
tracked changes and comments, and each with an **exact expected answer**.
They are the gold for LC-P2-07 (DOCX revision fidelity).

**Why they are synthetic.** A real advisor's manuscript tells us what
happens; it does not tell us what *should* happen, and a parser that agrees
with a real document is not thereby correct. Every fixture here can state
its expected result exactly, because the corpus is written rather than
found.

**Why they are generated rather than checked in.** The corpus is built by
`tests/docx_fixtures.py` at test time. Two reasons:

- A checked-in binary is a binary the repository has to carry, and a `.docx`
  is a ZIP whose entries carry timestamps — so it is not byte-reproducible
  unless the writer pins them, and a fixture whose bytes move makes every
  hash-based check meaningless. The writer pins every entry to the ZIP
  epoch.
- The gold is **derived from the same words that write the XML**, so it
  cannot drift away from the file the way a transcribed expectation can.

**Where the pieces are.**

| File | What it holds |
|---|---|
| `tests/docx_fixtures.py` | the writer: `Fixture`, `Revision`, `Comment`, and the gold |
| `tests/docx_corpus.py` | the twenty-eight cases, and the corpus's known gaps |
| `tests/test_docx_fixture_corpus.py` | 97 tests that check the corpus itself |
| `tests/evaluation_docx_fidelity.py` | the measurement the corpus is the gold for |

**Why the corpus is tested before anything trusts it.** A gold that is wrong
does not fail loudly — it fails by making a correct parser look broken, or a
broken parser look correct. So `test_docx_fixture_corpus.py` re-reads the
written ZIP with `zipfile` and `xml.etree` — deliberately **not** with the
parser this project is going to write, and not with `python-docx`. A gold
verified by the same code that will be measured against it is not a gold.

**Two bugs this corpus found in itself**, recorded because they are what a
synthetic corpus is for:

1. The first version emitted the revision elements at the **front** of the
   paragraph, so pandoc's `--track-changes=accept` and `--track-changes=reject`
   gave the same text. A revision's position inside the paragraph is
   load-bearing.
2. The first version carried **hand-written character offsets**, which
   pointed at a different part of the sentence than the revision's own text.
   The offsets are now **derived from the text** — a deletion names the
   baseline words it removes, an insertion names the words it follows — and
   the writer **refuses** to build a fixture whose anchor does not occur in
   its baseline.

**The second is the more important one: a hand-written expectation drifts
away from the thing it describes.** A derived one cannot.

**What the corpus does not reach.** Ten real-world cases are listed in
`KNOWN_GAPS` in `tests/docx_corpus.py` — run fragmentation inside a
revision, Word renumbering revision ids on save, comments in headers and
footnotes, a document whose revisions have been accepted, a corrupt ZIP,
and the rest. Those need a real Word file, and the pilot corpus is where
they are obtained. **The corpus's limits are written down rather than
discovered later.**

**The measurement.** `tests/evaluation_docx_fidelity.py` runs four arms over
this corpus and scores them. The result is recorded at
[`docs/acceptance/LC-P2-07-fidelity-baseline.md`](../../docs/acceptance/LC-P2-07-fidelity-baseline.md).

```bash
python -m tests.evaluation_docx_fidelity --corpus-dir=<dir>
```

**The arms are not project dependencies.** `docx2python` is installed with
`uv run --with`, because a measurement tool that adds its subjects to the
product's dependency list changes the product it measures.
