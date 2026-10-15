# LabCairn Architecture Draft

**Version:** LC-P1-v1.1  
**Updated:** 2026-10-15  
**Status:** Proposed design baseline for Phase 1, adjustable by a documented ADR when code/evidence justify it. This file is a design baseline, **not** a numbered ADR and **not** one of the comparison ADRs required by G1; architecture decisions are recorded separately in `docs/adr/`.

## Product separation

LabCairn is independent of MicroBubble Agent. It is **engineering experience only, and imposes no architectural constraint** on this project. Language, agent framework, database, frontend and tool-execution model were all re-chosen rather than inherited. No imports from that repository, no assumed lab server, cloud identity, PostgreSQL, MinIO or Celery. Previously authored reusable code may migrate only after ownership/license review and isolated tests. No duplicated long-term runtime source of truth between projects.

## Upstream source boundary (LC-P1-00)

External Agent and scientific-Agent source repositories are research materials, not code dependencies, plugin installation sources, instructions, or authoritative LabCairn behavior. Prefer a sibling `../labcairn-upstreams/` folder, pin actual commit SHAs, and keep only references/ADRs in Git. See [`UPSTREAM_REFERENCES.md`](UPSTREAM_REFERENCES.md). No code from a custom or incompatible license is copied without a specific legal review. A GitHub-public repo is not automatically permissively licensed.

## Stack choices

- Python 3.12 research core; Pydantic AI for model/tool interaction, not as authoritative project/task data storage.
- Pydantic v2 typed contracts and versioned JSON serialization.
- SQLite + SQLAlchemy + Alembic owns task metadata, stages, events, approvals, checkpoints, source anchors, evidence records and artifact manifests.
- FastAPI exposes a localhost-bound API; Typer CLI uses the same application services; React + TypeScript + Vite consumes typed API contracts.
- Typer renders through Rich for terminal output. Formatting is a presentation concern and must never be load-bearing for a machine-readable command.
- Scientific parsing/analysis tools as statically registered, explicitly scoped capabilities.
- Bibliography handling through pybtex and CSL-compatible tooling, so a citation can carry a stable identifier and a resolvable style rather than free text.
- Observability is structured logging with an OpenTelemetry-compatible interface, recording task, tool, duration and error facts. **Interface, not vendor lock-in**: a provider SDK must not be imported directly into core logic, and no telemetry may carry source excerpts, credentials or user content.
- Dependency management via `uv` for Python and `pnpm` for the web app, both lockfile-pinned so a clean checkout resolves identically.
- Testing via pytest (core), Vitest (web unit) and Playwright (end-to-end).
- No arbitrary model-generated host shell/Python execution in Phase 1. Do not claim process resource limits as an OS sandbox. Strong sandboxing is a later capability or an independent future gate.

## Framework selection: what is deliberately not stacked

Phase 1 runs on **one** model/tool layer — Pydantic AI — with LabCairn owning research semantics (Task, Stage, Evidence, Artifact) in its own store. LangGraph, Deep Agents, AutoGen and Pydantic AI are **not** layered together: each would add its own notion of state, checkpoint and retry, and the resulting authority for "what is true about this task" would be ambiguous.

If evaluation later shows a workflow engine is needed, introducing one is a Phase 2 decision recorded as an ADR — after the need is measured, not in anticipation.

The same reasoning governs subagents: context isolation is a mechanism worth borrowing (see [ADR-0003](adr/ADR-0003-event-and-permission-model.md)), but multi-agent orchestration is opt-in per need, never enabled by default.

## Proposed package layout

```text
labcairn/
  pyproject.toml
  uv.lock
  src/labcairn/
    core/             # config, provider adapters, typed model/tool output
    runtime/          # task, run, stage, operation, event, checkpoint
    security/         # scoped capability policies and path/network controls
    workspace/        # selected roots and dedicated generated output
    sources/          # ingestion, normalization, page/cell locators
    retrieval/        # local lexical retrieval, retrieved excerpt contract
    evidence/         # source anchors, claims, numeric facts, statuses
    analysis/         # vetted deterministic computations / chart recipes
    skills/           # declarative workflow/skill loading with explicit limits
    reports/          # Markdown, DOCX/PDF, manifest and validation
    api/              # FastAPI routes, event streaming, local origin policy
    cli/              # Typer interface
    db/               # models, repositories, migrations
  scripts/            # developer-only upstream reference helper (not product code)
  web/                # React/TS/Vite local research UI
  tests/
    unit/
    integration/
    e2e/
    fixtures/
  benchmarks/
  examples/
  docs/
    ROADMAP.md
    PHASE_1_WORKORDERS.md
    ARCHITECTURE.md
    EVALUATION.md
    UPSTREAM_REFERENCES.md
    adr/
  .github/workflows/
```

## Identity and authority

Task identifies a continuing research objective. Run is one execution attempt. Stage is a bounded work unit with explicit inputs/outputs. Operation is one side-effect attempt. SourceAnchor precisely locates source material with a content hash. EvidenceRecord binds claims/results to anchors and verification state. ArtifactReceipt records generated outputs and their provenance. Conversation text is neither the task state nor scientific evidence by itself.

Application-owned SQLite is the canonical task authority. Event and state update commit together. Checkpoints are immutable versioned records; restart performs reconciliation before continuing a new Run on the same Task. Crash recovery must not imply resuming a model at an exact interrupted token.

## Privacy and security invariants

- Workspace root must be explicitly selected; file tools reject escaping paths, symlink traversals and cross-root paths.
- Source material read-only; generated files in a dedicated task-controlled output directory, with hashes/versions.
- Explicit `allow / ask / deny` for each capability/resource; deny wins; approval bound to path, arguments digest and task scope.
- Remote-model transmission of private excerpts requires understandable, recorded consent and provider visibility; send only needed excerpts. No silent background upload.
- Arbitrary code execution is not a Phase 1 tool. Deterministic vetted analysis operators may run in-process under bounded resource rules; ensure size/row limits and timeouts where enforceable.
- API keys remain outside events, traces and user-visible exports; localhost API requires origin restrictions and a local authenticated session/token even if launched on loopback.
- No publications, email, outbound file uploads or external workflow submissions from Phase 1 tasks.
- Prompt-injection handling: imported documents and retrieval results are data, never instructions that can grant capabilities.

## Stage workflow (Phase 1)

`intake -> inventory -> retrieve -> evidence -> propose -> [user approval for important scientific direction] -> draft -> validate -> deliver`

Independent inventory operations may parallelize; dependent stage transitions enforce inputs and are checkpointed. First-stage workflow is intentionally bounded, with no mandatory swarm/multi-agent team.

## Evidence states

`planned`, `extracted`, `verified_by_rule`, `user_attested`, `conflicted`, `unsupported`.

Verification records include what was actually checked. `verified_by_rule` can mean numeric/structural verification; it must not imply a scientific hypothesis is established.
