# LabCairn · 研迹

**Research that leaves a trail. · 让每一步研究，都有迹可循。**

> **Status: Design / Phase 1 under construction.** This repository is a new project. Features listed below are planned, not yet shipped. Do not use the current code for unsupported scientific or safety-critical decisions.

**LabCairn** is a local-first AI research workspace **under development, intended to be released as open source once copyright ownership is settled**. It is designed to help researchers work across papers, data, analysis and reports while keeping a traceable link between sources, claims, methods and outputs.

**It is not open source yet.** No licence has been granted, so no rights to use, study, modify or redistribute it have been conveyed. See [Licence status](#licence-status--not-yet-granted).

LabCairn is not intended to replace scientific judgment or claim autonomous scientific discovery. It aims to make AI-assisted research **inspectable, reproducible where the underlying data and methods permit it, and easier to revise**.

### Why this name

*Lab* + *cairn*. A cairn is the pile of stones a hiker leaves to mark a route that has already been walked. It is the right image for a research agent: the work is not the answer, it is the **path that a later reader can follow back to the source**. A cairn does not tell you where the mountain is; it tells you someone came this way, and here is how.

This is also why the project is deliberately **not** named `PaperAgent` or `AutoScientist`. The first would suggest paper writing software; the second would suggest autonomous scientific discovery. Both are narrower than the intent, which spans material, data, code and output.

### Positioning

> A local-first AI research workspace for evidence-grounded analysis, reproducible workflows, and verifiable research artifacts. **In development; open-source licensing pending.**

**Core principles:** Evidence-grounded · Reproducible · Local-first · Extensible · Human-controlled

**独立于 MicroBubble Agent。** The predecessor project is engineering experience only; it imposes no architectural constraint here, no code is imported from it, and none of its runtime assumptions carry over.

## Repository topics

`ai-agent` · `research-agent` · `scientific-research` · `local-first` · `reproducibility` · `research-tools` · `llm` · `python` · `in-development`

## Why LabCairn?

Many AI tools can draft an answer. In research, the harder questions are: *Where did that number come from? Which dataset, sheet or paper passage supports a claim? How was the figure generated? What changed between versions? What remains unverified?*

LabCairn is being built to make those questions first-class parts of the workflow.

## Planned first release (Phase 1)

- **Local research workspace:** bind explicitly selected directories; preserve originals and isolate generated outputs.
- **Scientific material intake:** text-based PDFs, Markdown, plain text (TXT), CSV and XLSX with locators to pages, sections and data cells.
- **Evidence trail:** attach source anchors, verification states and limitations to significant claims and numerical facts.
- **Bounded research Agent:** provider-configurable model calls, typed tools, a task plan and scoped human approvals.
- **Reproducible starter analysis:** approved deterministic summary statistics and figures with retained input hashes, parameters and source scripts/recipes.
- **Editable research deliverables:** Markdown report, basic DOCX/PDF export and artifact manifest.
- **Durable work:** tasks, runs, checkpoints, resume and revision history, with no blind repetition of uncertain side effects.
- **Two entry points:** CLI for developers and local Web UI for researchers, backed by the same core.

*Not in Phase 1:* arbitrary model-generated shell/Python execution, autonomous submission/publication, unsandboxed browser automation, large multi-agent swarms, guaranteed fully offline usage, or claims of scientific validation based solely on a passing format check.

## Planned architecture

- **Core:** Python 3.12, Pydantic AI, Pydantic v2
- **Persistence:** SQLite, SQLAlchemy, Alembic
- **Interfaces:** Typer CLI, FastAPI, React + TypeScript + Vite
- **Research tools:** PyMuPDF, pandas, NumPy, SciPy, Matplotlib, openpyxl, reference metadata adapters
- **Quality:** pytest, Vitest, Playwright, ruff, mypy, GitHub Actions

PyMuPDF is named by the intake work order (LC-P1-08) and Matplotlib by the bounded analysis work order (LC-P1-10); the remaining scientific libraries are **candidates** serving those same ingestion and deterministic-analysis responsibilities, and are only adopted if a work order justifies them. This list is a planning target, not a committed dependency set.

Tool execution and network disclosure are subject to explicit capabilities and permission boundaries. Local-first means local project state and artifacts by default, **not** that remote model calls never transmit selected material.

## Project development status

The project is currently at **Phase 1 / Foundation & MVP**. The research workflow is still under construction; the command line below is what exists today, and the rest arrives as its paths are implemented and verified.

- [Four-stage roadmap](docs/ROADMAP.md)
- [Phase 1 development work orders and acceptance gates](docs/PHASE_1_WORKORDERS.md)
- [Architecture and data boundaries](docs/ARCHITECTURE.md)
- [Evaluation protocol](docs/EVALUATION.md)
- [Upstream source-study strategy, pinned references and license policy](docs/UPSTREAM_REFERENCES.md)

## Developer setup (what exists today)

This is the **engineering baseline only**: the pinned interpreter, the dependency lock, the quality gates and the test suites. It is not a product install, and running it does not give you a LabCairn application. There **is** a command line, and it is described below; it is a developer-facing surface, not a finished product. Every command below is a repository-maintenance command, and `tests/test_readme_accuracy.py` executes each one and fails if any stops working.

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is provisioned by it) and, for the web package, Node ≥ 24.16 with pnpm ≥ 9.15.9.

Python side, from the repository root:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Web side, from `web/`:

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm lint
pnpm format:check
```

`uv run pytest` runs the Python suite and `pnpm test` runs the Vitest suite. Neither needs an API key, a network call or a paid provider: the executable product code today is the deterministic `FakeProvider` under `src/labcairn/core/providers/`, which is exercised entirely from tests, and the `labcairn` command line, which talks only to a local workspace.

## The command line (what exists today)

`labcairn` is a real console script, installed by `uv sync`, and it is the developer-facing surface on the same application layer the local API and the web workbench call — so what it reports is what they report.

The research workflow behind these commands is still under construction, and most of what the Phase 1 work orders promise is still to come. The command line is here because the surface, its machine-readable form and its exit codes are settled, and the work that fills them in is still ahead.

```bash
uv run labcairn --help
```

The commands, and what each can do today:

| Command | What it does | State today |
|---|---|---|
| `labcairn init` | Creates a workspace — the directory, a migrated SQLite database, a source directory and a policy file — and reports what it made; it refuses to overwrite a workspace that is already there | works |
| `labcairn doctor` | Reports the workspace, the database's revision, the policy's rules and each model provider's declared capabilities | works, and it only *reports*: it repairs nothing |
| `labcairn task create` | Makes a task, its output area and its first event, and binds it to the material the workspace holds | works |
| `labcairn task run` | Runs the `inventory` stage over a bound material, in the task's current run | works for the `inventory` stage only; the other declared stages belong to later work orders |
| `labcairn task resume` | The same stage in a **new** attempt — a new Run against the same Task, never a new Task | works for the `inventory` stage only |
| `labcairn task status` | Reports the task's state: its runs, stages, artefacts, approvals and event cursor; `--plan` reports the declared workflow instead | works |
| `labcairn sources inspect` | Reports one source as the ledger holds it | works, for material the workspace has ingested |
| `labcairn sources ingest` | Reads the workspace's supplied material through the permission boundary, stores it in the ledger, and binds it to the task | works; a file it cannot read is reported, not swallowed |
| `labcairn artifacts list` | Lists the receipts a task has produced | works |
| `labcairn serve` | Starts the local API service on `127.0.0.1:8000` and serves the workspace's current task; it binds loopback only, mints its own session token and writes it to the workspace rather than printing it | works, and the event stream and the stage bodies are refused by the layer until the packages that own them are wired in |

**Every command has a machine-readable form.** `--json` prints the same model the rendered output draws, byte for byte, so a script depends on the JSON and not on the prose. The two commands that report on a workspace rather than on a task — `init` and `doctor` — carry their own models, because the application layer has no operation that reports a workspace.

**Exit codes are part of the contract.** `0` is a result, `2` is a usage error, `3` is a refusal by the application layer, and `1` is a crash, so a script tells a refusal from a crash by the exit code alone. A refusal is rendered rather than raised: it names what was refused, carries the layer's `reason` and `message` in the JSON form, and writes nothing to standard output.

**`doctor` reports; it does not repair.** It says what it found. It will not fix a broken database, write a missing policy, or reach a paid model endpoint unless `--probe` says so.

## Principles

1. Evidence is not the same as truth: record locators and verification state; show uncertainty.
2. An AI-generated result does not become verified because a tool succeeded.
3. Source materials stay read-only by default; writes target a dedicated task output area.
4. Task identity and artifact history survive interruptions; never replay uncertain side effects blindly.
5. Network disclosure, code execution and external actions require explicit, inspectable authorization.
6. Every milestone must include a reproducible demonstration and an honest limitations section.

## Licence status — not yet granted

**License status: not yet granted.** The repository is public and readable, but it deliberately carries **no `LICENSE` file**: copyright ownership has not been cleared, so no open-source rights have been conveyed to anyone. Nothing here grants permission to use, study, modify or redistribute this code.

- `LICENSE.PENDING.md` **does not** grant rights and must not be read as an MIT grant.
- The absence of a restrictive `LICENSE` file is **not** permissiveness. Silence is not permission.
- Planned licensing remains MIT for original LabCairn code, subject to a dependency review that is still open — `PyMuPDF` is AGPL/commercial dual-licensed and is named by LC-P1-08, so that decision is unresolved.
- Third-party adaptations must retain required notices and comply with their own licences.

This README is not a substitute for a licence. LabCairn is independently developed and is not affiliated with OpenHands, Pydantic AI, Deep Agents, PaperQA2 or PaperSpine.

## 中文简介

LabCairn（研迹）是一个面向科研人员的本地优先 AI 研究工作台，正在建设中，**计划在版权归属明确后以开源许可证发布；目前尚未授予任何开源权利**。它计划把文献、实验数据、分析方法、科研论断和可编辑成果连接起来，让研究过程能够定位来源、保留修改历史并在必要时重新核验。项目目前处于第一阶段建设中；尚未发布的能力均为规划目标。
