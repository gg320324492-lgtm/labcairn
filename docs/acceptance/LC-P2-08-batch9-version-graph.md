# Batch 9 — the water manuscript's 3 → 5 version graph rehearsal

**What this record covers.** A supplied paper's draft chain was assembled on a
**rehearsal copy of the pilot store**, in LC-P2-08's version-graph shape. Four
files were inventoried: one old-format `.doc`, two byte-identical `.docx`
drafts, and one marked-up `.docx`. Three version rows, one unaccepted model
edge, 345 revision events and five feedback events were written. The old
format yielded no parse and no fabricated version. The real pilot store was
not written, and no rule was distilled.

**What this record does not carry.** The paper's title, its file names, its
sentences, and the names in its revision metadata. The material lives outside
this repository; the measured counts, hashes and gaps are in the chain-external
`RESULTS.md` and `write-plan.md` under `E:\labcairn-local\batch9-version`.
This record carries counts only.

## 1. The material, as measured

- **Four manuscript files, three unique byte strings.** Drafts 3 and 4 are
  byte-identical (`90591ae6…`, 2,607,531 bytes each). Draft 5 is distinct
  (`670defdb…`, 2,607,854 bytes). The old-format draft 2 is 4,718,592 bytes.
- Drafts 3 and 4 carry **no tracked changes and no comments**. Draft 5
  carries **237 insertions, 108 deletions and five Word comments**. An
  independent XML walk and the product's OOXML reader agree on all three
  numbers, their text totals, and the five complete comment ranges.
- The old-format file has an OLE2 header and no registered adapter. The
  ledger records it as `unparseable` with a disclosure, zero text rows and
  zero version rows. Its earlier place in the chain is **not** asserted.
- 73 of the 345 revision events carry no text; all 345 name a paragraph.
  All five comments have resolved anchors whose stored hashes match the
  anchored passages and bodies.

## 2. The copy and the gate

The rehearsal store was made from the real pilot store through SQLite's
backup API, with the real store opened `mode=ro`. Before any writes, the
copy's alembic revision (`0023`) and every table's row count equalled the
source's. The real store's sha256 was
`c0256fd37f551cafceb984ae7a453e7e22b74f8e7b1248f693476cb2cf607c17`
when the copy was made and when the rehearsal ended; it holds zero rows for
the batch-9 project. The final assembled copy measures
`08b6202382510777ddccbbc12e355be9588057371fc5d0343fde045f85cec712` and
`integrity_check = ok`.

Prepare, assemble, witnesses and mutations each used their own outside-the-
repository temp directory, with `TEMP`, `TMP`, `TMPDIR` and `MPLCONFIGDIR`
isolated. The worktree's `src` was the `PYTHONPATH` for every product import.
The real-store command has two doors: `--execute-on-real-store` and
`--owner-approved`, plus `--ws` naming the pilot workspace. Three refusals
were probed with the real workspace; all exited before a write and the real
store's hash did not move. **The doors were not opened.**

## 3. What the rehearsal wrote

| Operation | Rows |
|---|---|
| project | `paper_projects` +1 (`proj-batch9-water`) |
| consent | `access_grants` +1 |
| sources | `sources` +4, `source_texts` +1,276 (three readable DOCX files; zero from the OLE2 file; the identical pair shares one set of 455 text rows) |
| versions | `paper_versions` +3 (`ver-batch9-water-v03`, `-v04`, `-v05`) |
| edges | `version_edges` +1 (`model`, confidence `0.8`, unaccepted) |
| revision events | `revision_events` +345 — 237 `ins`, 108 `del`, all on draft 5 |
| feedback events | `feedback_events` +5 — all resolved, all on draft 5 |
| run bookkeeping | `approvals`, `runs`, `operations`, `stages` +11 each; `events` +72 |
| not written | `guidance_rules`, `guidance_rule_sources`, response links, settlements |

Draft 3 and draft 4 are two labels over **one document**. The product's
`check_duplicates` reports exactly that same-bytes/different-label pair; there
is no `v03 → v04` edge. Three version rows are an inventory of supplied files,
not a claim of three distinct texts. The one `v03 → v05` edge is read from
the supplied ordinals and is therefore a **model proposal**, not evidence and
not a decision: every version stays `unresolved`, and the edge has no
acceptor. The labels are ASCII operator labels, not material words.

## 4. The witnesses and their mutations

Four read-only witnesses, one per claimed property, all exited 0 against the
pristine copy:

| Witness | Property |
|---|---|
| `witness_chain.py` | the 3 → 5 edge is connected, uses the `model` enum, is unaccepted, and every version names its file's bytes |
| `witness_duplicates.py` | the identical pair is reported by the product, has no revision edge, and the unparseable file has no version |
| `witness_revisions.py` | 345 stored rows equal a second reader pass, and an independent XML walk agrees on 237/108 and their text totals |
| `witness_comments.py` | five stored rows equal a second reader pass, with matching body/anchor hashes and five OOXML comment ranges |

Eleven mutations were applied to **byte copies** of the assembled store:
delete, reverse and accept the edge; change the identical hash and add an
identical-bytes edge; delete, reclassify and alter a revision; delete and
alter a comment; and turn a resolved comment passage into a position anchor.
Every mutation changed exactly one row, every corresponding witness emitted
its own `WITNESS FAILED` assertion and exited non-zero, and every mutated
copy was restored byte-for-byte from the untouched assembled store and
verified by sha256 before removal. The assembled store's hash was identical
before and after. No whole pytest suite was run; another session was using
the machine. The case-by-case measurements are in `mutation-results.json`
outside the repository.

## 5. Gaps and the next decision

- The old-format draft 2 was not parsed; no text, revision, comment, version
  or edge was invented for it.
- Revision rows state *what* changed, not *why*; comments and revisions are
  not linked into a response or judgement chain.
- A filename ordinal proposes an order and does not settle it. No external
  model was called, no rule was distilled, and no acceptance was claimed.
- The extracted text and event bodies live in the copy's database, outside
  this repository. Approval to hold those bytes in the real pilot store is
  the owner's decision.
- The real-store checklist, exact row counts, rollback point and double-gate
  command are in `write-plan.md`. Until the owner opens both doors, the real
  pilot store stays unwritten; no push and no pull request were made.
