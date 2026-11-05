# LC-P2-28 — Full ingestion of review–response–revision sets — task breakdown

**Status:** design only, 2026-11-05. No work dispatched, no product code
changed. **ADR:** [`ADR-0020`](../adr/ADR-0020-opinion-and-flag-sources.md).
**Priority:** behind the Phase 2 exit gate; it adds source honesty, not a
measured capability gain.

## 0. Why this exists

Three material batches have now been measured. Batch 7's response letters
quote reviewer opinions as body text and mark revisions in red font; the
product's two negative witnesses hold its honest refusal. Batch 9's letters
supplied 44 clean objection/answer pairs through `record_replies`, plus a
mixed-source letter and a duplicate-file shape. Batch 8 supplied a
translation pass with thousands of tracked changes that is **not** a
distillation source. A full ingestion would have to tell all of these apart
without inventing events the files do not state.

## 1. Ownership map (parallel windows, no overlapping files)

| Window | Owns | Does not touch |
|---|---|---|
| T1 opinion identity | `src/labcairn/db/models.py`, a new migration, `src/labcairn/papers/replies.py`, the reply join and its witnesses | `material/ooxml.py`, version/edge code |
| T2 flag reader | `src/labcairn/material/ooxml.py`, the flag event type in the material module, its witnesses | the database models, reply code |
| T3 version alignment | `src/labcairn/application/papers.py` or the version-graph layer, its witnesses | T1/T2 files |
| T4 pilot + record | operator-side scripts (outside the repository), `docs/acceptance/LC-P2-28-*.md` | all `src/` and `tests/` |

T1 and T2 can run in parallel as separate worktrees; T3 needs T2's event
shape but can be specified before it lands. T4 is last.

## 2. Gates, in order

| Gate | What must be true | How it is known |
|---|---|---|
| G0 design | ADR-0020 accepted; the two negative witnesses remain green | `pytest tests/test_ooxml_revisions.py -k "red_font_is_not_a_revision or quoted_reviewer_paragraph_is_not_a_comment"` |
| G1 source types | `quoted_paragraph` and `docx_comment` are a closed enum; a quoted opinion carries source document, paragraph index, text hash; unknown author is a state, not a person | a witness that refuses a sixth state; a mutation that drops the paragraph index makes it red |
| G2 reply join | a reply names the opinion it answers; `settle_reply` can cite that address; a reply to no known opinion is refused | read-back witness + a mutation that lets an orphan reply settle |
| T2 flag | a colour run is `flagged_text`, never `ins`/`del`; clean files' stray red run is reported and not counted as a change | three-state negative witness (no revision / fake insertion / stray red run) |
| T3 alignment | marked + clean versions align; a flagged span has before/after text; no pair means no baseline and no invented text | a witness that refuses an unpaired flag |
| G3 mixed source | a letter whose points come from two papers is refused with a named reason | a witness over batch 9's mixed letter |
| G4 pilot | letters route through `replies`, flags route through the version graph, all on material outside the repository | a read-only pilot whose outputs are counts and hashes |
| G5 record | the acceptance record says what was measured, what was refused, and what remains NOT MEASURED | the record itself and the witness ledger over its commit |

## 3. What each window must not do

- **No product code change in T4.** The pilot drives the product's own
  doors; if a door is missing, T4 stops and reports it.
- **No answer text, no material words, no person names in the repository.**
  The material is unpublished and the repository is public; the CJK pin and
  the leak witnesses stay in force.
- **No widening of existing kinds.** A colour run is not an insertion; a
  quoted paragraph is not a Word comment. Two negative witnesses already
  hold these refusals and must stay green.
- **No distillation from batch 8's translation channel.** The owner ruled
  on 2026-11-05 that it is a language-rendering transform.
- **No new test file without three registrations**: the file's own
  `pytestmark`, `.github/ci-shards.json`, and
  `tests/evaluation/manifest.py`. A changed `src/` or `tests/` file may
  redden the shard-cost witness; costs must be re-measured from a runner,
  not guessed locally.

## 4. Acceptance clauses

1. A quoted opinion and a Word comment are distinguishable records, and the
   same words in two places are two records.
2. A reply names exactly one opinion; an orphan is refused.
3. A marked manuscript's red runs produce flagged text, not revisions; the
   clean file's stray red run is reported and not a change.
4. A flagged span's before/after text comes from the version pair, never
   from the marked file alone.
5. A mixed-source letter is refused with a reason that names both sources.
6. Batch 7 and batch 9 route end to end on a copy of the pilot store, with
   counts and hashes read back and no full ingestion of the real store until
   the owner approves the write.
7. No capability claim: this work order's number is source honesty, not a
   measured guidance gain.

## 5. What is explicitly not in scope

- Rating the reviewers, the authors or the science.
- Replacing the blind evaluation or changing its verdicts.
- Training, prompt optimisation, or a sixth gate.
- A new PR per window: the work lands locally, is reviewed and merged, and
  one delivery PR and one CI run cover the whole body of work.
