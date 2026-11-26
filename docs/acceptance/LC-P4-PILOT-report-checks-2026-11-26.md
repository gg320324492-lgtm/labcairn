# LC-P4-PILOT — the report's content checks, run once over the pilot copy

**Ticket:** LC-P4-PILOT (the pilot's report content checks)
**Date:** 2026-11-26.
**Tree:** `c3bde03b944eb3e9b50679fe1958eb2751ab5bab` (worktree
`priceless-neumann-e3dfa8`), Windows 11 Pro (10.0.26300 x64, AMD64),
Python 3.12.13. The run was taken on that tree; the commit carrying this
record changes no code under `src/`, `tests/` or `scripts/`.
**Status:** local evidence only. No push, no pull request, no CI run, no
merge.
**Workspace:** `E:/labcairn-local/pilot-ws` — database revision `0032`, at
head; task `01a212be-ddd1-7c9a-aaad-c1db083b8bc1` ("Pilot revision round 2
(desensitised copy pilot-paper-002)"); source `src-0ac499ea4d3a7d82`.
**Material:** `pilot-paper-002.docx`, sha256
`04cc31be9f9876fef975e8d4e6b427bb4a063920288fe5c0b72e8e3244a6172d`,
8,805,237 bytes, at
`materials/pilot/LC-P4-PILOT/desensitised-copy/pilot-paper-002.docx`.

**What is claimed here.** The product's report content checks were run **once**
over the pilot's exported report — the file the round actually wrote — and
what they read was written down: five checks, the ledger and the index behind
them, the artefacts they looked for on disk (none — this report names none),
and the things they could not read at all. The product's own route to those
checks was then measured on a **copy** of the workspace, once succeeding and
once refusing, so that "the command reaches the gate" is a measurement and
not a reading of the source.

**What is not claimed.** That the checks could have said more than they did.
Two of the five ran over an empty set — the pilot's report carries no figure
and no table, and its one record carries no number — and §6 says so rather
than rounding the run up into coverage. The pilot workspace was **read and
never written**; the measurements that needed a writable workspace were taken
on copies under `E:/labcairn-local/tmp`. No sentence of the manuscript, of
the advisor's marks, or of the report's prose is in this record; the refusal
messages §7 refers to carry the claim's wording, and they are described there
rather than reproduced.

## 1. The mechanism, and where it lives

The content checks are one module: `src/labcairn/reports/checks.py` (677
lines). It names five checks and one gate.

| check | what it is about | the gate's name for it |
| --- | --- | --- |
| `check_the_snapshot_names_the_records_the_report_carries` | the report's extent: it names exactly the records it carries | `snapshot` |
| `check_claims_and_disclosures_rest_on_records_the_ledger_holds` | every record the report names is the ledger's, and a claim states the ledger's status or the floor | `records` |
| `check_numbers_agree_with_the_ledger` | every number and unit in the report is the ledger's, compared exactly | `numbers` |
| `check_links_resolve` | every citation is an address the index can resolve | `links` |
| `check_figures_and_tables_are_the_artefacts_on_disk` | every artefact the report references is the artefact on disk | `artefacts` |

`check_report` (line 642) is the gate: it runs them in the report's own
dependency order and **stops at the first refusal**, because a report is not
written on the strength of the checks that happened to pass. A failed check
raises `ReportRefusedError`, and the report is not written.

**The checks read the model, never an export.** That is the module's own
reason and it is load-bearing: a check on a rendered file would be a *second*
content, and four renderers would then have to agree with each other. So
`report.json` is not a rendering — it is `ReportDocument.canonical_bytes()`
written to a file, and `ReportDocument.model_validate_json` reads it back to
the model. **The round-trip is exact**: re-serialising the document loaded
from the pilot's `report.json` reproduces the file's bytes, which is what
makes "run the checks over the export" a statement about the export and not
about a second copy of it.

**The seam is the ledger.** The checks never read the model's own copy of a
record. They read it through a `LedgerReader`, and the caller chooses what
the ledger is. The module says why: a caller that wants to check an *older*
revision has to hand over a ledger as it was at that revision's moment,
because the live ledger has moved on. §6 says what happened here.

## 2. What reaches the checks, and what does not

```
labcairn task report --path report        (src/labcairn/cli/commands.py:1388)
POST /report                               (src/labcairn/api/routes.py:781)
    -> labcairn.application.reports.render_report      (application/reports.py:240)
        -> _check_the_document                          (application/reports.py:636)
            -> labcairn.reports.checks.check_report     (application/reports.py:654)
```

**There is no route that checks an export that already exists.** Both routes
build a **fresh** document from the workspace's records and then **write** a
revision; neither takes a `report.json` as an input. The check and the write
are one operation, and the operation's output is the thing that would be
checked. To check an export that is already on disk, a caller must load it
and call `labcairn.reports.checks.check_report` itself — which is what this
record's measurement did, and what §5's product route could not do.

**Two other families of check exist, and neither is this one.** The first
round's §4.3 named the **C1/C2/C3 evidence checks**
(`src/labcairn/evidence/checks/`), which verify a *record* against the
material it cites; §8 runs them. The second is the **six §7.4 round-quality
checks** (`src/labcairn/application/quality_checks.py`), which verify a closed
review round against its dossier manifest and are reached by
`GET /review/quality`. The report content checks are a third thing, and this
record is about them.

## 3. What the checks read

The gate was run over the pilot's **revision 2** document, and then over
revision 1. The pilot's ledger was opened **read-only**
(`create_db_engine(..., readonly=True)`, which sets `PRAGMA query_only=ON`),
so the run could not have written even if it had wanted to.

| what the gate read | revision 2 | revision 1 | outcome |
| --- | --- | --- | --- |
| the document's own model | 1 section, 1 claim, 1 footnote, 1 named record, 1 anchor | the same shape | loaded and validated |
| the snapshot's records | 1 id, `as_of` 2026-11-26T11:38:47Z | 1 id, `as_of` 2026-11-26T11:37:29Z | `snapshot` passed |
| the ledger's rows | 1 row read (`evidence_records` holds 3 in the workspace) | 1 row read | `records` passed |
| the ledger's value and unit | 1 pair compared — **both sides null** | the same | `numbers` passed |
| the index's anchors | 1 anchor resolved, 1 `source_texts` row read | the same | `links` passed |
| the text at that anchor | 432 characters read from the database | the same | `links` passed |
| the observed source digest | `04cc31be…6172d`, equal to the material's | the same | `links` passed |
| the files on disk | **0 read** — the document names no figure and no table | 0 | `artefacts` passed |
| the four rendered forms | **0 opened** — `report.md`, `report.html`, `report.docx`, `report.pdf` | 0 | — |

The gate **passed** for both revisions: revision 2 in 0.0011 s, revision 1 in
0.0017 s, with every one of the five checks reached.

## 4. What they found

**Nothing to refuse.** The pilot's exported report is one the ledger
supports: the record it names is in the ledger, the words it states are the
ledger's words, the citation resolves to an address the index can read, and
the source behind that address still hashes to the digest the material has.

The single claim rests on the record
`01a217a3-5845-78c6-a41f-e0093a0b7d2e`, whose ledger status is
`user_attested` — a named human said so — and whose kind is `claim`. The
citation `fn-01a217a3-5844-772e-a92a-a1da3faf30bf` names the source
`src-0ac499ea4d3a7d82` at
`word/document.xml /w:document/w:body/w:p[7]` (accepted view), characters
0–432. The index read 432 characters there and observed the source digest
`04cc31be…6172d` — the digest of the pilot's copy, unchanged.

**The checks read the live ledger, and the live ledger has moved on.** The
report's snapshot is a view of the moment it was taken
(2026-11-26T11:38:47Z for revision 2); the ledger read here is the one as it
stands on 2026-11-26, after the [source-removal run](LC-P4-PILOT-source-removal-2026-11-26.md).
The two agree here, so
nothing was refused. That they *can* agree is the point of the ceiling rule
the `records` check applies: a report that states the ledger's status or the
floor stays true when the ledger is later promoted, so a drift would not
have been a refusal. §5's second run is what a disagreement looks like.

## 5. The route, measured

The claim that the product's own command reaches the gate was measured on
**two copies** of the pilot workspace, built in a directory named
`report-checks-2026-11-26` under `E:/labcairn-local/tmp`. Each copy holds the
database, the `.labcairn` directory, the output tree and the pilot's own
8.4 MB material subtree; the workspace's other 1.6 GB of material was left
out, because the checks read the disk only for artefacts the report names and
this report names none (§6).

**Copy A — the route succeeds.** `labcairn task report --path report --json`
against the copy wrote revision 3: receipt
`01a212be-ddd1-7c9a-aaad-c1db083b8bc1-r3-document`, six files, `report.json`
1,465 bytes / sha256 `aa026a758bc0f22ab3dc8e51eb01d755db591c64201cc56585ea89259ed1964e`,
`staleness: current`, and a chain that names the source
`src-0ac499ea4d3a7d82` at digest `04cc31be…6172d`. The copy's output went
from 12 files to 18.

**The re-render is the same report.** All six of revision 3's files differ
from revision 2's, and `report.md` differs on **one line** — the snapshot's
moment (`2026-11-26T11:38:47Z` against `2026-11-26T15:58:37Z`). The
document is a view at a moment, and the moment moved. The Markdown is
otherwise the same 957 bytes.

**Copy B — the route refuses.** One row was deleted from copy B's
`source_texts`: the text at the citation's address. The command was then run
again, unchanged, and it was **refused**:

```
report_content_refused: the links check refused the report: the citation
'fn-01a217a3-5844-772e-a92a-a1da3faf30bf' points at docx:
word/document.xml /w:document/w:body/w:p[7] (accepted), chars 0-432, which
the material answers with 'unresolvable'. Nothing is cited in its place.
Nothing was written: a report that says something the ledger does not
support must not be written at all.
```

Exit code 3. **Copy B's output still holds 12 files** — no `v3/` directory was
created, so the refusal wrote nothing at all. This is the gate being
load-bearing on the product's own route, and it is the first thing to say
about the mechanism that the first round's §4.3 did not: **the content checks
are not a separate command that a round may skip.** They run inside
`task report`, before the first byte of any form is rendered, and a report
they refuse is not written.

## 6. What the checks could not check, and why

Four things, stated as facts about this run and not as defects.

1. **The artefact check read no file.** The pilot's report carries **0
   figures and 0 tables**, so `check_figures_and_tables_are_the_artefacts_on_disk`
   had an empty set to work on and passed over it. It was exercised over
   nothing. This is structural and the first round recorded why: the copy
   holds **0 table-cell rows**, so there is no selection for the registered
   operators to take, and no figure follows from one. The check is
   load-bearing (§7) but this run did not exercise it on the pilot's material.

2. **The number check compared nulls.** The one record the report names is
   `kind=claim`, so it carries no value and no unit on either side. The
   check did compare — the document's stated value and unit against the
   ledger's, exactly — and both sides were null. It passed on a comparison
   between two absences, and it would have caught a number that was there.

3. **The four rendered forms were never opened.** `report.md`,
   `report.html`, `report.docx` and `report.pdf` were not read by any of the
   five checks, because the checks read the model and the renderers only
   draw it. That is the design, and it is also the limit of what this run can
   say: **these checks say nothing about the rendered forms.** That the four
   forms of one document agree with each other is the renderers' property,
   not the gate's, and it is not what §3 measured.

4. **The ledger read was the live one, not the one at the report's moment.**
   The module says a caller wanting to check an older revision must hand
   over the ledger as it stood then. This run handed over the ledger as it
   stands now. For the pilot's copy the two agree, so nothing was refused;
   §5's copy B is what happens when they do not. This is a fact about the
   seam, and it is why the record's `as_of` is worth keeping next to the
   ledger's revision.

Two further limits, of a different kind. **The export's own manifest was not
checked by these checks** — `report-manifest.json` carries a
`report_sha256` and a lineage chain, and the gate does not read it; the
revision machinery's `verify` is a separate mechanism that runs inside the
write. And **the pilot's report is one claim and one citation**, so every
count in §3 is a count of one; this run is a demonstration that the checks
read what they say they read, not a measure of how the checks behave on a
report of substance.

## 7. What each check reads

A check that cannot fail is not a check. Each probe below takes the pilot's
exported document, changes **exactly one thing**, and runs the gate again.
Every probe refused, and each refused with its own check — which is what
says what each check reads.

| probe | the one thing changed | the check that refused |
| --- | --- | --- |
| control | nothing | — (passed) |
| P1 | the claim's wording, by one character | `records` |
| P2 | the claim's status, raised to `verified_by_rule` | `records` |
| P3 | the snapshot names a record the document does not carry | `snapshot` |
| P4 | the citation's locator, moved one character along | `links` |
| P5 | a table naming bytes that are not on disk | `artefacts` |
| P6 | the record's numeric value | `numbers` |
| P7 | the claim names a record the ledger holds not | `snapshot` |

P1 and P2 are the ceiling rule working in both directions: a report that
states words the ledger does not hold, and a report that claims more credit
than the ledger gives, are both refused. P5 is the artefact check refusing a
file it cannot read, and it is the probe the pilot's own report could not
supply — it has no table to break.

**The refusal messages quote the material.** P1's message carries both the
report's wording and the ledger's, and P5's carries the path it could not
read. Those messages are evidence and they are **not** in this record; they
are in the evidence directory (§10), where the pilot's prose stays outside
the repository.

## 8. The C1/C2/C3 checks, which the first round left out

The first round's §4.3 said the C1/C2/C3 checks "are separate commands and
this round did not run them" — the [first round's](LC-P4-PILOT-first-round-2026-11-26.md)
words. They were run here, over the one record the
pilot's report carries, against the same read-only ledger and index.

| check | outcome | what it said |
| --- | --- | --- |
| C1 `c1.source_exists` | `pass` | all 1 anchor resolved, and every recorded content hash still matches the source |
| C2 `c2.quotation_match` | `pass` | the quoted span appears character-for-character in the located text |
| C3 `c3.numeric_consistency` | `indeterminate` | the record is `kind=claim`, which carries a statement rather than a quantity; C3 has no number to reconcile |

**C3's `indeterminate` is the right answer and not a failure.** It is a
member of a closed four-member enum beside `pass` and `fail`, and it is not
equal to `pass`: the check declined to answer a question the record did not
ask. §4.3 of the first round called the C1/C2/C3 checks "a separate act" —
they are separate *from the report's content checks*, and they are not
separate *from the record*: both families read the same ledger and the same
index. What §4.3 got right was that they had not been run. They have now
been, on this copy, over this record.

## 9. Where each number came from

Every number in this record is a local reading on the tree named above, taken
on 2026-11-26. The scripts live outside the repository, in the directory
named `report-checks-2026-11-26` under `E:/labcairn-local/tmp`, and were run
with `PYTHONPATH` pointing at this worktree's `src` — the venv at
`E:/LabCairn/.venv` is an editable install whose `.pth` names the **main**
checkout, so the run printed the path it imported from
(`E:\LabCairn\.claude\worktrees\priceless-neumann-e3dfa8\src\labcairn\__init__.py`)
rather than relying on it. `git diff --stat main..HEAD -- src/` is empty, so
the two trees' `src` is byte-identical in any case.

**The same trap has a witness, and it fires on any worktree that is not the
main checkout.** `tests/test_scaffolding.py::test_core_resolves_inside_the_source_tree`
asserts that `labcairn.core` resolves under the repository's own `src`, and
against this venv it fails on any worktree but the main one — the installation
is the main checkout's, so the assertion sees a path outside the tree. It is
a property of the environment, not of any change in the tree: it fails here
on the tree this record was written on, with a one-document commit on top of
it.

**The two ways of fixing it cannot both be had at once.** Putting this
worktree's `src` first on `PYTHONPATH` makes that witness pass, and it
makes `tests/test_no_reference_leakage.py::test_wheel_installs_clean_and_imports`
fail — that one builds a clean room and asserts the wheel's own installation
imports there, and a `PYTHONPATH` shadow defeats the point of it. So: the
tree's own witnesses were run **without** `PYTHONPATH`, and the measurements
in this record were run **with** it, because the question here is which tree
the code came from. The path the run imported from was printed by the run
itself rather than assumed, and it is recorded above. Nothing in this record
depends on the shadow either way: `git diff --stat main..HEAD -- src/` is
empty, so the two trees' `src` is byte-identical.

**The witness ledger was not run, because no witness was added.** This record
adds no test file — the behaviour it measured, the route refusing a report
the ledger does not support, is already witnessed at the application, API and
CLI layers — so there is no deletion to check for. The document witnesses that
watch this tree were run and pass: `tests/test_external_path_references.py`
and `tests/test_no_reference_leakage.py`, 116 passed.

| number | where it is used | how it was read |
| --- | --- | --- |
| `5` checks, `677` lines | §1 | `wc -l src/labcairn/reports/checks.py`; the five names are the module's `__all__` |
| `2` routes that reach the gate | §2 | `src/labcairn/cli/commands.py:1388` and `src/labcairn/api/routes.py:781`, both calling `render_report` |
| `0` routes that check an existing export | §2 | the CLI's full command list (`init`, `doctor`, `serve`, `task …`, `sources …`, `artifacts list`, `guidance rule-confirm`, `roles run`) and the API's routes; none takes a `report.json` |
| `2` revisions, `6` files each, `12` exported files | §3 | `find output -type f \| wc -l`, run from `E:/labcairn-local/pilot-ws` → `12`; the per-file table below |
| `1,461` / `29c7dcef…0757d6c` (v1 `report.json`) | §3 | `sha256sum` and `stat -c%s` over the file |
| `1,465` / `3904ea81…4cf266c` (v2 `report.json`) | §3 | the same; both digests agree with the first-round record's §5 |
| `1,465` / `aa026a75…ed1964e` (copy A v3 `report.json`) | §5 | the same, over copy A's revision 3 |
| `0.0011 s` (v2 gate), `0.0017 s` (v1 gate) | §3 | `time.perf_counter()` around `check_report` in `run_checks.py` |
| `432` characters read at the anchor | §3, §4 | `len(located.text)` from `LabCairnIndex.locate` |
| `3` rows in `evidence_records` | §3 | `SELECT COUNT(*) FROM evidence_records` over `file:…?mode=ro` |
| `0032`, at head | the header | `SELECT version_num FROM alembic_version`; `labcairn doctor`'s own `current_revision` reads the same |
| `1` row deleted in copy B | §5 | `DELETE FROM source_texts WHERE locator_key = …` → `rowcount` `1`; `76,577` rows before, `76,576` after |
| exit code `3` | §5 | the CLI's refusal exit code, read from the process status |
| `18` files (copy A) and `12` files (copy B) | §5 | `find … -type f \| wc -l` over each copy's `output` |
| `1` line differs between v2 and v3 `report.md` | §5 | `diff v2/report.md v3/report.md` |
| `8,805,237` bytes, `04cc31be…6172d` | the header | `stat -c%s` and `sha256sum` over the material in the pilot workspace |
| `7` probes, all refused but the control | §7 | `run_probes.py`, one change per probe |
| `1` / `1` / `indeterminate` | §8 | `run_evidence_checks.py`, over the record `01a217a3-5845-78c6-a41f-e0093a0b7d2e` |
| `116` document witnesses passed | §9 | `pytest tests/test_external_path_references.py tests/test_no_reference_leakage.py -q` → `116 passed` |
| `269` tree witnesses passed, `1` failed | §9 | `pytest tests/test_external_path_references.py tests/test_no_reference_leakage.py tests/test_ci_shard_coverage.py tests/test_release_record.py tests/test_first_release_record.py tests/test_identifier_records.py tests/test_scaffolding.py tests/test_readme_accuracy.py -q` → the one failure is `test_core_resolves_inside_the_source_tree`, and it is the environment's (§9) |
| `19:38:47` (pilot database mtime), `12` files, `v1` and `v2` only | §10 | `stat`, `find`; the pilot workspace after every run in this record |

**The pilot's twelve exported files, measured again.** Every digest below was
recomputed from the bytes on disk, and every one of the twelve agrees with
the first-round record's §5 table.

| File | Revision 1 (bytes / sha256) | Revision 2 (bytes / sha256) |
|---|---|---|
| `report.json` | 1,461 / `29c7dcef…0757d6c` | 1,465 / `3904ea81…4cf266c` |
| `report.md` | 952 / `39ee5f9d…fc77472df` | 957 / `6ae84f37…291b9cf20` |
| `report.html` | 2,026 / `b9db579b…79a2e044` | 2,030 / `a84790f3…38e01c3b6` |
| `report.docx` | 37,264 / `a38dc313…3bdcbe90` | 37,266 / `080309ad…9e101c302` |
| `report.pdf` | 2,539 / `0398f01b…f895ee511` | 2,541 / `997750a3…c99e1501` |
| `report-manifest.json` | 502 / `b11dc789…f01c70ab` | 502 / `2c47914e…af63d07c` |

## 10. Where the material and the evidence are

- **The pilot workspace:** `E:/labcairn-local/pilot-ws`, unchanged. Its
  database still carries revision `0032`, its output area still holds exactly
  **12** files in `v1` and `v2`, and its database file's mtime is still
  2026-11-26 19:38:47 — before any run in this record. Every run that needed
  to write wrote to a copy.
- **The copies:** two workspace copies in the directory named
  `report-checks-2026-11-26` under `E:/labcairn-local/tmp` — `ws-copy-a`
  (revision 3 written) and `ws-copy-b` (refused, 12 files) — both outside the
  repository and both holding a copy of a workspace that holds real material.
- **The evidence:** the same directory — the three scripts and their three
  result files, including the refusal messages, which carry the pilot's
  prose and therefore stay outside the repository.
- **The external paths:** `docs/ci/external-paths.json` is the ledger of what
  under `E:/labcairn-local` a tracked file may name, and it already carries
  `E:/labcairn-local/pilot-ws` and `E:/labcairn-local/pilot-ws/labcairn.db`
  with the expectation `present`. This record names the same paths and adds
  no new one outside the repository.
- **The credential:** none was needed and none was read. No key is in this
  record, in the scripts, or in the evidence directory.

## 11. What this record is not

1. **It is not a second round.** Nothing was analysed, no claim was made, no
   model was asked and no suggestion was settled. The pilot's material was
   read by the product's own checking machinery and by nothing else.

2. **It is not coverage of the report checks.** Two of the five ran over an
   empty set (§6), the rendered forms were never opened, and the report under
   test is one claim and one citation. What this record establishes is that
   the mechanism exists, that the product's own command reaches it, that the
   gate refuses and writes nothing when the material is gone, and that each
   of the five checks reads what it claims to read.

3. **It does not stand in for the checks the first round still left out.**
   §8 closes §4.3's C1/C2/C3 for the one record this copy carries. It does
   not close §4.1 (the suggestion loop needs comments, and the copy has
   none) or §4.2 (the figure needs table cells, and the copy has none);
   those are facts about the copy, not about the checks.

4. **It changed nothing in the pilot.** Read-only engine, no rows written,
   no file added, no file removed, twelve files where there were twelve. The
   refusal in §5 was produced on a copy, and the copy is where the failure
   stays.

5. **It adds no test file, so the main session has nothing to register.**
   The behaviour measured — the route refusing a report the ledger does not
   support, and writing nothing when it refuses — is already witnessed at the
   application, API and CLI layers. The gap this record names in §2 is a
   **missing route**, not a missing witness: there is no command that checks
   an export that already exists, and a witness for an absence is not a
   witness.

6. **It is not a verdict on the product.** The mechanism is present,
   reachable, load-bearing and refuses correctly. What it lacks is a route
   that checks an export that already exists (§2) — a seam a caller has to
   open for itself. This record names the seam and does not close it.
