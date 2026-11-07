# Phase 3 — Planning Proposal (Not Approved)

**Status:** Proposal for owner decision — not approved, not dispatched.
**Date:** 2026-11-06.
**Baseline:** `b3fba5f1581b066e64c2bc7b884ebc952605245d`, printed by
`git rev-parse HEAD` before this proposal was written.
**Companions:**
[`PHASE_3-design-traceability.md`](PHASE_3-design-traceability.md),
[Multisource research learning supplement](MULTISOURCE-research-learning-plan.md),
[`PHASE_3-planning-decisions-2026-11-06.md`](../acceptance/PHASE_3-planning-decisions-2026-11-06.md),
[`PHASE_3-scoping-pack.md`](PHASE_3-scoping-pack.md),
[`CURRENT.md`](../handoff/CURRENT.md),
[`ROADMAP.md`](../ROADMAP.md).

## 0. What this document is and is not

This is an English planning proposal derived from owner-supplied product
definition material. The source Word and PDF files, their extracted text and
the Chinese working drafts stay outside the repository. No sentence from the
source material is copied into the public tree; only English decision
summaries, candidate work packages, acceptance language and a gap register
appear here.

It is **not** a work order, a status board, an approved exit gate, an ADR, an
implementation instruction, or evidence that Phase 3 has started. Candidate
labels below are not ticket ids. The existing
[`PHASE_3-scoping-pack.md`](PHASE_3-scoping-pack.md) remains the earlier
authorised scoping record; the later owner decisions that this proposal
reflects are recorded separately in
[`PHASE_3-planning-decisions-2026-11-06.md`](../acceptance/PHASE_3-planning-decisions-2026-11-06.md).

## 1. Owner decisions recorded for this proposal

The owner decided on 2026-11-06 to:

1. convert the Chinese working drafts into an English planning proposal,
   synchronise current pointers, and still write no Phase 3 product code or
   dispatch implementation work orders;
2. adopt a Windows research-group internal trial as the proposed Phase 3 exit
   gate, moving multi-platform public distribution to a later work package;
3. preserve the source-material gaps honestly rather than filling them by
   inference;
4. authorise one delivery PR and one runner run for this planning material.

The owner also asked this session to repair gaps in the planning material
against the repository's actual state and the direction of the execution
brief. Section 6 is that repair: a code-facing gap register, not product code.
No later decision has opened a Phase 3 board, approved a numbering system,
approved a gate split, approved a reviewer form, authorised provider spend,
or authorised Phase 3 product implementation.

## 2. Proposed Phase 3 exit gate

The proposed exit gate is a **Windows research-group internal trial** of one
complete document-revision loop: an advisor supplies a DOCX carrying comments
or tracked changes; an authorised participant imports the paper and approved
reference material on one machine; the product locates each opinion, proposes
an evidence-linked response, performs only approved edits on an independent
copy, and exports a marked-up draft, a clean draft, a point-by-point response
table and a quality report. The advisor reopens the marked-up draft in
Microsoft Word and the two sides exchange DOCX files. Offline substitution
must prove the whole loop first; one real model may then be exercised on a
bounded, de-identified sample under a separate owner authorisation.

The current ROADMAP P3 row still describes a multi-platform public release.
The owner's 2026-11-06 decision changes the proposed P3 direction; the
ROADMAP, CURRENT, CHANGELOG and scoping pack are updated in the same delivery
so the plan and work-order records do not drift. Public, signed distribution
is deliberately placed in later work package `W28`, not in this exit gate.

## 3. Candidate work orders and gate split

These are candidate labels, formalised on 2026-11-07: the owner decision
record [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md)
adopts `LC-P3-00` through `LC-P3-08` as the ticket numbering and records
the gate, reviewer form and support matrix. Adoption is not dispatch — a
ticket starts only on the owner's word. The sequence
`00 → 01/02 → 03 → 04 → 05/06 → 07 → 08` is a dependency
proposal; `01` and `02` may run independently.

| Candidate | Stage | Deliverable and completion evidence |
|---|---|---|
| `LC-P3-00` scope and acceptance baseline | G0 | A dated decision record for the exit gate, Windows and Word support matrix, sample classification and reviewer form. Records the local threat boundary, outbound-data rules, DOCX write path and trial-distribution decisions with their triggers. |
| `LC-P3-01` real-browser baseline | G1 | Runs the existing API and workbench in a real browser against an offline sample. Evidence for task and version switching, comment display, approval, event reconnection and refusal behaviour; measured gaps are named, not assumed away. |
| `LC-P3-02` DOCX fidelity experiment | G1 | Compares local OOXML rewriting with a Windows Word adaptation path on small samples. Covers mixed comments and revisions, tables, equations and images; records Word version, open and reopen results, preservation of non-target regions, and refusal for unsupported structures. Produces an editing ADR and a support matrix. |
| `LC-P3-03` project authorisation and versioned writes | G2 | Import, read-only original, independent copy, content hash, publication receipt and recovery path. Real file operations prove that cross-project access, path escape, stale approval and duplicate requests are refused. |
| `LC-P3-04` comment-to-revision loop | G2 | The existing workbench and runtime carry import, proposal, per-item review, approved application and the four deliverables. A substitute model supplies reproducible input and output; opinions needing an experiment or missing evidence stay unresolved as explicit tasks. |
| `LC-P3-05` desktop shell and installer | G3 | Reuses the workbench, tightens preload and IPC, navigation, file opening, runtime lifecycle and local API session boundaries. A clean Windows environment proves install, launch, upgrade drill, uninstall and rollback; support limits and signing status are recorded. |
| `LC-P3-06` one-model bounded validation | G3 | One real model exercises the proposal path within an owner-authorised scope. Records model, sample fingerprint, outbound scope, budget, usage, refusal and repeatable acceptance evidence. Credentials and raw samples remain in the authorised environment. |
| `LC-P3-07` reliability and trial handover | G4 | Fault drills on the installed build: interrupted writes, locked files, network loss, model timeout and known errors. Delivers local de-identified diagnostics, backup and rollback, known limits and an operator manual. |
| `LC-P3-08` internal-trial review and exit decision | G4 | One advisor-to-student-to-advisor loop on the candidate installer, with actual samples, versions, gate rows and a named reviewer. The owner decides from the evidence whether Phase 3 is closed. |

Proposed stage outcomes: G0 has a dispatchable board and acceptance language;
G1 confirms the browser and Word write paths; G2 reproduces the offline
revision loop; G3 completes the installed build and the bounded single-model
validation; G4 completes the internal trial and an independent review. If the
G1 DOCX experiment cannot prove fidelity, automatic modification of that
structure is blocked and the support matrix is re-decided.

## 4. Windows internal-trial acceptance checklist

| Item | Passing condition |
|---|---|
| Import to delivery | A commented or revised sample runs through the installed build from a new project. Marked draft, clean draft, response table and quality report all bind to one task, one input version and one output version. |
| Original and format | The original hash is unchanged. Both DOCX files open and reopen in the supported Word environment without a repair prompt. The clean draft matches approved edits; non-target equations, images, tables and relationships survive. Changes outside the support matrix are refused or handed to a person. |
| Point-by-point response | Every supported input opinion is either located or explicitly marked as a location failure, with accepted, partly accepted, rejected or pending status. Automatic edits link to the opinion, evidence, operator and version. Model suggestions and advisor confirmations are separate records. |
| Research quality | The sample contains a directly editable case, a case needing further evidence, and an uncertain-location case. Missing experiments, references or data block a quality pass or become named tasks. File-delivery status and research-quality status are decided separately. |
| Permission and privacy | Cross-project references, path escape, writes to the original, forged or expired approvals, unauthorised outbound data and instructions embedded in the document all have refusal evidence. The real model receives only approved, de-identified content; logs and receipts use safe fields. |
| Cancel, retry and recovery | Two side-effectful interruption points around publication are exercised. Cancellation, duplicate submission and restart resolve to a safe retry, a recovered result or a manual check. The original is intact and output receipts are not duplicated. |
| One real model | The installed build runs one controlled de-identified case; the model returns at least one locatable, reviewable revision suggestion, and a person reviews it before delivery. Budget or permission failures cause no outbound call; timeout and unavailability have explicit degraded paths. This result belongs to Phase 3 and does not rewrite Phase 2's `real_model_smoke = NOT RUN`. |
| Distribution and review | A clean supported Windows environment proves install and run, and a rollback preserves user data. Evidence names the commit, package hash, OS and Word versions, case results and limits. A failure in core security, original protection or delivery gating keeps the exit decision blocked. |

Three sample classes are proposed: public synthetic DOCX for CI and negative
tests, a de-identified owner-authorised domain sample for the controlled real
model, and an authorised trial sample for advisor review. Raw samples and
replies remain in the authorised environment; only de-identified evidence or
synthetic reproductions belong in this public repository.

The status vocabulary follows
[`PHASE_1_WORKORDERS.md`](../PHASE_1_WORKORDERS.md): `NOT STARTED`,
`IN PROGRESS`, `PASS`, `PASS WITH NOTES`, `BLOCKED`, `FAIL`. Evidence and
status change in the same commit. A reviewer who did not implement the work
re-runs key cases at a named commit. If an independent agent session stands
in for a human reader, the record must literally say
`independent agent session stood in for a human reader; no human being
performed this reading`; real advisor and student trial use cannot be
simulated by an agent and reported as human use.

## 5. Board-opening prerequisites and external resources

- **Before dispatch:** `00` must close; `01` and `02` may then start. Public
  samples prove the existing entry points and the DOCX write path before `03`
  fixes authorisation, transaction and recovery design.
- **Board record:** formal numbering, gate split, Windows and Word support
  matrix, trial places and reviewer form are confirmed together. The board and
  ROADMAP are revised in the same change; Phase 2 records keep their own
  wording.
- **Before a real model:** provider, model, permitted outbound scope, call and
  cost ceiling, credential holder, sample and stop-loss are fixed by the
  owner. CI uses a substitute by default. Phase 2's Provider Smoke `NOT RUN`,
  the 35 unaccepted model-proposal edges and the archived ADR-0020 / LC-P2-28
  remain cited from their Phase 2 records.
- **Before trial distribution:** package channel, signing and installation
  policy, backup and rollback responsibility, and authorised trial
  participants are fixed. Public release, release tags and signing
  credentials remain owner decisions.

## 6. Implementation gap register (code-facing; no product code written)

The owner asked for gaps to be repaired against the repository's actual
state. This section names the measured product entry points and the work that
each candidate stage would have to add. It is an engineering gap register,
not an implementation instruction and not evidence that code was changed.

| Existing entry point | Measured state at the baseline | Gap to close before the candidate stage can pass |
|---|---|---|
| `web/src/app/Workbench.tsx`, `web/src/views/`, `web/src/app/useEventStream.ts` | Workbench views, API contract and browser unit tests exist. | No real-browser end-to-end evidence against a live local service; `docs/THREAT-MODEL.md` records this as an unexercised boundary. `LC-P3-01` must measure it before a shell is chosen. |
| `src/labcairn/material/ooxml.py`, `src/labcairn/papers/revisions.py`, `src/labcairn/papers/alignment.py`, `src/labcairn/reports/render/docx.py` | High-fidelity reading of comments and tracked revisions, revision events, version alignment and a report-only DOCX writer exist. | No proved fidelity-preserving edit to an existing manuscript, no marked-draft and clean-draft export from that edit, and no Word open/reopen matrix. `LC-P3-02` must decide this with short samples and an editing ADR. |
| `src/labcairn/application/`, `src/labcairn/security/paths.py`, `src/labcairn/security/untrusted.py`, `src/labcairn/workspace/readonly.py` | Task/Stage/Operation, recovery, allowed roots, path canonicalisation, untrusted-text boundaries and a source-root read-only guard exist. | No project-scoped import receipt that binds the read-only guard, independent-copy transaction and publication receipt into one revision loop. `LC-P3-03` must add and witness that integration. |
| `src/labcairn/papers/replies.py`, `chain.py`, `versions.py`, `src/labcairn/roles/` | Replies, feedback chain, version graph and on-demand role execution exist. | No point-by-point proposal-to-approved-edit-to-response-table binding, no quality report separating file delivery from research quality, and no explicit unresolved-evidence state for the new loop. `LC-P3-04` must wire these. |
| `web/`, `.github/workflows/web.yml`, `.github/workflows/release.yml` | A React/TypeScript workbench, wheel/sdist release checks and web quality gates exist. | No Electron/Tauri/PyInstaller configuration, desktop process lifecycle, installer, signing or upgrade/rollback drill. `LC-P3-05` is a selection and measurement stage before implementation. |
| `src/labcairn/workspace/outputs.py` | The atomic write names its temp file with a fixed 46-character `.lc-write-<hex>.tmp` form under `<ws>/output/<uuid>/analysis/<capability>/`. The full-suite recheck of 2026-11-07 observed `FileNotFoundError` opening that temp name exactly when the visible path length crossed 260 characters, and reproduced the 259/260 switch bare — directory creation succeeds, the exclusive open fails; three green and two red single-node runs tie the observation to path length, not a race (see the operator-side recheck record). | The write seam carries no path-length budget: a real installed workspace under a deep root can meet the same wall. The fix — a shorter temp name or a depth-checked output layout, plus a witness that writes near the ceiling — belongs to a batched implementation stage decision, not to this proposal, and no code change is made here. |
| `src/labcairn/application/model_request.py`, `src/labcairn/providers/`, `tests/test_real_provider_smoke.py` | Outbound gate, consent, budget, adapter boundary and a loud `NOT RUN` smoke harness exist. | No owner-credentialed single-model bounded run through the new revision loop, and no receipt that links model output to a reviewable suggestion. `LC-P3-06` requires a separate spend decision. |
| `src/labcairn/application/recovery.py`, `tests/test_fault_injection_e2e.py` | Reconciliation after a crash and fault-injection witnesses exist for the current surfaces. | The two new side-effectful interruption points around publication are not witnessed, and installed-build diagnostics and rollback are not written. `LC-P3-07` must add them. |
| `src/labcairn/skills/`, `src/labcairn/security/capabilities.py` | First-party skills and capability namespaces exist. | No third-party plugin/MCP registry, signed manifest, sandbox or revocation path. This stays an owner decision; no execution is authorised here. |
| `docs/ARCHITECTURE.md` observability constraint, `src/labcairn/api/session.py`, `src/labcairn/evidence/retrieval.py` | Privacy-safe structured-logging constraint, local session boundaries and an in-process `RetrievalTelemetry` record exist. | No independent telemetry module, no installed-build diagnostic bundle, and no proven Windows build telemetry. Later work packages must not carry source excerpts, credentials or user content. |
| `tests/test_ci_shard_coverage.py`, `.github/ci-shards.json`, `tests/evaluation/manifest.py` | Shard coverage, runner-measured costs and the evaluation class manifest are watched. Existing test files do not all carry `pytestmark`; the registry is the authority for gate classes. | Any new test file must declare its gate class with `pytestmark`, appear in exactly one `.github/ci-shards.json` shard, and be registered in `tests/evaluation/manifest.py`; costs must be re-measured from a runner log with `.github/remeasure_shards.py <run-id>`. A local timing is not a runner cost. The web gate currently runs on Ubuntu only, so a Windows browser measurement is a separate gap for `LC-P3-01`. |

No product source, test, workflow or migration file is changed by this
proposal. The gap register is deliberately written so a later board cannot
mistake "a plan names the code" for "the code exists".

## 7. Longer-term product work packages (proposal only)

The owner-supplied brief describes a larger product after the Phase 3 exit
gate. These `W10`–`W29` labels are a dependency map for future owner
decisions, not Phase 3 acceptance clauses, not scheduled milestones and not
approved work orders.

| Group | Candidate labels | Proposed boundary |
|---|---|---|
| Collaboration, project and privacy | `W10`–`W14` | Identity and membership lifecycle, private object storage, project workspaces, durable orchestration and audit. All shared-data access is gated by identity and authorisation evidence. |
| Advisor experience, models and extension governance | `W15`–`W21` | Paper evolution archive, model registry and routing, persistent role orchestration, reviewed experience publication, tool registry and third-party trust, public knowledge contribution and capability evaluation. |
| Literature, experiment, analysis and research delivery | `W22`–`W27` | Data lineage, local analysis with four-level verification, reproducible figures, literature synthesis, staged instrument access and editable presentation output. |
| Distribution, operations and public release | `W28`–`W29` | Multi-platform packages, signing and notarisation, public release, self-hosted collaboration deployment, privacy-safe observability and recovery. |

Milestone names and completion conditions in the source brief are retained
as a proposal only. Every later package needs its own owner decision,
input and authorisation, support matrix, budget, failure recovery,
acceptance samples and evidence location. A package without real resources
stays `NOT STARTED` or `BLOCKED` until its prerequisites are measured.
The product owner keeps scope, sign-off, budget and distribution authority.

## 8. Unresolved source questions

The traceability companion records all Q1–Q96 rows, and
[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) holds the
owner rulings of 2026-11-07 that closed five of the seven recorded gaps:
Q76, Q81 and Q86 had their recommendations adopted as decisions; Q86 and
Q87 additionally received fresh owner segments; the project-workspace row
(Q96) closes by the owner's reverse-infer instruction from the preserved
stem and options. Two rows remain, and the reverse-infer route does not
reach either because no options survived for them:

| Source question | Status | Trigger |
|---|---|---|
| Q77 | No stem and no options in the material (the interview jumps 76 to 78); the five knowledge tiers are recoverable from Q78's answer, the per-tier boundaries, write rules and lifecycle were never defined. | Before a memory interface is frozen — a design task, not a reconstruction. |
| Q82 | Nothing survives: no stem, no options, no conclusion. | Before a later requirements baseline is frozen; only an owner statement can fill it. |

No row is silently closed, and no work package is inferred from a missing
original question; the open rows remain triggers for a decision, not
approval to build.

## 9. Delivery and evidence discipline

Numbers, decisions and gate verdicts are anchored to the baseline printed
above or to a later printed full SHA; no unprinted SHA is quoted. A dated
owner decision record precedes any change to this proposal's status. The
status board changes in the same commit as its evidence. Independent review
at a named commit is required before a row is called done; a non-human
substitute is disclosed in the words quoted in section 4.

This planning delivery uses the owner-authorised single delivery PR and
single runner run. It does not configure a provider secret, spend a provider
request, sign a package, cut a tag, create a release, push directly to
`main`, enable auto-merge, or start Phase 3 product implementation.

## 10. What this document does not do

It does not create a work order, open a status board, approve a gate split or
ticket numbering, accept ADR-0020, renumber LC-P2-28, accept any of the 35
model-proposal edges, change Phase 2's frozen verdict, replace a human trial
participant with an agent, add a credential, spend provider money, implement
product code, add a test without the three registrations, publish a package,
or claim a Phase 3 gate result.
