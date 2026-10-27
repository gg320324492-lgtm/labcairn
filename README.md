# LabCairn · 研迹

**Research that leaves a trail. · 让每一步研究，都有迹可循。**

> **Status: Design / Phase 1 under construction.** This repository is a new project. Features listed below are planned, not yet shipped. Do not use the current code for unsupported scientific or safety-critical decisions.

**Read this page in:** English · [中文](#中文版--chinese-version) · the standalone Chinese document is [README.zh-CN.md](README.zh-CN.md).

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
- **Research tools:** pdfplumber and pdfminer.six (PDF), openpyxl (spreadsheets), Matplotlib (figures), python-docx and reportlab (export), pandas, NumPy, SciPy, reference metadata adapters
- **Quality:** pytest, Vitest, Playwright, ruff, mypy, GitHub Actions

The PDF library was named by the intake work order (LC-P1-08) and settled by [ADR-0008](docs/adr/ADR-0008-pdf-ingestion-library.md) on `pdfplumber` and `pdfminer.six`, both MIT; Matplotlib was named by the bounded analysis work order (LC-P1-10) and settled by [ADR-0012](docs/adr/ADR-0012-chart-rendering-library.md). pandas, NumPy and SciPy are **candidates** serving those same ingestion and deterministic-analysis responsibilities, and are only adopted if a work order justifies them. This list is a planning target, not a committed dependency set.

Tool execution and network disclosure are subject to explicit capabilities and permission boundaries. Local-first means local project state and artifacts by default, **not** that remote model calls never transmit selected material.

## Project development status

The project is currently at **Phase 1 / Foundation & MVP**. The research workflow is still under construction; the command line below is what exists today, and the rest arrives as its paths are implemented and verified.

- [Four-stage roadmap](docs/ROADMAP.md)
- [Phase 1 development work orders and acceptance gates](docs/PHASE_1_WORKORDERS.md)
- [Architecture and data boundaries](docs/ARCHITECTURE.md)
- [Evaluation protocol](docs/EVALUATION.md)
- [Threat model — what the product protects, and what it does not claim](docs/THREAT-MODEL.md)
- [Upstream source-study strategy, pinned references and license policy](docs/UPSTREAM_REFERENCES.md)

## Start here

**[docs/QUICKSTART.md](docs/QUICKSTART.md)** is the walkthrough. It takes a directory holding a text PDF, a CSV and a Markdown, binds it, creates a task, produces a report with source locators and an evidence ledger, makes one revision, and reopens the same task after a restart — and every step it names is either a command [the command line](#the-command-line-what-exists-today) has today, or a step the repository's own walk script makes.

**That walk script is `scripts/outsider_path.py`**, and it is the one command that runs the whole path: it clones the repository outside the checkout, runs the commands above there for real, and makes every step of the walk a check that raises rather than warns — so its exit code is the assertion.

**[docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md)** carries what this alpha does **not** do. It is the larger half of the handoff, and it is worth reading before you decide whether the alpha is any use to you.

**[docs/acceptance/LC-P1-14-outsider-path.md](docs/acceptance/LC-P1-14-outsider-path.md)** is the measured record of the walk the quickstart describes, and **[CHANGELOG.md](CHANGELOG.md)** says what changed.

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

**`labcairn task report` renders the report; nothing draws the figure.** The report path is now a command and a route on the local service, both calling the application layer's own `render_report`, and a fresh workspace's policy permits `report.render` — which the registry binds to the task's own output area. **The deterministic figure is still reached only through the layer's `run_analysis`**: no command and no route asks it. And a report needs something to carry: **no operation writes an evidence record**, so a task with nothing to report is refused with a reason and writes nothing at all. The quickstart says where that leaves a reader, and the release notes carry it as a known limitation rather than a surprise.

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
- Planned licensing remains MIT for original LabCairn code, subject to a dependency review that is still open — `PyMuPDF` is AGPL/commercial dual-licensed and was named by LC-P1-08, but [ADR-0008](docs/adr/ADR-0008-pdf-ingestion-library.md) decided against it: the PDF dependency is `pdfplumber` and `pdfminer.six`, both MIT, so `PyMuPDF` is not in the dependency graph.
- Third-party adaptations must retain required notices and comply with their own licences.

This README is not a substitute for a licence. LabCairn is independently developed and is not affiliated with OpenHands, Pydantic AI, Deep Agents, PaperQA2 or PaperSpine.

## 中文版 / Chinese version

本节是本文件的完整中文版本；独立排版的中文文档见 [README.zh-CN.md](README.zh-CN.md)。两处内容一致。

> **状态：设计阶段 / 第一阶段在建。** 本仓库是一个新项目。下面列出的能力均为**规划目标，尚未交付**。请勿将当前代码用于缺乏科学依据或安全攸关的决策。

**LabCairn（研迹）**是一个面向科研人员的本地优先 AI 研究工作台，**正在建设中，计划在版权归属明确后以开源许可证发布；目前尚未授予任何开源权利**。它计划把文献、实验数据、分析方法、科研论断和可编辑成果连接起来，让研究过程能够定位来源、保留修改历史并在必要时重新核验。

**它目前还不是开源软件。** 仓库尚未授予任何许可证，因此使用、研究、修改或再分发它都还没有获得授权。详见[许可证状态](#许可证状态--尚未授予)。

LabCairn 不打算取代科研判断，也不声称能自主完成科学发现。它计划让 AI 辅助的研究**可检视、在数据与方法允许的范围内可复现、并且更容易修订**。

### 为什么叫这个名字

*Lab*（实验室）+ *cairn*（石堆、路标）。石堆是徒步者留在路上、标记已走过的路线的石头。它正是一个研究智能体该有的意象：成果不是答案，而是**后来的人能顺着它回到来源的那条路径**。石堆不会告诉你山在哪里；它告诉你有人来过这里，以及是怎么来的。

这也正是本项目刻意**不**叫 `PaperAgent` 或 `AutoScientist` 的原因。前者暗示是论文写作软件，后者暗示是自主科学发现；两者都比这里的意图狭窄——这里的意图横跨材料、数据、代码与产出。

### 定位

> 一个面向有证据支撑的分析、可复现的工作流与可核验科研产物的本地优先 AI 研究工作台。**在建中；开源许可证待定。**

**核心原则：** 证据优先 · 可复现 · 本地优先 · 可扩展 · 人来掌舵

**独立于 MicroBubble Agent。** 前身项目只是工程经验的积累；它对本项目不施加任何架构约束，这里没有从它导入任何代码，它的任何运行时假设都没有延续过来。

### 仓库标签

`ai-agent` · `research-agent` · `scientific-research` · `local-first` · `reproducibility` · `research-tools` · `llm` · `python` · `in-development`

### 为什么是 LabCairn？

许多 AI 工具能起草一份答案。而在科研中，更难的问题是：*那个数字从哪来？哪个数据集、哪张表或哪段论文支撑这个论断？图是怎么生成的？版本之间改了什么？还有什么没有核实？*

LabCairn 正在被建造成让这些问题成为工作流里一等公民的东西。

### 计划中的首个版本（第一阶段）

- **本地研究工作区：** 显式绑定选定的目录；保留原件，把生成物隔离到别处。
- **科研材料摄取：** 文本型 PDF、Markdown、纯文本（TXT）、CSV 与 XLSX，带指向页、章节与数据单元的定位符。
- **证据链：** 为重要论断与数值事实附上来源锚点、核验状态与局限说明。
- **有边界的科研智能体：** 可配置供应商的模型调用、有类型的工具、任务计划与限定范围的人工批准。
- **可复现的起步分析：** 经批准的确定性统计量与图，保留输入哈希、参数以及来源脚本/配方。
- **可编辑的科研交付物：** Markdown 报告、基础 DOCX/PDF 导出与产物清单。
- **耐久的作业：** 任务、运行、检查点、恢复与修订历史，不盲目重放不确定的副作用。
- **两个入口：** 面向开发者的命令行与面向科研人员的本地 Web 界面，二者共用同一个核心。

*不在第一阶段内：* 任意由模型生成的 shell/Python 执行、自主提交或发表、未加沙箱的浏览器自动化、大型多智能体集群、保证完全离线可用，或仅凭格式检查通过就声称科学验证有效。

### 计划中的架构

- **核心：** Python 3.12、Pydantic AI、Pydantic v2
- **持久化：** SQLite、SQLAlchemy、Alembic
- **界面：** Typer 命令行、FastAPI、React + TypeScript + Vite
- **科研工具：** pdfplumber 与 pdfminer.six（PDF）、openpyxl（表格）、Matplotlib（图）、python-docx 与 reportlab（导出）、pandas、NumPy、SciPy、引用元数据适配器
- **质量：** pytest、Vitest、Playwright、ruff、mypy、GitHub Actions

PDF 库由摄取工单（LC-P1-08）点名，由 [ADR-0008](docs/adr/ADR-0008-pdf-ingestion-library.md) 定为 `pdfplumber` 与 `pdfminer.six`（均为 MIT）；Matplotlib 由有边界的分析工单（LC-P1-10）点名，由 [ADR-0012](docs/adr/ADR-0012-chart-rendering-library.md) 定下。pandas、NumPy 与 SciPy 是服务同样职责的**候选**，只有在工单给出理由时才会采用。这份清单是规划目标，不是已承诺的依赖集合。

工具执行与网络披露受明确的能力与权限边界约束。本地优先意味着项目状态与产物默认留在本地，**并不意味着**远程模型调用绝不传输被选中的材料。

### 项目开发状态

项目目前处于**第一阶段 / 基础与 MVP**。科研工作流仍在建设中；下面列出的命令行是今天真实存在的东西，其余部分会随路径被实现和验证后到来。

- [四阶段路线图](docs/ROADMAP.md)
- [第一阶段开发工单与验收关口](docs/PHASE_1_WORKORDERS.md)
- [架构与数据边界](docs/ARCHITECTURE.md)
- [评估协议](docs/EVALUATION.md)
- [威胁模型——产品保护什么，以及不声称什么](docs/THREAT-MODEL.md)
- [上游源码研读策略、固定引用与许可证政策](docs/UPSTREAM_REFERENCES.md)

### 从这里开始

**[docs/QUICKSTART.md](docs/QUICKSTART.md)**（英文）是上手向导：它带着一个含文本型 PDF、CSV 与 Markdown 的目录走完全程——绑定、建任务、产出带来源定位符与证据账本的报告、做一次修订，并在重启后重新打开同一个任务——而它提到的每一步，要么是[命令行](#命令行今天有什么)今天就有的命令，要么是仓库自带脚本所走的一步。

**那份走查脚本就是 `scripts/outsider_path.py`**，也是把整条路径跑完的唯一一条命令：它把仓库克隆到检出目录之外，在克隆里真实地跑上面的命令，并把走查的每一步都变成"不成立就抛出"的检查——所以它的退出码就是断言。

**[docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md)**（英文）记录本次 alpha **不**做什么。那是交付材料里更大的一半。

**[docs/acceptance/LC-P1-14-outsider-path.md](docs/acceptance/LC-P1-14-outsider-path.md)**（英文）是快速上手所描述的那条路径的实测记录；**[CHANGELOG.md](CHANGELOG.md)**（英文）记录变更。

### 开发环境（今天有什么）

这只是**工程基线**：固定的解释器、依赖锁、质量关卡与测试套件。它不是产品安装，跑通它也不会给你一个可用的 LabCairn 应用。**确实有**一个命令行，下面会介绍；它是面向开发者的界面，不是完成品。下面每一条命令都是仓库维护命令，`tests/test_readme_accuracy.py` 会逐条执行，任何一条不再可用都会让测试变红。

需要 [uv](https://docs.astral.sh/uv/)（Python 3.12 由它自动准备），Web 包还需要 Node ≥ 24.16 与 pnpm ≥ 9.15.9。

Python 侧，在仓库根目录执行：

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Web 侧，在 `web/` 目录执行：

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm lint
pnpm format:check
```

`uv run pytest` 跑 Python 测试套件，`pnpm test` 跑 Vitest 套件。两者都不需要 API 密钥、网络调用或付费供应商：今天可执行的产品代码是 `src/labcairn/core/providers/` 下确定性的 `FakeProvider`，它完全由测试驱动；以及 `labcairn` 命令行，它只与本地工作区对话。

### 命令行（今天有什么）

`labcairn` 是真实的 console script，由 `uv sync` 安装，它是本地 API 与 Web 工作台所调用的同一应用层上的开发者界面——所以它报告什么，它们就报告什么。

这些命令背后的科研工作流仍在建设中，第一阶段工单承诺的大部分能力仍在后面。命令行之所以先在，是因为界面、它的机器可读形式以及退出码都已经定下来了，而填满它们的工作还在前面。

```bash
uv run labcairn --help
```

命令清单，以及每条今天能做什么：

| 命令 | 做什么 | 今天的状态 |
|---|---|---|
| `labcairn init` | 创建一个工作区——目录、已迁移的 SQLite 数据库、源目录与策略文件——并报告它做了什么；已有工作区时它拒绝覆盖 | 可用 |
| `labcairn doctor` | 报告工作区、数据库的修订号、策略的规则，以及每个模型供应商标称的能力 | 可用，而且它只*报告*：它不修复任何东西 |
| `labcairn task create` | 建一个任务、它的输出区和第一条事件，并把它绑定到工作区持有的材料上 | 可用 |
| `labcairn task run` | 在任务当前的运行里，对已绑定的材料跑 `inventory` 阶段 | 只对 `inventory` 阶段可用；其余已声明阶段属于后续工单 |
| `labcairn task resume` | 同一阶段的**新**一次尝试——针对同一个 Task 的新 Run，绝不是新 Task | 只对 `inventory` 阶段可用 |
| `labcairn task status` | 报告任务的状态：它的运行、阶段、产物、批准与事件游标；`--plan` 报告声明的工作流 | 可用 |
| `labcairn sources inspect` | 按账本持有的样子报告一份材料 | 可用，针对工作区已摄取的材料 |
| `labcairn sources ingest` | 通过权限边界读取工作区提供的材料，把它存进账本并绑定到任务 | 可用；读不了的文件会被报告出来，而不是被吞掉 |
| `labcairn artifacts list` | 列出任务产出的收据 | 可用 |
| `labcairn serve` | 在 `127.0.0.1:8000` 上启动本地 API 服务并提供工作区当前的任务；它只绑定回环地址，自行签发会话令牌并写入工作区，而不是打印出来 | 可用；在拥有它们的包接好之前，事件流与阶段请求体会被该层拒绝 |

**每条命令都有机器可读形式。** `--json` 打印的是渲染输出所依据的同一个模型，逐字节相同，因此脚本依赖的是 JSON 而不是散文。两条针对工作区而非任务的命令——`init` 与 `doctor`——各自带自己的模型，因为应用层没有"报告一个工作区"的操作。

**退出码是契约的一部分。** `0` 是结果，`2` 是用法错误，`3` 是应用层的拒绝，`1` 是崩溃，所以脚本只凭退出码就能区分拒绝与崩溃。拒绝是被渲染出来的而不是被抛出的：它说明拒绝了什么，在 JSON 形式里带上该层的 `reason` 与 `message`，并且不往标准输出写任何东西。

**`doctor` 只报告，不修复。** 它说出它发现了什么。它不会修复损坏的数据库、不会补写缺失的策略，也不会去够付费模型端点——除非 `--probe` 这么要求。

**`labcairn task report` 能渲染报告；没有任何命令能画图。** 报告路径现在既有命令也有本地服务的对应路由，两者都调用应用层自己的 `render_report`，而且全新工作区的策略允许 `report.render`——注册表把这一能力绑定在任务自己的输出区。**确定性图仍然只能通过应用层的 `run_analysis` 到达**：命令行和服务都没有为它提供入口。而报告需要有内容可承载：**没有任何操作会写入证据记录**，所以一个无话可说的任务会被拒绝并给出理由，且不会写下任何文件。快速上手会说明这对读者意味着什么；发布说明把它作为已知限制列出，而不是留作意外。

### 原则

1. 证据不等于真相：记录定位符与核验状态；把不确定性显示出来。
2. 工具跑成功了，AI 生成的结果也不会因此变成已核验。
3. 源材料默认只读；写入只落在任务专属的输出区。
4. 任务身份与产物历史经得起中断；绝不盲目重放不确定的副作用。
5. 网络披露、代码执行与对外动作都需要明确且可检视的授权。
6. 每个里程碑都必须包含一个可复现的演示和一节诚实的局限性说明。

### 许可证状态 —— 尚未授予

**许可证状态：尚未授予。** 仓库公开可读，但它刻意**不带 `LICENSE` 文件**：版权归属尚未理清，因此没有向任何人授予任何开源权利。这里的任何内容都不授予使用、研究、修改或再分发本代码的许可。

- `LICENSE.PENDING.md` **不**授予任何权利，也不得被当作一份 MIT 授权来读。
- 没有限制性 `LICENSE` 文件**不等于**宽松。沉默不是许可。
- 计划中的许可证对 LabCairn 原创代码仍是 MIT，但这一决定取决于一次尚未结束的依赖审查——`PyMuPDF` 是 AGPL/商业双许可，并由 LC-P1-08 点名，但 [ADR-0008](docs/adr/ADR-0008-pdf-ingestion-library.md) 已决定不用它：PDF 依赖是 `pdfplumber` 与 `pdfminer.six`，两者均为 MIT，因此 `PyMuPDF` 不在依赖图里。
- 第三方改编必须保留所要求的声明，并遵守它们各自的许可证。

本 README 不能替代许可证。LabCairn 独立开发，与 OpenHands、Pydantic AI、Deep Agents、PaperQA2 或 PaperSpine 无隶属关系。

