# Phase 3 — Scoping Pack

**Status:** scoping only, 2026-11-06. The owner authorised a scoping / ADR
pack and nothing beyond it. Phase 3 implementation has not started, no
`LC-P3-xx` work order exists, and this document is neither a work order nor
an approval to build one.

**Why a pack exists before a board.** The roadmap's P3 row is a strategic
target, not an implementation work order
([`ROADMAP.md:5-7`](../ROADMAP.md), [`ROADMAP.md:75-76`](../ROADMAP.md)).
Phase 2's administrative closeout is CLOSED
([`LC-P2-28-phase2-open-items.md`](../acceptance/LC-P2-28-phase2-open-items.md)).
The owner's 2026-11-06 decision authorises this scoping pack so that a
future board can name its dependencies, boundaries and decisions without
silently reopening closed acceptance records.

## 1. Strategic boundary

The P3 row names: stronger isolation, packaging, plugin/MCP trust,
Windows/macOS/Linux distribution, robustness, observability, documentation
and benchmark expansion. Its exit gate is a secure, maintainable,
multi-platform public release and documented operational limits. P4 is
continuous improvement and is outside this boundary.

Current-state documents say the same thing: Phase 3 has not started
([`handoff/CURRENT.md`](../handoff/CURRENT.md),
[`CHANGELOG.md`](../../CHANGELOG.md)). The final Phase 2 open-item ledger
says *"The project does not proceed to Phase 3 without a new owner
decision"* and calls the workbench / desktop shell a strategic target,
not an approved work order
([`LC-P2-28-phase2-open-items.md:47-55,71-72`](../acceptance/LC-P2-28-phase2-open-items.md)).

This pack does not revise the roadmap's version or create a board. The
existing planning discipline requires a roadmap and its work orders to be
revised together
([`ROADMAP.md:3-4`](../ROADMAP.md),
[`PHASE_1_WORKORDERS.md:19,21`](../PHASE_1_WORKORDERS.md)). A board can be
written only after the owner decides its numbering, gate split and reviewer
form.

## 2. What is deliberately excluded

### 2.1 Permanent Phase 2 limitations

The 35 model-proposal version edges remain unaccepted
([`LC-P2-28-phase2-open-items.md:7-14`](../acceptance/LC-P2-28-phase2-open-items.md)).
The owner expects no further paper-material batches, so the second paper's
missing connecting edge, the unestablished author-draft / mentor-copy edge
type, undecided `F027` role and branch-shaped editorial rounds are permanent
limitations of the measured record
([`LC-P2-28-phase2-open-items.md:16-28`](../acceptance/LC-P2-28-phase2-open-items.md)).

The real-provider smoke remains `NOT RUN`; no human rated a blind sheet,
settled a dispute, or performed the independent G1/G2 re-review; and
agent-to-agent agreement is not inter-human reliability
([`LC-P2-28-phase2-open-items.md:30-45`](../acceptance/LC-P2-28-phase2-open-items.md)).
The 2026-11-05 review record's `POSIX-only witnesses remain NOT MEASURED`
line is a dated snapshot. A 2026-11-06 WSL run of the POSIX-only path and
session-directory witnesses passed, but that operator-side measurement is
outside the frozen Phase 2 gate record and does not change its verdict.

### 2.2 Owner-side decisions and credentials

The owner keeps the provider credential and the decision to spend
([`LC-P2-26-ci-provider-secret.md`](../acceptance/LC-P2-26-ci-provider-secret.md)).
No credential enters the working tree, an issue, a pull request body, a log,
a session transcript or a test. `provider-smoke.yml` remains schedule /
manual dispatch only and is not a required `pull_request` check. Branch
protection, evaluation-trigger policy, future human reading, signing
credentials and release tag authority remain owner decisions.

### 2.3 Design-only material

[`ADR-0020`](../adr/ADR-0020-opinion-and-flag-sources.md) is `Proposed`;
the [`LC-P2-28` breakdown](../plans/LC-P2-28-review-ingestion-task-breakdown.md)
is design only. The final open-item ledger says they were not Phase 2
acceptance clauses and were not implemented
([`LC-P2-28-phase2-open-items.md:47-52`](../acceptance/LC-P2-28-phase2-open-items.md)).
ADR-0020 itself says it is the record of what a future ingestion would have
to prove, not permission to start it
([`ADR-0020:106-109`](../adr/ADR-0020-opinion-and-flag-sources.md)). A
future owner decision must either archive that design or move it into a
newly approved board; this pack does neither.

## 3. Candidate scope families

These are scoping labels, not ticket ids. Each family needs its own owner
approval, ADR and acceptance clauses before implementation.

| Family | Scope question | Named dependencies |
|---|---|---|
| `packaging-artefact-hardening` | Which wheel/sdist content and release checks become the reproducible publication contract? | `pyproject.toml`, [`release.yml`](../../.github/workflows/release.yml), [`LC-P1-14-release-contents.md`](../acceptance/LC-P1-14-release-contents.md), owner channel and tag authority. |
| `cross-platform-distribution` | Which Windows/macOS/Linux install and upgrade paths, signing, notarisation and published release are in scope? | Package hardening, [`UPSTREAM_REFERENCES.md`](../UPSTREAM_REFERENCES.md), owner-held signing/account credentials, a decision about `web/package.json`'s `UNLICENSED`. |
| `desktop-shell-selection` | Is there a desktop shell at all, and what evidence must a real browser measurement produce first? | [`LC-P2-16-task-breakdown.md:68-76,200-203`](../plans/LC-P2-16-task-breakdown.md), [`THREAT-MODEL.md:984`](../THREAT-MODEL.md), existing `web/src/app/` and `web/src/views/`. |
| `plugin-mcp-trust-model` | Are third-party plugin/MCP extensions allowed, and what registration and capability-grant boundary would they have? | [`ADR-0006`](../adr/ADR-0006-capability-namespaces.md), [`THREAT-MODEL.md:245,260-283`](../THREAT-MODEL.md), `src/labcairn/security/`, owner decision on third-party execution. |
| `stronger-isolation` | Is the deployment explicitly single-user, or is a real multi-user isolation scheme designed? | [`PHASE_2-capability-reuse-matrix.md:397-401`](../plans/PHASE_2-capability-reuse-matrix.md), [`LC-P2-18-competitor-baseline-brief.md`](../plans/LC-P2-18-competitor-baseline-brief.md), [`THREAT-MODEL.md:310`](../THREAT-MODEL.md). |
| `observability-interface` | Which privacy-safe structured interface is allowed, and which vendor rule applies? | [`ARCHITECTURE.md:24`](../ARCHITECTURE.md), [`ADR-0003:181`](../adr/ADR-0003-event-and-permission-model.md), owner vendor decision. |
| `robustness-and-browser-witness` | Which real-browser, recovery and non-concurrent whole-suite measurements become P3 acceptance evidence? | [`THREAT-MODEL.md:984`](../THREAT-MODEL.md), [`LC-P2-14-phase2-exit-gate.md:90-93`](../acceptance/LC-P2-14-phase2-exit-gate.md), owner decision on gate membership. |
| `operational-limits-docs` | Which measured limits ship with a release, and which current-state documents are revised together? | Results from the other families, [`ROADMAP.md:4`](../ROADMAP.md), owner version and tag decision. |
| `benchmark-expansion` | Which corpus, human reading and comparison basis may extend the benchmark? | [`ROADMAP.md:189-190`](../ROADMAP.md), external corpus and budget, evaluation manifest and shard registrations. |

Two ADR-0020 work shapes remain recorded as design only: quoted-opinion
identity with reply join, and flagged-text events with version alignment
([`ADR-0020:83-84`](../adr/ADR-0020-opinion-and-flag-sources.md)). Their
stage assignment is an owner decision, not an output of this pack.

## 4. Decisions before any implementation

1. Whether and when to create a Phase 3 board, its numbering, gate split and
   roadmap version.
2. Whether ADR-0020 / LC-P2-28 are archived as Phase 2 design or renumbered
   into a future board; whether ADR-0020 is accepted or superseded.
3. Whether a desktop shell is in scope; a selection ADR and real-browser
   measurement may be required before any commitment.
4. Which credentials, signing, notarisation, store accounts, tag authority
   and spending the owner retains.
5. Whether third-party plugin/MCP execution is allowed at all.
6. Whether any P3 robustness ticket may include Phase 2 residuals; the 35
   edges, human-reader claims and frozen gate verdicts stay excluded.
7. Whether provider smoke remains schedule / manual dispatch only.
8. Who supplies the independent review at a named commit, and how a
   non-human substitute is disclosed.

## 5. Acceptance discipline for a future board

[`PHASE_1_WORKORDERS.md:19,21`](../PHASE_1_WORKORDERS.md) defines the board
as the completion record: a status changes in the same commit as its
evidence, and a row is done when an independent review at a named commit
says so. The vocabulary is `NOT STARTED`, `IN PROGRESS`, `PASS`, `PASS WITH
NOTES`, `BLOCKED` and `FAIL`. A new test file must register its gate class,
shard cost and evaluation manifest entry, and shard costs must come from a
runner measurement. No corpus answer text, material words or person names
enter this public repository.

## 6. Record hygiene

Historical gate records and dated end-of-day snapshots keep their own
wording. Current pointers must not quote those snapshots as current
measurements. Some older planning documents still contain no-licence,
deferred-PR or "workbench has not moved" wording; a future board must decide
which are explicitly dated snapshots and which are current statements to
correct. This pack does not rewrite those historical records.

## 7. What this document does not do

It does not create a work order, accept ADR-0020, revise the roadmap's
version, implement product code, change a Phase 2 verdict, accept a model
edge, add a credential, spend provider money, push, open a pull request,
start CI, enable auto-merge, or claim a Phase 3 gate result.
