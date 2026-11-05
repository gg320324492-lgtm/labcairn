# Batch 10 — the eight-directory version graph rehearsal

**What this record covers.** A supplied material batch was assembled on a
**rehearsal copy of the pilot store** in LC-P2-08's version-graph shape. Eight
numbered version directories became eight version rows and seven unaccepted
model-proposal edges. One paper project, 18 inventoried sources, 17 disclosed
reader refusals and 49 addressable text rows were written. No revision or
feedback event was fabricated, and no rule was distilled. **The real pilot
store was not written.**

**What this record does not carry.** The material's title, file names,
sentences, figure labels and names in revision metadata. The material and the
measured evidence live outside this repository under
`E:\labcairn-local\batch10-graph\`; the reconnaissance is under
`E:\labcairn-local\batch10-recon\`. This record holds counts, structural
findings and hashes only.

## 1. The material, as measured

- **184 files / 1,039,128,589 bytes** in eight numbered version directories.
  All 184 SHA-256 values are distinct; 14 basenames recur with different
  bytes. 18 files are text-bearing (17 OLE2 `.doc` and one `.docx`); the other
  166 are auxiliary assets: 128 images, 17 Origin projects, 18 slide decks and
  3 PDFs. Auxiliary assets were inventoried outside the repository only and
  became no source, version or edge.
- One representative main document per directory became a version row. The
  first directory holds at least three textual branches, so the eight rows
  represent eight numbered slots rather than eight settled manuscript bodies.
  Five named marked counterparts, one discussion segment, three other early
  branches and a short `.docx` note were not made into numbered chain
  versions.
- **7 edges** were proposed from the directory ordinals, `d1 -> d2 -> ... -> d8`.
  Every edge uses `source = model`, `confidence = 0.8`, `accepted_by = NULL`
  and `accepted_at = NULL`. A name is not evidence of authorship order, so no
  edge is human-confirmed and no confirmation operation was run.
- The product's duplicate check reports no same-byte, same-label or
  unlabelled group among the eight version rows. The 14 repeated basenames are
  a negative witness that a repeated name is not a repeated byte string.

## 2. The copy and the gate

The rehearsal store was made from the real pilot store through SQLite's
`backup` API with the source opened `mode=ro`; the copy's WAL was settled and
every table's row count and the alembic revision matched. The real store's
sha256 remained
`1d0898786cac7dabbb8c7b801bee4a392c2026f7fa4b8ad2ebc3ac6aeab1a000`
(68,513,792 bytes) before and after the run. The assembled copy is
`96079bcd0ff4a09c9751bdb257bff98feac5cece7bf0449051a48a1c124a3cef`
(68,829,184 bytes), alembic `0023`, `integrity_check = ok`.

The real-store path has two doors: `--execute-on-real-store` and a non-empty
`--owner-approved`, with `--ws` naming the real workspace. Three refusal
paths were probed (missing both flags, missing the approval phrase, and both
flags with the wrong workspace); each stopped before opening a store. **The
gate was not opened.** The real store holds zero rows for the batch-10
project, version, edge, grant and source ids.

## 3. What the copy holds

| Operation | Rows |
|---|---:|
| project | +1 |
| consent grant | +1 |
| versions | +8 |
| model proposal edges | +7 |
| sources | +18 |
| source problems (`no_adapter_for_kind`) | +17 |
| addressable source texts | +49 |
| revision events | +0 |
| feedback events | +0 |
| runs / stages / operations / approvals | +34 each |
| events | +205 |
| every other table | +0 |

Each version's content hash is rebuilt by `record_version` from the ingestion
ledger's own hash, so the bytes are confirmed even when no text adapter
exists. The chain witness independently hashes all eight main-document copies
and compares them to the stored rows.

The 17 OLE2 `.doc` files have no product adapter. Ingestion reports 17
`unparseable` sources, each with a disclosure and a refusal problem, and
zero addressable text rows for them. The one `.docx` is readable and supplies
the 49 text rows. External conversion probes can produce plain text for all
18 text-bearing files, but that text loses tables, figures, formatting and
revision attribution; it was not treated as a faithful product read.

## 4. Revisions and comments, measured separately

| Measurement | Count | Stored events |
|---|---:|---:|
| COM-visible OLE2 tracked revisions | 286 | 0 |
| insert / delete / property / paragraph-number types | 146 / 100 / 33 / 7 | 0 |
| revisions in the five named marked pairs | 277 | 0 |
| anonymous revision author keys | 2 | not role labels |
| COM-visible comments in the 17 OLE2 files | 0 | 0 |
| Word comments in the one `.docx` note | 2 | 0 |
| native `.docx` insertions / deletions | 0 / 0 | 0 |

Read-only conversion probes measured 13/17 antiword successes and 4/17
refusals; a Word-compatible COM object model opened 17/17. The five named
marked pairs all carry zero Word comments and one carries zero tracked
revisions. The product's OOXML reader independently finds 2 comments with
resolved anchors, 47 paragraphs and 0 revisions in the `.docx` note. The note
is not one of the eight numbered main-document versions, so no feedback event
was attached to this graph. COM event counts and converted OOXML element
counts are different granularities and were not equated. No author role,
advisor/student mapping, comment-to-issue mapping or rule distillation is
claimed.

## 5. Witnesses and mutations

Five witnesses watch the eight-version chain and its unsettled edges, the
duplicate/negative-byte report and auxiliary-asset inventory, the 17
`unparseable` disclosures, the 286 measured OLE2 revisions with zero stored
events, and the comment counts with zero stored feedback events. All five pass
against the assembled copy. They read stored state, the product's `EdgeSource`
and `check_duplicates`, the product's OOXML reader, and four sanitized
chain-external JSON files; those four files contain zero material words.

19 effective mutations were applied one at a time to byte copies of the
assembled store or to the external measurements. Each reported exactly one
changed row or file, made its target witness exit non-zero with a failed
assertion, and had its case copy and all four external files restored by
bytes with SHA-256 checks. The assembled store's hash was unchanged before
and after; the five witnesses passed again afterward. Machine-readable
results are in `mutation-results.json` under the chain-external workspace.
No whole-suite pytest run was started.

## 6. Status and limits

This is a **rehearsal**: the write plan is `NOT EXECUTED`, no owner approval
was supplied, no push or CI run was started, no pull request was opened and no
product code was changed. The seven edges still need human confirmation. A
decision is still needed on whether marked counterparts are separate versions
or annotation layers, and on whether an OLE2 reader with revision and anchor
fidelity is to be built. Until then, the 17 `.doc` bodies remain disclosed as
unparsed and the 286 tracked revisions remain external measurements rather
than addressed chain events.
