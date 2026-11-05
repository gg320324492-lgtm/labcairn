# Batch 8 — one paper's draft chain becomes a version graph

**What this record covers.** A new material batch was assembled into the
pilot store as a **version graph** (LC-P2-08's shape): nine supplied files,
one paper, a seven-step draft chain, and the revision events the reader can
read from the one file that carries tracked changes. **No rule was
distilled** from it; §4 says why, and the owner's decisions are §3.

**What this record does not carry.** The paper's title, its file names, its
sentences, and the names of the people in the revision metadata. The
material is called **batch 8** and lives outside this repository, at
`E:\labcairn-local\intake-paper1-20261105`; the reconnaissance that measured
it is `E:\labcairn-local\batch8-recon\RECON.md`.

## 1. The material, as measured

- **9 `.docx`, 8 unique texts** — two files are the same text (5 and 6); the
  others differ at 53–90% of their 7-gram shingles, so the chain is a series
  of rewrites, not small edits.
- The chain runs **draft 4 → 5 → 6 → 7 → 8 → 9 → 9(revised) → 10 → 10
  (translation)**. Draft 4 carries **35 insertions** by two authors (23 and
  12); the translation carries **1,108 insertions and 1,146 deletions** by
  one author in a single day. **No Word comments anywhere.**
- The material is English-dominant with Chinese abstract/keyword material;
  the translation pass's deletions are 49.8% CJK against insertions at 0.03%
  — it is a rendering pass, not an academic revision.

## 2. What was written

| Operation | Rows |
|---|---|
| project | `paper_projects` +1 (`proj-batch8-paper1`) |
| versions | `paper_versions` +9 (5 and 6 carry the same content hash) |
| edges | `version_edges` +7, **all accepted by the owner** (`accepted_by = owner`) |
| revision events | `revision_events` +2,289 — 1,143 insertions, 1,146 deletions |
| sources | `sources` +9; the reader's text rows +3,848 |
| the run's own bookkeeping | grants, approvals, runs, stages, operations, audit events |

The seven edges are **filename-order hypotheses**, not content evidence:
`source = model`, confidence 0.8, and the owner accepted them as the
chain's reading on 2026-11-05. A correction would write a second edge and
leave the proposal readable; nothing here was corrected.

**The rehearsal first.** The whole assembly was run on a copy of the store
(`E:\labcairn-local\batch8-graph\rehearsal.db`), where three witnesses were
green and eight mutations were each made red; the copy's bytes were
unchanged by the mutation pass. The rehearsal's shape (9 versions, 7 edges,
2,289 events) matched the real write's.

**The real write.** Owner-approved on 2026-11-05, with the operator script's
two doors (`--execute-on-real-store --owner-approved`). A rollback point was
written before the store was opened:
`E:\labcairn-local\pilot-ws\labcairn.db.backup.before-batch8-20261105T091830Z`.
The store's sha256 moved from `2e833fbaaad08954…` to `c0256fd3f551caf…`.

## 3. The owner's decisions

- **The advisor is one of the two revision authors.** The owner stated which
  one, outside this repository; the record does not carry the name.
- **The translation pass is not a distillation source.** It is a rendering
  transform; a rule distilled from it would teach translation wording, not
  the paper's questions, methods or claims.
- **All seven filename-order edges are accepted** as the chain's reading.
- **The real store is written** (this record) — the copy-first rule held.

## 4. Distillation: none, and why

The distil path was walked and **not** used to mint a rule. Four measured
reasons:

1. The only rich revision channel is the translation: 80 of the 90
   paragraphs that change both ways delete Chinese and insert no Chinese at
   all. It is language rendering, not academic revision.
2. The revision author of that pass is not the advisor — the owner named the
   other author as the advisor — so a rule's case would carry an actor the
   material does not support.
3. `distil_candidate_from_revisions` records `operator_proposal`, which the
   product's own text reserves for a person reading a mentor's changes; this
   run is an agent's, and minting here would make the record claim a person
   did something no person did.
4. 747 of the 2,254 translation changes carry empty text, and three more
   have no paragraph; a rule built from them would often have only a
   paragraph for its scope.

**The source is live, though.** All 2,289 events resolve through
`read_revision_sources` to a product-minted key; the 15-case sample resolved
15/15 with the right version and kind. The channel is readable and linked;
it is only the *rule* that was not minted.

## 5. What this does not claim

- No rule, no counterexample, no guidance-memory change.
- The edges are the owner's accepted reading of the filenames, not proof
  that draft *n* was made from draft *n-1*.
- The translation remains readable as material; it is simply not a
  distillation source under the owner's decision.
