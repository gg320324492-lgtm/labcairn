# LC-P4 pilot — what the Chinese in the tree is, and what holds it

**Date:** 2026-11-27
**Base commit:** `8dacfea180b4e882b7ac87d2c4e2739b609b0528`
**Record read at:** the commit that adds this file; the sentence naming it
is an amendment in the same branch.
**Measured by:** the classification window, on the development machine.
**Status:** the classification is measured and pinned; the runs that did not
belong are redacted or replaced; **the published history still carries
them**, and that is the owner's decision to make.

## 1. What was open

Two measurements watched the tree's Chinese and neither judged it. The
longest Han run per file (`CJK_RUN_CEILINGS`) and the whole Han load per
file (`CJK_HAN_TOTALS`) are both *quantity* pins: a file whose Chinese is
the project's own ADRs reads the same as a file whose Chinese is a sentence
from the manuscript, and a run replaced by a different run of equal length
moves neither number. The question had been open across three batches:
`docs/handoff/CURRENT.md` listed it under what the batch did not answer,
and the batch-17 review recorded the same gap in its R4.

This record answers it: every Han run in the tree was read, classified, and
pinned by digest; runs that did not belong were removed; the two quantity
pins were re-measured and carried.

## 2. What was measured

| | before | after |
|---|---|---|
| files carrying Chinese | 56 | 53 |
| Han characters in the tree | 13,139 | 13,074 |
| Han runs in the tree | 1,971 | 1,956 |
| longest-run pin entries | 56 | 53 |
| totals pin entries | 56 | 53 |

The difference is accounted for: three files carry no Chinese now and
dropped out of both tables (the trial record, the exit decision, and the
LC-P2-11 task breakdown); two files kept a shorter run and their totals
were re-measured, not adjusted (ADR-0014 121 -> 113, readerB 11 -> 5). Every
remaining value in both tables was measured again at this tree, not carried
forward.

## 3. The classes

A run's class is a judgment about its source. Five classes are allowed in
the tree, three are not.

| class | allowed | what it is |
|---|---|---|
| `project-voice` | yes | the project's own documents, written in Chinese by design |
| `design-quotation` | yes | the project's own execution design, quoted verbatim |
| `product-vocabulary` | yes | Chinese strings the product or its tests must recognise |
| `measurement` | yes | Han code points in the machinery that measures Chinese |
| `machine-output` | yes | a machine's own string, quoted as evidence |
| `corpus-quotation` | **no** | words of the manuscript corpus, quoted |
| `corpus-label` | **no** | a label carrying the manuscript's title-of-record |
| `person-name` | **no** | a label carrying a person's name |

After this batch the tree carries 53 files and 1,956 runs: 26 files
`design-quotation` (201 runs), 7 `project-voice` (1,557), 16
`product-vocabulary` (187), 2 `measurement` (8), 2 `machine-output` (3).
**No run is in a class the tree is not allowed to carry.**

The full per-run record is `tests/cjk_run_classes.json`: one entry per file
with a one-line reason and, for every run, its `(sha256 prefix, length,
class)`. The registry carries no Han character and no run's text. A reader
re-derives any entry by extracting the file's runs with
`python scripts/cjk_ceilings.py --classify --json` and reading the reason
beside it.

## 4. What was read, class by class

**`project-voice` — 7 files, stayed.** The Chinese README and the Chinese
section of the English README (bilingual by design, 1,035 of the tree's
runs), the owner's Phase 4 execution plan written in Chinese (4,193
characters), the owner's ruling on the reviewer's designation, the
reviewing session's own title, the README's own headings quoted by the
records that review them, and the README heading anchor its consistency
test holds.

**`design-quotation` — 26 files, stayed.** The execution design's rules are
quoted verbatim throughout the ADRs, the Phase 2 plans, the upstream study
records, the acceptance records, the modules that implement the rules, and
their witnesses. This is the tree's own specification, not the manuscript:
it is the voice the ADRs are written to state, and the task that opened
this question lists the ADRs among the tree's voice. **The four reader
requirements in `LC-P2-07-fidelity-baseline.md` section 4.6 are part of this
same quotation and were read before they were classified.** They are the
design's requirements for the DOCX reader (read the XML directly; a
plain-text conversion is a comparison view; report fidelity against the
original; write `UNKNOWN` for missing metadata), each already carries its
English paraphrase beside it, and they are the standard that record's
measurement is against. They are the same source as the ADR quotations
that the tree keeps, so they stay, and their class says so. Treating them
as corpus material while keeping the ADR quotations that come from the same
design would be a distinction the tree cannot state; the review that opened
the question named them as the mentor's rule statements, and the
classification records that the mentor's design is the project's own
specification. A reader can disagree with the call, and the registry shows
exactly which runs it covers.

**`product-vocabulary` — 16 files, stayed.** The overclaim detector's
Chinese modals and the compounds that exclude them
(`LC-P2-25-guard-of-the-guards.md`, `LC-P1-01-evidence.md`,
`test_readme_accuracy.py`); the locator words the evidence model parses
(ADR-0004); the placeholder markers the quality skill recognises; the
version-name words the version parser parses; the generic file-name
examples those rules are about; and the non-ASCII fixtures the encoding,
path, caption and JSON tests feed the product. The chemistry term inside a
corpus label is the corpus's subject matter, not the mentor's words, and
the class records where the line was drawn: the subject stays as the
English paraphrase already in `LC-P2-11-revision-distillation.md`, and the
corpus's own label is redacted (below).

**`measurement` — 2 files, stayed.** The Han range endpoints in
`scripts/cjk_ceilings.py` and `tests/test_pilot_decisions.py` are code
points, not language. The measuring machinery is allowed to know where Han
characters are.

**`machine-output` — 2 files, stayed.** The Windows edition name
(`Microsoft Windows 11 ...`) and the system's access-denied text, quoted as
evidence of the clean-Windows drill and the fixture trials. They are the
machine's strings, not the corpus's.

**`corpus-quotation` — none remain.** The previous batch removed the
mentor's comments, the distilled rule statement and the template title from
three records (`LC-P2-11-material-words-out-of-the-records.md`). This batch
read every remaining run and found no new quotation of the manuscript's
prose. The section 4.6 requirements are design, not manuscript; the call is
recorded above.

**`corpus-label` — 3 files, redacted.** Three records carried the trial
sample's file names: `LC-P3-08-trial-record-2026-11-22.md` (three table
rows and the stripped copy), `LC-P3-08-exit-decision-2026-11-22.md` (the
fingerprint block), and `LC-P3-08-review-2026-11-22-readerB.md` (the
annotated file's label in two rows). **A label that carries material is
material too**: the names carried the manuscript's title-of-record. The
subject matter itself is already in the tree as an English paraphrase, so
redacting the labels hides no finding; each row stays identified by its
byte count and sha256, the workspaces named in the records still hold the
original names, and each record says in place that it was redacted and why.
The trial record, the exit decision and every record that printed the
labels were carried with the change.

**`person-name` — 3 files, redacted or replaced.**

- `ADR-0014-paper-revision-provenance.md`: the D2 example named an author
  by a Chinese surname-and-title label, dated 2026-03-02, with a Chinese
  inserted phrase. The label is a person label whatever its provenance, and
  its provenance cannot be established from the tree; it is now `a w:ins by
  the advisor's account`, and the inserted text is its English gloss. The
  example's force is unchanged: an observed revision is one read from the
  XML.
- `docs/plans/LC-P2-11-task-breakdown.md`: the counterexample read "Teacher
  Wang always corrects it this way". It is now "the advisor always corrects
  it this way" -- the same point, no surname. The file carries no Chinese
  now.
- `tests/docx_corpus.py`: the synthetic corpus's non-ASCII author was a
  Chinese surname-and-title label. The corpus is stated to be synthetic, so
  this was not a real person's name; it was replaced with a non-name author
  label all the same, because the name shape is what a person label is, and
  because it lets the witness refuse that shape mechanically. The fixture's
  property -- a non-ASCII author name and character-vs-byte offsets -- is
  unchanged, and its Han load is the same length.

No other surname-and-title run exists in the tree. The witness refuses the
shape independently of the registry, so a name re-pinned as `project-voice`
still reddens.

## 5. The witness, and how a run is classified

`tests/test_chinese_run_classes.py` holds the registry against the tree:

1. **Every run is registered.** The tool recomputes each file's runs, in
   order, as `(digest, length)`, and the registry must match exactly --
   path set, order, digests, lengths. An added run is a run nobody
   classified; a removed run is a value carried forward; a changed digest
   is a run whose text moved. The failure names the file, the digest and
   the length.
2. **Every class is allowed.** The allowed set is written in the test
   itself, not read from the registry, so relaxing one file cannot hide
   the rule in the other.
3. **No run is a surname plus a title**, checked by shape from code points,
   independently of the registry.
4. **The registry is derivable**: `--classify --json` reproduces the
   pinned file exactly.
5. **The registry and this witness carry no Han character**, so watching
   the tree's Chinese does not add to it.

**How a new run gets a class.** Run `python scripts/cjk_ceilings.py
--classify --json`; a run whose digest the registry does not hold is
emitted as `unclassified`, and the witness refuses it. The person adding
the run either removes it or records its class in the registry in the same
commit. The diff is the review point, exactly as it is for a new long run
in the ceiling table. The class is a judgment; the mechanism makes the
judgment visible and keeps the tree's count of unjudged runs at zero.

**The guards, and the mutations measured.** The class witness has its own
arms: a short run appended below a longer one, a same-length replacement, a
forbidden class, and a name shape. Each arm was also driven through the
real tree:

| mutation | class witness | longest-run pin | totals pin |
|---|---|---|---|
| a 2-character run replaced by a different 2-character run | **red** (digest changed) | green | green |
| one registry class set to `corpus-quotation` | **red** (allowedness) | green | green |
| a surname-and-title run appended and re-pinned as `project-voice` | **red** (name shape) | green | green |
| a new file carrying Han | **red** (unregistered file) | **red** | **red** |

The first two rows are the mutations only this witness can catch. The
third is the case a registry alone would bless; the shape arm catches it.
All mutations were reverted and the registry re-derived to equality before
the work was committed.

## 6. The two pins, carried

Both tables were re-measured from `--json` and `--totals --json`; no value
was edited by hand. Three entries left each table because their files carry
no Chinese now, and the two files that kept a shorter run were re-pinned at
their measured values. Two cross-checks now tie the three measurements
together: every file in `CJK_RUN_CEILINGS` must be in the registry with a
longest run equal to its pinned ceiling, and every file in `CJK_HAN_TOTALS`
must be in the registry with run lengths summing to its pinned total. A
re-pin of one table alone reddens the other.

## 7. What the promise now means

`docs/handoff/CURRENT.md` states *"Nothing of the paper is in the
repository."* After this batch that sentence has a checkable form:

- Every Han run in the tree is registered by digest, with a class and a
  reason a reader can re-derive.
- No run is in `corpus-quotation`, `corpus-label` or `person-name`; the
  witness refuses any class outside the five the project allows.
- No run is a surname-and-title label, whatever its class.
- The remaining Chinese is the project's own voice, its own design quoted,
  the vocabulary the product must handle, and strings a machine printed.
- The classification is the tree at the commit that adds this record; it
  is re-derived and re-pinned when the tree moves, and it reddens in both
  directions.

## 8. What this record does not do

- **The published history still carries the removed labels and names.**
  Measured at this tree with local refs: the trial record (commit
  `268d679`), the exit decision (`c19115f`), the readerB review
  (`7d42b9d`), ADR-0014 and the synthetic corpus (`b1d73a3`), and the
  LC-P2-11 task breakdown (`70aa66c`) are all ancestors of `origin/main`.
  The redactions clean the tree tip only. Whether the published history is
  rewritten is the owner's decision, and the cost is the same one
  `LC-P4-PILOT-history-exposure-and-name-watcher-2026-11-27.md` measured
  for the earlier leak: a force-push over published refs.
- **The classification cannot read provenance off the characters.** It
  holds a registered judgment. A person who re-pins a corpus quotation as
  `project-voice` gets it into the registry; what stops that is the review
  of the diff, not the witness. The name-shape arm narrows the gap only
  for the one shape it can name.
- **The pilot workspace and `E:/trial-material/` were not read.** The
  class of a run was judged from the tree and the records, not by opening
  the corpus.

## 9. Files changed

Redacted or replaced: `docs/adr/ADR-0014-paper-revision-provenance.md`,
`docs/plans/LC-P2-11-task-breakdown.md`,
`docs/acceptance/LC-P3-08-trial-record-2026-11-22.md`,
`docs/acceptance/LC-P3-08-exit-decision-2026-11-22.md`,
`docs/acceptance/LC-P3-08-review-2026-11-22-readerB.md`,
`tests/docx_corpus.py`.

Extended: `scripts/cjk_ceilings.py` (`--classify`, `--registry`, run
digests; the two existing measurements unchanged),
`tests/test_no_reference_leakage.py` (the ceiling table carried, the
cross-check added), `tests/test_chinese_totals_pin.py` (the totals table
carried, the cross-check added).

Added: `tests/test_chinese_run_classes.py` (the witness),
`tests/cjk_run_classes.json` (the registry), this record. The new test file
is not yet in `tests/evaluation/manifest.py` or in `.github/ci-shards.json`;
that registration belongs to the integrating session. Corrected in place:
`docs/acceptance/batch-17-review-2026-11-27.md` R4, which named the trial
record among the records carrying corpus labels.