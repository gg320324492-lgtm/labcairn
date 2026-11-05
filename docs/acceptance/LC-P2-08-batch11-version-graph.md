# Batch 11 — the two-paper version graph (rehearsal and real-store write)

**What this record covers.** A supplied material batch of two small papers was
assembled in LC-P2-08's version-graph shape on a **rehearsal copy of the pilot
store**, checked by four witnesses and a mutation harness, and then written to
the **real pilot store** after the owner approved the measured counts in a
dialog. Two paper projects, 30 version rows and 28 unaccepted model-proposal
edges were written to the copy and then to the real store. Every tracked change
and every Word comment that the material holds was written through the
product's own door and reconciled against an independent count taken from the
material's bytes.

**The real pilot store was written on 2026-11-05.** Its sha256 changed from
`fe1905fd6f38c13f03fc72641257a5193fb23be022cdc7aeee19ae489312fb0f` to
`f85181efb8318980f747cadb5f4843b8bedd4651c96cfc32842fb7cad230526a`. The
rollback point is
`E:\labcairn-local\pilot-ws\labcairn.db.backup.before-batch11-graph-20261105T171744Z`,
a full SQLite backup taken before the run. The rehearsal copy is at
`E:\labcairn-local\batch11-graph\rehearsal.db`; the plan and the execution log
are `E:\labcairn-local\batch11-graph\write-plan.md` and
`E:\labcairn-local\batch11-graph\real-write.out`. The write plan's status is
**EXECUTED**.

**What this record does not carry.** The material's title, file names,
sentences, figure labels and names in revision metadata. The material and the
measured evidence live outside this repository under
`E:\labcairn-local\batch11-graph\`; the reconnaissance is under
`E:\labcairn-local\batch11-recon\`. This record holds counts, structural
findings, neutral ids and hashes only.

## 1. The material, as measured

- **109 files** in 24 directories: 88 `.docx` and 21 images (18 `.tif`, 2
  `.jpg`, 1 `.png`). Every file was copied under a neutral name,
  `batch11-<file id><suffix>`, and the mapping is held outside the
  repository.
- **1,479 insertions, 639 deletions, 12 `moveFrom` and 21 `moveTo`** across
  the 88 documents; **5 Word comments**, all of them in the first paper's
  draft chain (`F032` holds one, `F033` holds four). The second paper holds
  none, although its draft directory is labelled as holding a teacher's
  comments: a directory label is not a comment.
- 15,080 red runs and 2,073 yellow highlights are formatting. The material's
  marked state is **red font, not tracked changes**, and the store holds no
  revision row for a red run.
- 1,343 `rPrChange` and 5 `pPrChange` elements are **not** revision events:
  the product's reader counts `ins`, `del`, `moveFrom` and `moveTo`, and
  nothing else.
- The product's reader counts **exactly** the elements the material holds:
  818 / 272 / 7 / 16 for the first paper and 661 / 367 / 5 / 5 for the
  second, reconciled version by version.

### 1.1 The content key, and a correction to the reconnaissance

The content key is the **whitespace-normalised body**, hashed. Two renderings
of one body differ in line breaks and padding, so a key that counted
whitespace would call one body two. With the raw digest the pair
`F016`/`F017` comes out as two bodies; with the normalised key it is one.

The reconnaissance's per-directory table gives `D24` as 661 insertions and
367 deletions. `D24` is the second paper's ten-file draft chain and its own
files hold 365 insertions and 52 deletions; the remaining 296 insertions and
315 deletions are in `F069`, which the same table counts under `D17`. The
paper totals (661 / 367) are right; the `D24` row counts `D17`'s numbers a
second time. Measured per directory:

| Directory | docx | `ins` | `del` | `moveFrom` | `moveTo` |
|---|---:|---:|---:|---:|---:|
| `D09` (first paper's draft chain) | 10 | 818 | 272 | 7 | 16 |
| `D17` (second paper's minor revision) | 7 | 296 | 315 | 0 | 0 |
| `D24` (second paper's draft chain) | 10 | 365 | 52 | 5 | 5 |
| every other directory | 61 | 0 | 0 | 0 | 0 |

## 2. The graph

| | First paper | Second paper | Total |
|---|---:|---:|---:|
| version rows | 13 | 17 | 30 |
| version edges | 12 | 16 | 28 |
| unaccepted `model` edges | 12 | 16 | 28 |
| `revision_events` | 1,113 | 1,038 | 2,151 |
| — `ins` / `del` | 818 / 272 | 661 / 367 | 1,479 / 639 |
| — `moveFrom` / `moveTo` | 7 / 16 | 5 / 5 | 12 / 21 |
| `feedback_events` | 5 | 0 | 5 |
| material copies ingested | 40 | 69 | 109 |

The projects are `proj-batch11-p1` and `proj-batch11-p2`. Every edge uses
`source = model`, `confidence = 0.8`, `accepted_by = NULL` and
`accepted_at = NULL`: a file name is a proposal, not evidence of order, so
no edge was accepted and no confirmation operation was run. Every edge
carries evidence a reader can look at — the 7-gram Jaccard of the two
bodies it joins, computed from the material's bytes, and a statement of what
the order rests on.

The product's duplicate check, run per project over the version rows,
reports no group: no two versions share their bytes, no two share a label,
and every label declares a round, so none is reported as unlabelled. The
check is run per project because the two papers share label words and
comparing them across papers would report two different bodies as a name
collision.

### 2.1 The order, and where it is thin

The order comes from the reconnaissance's nominal order — "version orders
visible from directory and filename shapes" — read file by file inside each
directory: the ten-file draft chain, then the submitted main article, then
the revision rounds.

**Two seams of the first paper's chain are structural and not textual.** The
draft chain's last file and the submitted main article share 5.00% of their
7-grams; the submitted main article and the revision's working manuscript
share 6.01%. The submitted article is 7,945 characters and the revised
manuscript is 53,471: they are not two states of one manuscript, and the
material cannot trace the revision's claimed changes to the submitted
article. The second paper's seams are 27.39%, 72.25%, 98.65%, 80.16%,
92.90%, 73.29% and 43.41%.

**Two edges of the second paper's chain are branches, not a settled order.**
The reconnaissance's chain places the editorial round after the minor
revision and the english copy last, but it also records that the bytes do
not establish the editorial rounds' order relative to the minor revision and
to the english copy. Those edges say so in their evidence rather than
claiming an order nobody established.

### 2.2 One body is one version

Three groups of files hold one body between them. Each group is carried by
**one** version row; the other files of the group are sources and not
versions.

| Group | Carried by | The other files |
|---|---|---|
| `F016`, `F017`, `F024`, `F025` | `ver-batch11-p1-r1s` (`F016`) | `F017` (clean twin), `F024` and `F025` (the minor round) |
| `F050`, `F051` | `ver-batch11-p2-r1h` (`F050`) | `F051` (clean twin) |
| `F068`, `F070` | `ver-batch11-p2-r2m` (`F068`) | `F070` (clean twin) |

The minor round of the first paper re-issues the major revision's submitted
manuscript **unchanged**. The graph records one body and one version, and
the re-issue is recorded here rather than being papered over with a second
version row and a cosmetic edge.

## 3. Gaps, recorded as gaps

- **21 image files** were ingested as `kind = other` with
  `readability = unparseable`. They are recorded and hashed, no text is
  extracted from them, and the store's own disclosure says so: *"no adapter
  is registered for 'other'; the material is recorded and hashed, and no text
  is extracted from it. That is different from a material that was read and
  contained nothing."*
- **The two empty-text containers** (`F020`, `F047`) are sources. No version
  row names them, and they hold no text.
- **One file whose role is undecided** (`F027`) is ingested and **not placed
  on a version edge**: the reconnaissance leaves its role open, and a
  version edge is a claim about the manuscript's history.
- **Eight directories hold no manuscript body** (`D08`, `D14`, `D15`, `D18`,
  `D19`, `D20`, `D21`, `D22`) and so mint no version. Their files are
  ingested all the same.
- Nothing was parsed out of a file that could not be read, and no revision
  or comment row was fabricated for one.

## 4. Witnesses and mutations

Each claim has a witness that reads the store and the material's bytes
independently of the assembly script. Each witness was made to fail by a
mutation that breaks exactly that claim, applied to a copy of the store made
through SQLite's backup API. The original's digest was compared with the
digest taken before each case.

| Claim | Mutation | Witness exit | Failed checks | Original store |
|---|---|---:|---:|---|
| the graph is one connected chain | delete one edge of the second paper | 1 | 4 | unchanged |
| one body is one version | point a second version at the same body | 1 | 2 | unchanged |
| an empty container mints no manuscript | point a version at the empty container | 1 | 1 | unchanged |
| the stored changes are the material's | delete one stored comment | 1 | 1 | unchanged |

The first attempt at the second mutation **survived**, and the reason is
worth recording: it moved a body's carrier from one file of a group to
another file of the same group, which leaves one body with one version — the
claim still holds. The mutation was rewritten to make two versions hold one
body, which is what the claim forbids. All four witnesses pass on the
assembled copy.

## 5. What this rehearsal does not establish

- **No version order is settled.** Every edge is a model proposal and none
  is accepted.
- **The first paper's revision cannot be traced to its submitted article.**
- **The draft chain is not connected to the submitted article by content.**
- **No party is established.** The five comments carry the shape of a
  person's mark, and the material does not say who wrote them, so the rows
  carry no party and no issue key: an issue key is a person's judgement and
  nobody has given one.
- **The batch supports no chain settlement.** There is no judgement or
  assessment row in the material.

## 6. The approved real-store run

The owner approved the measured counts in a dialog on 2026-11-05. The run
wrote 30 version rows, 28 unaccepted model-proposal edges, 2 projects,
2 access grants, 109 ingested material copies, 2,151 revision events and
5 feedback events, after taking the SQLite backup named in the opening as
the rollback point.

The run's first invocation used the machine's Python 3.10 and stopped at
`ImportError: cannot import name 'UTC' from 'datetime'` before any write;
the store's digest, row counts, material-copy count and backup count were
unchanged. The second invocation used the project's Python 3.12.13 and
completed with exit code 0. Both execution flags were present, and the
owner's approval phrase was passed as `--owner-approved`.

A table-by-table comparison against the backup found **no deleted rows** in
any table. The one existing `tasks` row gained 109 `bound_source_ids` (87
before, 196 after, none removed) and advanced its event sequence and update
time; its task id, title, objective, criterion, revision, creation time and
schema version did not change. `PRAGMA integrity_check` returned `ok` on
both the store and the backup, and `PRAGMA foreign_key_check` returned no
rows. All four read-only witnesses were rerun against the real store and
passed. The mutation harness was not pointed at the real store.

The id list, the two gates and the rollback procedure are in
`E:\labcairn-local\batch11-graph\write-plan.md`, whose status is
**EXECUTED**. The owner's approval settled two of the rehearsal's four
open questions: the two papers became projects in the real store, and the
text-identical re-issue received no separate version row. `F027`'s role and
the editorial rounds' order remain open; every edge is still an unaccepted
model proposal.
