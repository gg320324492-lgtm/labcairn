# LC-P1-11 and LC-P1-12 — Task breakdown

**Gate:** G4 (Usable application)
**Work orders:** [LC-P1-11](../PHASE_1_WORKORDERS.md) — report assembly, export
and artefact versioning · [LC-P1-12](../PHASE_1_WORKORDERS.md) — CLI and local
Web research workbench
**Status:** written, not implemented. **The four decisions in §1.4 were taken by the
owner on 2026-10-20**; each one is recorded below with what it costs.
**Date:** 2026-10-20

---

## 1. Goals and boundaries

### 1.1 What G4 must produce

From the two work orders:

> **LC-P1-11 — Build:** Markdown/HTML preview + basic editable DOCX and PDF,
> evidence citations and stable artefact manifest; linked chart/data notes;
> content verification separate from formatting/rendering. Revisions keep v1 and
> generate v2 without altering originals. Limit first-pass report format and
> explicitly say not journal-ready.
>
> **Acceptance:** exports are openable; numeric values agree with ledger,
> figures/captions intact, links resolve, output hash/lineage retained.
> Rerendering after material change invalidates stale output.
>
> **LC-P1-12 — Build:** Typer CLI for `init`, `doctor`, `task create/run/
> status/resume`, `sources inspect`, `artifacts list`; FastAPI localhost API
> with CSRF/origin/session guard and event stream; React UI for project
> selection, plan/steps, pending approval, source anchors, evidence status,
> artifacts/preview and revisions. CLI/API/UI call same application layer.
>
> **Acceptance:** clean clone developer launch with working smoke path; Web
> refresh recovers DB snapshot, no repeated operation; request approval cannot
> be spoofed from another origin; CLI and UI show identical Task state.

Concretely, by the end:

1. **A report document model** — the report's *content* as data: its sections,
   its claims, the ledger records each claim rests on, the figures it embeds and
   their captions. One model, several renderers.
2. **Renderers** that turn that model into Markdown, HTML, DOCX and PDF, with
   the numbers agreeing with the ledger and the figures and captions intact.
3. **A report artefact manifest** — the list of what a report is made of, with
   each part's hash and its lineage, so a report can be re-derived and a
   changed part can be named.
4. **Revisions** — v2 does not alter v1, and a report whose material has
   changed is marked stale rather than quietly re-rendered.
5. **One application layer** — the operations the CLI, the local API and the web
   UI all call, so that "CLI and UI show identical Task state" is a property of
   the code rather than of three implementations agreeing.
6. **A Typer CLI** and **a local FastAPI service with a React UI**, both
   behind that layer, both guarded: a local API on loopback still needs an
   origin restriction and a session.

### 1.2 Already done — removed from scope

- **The spine.** Versioned contracts, the permission boundary, the durable task
  store with crash recovery, material ingestion with locators, the lexical
  index, the evidence ledger, bounded statistics with a deterministic figure,
  and the reproducibility manifest are all merged and accepted (see
  [the G3 review](../acceptance/G3-acceptance.md)). G4 does not re-implement
  any of it.
- **The stage graph.** `labcairn.skills.declaration` already states the
  `intake → inventory → retrieve → evidence → propose → [approval] → draft →
  validate → deliver` flow **as data**, with typed ports and a digest. G4's
  report assembly consumes that graph; it does not re-declare a pipeline.
- **The artefact receipt.** `labcairn.reports.receipt.ArtifactReceipt` already
  reserves the kinds G4 needs — `REPORT`, `FIGURE`, `TABLE`, `DATASET`,
  `MANIFEST` — and carries `derived_from` and a paired `staleness`. G4 writes
  receipts, it does not invent a second artefact record.
- **The web baseline.** `web/` is a buildable, type-checked, unit-tested React
  skeleton. G4 replaces the placeholder with a product; it does not invent a
  build system.

### 1.3 Explicitly NOT in G4

- **A real provider.** The provider adapters and their truthful capability
  detection are LC-P1-02's, and are merged. G4 does not add a model call.
- **Journal-ready typesetting.** The work order says the first pass is not
  journal-ready, and this document keeps that: G4 renders a *report*, and says
  so on its own face.
- **A hosted or multi-user product.** The API is a local service on loopback,
  with a local session, and the UI is a local web app. There is no account, no
  tenancy and no deployment story.
- **Phase 2's upgrades.** Better citation identity, an analysis sandbox,
  higher-fidelity plots, editing, conditional reviewers and sub-agents are
  Phase 2 items — the roadmap says so, and G4 does not pre-empt them.
- **The fabricated-DOI clause.** It is LC-P1-09's and it is still open; see
  §1.4.1.

### 1.4 Four decisions the owner took, and what each one costs

These are the decisions that change what the work orders deliver, and each of
them has a cost that is not obvious until it is stated. **All four were taken
on 2026-10-20, and all four took the recommended option** — which is not
the same as the costs being free, and each cost is stated below.

#### 1.4.1 What a report may cite

**The facts, measured:** an `EvidenceRecord` carries no external identifier —
it binds to sources by `anchor_ids`, the extracted span, and the content
hash. The **source** model does have a place for identifiers
(`Source.identifiers`, of kind DOI, ARXIV, ISBN or LOCAL), and the values
are shape-validated and nothing more. But **ingestion records none** — the
PDF walk writes `identifiers=()` — and **nothing in `src/` resolves an
identifier to a source**. So an identifier in the model is a slot that nothing
fills and nothing checks, and LC-P1-09's *fabricated source fails* clause is
open for exactly that reason.

- **Option A — TAKEN (2026-10-20): a report cites locators only.** A claim's citation
  is *what the text said and where it was*: file, page, span, line or cell,
  with the content hash. A report never prints an identifier as if it were a
  citation, because nothing could verify it — and an unverified identifier is
  exactly the fabrication the clause refuses.
- **Option B — not taken.** G4 would have made identifiers real: Ingestion extracts them from the
  material, the report cites them, and the bibliography is CSL-shaped
  (`ARCHITECTURE.md` names pybtex for this). This closes the *fabricated
  DOI* half of LC-P1-09's clause — **but only if something verifies the
  identifier**, and a local-first system that does not transmit outward cannot
  resolve a DOI against a registry. An identifier extracted from a PDF is
  asserted by the PDF, and a fabricated PDF would assert a fabricated DOI.
  Verification would have to be *local*: the identifier resolving to the
  material that carries it, which is a locator in disguise.

*Cost of A:* the source model's `identifiers` slot stays empty, and a report
cannot be cited by DOI; the report says what it can support instead of
printing a plausible identifier. *Cost of B:* an ingestion change, a
bibliography dependency, and a clause satisfied only in the weaker sense —
the identifier resolves to the material that asserts it, not to anything
outside.

**Either way, one thing is true and must be said in the report's own face: an
identifier that came from the material is the material's claim, not the
report's.**

#### 1.4.2 What "the same versioned report" means for G4's exit test

G4's exit test is *"CLI and Web produce same versioned report"*.

- **Option A — TAKEN (2026-10-20): one renderer, and both surfaces serve the
  same bytes.** The report is rendered once into bytes; the CLI writes that file and
  the UI serves exactly those bytes. "Same" is **byte-identical**, and the
  acceptance test compares hashes.
- **Option B — not taken.** Each surface would have rendered its own copy: The CLI renders a file, the
  UI renders in the browser from the same model. "Same" is *the same content*,
  checked by comparing the two renderings' structure.

*Cost of A:* the UI cannot offer "regenerate and view" without asking the
server to re-render — which is fine, because the server is the only thing that
renders. *Cost of B:* two renderers that can disagree, and the exit test
becomes a comparison of two things rather than a hash ✓ — weaker, and it is
exactly the "one document, one meaning" the repository keeps insisting on.

#### 1.4.3 Whether the exports are byte-reproducible

A **DOCX is a ZIP** and a **PDF carries a creation date** and embeds subsetted
fonts. Both are containers with metadata that a naive exporter fills with the
current time, so by default **neither is byte-reproducible** — while Markdown
and HTML are.

- **Option A — TAKEN (2026-10-20): the report's reproducible form is Markdown and
  HTML; DOCX and PDF are exports whose bytes are recorded but not claimed
  reproducible.** The artefact manifest records the hash of what was written,
  and the report says which of its forms is reproducible.
- **Option B — not taken.** The exporters would have pinned the container metadata: — a fixed timestamp
  in the DOCX's ZIP entries, a fixed creation date and no variable IDs in the
  PDF — so that all four forms are byte-reproducible.

*Cost of A:* a DOCX is not comparable by hash, so "the same report" is a claim
about content for that form. *Cost of B:* the exporters must reach into
container metadata, which is library-version-specific and brittle; and a PDF
whose creation date is fixed is lying about when it was made.

#### 1.4.4 The local API's session and origin model

`docs/ARCHITECTURE.md` requires that the localhost API have **origin
restrictions and a local authenticated session or token, even when launched on
loopback**, and LC-P1-12 adds a CSRF guard.

- **Option A — TAKEN (2026-10-20): both, and the origin check is the real defence.**
  The service binds `127.0.0.1`, refuses any request whose `Origin` is not
  its own, and requires a bearer token minted at start-up, written to a
  workspace file the CLI prints. The UI obtains the token through a
  same-origin request.
- **Option B — not taken.** A cookie session with a one-time bootstrap token would
  have been the alternative: The CLI
  prints a one-time URL the user opens; the server sets a session cookie.

*Cost of A:* the token has to reach the browser, and a bearer token in a
header is the kind of thing a careless front end leaks into a log. *Cost of B:*
a cookie needs CSRF defence on its own terms, and a one-time URL is a URL
that can be pasted somewhere it should not be.

## 2. The shape of the thing

### 2.1 The path from a task to a report

```text
  task + run + stages          (runtime, merged)
        │
        ▼
  evidence records             (ledger, merged — claims, numerics, results,
        │                       each with its verification state and its
        │                       anchor ids)
        ▼
  figures                      (analysis, merged — deterministic, with their
        │                       captions and their own manifests)
        ▼
  ReportDocument               ← G4's model: sections, claims, figures,
        │                       tables, and the record each claim rests on
        ▼
  renderers                    Markdown · HTML · DOCX · PDF
        │
        ▼
  report artefact manifest     ← the list of what the report is made of,
        │                       each part's hash and its lineage
        ▼
  artefact receipts            (merged — REPORT, FIGURE, TABLE, DATASET)
        │
        ├── the CLI writes the file
        ├── the API serves the same bytes
        └── the UI shows the same bytes
```

**The report is rendered once.** The CLI writes the bytes and the API serves
the same bytes; the UI never composes a report of its own (§1.4.2). That is
what makes "CLI and Web produce the same versioned report" a hash comparison
rather than a promise.

### 2.2 The document model, and why it is the spine

A `ReportDocument` is **data**: its sections, its claims, the ledger record
each claim rests on, the figures it embeds with their captions, and the
tables it includes. It is a frozen, versioned pydantic model, and it has
**canonical bytes** — so a report is hashable, and two reports of the same
content are the same bytes.

Everything else follows from that one decision:

- **content verification is separate from rendering** (the work order's
  words), because the checks run against the model, and the renderers cannot
  change a result — they can only draw it;
- the numbers in the report are the **ledger's** numbers, copied into the
  model at build time and checked against the ledger at check time, so a
  report that says 4.25 says what the ledger says or it is refused;
- the manifest lists the model's parts, and the receipt records the
  manifest's hash — so the chain from the ledger to the exported file is
  linear, and a changed part is nameable.

**A `ReportDocument` is not the ledger.** It is a *view* of a set of ledger
records, frozen at a moment, and the report says which moment. A report that
is re-rendered from a changed ledger is a **new revision** (§2.4), not a
correction of the old one.

### 2.3 The four renderers, and what they may and may not do

| Form | What it is | How it is produced | Byte-reproducible? |
|---|---|---|---|
| **Markdown** | the reference form | the model's own writer | yes — it is text with a declared encoding |
| **HTML** | the preview form | the model's own writer, in one self-contained file (no external assets, no scripts) | yes — same reason |
| **DOCX** | the editable form | a document writer over the model | **only if the container metadata is pinned** (§1.4.3) |
| **PDF** | the fixed form | a document writer over the model, or the HTML through a converter | **only if the creation date and the font subsetting are pinned** (§1.4.3) |

**The renderers draw; they do not decide.** A number in a report comes from
the model, and a caption comes from the model, and the renderer's only
freedom is how it draws them. A renderer that has to compute a number to
draw it is a renderer that can disagree with the ledger, and the work order
says content verification is separate from formatting.

**The report says what it is.** Every export carries the statement that it
is a first-pass report and **not journal-ready** — the work order requires
the limit to be explicit, and a report that does not say it is claiming a
standard it has not met.

### 2.4 Revisions, and what makes a report stale

The receipt already carries `revision`, and its docstring already says that
**LC-P1-11's artefact versioning increments it rather than overwriting**. So:

- **v1 and v2 coexist.** A second report of the same task is a new receipt
  with `revision = 2` and a new file; the first is never altered.
- **staleness is computed by the machinery that already exists.**
  `ResumeCoordinator.invalidate_on_source_change` walks the artefacts whose
  chain names a changed hash and marks them `STALE` with a reason — the
  same walk that marked LC-P1-10's figure and manifest stale in its exit
  demonstration. A report whose material changed is **stale**, and the
  staleness is a *fact about the receipt* rather than a note in the document.
- **re-rendering after a material change does not silently produce a new
  report.** It produces a new revision of a *new* document, and the old one
  stays stale and says so.

### 2.5 One application layer, three surfaces

The work order is explicit: *"CLI/API/UI call same application layer"*. The
layer is a small set of **operations** — create a task, run a stage, list
sources, list artefacts, render a report, request an approval, consume one —
each of which:

- goes through the **capability** model (`CapabilityId`, `PermissionPolicy`,
  `ApprovalLedger`) exactly as the run path does, so a surface cannot grant
  itself a permission the other surfaces would not;
- reads and writes through the **TaskStore**, so the three surfaces see one
  state;
- returns **data**, and the surface formats it. `ARCHITECTURE.md` says
  formatting must never be load-bearing for a machine-readable command, and
  the CLI's `--json` output is the same data the API returns and the UI
  draws.

**What the store does not have yet — and this list was wrong when this
document was written.** It said the store lacks *list* queries for tasks,
runs, stages and artefacts. T05 found the gap is **larger**: the store
cannot **read** a task, a source or an approval at all, so the list was only
part of what the operations need. The nine readers T05 added are
`list_tasks`, `load_task`, `list_runs`, `list_stages`, `list_artifacts`,
`list_approvals`, `list_operations`, `list_sources` and `load_source`, and
each one is needed by an operation — `load_task` by `read_task_state`,
`list_runs`/`list_stages`/`list_artifacts`/`list_approvals` by the state and
plan reads, `list_operations` by `run_stage` and the approval path,
`list_sources` and `load_source` by the source operations, and `list_tasks`
by the list operation itself.

**The ordering rule, because a list whose order changes between runs is a
bug a reader reports as "it shuffled".** Each kind leads with the
project's own sequence column where it has one — tasks by
`(created_at, task_id)`, runs by `(attempt, run_id)`, artefacts by
`(revision, artifact_id)`, sources by `(ingested_at, source_id)` — and with
the UUIDv7 id where it does not (stages, approvals, operations); every
ordering ends with the unique natural key, so no two rows tie.

### 2.6 The local API's guards

Three things, and the order matters:

1. **The bind address.** `127.0.0.1` only. Not `0.0.0.0`.
2. **The origin check.** Every request whose `Origin` is not the service's
   own is refused, whatever it asks for. This is the real defence: a page in
   the user's browser on another site cannot drive a local service, and the
   browser sends the `Origin` whether the page means to or not.
3. **The session.** A token minted at start-up, written to a file in the
   workspace, printed by the CLI, and required on every request that changes
   anything. The UI obtains it through a same-origin request.

**The web refresh rule** — *"Web refresh recovers DB snapshot, no repeated
operation"* — is a consequence, not a feature: the UI holds **no state of its
own**. It reads the task from the API, and a refresh re-reads it. The only
thing that must not happen twice is an *operation*, and operations are
idempotent by construction: creating a task twice is two tasks with two ids,
and the UI's "create" is a single request the server either applies or
refuses.

### 2.7 The typed contract the UI consumes

`ARCHITECTURE.md` says the React app *"consumes typed API contracts"*. The
TypeScript side therefore gets its types from **one** source, not from a
hand-written mirror: the API's response models are exported as a JSON Schema
or an OpenAPI document, and the TypeScript types are generated from it and
checked in CI against the Python models. A hand-written mirror is a second
spelling of the API's shape, and it is the same defect the catalogue's
docstring warns about.

---

## 3. The subtasks

### File ownership map (this is the parallel contract)

| Module | Owns |
|---|---|
| `labcairn/reports/model.py` | **T00** — the `ReportDocument` and its canonical bytes |
| `labcairn/reports/render/` | **T01** — the four renderers |
| `labcairn/reports/manifest.py` | **T02** — the report artefact manifest |
| `labcairn/reports/revisions.py` | **T03** — revisions and staleness |
| `labcairn/reports/checks.py` | **T04** — the content checks |
| `labcairn/application/` | **T05** — the one application layer, and the store queries it needs |
| `labcairn/cli/` | **T06** — the Typer CLI |
| `labcairn/api/` | **T07** — the FastAPI service and its contracts |
| `web/src/` | **T08** — the React workbench |
| `examples/` | **T09** — the end-to-end smoke path |

**The two contracts that must be frozen before anything is branched** are
`labcairn/reports/model.py` (T00) and the operation list in
`labcairn/application/` (T05). The three surfaces are the parallel work, and
they are parallel only because those two are fixed first — the same
discipline the work orders state for LC-P1-02.

### T00 — the report document model

`ReportDocument`: the sections, the claims and the ledger record each rests
on, the figures with their captions, the tables, and the provenance
footnotes. Frozen, versioned, with **canonical bytes**.

*Why first:* every other thing renders it or checks it, and the content
checks and the manifest are both statements about it.

*Cost:* the model is a second representation of the ledger's contents, and
the cost is paid by making it a **frozen view at one moment** rather than a
live view — it names the moment, and a report is never "current" the way
the ledger is.

### T01 — the four renderers

Markdown, HTML, DOCX and PDF over one model. Each renderer is a pure
function of the model; none of them may compute a number.

*The libraries are a technical selection, not an owner decision, with one
exception:* their licences join matplotlib's bundled-font obligation in G5's
audit, so the choice is recorded in the ADR that the dependency decision
writes. A Markdown writer and an HTML writer are small enough to own; the
DOCX and PDF writers are not, and they are the two that carry the
reproducibility question of §1.4.3.

*Cost:* four renderers is four chances to draw the same model differently,
and the content checks (T04) are what keep them honest — a renderer that
drops a claim is caught by the check that every claim in the model appears
in the output.

### T02 — the report artefact manifest

The list of what a report is made of: each part, its hash, its lineage, and
the report's own digest. Written as an `ArtifactReceipt` of kind `MANIFEST`,
because the kind is already reserved for it.

*Cost:* the manifest is a document about a document, and it can disagree with
the document unless the manifest is built from the model's parts and the
receipt records the manifest's hash — which is why the manifest is built
*from* the model rather than assembled beside it.

### T03 — revisions and staleness

`revision` increments; v1 is never altered; a report whose material changed
is marked `STALE` by the invalidation walk that already exists, with the
repository's reason.

*Cost:* the staleness of a report is a property of the **receipt**, not of
the document, so a reader who opens the file sees a report that is not
marked stale and must look at the receipt to know. That is the same trade
the figures already make, and the report's own face can carry a line saying
"this report was rendered from material that has since changed" — but only
because the report is re-rendered, not because the file watches itself.

### T04 — the content checks

The checks that run against the **model**, before any rendering: every
number in the report agrees with the ledger; every figure in the report has
its caption; every link resolves; every claim names the record it rests on.
They are the work order's *"content verification separate from formatting and
rendering"*, made mechanical.

*Cost:* the checks need the ledger, so a report cannot be checked without
one — and a report built from a snapshot of the ledger can be checked
against that snapshot, not against the live ledger. The check is against
what the report says it was built from.

### T05 — the application layer, and the queries it needs

The operations the three surfaces call, and the **list queries the store
does not have**: tasks, runs, stages, artefacts. Each operation goes
through the capability model and returns data.

*Cost:* the layer is a seam, and a seam is a place where a guard can be
applied to seven of the eight callers. The mitigation is the one the
repository already uses for the operator catalogue: the layer is **the only**
thing that touches the store, so a surface cannot reach past it.

### T06 — the Typer CLI

`init`, `doctor`, `task create/run/status/resume`, `sources inspect`,
`artifacts list`. Every command has a machine-readable form, and the
formatted output is a rendering of the same data, never the source of it.

*Cost:* `doctor` is the command that most wants to be prose, and it is the
one the architecture's rule catches: its findings are data, and the prose
says what the data says.

### T07 — the local API

FastAPI on `127.0.0.1`, the origin check, the session, the event stream over
the events the runtime already records, and the typed contracts the UI
consumes.

*Cost:* the event stream is a long-lived request, and a browser that
reconnects must not replay operations — which is why the stream carries
**events** (facts about what happened) and never commands.

### T08 — the React workbench

Project selection, the plan and the steps, the pending approval, the source
anchors, the evidence status, the artefacts and their preview, and the
revisions. The UI holds no state of its own; it reads the task and draws it.

*Cost:* the UI cannot be developed against a mock and then be right, because
the contract it consumes is generated from the Python models — a mock that
drifts is caught by the contract check, not by a human noticing.

### T09 — the end-to-end smoke path

The demonstration G4's exit test names: a clean-clone developer launch with a
working smoke path, and the three surfaces producing the same report bytes.
It is run by a test, because the G1 and G2 demonstrations are run by nothing
and that is a hole the G3 review named.

---

## 4. The acceptance mapping

### 4.1 LC-P1-11's own acceptance clause

> **Acceptance:** exports are openable; numeric values agree with ledger,
> figures/captions intact, links resolve, output hash/lineage retained.
> Re-rendering after material change invalidates stale output.

| # | Clause | Carried by | The test that proves it |
|---|---|---|---|
| 1 | exports are openable | T01 | each of the four forms is parsed back by something that is not the writer — the DOCX and the PDF by a reader, the Markdown and the HTML by a parser — and the content it reads back is the model's |
| 2 | numeric values agree with ledger | T00, T04 | every number in the report is compared with the ledger record it came from, and a report that says 4.25 where the ledger says 4.5 is refused |
| 3 | figures/captions intact | T00, T01, T04 | the figure's bytes in the report are the figure artefact's bytes, and the caption beside it is the caption in the model |
| 4 | links resolve | T04 | every link in the report points at a locator that the index can resolve, and the check is a resolution, not a string comparison |
| 5 | output hash/lineage retained | T02 | the manifest records each part's hash and its lineage, and the receipt records the manifest's hash, so the chain from the ledger to the exported file is one line of hashes |
| 6 | re-rendering after material change invalidates stale output | T03 | the invalidation walk marks the report `STALE` with a reason, and the re-render is a new revision that does not alter the old one |

### 4.2 LC-P1-12's own acceptance clause

> **Acceptance:** clean clone developer launch with working smoke path; Web
> refresh recovers DB snapshot, no repeated operation; request approval cannot
> be spoofed from another origin; CLI and UI show identical Task state.

| # | Clause | Carried by | The test that proves it |
|---|---|---|---|
| 1 | clean clone developer launch with working smoke path | T09 | the demonstration runs from a fresh checkout, against a temporary database and workspace, with no network and no credential |
| 2 | Web refresh recovers DB snapshot, no repeated operation | T07, T08 | the UI is reloaded and the task it shows is the task in the database; the operation that follows is applied once, because the UI holds no state and the server's operations are idempotent by construction |
| 3 | request approval cannot be spoofed from another origin | T07 | a request carrying another origin is refused, with and without a token; and a request from the right origin without the token is refused |
| 4 | CLI and UI show identical Task state | T05, T06, T08 | the CLI's `task status --json` and the API's task document are compared, field by field, from the same store — and, per §1.4.2, the report's bytes are compared by hash |

### 4.3 The conditions of ADR-0004 Contract 4 that G4 touches

| # | Condition | Verdict expected here |
|---|---|---|
| A3 | An evidence record states what was found, not what was concluded | **DISCHARGED for the report.** A report's claim names the ledger record it rests on, and a record that is `conflicted` or `unsupported` cannot become a report sentence that reads as a finding |
| A6 | Every source is recorded with what was extracted from it | **DISCHARGED for the report.** The report's provenance footnotes carry the source, the locator and the content hash |
| A10 | Interpretation always unverified | **DISCHARGED for the report.** A report's own interpretation — its narrative — is marked as not machine-verified, exactly as the figure's is; and a report may not restate an interpretation as a claim |
| A11 | Retrieved text is data | **DISCHARGED for the report.** The report renders retrieved text, so it escapes it; and a retrieved excerpt is never a command to the renderer |
| A12 | Fabricated source fails | **PARTLY, and the owner's decision in §1.4.1 says how far.** A report cites locators, so a fabricated source cannot be cited by identifier; but nothing *verifies* an identifier that the material itself carries, and the report says so on its face |

---

## 5. What these work orders cannot deliver

Named now so they are not discovered as surprises.

- **A report that is ready to submit.** The work order says the first pass is
  not journal-ready, and the report says so on its face. The formats are
  basic: no journal class, no reference manager round-trip, no typesetting
  beyond what a document writer does.
- **A citation that resolves outside.** A report's citations are locators
  (§1.4.1). A reader who wants the DOI has to find it in the material.
- **A bibliography with a stable identifier per entry**, unless the owner
  takes Option B of §1.4.1, and even then the identifier resolves to the
  material that asserts it, not to anything outside.
- **A multi-user or hosted product.** The API is a local service on
  loopback with a local session; there is no account, no tenancy, no
  deployment.
- **Any work that a user could not do by hand in an hour.** G4 is a local
  workbench for one person on one machine.
- **The fabricated-DOI clause.** It is LC-P1-09's, and Option A of §1.4.1
  leaves it open.
- **A second opinion on any of it.** Every work order in this repository has
  been reviewed by the party that wrote the fixes, and the G3 review says
  what an independent reviewer would still want to look at.
