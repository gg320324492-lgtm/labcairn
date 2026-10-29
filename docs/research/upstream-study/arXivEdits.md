# arXivEdits — upstream study

**Role in Phase 2:** reference for LC-P2-08 (version DAG and cross-version alignment)
and LC-P2-10 (edit-intent classification). Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/chaojiang06/arXivEdits |
| **Pinned SHA** | `113913d68522c1c8428d8e191d5c9bed633da6ce` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Paper** | Jiang, Xu & Stevens, *arXivEdits: Understanding the Human Revision Process in Scientific Writing*, EMNLP 2022 — https://arxiv.org/abs/2210.15067 |
| **Licence of the repository code** | **none declared** — see below |
| **Licence of the corpus** | per-paper, recorded in the dataset |
| **Decision** | **study only; no code copied, no weights used, no data ingested** |

## The licence question, and why it is not a formality

**The repository ships no `LICENSE` file.** `find . -maxdepth 3 -iname 'LICENSE*'`
at the pinned SHA returns nothing; the root holds `README.md`, `code/` and `data/`.

The README does contain the word "license", and reading it as the repository's
licence is the mistake this record exists to prevent. What it says is:

> *"We add license information every version of all papers."*

Those are the licences of **the 751 arXiv papers in the corpus** — an
`arXiv.org/licenses/...` URL per paper version, e.g.
`http://arxiv.org/licenses/nonexclusive-distrib/1.0/`. Eight distinct
per-paper licences are listed. That is a statement about the *data*, and it
is a useful one: it means the corpus is not uniformly licensed, and a Phase 2
experiment that trains on it inherits a per-paper mixture rather than one
clear grant.

It is not a statement about the code. A repository with no licence file grants
no rights to copy its source, and "no licence declared" is the honest label —
not "MIT", and not "public domain because it is on GitHub". The consequence
for Phase 2 is concrete: **the alignment pipeline may be read and its ideas
understood, and no line of it may be copied into LabCairn.** The
implementation must be written from the paper and from the specification of
the behaviour, which is what the project's own `UPSTREAM_REFERENCES.md`
already requires ("a README, docstring or architecture overview is a claim, not
evidence").

The fine-tuned checkpoints are a separate matter again. The README publishes
BERT sentence-alignment checkpoints and T5 edit-intention classifiers on the
Hugging Face Hub. **Weights are not covered by a code licence**, and no
weight file is fetched, downloaded or evaluated in this project. An
experiment that wants a trained aligner must record that model's own licence
at the time of use — the same rule the design's dataset-consent section sets
for corpora.

## What is actually in the tree

| Path | What it is | Relevance |
|---|---|---|
| `code/aligner/CRF_aligner.py` | BERT + CRF sentence pair alignment | the alignment idea; see below |
| `code/edits/extract_edits.py` | character-offset edit extraction over an aligned pair | the edit-span idea |
| `code/intention/` | fine-tuned T5 edit-intention classification | the label taxonomy's source |
| `code/pipeline/` | end-to-end: align → extract edits → classify intention | the shape of a comparable baseline |
| `data/` | the corpus, 751 papers, per-paper licence column | the licence column above |

The pipeline is the useful part: **input paragraph pairs, output sentence
alignment, then edit extraction, then intention classification.** That is the
same decomposition Phase 2 needs for LC-P2-08 → LC-P2-10, and the design
already names it.

## The two implementation facts that matter for adoption

**The aligner requires a GPU.** `CRF_aligner.py:24` opens with

```python
assert torch.cuda.is_available(), print("CUDA is not available!")
```

and hard-codes `my_device = torch.device("cuda:0")`. It also depends on
`pytorch_transformers`, a package that predates the `transformers` split and
is unmaintained. So the reference implementation is **not runnable on the
Phase 2 pilot machines** and cannot serve as an executable baseline as it
stands. Two consequences: the comparison in LC-P2-14 needs a *reimplementation*
of the method rather than a subprocess call to this code, and the Phase 2
implementation must be written against a CPU-only, dependency-light target
from the start.

**Edit extraction is character-offset diffing.** `extract_edits.py` builds
character offsets with `diff_match_patch` and a hand-written
`char_offsets_from_diff_v1` / `_v2` pair, then tokenises with NLTK's
`sent_tokenize` / `word_tokenize`. This is the classic approach and the
design lists `diff-match-patch` in its C tier as a text-diff reference
baseline. It is worth noting what it does *not* do: it operates on two plain
strings, so it has no author, no timestamp and no notion of which side is
"the advisor" — because arXiv versions carry none. **That is the gap Phase 2
must close**, and it is why the primary source for LC-P2-07 is the OOXML
itself, not a diff of extracted text.

## How well it fits the mentor-trajectory question

**Partial, and the limits are structural rather than fixable by tuning.**

| What Phase 2 needs | arXivEdits provides | Gap |
|---|---|---|
| sentence-level alignment across versions | yes (BERT+CRF) | needs GPU; needs reimplementation |
| edit spans with character offsets | yes (diff_match_patch) | plain-text only, no author/date |
| edit *intention* labels | yes (T5, 6 classes) | the taxonomy is arXiv-flavoured; see below |
| who wrote the change | **no** | arXiv versions have no authors; Word revisions do |
| student response to advice | **no** | no advice exists in the data |
| reviewer reaction to the change | **no** | no review data |
| outcome of the change | **no** | no downstream signal |

The last four rows are the whole of the mentor-trajectory question, and
arXivEdits answers none of them. Its value is **methodological**: it shows
that sentence alignment plus edit extraction plus intention classification is
a workable decomposition, it supplies a published label taxonomy to argue
with, and it supplies a corpus whose licence is recorded per paper.

## The label taxonomy, read as a starting point and not as a target

The edit-intention classes are the interesting part, because they are a
published, citable answer to "what are the kinds of change a researcher
makes". The design's LC-P2-10 label set ("research question and motivation,
novelty and contribution, introduction and storyline, method and hypothesis,
data quality, controls and ablation, statistical conclusion, figures, sources,
review response, language and format, other/unknown") is a **separate, wider**
taxonomy, and the two are not interchangeable.

Concretely, for Phase 2:

- arXivEdits' categories describe **what kind of text edit** was made, which
  is a different axis from **what kind of problem the advisor was pointing
  at**. A rewrite can be motivated by an evidence gap and be implemented as a
  paraphrase; the two labels answer different questions.
- A Phase 2 annotation guide that renames arXivEdits' classes would be
  claiming a comparability that does not exist. The honest relationship is:
  **arXivEdits is a comparison baseline for the alignment and extraction
  steps, and its intention taxonomy is one published candidate among several
  for the Phase 2 label set** — which the design says must be settled by
  two annotators and an arbiter (LC-P2-10), not by importing a taxonomy from
  a 2022 paper.

## Reproducing the reference

Nothing here is reproduced, and the record says why rather than leaving it
implicit:

```bash
# the clone used for this study
git clone --filter=blob:none https://github.com/chaojiang06/arXivEdits.git
git -C arXivEdits rev-parse HEAD   # 113913d68522c1c8428d8e191d5c9bed633da6ce
```

Running the pipeline needs CUDA, `pytorch_transformers`, NLTK corpora, and
downloaded Hugging Face weights. **No such run was performed, and no number
from this repository is reported anywhere in Phase 2 as a measured result.**
The claims in this record are all claims about *what the tree contains*, and
each was read at the pinned SHA.

## Failure cases Phase 2 must not inherit

Carried forward as negative-test candidates for LC-P2-08 and LC-P2-09, each
one a place where a diff-based method produces a confident wrong answer:

1. **Paragraph reordering.** A moved paragraph diffs as delete-plus-insert,
   and the alignment has no way to know it was a move.
2. **Sentence split and merge.** One sentence rewritten as two diffs as
   delete-plus-insert-plus-insert, with no relation to the original one.
3. **Structural rearrangement.** Moving a section changes every offset after
   it, so character offsets are only comparable within a matched region.
4. **Number-only change.** A changed result value inside otherwise identical
   text is a *scientific* change and a *near-invisible* textual one; a
   similarity-threshold aligner may score the pair as "unchanged" and drop
   the most important edit in the paper.
5. **Paraphrase.** High lexical dissimilarity between an original sentence
   and its rewrite, which is exactly the case where the advisor's intent is
   worth learning and the text gives the least signal.

Case 4 is the sharpest: the phase's target is *scientific* revision, and a
method that filters by textual similarity is weakest exactly where the
scientific content moved.

## What is decided, and what is not

**Decided:**

- arXivEdits is a **study-only** reference. No code copied, no weights
  fetched, no corpus ingested.
- Its value to Phase 2 is the **decomposition** (align → extract → classify)
  and the **published taxonomy to argue with**, not an executable baseline.
- If LC-P2-14 compares against an arXivEdits-style baseline, the baseline is a
  **reimplementation**, and the record must say so and name the licence
  position of the original.

**Not decided:**

- Whether the Phase 2 implementation adopts a neural aligner at all. The CPU
  constraint, the unmaintained dependency, and the licence position all point
  to a rule-and-similarity aligner first, with the neural route open only if a
  measured gap requires it.
- Whether any arXivEdits corpus is used. It is **not authorised** by
  anything read so far: the corpus is a mixture of eight per-paper licences,
  several of which are non-commercial (`by-nc-sa`) or attribution-bound
  (`by-sa`), and the design's data-consent rules apply to it unchanged.
