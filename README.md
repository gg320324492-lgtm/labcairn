# LabCairn · 研迹

**Research that leaves a trail. · 让每一步研究，都有迹可循。**

> **Status: Design / Phase 1 under construction.** This repository is a new project. Features listed below are planned, not yet shipped. Do not use the current code for unsupported scientific or safety-critical decisions.

**LabCairn** is an open-source, local-first AI research workspace designed to help researchers work across papers, data, analysis and reports while keeping a traceable link between sources, claims, methods and outputs.

LabCairn is not intended to replace scientific judgment or claim autonomous scientific discovery. It aims to make AI-assisted research **inspectable, reproducible where the underlying data and methods permit it, and easier to revise**.

### Why this name

*Lab* + *cairn*. A cairn is the pile of stones a hiker leaves to mark a route that has already been walked. It is the right image for a research agent: the work is not the answer, it is the **path that a later reader can follow back to the source**. A cairn does not tell you where the mountain is; it tells you someone came this way, and here is how.

This is also why the project is deliberately **not** named `PaperAgent` or `AutoScientist`. The first would suggest paper writing software; the second would suggest autonomous scientific discovery. Both are narrower than the intent, which spans material, data, code and output.

### Positioning

> An open-source, local-first AI research workspace for evidence-grounded analysis, reproducible workflows, and verifiable research artifacts.

**Core principles:** Evidence-grounded · Reproducible · Local-first · Extensible · Human-controlled

**独立于 MicroBubble Agent。** The predecessor project is engineering experience only; it imposes no architectural constraint here, no code is imported from it, and none of its runtime assumptions carry over.

## Repository topics

`ai-agent` · `research-agent` · `scientific-research` · `local-first` · `reproducibility` · `research-tools` · `llm` · `python` · `open-source`

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

The project is currently at **Phase 1 / Foundation & MVP**. Installation instructions and executable demos will be added only after the corresponding paths are implemented and verified.

- [Four-stage roadmap](docs/ROADMAP.md)
- [Phase 1 development work orders and acceptance gates](docs/PHASE_1_WORKORDERS.md)
- [Architecture and data boundaries](docs/ARCHITECTURE.md)
- [Evaluation protocol](docs/EVALUATION.md)
- [Upstream source-study strategy, pinned references and license policy](docs/UPSTREAM_REFERENCES.md)

## Principles

1. Evidence is not the same as truth: record locators and verification state; show uncertainty.
2. An AI-generated result does not become verified because a tool succeeded.
3. Source materials stay read-only by default; writes target a dedicated task output area.
4. Task identity and artifact history survive interruptions; never replay uncertain side effects blindly.
5. Network disclosure, code execution and external actions require explicit, inspectable authorization.
6. Every milestone must include a reproducible demonstration and an honest limitations section.

## Open source and attribution

**License status: not yet granted.** The repository exists (`gg320324492-lgtm/labcairn`) but deliberately carries **no `LICENSE` file**: copyright ownership has not been cleared, so no open-source rights have been granted to anyone. A placeholder such as `LICENSE.PENDING.md` **does not** grant rights and must not be read as an MIT grant. Planned licensing remains MIT for original LabCairn code, subject to a dependency review that is still open — `PyMuPDF` is AGPL/commercial dual-licensed and is named by LC-P1-08, so that decision is unresolved. This README is not a substitute for a license. Third-party adaptations must retain required notices and comply with their own licenses. LabCairn is independently developed and is not affiliated with OpenHands, Pydantic AI, Deep Agents, PaperQA2 or PaperSpine.

## 中文简介

LabCairn（研迹）是一个面向科研人员的开源、本地优先 AI 研究工作台。它计划把文献、实验数据、分析方法、科研论断和可编辑成果连接起来，让研究过程能够定位来源、保留修改历史并在必要时重新核验。项目目前处于第一阶段建设中；尚未发布的能力均为规划目标。
