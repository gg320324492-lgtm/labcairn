# LC-P4-PILOT — taking the stale source back

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Date:** 2026-11-26 (the removal run), recorded 2026-11-26.
**Tree:** `64f1bb7e4a15e8ca72180864ea1067cadc6ce340` (worktree
`agitated-snyder-e39ca5`, branch `claude/agitated-snyder-e39ca5`), Windows 11
Pro (10.0.26300 x64, AMD64), Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Material id:** `pilot-paper-002`.
**Workspace:** `E:/labcairn-local/pilot-ws`, task
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1`, paper project `proj-pilot-002`.

**What is claimed here.** The product's own removal command took the stale
row out of the pilot ledger and left everything else alone: the row that
named the path which is no longer there is gone, the row that names the path
where the material now sits is untouched, and the extracted text and the
version resting on that text still resolve. Both refusals the command
promises were refused rather than acted on, and neither refusal changed the
store. **What is not claimed:** that the pilot's step 3 has run — the record
of the request is
[`LC-P4-PILOT-real-request-2026-11-25.md`](LC-P4-PILOT-real-request-2026-11-25.md),
§8, and this record does not stand in for it. This record also does not
claim the removal is the only way a row can be wrong: §9 records what the
run did **not** cover.

**The boundary this record obeys.** Ids, digests, counts and paths. No
sentence of the manuscript, no sentence of the advisor's marks, no key
(`LC-P4-PILOT-model-authorisation-draft.md` §8; G0 §4). The addresses the
product's reading face returns carry text; this record counts them and
does not quote them.

## 1. The state before

The pilot's copy was imported, then **moved** and imported again — the
grant's scope is a root-relative coordinate, so the copy has to sit at
`materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` for
its key to fall inside the grant. A source's identity is its location, so
the moved file became a *second* source rather than a moved one, and the
first import left a row behind that names a path which is not there any
more. The import record says so and left it alone
([`LC-P4-PILOT-import-2026-11-25.md`](LC-P4-PILOT-import-2026-11-25.md) §6).

Measured read-only on `E:/labcairn-local/pilot-ws` before the removal:

| source id | path | digest | bytes | ingested (UTC) |
| --- | --- | --- | --- | --- |
| `src-0738f31ecf1e750b` | `materials/pilot-paper-002/pilot-paper-002.docx` | `04cc31be…a6172d` | 8,805,237 | 2026-11-25T12:50:25Z |
| `src-0ac499ea4d3a7d82` | `materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` | `04cc31be…a6172d` | 8,805,237 | 2026-11-25T18:28:26Z |

One digest, two rows. The full digest is
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`; the
table shortens it and §2 gives the whole of it.

**The stale row named a path that was not on the disk.** Listed before the
removal: `materials/pilot-paper-002/` does not exist under the workspace,
and the path the material now sits at holds a file of 8,805,237 bytes. The
row was stale in the literal sense, not only in the sense of the ledger.

The store held **198** source rows; 196 of them were unrelated to the
pilot material and were not touched by anything below.

## 2. The command

Read first, from the command's own help
(`labcairn sources remove --help`): the row goes and the evidence stays,
because the extracted text and the addresses into it are keyed by the
content hash; a manuscript's version that named the material follows the
bytes to the row that holds them; where the material is nowhere else in
the ledger the removal is refused rather than take a version's row with it;
and a source the ledger does not hold is refused.

The removal was run from the worktree, through the installed console
script, against the pilot workspace:

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources remove \
  --source src-0738f31ecf1e750b --json
```

Exit code **0**. The command's own report:

```json
{"source_id":"src-0738f31ecf1e750b",
 "relative_path":"materials/pilot-paper-002/pilot-paper-002.docx",
 "content_sha256":"04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d",
 "released_task_ids":["01a212be-ddd1-7c9a-aaad-c1db083b8bc1"],
 "removed_problem_count":0,
 "repointed_version_ids":["ver-pilot-002-input"],
 "repointed_to_source_id":"src-0ac499ea4d3a7d82"}
```

## 3. What the removal did

**The row that went:** `src-0738f31ecf1e750b`, the one naming
`materials/pilot-paper-002/pilot-paper-002.docx`.

**The rows that stayed:** `src-0ac499ea4d3a7d82`, the one naming
`materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` — and
the other 196 rows of the store. Read back through the product's own
reading face afterwards, the survivor still answers with its digest, its
size and the coordinate the grant's scope is matched against:

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources inspect \
  --source src-0ac499ea4d3a7d82 --json
```

→ `source_id src-0ac499ea4d3a7d82`, `relative_path
materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`,
`content_sha256 04cc31be…a6172d`, `size_bytes 8805237`, `resource_key
pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`.

**The removed id answers as removed, not as absent:** `sources inspect
--source src-0738f31ecf1e750b` exits **3** with
`source_not_found`, and so does `sources addresses --source
src-0738f31ecf1e750b`.

**The task let the material go.** Task `01a212be-ddd1-7c9a-aaad-c1db083b8bc1`
held the stale id; its binding went from **198** source ids to **197**. The
other task in the workspace, `01a18ff1-eb04-770d-acaa-3ffe59e17a60`, held
196 ids and did not hold the stale one, and its binding did not move.

**No disclosure went with the row.** `removed_problem_count` is **0**,
which agrees with the store: the stale row carried no disclosures of its
own, and the material's disclosures are counted per source row (the whole
digest accounts for 0).

## 4. The counts before and after

Counted on the store itself, read-only, before the removal and again after
it; the *before* column was read back from a copy of the database taken
immediately before the command ran (§8).

| table | before | after | |
| --- | --- | --- | --- |
| `sources` | 198 | 197 | the stale row left |
| `source_texts` | 76577 | 76577 | unchanged |
| `source_anchors` | 2 | 2 | unchanged |
| `source_problems` | 113 | 113 | unchanged |
| `paper_versions` | 106 | 106 | unchanged |
| `paper_projects` | 10 | 10 | unchanged |
| `tasks` | 2 | 2 | unchanged |
| `evidence_records` | 2 | 2 | unchanged |
| `evidence_anchors` | 3 | 3 | unchanged |
| `events` | 10288 | 10289 | the task's revision (§7) |

Set differences, not only counts: **one** source id is gone from
`sources` (`src-0738f31ecf1e750b`) and none was added; **zero** rows of
`source_texts`, `source_anchors` and `source_problems` were lost or
added; **no** paper version was lost or added; **one** version changed the
row it names; and **no** version changed the digest it records.

## 5. The evidence stays

**The extracted text stayed.** The 268 rows of `source_texts` for the
material's digest were 268 rows before the removal and are 268 rows after
it, and the set of their primary keys is unchanged — none lost, none
added. That table holds `source_content_sha256` and no source id at all, so
the two rows the store had for one digest were always sharing one body of
text.

**The addresses still resolve.** Through the product's own reading face,
the survivor still lists the material's addresses:

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources addresses \
  --source src-0ac499ea4d3a7d82 --json
```

→ **268** addresses, every one of them carrying
`source_id src-0ac499ea4d3a7d82`, one locator kind (`docx`). The count is
the count of the text rows above: the addresses are a view over the
digest's text, and they are still there after the row that used to name
the other location was taken back.

**The version followed the bytes.** `ver-pilot-002-input` (project
`proj-pilot-002`) was recorded against the stale row. After the removal it
names `src-0ac499ea4d3a7d82`, and the digest it records is unchanged —
`versions whose digest changed: []`. A version is the set of bytes it was
made from, and the bytes are still in the ledger under the other row.

## 6. The refusals

Both refusals are facts of this run: the command refused, exited **3**, and
neither changed anything in the store.

**A source the ledger does not hold.**

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources remove \
  --source src-0000000000000000 --json
```

→ exit **3**, `{"reason":"source_not_found","message":"application refused
(source_not_found): the ledger holds no source with the id
'src-0000000000000000'."}`. The rendered form says the same in two lines.

**A version whose material is nowhere else in the ledger.** The store
holds such a row: `src-7d2879abf550de62`
(`materials/v03-copy-chinese-draft.docx`), whose digest
`dd7e1aaa…9dcce` appears on **one** source row and nowhere else in the
ledger, and which the version `ver-pilot-v03-copy` names.

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources remove \
  --source src-7d2879abf550de62 --json
```

→ exit **3**, `{"reason":"paper_contract_refused", …}`: *"the paper version
'ver-pilot-v03-copy' was recorded against the material
'src-7d2879abf550de62', and a version with no file is not a version: the
material's bytes are nowhere else in the ledger, so taking the material
back would take that version's row with it. The material stays in the
ledger until the version does."* The rendered form says the same.

**Nothing moved.** Counted again after both refusals, the store was the
same as it was after the removal: `sources` 197, `source_texts` 76577,
`source_anchors` 2, `source_problems` 113, `paper_versions` 106,
`evidence_records` 2, `evidence_anchors` 3, `events` 10289. The refused
row is still there with its path, its version `ver-pilot-v03-copy` still
names it, and its own 11 disclosures and 2,695 text rows are still there.
The refusals wrote no event either.

## 7. The event log

The removal wrote **one** event: `task_revised` (seq 57) for task
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1`, at 2026-11-26T11:33:17Z.

**The removal of the row itself is not in the log.** The event vocabulary
has `source_changed` (`src/labcairn/runtime/event.py:76`, used by the
recovery path at `src/labcairn/recovery/resume.py:378`), and
`remove_source` writes no event of that kind — it writes the task's
revision and nothing else. The `task_revised` event's `transition` is
`null` and its `payload` is `{}`, so it records *that* the task was
revised and not *which* source was released. **A reader of the event log
alone cannot tell that a source was taken back.** §9 keeps this as an
observation about the ledger's provenance, not as a claim that the removal
was wrong.

**Five events in the same window are not the removal's.** The store's
`events` count went from 10289 to 10294 while this record was being
written, and the five new events are not the removal's: they carry the run
id `01a213fd-c394-7121-9a80-d77492e09bc9` of a run started on 2026-11-25
and still marked `running`, a stage named `inventory`, and an operation
with capability `source.inventory` whose `resource_key` is
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` — the
**survivor's** coordinate. The removal's own context carries a task and
no run, and `remove_source` writes no stage, no operation and no run.
Those five events belong to the pilot request that is still open; they are
counted here so that the next reader is not surprised by them, and they
are the reason this record gives the event count as 10289 rather than
10294.

## 8. What was kept, and how it was measured

**The store was not hand-edited.** Every change in §3 and §6 was made by
`labcairn sources remove` and nothing else. The counts were read with
read-only SQLite connections (`file:…?mode=ro`).

**A copy of the database was taken before the command ran**, and the
*before* column of §4 is read back from it rather than remembered:
`E:/labcairn-local/tmp/labcairn.db.backup.before-source-removal-2026-11-26`
(93,822,976 bytes). It is outside the repository, and it is a copy of a
workspace that holds real material.

**The reading face was used where it exists.** The survivor's row, the
removed id's absence, the addresses and both refusals were all read
through `labcairn`, not through the store's tables alone.

**The command was run from this worktree**, whose `uv run` built its own
environment, so the code that ran is the code in the tree this record was
written on (`64f1bb7`).

## 9. What this run did not cover, and what looked wrong

Stated plainly, because the value of this record is that it says what
happened.

1. **The removal leaves no trace of itself in the event log** (§7). The
   ledger has an event type for a source changing and the removal does not
   use it; the one event it writes (`task_revised`) has an empty payload,
   so it does not name the source that was released either. A source
   that leaves the ledger and a task that is revised are not the same
   thing, and only the second is in the log.

2. **"The addresses stay" was not exercised on a source that held
   addresses.** The material this removal took back holds **no** row in
   `source_anchors` and no row in `evidence_records` — the addresses the
   reading face returns for it are the 268 rows of `source_texts`, and
   those stayed. The claim is therefore measured for the extracted text
   and for the version, and **not** instantiated for the `source_anchors`
   table or for an evidence record. The schema explains why the text
   could not have gone: `source_texts` has `source_content_sha256` and no
   source id, and `source_texts`, `source_anchors`, `source_problems` and
   `sources` carry **no foreign keys** at all (read from the live
   database's `pragma foreign_key_list`). The one table that does have
   one, `paper_versions.source_id`, is `ON DELETE CASCADE` — which is why
   the version is re-pointed before the row is deleted, and why the
   refusal in §6 exists at all.

3. **A source id in `source_anchors` has nothing keeping it honest.**
   `source_anchors.source_id` is a plain column with an index and no
   foreign key. If a row that held addresses were taken back, the address
   rows would stay and their `source_id` would name a source the ledger
   does not hold. Nothing in this run had that shape, so nothing in this
   run shows what happens — the path is untested here, and it is
   reported as untested rather than as safe.

4. **The two refusals left no trace either.** Neither wrote an event and
   neither changed a row (§6). That is the right behaviour for a refusal
   that comes before any effect, and it is also the reason an operator
   who runs a refused removal has nothing in the log to show that it was
   attempted.

5. **The command's `--task` option does not narrow what the removal
   releases.** The CLI takes `--task`, and the release goes to every task
   that held the material — the application layer says so on purpose
   (`_release_the_bindings`, `src/labcairn/application/material_ingestion.py`),
   and this run could not distinguish the two because the stale id was
   held by one task only.

6. **Nothing about the removal was wrong in the sense of acting where it
   should not have.** The stale row went; every other row stayed; the
   text stayed; the version followed the bytes to the row that holds
   them; the two refusals refused and changed nothing. The observations
   above are about what the removal *does not record* and what it did not
   *exercise*, not about what it did to the ledger.

## 10. Evidence

| # | what | how | result |
| --- | --- | --- | --- |
| E1 | the command's own contract | `labcairn sources remove --help` | the four claims of §2 read from the help |
| E2 | the state before | read-only SQLite on `E:/labcairn-local/pilot-ws` | 198 source rows; the two rows of §1; the old path absent from the disk |
| E3 | the removal | `labcairn … sources remove --source src-0738f31ecf1e750b --json` | exit 0; the report of §2 |
| E4 | the counts | read-only SQLite before and after, the *before* read back from the copy of §8 | the table of §4 |
| E5 | what stayed | `sources inspect --source src-0ac499ea4d3a7d82 --json`; `sources inspect --source src-0738f31ecf1e750b --json` | the survivor answers; the removed id is `source_not_found` (exit 3) |
| E6 | the text stayed | `source_texts` row count and primary-key set, before and after | 268 rows for the digest, 0 lost, 0 added |
| E7 | the addresses still resolve | `sources addresses --source src-0ac499ea4d3a7d82 --json` | 268 addresses, all naming the survivor |
| E8 | the version followed the bytes | `paper_versions` before and after | `ver-pilot-002-input`: `src-0738f31ecf1e750b` → `src-0ac499ea4d3a7d82`; no version changed its digest |
| E9 | the task let the material go | `tasks.bound_source_ids` before and after | 198 → 197 for `01a212be…`; 196 unchanged for `01a18ff1…` |
| E10 | refusal: no such source | `labcairn … sources remove --source src-0000000000000000 --json` | exit 3, `source_not_found` |
| E11 | refusal: version with no other row | `labcairn … sources remove --source src-7d2879abf550de62 --json` | exit 3, `paper_contract_refused` |
| E12 | the refusals changed nothing | read-only SQLite after both | every count as after the removal; the refused row, its version, its 11 disclosures and 2,695 text rows still there |
| E13 | the event log | read-only SQLite on `events` | one `task_revised` from the removal (§7) |
| E14 | the schema | `pragma foreign_key_list` on the live database | `paper_versions.source_id → sources.source_id ON DELETE CASCADE`; no foreign keys on `sources`, `source_texts`, `source_anchors`, `source_problems` |

## 11. What this record is not

It is not a claim that the pilot's request has run (§0), it is not a claim
that the removal is a full provenance record (§7, §9.1), and it is not a
claim about the paths §9.2 and §9.3 leave untested. It is a record of one
run of one command against the pilot workspace on 2026-11-26, and the
counts in it were measured on that store at that time.
