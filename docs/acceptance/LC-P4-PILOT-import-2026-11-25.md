# LC-P4-PILOT — the import of the signed desensitised copy

**Ticket:** LC-P4-PILOT (pilot preparation, prerequisite material)
**Date:** 2026-11-25 (the import run), recorded 2026-11-26.
**Tree:** `5a4e4587d076f1e934df86ed6a00e6126981fcc0` (worktree
`pilot-import-request-0745db`), Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.10.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Material id:** `pilot-paper-002`.
**Workspace:** `E:/labcairn-local/pilot-ws`, task
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1`, paper project `proj-pilot-002`.

**What is claimed here.** The copy the owner signed was imported into the
pilot workspace through the product's own surface, the import's own digest
check agrees with the registered digest, and the counts the registration
holds are the counts the imported copy still measures. **What is not
claimed:** that the pilot's step 3 has run — the record of the request is
[`LC-P4-PILOT-real-request-2026-11-25.md`](LC-P4-PILOT-real-request-2026-11-25.md),
§8, and this record does not stand in for it.

**The boundary this record obeys.** Ids, digests, counts and paths. No
sentence of the manuscript, no sentence of the advisor's marks, and no key
(`LC-P4-PILOT-model-authorisation-draft.md` §8; G0 §4).

## 1. The gate that had to pass first

The import may not run before the desensitisation checklist carries a
signature, so the registration was checked with the product's own script and
its own signed mode:

```
uv run python scripts/pilot_material_registration.py check \
  docs/pilot/registrations/pilot-paper-002.json \
  --copy "E:/trial-material/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx" \
  --require-signed
```

Exit code **0**, and the script's verdict: *the record holds*. The record's
part D carries the signed result (2026-11-25, operator `owner`), which is
what `--require-signed` demands; every item A-1 … D-5 reads `pass`.

## 2. The digest comparison — the import's own check

| Reading | Value |
|---|---|
| Registered (`copy.sha256` in the registration) | `04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d` |
| Measured on the file in `E:/trial-material` | `04cc31be…a6172d` — 8,805,237 bytes |
| Measured on the copy **after** it was placed inside the workspace | `04cc31be…a6172d` — 8,805,237 bytes |

Three readings, one value: the copy that was signed is the copy that was
imported, and the copy inside the workspace is the copy that was signed. The
registration's `origin_sha256` (`a7a38132…`, 8,871,367 bytes) is the
material this one was made from; it is a different file and it stays
outside the workspace.

## 3. The counts, measured again on the imported copy

The registration carries the counts as `metadata`. They were **re-measured
on the file that was actually imported**, not copied across:

| Count | Registered | Measured on the imported copy | How it was read |
|---|---|---|---|
| Pages | 18 | 18 | `docProps/app.xml`, the `<Pages>` element |
| Words | 11,710 | 11,710 | `docProps/app.xml`, the `<Words>` element |
| Figures | 7 | 7 | 7 `<w:drawing>` elements, and 7 parts under `word/media/` |
| Tables | 1 | 1 | 1 `<w:tbl>` element |

Every count agrees. Nothing the desensitisation removed changed any of
them, which is the count comparison the import step is for.

## 4. What the ledger holds after the import

The import itself is the product's own command:

```
uv run labcairn --workspace E:/labcairn-local/pilot-ws sources ingest
```

Exit code **0**. The run's own summary: **197 files ingested, 158 readable,
39 unreadable (39 with no adapter), 0 empty, 0 failed**; 9 paper projects had
their revision trajectory indexed.

For this copy, the ledger holds:

| Field | Value |
|---|---|
| Source id | `src-0ac499ea4d3a7d82` |
| Workspace-relative path | `materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` |
| Root-relative key | `pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx` |
| Content digest | `04cc31be…a6172d` |
| Readability | `readable` |
| Ingested at | 2026-11-25T18:28:26Z |
| Text rows for this digest | **268** rows in `source_texts`: 251 `accepted` (23,432 characters) and 17 `rejected` (396 characters) |

The 268 rows are the material the request will read its excerpts from: the
accepted view is what the product extracted from the imported file, and the
rejected rows are the fragments the extractor refused. Both are the import's
own output; nothing was extracted a second time by hand.

## 5. Why the copy sits under `pilot/LC-P4-PILOT/desensitised-copy/`

The grant the owner signed
([`LC-P4-PILOT-model-authorisation-draft.md`](../plans/LC-P4-PILOT-model-authorisation-draft.md)
§2, and the `model_suggestions` block of the workspace's `providers.json`)
covers the material under **`pilot/LC-P4-PILOT/desensitised-copy/**`**, and
the registration's `storage.relative_path` is
`pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`. A scope is a
**root-relative coordinate**, so the copy has to sit at that path under the
workspace's source root for its key to fall inside the scope at all.

The copy was first placed at `materials/pilot-paper-002/pilot-paper-002.docx`,
whose root-relative key is `pilot-paper-002/pilot-paper-002.docx` — **outside**
the scope. A request against that key is refused by the transmit gate, and
§8 of the request record shows that refusal being taken for real. The file
was then moved (not copied) to the path the registration names, and the
import was run again.

**One leftover, recorded rather than repaired.** The first placement left a
source row of its own, `src-0738f31ecf1e750b`, whose `relative_path` names
a file that is no longer in the workspace. The store therefore holds **two
rows for one digest**, and one of them points at a path that does not exist.
The product has no command that drops a source, and a hand-edit of the
store is not a fix — so the row is left as it is and named here.

## 6. What the import does not give the pilot

The copy carries **no Word comments**: there is no `word/comments.xml` in
it, and it has 0 `commentRangeStart` elements. The file it was made from
(`a7a38132…`, the advisor's annotated working sample) has the same count —
0 comments, 96 insertions and 17 deletions — so the desensitisation did not
drop anything here; **this material's advisor marks are tracked changes,
not comments**, and the copy keeps all 113 of them.

That has a consequence the pilot has to know: the product's suggestion loop
walks **comment** feedback events, so for this copy it has nothing to ask.
Measured, not assumed — the loop was run over the imported version in real
mode and made **0 requests** (0 opinions, 0 skipped, 0.007 s); the numbers
are in the request record's §8.6.

So the pilot's first real model request could not be a suggestion about an
opinion in this copy. What it was instead, and what it cost, is the subject
of the request record.

## 7. Evidence

| What | Where |
|---|---|
| Registration gate (`--require-signed`) | `scripts/pilot_material_registration.py check …`, exit 0 |
| The import | `uv run labcairn --workspace E:/labcairn-local/pilot-ws sources ingest`, exit 0, summary in §4 |
| The imported copy | `E:/labcairn-local/pilot-ws/materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`, 8,805,237 bytes, digest `04cc31be…a6172d` |
| The ledger | `E:/labcairn-local/pilot-ws/labcairn.db` — `sources` (`src-0ac499ea4d3a7d82`), `source_texts` (268 rows for this digest) |
| The signed registration | `docs/pilot/registrations/pilot-paper-002.json` |
| The signed checklist | `docs/plans/LC-P4-PILOT-desensitisation-checklist.md` |
| The counts' measurements | `docProps/app.xml`, `word/document.xml`, `word/media/` of the imported copy |

Nothing in this record was written by hand into the store, and nothing in it
quotes the material.
