# Changelog

**Format:** [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
**Versioning:** the package declares `0.1.0` in `pyproject.toml`.

**No tag has been cut and no release has been published.** Everything below
is **unreleased**, and the repository grants no rights to anyone — see
[`LICENSE.PENDING.md`](LICENSE.PENDING.md) and the
[licence status](docs/RELEASE-NOTES.md#4-licence-and-security-status).

The changelog is organised by **gate**, because the gates are how this
project is organised: each one closed on a review, and each has a record.
The links are the records.

---

## [Unreleased]

### Since the gates closed

**Added**

- **The consent machinery — the grant table, the two gates, and the
  refusals.** `access_grants` and `derived_copies` (migration
  `0011_access_grants.py`), the permission check that answers whether a use
  is permitted, the two independent gates a transmit request has to pass
  (the operation approval, and the grant that names the destination), the
  withdrawal and the propagation that reaches the copies derived from it, and
  the intake guards that refuse an archive **before it is opened**. **The
  absence of a row is the refusal**, and a refusal names the missing
  permission and what would satisfy it. The fourteen acceptance clauses each
  have a named witness, and an **independent review against the merged
  tree** found four properties that were true of the code and unwatched — a
  read grant answering a training use, the refusals that never reached a
  surface, an order that was not wired, and a demonstration that printed a
  claim it did not carry — **each of which now has a witness that fails when
  the property breaks**.
  [LC-P2-06 acceptance](docs/acceptance/LC-P2-06-acceptance.md) ·
  [the independent review](docs/acceptance/LC-P2-06-review.md).

- **The paper project and the version graph.** `paper_versions` and
  `version_edges` (migration `0010_paper_version_graph.py`), the contracts
  that hold them, the alignment that **proposes** an edge without deciding
  it, the human path that settles one, and the two checks that are about not
  lying about an archive. **A version graph and not a version list**: the
  process branches, so the parent lives in the edge table and the version
  table has no parent column. A confidence score is not a decision, and an
  unresolved relationship is a value rather than an absence.
  [LC-P2-08 acceptance](docs/acceptance/LC-P2-08-acceptance.md).

- **The OOXML-native reader.** `w:ins`, `w:del`, `w:commentRangeStart/End`
  and the rest, read out of the package itself rather than out of a
  converted document: `src/labcairn/material/ooxml.py`, with `DocxLocator`,
  `SourceKind.DOCX` and migration `0009`. **Revision recall 30/30, deletion
  recovery 8/8 and comment recall 14/14 on the synthetic corpus**, with four
  mutations applied to prove the witnesses fail for their properties.
  [LC-P2-07 fidelity baseline](docs/acceptance/LC-P2-07-fidelity-baseline.md).

- **The first Phase 2 work-order list, as a draft.**
  [`docs/plans/PHASE_2-work-orders-draft.md`](docs/plans/PHASE_2-work-orders-draft.md):
  six tickets with prerequisites, cost and acceptance clauses, in the order they
  have to happen — freeze the Phase 1 baseline (the exit gate's
  *"measured capability gain"* has no denominator until then), restart-durable
  consent (whose blocker is measured: `ApprovalRow` holds no grant-time policy
  digest and no bound-source column, so `ApprovalStore.consume` is not itself
  restart-durable for the two checks that make a consent mean something), the
  product's first model call, the competitor baseline **gated on that call** (our
  compared figures come from the deterministic corpus layer, so naming a model in
  the run basis would fabricate the comparison — a wall already witnessed),
  citation identity, and retrieval beyond three papers. **Nothing is dispatched.**
  Five carried Phase 1 debts are listed with what inheriting each one costs, and
  the licence, the spending authorisation and the G1/G2 human reviewer are named
  as **not tickets**.

- **The G1/G2 human review has a checklist.**
  [`docs/acceptance/G1-G2-human-review-checklist.md`](docs/acceptance/G1-G2-human-review-checklist.md)
  gives a named reviewer every clause of the two gates with the node id that
  holds it, the mutation that must go red, the commits each gate has taken since
  it closed, the three exit demonstrations with their check counts re-counted
  from the source (36 / 14 / 18), and the four places the two records are
  weakest — starting with the fact that four of G1's thirteen clause rows and all
  six of LC-P1-07's were recorded **by behaviour, not by node id**. **It carries no
  verdict**: the owner's ruling stands that the two AI retro-review rounds are
  procedural independence, not human, so the board's rule for G1 and G2 stays
  open until a person executes it.
  `tests/test_status_consistency.py::test_the_human_review_checklists_node_ids_exist`
  resolves every id the checklist cites — `::` continuations included — against
  the class the citation names, which is what a reader typing the id does.
  Writing the checklist produced three wrong ids by hand (`TestApprovalGate` for
  `TestApprovalCheckpoint`, a `tests/test_recovery_probe.py` that never existed,
  and two methods cited under the wrong class), and the first version of this
  check missed the third because it asked whether each segment exists *anywhere*
  in the file. Bare-file citations are still unchecked, and the witness says so.

- **The deterministic figure has a surface.** `labcairn task figure` and
  `POST /analysis` call the layer's own `run_figure`; `labcairn task
  approval-request` and `labcairn task approval-grant` are the consent it needs,
  because `recipe` is now one of `analysis.run`'s consented arguments — a
  signature covers the bytes the figure is drawn from, not only the material
  (ADR-0012 constraint 7). The run path no longer takes a recipe beside the
  consent it spends.

- **The report has a surface.** `labcairn task report --path report
  [--template default] [--json]` and `POST /report` on the local service both
  call the application layer's own `render_report` and answer with its own
  `ReportRendered`, so the bytes a CLI writes and the bytes the service serves
  are one artefact. A fresh workspace's policy now permits `report.render`, which
  the registry binds to output roots. **The workbench asks for it too**: a button
  that states the two claims the service takes no default for, then reads the
  artefact list again — and shows the service's own refusal when the task has
  nothing to carry. **The workbench asks for the figure's consent too**: a
  Figure panel builds the selection from the source the service reports, asks
  for `analysis.run`, leaves the pending question in the Approval panel, and
  draws once it is granted. Two steps are the design. The report is still
  refused — writing nothing — when the task holds no record to carry, which is
  the correct answer rather than a gap: the next bullet is the operation that
  records one.
- **A task can be given a claim to carry.** `labcairn task claim` and
  `POST /claims` call the layer's `record_claim`, which resolves the address in
  the text the ledger holds for the source's current bytes, refuses one nothing
  answers, and writes an anchor and an `extracted` record as the user's own.
  `labcairn sources addresses` and `GET /sources/{source_id}/addresses` list the
  addresses a claim can rest on. **What it does not do** is extract, propose or
  verify: the caller supplies the words, and no surface runs C1, C2 or C3.
  [release notes §2.2](docs/RELEASE-NOTES.md).
- **The recovery pass runs at the surfaces.** `run_stage` calls
  `labcairn.application.recovery.reconcile_abandoned` after the policy verdict and
  before any consent is spent: an operation a crash left `ATTEMPTING` becomes
  `UNCERTAIN`, its stage is blocked with the recovery layer's reason, and the next
  `task run` or `POST /stages` is refused with `operation_uncertain` rather than
  planning a second operation for the same work. `labcairn task reconcile
  <operation-id> --expected-sha256 <hash>` is the operator's half, because the
  value a probe needs is not recoverable from the store. **The limit that
  remains** is stated in [ADR-0003 C2](docs/adr/ADR-0003-event-and-permission-model.md)
  and in [release notes §2.18](docs/RELEASE-NOTES.md).
- **The approval ledger asks the capability registry.** Both consume paths refuse
  an id the registry has never held, with a reason of its own
  (`capability_unregistered`), which closes the defence-in-depth gap G1 recorded.

**Changed**

- **§1.4.1b is the harness's behaviour, not a note beside it.** The owner ruled
  on 2026-10-29, and `tests/evaluation/aggregate.py` now classifies every
  non-passing case by **what the skip's own reason says**: a fact of the machine
  (an OS, a filesystem, a volume with no 8.3 short names) and a test in a class
  the owner ruled discharged outside the offline run are **accepted**, a file the
  run did not select and a file in which pytest collected no case are named as
  what they are, and **any other skip fails the blocker** — for a blocker's own
  witnesses and for the sixth blocker's required CI tests alike. Accepted
  exclusions are printed in the row — a witness case by its node id and pytest's
  own reason, a required CI test by its file under the category it fell in.
  Scope: the owner
  chose **all blockers**, not only the sixth, which is what the second blocker's
  Windows row needed. `docs/EVALUATION.md` is not amended — this is the harness's
  reading of one clause, recorded so it can be checked.

**Fixed**

- **A test class's cases are keyed to the file that holds them.** pytest writes
  the module and the test class in one dotted `classname`, and the JUnit reader
  assumed there was no class, so `tests.test_skill_ledger.TestDigests` became
  `tests/test_skill_ledger/TestDigests.py` — a path that is not in the tree. Six
  files in this suite hold their cases in classes, and their cases entered no
  denominator: the `unsupported-claim-detection` metric reported **34/34** witness
  cases where the tree held **82**. The reader now takes the module from the tree
  (the longest dotted prefix that is an actual file), the test class stays in the
  node id, and `tests/evaluation/runner.py` names the tree it is reading. The
  same class is kept when a report carries a `file` attribute (pytest's legacy
  JUnit family writes one), so switching `junit_family` cannot reintroduce the
  collision. And the blockers table's column that counts cases which did not
  pass — three, on the second blocker, all of them accepted platform skips — now
  says **"Cases that did not pass"** instead of a bare *"Cases"*, because a HELD
  blocker beside the number 3 invites exactly the wrong reading.
- **Three CI shard files that collect nothing are reported as such.**
  `test_store_support.py`, `test_recovery_support.py` and `test_skill_support.py`
  are support modules other tests import; they are filed in a gate class and in
  every shard, and pytest collects no case in them. The blocker's row used to say
  the run "did not select" them. It now says no case was collected, which is the
  finding — **and whether a required test file that carries no case belongs in
  the shard list is carried to Phase 2 rather than settled here.**

- **The Windows case-fold now has a witness that bites.** The G1 regression test
  `test_a_deny_on_the_resolved_spelling_beats_an_allow_on_the_declared_one` asserted
  only `permission is DENY`, which a broken fold still satisfies: `evaluate` matches
  both spellings and the pre-resolved lowercase key hits the deny rule with no
  folding, so replacing `_FOLD` with the identity left the whole suite green. The
  Windows branch now also asserts `matched_spelling == "declared"` — the only
  observable that distinguishes a real case-fold from none. Verified by mutation on
  a Windows runner: passes under `str.casefold`, fails under the identity
  (`matched_spelling` reads `resolved`). It bites on the `windows-latest` shard,
  where the case-insensitive filesystem that makes the bypass possible actually
  exists; the POSIX early return stays, because there the two spellings are
  genuinely different files.

- **The real-provider smoke could not have run, and now it can.** The skipped
  witness in `tests/test_provider_credentials.py` hard-coded a protocol and a
  model and passed `environ={}` to the credential loader, so **no credential on
  any machine could have satisfied it** — the records that said "removing the
  skip runs it with no new code" were wrong. The probe now lives in
  `tests/test_real_provider_smoke.py`, the file the evaluation harness had been
  naming as the protocol's fifth gate class since LC-P1-13 T04 without one ever
  existing, and it is configured by `LABCAIRN_PROVIDER_SMOKE_KEY` / `_MODEL` /
  `_PROTOCOL` / `_BASE_URL`. It **ran twice on 2026-10-28** against
  `MiniMax-M3.1-Flash` over an Anthropic-protocol endpoint: `tool_calls` and
  `usage_reporting` **ok**, both structured-output forms **unsupported** in
  pydantic-ai's client before a request is sent. **The gate class is discharged
  by a job of its own, not by the required checks**: the required checks name no
  credential and one never will, because a check that can only pass where a
  secret exists is a check branch protection waits on forever — so
  `.github/workflows/provider-smoke.yml` holds it and runs on a schedule and on
  demand, and fails rather than skipping when a variable is missing — and it has
  run: dispatch 40663728369 at `0adfbe3`, 2026-10-28, printing the same endpoint
  fingerprint as the two local runs. The
  predicate that decides whether the witness runs is witnessed in the unit class
  (`tests/test_provider_credentials.py:309` and
  `tests/test_provider_credentials.py:355`), and `requires_provider` was added to
  the marker-to-class mapping so
  the fifth class is reachable by construction rather than unreachable in prose.
  **The harness's own veto went with it:** `--classes real_model_smoke` printed
  the runnability table's sentence about the environment — *"no real provider
  credential is configured in this environment"* — without looking at the
  environment, and invoked nothing, so no reader with a credential could
  discharge the class. Naming it now runs it; the default run still refuses it,
  and both halves are pinned
  (`tests/test_evaluation_harness.py::test_a_class_named_on_the_command_line_is_run_rather_than_refused`,
  `::test_the_default_run_reports_the_real_model_class_as_not_run`). Measured: the
  named run says **`1/1`** with the credential and `0/1` without it.
  [release notes §2.7](docs/RELEASE-NOTES.md).
- **The competitor baseline's real blocker is now a test, not a sentence.** After
  the credential landed, the question was whether the §5.1 harness change —
  carrying a provider's model into the run basis — was the next step. Reading the
  code says no: the compared numbers come from the deterministic corpus layer, not
  a model, so the run basis declaring `model=""` is the accurate fact, and
  threading a model the run never used would manufacture the exact
  "rate-without-a-limitation" the protocol forbids. The refusal is now executed
  (`tests/test_evaluation_harness.py::test_the_offline_run_refuses_a_competitor_on_the_model_alone`)
  with a control proving the same baseline becomes comparable the instant a
  model-declaring run exists
  (`::test_a_model_declaring_run_makes_that_same_competitor_comparable`). The gate
  on any comparison is a **model-driven answer path in the product** — Phase-2
  work, not a harness edit. [LC-P1-13 baseline §5.1](docs/acceptance/LC-P1-13-baseline.md).
- **A reader can decode an `operation_reconciled` row without loading the
  recovery layer.** `ReconciliationPayload` and its registration moved to
  `labcairn.runtime.event` — the module the read boundary already imports — so
  the schema no longer depends on the coordinator having been imported in the
  same process. Before the move, a direct reader (a diagnostic script, a test
  calling `events_after`) was refused by the anti-bag rule on a row the writer
  had accepted. Witness: `tests/test_event_payload_vocabulary.py` reads the
  stored event in a fresh interpreter that loads no `labcairn.recovery` module;
  with the registry entry removed, that read fails with the pre-fix message.
  [ADR-0007](docs/adr/ADR-0007-event-payload.md).

### The public alpha (G5) — closed on two independent reviews

The handoff: evaluation, fault injection, and the documents.

**Added**

- **The public fixture corpus** — four scenarios across three genres plus
  the negative one, every byte synthetic, with source locators, hashes and
  answer keys that are **not** the product's own output.
  `tests/fixtures/public/` · [record](docs/acceptance/LC-P1-13-fixtures.md)
- **The evaluation harness** — one command that runs the protocol's five
  gate classes and writes the results with their denominators, and that
  reports the Phase 1 blockers honestly, including the ones that did not
  hold. `tests/evaluation/` ·
  [record](docs/acceptance/LC-P1-13-evaluation.md)
- **The outsider's path** — a script that clones the repository outside the
  checkout, builds an environment inside the clone, runs the README's
  commands there for real, binds a research folder, produces a report and a
  deterministic figure with source locators and an evidence ledger, revises
  it, survives a restart, and reads the same task back through two surfaces.
  Every step is a check that raises rather than warns, so the exit code is
  the assertion. `scripts/outsider_path.py` ·
  [record](docs/acceptance/LC-P1-14-outsider-path.md)
- **The threat model** — six faces (writes, reads, network, credentials,
  crash and concurrency) with `path:line` citations, and a larger §6 of
  **what the product does not claim**.
  [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md)
- **The documentation set** — the bilingual README and its standalone
  Chinese document, the quickstart, the contribution guide, this changelog,
  and the release notes with the known limitations.
  [docs/QUICKSTART.md](docs/QUICKSTART.md) ·
  [docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md)
- **The font licence audit** — measured, and the factual half of the licence
  audit is done: **no third-party font file reaches any artefact**, so the
  GPL font reportlab bundles does not attach to what a user receives.
  [record](docs/acceptance/LC-P1-14-font-licence-audit.md)

**Still open in this gate** — and named rather than glossed:

- the fault injection run **through the surfaces**, and the two exit
  demonstrations that were run by nothing;
- the **real-provider smoke**, which waits on the owner's credential and on
  the owner's decision about what a declared skip means;
- the **competitor baseline**, at whatever scope the owner settles;
- the **NOTICE**, the dependency and security checks, and the release's own
  member lists;
- the **review dossier**.

**Known limitations of this alpha** are listed in one place:
[the release notes](docs/RELEASE-NOTES.md). They are the larger half of the
handoff, and none of them is estimated.

---

## Phase 1, gates G0 to G4 — closed, never released

### G0 — upstream source study (LC-P1-00)

**Added** — the curated checkout strategy, the source/commit/licence index,
the architecture decisions, and no vendored dependencies.
[Record](docs/acceptance/LC-P1-00-evidence.md) ·
[review](docs/acceptance/LC-P1-00-review-623e3ca.md)

### G1 — the trusted core (LC-P1-01 to LC-P1-04)

**Added** — the deterministic `FakeProvider`; the versioned typed contracts
and their JSON serialization; the capability policy and the approval
binding; the workspace roots and the path guard; the security invariants;
the `research-report` skill contract.
[Acceptance](docs/acceptance/LC-P1-01-evidence.md)

### G2 — durable work (LC-P1-05 to LC-P1-07)

**Added** — the SQLite task store with transactional event append; the stage
plan; the injected restart; and crash recovery that enters `UNCERTAIN`
rather than guessing, so an uncertain side effect is never replayed blindly.
[Acceptance](docs/acceptance/G2-acceptance.md) ·
[narrative record](docs/acceptance/G2-evidence.md)

### G3 — the evidence path (LC-P1-08 to LC-P1-10)

**Added** —

- **Material ingestion and locators.** Text, Markdown, CSV, XLSX and PDF
  adapters produce text units addressed by page, line, row and header, or
  sheet and cell. The PDF library was settled by
  [ADR-0008](docs/adr/ADR-0008-pdf-ingestion-library.md) on `pdfplumber` and
  `pdfminer.six`, both MIT — **not** PyMuPDF. A page that reads as two
  columns is **refused and disclosed** rather than extracted, because
  splicing two columns stores sentences the author never wrote.
  [Acceptance](docs/acceptance/LC-P1-08-acceptance.md)
- **Retrieval and the evidence ledger.** An FTS5 index over a trigram
  tokenizer; four working cite-support checks; a record state machine whose
  only transitions are `advance` and `attest`; and a gate that **refuses as
  a whole**, so a partial citable list can never be handed to a caller.
  [Acceptance](docs/acceptance/LC-P1-09-acceptance.md)
- **Bounded analysis and a deterministic figure.** Seven descriptive
  operators and a catalogue built from their own id constants; a grouped
  aggregate that returns a table rather than a number; a figure's editable
  source as a recipe of exactly three parts — **data, encoding, output** —
  with no script beside it and no way to run one; a deterministic renderer
  whose controls were measured rather than asserted; and the reproducibility
  manifest, with six fields and one hash lineage.
  [Acceptance](docs/acceptance/LC-P1-10-acceptance.md)

### G4 — the usable application (LC-P1-11 and LC-P1-12)

**Added** —

- **The report path.** One `ReportDocument` — the model — with four
  renderers over it (Markdown, HTML, DOCX and PDF), the report artefact
  manifest, the revisions, the staleness that finds them, five content
  checks, the document builder, and the application layer's `render_report`.
  A report cites **locators only**, and an address that does not resolve is
  refused and cited **nothing** in its place.
  [Acceptance](docs/acceptance/LC-P1-11-acceptance.md)
- **Three surfaces behind one application layer.** The layer the CLI, the
  local API and the web UI all call; the event read with the cursor that
  resumes it; the Typer CLI; the local FastAPI service on `127.0.0.1` with
  its three guards; and the React workbench. The gate's exit test — *"CLI
  and Web produce same versioned report"* — is demonstrated: the CLI's task
  document and the local service's, field by field, and the report's bytes
  by hash. [Acceptance](docs/acceptance/LC-P1-12-acceptance.md) ·
  [gate review](docs/acceptance/G4-acceptance.md)

**Also in this period**

- **The CI runs in six shards per platform.** 34.5 minutes → 7.3. The shard
  file records the commit its costs were measured at, and a witness fails if
  anything under `src/` or `tests/` has changed since — because a value that
  can change is re-measured, not carried forward.
- **The earlier gates' exit demonstrations are run by a test.** They had been
  run by nobody since G1 closed, which is how a broken one survived to G5.
- **The G1 path-guard limit is stated and watched.** A write to a new file
  under an 8.3 short-spelled directory is accepted — the key names the tail
  below the root, and the tail is the same in both spellings.

---

## How to read this

**The record says what was decided; the measurement says what is true.** Where
they differ, the measurement wins and the record is corrected. Every claim
here points at a document, a commit or a test — and a claim with no witness
is a finding, not a credit.

**The limits are not in this file.** They are in
[the release notes](docs/RELEASE-NOTES.md), because a changelog says what
changed and a release notes says what is still not true.
