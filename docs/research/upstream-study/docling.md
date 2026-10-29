# Docling — upstream study

**Role in Phase 2:** reference for LC-P2-07 (DOCX revision fidelity) and one of
the two comparison parsers in the fidelity measurement. Read, not linked.

| | |
|---|---|
| **Repository** | https://github.com/docling-project/docling |
| **Pinned SHA** | `8f7ae54409583908f06a2172d260e71b964cc4dd` |
| **Pin method** | `git clone --filter=blob:none` of the default branch, 2026-10-29; SHA read from the local object store |
| **Licence** | **MIT**, verified by opening `LICENSE` at the pinned SHA ("MIT License / Copyright The Docling Contributors") |
| **Decision** | **study only; not a dependency; the comparison arm for text, not for revision truth** |

## The licence, read from the file

The root `LICENSE` at the pinned SHA is the MIT licence, "Copyright The
Docling Contributors". A walk for other licence files finds
`.agents/skills/dignified-python/LICENSE` and `.github/license-header.txt` —
both agent-harness material rather than library code, and neither a
different grant for the library. So the licence position is **clean**, unlike
arXivEdits' and XtraGPT's.

That makes the decision here a **capability** decision, not a permission one,
which is the more useful kind to record.

## The measured finding: revisions are dropped, not represented

The design's §3.2 said the community had reported Docling losing Word
revision text and asked the executing agent to *"assess the loss on documents
with Word revisions; it cannot be the single source of truth for original
revision information."* That is confirmed at the pinned SHA, and the
mechanism is visible in the source.

**Deletions are dropped.** `docling/backend/msword_backend.py:2053`:

```python
# Deleted-text runs (w:del) carry w:delText rather than w:t, so their
# run.text is empty and the filter drops them.
runs = [
    run
    for r_el in paragraph._p.xpath(".//w:r")
    if (run := Run(r_el, paragraph)).text.strip()
]
```

A deleted run holds its text in `w:delText`, not `w:t`. `python-docx`'s
`Run.text` reads `w:t`, so a deleted run reads as empty and the filter
discards it. **The text a mentor deleted never reaches the document model.**
For a project whose entire thesis is *"the deletion is the signal"*, that is
the single most consequential behaviour to know.

**Insertions are not distinguished.** The same filter's docstring lists
*"tracked insertions"* among the content that `paragraph.runs` omits — so
inserted text is likewise outside the run list that this code path reads.
Inserted text that survives into the output arrives as ordinary text, with
nothing marking it as an insertion. **An inserted sentence is
indistinguishable from one the author wrote.**

**The OpenDocument path is the same shape.** `opendocument_backend.py:1931`:

```python
# The walk drops deleted tracked-change text, so drop its comments too.
"descendant::text:tracked-changes//office:annotation"
```

The comment to drop tracked-change comments is itself an admission that
tracked changes are being dropped. The design's §3.2 also recorded that
comment-anchor association is incomplete in the 2026 community reports; the
source here shows the mechanism — comments are linked to **paragraphs**
(`paragraph_comment_map`, `msword_backend.py:881`), not to character ranges.
A comment that covers three words inside a forty-word paragraph is linked to
the whole paragraph. **Sub-paragraph anchoring, which is what a mentor's
"this phrase" needs, is not what this produces.**

## What it does well

Docling is a good document-ingestion library and its strengths are real:

- **A structured document model.** `DoclingDocument` with items, hierarchy
  and a content layer — far richer than a flat text extraction, and directly
  analogous to what Phase 2 wants for a manuscript.
- **Comments as first-class content.** `_add_comments` (`:4918`) adds
  reviewer annotations to the NOTES content layer and links them to annotated
  items, with a documented comment-text format.
- **Broad format coverage**, and a licensing posture clean enough to build on
  if it were the right tool.

Its design goal is **reading a document as it should look now**, with
annotations attached. That goal is compatible with dropping revisions —
arguably it *requires* dropping them, because a document model that shows a
draft's accepted text is a different product from one that shows its
history. The design and Docling are solving different questions.

## How it fits the mentor-trajectory question

| Phase 2 need | Docling | Gap |
|---|---|---|
| comment body and author | yes — first-class | — |
| comment anchor | paragraph-level | sub-paragraph anchoring absent |
| inserted text present in the output | usually yes | not marked as an insertion |
| **deleted text present in the output** | **no — dropped** | the central signal |
| revision author and date | no | not represented |
| revision identity / id | no | not represented |
| `w:moveFrom` / `w:moveTo` | no | not represented |
| structured document model | yes | the right shape to imitate |

The two missing rows — deleted text and revision identity — are exactly
what separates "read the current draft" from "read the revision history".
**Docling can be the comparison arm for the comment dimension and for the
text dimension, and it cannot be an arm for the revision dimension at all,
because it has no revision representation to compare against.**

This is a more useful result than "Docling is good" or "Docling is bad".
The fidelity measurement gets a **three-arm** structure rather than a
two-arm one:

| Arm | What it is | What it measures |
|---|---|---|
| **OOXML-native** | the Phase 2 parser, reading `word/document.xml` and `word/comments.xml` directly | the fidelity target |
| **Text extraction** | Docling, `python-docx`, or pandoc's accepted-text view | what a *reading* tool can know |
| **Library** | docx2python | what an *extraction library* can know |

And the measurement's headline question becomes sharp and answerable: **how
much of the revision history survives in the text-extraction arms at all?**
The answer for deleted text is already visible in the source — none of it
does — and the measurement turns that source reading into a number.

## The community reports the design cites

The design cites two 2026 community issues: `docling-core/issues/464`
(comment anchoring) and `docling/issues/3152` (revision text loss). The
source reading above is consistent with both, and adds a mechanism the
issues do not state: the loss is a consequence of `python-docx`'s `Run.text`
contract combined with an emptiness filter, and the anchor granularity
follows from a paragraph-level map. **An issue report says a symptom; the
source says why.** Phase 2 records the source reading, because a future
Docling version may fix the symptom without the record changing.

## What is decided, and what is not

**Decided:**

- Study only. Not a dependency, not a source of truth.
- Its role in LC-P2-07 is as the **text-extraction comparison arm**, and the
  fidelity report must state that this arm **cannot observe deletions at
  all** — a scope limit of the arm, not a failure of the arm.
- The structured-document-model idea is worth **imitating** for Phase 2's
  own manuscript model: revisions as items in a content layer, with the
  model able to say "this text is a deletion" rather than omitting it.

**Not decided:**

- Whether Docling should be **installed** to run the measurement, or
  whether a smaller text-extraction arm (pandoc, already present on this
  machine) suffices. Docling is a heavy dependency with a model-downloading
  component; the fidelity measurement does not need it, and the design's
  B-tier rule is "clone only when an experiment gap requires it".
- Whether Phase 2's manuscript model should adopt Docling's item/content
  layer shape wholesale. **No** — LabCairn already has a source/locator
  model (ADR-0008, ADR-0009), and a second document model is precisely the
  "two vocabularies for one thing" failure the project's history records.
  The *idea* is borrowed; the *model* is not.

## Reproducing the reference

```bash
git clone --filter=blob:none https://github.com/docling-project/docling.git
git -C docling rev-parse HEAD   # 8f7ae54409583908f06a2172d260e71b964cc4dd
```

Docling was **not installed** and **no benchmark was run** for this study.
Every claim above was read at the pinned SHA — the file and line references
are for that commit, and they are checkable.
