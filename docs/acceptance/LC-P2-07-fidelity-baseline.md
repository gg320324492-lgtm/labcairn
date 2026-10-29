# LC-P2-07 — DOCX revision fidelity: the baseline measurement

**Date:** 2026-10-29 · **Base commit:** `66dde87` · **Measured by:** the
executor, on the development machine

**What this record is.** The fidelity measurement for LC-P2-07, run against
the synthetic corpus in `tests/docx_corpus.py`. It answers one
question: **when a reader opens a Word file with tracked changes, how much
of the revision history does it recover?**

**What it is not.** It is not a verdict on the arms, and it is not a
benchmark of real Word documents. The corpus is synthetic, the arms are
particular versions, and every number below is a number *about this corpus,
on this machine*. It is also **not yet a result for LabCairn** — the
OOXML-native arm is the work LC-P2-07 has still to do, and it is present in
the table as a row of zeros so that the shape of the comparison is fixed
before the reader is written.

---

## 1. How to reproduce it

```bash
# the corpus and its gold are written by the fixture module
python -m tests.evaluation_docx_fidelity --corpus-dir=<dir>

# with the comparison arms installed (they are NOT project dependencies)
uv run --no-project --with docx2python --with python-docx \
  python -m tests.evaluation_docx_fidelity --corpus-dir=<dir> --json=report.json
```

**The arms are installed with `uv run --with`, not added to
`pyproject.toml`.** A measurement tool that adds its subjects to the
product's dependency list would change the product it measures. The
isolation is the point, and it is the same rule the design applies to the
reference repositories.

**The corpus test** — `tests/test_docx_fixture_corpus.py` — checks the
corpus itself, before any of this runs. 97 cases, all green.

## 2. The corpus

| | |
|---|---|
| Fixtures | **28** |
| Revisions | 30 (8 deletions, 12 insertions, 6 moves) |
| Comments | 14 (4 of them deliberately un-anchorable) |
| Paragraphs | 1–12 per fixture |

Each fixture isolates one behaviour and states its purpose and its
expectations. The negative list is the design's §7 list: insertion,
deletion, comment spanning a revision, several authors, an orphan comment
marker, a move pair, nesting, a revision with no author, a revision with no
date, a comment with no anchor, non-ASCII text, markup characters, and an
empty revision.

**The corpus found two of its own bugs before it found anything else**, and
both are worth recording because they are what a synthetic corpus is for:

1. The first version emitted the revision elements at the **front** of the
   paragraph, so pandoc's `--track-changes=accept` and `--track-changes=reject`
   gave the same text. A revision's position inside the paragraph is
   load-bearing, and the corpus's test caught the fixture being wrong
   rather than the reader.
2. The first version carried **hand-written character offsets**, which
   pointed at a different part of the sentence than the revision's own text.
   The offsets are now **derived from the text** — a deletion names the
   baseline words it removes, an insertion names the words it follows — and
   the writer refuses to build a fixture whose anchor does not occur in its
   baseline.

The second is the more important finding. **A hand-written expectation
drifts away from the thing it describes.** The derived one cannot.

## 3. The measurement

| Arm | What it is |
|---|---|
| `ooxml-native` | LabCairn's own reader — **not written yet** |
| `pandoc` | text extraction, `--track-changes=accept\|reject\|all` |
| `python-docx` | the library this project already depends on for *writing* DOCX |
| `docx2python` | an extraction library that does handle comments |

**Six columns, and each answers a different question.**

| Column | The question |
|---|---|
| revision recall | did the arm report the changes as **events**? |
| comment recall | did the arm report the comments? |
| deletion recovery | did the arm recover the **deleted text**? |
| accept view correct | is the text-as-if-accepted exactly right? |
| reject view correct | is the text-as-if-rejected exactly right? |
| attributes | can the arm say **who** made a change? |

**Precision and recall are separate, and false negatives are counted
separately from false positives.** A metric that counted only the comments
an arm got right would let an arm that returns *nothing* score perfectly.
An arm that could not read a file is counted as missing everything, not
excluded from the average — excluding it would let an arm that fails on
every fixture report an average over the fixtures it happened to read.

## 4. The result

```
corpus: 28 fixtures, 30 revisions, 14 comments, 8 deletions

arm            rev found rev miss  rev rec cmt found cmt miss  cmt rec   del recov  accept ok  reject ok  attr
--------------------------------------------------------------------------------------------------------------
ooxml-native           0       30    0.000         0       14    0.000     0/8        0/28       0/28       no
pandoc                 0       30    0.000         0       14    0.000     0/8       26/28      28/28       no
python-docx            0       30    0.000         0       14    0.000     0/8       13/28      18/28       no
docx2python            0       30    0.000         6        8    0.429     0/8       23/28       9/28       no
```

### 4.1 No arm reports a revision as an event

**All three comparison arms report zero revisions out of thirty.** Not one
of them says "this text was deleted on this date by this person".

That is the measurement's central finding, and it is not a defect in the
arms — it is what a *text* is. A reader that produces text has, by
construction, no place to put "who did this", and the phase needs that
place to exist. **This is why the OOXML-native arm has to be a new reader
rather than a configuration of an existing one.**

### 4.2 No arm recovers a deletion

**Zero of eight deletions were recovered by any arm.** The deleted text
lives in `w:delText`, not `w:t`, and every text-producing reader reads
`w:t`.

The upstream study predicted this for Docling from its source
(`msword_backend.py:2053`); the measurement confirms it for all three arms
on this corpus. For a project whose thesis is *"the deletion is the
signal"*, this is the number that matters most, and it is zero.

### 4.3 `pandoc` — the best text arm, and it still loses an edit

pandoc's rejected view is **exactly right on all 28 fixtures**. Its
accepted view is right on **26**.

**The two it gets wrong are `06-insertion-without-author` and
`08-insertion-without-author-or-date`, and the reason is specific: pandoc
silently drops a tracked insertion that carries no `w:author`.** The two
fixtures' XML differ in that attribute and in nothing else, and the
inserted text is present in one accepted view and absent from the other.

This was found by measurement, not by reading pandoc's source, and it is
the design's §7 case "a document with no author" — where the correct
answer is **UNKNOWN, not gone**. A reader that discards the change has
turned "we do not know who did this" into "nobody did this", and the
difference is invisible in the output.

### 4.4 `python-docx` — the project's own dependency, and the weakest text arm

`python-docx` is already a dependency of this project (LC-P1-11's report
export). It is also the **worst** of the three text arms: its accepted view
is right on 13 of 28 and its rejected view on 18.

**The accepted view is worse than the rejected one, and that asymmetry is
the finding.** `python-docx`'s `Run.text` reads `w:t` only, so a deleted
run reads as empty — the deletion leaves no trace in the text it produces.
The rejected view is closer because the baseline text is still there.

### 4.5 `docx2python` — it handles comments, and it loses half of them

**Comment recall 0.429: six of fourteen comments recovered, eight lost.**

The six fixtures where comments were lost are exactly the ones the design
names:

| Fixture | Lost | Why |
|---|---|---|
| `13-orphan-comment-end-only` | 1 of 1 | the range ends without starting |
| `14-comment-without-anchor` | 1 of 1 | no range markers at all |
| `21-multiple-comments-and-revisions` | **2 of 2** | one unpaired marker took the whole set |
| `22-long-document` | 1 of 1 | the comment is un-anchored |
| `23-everything-at-once` | **2 of 2** | one unpaired marker took the whole set |
| `28-comment-on-empty-paragraph` | 1 of 1 | the range covers empty text |

**The `21` and `23` rows are the important ones: a single unpaired marker
takes every comment in the document with it.** The mechanism is in
`docx_output.py:418` — the library compares the number of comment ranges
with the number of comment elements and, when they differ, warns and
returns an empty list.

**The correction to the upstream study.** The study of docx2python, read
from source, recorded this as "the whole comment set disappears on any
mismatch". The measurement is more precise, and the precise version
matters for the parser's requirements:

| Case | Counts | Result |
|---|---|---|
| `12-orphan-comment-start-only` | 1 range, 1 element — the counts **match** | the comment **is** extracted, with an empty anchor |
| `13-orphan-comment-end-only` | 1 range, 1 element — the counts **match** | the comment **is** extracted, with an empty anchor |
| `14-comment-without-anchor` | 0 ranges, 1 element — the counts **differ** | the comment is **lost entirely** |

So the trigger is the **count mismatch**, not the malformed marker itself.
A comment whose marker is unpaired but whose count is balanced survives; a
comment with no marker at all does not. **Either way the anchor is lost**,
and the loss is silent in the output — the caller receives a comment with
an empty reference and no indication that the anchor was there.

**The second measurement of docx2python: its anchor is the whole
paragraph, not the comment's range.** On `11-two-comments-one-paragraph`,
two comments on different parts of one paragraph both report the same
anchor text — the paragraph's. A mentor's "this phrase" becomes "this
paragraph", which is a materially weaker claim.

### 4.6 What the measurement says about the design

| The design asked | The measurement says |
|---|---|
| *"OOXML 原始 ZIP/XML 只读解析优先"* — read the XML directly | **Supported.** No text arm reports a revision as an event; none recovers a deletion. |
| *"普通文本转换只能作为对照视图"* — plain-text conversion is a comparison view only | **Supported and sharpened.** pandoc's rejected view is exact on 28/28, which makes it a good *comparison* and a poor *source*. |
| *"Docling/docx2python/Pandoc 与原始 XML 的保真率做对照报告"* | **Done here**, for three of the four; Docling is not installed and is not needed to make the finding, which is structural rather than specific to it. |
| *"对缺失元数据输出 UNKNOWN，不伪造作者和时间"* | **Supported.** pandoc discards such an edit entirely, which is the failure this rule exists to prevent. |

## 5. The numbers this does **not** establish

- **Nothing about real Word documents.** The corpus is synthetic. A real
  Word file fragments a revised sentence across several runs, renumbers
  revision ids on save, and puts comments in headers and footnotes. The
  corpus's `KNOWN_GAPS` lists ten such cases; the pilot corpus is where
  they are obtained.
- **Nothing about Docling.** It was not installed. Its source reading
  (`docs/research/upstream-study/docling.md`) predicts the deletion loss,
  and the prediction is confirmed for the other three arms — but Docling's
  own number is not measured here, and this record does not claim it.
- **Nothing about the OOXML-native arm's quality.** It is a row of zeros
  because it does not exist. When it is written, this measurement becomes
  its acceptance test, and the acceptance is: **the revision recall and the
  deletion recovery must be 1.0 on this corpus**, and the comment recall
  must be 1.0 including the four un-anchorable comments, which must be
  reported as `UNKNOWN` with a reason rather than dropped.
- **Nothing about how a reader performs on the pilot corpus.** That is a
  second measurement, and it is the one that decides whether the parser is
  good enough.

## 6. What this record asks of LC-P2-07

1. **The OOXML-native reader must recover every revision and every deletion
   on this corpus**, with the author and date reported as `UNKNOWN` where
   the file omits them. Zero of the comparison arms manage this.
2. **The reader must report every comment, including the four whose anchor
   is unresolvable**, with `anchor_status = UNKNOWN` and a reason naming
   the unmatched marker. `docx2python` loses eight of fourteen; the
   requirement is fourteen of fourteen with four of them marked unknown.
3. **The reader's anchor must be the comment's range, not the paragraph's.**
   Measured against `docx2python`'s paragraph-granular anchor.
4. **The reader must not modify the original bytes.** The corpus's
   byte-reproducibility test is the first half; the reader's own test is
   the second.
5. **A parser that returns nothing must not score well.** The false-
   negative floor in §3 is what keeps that true, and it must survive into
   the acceptance test.

## 7. The commits and the environment

| | |
|---|---|
| Base commit | `66dde87` |
| Corpus | `tests/docx_corpus.py`, `tests/docx_fixtures.py` |
| Corpus test | `tests/test_docx_fixture_corpus.py` (97 cases) |
| Measurement | `tests/evaluation_docx_fidelity.py` |
| pandoc | 3.10 (installed on the machine; GPL-2.0, used as a comparison only) |
| python-docx | the project's own declared dependency, 1.2.0 |
| docx2python | 66b1ae3e24ffa7040ed5244490ce2872ac2e86bb, run via `uv run --with` |
| Python | 3.12.13 (the project's virtualenv) |

**The repository is clean at the base commit apart from the files this
work adds.** The measurement writes its corpus outside the repository — the
project's own rule, that a run's working directory must not be inside the
checkout.
