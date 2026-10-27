# LabCairn — Release notes

**Version:** 0.1.0 (`pyproject.toml`) · **Status:** unreleased — no tag has
been cut · **The tree this describes:** `main` at
`dd08573650dd28b433c3aac387d88b4b71912cdc`, 2026-10-25

**Every limitation below names the document that measured it, and each of
those documents names its own commit.** A number belongs to the commit it
was measured at.

**This is a private preview, not an open-source release.** The repository
carries **no `LICENSE` file** and no rights have been granted to anyone —
see §4. If you are here to decide whether LabCairn is worth using, **read §2
first**: it is the larger half of this document.

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
  PDF, with revisions and staleness.

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

### 2.1 The figure has no surface, and the report's surfaces are newer than the README's table

**The report has two entries now.** `labcairn task report --path report` renders
it, and `POST /report` on the local service renders the same document through the
same layer operation and answers with the same model — so G4's exit test's
*"same versioned report"* is reachable from either surface, and a fresh
workspace's policy permits `report.render` (the registry binds it to output
roots, and the content checks — not the rule — decide whether a report may exist).
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
  stand beside the run, and there is no one-command shortcut. **The workbench can
  draw no figure**: the route exists and no UI asks for the approval chain.
- **A report is refused, not written, when the task has nothing to carry.**
  `labcairn task report` on a bare task answers
  `report_content_refused` and leaves the output area empty — the correct
  behaviour, and the reason the success path is still the walk's (§2.2: the
  product writes no evidence record), not a surface's. The bytes the two surfaces
  produce are compared where a report does exist, in `tests/test_smoke_path.py`.

*Evidence:* [LC-P1-14 acceptance record §7.1](acceptance/LC-P1-14-outsider-path.md)
(written when neither entry point existed) ·
`tests/test_cli.py::test_task_report_refuses_a_task_with_nothing_to_carry_and_writes_nothing` ·
`tests/test_api.py::test_a_report_render_with_the_token_reaches_the_layer_and_reports_its_reason` ·
`docs/QUICKSTART.md` §4.7.

### 2.2 The claim in the report is written by the demonstration, not by the product

**The product has no operation that writes an evidence record or an anchor.**
The walk writes the claim's own address and the record that rests on it
itself, against the addresses the ledger holds.

*Consequence:* the report carries real claims, cited to real addresses in
the material the CLI ingested — **but the claims were made by the walk, not
by the product.** A product-shaped path that produces a claim from the
material is not demonstrated.
*Evidence:* [threat model §6.4](THREAT-MODEL.md) ·
[acceptance record §7.3](acceptance/LC-P1-14-outsider-path.md).

### 2.3 The report's second revision is not recomputed from the revised material

A revision **is** generated, and v1's bytes are unchanged afterwards. But the
attempt to render the report again from the revised bytes is **refused**:

> the report was refused before it could be written as a revision: the chain
> names 'materials/measurements.csv' twice with different hashes.

*Consequence:* **the second revision still rests on the material the claims
were read from.** The report's content is not recomputed from the revised
bytes.
*Evidence:* [acceptance record §7.2](acceptance/LC-P1-14-outsider-path.md).
**This is a Phase 2 finding, recorded rather than fixed.**

### 2.4 The workbench has never run against a real service

Every web test stops at the `fetch` boundary, against a fake. The G4
demonstration drives the service through an in-process ASGI transport — not
a browser — and reads `GET /task` and `GET /artifacts`.

*Consequence:* "CLI and UI show identical Task state" is honoured **through
the API**, not measured between the two interfaces. **This document does not
make the browser claim.**
*Evidence:* [threat model §6.1](THREAT-MODEL.md) ·
`web/src/test/fakeApi.ts` · `examples/g4_exit_demo.py:1216-1221`.

### 2.5 The workbench does not consume the API's event stream

By decision: `web/src/api/paths.ts:14-21` names the omission explicitly —
*"The event stream is not among them. The service offers `/events` and
`/events/stream`, and the workbench reads neither."*

*Consequence:* a change that alters the event stream alone will not show up
in the workbench.
*Evidence:* [threat model §6.2](THREAT-MODEL.md).

### 2.6 The workbench cannot switch the selected project

**Because the API has no such operation.** The service's routes are reads of
one bound workspace plus four mutating consent routes; none selects a
workspace. The CLI can.

*Evidence:* [threat model §6.3](THREAT-MODEL.md) ·
`src/labcairn/api/routes.py`.

### 2.7 The real-provider smoke has not been executed

**There is no credential for a real provider in this repository**, and
Phase 1 has no provider configured — `labcairn doctor` reports an empty
provider list on a fresh workspace. The smoke test exists
(`tests/test_provider_credentials.py:293`) and is **skipped**, with the
reason written down: it needs the project owner's explicit authorisation to
spend money and a credential supplied for that purpose.

*Consequence:* **the fifth of the protocol's five mandatory gate classes is
not discharged.** `docs/EVALUATION.md` says *"Mock-only success is
insufficient"*, and the standing witness has never run on any platform, so the
harness reports the class **NOT RUN** and exits 2.
**The clause and the class are not the same thing, and this row once conflated
them**: LC-P1-03's acceptance *"real smoke on at least one provider"* **was met
once, by hand** — `b237751`, 2026-10-16, on a credential the owner supplied
against a live Anthropic-protocol endpoint, which is where the
`tool_calls`/`usage_reporting` results on the status board come from. A probe
that ran once outside the harness is not a gate class that runs on every commit.
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

### 2.12 Two limitations in the product's own code

- **`ApprovalLedger.consume()` does not resolve the capability against the
  registry** — a defence-in-depth gap whose ordering constraint belongs in an
  ADR.
- **`ArtifactLedger` is in memory** — so the ledger does not survive a
  process restart the way the SQLite store does.

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

### 2.15 The DOCX and the PDF are not byte-reproducible

A DOCX is a ZIP whose entries carry timestamps and a PDF carries a creation
date. **The report's reproducible forms are Markdown and HTML.** The DOCX
and the PDF are compared as stored against served, not across two renders.

*Evidence:* [acceptance record §6](acceptance/LC-P1-14-outsider-path.md).

### 2.16 Rotated PDF text is not detected, and the two-column detector is bracketed

A rotated page would extract in the wrong order and nothing would record it.
The two-column detector is bracketed against **single-column** fixtures; the
coverage band below its threshold is stated in the ADR and in the adapter's
own docstring, and **cannot be closed with this signal**.

*Evidence:* [docs/handoff/CURRENT.md](handoff/CURRENT.md) §"Carried
limitations" · `docs/adr/ADR-0008-pdf-ingestion-library.md`.

### 2.17 A read still takes SQLite's write lock

`src/labcairn/db/session.py` opens every transaction with `BEGIN IMMEDIATE`. That
is right for a write; a read is a transaction too, so a read takes the write
lock for as long as it is open. The per-request session bounds that window
to one request.

*Evidence:* [docs/handoff/CURRENT.md](handoff/CURRENT.md) §"What does not
exist yet".

### 2.18 A surface can enter doubt and refuse, but it cannot finish the bookkeeping

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
4. **`LICENSE.PENDING.md` §6 predates the decision it describes.** It says
   the PyMuPDF decision "has not been made". It was made on 2026-10-17:
   [ADR-0008](../docs/adr/ADR-0008-pdf-ingestion-library.md) chose
   `pdfplumber` and `pdfminer.six`, both MIT, and **PyMuPDF is not in the
   dependency graph** — `pyproject.toml` names `pdfplumber`, not PyMuPDF.
   The README's licence paragraph and the notice agree with each other and
   both predate that decision. **The copyright question, which is the
   blocking one, is untouched by it.**

---

## 4. Licence and security status

**No rights have been granted.** The repository is public and readable, and
it deliberately carries **no `LICENSE` file**: copyright ownership has not
been cleared, so there is no licensor capable of making a grant. Until that
is settled, the repository is **all-rights-reserved by default**.

- `LICENSE.PENDING.md` **does not** grant rights and must not be read as an
  MIT grant.
- The absence of a restrictive `LICENSE` file is **not** permissiveness.
  Silence is not permission.
- MIT is the **planned** direction for original LabCairn code, contingent on
  the conditions in `LICENSE.PENDING.md` §5 — **ownership is the blocking
  one.**
- Third-party adaptations must retain required notices and comply with their
  own licences.

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
document's.

---

## 6. Where to go next

- **[The quickstart](QUICKSTART.md)** — the path, from a clean clone.
- **[The threat model](THREAT-MODEL.md)** — what is protected, from what,
  and what is not claimed.
- **[The evaluation protocol](EVALUATION.md)** — the five gate classes and
  the six Phase 1 blockers.
- **[CHANGELOG.md](../CHANGELOG.md)** — what changed.
- **[The work orders](PHASE_1_WORKORDERS.md)** — the board, and its status.
