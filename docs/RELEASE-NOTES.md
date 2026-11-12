# LabCairn — Release notes

**Version:** 0.1.0 (`pyproject.toml`) · **Status:** unreleased — no tag has
been cut · **The tree this describes:** `main` at
`e13b967`, 2026-11-02

**Items below dated 2026-11-03 are measured on the branch that has not
landed** (`docs/debt-closures` at `bb8f8f6`, pull request #146 open). Their
numbers belong to that tree and to the commit each of them names; they are
not claims about `main` until the merge.

> **The clause above is a dated snapshot from 2026-11-03, kept as written, and
> its last sentence is no longer true.** Pull request #146 **merged** on
> 2026-11-04T19:19:22Z as `384eb2f3a6c8a3f340dde625927bd8dbe9cf750c`, an
> ancestor of `main` (`gh pr view 146 --json state,mergedAt,mergeCommit` on
> 2026-11-12 → `MERGED`; `git merge-base --is-ancestor bb8f8f6 HEAD` → exit 0).
> So **the 2026-11-03 numbers *are* claims about `main` today**, and they belong
> to `bb8f8f6` in the sense that a measurement belongs to the commit it was taken
> at, not in the sense that the trunk lacks them. Read the quarantine as history:
> it was accurate for one day.

**Every limitation below names the document that measured it, and each of
those documents names its own commit.** A number belongs to the commit it
was measured at.

**This is an unreleased private preview.** No tag has been cut. LabCairn
original code is granted under MIT by the root `LICENSE`; see §4 for the
third-party notices and the remaining owner-side credential. If you are here
to decide whether LabCairn is worth using, **read §2 first**: it is the
larger half of this document.

---

## 1. What this release is

LabCairn is a **local-first AI research workspace** under construction. This
alpha hands over what exists, measured rather than asserted:

- a **CLI** (`labcairn`), a **local API service** and a **React workbench**,
  all three on one application layer;
- **material ingestion** for text PDFs, Markdown, TXT, CSV and XLSX, with
  **locators** — a page, a line and a section, a row and a column, a sheet
  and a cell — and content hashes;
- an **evidence ledger** with a store, an index, four working checks and a
  gate that refuses as a whole;
- **bounded deterministic analysis** and a **deterministic figure** whose
  editable source is a three-part recipe with no script beside it;
- a **report path** that renders one document into Markdown, HTML, DOCX and
  PDF, with revisions and staleness;
- **the mentor-trajectory line** — a **feedback chain** whose four rings are
  a comment, a change, a judgement and an assessment; a **rule memory** whose
  rules are versioned rows — readable **at the version a citation names** and
  not only at the newest, since a superseded row keeps the state, the sources
  and the checks it had — which **learns a rule from a comment or from a
  tracked change** — so a marked-up manuscript holding hundreds of revisions
  and no comment is material a rule can be drawn from, and the case's key is
  the product's, not the caller's — and whose retrieval serves a rule on the
  sources that stand: for a comment, the ones a judgement says were answered;
  for a revision, the change itself, which carries no answered judgement to
  wait for; **a three-role loop** that writes a guidance card and has it
  critiqued independently; and **a DOCX reader** that reads revisions and
  comments out of the package itself, with locators.

**What a reviewer can do with it:** follow the
[quickstart](QUICKSTART.md) from a clean clone and get a report with source
locators and an evidence ledger, a revision, and a reopened task. That path
is a **script whose exit code is the assertion**, and it is run by a test on
every CI run.

**What this release is not:** a finished application, an installable product,
or an open-source distribution.

---

## 2. Known limitations

**These are the limits of this alpha, and every one of them is measured or
cited — not estimated.** Each names where the evidence is.

### 2.1 A figure takes two steps, and a claim is stated by the caller

**The report has three entries now.** `labcairn task report --path report` renders
it, and `POST /report` on the local service renders the same document through the
same layer operation and answers with the same model — so G4's exit test's
*"same versioned report"* is reachable from either surface, and a fresh
workspace's policy permits `report.render` (the registry binds it to output
roots, and the content checks — not the rule — decide whether a report may exist).
**The figure has three of its own**: `labcairn task figure`, `POST /analysis`,
and the workbench's **Figure** panel, all through the layer's `run_figure`.
`docs/QUICKSTART.md` §4.7 documents both; the README's command table predates
them and stays conservative rather than the commands being hidden.

**The workbench asks for it now.** `web/src/app/Workbench.tsx` has a
**Render the report** action that states the two claims the service takes no
default for and then reads the artefact list again rather than trusting the
receipt the POST handed back; its tests cover both the request and the refusal.

**What remains** is the gap in two shapes.

- **A figure needs a granted approval, not only permission.** `labcairn task
  figure` and `POST /analysis` reach the layer's `run_figure`, and the consent binds
  the recipe's path as well as the material, the operator and its parameters
  (ADR-0012 constraint 7) — so `task approval-request` and `task approval-grant`
  stand beside the run, and there is no one-command shortcut. **The workbench is
  one of the figure's entry points**, and it does not shortcut the chain either:
  its Figure panel builds the selection from the source the service reports, asks
  `POST /approvals`, leaves the question pending in the Approval panel, and draws
  with `POST /analysis` once the answer is granted. Two steps are the design.
- **A report is refused, not written, when the task has nothing to carry.**
  `labcairn task report` on a bare task answers
  `report_content_refused` and leaves the output area empty — the correct
  behaviour. **The success path is a surface's now**: `labcairn task claim`
  records a claim, `POST /claims` does the same over the service, and the
  report that rests on the record is the next command or request (§2.2). The
  bytes the CLI and the service produce are still compared where a report
  exists, in `tests/test_smoke_path.py`.

*Evidence:* [LC-P1-14 acceptance record §7.1](acceptance/LC-P1-14-outsider-path.md)
(written when neither entry point existed) ·
`tests/test_cli.py::test_task_report_refuses_a_task_with_nothing_to_carry_and_writes_nothing` ·
`tests/test_api.py::test_a_report_render_with_the_token_reaches_the_layer_and_reports_its_reason` ·
`docs/QUICKSTART.md` §4.7.

### 2.2 A claim is recorded by the product, but not proposed by it

**The product writes evidence records and anchors now.** The layer's
`record_claim` writes an anchor — bound to the source's current hash and to
the text at the address — and an `extracted` record that names it, in one
commit. The addresses come from `list_source_addresses`, the ledger's own
account of what the ingestion read. Both are on the surfaces:
`labcairn task claim` and `POST /claims`; `labcairn sources addresses` and
`GET /sources/{source_id}/addresses`. The outsider walk records its three
claims through the operation instead of writing the ledger's rows itself.

**What the product still does not do is decide what the material says.** The
caller names the address and supplies the span, the value and the unit;
`record_claim` locates the address, refuses one nothing answers, and writes
the record — it does not extract a claim, and it does not accept a model's
proposal (`created_by` is `user`). Nor does it verify: the records it writes
are `extracted`, and C1, C2 and C3 remain separate acts that no surface runs
in this alpha.

*Consequence:* a report can be produced end to end from a product-written
record, and the witness is a surface's own path rather than the
demonstration's. A model-driven extractor is still not demonstrated.
*Evidence:* `tests/test_application_evidence.py` ·
`tests/test_cli.py::test_task_claim_makes_the_task_reportable` ·
`tests/test_api.py::test_a_claim_recorded_through_the_service_makes_the_task_reportable` ·
[acceptance record §7.3](acceptance/LC-P1-14-outsider-path.md).

### 2.3 The report's second revision is not recomputed from the revised material — closed 2026-11-02

A revision **was** generated, and v1's bytes were unchanged afterwards, but
the attempt to render the report again from the revised bytes was **refused**:

> the report was refused before it could be written as a revision: the chain
> names 'materials/measurements.csv' twice with different hashes.

**Closed by carrying only the parts computed over the current material.** A
report's document gathered every figure the ledger held; after a re-ingest
the old figure and the new one both remained, naming one file under two
hashes. The document builder now leaves out a figure or a table whose own
``derived_from`` names a material hash the source row no longer records — the
stale part is a record of an earlier run, not a part of this report. The chain
then names one material under the hash the ledger holds now, and the second
revision is recomputed from the revised bytes. The old part stays in the
ledger, and v1's bytes stay untouched.

*Consequence:* the second revision's figures and tables rest on the material
the ledger holds now; its **claims** still rest on the records they were read
from, because the product does not re-extract a record from moved bytes —
that is the separate limit §2.2 names.
*Evidence:* `tests/test_application_layer.py::test_a_second_revision_is_recomputed_from_the_revised_material` ·
`tests/test_analysis_report_build.py::test_the_part_carried_is_the_one_computed_over_the_current_material` ·
[acceptance record §7.2](acceptance/LC-P1-14-outsider-path.md).

### 2.4 The workbench has never run against a real service

Every web test stops at the `fetch` boundary, against a fake. The G4
demonstration drives the service through an in-process ASGI transport — not
a browser — and reads `GET /task` and `GET /artifacts`.

*Consequence:* "CLI and UI show identical Task state" is honoured **through
the API**, not measured between the two interfaces. **This document does not
make the browser claim.**
*Evidence:* [threat model §6.1](THREAT-MODEL.md) ·
`web/src/test/fakeApi.ts` · `examples/g4_exit_demo.py:1216-1221`.

### 2.5 The workbench does not consume the API's event stream — closed 2026-11-02

~~By decision: `web/src/api/paths.ts:14-21` names the omission explicitly —
*"The event stream is not among them. The service offers `/events` and
`/events/stream`, and the workbench reads neither."*~~

**Closed by `37591c7`, and the quotation this limitation rested on is now the
opposite of itself** — `paths.ts` reads *"The event stream is among them, and
it is a second way to read the same log, not a second source of truth."* The
workbench reads the SSE body with the client's own `fetch` in
`web/src/api/events.ts`, never `EventSource`, so the path check, the base and
the token boundary stay in the client; it resumes from each page's
`next_after_seq`, and it says whether the reading is going.

**The record lagged the tree by one day and nothing caught it:** the commit
that closed the limit rewrote [threat model §6.2](THREAT-MODEL.md) and its
C14 row, and left this section quoting the file's superseded words. A limit
that names a quotation as its evidence names a thing a later commit may
reverse, which is why the row is struck rather than deleted.

*Consequence, then:* a change that alters the event stream alone will not show
up in the workbench. *Consequence, now:* the stream is a second reading of one
log, so a change to it shows in the events panel and not in the state panel —
**the two panels are the check that they were not confused.**
*Evidence:* `web/src/views/EventsView.test.tsx` — draws what the service sent
and says the stream is live, resumes from the cursor after a disconnect and
draws no event twice, says it is disconnected rather than showing a stopped
clock, keeps what it read when the connection is lost, waits on the service
rather than inventing an empty log.

### 2.6 The workbench cannot switch the selected project — closed 2026-11-02

~~**Because the API has no such operation.** The service's routes are reads of
one bound workspace plus four mutating consent routes; none selects a
workspace. The CLI can.~~

**Closed by `37591c7`.** `POST /task/select` (`src/labcairn/api/routes.py:273`)
moves the workspace's `current_task` through a host-supplied port; the task is
validated through the application layer before anything is written, and the
route needs the session token like every other change. The CLI and the page are
now about the same task because there is one operation that says which task it
is.

*Evidence:* `tests/test_api.py` — `test_selecting_a_task_binds_the_service_to_it`,
`test_selecting_a_task_from_a_foreign_origin_is_refused`,
`test_selecting_a_task_needs_the_session_token`,
`test_an_unwired_selection_refuses_rather_than_pretending` ·
`web/src/app/workbench.test.tsx` ·
`tests/test_workbench_live_service.py`, which drives one service over httpx's
in-process ASGI transport and the console script in a subprocess and compares
`GET /task` with `task status --json`.

### 2.7 The real-provider smoke runs only where a credential is named

**No required check holds a credential, and none ever will**, and Phase 1
configures no provider — `labcairn doctor` reports an empty provider list on a
fresh workspace. The in-suite witness is
`tests/test_real_provider_smoke.py::test_real_provider_smoke_records_capabilities_and_usage`:
it **skips** unless the owner names a credential and a model through
`LABCAIRN_PROVIDER_SMOKE_KEY` and `LABCAIRN_PROVIDER_SMOKE_MODEL` (optionally
`..._PROTOCOL` and `..._BASE_URL`), and a key that merely happens to be in a
developer's environment does not enable it. The rule that decides whether it
runs is tested in `tests/test_provider_credentials.py`, filed under the unit
class — a gate that is only checked inside the class it gates is a gate no
offline run verifies.

**It has run.** Twice, on 2026-10-28, on a credential the owner supplied for
this purpose: model `MiniMax-M3.1-Flash`, protocol `anthropic`, endpoint
`https://api.minimax.cn/anthropic`. `tool_calls` **ok**, `usage_reporting`
**ok**, `structured_output_native` and `structured_output_prompted`
**unsupported** — pydantic-ai's profile declines before a request leaves the
machine, so those two say nothing about the endpoint and §2.14 keeps its
meaning. The two records differed only in `observed_at`.

*Consequence:* **the fifth of the protocol's five mandatory gate classes is not
a witness the required checks produce.** `docs/EVALUATION.md` says
*"Mock-only success is insufficient"*. The default harness run still reports the
class **NOT RUN** and exits 2, because no required check holds a credential — and
one never will: a check that runs only where a secret exists is a check branch
protection would wait on forever, which is exactly what amendment C-1 refuses to
paper over with a filter. The credential lives in the repository now, and
`.github/workflows/provider-smoke.yml` is the job that spends it, on a schedule
and on demand. **It has run there**: dispatch 40663728369 at `0adfbe3` completed
green on 2026-10-28 09:22 UTC, and the record it printed carries the same
endpoint fingerprint as the two local runs above — `db47efa5…385c`, `tool_calls`
and `usage_reporting` ok, both structured-output forms unsupported at the client.
GitHub masked the key as `***` in the log, which is the only place the run could
have shown it.

> **Denominator note (added 2026-11-12).** "The credential lives in the
> repository" means **one GitHub Actions secret**, not a tracked key:
> `gh api repos/gg320324492-lgtm/labcairn/actions/secrets --jq '.total_count'`
> → 1 (exit 0), while `git ls-files | grep -iE
> 'credential|api_key|secret|\.env'` names `.env.example`,
> `src/labcairn/providers/credentials.py` and two records, and no key.
> `docs/QUICKSTART.md` §2 says "there is no credential in this repository"
> about the **tracked files of a local clone** — a different object with the
> same noun. Neither statement is false, and neither implies the other.

**What changed on 2026-10-28, besides the file:** the harness used to refuse the
class even when a reader named it — `--classes real_model_smoke` printed the
runnability table's sentence about the environment without looking at the
environment, so the class was not skipped but **unreachable by any invocation**.
Naming it now runs it. Measured the same day: without a credential the run says
`0/1` and quotes the witness's own skip reason and exits 1; with the owner's
credential named it says **`1/1`**, and the command's exit is still 1 because a
single-class run evaluates none of the blocker witnesses — which is that run's
honest answer, not a failure of the class.
What changed is the kind of the gap: it was *"there is nothing to run"* — the
manifest named a witness file for two gates that no commit ever wrote — and it
is now *"the thing to run needs a secret this repository does not hold"*, which
is answered by adding one, not by writing code. **Ruled 2026-10-28 (§1.4.2):** the
credential has been added, and the owner accepts the scheduled/dispatched
`provider-smoke.yml` as this gate class's discharge. The default required-check
path reports NOT RUN offline and always will — a check that runs only where a
secret exists is a check branch protection waits on forever, and amendment C-1
forbids dressing that up with a path filter. **The class is discharged; the
sentence "the required checks prove it ran" is false, and stays so.**
**The clause and the class are not the same thing, and this row once conflated
them**: LC-P1-03's acceptance *"real smoke on at least one provider"* **was met
once, by hand** — `b237751`, 2026-10-16, on a credential the owner supplied
against a live Anthropic-protocol endpoint, which is where the
`tool_calls`/`usage_reporting` results on the status board come from. A probe
that ran by hand is not a gate class that runs on every commit, and the 2026-10-28
runs are the same half of that distinction — now with a file in the suite that a
credential can turn on.
*Evidence:* [threat model §6.7](THREAT-MODEL.md) ·
[evaluation protocol §"Mandatory automated gates"](EVALUATION.md) ·
[the gate's exit-test table](acceptance/G5-acceptance.md).

### 2.8 The competitor baseline has not been run

The protocol permits a comparison only on like-for-like matched tasks with
verified capabilities and documented confidence intervals. **No comparison has
been made**, and none is presented here. `docs/EVALUATION.md` is explicit
that a comparison that is not like-for-like is a number in a document, and
this repository does not ship those.

*Consequence:* **no claim of superiority over PaperQA2, PaperSpine or any
other product is made anywhere in this repository.**
*Evidence:* [evaluation protocol](EVALUATION.md) ·
[LC-P1-13/14 task breakdown §1.4.3](plans/LC-P1-13-14-task-breakdown.md).

### 2.9 G1's and G2's work orders have no independent review

Both gates were verified by **internal cross-validation** — a reviewer who
did not implement the work, but who was inside the project. G3 and G4 had
more: a review at a named commit, by reviewers who wrote none of the gate's
fixes, who broke each fix in turn.

*Consequence:* two rows of the work-order board say "accepted" on evidence
the board's own rule does not accept. **This is stated on the rows, not left
implicit.**

**Ruled 2026-10-28.** The two rounds of retro-review this branch ran against
G1 and G2 were performed by AI agents that wrote none of the fixes — the
independence is **procedural, not human**. The owner accepts those reviews as
closeout evidence for Phase 1: the findings were worked through and the
record/code contradictions they surfaced are corrected on this branch. The
board's rule — an independent review at a named commit by a party that wrote
none of the fixes — **is not thereby discharged for G1 or G2**; a human
independent review of those two gates remains an open follow-up, not a
completed item. What changed is what Phase 1's handoff *claims*: the AI review
was real, the corrections it caught landed, and the rule it does not satisfy is
named as still open rather than papered over.

*Evidence:* [threat model §6.6](THREAT-MODEL.md) ·
[docs/README.md](../docs/README.md) §"Division of responsibility".

### 2.10 Phase 1 is local single-user

The service binds loopback, which keeps a **network peer** out. It does not
keep a **local process** out: the workspace files, the session-token file
and the SQLite database are readable by whatever runs as the same user.

*Consequence:* a provider key in an environment variable is readable by any
local process. The product reads it from where the operator put it; it
cannot change that.
*Evidence:* [threat model §6.10 and §8 R1–R2](THREAT-MODEL.md).

### 2.11 The path guard's refusal set is platform-dependent

For **backslash spellings**, `..\sources\paper.txt` is refused on Windows
and admitted on POSIX, where a backslash is an ordinary filename character.

*Consequence:* **containment holds on both** — the admitted write lands
inside the task's output area and the source material is untouched. This is
a difference in *how many spellings are refused*, not an escape. The
document does not quote a number for the refused set.
*Evidence:* [threat model §1.3a and §6.11](THREAT-MODEL.md).

### 2.12 Two limitations in the product's own code, both now closed

- ~~**`ArtifactLedger` is in memory** — so the ledger does not survive a
  process restart the way the SQLite store does.~~ — **closed since the
  gate.** `SqliteArtifactLedgerStore` records every entry in
  `artifact_ledger_entries` (migration 0022), and a new instance on the same
  database loads the stored artifact and re-checks its digest. Witnessed by
  `tests/test_artifact_ledger_persistence.py`; see
  [LC-P1-06-artifact-ledger](acceptance/LC-P1-06-artifact-ledger.md). The
  in-memory default remains for callers that do not pass a store.
- ~~**`ApprovalLedger.consume()` does not resolve the capability against the
  registry**~~ — **closed since the gate.** `consume()` asks the registry and
  refuses an id it does not hold with `capability_unregistered`
  (`src/labcairn/security/approval.py:215-222`), a reason of its own rather
  than `args_changed`, so the remedy it names is the true one. Witnessed by
  `tests/test_security_approval.py::test_an_unregistered_capability_is_refused_before_the_grant_is_spent`
  and `::test_a_grant_bound_to_an_unregistered_capability_cannot_be_consumed`.

*Evidence:* [threat model §6.12](THREAT-MODEL.md).

### 2.13 `httpx` is not a declared dependency

It arrives transitively through `pydantic-ai`, and both the credentials and
the provider-factory modules flag this. A transitive dependency's version is
not this project's to pin, and it is not.

*Evidence:* [threat model §6.8](THREAT-MODEL.md) ·
`src/labcairn/providers/credentials.py:36-40`.

### 2.14 Structured-output capability is unmeasured

Both probes fail in pydantic-ai's client layer **before a request is sent**,
so they say nothing about the endpoint.

*Evidence:* [threat model §6.9](THREAT-MODEL.md).

### 2.15 The DOCX is byte-reproducible; the PDF is recorded, not claimed — DOCX closed 2026-11-02

A PDF carries a creation date and a document id from the render, and the
owner decided on 2026-10-20 (the breakdown's §1.4.3, Option A) that its
bytes are recorded but **not claimed reproducible**: pinning the creation
date would be a false statement about when the file was made. That decision
stands, and the PDF is not changed.

The DOCX is now reproducible. python-docx writes a ZIP whose entries carry
the writer's clock; after it saves, the package is rewritten once with every
entry stamped at the report's own ``as_of`` — the same date ``core.created``
and ``core.modified`` already carry, and the date the document states on its
face. Entry order, bytes, compression and attributes are preserved. Two
renders of one document are byte-identical; a different moment or different
content renders to different bytes. The report's own notice says so.

*Evidence:* `tests/test_analysis_report_render.py::test_the_docx_is_byte_reproducible` ·
`...::test_the_docx_bytes_change_with_the_document` ·
`...::test_the_pdf_is_not_byte_reproducible` ·
[acceptance record §6](acceptance/LC-P1-14-outsider-path.md).

### 2.16 Rotated PDF text is not detected, and the two-column detector is bracketed

A rotated page would extract in the wrong order and nothing would record it.
The two-column detector is bracketed against **single-column** fixtures; the
coverage band below its threshold is stated in the ADR and in the adapter's
own docstring, and **cannot be closed with this signal**.

*Evidence:* [docs/handoff/CURRENT.md](handoff/CURRENT.md) §"Carried
limitations" · `docs/adr/ADR-0008-pdf-ingestion-library.md`.

### 2.17 A read took SQLite's write lock — closed 2026-11-02

`src/labcairn/db/session.py` opened every transaction with `BEGIN IMMEDIATE`. That
is right for a write; a read is a transaction too, so a read took the write
lock for as long as it was open. The per-request session bounded that window
to one request.

**Closed by a read-only engine.** A read-only engine opens a plain deferred
`BEGIN` and sets `PRAGMA query_only=ON`; the CLI's four read commands use it,
and the write engine still opens `BEGIN IMMEDIATE` before its first read
(ADR-0003 C3). Measured behind a held writer: the read went from failing after
0.40025 s with `database is locked` to completing in 0.00015 s.
[LC-P1-06 read-lock record](acceptance/LC-P1-06-sqlite-read-lock.md).

### 2.18 A surface can enter doubt and refuse, but it cannot finish the bookkeeping

### 2.19 The mentor's own material is in the chain, and it says something narrow

**The rule memory serves nine rules, out of twenty-four confirmed and one
candidate.** That is re-measured at `00a8072` through the product's own doors
against a read-only copy of the pilot store, and the store came back
byte-identical afterwards — the count this section first carried, **three of
eighteen**, was the pilot's alone and had been overtaken by the second, third
and fourth corpora. The retrieval serves a
confirmed rule on the sources that stand, and the owner's own judgements on
the pilot's ten correspondences came back **two holds, eight does not** —
so of the sixteen rules learned from comments, **one is served and fifteen
are reported as unserved**. **That is the material's answer, not a
defect**: of the mentor's forty-six comments on the first paper, the ones a
later version really answered are few. **A memory that served all of them
would be serving rules the chain cannot show to have been applied.**

**The other two served rules are the third pilot's, learned from tracked
changes, and they are served on a different ground.** A comment source
carries an answered judgement and can stop standing when the judgement says
it was not answered; **a revision source has no answered judgement to wait
for** — its source is the change itself, so it stands while the chain holds
the change and the reader may read the manuscript. Read back through the
product's own doors at `7677e59` on 2026-11-03: **24 confirmed rules and one
candidate; 9 served and 15 reported as unserved.** The nine are **the eight
learned from tracked changes plus one from the first corpus** — every rule
whose sources stand — and the fifteen are comment-derived rules with **no
answered judgement on their sources**, which is the material's answer rather
than a defect.

**Which is worth stating plainly as a limit of the material, not of the
code:** a rule learned from a comment must survive the question *was this
answer?*, and a rule learned from a change does not. The second is easier to
serve and, for that reason, weaker as evidence — the chain shows the mentor
wrote something, and shows no later draft agreeing with it.
[LC-P2-09 acceptance](acceptance/LC-P2-09-acceptance.md) §9 ·
[the second corpus](acceptance/second-corpus-absorption.md) ·
[the revision distillation](acceptance/LC-P2-11-revision-distillation.md) §6.

### 2.20 The second paper's rules are not in the chain's reach

**The second pilot project has three versions and no version edge**, because
the material does not say which came first and the chain does not order
what it cannot order — and **a change travels an edge**, so the operation
that records a change refuses every version in it. **Its eight rules are
therefore unserved, and the memory reports them.** **This is a material
gap and not a product one**: it is closed by material, not by code.

### 2.21 The phase's exit gate has no denominator

**The exit gate is *"measured capability gain against a frozen P1
baseline"* — and there is no baseline document in the tree.** The harness
can read one (`evaluation.comparison.load_baseline`) and nothing supplies
it. **So the phase cannot be closed by measurement today**, and the
comparison that would close it — the three tasks against selected upstream
systems — has not been run either.
[the phase's one work order](plans/PHASE_2-work-orders.md).

### 2.22 The reader records one change twice in one file

**On one version of the pilot's first paper the reader reports 243 changes
and there are 239** — four are read a second time. **The chain does not
lose anything**, because a revision event's id is derived from the
element's path and the second reading lands on the row the first one
wrote. **But the assumption that id rests on is false as written** — the
element's path is *not* unique inside a part — and it holds today only
because the four duplicates are the same change. **Two different changes
sharing a path would lose one of them silently.**
[LC-P2-07 fidelity baseline](acceptance/LC-P2-07-fidelity-baseline.md).

**Closed 2026-11-03.** The double-read that produced the 243 was fixed by
`f4a7e94` — that file now reads 239 events against 239 distinct addresses.
The identity no longer rests on the path at all: a change is keyed by
`(version, part, element_path, occurrence)`, the first change at an address
keeping the id every stored row already carries, so the 2164 pilot rows and
the rules bound to them do not move.
[LC-P2-07 revision-event identity](acceptance/LC-P2-07-revision-event-identity.md).


**The surfaces run the recovery pass now.** `run_stage` calls it after the policy
verdict and before any consent is spent, so a crash through the CLI or the service
leaves its operation `UNCERTAIN`, blocks the stage with the reason the recovery
layer states, and the next run is **refused** with `operation_uncertain` rather
than planning a second operation for the same work. Answering the doubt is the
operator's: `labcairn task reconcile <operation-id> --expected-sha256 <hash>`,
because the hash a probe needs lived inside `args_digest` — a hash of a hash — and
no stored row gives it back. A `CONFLICT` keeps the operation `UNCERTAIN`, keeps
the stage blocked and writes nothing to the path it probed.

*What remains:* the transaction the crash interrupted — confirmation, completed
stage, receipts, which the ADR's own boundary says are one fact — was never
written, and a reconciled `CONFIRMED` operation does not complete a stage. So the
run that follows performs the bookkeeping under **its own** operation: the effect
happened once, and the log holds two operation rows saying so.
*Evidence:* [ADR-0003 C2](adr/ADR-0003-event-and-permission-model.md) ·
`tests/test_application_layer.py::test_a_run_enters_uncertain_and_refuses_an_operation_a_crash_abandoned` ·
`tests/test_fault_injection_e2e.py::test_a_task_continues_from_what_was_recorded_after_a_crash`.

### 2.23 The largest file the product will read is one number, written once — with one split kept on purpose

**Measured 2026-11-03 at `bb8f8f6`, single-sourced at `7e94338`.** The ceiling
on a supplied manuscript is **96 MB**, and the number came from material rather
than from taste: the third pilot's late drafts are **71.4 MB** and the previous
64 MB ceiling refused **seven versions of one real manuscript** — the refusal
came from the read limit, and the pilot could not be ingested until it moved.

**It was spelled in five places and it is now spelled in one** —
`security/capabilities.py`, the module both read doors and every papers module
already import, so the change adds no edge and no cycle.
`workspace/readonly.py` re-exports it and both of its doors take it as their
default; `papers/feedback.py` and `papers/replies.py` alias it under the name
their callers already use. **One literal remains**: `papers/revisions.py` still
writes `MAX_MANUSCRIPT_BYTES = 96_000_000`, because the window doing the work
was told not to edit that file, and a boundary in a task brief is not
something the runner of the task gets to dissolve. It is **neither hidden nor
loose**: the scan witness asserts the ceiling's digits appear in **exactly
those two files** and **once in `security/capabilities.py`** — so a *third*
file, or a doubled definition in its home, turns it red — and the kept copy is
pinned to the same value by `test_the_manuscript_readers_share_the_one_ceiling`.
**And the gap that existed here for a few hours is closed, which is worth
recording as the shape it took.** The set assertion alone allowed that file to
hold the digits **twice** — measured: a second literal planted inside
`papers/revisions.py` left **every** ceiling witness green, because the set of
files was unchanged and the value still equalled the ceiling. The count is now
pinned per file (`spelled["papers/revisions.py"] == 1`), and the same mutation
turns exactly that one witness red. **A witness that pins a set is not a
witness that pins a count**, and the difference only shows when the second
copy is added inside a file already on the list.

**And a claim this section used to make was wrong, so it is replaced with what
was measured.** The earlier text said that raising the read doors past 64 MB
would make an `fs.read` approval ask for more than the capability schema
allows. **No path in the tree does that**: all seven approvals that carry the
ceiling carry `CapabilityId.SOURCE_READ`, whose `max_bytes` bound is 512 MB
and so admits 96, and every `fs.read` site passes only a path or nothing —
`read_artifact`'s two real callers omit `max_bytes` and take its 1 MB default.
The 64 MB bound on `FsReadArgs` is therefore **not** a ceiling in the same
sense, and it is now asserted as a deliberate split: widening it onto the
manuscript ceiling would make every artefact read approvable at a size its own
capability never offered
(`test_an_artefact_read_may_not_be_approved_at_the_manuscript_ceiling`).

**What the real coupling is, in the direction the old text had wrong.** The
ceiling is sent *into* `SourceReadArgs`, so a ceiling above the schema's bound
would have every one of those seven approvals refused **at consent time** — the
read would never be reached. That is the invariant the split protects, and
`test_the_source_read_schema_admits_the_ceiling` now holds it. Three mutations
were run against these four witnesses, each caught by the one that names it:
re-spelling the literal in `readonly.py`, widening `FsReadArgs` onto the
manuscript ceiling, and moving `SourceReadArgs`' default off it.

**One consequence of the move, stated because it is data and not code.** The
pilot database holds **20 `granted` `source.read` approvals whose arguments
digest over the old 64 MB ceiling** — recomputed with the product's own
`compute_args_digest` over the stored task, capability and resource, all 20
match `path + max_bytes=64_000_000` and none matches 96. Nothing breaks today
because the papers only *evaluate* consent and never spend a stored grant; but
those rows describe a request the product no longer makes, and **a future
pilot run re-requests them rather than reusing them.**

*The measurement:* `src/labcairn/security/capabilities.py`, the docstring over
`MAX_SOURCE_READ_BYTES` · *the witnesses:*
`tests/test_workspace_boundaries.py::test_a_file_over_the_ceiling_is_refused_by_both_read_doors`
and `::test_both_read_doors_default_to_the_one_ceiling` (the two doors), plus
`::test_the_ceiling_is_written_once_in_the_product`,
`::test_the_manuscript_readers_share_the_one_ceiling`,
`::test_the_source_read_schema_admits_the_ceiling` and
`::test_an_artefact_read_may_not_be_approved_at_the_manuscript_ceiling` (the
single source, the kept literal in `papers/revisions.py`, the schema's bound,
and the split that is kept) ·
[LC-P2-11 revision distillation](acceptance/LC-P2-11-revision-distillation.md) §6.

---

## 3. What the evidence does **not** establish

**These are limits of the handoff itself, and they are stated here rather
than left for the next reader to find.**

1. **No CI workflow runs `pnpm format:check`.** The README documents it, and
   the `web` workflow runs install, typecheck, lint, test and build. The
   Python suite runs it only on a machine that has pnpm, which a runner does
   not. *Evidence:* [acceptance record §7.8](acceptance/LC-P1-14-outsider-path.md).
2. **The quickstart's command list is not watched.** Nothing asserts that the
   commands on the [quickstart](QUICKSTART.md) and the ones in the README's
   table are the same set. The README's table *is* fail-closed in both
   directions against `scripts/outsider_path.py`'s; the quickstart's is not.
   *Evidence:* [quickstart §8](QUICKSTART.md).
3. **The two witnesses for the Windows short-name property skip where the
   volume makes no 8.3 short names.** The path layer's fix for the 8.3
   short-name trap is real: a new file declared with the short spelling
   under a long-spelled root is **accepted**, with the key
   `outputs/summary.md`, exactly as the long spelling is. **The witnesses are
   sound** — they use `RootKind.OUTPUT`, and the `AttributeError` an earlier
   draft of them raised is gone. But they **skip on a volume that generates
   no 8.3 names**, and that is the volume this machine's temporary
   directory is on. **On a runner whose volume does generate them — the CI's
   Windows runner — they run, and they pass.** So the property **is** watched
   where the platform can watch it, and it is **NOT MEASURED on a
   development machine whose volume makes no short names.**
   *Measured on 2026-10-25 on the **C:** volume, which does generate 8.3
   names: the product's own `canonicalize` accepts both spellings with the
   same key, and `examples/g1_exit_demo.py` under a short-spelled `TEMP`
   exits 0 with its 36 checks — measured by this gate's independent review
   ([`g5-review-records.md`](acceptance/g5-review-records.md) §10.3) — and
   on the CI's Windows runner, where the two witnesses run and pass. The two
   witnesses are
   `tests/test_security_paths.py::test_a_new_file_under_a_short_spelled_root_is_not_refused`
   and `::test_a_path_outside_a_short_spelled_root_is_still_refused`.*
4. **The old placeholder predates the decisions it described.** It named
   the PyMuPDF question as unmade; [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md)
   chose `pdfplumber` and `pdfminer.six`, both MIT, on 2026-10-17, and the
   owner confirmed the copyright holder and authority to grant MIT on
   2026-11-06. The placeholder was deleted in the same commit as the root
   `LICENSE` was added. This paragraph is a historical note, not the
   current licensing statement; §4 is current.

---

## 4. Licence and security status

**LabCairn original code is granted under MIT.** The root `LICENSE` is the
grant and names `Copyright (c) 2026 Tonghe Du`; `pyproject.toml` declares
the SPDX identifier. The owner confirmed the copyright holder and authority
to grant it on 2026-11-06.

- `NOTICE` records third-party material and grants no rights by itself.
- A built wheel carries `licenses/LICENSE` and `licenses/NOTICE`; the
  release workflow and its witness watch the member list.
- The dependency review is recorded in [ADR-0008](adr/ADR-0008-pdf-ingestion-library.md):
  `PyMuPDF` is not in the dependency graph.
- Third-party adaptations must retain required notices and comply with
  their own licences.

**The security posture** is written down in the
[threat model](THREAT-MODEL.md): six faces — writes, reads, network,
credentials, crash and concurrency — and a larger §6 of what the product
does **not** claim. Every claim it makes that a machine can check has a
witness in `tests/test_threat_model.py`, which also checks that every
`path:line` citation in the document resolves.

**Third-party material in this repository.** The paper fixtures under
`tests/fixtures/papers/` are three arXiv papers, **CC BY 4.0**, and their
attribution is [`tests/fixtures/papers/MANIFEST.md`](../tests/fixtures/papers/MANIFEST.md).
The public fixture corpus under `tests/fixtures/public/` is **entirely
synthetic** and says so inside every one of its files. The
[font audit](acceptance/LC-P1-14-font-licence-audit.md) measured that **no
third-party font file reaches any artefact**.

---

## 5. Provenance

Everything in §2 was measured against a named commit, and each citation
names the document that carries it. The versions below are this machine's:

| | |
|---|---|
| Commit measured | `dd08573650dd28b433c3aac387d88b4b71912cdc` (`main`, 2026-10-25) |
| Python | 3.12.13, pinned by `.python-version` |
| uv | 0.11.21 |
| Node | v24.16.0 · pnpm 9.15.9 — the versions `web/package.json` declares |
| Platform | Windows 11 Pro 10.0.26200, x86_64 |

**The walk's measurement** — 115 checks, all held, in the reviewer mode,
including the whole test suite in a clean clone — is in
[the acceptance record](acceptance/LC-P1-14-outsider-path.md) with its
command lines, exit codes and seconds.

**The board says G5 is closed; this document says the exit test is not fully
discharged. Both are true, and the difference is the owner's to settle.**
G5's exit test is *"outsider fresh install, 3 fixtures, fault injection, docs and
real-provider smoke"*; **four of the five are delivered and watched**, and the
real-provider smoke (§2.7) and the competitor baseline (§2.8) have not run.
**This paragraph was written at `dd08573` (2026-10-25), when the gate was still
open.** The closure landed two days later at `ff9afc5` (PR #118), on two
independent reviews that wrote none of the gate's fixes, verdict **PASS WITH
NOTES** — the notes being exactly §2.7 and §2.8, and the four owner decisions
in [`acceptance/G5-acceptance.md`](acceptance/G5-acceptance.md).
**So nothing in this document may be read as a claim that the fifth clause ran.**
Whether a declared, reported skip of it releases the alpha as *"Phase 1 complete"*
is the task breakdown's §1.4.1b question, and it is the owner's ruling, not this
document's. **Both neighbours of that question are now ruled.** §1.4.2 was ruled
on 2026-10-28 — the scheduled `provider-smoke.yml` probe discharges the fifth
gate class, and the offline run still reports it NOT RUN. §1.4.1b was ruled on
2026-10-29: a skip whose reason names **a fact of the machine** no longer fails a
blocker, **any other skip does**, and the accepted ones are named in the row — a
witness case by its node id and pytest's own reason, a required CI test by its
file under the category it fell in. [The evaluation
record](acceptance/LC-P1-13-evaluation.md) carries the measured run, and the
[R5 gate](acceptance/G5-acceptance.md) carries the ruling.

---

## 6. Where to go next

- **[The quickstart](QUICKSTART.md)** — the path, from a clean clone.
- **[The threat model](THREAT-MODEL.md)** — what is protected, from what,
  and what is not claimed.
- **[The evaluation protocol](EVALUATION.md)** — the five gate classes and
  the six Phase 1 blockers.
- **[CHANGELOG.md](../CHANGELOG.md)** — what changed.
- **[The work orders](PHASE_1_WORKORDERS.md)** — the board, and its status.
