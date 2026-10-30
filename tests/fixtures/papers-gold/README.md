# LC-P2-10's gold corpus

The manuscripts LC-P2-10's annotations are made against, and the note that says
which of them carries which case.

**Nothing here is imported by any module under `src/`.** These are test
inputs, and the readers that will use them are LC-P2-10 T03, T04 and T06, plus
LC-P2-11 later. What exists now is the corpus, the generator that writes it,
and the manifest it is bound to.

## What is in this directory

**One file: this README.** The `.docx` manuscripts are **generated, not
committed** — the reason is the same one
[`tests/fixtures/README.md`](../README.md) gives for LC-P2-07's corpus, and it
is worth repeating here rather than inventing a second argument:

- A checked-in binary is a binary the repository has to carry, and a reviewer
  cannot read it. A `.docx` is a ZIP, so a reviewer who cannot read it cannot
  tell whether it says what the corpus claims.
- A ZIP entry records the moment it was written, so the same fixture written
  twice a second apart is two different files. The writer
  (`tests/docx_fixtures.py`) pins every entry to the ZIP epoch, so the bytes
  **are** reproducible — but only because the writer does that, and a pinned
  binary in the tree is a binary nobody can rebuild.

The generator is [`tests/gold_set_fixtures.py`](../../../tests/gold_set_fixtures.py),
and the generator — not the file — is the reviewable artefact.

## The corpus

Four manuscripts, two projects, two partitions, ten comments.

| Manuscript | Project · version | Partition | Comments |
|---|---|---|---|
| `gold-a-v1` | `proj-gold-a` · `ver-gold-a1` | `train` | `c301`, `c302`, `c303` |
| `gold-a-v2` | `proj-gold-a` · `ver-gold-a2` | `train` | `c401`, `c402` |
| `gold-b-v1` | `proj-gold-b` · `ver-gold-b1` | `test` | `c501`, `c502` |
| `gold-b-v2` | `proj-gold-b` · `ver-gold-b2` | `test` | `c601`, `c602`, `c603` |

**Why four.** The split is by `PaperProject`, never by event: two versions of
one paper are two observations of one thing, so every version of a project is
in one partition. Project A has two versions, because a recurrence is a fact
about two versions. Project B has two, because a project with one version
cannot show a split at all. Four manuscripts is what that structure gives.

**The split is `train` and `test`, one project each.** `validate_manifest`
refuses a project that appears in two partitions, and names it when it does.

## Which manuscript carries which case

| Case | Carried by | What it is |
|---|---|---|
| **An anchor that is not there at all** | `gold-a-v2` / `c402` | The comment is in `word/comments.xml` and **no range marker points at it** — there is no `commentRangeStart` and no `commentRangeEnd`, so the pair that was meant to bracket it does not exist. The reader reports the comment with its body, its author and its date, and reports that its anchor is unknown: there is no paragraph and no character range to read. **This is where the annotator writes `UNKNOWN`**, and it is the annotation guide's case one: the body-side address has nothing to read, so all three of its labels are `unknown`, while the comment's own address still gets real labels. |
| **No author** | `gold-a-v1` / `c303` | The comment's `w:author` attribute is present and empty, which is the writer's only way of saying the author is absent. An author is **not** inferred from the document, the file name or the surrounding comments. |
| **No date** | `gold-b-v2` / `c601` | The comment's `w:date` attribute is present and empty, so the reader reports no date. The file's modification time is **not** a substitute. |
| **The comment and its anchor are about different things** | `gold-b-v1` / `c501` | The comment asks for a control experiment and a baseline variant — a *controls and ablation* problem — and it is anchored on the sentence that reports the evaluation set, which is a *data quality* problem. **This is the case that makes "the two addresses are labelled separately" an observable difference rather than a slogan**: the two labels on this item are not the same label, and the annotation guide's worked example uses this same shape. |
| **The two addresses do not get the same answer** | `gold-b-v1` / `c501` | The corpus is built so that version 2 adds the control the comment asked for, and reports it on the same held-out set — while the evaluation set's own problem, that it is small and drawn from a single collection, is never mentioned again. So the two addresses of this one comment can be answered differently, which is the annotation guide's case for keeping them apart. |
| **An anchor that spans two sentences** | `gold-a-v1` / `c302` | The paragraph the comment is attached to holds two sentences, and the subject the comment is about crosses the boundary between them. A reader that takes one sentence at a time cannot resolve it. |
| **A recurring issue** | `gold-a-v1` / `c302` and `gold-a-v2` / `c401` | The same issue — the significance claim that three seeds cannot carry, and that ten seeds still cannot carry without a test — raised in round one and again in round two. The two comments share one person-given `issue_key`, and they are in one project and in different rounds, which is what the chain's recurrence query is over. |

### The issue kinds the corpus was built to carry

**These are the corpus's intentions, not the gold set's labels.** A reader may
disagree with them — that disagreement is the thing the exercise is for. The
manifest now carries two readings per item and an arbiter's resolution, and
the acceptance record reports how far those two readings agreed.

**This table is an answer key, and it is out of reach of the annotators.**
Whoever labels this corpus reads the manuscript, not this file. The
recurring-issue key in the manifest was renamed for the same reason: **a key
that names its issue hands a reader the answer**, and two of the three
sessions that labelled this corpus had the old name's wording in reach
before they labelled. See the annotation guide's §1.0.1.

**And the readings made without the labels are in the tree too**, in
[`docs/papers/gold-set-blind-readings.json`](../../../docs/papers/gold-set-blind-readings.json).
**They are not here for an annotator either** — they are the evidence that
the labels above are the labels an independent reader reaches as well, and
**a witness checks that they carry no issue key and name none of the
manifest's readers**, because a record of somebody's blindness that names
what they were blind to is not a record of blindness.

| Issue kind | Carried by | At which address |
|---|---|---|
| `data_quality` | `c301`, `c601`, and `c501`'s body-side address | both addresses, except on `c501`, where it is the body-side address that differs |
| `statistical_conclusion` | `c302`, `c401` | both addresses |
| `method_and_hypothesis` | `c303` | both addresses |
| `language_and_format` | `c402`, `c603` | both addresses on `c603`; on `c402` only the comment's own address, because its body-side address has nothing to read |
| `controls_and_ablation` | `c501` | the comment's own address; `c501`'s body-side address is a *different* kind, on purpose |
| `introduction_and_storyline` | `c502` | both addresses |
| `review_response` | `c602` | both addresses |

**`c501` is the one item whose two addresses are meant to carry different
issue kinds** — `controls_and_ablation` at the comment, `data_quality` at the
body — and `c402` is the one item whose body-side address cannot be read at
all. Every other comment is one kind at both addresses, which is what makes
`c501` a difference rather than a habit.

The label set itself lives in
[`src/labcairn/papers/labels.py`](../../../src/labcairn/papers/labels.py), and
it is closed: a label outside it is refused by name.

## The manifest

[`docs/papers/gold-set-manifest.json`](../../../docs/papers/gold-set-manifest.json)
is the contract the annotators fill in. One item per comment in the corpus, so
**ten items**.

Each item carries:

| Field | What it is |
|---|---|
| `item_id` | the item's own id, derived from the project, the version and the comment |
| `project_id`, `version_id` | the paper project the comment was written against, and the version of it |
| `feedback_id` | the id the chain would mint for this comment in this version: `fb-<sha256(version_id + NUL + comment_id)[:16]>` |
| `fixture`, `comment_id` | which manuscript and which comment in it |
| `comment_locator` | **the comment's own address**, in `word/comments.xml` — *what was written* |
| `paragraph`, `start`, `end` | **the body-side address** — *where it was written about*. All three are `null` on `c402`, because its anchor is not in the file. |
| `annotations` | the two independent readings. **Filled.** |
| `resolution` | the arbiter's answer. **Filled.** |
| `issue_key` | the person-given key for "the same problem", where there is one |

**Both addresses are read out of the written file**, by the project's own
reader (`labcairn.material.ooxml.read_document`), rather than recomputed here.
A gold set is scored against systems that read the same manuscript, so its
addresses have to be in the reader's coordinate system; an address spelled a
second way would be a second vocabulary for the same rows.

**The contract reads the manifest itself.**
`labcairn.papers.gold_manifest.load_manifest()` loads this file from
`docs/papers/gold-set-manifest.json` and checks it against the manifest's own
rules, and `validate_manifest` checks the structure on its own.

### The body-side address is paragraph-granular

**This is the writer's granularity and the reader's, and it is worth knowing
before you fill anything in.** The fixture writer
(`tests/docx_fixtures.py`) puts a comment's range markers around the whole
paragraph it is attached to, so the reader reports `start` at the beginning of
the paragraph and `end` at its end. The **subject** the comment is about —
the phrase inside the paragraph — is the corpus's own record, in the
fixture's `anchor_text`, and it is named in each fixture's `expectations` and
in the case table above.

Every commented paragraph in this corpus holds exactly one comment, so the
paragraph-wide reading and the subject reading never compete for the same
comment.

**One item has no body-side address at all.** `c402`'s comment carries no
range markers, so the reader reports no paragraph and no offsets for it, and
the manifest records `null` for all three. That is the annotation guide's case
one: the body-side address has nothing to read, so all three of its labels are
`unknown`, and the comment's own address still gets real ones.

### `issue_key` is one field beyond the manifest's schema

`labcairn.papers.gold_manifest` reads the fields above and **ignores
`issue_key`** — it is not part of the manifest's own schema. It is here so
that the recurring issue is visible in the manifest as well as in the corpus,
and it is copied from the generator rather than written by hand. A comment with
no key is uncategorised, and no key is inferred from the text: ADR-0017 D6
says a recurrence is a relation somebody records, not something a similarity
score decides.

## The annotations are in, and they are not a person's work

**Every item carries two annotations and an arbiter's resolution, and the
reading was made by Claude sessions rather than by people.** LC-P2-10 T06 was
two sessions working independently from the annotation guide over this corpus,
followed by a third that wrote its own reading first and compared it against
the two afterwards. **The manifest's ids say which is which** — `agent-annotator-a`,
`agent-annotator-b`, `agent-arbiter-1` — because an id that does not say what
it is will be read as a person.

**The two states are separate checks, and the project keeps them separate:**

- `labcairn.papers.gold_manifest.validate_manifest` says the manifest is **well
  formed**.
- `labcairn.papers.gold_manifest.require_annotated` says the gold set is
  **finished**.

**A manifest that carries labels nobody wrote is worse than an empty one**,
because it looks finished — which is why the ids say who read it, and why the
acceptance record says what the agreement number does and does not measure.
**These labels were written by sessions, and the ids say that**, so a reader
cannot mistake the manifest's shape for a human's work.

### How one is filled in

One item per comment, and the comment's two addresses are labelled separately.
Each annotation carries the annotator's id, the moment, and the three axes of
each address:

```json
"annotations": [
  {
    "annotator_id": "agent-annotator-a",
    "annotated_at": "2026-10-30T23:25:45+08:00",
    "comment_address": {
      "issue_kind": "statistical_conclusion",
      "response_state": "unknown",
      "assessment_outcome": "unknown"
    },
    "body_address": {
      "issue_kind": "statistical_conclusion",
      "response_state": "unknown",
      "assessment_outcome": "unknown"
    }
  },
  { "...": "the second annotator" }
],
"resolution": {
  "arbiter_id": "agent-arbiter-1",
  "resolved_at": "2026-10-30T23:40:00+08:00",
  "comment_address": { "...": "the arbiter's answer" },
  "body_address": { "...": "the arbiter's answer" }
}
```

**The `agent-` prefix is not decoration.** The ids name sessions, and a
reader who was not there cannot tell from `annotator-a` whether it was a
person or a process — so the id says which it was.

The axis names and the labels each axis accepts are in
[`src/labcairn/papers/labels.py`](../../../src/labcairn/papers/labels.py), and
what each axis asks, and when `UNKNOWN` is the honest answer, is in
[`docs/papers/annotation-guide.md`](../../../docs/papers/annotation-guide.md) —
the guide LC-P2-10 T01 writes, and the document the two annotators work from.
**`unknown` is an answer, not a missing value**: a comment whose anchor is not
there, a response nobody made, an assessment with no evidence — each has an
honest answer that is neither "addressed" nor "not addressed".

**The resolution is a row of its own, and never an overwrite.** A disagreement
that existed is information: it is the thing the agreement number is computed
from.

## Generating the corpus

**Write it outside the checkout.** The project's own rule is that a workspace
inside the checkout makes the run depend on the tree it runs in and leaves the
checkout dirty. Run this from the repository root:

```bash
python -c "import sys; from pathlib import Path; sys.path.insert(0, 'tests'); import gold_set_fixtures as g; [print(n, p) for n, p in g.write_corpus(Path('../gold-corpus')).items()]"
```

**Nothing is written at import.** A module that writes files when it is
imported dirties the checkout during pytest's collection, and the collection is
not a place where a side effect belongs. Every write is an explicit call.

### The bytes do not move

**The corpus is byte-reproducible, and that is what makes the manifest's
`sha256` worth anything.** Every ZIP entry is pinned to the ZIP epoch by the
writer, and the entries are written in a fixed order. The generator says so
itself:

```python
from gold_set_fixtures import assert_corpus_is_reproducible

assert_corpus_is_reproducible(Path("../gold-corpus-check"))
```

It checks three things: two directories give the same bytes, writing over a
file gives the same bytes as the first write, and the hash the manifest
records is the hash of those bytes.

### The manifest is bound to the corpus

The manifest's `corpus` section names every manuscript, its project, its
version, its partition, the SHA-256 of its bytes, and the generator that wrote
it. The generator can check that the committed manifest still describes the
corpus in the tree:

```python
from gold_set_fixtures import assert_manifest_matches_corpus

assert_manifest_matches_corpus()
```

**Structure only.** The annotators fill in `annotations` and `resolution`, so
those are not compared — a manifest that has been annotated is still a
manifest that must match its corpus. Everything that names the material is
compared, and the manifest is also read through `validate_manifest`, so a
manifest that breaks one of the manifest's own rules is refused by name.

## What this corpus cannot reach

Stated here rather than discovered later, because a synthetic corpus that
looks complete is worse than one that admits what it cannot do.

- **Real advisor prose.** These are ten comments and sixteen paragraphs of
  clean English about a classifier. Real comments carry hedging, politeness,
  typos and half-finished thoughts, and none of that is here.
- **A comment range narrower than its paragraph.** The writer cannot express
  one, so no comment in this corpus is attached to a phrase the file can
  single out. LC-P2-07's corpus has the same limit, and the pilot corpus is
  where it is reached.
- **A range that starts and never ends, and a range that ends and never
  started.** The writer can express both, and the reader names them
  separately from a comment with no range at all. This corpus carries only the
  third, because it is the one the annotation guide gives a rule for: an
  unpaired marker still names a paragraph, and the guide does not say what an
  annotator should do with a body-side address that has a paragraph and no
  offsets. A corpus case the guide cannot answer is a broken gold set.
- **Comments in headers, footnotes or endnotes**, comments carried in the
  `w15` comments-extended part, and run fragmentation inside a revision. The
  list of what a real Word document contains and this writer cannot produce is
  `KNOWN_GAPS` in [`tests/docx_corpus.py`](../../../tests/docx_corpus.py).
- **Real disagreement.** The issue kinds above are the corpus's intentions.
  What two annotators actually disagree about is not in here, and it is not
  something a generator can supply.
