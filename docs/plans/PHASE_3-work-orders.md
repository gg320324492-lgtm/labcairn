# Phase 3 — the G1 work orders: `LC-P3-01` and `LC-P3-02`

**Status:** the official Phase 3 G1 work orders, issued 2026-11-08 on the
owner's decisions recorded in §2. **Issuing a work order is not doing the work.**
No implementation has begun, no window has been opened, no witness has run, no
real browser or desktop host was started, no Phase 3 gate has passed, and no
push, pull request or CI run is authorised by this document.

**Date:** 2026-11-08.

**Anchors, printed live at writing.** `git rev-parse HEAD` is
`d38010e9b8cf270beb19c38d6979ea14284c318d` and `git rev-parse origin/main` is
the same commit — the fourteen-commit documentation batch landed as PR #152 and
the two are aligned as this file was written. Every other value here is either
measured live on 2026-11-08 against this tree, or quoted from a dated record
that is named where it is quoted. A window that works these tickets re-measures
the anchors, the gap-register rows and the host versions at dispatch: this file
is not a carry-forward of them.

**Authority, in three parts.**
[`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §1 adopted
`LC-P3-00` … `LC-P3-08` as formal ticket ids with the sequence named in
[`PHASE_3-execution-plan.md`](PHASE_3-execution-plan.md) §3, and recorded that
*adoption of a label is not dispatch*. That plan's §3 gives each ticket's stage
and completion evidence, §4 is the acceptance checklist these two tickets map
onto, and §6 is the code-facing gap register whose rows they quote. The owner's
decisions of 2026-11-08 (§2 below) answered the six open decision points the
preparation package left to the owner, which is the word `LC-P3-00` §1 waits
for. The preparation package itself lives outside the repository, is not
evidence of any run, and is not cited here as one; where its draft disagreed
with this tree, this file follows the tree, and §4.4 and §7 say which two items.

**The gate-name caution this file needs.** Phase 3 names its stages `G0` … `G4`
and Phase 1 already used those five letters for gates that are closed. Every
"G1" in this file means **Phase 3 G1**.
[`../PHASE_1_WORKORDERS.md`](../PHASE_1_WORKORDERS.md),
[`../acceptance/G1-evidence.md`](../acceptance/G1-evidence.md) and the `## Gates`
table in [`../handoff/CURRENT.md`](../handoff/CURRENT.md) are Phase 1's records
and keep their meaning. Phase 3 G0 is not declared closed here: `LC-P3-00` is a
dated decision record, not a gate verdict.

---

## 1. The board at this writing

Status vocabulary is the project's own — `NOT STARTED` · `IN PROGRESS` · `PASS`
· `PASS WITH NOTES` · `BLOCKED` · `FAIL` — and **no Phase 3 row is `PASS` or
`PASS WITH NOTES`**. A row moves in the same commit as the evidence that moves
it, and never because something looks finished.

| Ticket | Stage | Status | What the row rests on |
|---|---|---|---|
| `LC-P3-00` | Phase 3 G0 | decision record, landed 2026-11-07 | [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) — a dated owner decision record, not a gate verdict. |
| `LC-P3-01` | Phase 3 G1 | **`NOT STARTED`** — work order issued 2026-11-08 (§4) | This file. No browser was started and no witness ran. |
| `LC-P3-02` | Phase 3 G1 | **`NOT STARTED`** — work order issued 2026-11-08 (§5) | This file. No sample was written, opened or reopened. |
| `LC-P3-03`, `LC-P3-04` | Phase 3 G2 | `NOT STARTED` — no work order written | Execution plan §3; `03` follows `01` and `02`. |
| `LC-P3-05` | Phase 3 G3 | `NOT STARTED` — no work order written | Execution plan §3; scoped as written per `LC-P3-00` §6. |
| `LC-P3-06` | Phase 3 G3 | **`BLOCKED`** | `LC-P3-00` §4 and §2 item 5 below: the seven provider fields are unnamed. |
| `LC-P3-07`, `LC-P3-08` | Phase 3 G4 | `NOT STARTED` — no work order written | Execution plan §3. |

Source questions **Q77** and **Q82** stay open at their own triggers
(`LC-P3-00` §8, execution plan §8), unchanged by anything here.

---

## 2. What the owner decided, and where each decision lands in these tickets

| # | The decision of 2026-11-08 | What it settles | Where it binds |
|---|---|---|---|
| 1 | **Browser driver: Playwright**, taking the **system-browser channel** where one exists so the run does not add a browser download. The driver package itself still has to be installed. | The choice the preparation package left to the owner. | §4.4, §4.5, §4.10 |
| 2 | **COM and ProgID automation of a desktop host: not allowed.** The WPS and Office reopen checks are **human-performed checklist steps with recorded evidence**. | Whether the project may drive real desktop applications programmatically. It may not. | §3 rule 2, §4.9, §5.8 |
| 3 | **The real advisor sample comes after** the synthetic and substitute-first work, and until it is supplied it stays a **named gap**. | The timing `LC-P3-02` was waiting on. | §5.9, §8 |
| 4 | **The §4 checklist split, confirmed:** `LC-P3-01` carries the real-browser baseline **and** the dual-host reopen checks; `LC-P3-02` carries the DOCX revision loop **and** the real-sample half. | Which ticket is the basis for which row, and who runs the checklist. | §4.11, §5.8 |
| 5 | **The seven provider fields are decided after G1; `LC-P3-06` stays `BLOCKED`.** | No G1 ticket waits on the provider, and no G1 ticket may make an outbound call. | §1, §3 rule 1, §8 |
| 6 | **The write-seam path-length (MAX_PATH) repair rides the G1 implementation batch.** | Which batch takes the repair the gap register called "a batched implementation stage decision". | §7, §5.6 |
| 7 | **Q77 and Q82 stay at their triggers.** | Nothing is inferred from a source question whose original is missing. | §1, §8 |

---

## 3. Rules both G1 windows carry

Restated here because a window that has to look each one up separately is a
window that skips one.

1. **Substitute-first, zero outbound.** Public synthetic material and a
   substitute model behind the existing provider gate. No real provider call, no
   spend, no credential: `LC-P3-00` §4 keeps CI on substitutes, and Phase 2's
   `real_model_smoke = NOT RUN` and its 35 unaccepted model-proposal edges are
   cited from their own records, not restated as current facts.
2. **No COM, no ProgID, no UI automation of WPS or Word.** The trial machine does
   register `KWPS.Application` and `Word.Application.14` (`LC-P3-00` §5, measured
   live 2026-11-07); registering an automation surface is not permission to use
   it. Host-side open and reopen are recorded human steps (§4.9).
3. **A new test file registers in three places and gets a runner-measured
   cost:** `pytestmark` naming a gate class from `tests/evaluation/manifest.py`'s
   protocol classes, exactly one shard in `.github/ci-shards.json`, and a row in
   `tests/evaluation/manifest.py`'s gate table — with costs re-measured from a
   runner log by `python .github/remeasure_shards.py <run-id>`. A local timing is
   not a runner cost, and a file in no shard is a test a runner never runs
   (execution plan §6, last row). Extending an existing file skips the
   registration, not the shard-cost witness.
4. **File ownership is the contract.** The areas in §4.5 and §5.5 are the map. A
   window that needs a file outside its area says so instead of reaching for it.
   `01` and `02` may run in parallel precisely because their areas do not
   overlap; §7's write seam is a third area, not a shared one.
5. **A claim is a witness, and the witness must fail for the property.** Each
   assertion below is checked by its counter-mutation before any record reports
   it as holding; a mutation that leaves the assertion green tested nothing.
6. **A measurement says where it ran.** `.github/workflows/web.yml` runs its
   quality gate on `ubuntu-latest` only (measured live 2026-11-08, line 48), and
   execution plan §6 names the Windows browser pass as a separate gap for
   `LC-P3-01`. So every Windows-side number in this batch is locally measured
   until a runner says otherwise, and the report names which it was. Post-merge
   runner results stay outside the tree (`LC-P3-00` §7's A1/A6 ruling).
7. **Push, pull request and CI wait for the owner** (`CLAUDE.md`). One whole-suite
   run at a time; `--basetemp` and `TEMP`/`TMP`/`TMPDIR`/`MPLCONFIGDIR` outside
   the repository; status read from the command, never from a pipe.
8. **Public-boundary hygiene.** No sentence of advisor material, no owner-side
   absolute workspace path, no runner tally in a new file, and the CJK ceiling
   witness watches the Chinese run length of every tracked file this batch adds
   (`LC-P3-00` §7).

---

## 4. `LC-P3-01` — real-browser baseline

**4.1 Goal.** Drive the existing workbench (`web/`) in a **real browser** against
a **live local service** built by the app factory `labcairn serve` uses and
reached over a real HTTP socket, and turn the boundary
[`../THREAT-MODEL.md`](../THREAT-MODEL.md) §6.1 records as unexercised into
measured evidence plus a named-gap list — before `LC-P3-05` chooses a desktop
shell, which is what execution plan §6's first gap-register row requires.

**4.2 Scope.** The wire and the render: `create_app` → a socket → the page the
participant sees. In-process transports are out of scope *as evidence*:
`tests/test_workbench_live_service.py:142` drives the service through
`httpx.ASGITransport` (measured live 2026-11-08), and
[`../THREAT-MODEL.md`](../THREAT-MODEL.md) §6.1 records that every web test stops
at the `fetch` boundary `web/src/test/fakeApi.ts` answers. The nearest precedent
is that same witness: it compares `GET /task` with `task status --json` field for
field before and after a `POST /task/select`. This ticket carries that comparison
across the socket and into a rendered page.

**4.3 Non-goals.** No desktop shell, installer, Electron/Tauri/PyInstaller
configuration (`LC-P3-05`). No import receipt, independent-copy transaction or
publication receipt (`LC-P3-03`). No proposal-to-approved-edit binding
(`LC-P3-04`). No real model and no outbound call (`LC-P3-06`). No DOCX fidelity
experiment (§5). No performance or load claim: a browser pass measures that the
path works and what it shows, and how well is not a question this ticket answers.

**4.4 Starting state, measured live 2026-11-08.**

| Fact | Measured at |
|---|---|
| `web/package.json` carries `jsdom 30.1.2` and **no** Playwright, Puppeteer, Selenium or Electron package | `web/package.json`, 2026-11-08. `jsdom` is not a browser and does not exercise the wire, so the driver decision (§2 item 1) has an install cost this ticket records rather than assumes away. |
| The web quality gate runs on `ubuntu-latest` | `.github/workflows/web.yml:48`, 2026-11-08 |
| The service is reachable in tests only through an in-process transport | `tests/test_workbench_live_service.py:142`, 2026-11-08 |
| The stream is read with the client's own `fetch`, never `EventSource` | [`../THREAT-MODEL.md`](../THREAT-MODEL.md) **§6.2** (line 637), 2026-11-08 — the preparation draft cited §6.1 for this and its own freshness review corrected it; §6.2 is the row in this tree |

**4.5 Areas this window owns.**

| Area | What it is for |
|---|---|
| a browser-driving witness in `tests/`, **or** an extension of `tests/test_workbench_live_service.py` | The assertions of §4.8. Which of the two it is is the window's first recorded decision, and §3 rule 3 decides what registration follows. |
| the driver's installation point — the Python project **or** `web/package.json` with `web/pnpm-lock.yaml` | Playwright and its system-browser channel (§2 item 1). Whichever side carries it, the record names the side, the driver version and the browser channel actually used. |
| a dated evidence record under `docs/acceptance/` | The measured result, the gap list, and the versions used. |
| [`../THREAT-MODEL.md`](../THREAT-MODEL.md) §6.1 and §6.2 | Updated in the same change as the evidence, so the boundary statement does not lag the run. This is the only G1 window that edits the threat model. |

It does **not** own `src/labcairn/workspace/outputs.py` or
`src/labcairn/security/paths.py` (§7), and it edits no dated Phase 1 or Phase 2
record.

**4.6 Dependencies.**

- **`LC-P3-00`, satisfied as a record.** Its numbering, gate split and reviewer
  form are what this ticket is written under. It is a dated decision record, not
  a claim that Phase 3 G0 is closed.
- **A driver that has to be installed.** §2 item 1 chose Playwright; the package
  is not in the tree today (§4.4), so the install is this ticket's first act, and
  which side carries it is §4.12.
- **Not on `LC-P3-02`.** Execution plan §3 says `01` and `02` may run
  independently, and neither blocks the other. The one ordering that does exist
  runs the other way: §4.9's checklist examines files §5 produces, so a substitute
  round-trip has to exist before the checklist can be performed.
- **Not on the provider.** `LC-P3-06` is `BLOCKED` (§2 item 5); this ticket neither
  waits on it nor unblocks it, and it makes no outbound call.
- **A sequencing constraint, not a dependency, on §7.** The browser path writes
  through the same output seam §7 repairs. This ticket does not edit that seam, and
  if its run reaches a deep workspace path it reports what it met instead of
  fixing it.

**4.7 Deliverables.**

1. A real-browser run against a live local service, with each assertion of §4.8
   carrying a witness that fails when its property is broken.
2. A **measured-gap list**: every boundary the run did not cover, each with its
   evidence address. Execution plan §3's own wording is the rule — *measured gaps
   are named, not assumed away* — and a run that reports no gaps has to show how
   it knows.
3. A record naming the browser and its version, the driver and its version, the
   system-browser channel used or why none was available, the platform, and
   whether each number came from this machine or from a runner.
4. The dual-host reopen checklist of §4.9, performed and recorded.

**4.8 Acceptance evidence — the minimum assertion set.**

- *Task and version switching.* The page drives `POST /task/select`; the rendered
  state panel shows `GET /task` bytes identical to `task status --json` for the
  same task — the field-for-field comparison the live-service witness established,
  now through a socket and a render.
- *Comment display.* An imported comment-bearing synthetic sample is visible in the
  workbench view that reads it.
- *Approval.* An approval action taken from the page produces the recorded state
  the API contract promises, and a second approval of the same item is refused as
  a duplicate.
- *Event reconnection.* The witness interrupts the stream and asserts that the
  page reports `connecting` / `reconnecting`, returns to `live` through the
  client's own resume cursor, and neither duplicates an event across the gap nor
  loses one. The path check, the base and the token boundary stay in the client
  because the client uses `fetch` and not `EventSource` (§4.4).
- *Refusal, visible to the page.* A cross-origin page context is refused by the
  `Origin` guard (`src/labcairn/api/guards.py`), a wrong or absent session token is
  refused, and each refusal reaches the screen. These defences have been exercised
  from the API side; this ticket exercises them from the client they defend
  against.

**4.9 The dual-host reopen checklist — human-performed, because COM is not
allowed.** This is the half the owner assigned to `LC-P3-01` in §2 item 4. It is
the instrument this ticket owns; the DOCX files it examines come from §5's
substitute runs. Nothing here is automated, and a recorded checklist is not a
pytest witness: its value is that a named person performed it and wrote down what
happened. Every row carries the artifact and its content hash, the host, **the
host's version re-measured at run time**, whether the file opened without a repair
prompt, what survived and what did not, who performed the step, when, and where
the evidence sits. The form to follow is the project's existing
[`../acceptance/G1-G2-human-review-checklist.md`](../acceptance/G1-G2-human-review-checklist.md),
which is a Phase 1 record.

| Step | Primary host — WPS Office, the acceptance host | Reference host — Microsoft Office 2010, the compatibility reference |
|---|---|---|
| Open each DOCX the substitute run exported | **The judge:** opens with no repair prompt; the comments and tracked revisions are present. | **Second judgement:** opens with no repair prompt. |
| Close, then reopen the same file | Comments, tracked revisions, equations, images, tables and relationships are as they were. | The same check; a repair prompt is a finding, not a retry. |
| Refusal cases | A structure the support matrix does not cover was refused or handed to a person, with the wording recorded. | Recorded identically. |

`LC-P3-00` §5 measured **WPS Office 12.1.0.29690** as the primary acceptance host
and **Microsoft Office 2010, file version 14.0.7252.5000** as the compatibility
reference on 2026-11-07. Those are anchors. If the trial machine changes before
these runs, the matrix is re-measured live before anyone uses it.

**4.10 Substitute boundary.**

| Allowed by substitution | Not substitutable |
|---|---|
| Offline public synthetic sample material | A real browser process. `jsdom` answers stubbed fetches: it is the boundary being measured, not a stand-in for it. |
| A substitute model behind the provider gate | The live service on a real socket. Replacing the in-process transports *is* the ticket. |
| Zero outbound requests and zero spend: the run is localhost | The Windows-side measurement. The web gate runs on Ubuntu, so a Windows browser pass is locally measured until a runner says otherwise. |

**4.11 Completion, and what this ticket is the basis for.** Done when every
assertion in §4.8 has a passing witness against a real browser and the live
service, the gap list is written with an evidence address per gap, the checklist of
§4.9 is recorded, and the record names browser, driver, channel and platform.
Mapping onto execution plan §4: this ticket is the **evidence channel** for the
"Import to delivery" row — the surface a trial participant uses is proven to drive
the endpoints the records claim — the browser-facing half of the "Permission and
privacy" row, and, by §2 item 4, the reopen half of "Original and format". It
satisfies none of those rows: every §4 row is judged at the Phase 3 G4 internal
trial on the installed build.

**4.12 Open items inside this ticket.** Which side carries the driver package
(Python or `web/`), and whether the witness is a new file or an extension of the
live-service witness, are the window's first recorded decisions — §2 item 1 settled
*which driver*, not *where it lands*. Which system-browser channel exists on the
trial machine is a measurement the window takes, not a fact carried here.

---

## 5. `LC-P3-02` — dual-host DOCX fidelity

**5.1 Goal.** Decide, with short samples and an editing ADR, whether the product
can edit an **existing** manuscript without damaging what it did not touch, and for
which host and which structures. Execution plan §6 states the gap: *"No proved
fidelity-preserving edit to an existing manuscript, no marked-draft and
clean-draft export from that edit, and no Word open/reopen matrix. `LC-P3-02` must
decide this with short samples and an editing ADR."*

**5.2 What kind of ticket this is.** Execution plan §3's stage outcome says G1
confirms the browser and the DOCX write paths, and it names the failure branch:
**if the G1 DOCX experiment cannot prove fidelity, automatic modification of that
structure is blocked and the support matrix is re-decided.** A "no" is a completion
of this ticket, not a failure of it — a "no" recorded with its measurements is what
the support matrix is for.

**5.3 Scope.** The read side that exists (`src/labcairn/material/ooxml.py`,
`src/labcairn/papers/revisions.py`, `src/labcairn/papers/alignment.py`) and the
report-only writer (`src/labcairn/reports/render/docx.py`, whose library boundary
is [`ADR-0013`](../adr/ADR-0013-report-export-libraries.md); `python-docx>=1.2,<2`
is what `pyproject.toml` declares — measured live 2026-11-08) against a Windows
host adaptation path, on short synthetic samples covering mixed comments and
tracked revisions, tables, equations and images. What is measured: the host and its
version, open and reopen results, what survived in the regions the edit did not
target, and what was refused.

**5.4 Non-goals.** Not the integrated loop: no project-scoped import receipt, no
read-only-original guard integration, no publication receipt (`LC-P3-03`); no
proposal-to-approved-edit-to-response-table binding and no quality report
(`LC-P3-04`). Not the reopen checklist, which §4.9 assigns to `LC-P3-01` — this
ticket produces the files and the fidelity measurements. No real model. No real
advisor material before it is supplied (§5.9). No support claim beyond the
structures and hosts actually measured.

**5.5 Areas this window owns.**

| Area | What it is for |
|---|---|
| the experiment's own modules under `src/labcairn/` and their tests | The option space, the measurements, and the refusal witnesses. Module names are the window's to record, not pre-decided here. |
| an editing ADR at the next free number in `docs/adr/` — measured live 2026-11-08, `ADR-0020-opinion-and-flag-sources.md` is the highest present, so **`ADR-0021`** | The options considered, what each measurement showed, which option the record adopts, and what a no-fidelity result does (§5.2's failure branch). |
| a support-matrix record under `docs/acceptance/` | Host, version, open and reopen result, and preserved-or-refused structure classes, per sample run. |
| a dated evidence record under `docs/acceptance/` for the substitute run | What was measured on which machine, and which half is still open. |

It does **not** own `src/labcairn/workspace/outputs.py` or
`src/labcairn/security/paths.py`: the write seam is §7's area in this batch, and
the dependency runs through §5.6 as a sequence, not through an edit. It does not
edit [`../THREAT-MODEL.md`](../THREAT-MODEL.md).

**5.6 Dependencies, named rather than assumed.**

- **On §7, and this one is load-bearing.** `src/labcairn/workspace/outputs.py` is
  the only place in the product that writes a file — its own first line says so —
  and `src/labcairn/workspace/outputs.py:164` names its atomic temporary as
  `.lc-write-<hex>.tmp` (measured live 2026-11-08: a fixed 46-character name).
  Execution plan §6 records a `FileNotFoundError` opening that name exactly when
  the visible path length crossed 260 characters, with the 259/260 switch
  reproduced bare. An editing ADR that assumes a write always succeeds is an ADR
  written on top of a wall, so the owner put the path-length repair **in this
  batch** (§2 item 6) and this ticket sequences against it instead of editing the
  seam.
- **On `LC-P3-03`, bounded.** The independent-copy guarantee the edit loop assumes
  is `LC-P3-03`'s deliverable. For G1 this ticket may run on an explicitly
  temporary independent-copy mechanism, and the ADR must say *temporary*, because
  an experiment's shortcut that is not labelled is how a temporary thing becomes a
  product mechanism.
- **On `LC-P3-01`, one-directional.** Execution plan §3 says `01` and `02` may run
  independently, and neither blocks the other. But §4.9's checklist consumes this
  ticket's outputs, so this ticket's substitute run lands before the checklist is
  performed.
- **On the provider: not at all.** `LC-P3-06` is `BLOCKED` (§2 item 5) and this
  ticket neither waits on it nor unblocks it.

**5.7 Deliverables.**

1. The **editing ADR** (`ADR-0021`, §5.5): the options, what each measurement
   showed, the adopted option, and what a no-fidelity result does.
2. The **support matrix**: host, version, open and reopen result, and the
   preserved-or-refused structure classes for every sample run.
3. **Refusal witnesses**: a structure outside the support matrix fed to the
   write-back path is refused or handed to a person, asserted **before any file is
   touched**.
4. The **substitute-set round-trip measurement**: write, reopen, compare — with the
   original's hash unchanged and the non-target regions compared rather than
   assumed.
5. The named-gap statement for the real-sample half (§5.9).

**5.8 Acceptance evidence.** Done when the editing ADR exists with its
option-space measurements; the support matrix records host, version, open and
reopen result and preserved-or-refused classes for every sample run; the
substitute-set round-trip has been measured on the primary host with the reference
host's no-repair-prompt result recorded through §4.9's checklist — `LC-P3-01`'s
instrument, run against this ticket's outputs; the refusal witnesses go red under
their counter-mutation; and the real-sample loop is either passed or explicitly
held open as a named gap. Mapping onto execution plan §4: this ticket is the
decision basis for the edit half of the **"Original and format"** row (the clean
draft matches the approved edits; non-target equations, images, tables and
relationships survive; changes outside the support matrix are refused or handed to
a person) and for the **real-sample half** of the trial rows. The row itself is
judged at Phase 3 G4.

**5.9 Substitute-first, and the half that is held open.** §2 item 3 fixes the
order.

| Substitute-first — may start with no new material | Real-material-gated — held open as a named gap |
|---|---|
| Synthetic comment-and-revision samples, with the Phase 2 DOCX fixture corpus and the read-side baseline in [`../acceptance/LC-P2-07-fidelity-baseline.md`](../acceptance/LC-P2-07-fidelity-baseline.md) | The advisor sample's full loop: import → locate → propose → confirm → write-back → dual-host reopen |
| Both rewrite strategies measured on those samples, with their cost | The ADR's **adoption** as the product's decision, which must cite the real-sample run and not only the synthetic one |
| Round-trip mechanics on the primary host with synthetic files | Nothing else. Refusal evidence is synthetic by nature: a refusal needs no real material to be a real refusal. |

Until the sample arrives the ticket's own record carries **real-sample loop: NOT
RUN — held open pending the owner's sample**. `LC-P3-00` §3 governs this: rows
defined by real advisor use cannot be simulated and reported as advisor use.

---

## 6. What this file does not do

It dispatches no window and opens no worktree. It authorises no push, pull request
or CI run. It writes no product source, no test, no migration and no workflow
file. It closes no gate and marks no ticket done. It quotes no commit other than
the two printed in the header. Its `NOT STARTED` rows are the truth at this commit,
and the board changes in the same commit as any evidence that moves one.

---

## 7. The repair this batch carries: the write seam's path-length budget

**A batch item, not a ticket.** It has no `LC-P3-` id, no file is changed by this
commit, and it is written here because two of the three G1 areas depend on which
way it goes. §2 item 6 is the owner's decision that this batch takes it.

**The measured fact.** `src/labcairn/workspace/outputs.py` is the only place in the
product that writes a file, and its atomic temporary name is fixed at 46 characters
(line 164, measured live 2026-11-08). Execution plan §6's row for that file records
a `FileNotFoundError` opening it exactly when the visible path length crossed 260
characters, the 259/260 switch reproduced bare, and the observation tied to path
length rather than to a race — with the recheck record that carries those numbers
living outside the tree. Windows is where the wall is; any POSIX ceiling is a
different number and only a POSIX run may state it.

**What the fix has to include.**

- A shorter temporary name, **or** a depth-checked output layout, **or** a length
  budget at the workspace root — with the seam's own budget stated, since a layout
  rule and a name rule solve different halves of the same wall.
- **The existing leftover scan re-checked, not assumed.**
  `tests/test_workspace_boundaries.py:556` finds leftovers by
  `".lc-write-" in p.name`. A shorter name that keeps the prefix leaves that check
  standing as written; **any** change to the prefix means that witness is
  re-measured in the same change, and no direction may weaken it.
- **A witness that writes near the ceiling**, which must go red under the
  counter-mutation that restores the 46-character name (and, for a
  budget-checking direction, removes the budget check) *because its own assertion
  failed* — not under a lint, encoding or line-length accident.
- **The long-path refusal stated as what this tree actually does.** The preparation
  draft's raw-Windows direction did **not** reproduce in its own 2026-11-08 freshness
  review: the prefixed spelling opened successfully where the draft expected a
  refusal. What this tree can rest on is `src/labcairn/security/paths.py`'s
  deliberate refusal of that spelling, and the operator-side recheck has to be
  re-run verbatim before any ADR quotes an errno for this seam.

**Ownership for the batch.** `src/labcairn/workspace/outputs.py`,
`src/labcairn/security/paths.py` and `tests/test_workspace_boundaries.py` belong to
this item while the batch runs. `LC-P3-01` and `LC-P3-02` do not edit them; both
sequence against them.

---

## 8. Open gaps, with what each is waiting on

| Gap | Waiting on | Where it is stated |
|---|---|---|
| The real advisor sample and its full loop | The owner supplying the sample (§2 item 3) | §5.9 |
| `LC-P3-06` — one bounded real-model validation | Provider, model, permitted outbound scope, call and cost ceiling, credential holder, sample class, stop-loss (§2 item 5) | §1, [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §4 |
| A Windows browser pass a runner has run | A runner run, which the owner starts | §3 rule 6, execution plan §6 last row |
| Which side carries the driver, and whether the witness is new or extended | The implementation window's first recorded decision | §4.12 |
| Which system-browser channel the trial machine has | A measurement at dispatch | §4.12 |
| Q77's per-layer rules and Q82's original | Their own triggers: a memory-interface design task, and a later requirements baseline only the owner can state | §1, [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §8 |
| Work orders for `LC-P3-03` … `LC-P3-08` | Not written. This file issues the G1 pair and nothing else. | §1 |
