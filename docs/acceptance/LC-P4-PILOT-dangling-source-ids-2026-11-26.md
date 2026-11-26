# LC-P4-PILOT — a dangling source id, read back through every face

**Ticket:** LC-P4-PILOT (the source-removal's own reading faces)
**Date:** 2026-11-26 (the reading, 17:28–17:43 UTC), recorded 2026-11-27.
**Tree:** `124e843542b047c40712ddb01dd35642d0ce5f33` (worktree
`determined-mayer-ac3f06`, branch `claude/determined-mayer-ac3f06`), Windows 11
Pro (10.0.26300 x64, AMD64), Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Material:** **none of the pilot's was read.** A synthetic material of this
reading's own (a CSV with one header row and one data row, 33 bytes) was
written into a scratch workspace under the registered temp area
`E:/labcairn-local/tmp/`, so that the shape the record describes — a source
holding addresses, taken back — is built from the product's own commands and
nothing under the local material area is opened. No document text, digest of
a document, or key of the pilot appears in this record.
**Workspace:** a scratch directory of this reading's own, under
`E:/labcairn-local/tmp/`; its database is a scratch database the reading took
a source row back out of. No row of the pilot's ledger
(`E:/labcairn-local/pilot-ws`) was read or written.

**Origin record:**
[`LC-P4-PILOT-source-removal-2026-11-26.md`](LC-P4-PILOT-source-removal-2026-11-26.md),
§9.3.

**What was measured.** That record measured the ledger's half of a dangling
source id — the address rows stay, the address still resolves to the text,
and the `source_id` they carry points at a source the ledger no longer
holds — and it said the product's reading faces were not measured, "reported
as untested rather than as safe." This record measures that other half: a
ledger in the shape the record describes, read through every face the
product has over it. Each face says what it says, and the record says so.

**What the reading found.** The faces split into three, and the split is the
finding:

1. **The source-id faces refuse, and name the id.** `labcairn sources
   addresses` and `labcairn sources inspect` — and the service's two
   `GET /sources/…` routes — return a refusal `source_not_found` that names
   the id of the source that is gone. A reader who asks "what is at source
   X" is told "there is no such source": the honest answer, and the one a
   reader can act on.

2. **The report face refuses, and names the id.** `labcairn task report` —
   and the service's `POST /report` — refuses with `report_content_refused`,
   and the message names the anchor, the record, **and the source id that is
   gone**: "the anchor … of the record … points at the source …, which the
   report does not carry." The guard fired, and it says why.

3. **The record face reads as sound while the row it names is gone.** The
   service's `GET /records` (the layer's `list_task_records`) returned
   **HTTP 200** and the record that cites the gone address: its state, its
   anchor ids, its source hash — all present, and nothing in the body that
   says the source is gone. And the attestation face (`labcairn task
   claim-attest`, the layer's `attest_claim`) advanced that record into a
   **citable** state, `user_attested`, with exit 0, without asking of the
   anchor's source row a second time. **This is the finding, and it is the
   important one.** A reader who looks at the record face is told the record
   stands in a state a report may cite, while the report face refuses to
   carry it: the two faces disagree, and the one that reads as sound is the
   one a reader is most likely to trust, because it is the record and not
   the report.

The task-bound faces (`labcairn task status`, `GET /task`, `GET /sources`)
read as sound as well, but they are **not** the finding: the removal
*released* the task's binding to the gone source, so the task no longer
claims it, and those faces honestly report only the survivor. The dangling
reference is reachable through the record and its anchor, not through the
task's binding.

**The boundary this record obeys.** Ids, digests, counts, states, exit
codes and HTTP statuses. No sentence of the pilot's manuscript or of the
advisor's marks; the addresses the reading faces return carry text, and this
record counts them and names their digests rather than their text.

## 1. The shape, built

The scratch workspace was built under `E:/labcairn-local/tmp/`, a directory
of this reading's own, through the product's own commands:

| step | the command | what it left in the ledger |
| --- | --- | --- |
| the workspace | `labcairn --workspace … init` | the scratch database, `materials/`, a policy digest `49a71194…` |
| the task | `labcairn task create --title … --objective … --criterion …` | task `01a218e6-b5b2-709d-b0d6-aec00343dbd7`, bound to source `src-925b4c8616fe959a` |
| the addresses | `labcairn sources addresses --source src-925b4c…` | **2** addresses into that source, extraction version `7a54f54e049db405cfa188cb7b9640b8` |
| the record | `labcairn task claim --source src-925b4c… --address 'k=3:csv|r=1:2|c=7:reading' --kind claim …` | record `01a218e7-088e-7311-8786-45ea8c0fa2c5` (state `extracted`), resting on anchor `01a218e7-088d-7d01-8fcc-9a9fc7678b1e` |
| the move | the material moved to a second path and re-ingested (`labcairn sources ingest`) | a second source row, `src-33b39c5a11eba0a6`, the task bound to both |
| the removal | `labcairn sources remove --source src-925b4c…` | the stale row gone; `released_task_ids` held the task; `removed_problem_count` **2**; `repointed_to_source_id` **null** |

The shape that the reading is taken over is now: the ledger holds one source
row, `src-33b39c5a11eba0a6`; one address row, `01a218e7-088d`, whose
`source_id` names `src-925b4c8616fe959a` — a source the ledger does not
hold; the two text rows that address into, keyed by the content hash
`bf4802393811fef890a8e7d181faaba9d68d1100fc58a0b76bcb612a260c58bf` and
surviving because they are indexed by the bytes and not by the source; and
the one record `01a218e7-088e` that cites the address. A **dangling id, not
a lost row**, the record's §9.3 predicted — now the reading is taken over
that id, not the row.

## 2. What each face read

Each face as the reading met it: the command or route, what it said, and the
code a reader would take away. "Reads as sound" is said of the faces that
returned the record without a refusal while the row the record's anchor
names is gone, and "refuses, and names the id" of the ones that did not.

| # | the face | the command / route | what it read | the code |
| --- | --- | --- | --- | --- |
| R1 | the source-id read, addresses | `labcairn sources addresses --source src-925b4c… --json` | `source_not_found`: "the ledger holds no source with the id 'src-925b4c8616fe959a'." — **refuses, and names the id** | exit **3** |
| R2 | the source-id read, inspect | `labcairn sources inspect --source src-925b4c… --json` | `source_not_found`, the same message — **refuses, and names the id** | exit **3** |
| R3 | the service's source read | `GET /sources/src-925b4c…` | `source_not_found`, the same message — **refuses, and names the id** | **403** |
| R4 | the service's address read | `GET /sources/src-925b4c…/addresses` | `source_not_found`, the same message — **refuses, and names the id** | **403** |
| R5 | the claim write, CLI | `labcairn task claim --source src-925b4c… …` | `source_not_found` — the write is refused before it writes | exit **3** |
| R6 | the claim write, service | `POST /claims` (`source_id` = the gone id) | `source_not_found`, **403** — a claim the task no longer holds material for cannot be recorded | **403** |
| R7 | the task-state read | `labcairn task status --json` | `bound_source_ids` now holds only `src-33b39c…`; the gone source is not claimed — **reads as sound, because the binding was released** | exit **0** |
| R8 | the service's task read | `GET /task` | the same `bound_source_ids`, only the survivor | **200** |
| R9 | the service's material read | `GET /sources` | the one source the task holds, the survivor | **200** |
| **R10** | **the record read, service** | `GET /records` | **HTTP 200, the record the ledger holds**: `evidence_id` `01a218e7-088e…`, `status` `extracted` (and `user_attested` after R13), `anchor_ids` `["01a218e7-088d…"]`, `source_content_hash` `bf480239…` — **reads as sound while the row its anchor names is gone** | **200** |
| **R11** | **the record read, layer** | `list_task_records(context)` | the same record, no refusal — the face the service serves, read through the layer | ok |
| R12 | the report, CLI | `labcairn task report --json` | `report_content_refused`: "the anchor '01a218e7-088d…' of the record '01a218e7-088e…' points at the source 'src-925b4c8616fe959a', which the report does not carry. A citation into material the report does not have is a citation the reader cannot open." — **refuses, and names the id** | exit **3** |
| R12′ | the report, service | `POST /report` | the same refusal, **403** | **403** |
| **R13** | **the attestation, CLI** | `labcairn task claim-attest 01a218e7-088e… --user … --note …` | the record advanced to `user_attested`, a **citable** state, with a C4 log entry whose only verdict is `not_checked` — **reads as sound, and moves the record into the state a report may cite** | exit **0** |
| **R13′** | **the attestation, layer** | `attest_claim(context, …)` | the same advance | ok |
| R14 | the event face | the `events` table, read | the one `source_removed` event, whose payload **names** the gone id — the one place in the log the id is visible | a table read |
| R15 | the index face | `LabCairnIndex(conn).locate(anchor)` | `resolution` `resolved`, the text present (read from the surviving text row, keyed by the content hash), but `observed_content_sha256` **None** — the index sees no source row to read the hash from | a library call |
| R16 | the export face | `GET /review/deliverables` | **422** — it asks for a `project_id` and a `dossier_artifact_id` (a closed review binding), which this shape does not hold; it refused before it read anything | **422** |

**The reading, in one line.** The faces that take the source id as their
own argument — R1–R6 — refuse it and say so. The face that builds a report
over the record — R12 — refuses it and says so, and names the id. The face
that *reads the record back* — R10 — does not: it returns the record at 200,
in a state that, once the attestation has run, is citable, while the anchor
the record rests on points at a source the ledger does not hold. **The row
whose source is gone is not unreadable on the read face; on the read face it
reads as if nothing were wrong.**

## 3. Where each number came from

Every number in the record is a count, a digest, an id, a byte count or a
code, and each was produced by one command. The commands were run against
the scratch workspace under `E:/labcairn-local/tmp/`, through this tree's own
console script (`uv run labcairn`), so the code that ran is the code in the
tree the record was written on (`124e843`).

| the number in the record | what it is | the command that produced it |
| --- | --- | --- |
| `01a218e6-b5b2-709d-b0d6-aec00343dbd7` | the scratch task's id | `labcairn task create … --json` |
| `src-925b4c8616fe959a` | the gone source's id | `labcairn task create … --json` (`bound_source_ids`) |
| `src-33b39c5a11eba0a6` | the survivor's id | `labcairn sources ingest … --json` (`source_ids`) |
| `01a218e7-088e-…` | the record's id | `labcairn task claim … --json` |
| `01a218e7-088d-…` | the anchor's id | `labcairn task claim … --json` (`anchor_id`) |
| `bf4802393811…` | the material's content hash | `labcairn sources inspect … --json` (`content_sha256`) |
| **2** | the addresses the gone source held | `labcairn sources addresses … --json` (the list's length) |
| `7a54f54e049d…` | the extraction version the addresses carry | `labcairn sources addresses … --json` |
| `2912aa729c97…` | the claim's span, as a hash | `labcairn task claim … --json` (`extracted_span_sha256`) |
| `49a71194d753…` | the scratch policy's digest | `labcairn init … --json` (`policy_digest`) |
| **2** (`removed_problem_count`) | the gone row's own disclosures, taken | `labcairn sources remove … --json` |
| `01a218e6…` (`released_task_ids`) | the binding the release let go | `labcairn sources remove … --json` |
| **1 / 1 / 2 / 1** | the rows in `sources` / `source_anchors` / `source_texts` / `evidence_records` after the removal | a read of the scratch database, `SELECT COUNT(*)` per table |
| **3** | the exit code a refused source-id read carries | `labcairn sources addresses/inspect … --json` (the code the command returned) |
| **403** | the status a refused source read carries on the wire | `curl … GET /sources/<id>` |
| **200** | the status the record face gives, the record reading as sound | `curl … GET /records` |
| **422** | the status the export face gives, out of reach | `curl … GET /review/deliverables` |
| `resolved` / `None` | the index's view of the gone anchor's resolution and observed hash | `LabCairnIndex(conn).locate(anchor)` |

The two witness numbers — that the record reads back at **200** and that the
attestation advances it into the citable set — are held still by the witness
file named at the foot of the record, not by the scratch workspace alone, so
that a face that learned to check the source row again would go red rather
than quietly change its answer.

## 4. What the reading did not exercise

Stated plainly, because the value of the record is that it says what
happened.

1. **The C1–C3 machine checks are not offered by any face.** The operation
   that moves a record through C1, C2 and C3 has no caller in the CLI or in
   the service, so the product does not ask the question the check would
   ask — "is the material still the bytes this record was written
   against?" — and the reading cannot report a C1 verdict for a record
   whose source is gone, because no face runs one. The attestation face is
   C4, whose only verdict is `not_checked`, and it advances on a person's
   word without consulting the source row at all.

2. **The index's answer to the drift question is `None`, not a verdict.**
   `locate` resolved the anchor to the surviving text row and read its
   text, but its `observed_content_sha256` is `None`: the index reads the
   observed hash from the source row, and the row is gone. A C1 comparison
   of the anchor's bound hash against an observed hash that cannot be read
   is indeterminate at the index level — the index says "I cannot see the
   source," not "the source drifted" — and no face offers that
   indeterminate answer to a reader.

3. **The report face's guard is the binding guard, not an integrity guard.**
   The report builder checks the anchor's source id against the sources the
   task is *bound to*, and the removal released that binding, so the check
   fired on "the report does not carry the source." The refusal names the
   binding, not the dangling id, and the record face is not guarded at all:
   nothing on the read path asks whether the anchor's source row still
   exists. The two faces that refuse do so for reasons a reader can act on;
   the one that does not refuse does not ask the question.

4. **The export face was out of reach on this shape.** `GET
   /review/deliverables` names a closed review binding — a project and a
   dossier receipt — that the scratch shape does not hold, and it refused
   with 422 before it read anything. So "the report the export would quote"
   was measured through the report face, which refuses, and not through the
   export, which the shape does not reach.

## 5. Where the material and the evidence live

The scratch workspace, its database, the service's log files and the pytest
temp directories of the reading all sit under the registered temp area
`E:/labcairn-local/tmp/`. The external-path ledger,
[`docs/ci/external-paths.json`](../ci/external-paths.json), answers for that
area: the area itself and the temp directory are kind `material`,
expectation `present`. The scratch directory this reading made is the
reading's own, not a delivery pack, and this record names the registered
parent directory rather than the child, so the record does not point at a
path the ledger has not judged. No row of the pilot's ledger was read or
written; the pilot's material under `E:/labcairn-local/` stayed out of the
tree, and only the ids, digests, counts and codes of the scratch reading
appear here.

The evidence that the two finding faces hold is in the witness file
[`tests/test_dangling_source_read_faces.py`](../../tests/test_dangling_source_read_faces.py),
which builds the same shape in a workspace of its own, under a temporary
directory, through the product's own operations — reads nothing of this
scratch workspace or of the pilot's — and holds two properties still: the
record read returns the record whose anchor names a source the ledger does
not hold, and the attestation advances that record into the citable set
without asking of the source row a second time. The file is new to this
reading and is not yet in the CI shard file; its registration and its shard
cost are for the merge that lands it, not for this record.

## 6. What the record does not claim

- **It does not say the dangling id is wrong.** It says what the faces
  read. The schema has no foreign key on `source_anchors.source_id` — the
  record's §9.3 said so, and the reading confirmed it on the scratch
  database — and whether a dangling id should be impossible is a decision
  about the schema, not a measurement the reading can make. This is a
  measurement window, and the finding is reported with the output that shows
  it, not closed.
- **It does not stand in for the report face's own record.** The report's
  refusal of a record it does not carry is witnessed elsewhere in the tree;
  this record cites it as the guard that fires and adds the faces that do
  not fire.
- **It does not say the two faces will stay disagreeing.** It says they do,
  on this tree, on this shape, measured. The witness holds the shape still,
  and a face that learned to check the source row again would make the
  witness red and force the reading to be re-measured.
