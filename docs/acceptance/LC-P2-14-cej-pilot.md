# LC-P2-14 — The batch-7 review–response–revision chain: two negative witnesses and a route pilot — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation
and ablation) · **Route under test:** [`LC-P2-09`](LC-P2-09-acceptance.md) (the
feedback chain) and [`LC-P2-07`](LC-P2-07-fidelity-baseline.md) (the DOCX reader) ·
**This record:** a **negative** result on one material and a **routing** result on
the same material.

**Status.** The two negative witnesses are in the tree and mutation-checked. The
route pilot ran end to end against the real material and its evidence lives
outside the repository. **No full ingestion was performed, and none is
committed to here**; §5 says what a future ingestion would need. **Nothing in
this record rates the material or the reviewers.**

**What this record does not carry.** The manuscript's title, its sentences,
the reviewer's comments, the authors' replies, the section names, the file
names and the names of the people involved are not in this file and not
anywhere in the repository. The material is referred to as **batch 7**, and
each file by the first twelve hex characters of its sha256. The pilot's own
outputs — which carry indices and hashes only — live outside the repository
under `E:\labcairn-local\cej-pilot\`, beside the read-only material. The tests
use synthetic sentences written for this file's purpose; no sentence from the
material is in the tree.

**Measured:** 2026-11-05 on `main` at `fc06cee7e79f20e831c9412f880e30fb323a8b30`,
on Windows 11 (AMD64), Python 3.12.13. The recon that named the material and
the two gap types is `E:\labcairn-local\batch7-recon\RECON.md` (chain-external).

---

## 1. The fixture the negative witnesses stand on

Two synthetic `.docx` files, built in `tests/test_ooxml_revisions.py` from the
same `_docx_bytes`/`_document` helpers the file's other hand-built cases use:

* **Red font, no tracked change.** One paragraph, three runs; the middle run
  carries `w:rPr/w:color w:val="FF0000"` and the archive declares no
  `w:ins`, no `w:del`, no move and no row mark.
* **A quoted opinion, no comments part.** Two paragraphs, the first beginning
  `Reviewer #2:` and the second `Response:`; the archive has no
  `word/comments.xml` and no comment range markers.

These are the two shapes batch 7 actually writes: its marked manuscripts carry
red runs and **zero** tracked changes, and its response letters carry the
reviewer's opinion as body text and **zero** Word comments. The reader must
report both as absent, because both guesses — "red means inserted" and "a
sentence beginning with a reviewer's name is a comment" — would mint events
the file does not state.

## 2. The two witnesses, and the mutations that make them red

| Witness | Property it holds | Mutation it must survive |
|---|---|---|
| `test_red_font_is_not_a_revision_and_its_text_is_counted_once` | `revisions` and `comments` are empty, no problem is reported, and the red words appear **once** in both views | the reader treats a run with any `w:color` as an `ins`: the first assertion fails (`RevisionEvent(kind='ins', text=' under nitrogen')`) |
| `test_a_quoted_reviewer_paragraph_is_not_a_comment` | `comments` and `revisions` are empty, no problem is reported, and both paragraphs are body text once each | `read_document` mints a `CommentEvent` for a paragraph starting `Reviewer #`: the first assertion fails (`comment_id='guessed-0'`) |

**Measured three ways, with the reader mutated in place and restored between
runs (no `git checkout`; the tree carried uncommitted work):**

```
no mutation:      2 passed
mutation A only:  test_red_font... FAILED, test_a_quoted... passed
mutation B only:  test_red_font... passed, test_a_quoted... FAILED
restored:         2 passed
```

Each mutation reddens **its own** witness and not the other, which is what
makes them two witnesses rather than one count. The full file is 38 passed.

**What the witnesses do not say.** They do not say the material is wrong to
use red font, and they do not say a quoted paragraph is less of a comment than
a Word comment. They say the product does not classify it as one. §5 names the
gap that follows from that.

## 3. The material, as the product's reader measured it

Six files: both response letters, both marked manuscripts and both clean
manuscripts. Read with `labcairn.material.ooxml.read_document` from bytes on
disk, never written to. The red-run count is this pilot's own rule: every
`w:r` whose direct `w:rPr` carries `w:color@w:val="FF0000"`. The recon reports
432 / 66 red runs in the marked files and 1 / 0 in the clean files; this rule
lands on 401 / 62 and 1 / 1. **The two are different counting rules over the
same archives** — the recon's rule is not restated here and is not claimed to
be the same one — and neither number changes what the files say: red runs are
present, tracked changes are absent.

| Round | File | sha256 prefix | Paragraphs | Reader revisions | Reader comments | Red runs | `w:ins` | `w:del` |
|---|---|---|---|---|---|---|---|---|
| R1 | response letter | `7d42fdf6f9e0` | 268 | 0 | 0 | 659 | 0 | 0 |
| R1 | marked manuscript | `11cc79df2ba2` | 180 | 0 | 0 | 401 | 0 | 0 |
| R1 | clean manuscript | `13a0d7d131f0` | 180 | 0 | 0 | 1 | 0 | 0 |
| R2 | response letter | `fdb2fbe70e83` | 129 | 0 | 0 | 162 | 0 | 0 |
| R2 | marked manuscript | `b87891240000` | 183 | 0 | 0 | 62 | 0 | 0 |
| R2 | clean manuscript | `9216a0d85837` | 183 | 0 | 0 | 1 | 0 | 0 |

**Every file extracts with zero problems.** The zero revision count is the
correct reading of these archives, and §2's real-material side: the marked
files say "changes marked" and mean red font.

**The one red run in each clean file is the control.** A colour is not a
sufficient mark of an edit — the clean files carry a red run that is not one.
Any future red-source rule has to survive that fact (§5.2).

## 4. The route pilot

**What was routed.** For each round, the response letter entered the pilot
workspace under a neutral name, was ingested by the product's own ingestion,
and was registered as a version of the pilot project. `record_replies` then
paired **one `Response:` paragraph with the nearest preceding non-response
paragraph** — the pilot's rule, stated here so it can be contested; the letter
states no explicit link — and recorded the exchanges. `list_replies` read them
back.

| Round | `Response:` paragraphs | Pairs found | Rows recorded | Rows read back | Words match the document |
|---|---|---|---|---|---|
| R1 | 29 | 29 | 29 | 29 | yes |
| R2 | 8 | 8 | 8 | 8 | yes |

**The words are the document's, not the caller's.** Each read-back row's
`objection_text_sha256` and `answer_text_sha256` were recomputed from the
paragraph at the index the row names, and every one matched. The parties are
`reviewer`/`author` throughout, and the pairing grade is `observed` — the only
grade the pilot can honestly claim.

**The store check was read-only.** The pilot store (a store this pilot created
under its own directory, not the chain's) was opened with SQLite
`mode=ro` after the run: **37 rows in `replies`** (29 + 8), two rows in
`paper_versions`. Nothing in the chain's real store was read or written.

**What this proves, and what it does not.** It proves the reply table and
`record_replies`/`list_replies` hold this material's exchange shape with no
change to the product: one paragraph of objection, one of answer, a party on
each side. It does **not** prove the chain can route the opinion source or the
revision source; both are absent from these files in the shapes the product
reads, and §5 is about that.

## 5. The two gaps, and what a full ingestion would need

### 5.1 Opinion source: the comment is a quoted paragraph, not a Word comment

**The fact.** Every response letter carries the reviewer's opinion as ordinary
body text and has no `word/comments.xml`; the reader reports zero comments,
correctly. The opinion therefore has no `comment_locator`, no `CommentEvent`,
and no address of its own in the product's vocabulary. The reply row names the
**paragraph** the objection was read from and carries its text hash — a place
in the letter — but the product has no way to say "this is a reviewer's
opinion, sourced from a quoted paragraph of this letter".

**What a future ingestion would need, at minimum:**

1. A **comment-source type** on the chain's comment records — at least
   `docx_comment` (the existing shape) and `quoted_paragraph` (this one), with
   the source document and the paragraph index carried, so two opinions that
   say the same words in different places are different records.
2. A **reader for the quoted shape**: the layout rule (the paragraph before a
   `Response:` paragraph) is a *pairing rule*, not a parse; the product must
   keep the rule separable from the text, as `record_replies` already does
   with paragraph indices.
3. A **link from the reply to its comment record**, so a settlement can say
   which opinion an answer is about. Today the reply has the objection
   paragraph but no comment identity; `settle_reply` takes evidence and a
   decider, not a comment address.
4. The **author of a quoted opinion is not stated by the file** — only the
   `Reviewer #N` framing. A record that needs an author must carry it as
   unknown or as a reviewer label, never as a person.

**Magnitude.** One work order of the size of LC-P2-09's reply subtask: a
source-type enum and its constraints, a reader for the quoted layout, a join
column and its witness, plus the route over this material. The pilot's
pairing rule already fits the table, so the work is the missing identity, not
a second reply mechanism.

### 5.2 Revision source: the marked manuscript is red font, not tracked changes

**The fact.** Both marked manuscripts declare zero `w:ins`/`w:del` and carry
401 and 62 red runs (this pilot's rule). Red marks *where* the authors changed
something; it does not carry the original words, so the deleted text is not
recoverable from the marked file at all. The clean manuscript is the only
place the edited text can be compared against, and the clean file's own red run
shows the colour is not a sufficient mark.

**What a future ingestion would need, at minimum:**

1. A **minimum recognition rule** stated as a rule and not as a heuristic:
   a run whose `w:rPr/w:color@w:val` is the material's agreed mark colour
   (here `FF0000`) is *flagged text*, not an insertion. The flag is an event
   of its own kind — not `ins`, because the file never says the words were
   inserted.
2. A **version pair** (marked, clean) and a paragraph-level alignment between
   them, so a flagged span can be given its before/after text; without the
   clean file the flag has no baseline, and inventing one from the marked file
   alone would be the guess the reader refuses today.
3. A **witness for the false positive**: the clean files each carry one red
   run that is not an edit, so the rule must report it as flagged text and not
   as a change. The synthetic witness in §2 is the unit-level half; a real
   pair is the other half.
4. **An answer to what a flag means** — "the authors marked this", not "this
   is a tracked change" — because the chain's revision kinds, author and date
   do not exist in these files.

**Magnitude.** One work order: a flag event kind in the DOCX reader, a
marked/clean alignment step (the version graph already holds the pair), the
false-positive witness, and the route over two rounds. It is smaller than
LC-P2-07's reader because the XML carries no revision tree to walk; it is
larger than a colour filter because the before/after text needs the pair.

### 5.3 What is explicitly not proposed here

* **No full ingestion of batch 7.** The material has no advisor-graded ground
  truth; the batch is a negative witness and a route, not a rating case.
* **No change to the reader in this commit.** The two witnesses hold the
  product's current, honest refusal; the gaps above are design evidence for a
  future work order, not a licence to guess today.
* **No score, no comparison, no claim about the reviewers.** The count of
  exchanges is a property of the letters, not a measure of their quality.

## 6. Where the evidence lives

| What | Where |
|---|---|
| Recon (four questions, chain-external) | `E:\labcairn-local\batch7-recon\RECON.md` |
| Pilot script and outputs (indices, counts, hashes) | `E:\labcairn-local\cej-pilot\run_pilot.py`, `out\route.json`, `out\summary.txt` |
| Pilot store (this pilot's own) | `E:\labcairn-local\cej-pilot\pilot.db` |
| Mutation harness for the two witnesses | `E:\labcairn-local\cej-pilot\mutate.py` |
| The witnesses | `tests/test_ooxml_revisions.py` |
| The reader they are about | `src/labcairn/material/ooxml.py` |
| The reply table they route into | `src/labcairn/papers/replies.py` |

**The material itself is not in the repository and is not in this record.**
`tests/test_no_reference_leakage.py` is the witness that keeps it out; the
pilot's copies and its store live outside the checkout, under
`E:\labcairn-local\`, which is where every chain-external measurement in this
project lives.
