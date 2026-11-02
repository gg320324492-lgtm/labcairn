# LC-P2-10 — independent review of the process-annotation and gold-set record

**Record reviewed:** `docs/acceptance/LC-P2-10-acceptance.md` (the label set,
the guide, the agreement machinery, the synthetic corpus, and the ten items'
two readings plus the arbiter's resolution), as it stands in this branch.
**The tree reviewed:** `e10359e`, the branch tip this review worked in.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreter:** the repository's virtualenv at `E:\LabCairn\.venv` (CPython
3.12) with `PYTHONPATH` pointed at this worktree's `src/` — `import labcairn`
verified to resolve to this worktree before any run. Each run had its own
`--basetemp` under `E:\labcairn-local\tmp`.

**Method.** All thirty-four mutations of §4 were re-applied, one at a time;
every mutation's diff was read before its witness ran, and the file was
restored with `git checkout --` after. Several first applications produced no
usable result and were redone before anything was believed; each redo is
noted below, because several of the record's mutation rows are sensitive to
*which layer* the mutation is spelled at — a fact a re-applier needs.

## 1. Baseline

The four witness files (`test_gold_set_labels.py`,
`test_gold_set_agreement.py`, `test_gold_set_manifest.py`,
`test_gold_set_corpus.py`) — **48 passed**, the 11 + 13 + 13 + 11 the
record's §5 table claims.

## 2. What was re-applied, and what happened

All thirty-four rows turned the witness their row names red. The ones with
a spelling sensitivity are marked; in each case the sensitivity is a
reproducibility note, not a false red — the property is witnessed and the
effective form is stated.

| # | Result | Note |
|---|---|---|
| M1-M3 | red, exactly their witnesses | |
| M4, M5 | red | `frozenset(f)` over an existing `frozenset` **returns the same object** in CPython, so the naive "copy" spelling survives; the real copy (`frozenset(sorted(f))`) reddens the identity witness. The record's "copied instead of imported" needs that spelling. |
| M6 | red, exactly its witness | |
| M7, M8 | red | |
| M9 | red | The witness is the `LabelAgreement.rate` property (`gold_manifest.py:206`); a mutation at `agreement()`'s own empty-manifest raise does not reach it. Effective form: `rate` returns `0.0` on a zero denominator. |
| M10, M11 | red | M11's witness watches the **parse layer** (`_item`); folding the resolution into `annotations[1]` there reddens it. The same intent spelled inside `agreement()` leaves the witness green, because the witness never calls `agreement()`. |
| M12-M16 | red, exactly their witnesses | |
| M17-M19 | red, exactly their witness | |
| M20 | red | `if False:` on the slack branch (all cases fall through to the structural one) leaves the witness green — its three cases get the same answers from both branches. Effective form: the inside-limit branch stops comparing against the slack (`> 0.0`), which reddens it on the case that costs exactly the slack. |
| M21 | red | The effective form is the wall clock (`gmtime()[:6]`); the default `ZipInfo(name)` stamps the 1980 epoch, which is *already fixed* and survives. |
| M22 | red | **The record's row names a witness the literal form cannot redden.** Deleting the annotations-count block leaves `test_the_completion_check_agrees_with_the_manifests_own_state` green on this tree — the tree's manifest is finished, so that witness takes its *finished* branch and only calls `require_annotated`, never reaching the counting. (Counting-mutation form A reddens `test_every_item_has_two_annotations_and_a_resolution` instead.) The form that reddens the named witness is *mis*-counting (`!= 1`), which makes the finished manifest fail the check. Finding 1 below. |
| M23-M28 | red, exactly their witnesses | M27 and M28 share `test_every_item_has_two_annotations_and_a_resolution`, as the record states. |
| M29 | red | Again a parse-layer witness: collapsing the two addresses in `_annotation` reddens it; the same intent in `_labels_of` (the agreement read) does not. |
| M30 | red, exactly its witness | |
| M31, M32 | red, exactly their witness | Both are data mutations on `docs/papers/gold-set-manifest.json` (a repeated `annotator_id`; an `arbiter_id` equal to an annotator). |
| M33, M34 | red, exactly their witnesses | Both are data mutations on `docs/papers/gold-set-blind-readings.json` (one flipped `issue_kind`; an injected `issue_key`). |

**The two-witnesses-cover-nothing check.** The record claims M30, M31 and M32
were each run against both of the two witnesses (the rule and the data), each
reddening only the one its row names. Verified: M30 (rule removed) against
the data witness — **green**; M31 (data broken) against the rule witness —
**green**. The two watch different things, as the record says.

## 3. What was checked against the tree, not against the tests

- **The blind readings are in the tree and are blind.**
  `docs/papers/gold-set-blind-readings.json` exists, its `readings[0]`
  records the fourth reading (`blind-audit-1`, with its `given`/`withheld`
  lists), and both witnesses over it pass on the unmutated tree — it
  carries no issue key and names none of the manifest's readers.
- **The manifest binds to the corpus bytes.**
  `test_the_corpus_section_records_the_bytes_that_are_written` and
  `test_the_corpus_is_reproducible` pass: the recorded sha256 values are the
  hashes of what `write_corpus` writes, twice identically.

## 4. What could not be checked, and why

- **The two independent readings themselves.** They were made by two Claude
  sessions and an arbiter, outside this tree and before it; the tree holds
  their *result* (the manifest's annotations, the blind readings file) and
  witnesses over both, but the process claims — that the two readings were
  made independently, that §6's one hint channel reached two of the three
  sessions and no more — are history, not state. The record says as much;
  this review says it too.
- **The sixty agreeing labels as a measurement.** What the tree can and
  does check is that the manifest's labels are internally consistent
  (closed set, two readers per item, an arbiter who is neither, all
  addresses labelled) and that the agreement number is computed from them
  over the named denominator. That the two readers *agreed* is a fact about
  the session that wrote the rows.

## 5. Findings

1. **(Finding) M22's row points at a witness the literal mutation cannot
   redden.** The completion-check witness takes its finished branch on this
   tree and therefore cannot see a deleted counting check. The record's
   "the completion check stops counting the readings" reddens
   `test_every_item_has_two_annotations_and_a_resolution` (which three
   mutations share), not the witness its row names. The named witness is
   reddened by the *mis*-counting form. One line in the record would make
   the row reproducible; as written, a re-applier reports a survivor.
2. **(Note) Six of the thirty-four rows are layer-sensitive** (M9, M11, M20,
   M21, M29, and M4/M5's copy spelling): each has exactly one spelling that
   reddens the named witness and at least one natural spelling that does
   not. Every one of them was resolved to a red in this review, so the
   verdict is unaffected — but the table's one-line descriptions are not
   yet reproducible on their own, which matters for the next reviewer.
3. No claim with nothing behind it was found. The four decisions of §1 are
   each held by named code and witnessed; the corpus, the manifest, the
   blind readings and the agreement machinery are all in the tree, and the
   witnesses over them are green.

## 6. Verdict

**Holds, with one reproducibility finding.** Thirty-four mutations
re-applied, thirty-four reddens — including the two data mutations and the
fourth blind reading's guards, and including the cross-check that the rule
witness and the data witness watch different things. The one finding is a
witness attribution on M22 that the literal mutation cannot reproduce, plus
the layer-sensitivity note on six rows; neither affects the properties the
record claims.
