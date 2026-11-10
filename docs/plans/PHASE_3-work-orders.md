## 1. The board at this writing

Status vocabulary is the project's own — `NOT STARTED` · `IN PROGRESS` · `PASS`
· `PASS WITH NOTES` · `BLOCKED` · `FAIL` — and **no Phase 3 row is `PASS` or
`PASS WITH NOTES`**. A row moves in the same commit as the evidence that moves
it, and never because something looks finished.

| Ticket | Stage | Status | What the row rests on |
|---|---|---|---|
| `LC-P3-00` | Phase 3 G0 | decision record, landed 2026-11-07 | [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) — a dated owner decision record, not a gate verdict. |
| `LC-P3-01` | Phase 3 G1 | **`IN PROGRESS`** — implementation merged 2026-11-08; evidence in [`LC-P3-01-browser-baseline.md`](../acceptance/LC-P3-01-browser-baseline.md); §4.9 human checklist and the LC-P3-02 substitute round-trip remain open | The dated window record and its witnesses; the shard-balance witness is expected red until the batch runner run; no PASS is claimed. |
| `LC-P3-02` | Phase 3 G1 | **`IN PROGRESS`** — implementation merged 2026-11-09; evidence in [`ADR-0021`](../adr/ADR-0021-manuscript-editing-rewrite.md), [`LC-P3-02-support-matrix.md`](../acceptance/LC-P3-02-support-matrix.md) and [`LC-P3-02-substitute-run-2026-11-08.md`](../acceptance/LC-P3-02-substitute-run-2026-11-08.md); the §4.9 human dual-host reopen checklist, the real advisor sample (§5.9) and the runner-measured shard costs (§3 rule 3) remain open | The dated run record and its witnesses, measured locally on the synthetic substitute set; no host result, no real-sample loop and no PASS is claimed, and the shard-balance witness is expected red until the batch runner run. |
| `LC-P3-03` | Phase 3 G2 | **`IN PROGRESS`** — implementation merged 2026-11-10 (merge `4855ea6`); evidence in [`LC-P3-03-revision-loop-2026-11-10.md`](../acceptance/LC-P3-03-revision-loop-2026-11-10.md); 17 witnesses, four refusal classes, all four counter-mutation families caught; the gate itself stays open | The dated run record and its witnesses, measured locally; no PASS is claimed. |
| `LC-P3-04` | Phase 3 G2 | **`IN PROGRESS`** — the binding loop (opinion → locate → suggest → apply → dossier) merged 2026-11-10 (merge `2dce121`); evidence in [`LC-P3-04-binding-loop-2026-11-10.md`](../acceptance/LC-P3-04-binding-loop-2026-11-10.md); 17 Python witnesses + 5 web witnesses, 6 counter-mutations caught, ledger `ADDED -- 17`; the gate itself stays open | Execution plan §3; §9. |
| `LC-P3-05` | Phase 3 G3 | **`IN PROGRESS`** — the selection-and-measurement stage landed 2026-11-10 (merge `1e35758`); evidence in [`LC-P3-05-selection-measurement-2026-11-10.md`](../acceptance/LC-P3-05-selection-measurement-2026-11-10.md) and [`ADR-0023`](../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md); the shell choice itself waits on the O6 fix, which landed 2026-11-10 (merge `9cdb19a`, record [`o6-event-stream-stall-2026-11-10.md`](../acceptance/o6-event-stream-stall-2026-11-10.md)) | The dated selection record; §10. |
| `LC-P3-06` | Phase 3 G3 | **`IN PROGRESS`** — the substitute-first half landed 2026-11-10 (merge `7d5be74`); evidence in [`LC-P3-06-substitute-first-2026-11-10.md`](../acceptance/LC-P3-06-substitute-first-2026-11-10.md); 33 witnesses, 12/12 counter-mutations; the real half still waits on `LC-P3-04` and the sample | `LC-P3-00` §4; the authorisation record at §11's §4.9; the real-model row stays gated by §4.8's right column. |
| `LC-P3-07`, `LC-P3-08` | Phase 3 G4 | **`NOT STARTED`** — work orders §12 and §13 were issued 2026-11-09 (owner decision: the ground-truth revision published on 2026-11-10); both tickets stay blocked on `LC-P3-05`'s installed build | Execution plan §3; §12, §13, and the 2026-11-10 owner decisions at the end of each section. |

Source questions **Q77** and **Q82** stay open at their own triggers
(`LC-P3-00` §8, execution plan §8), unchanged by anything here.

---

## 2. What the owner decided, and where each decision lands in these tickets

| # | The decision of 2026-11-08 | What it settles | Where it binds |
|---|---|---|---|
| 1 | **Browser driver: Playwright**, taking the **system-browser channel** where one exists so the run does not add a browser download. The driver package itself still has to be installed. | The choice the preparation package left to the owner. | §4.4, §4.5, §4.10 |
| 2 | **COM and ProgID automation of a desktop host: not allowed.** The WPS and Office reopen checks are **human-performed checklist steps with recorded evidence**. | Whether the project may drive real desktop applications programmatically. It may not. | §3 rule 2, §4.9, §5.8 |
| 3 | **The real advisor sample comes after** the synthetic and substitute-first work, and until it is supplied it stays a **named gap**. | The timing `LC-P3-02` was waiting on. | §5.9, §8 |
| 4 | **The §4 checklist split, re-decided:** `LC-P3-01` carries the real-browser baseline **and** the dual-host reopen checks; `LC-P3-02` carries the DOCX revision loop **and** the real-sample half. | Which ticket is the basis for which row after the re-split, and who runs the checklist. | §4.11, §5.8 |
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
   runner log by `python .github/remeasure_shards.py <run-id>`. **A
   repository-class file is the exception:** it declares no `pytestmark` and is
   filed under `REPOSITORY_CLASS` with the `repository-gate` clause; the
   harness requires a marker-less file in that class. The LC-P3-02 substitute
   corpus and record witnesses are the current examples. A local timing is
   not a runner cost, and a file in no shard is a test a runner never runs
   (execution plan §6, last row). Extending an existing file skips the
   registration, not the shard-cost witness. The registration files themselves
   are **commander-owned at merge**: a window reports the entries it needs and
   does not edit `.github/ci-shards.json` or `tests/evaluation/manifest.py`
   directly. Until the batch's own runner run, the shard-balance witness is
   expected red on `windows-latest`; that run's `--durations=0` log is the only
   source for the cost re-measurement, and no local timing is substituted.
   A browser witness that cannot find Playwright or a system browser on a
   runner **skips with a named reason** (`playwright` or system browser
   absent) and records the skip; a missing local browser must not turn the
   shard jobs red. The LC-P3-01 window supplies the browser evidence locally.
3a. **Platform-conditional code keeps one reachable body on both checker
   platforms** ([ADR-0022](../adr/ADR-0022-platform-conditional-code-keeps-one-reachable-body.md)):
   the platform question is routed through a helper call so no checker
   constant-folds it away, Windows-only attribute reads carry scoped
   `type: ignore[attr-defined,unused-ignore]` at the use site, and runtime
   semantics are preserved exactly — a non-Windows spawn flag stays `0`, it
   does not raise. A guard that reddens one platform's checker is a defect
   this rule names, not a re-run.
4. **File ownership is the contract.** The areas in §4.5 and §5.5 are the map. A
   window that needs a file outside its area says so instead of reaching for it.
   `01` and `02` may run in parallel precisely because their areas do not
   overlap; §16's write seam is a third area, not a shared one. A new product
   dependency is an owner decision: a window that needs one reports the
   package, version, licence and lockfile change, and does not edit
   `pyproject.toml`, `uv.lock`, `web/package.json` or `web/pnpm-lock.yaml`
   itself.
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
record. The two registration files (`.github/ci-shards.json`,
`tests/evaluation/manifest.py`) are commander-owned at merge; this window
reports its entries (§3 rule 3).

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

- *Task selection, and the version-switching gap.* The page drives
  `POST /task/select`; the rendered state panel shows `GET /task` bytes identical
  to `task status --json` for the same task — the field-for-field comparison the
  live-service witness established, now through a socket and a render. The
  workbench has no version-control surface; version switching is recorded as a
  named gap in §8, not claimed as exercised.
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
which is a Phase 1 record. For this batch the named performer is **the project
owner** (owner decision of 2026-11-08); every row records that name and the
date it was performed.

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
target, and what was refused. Any Windows-adaptation dependency is an owner
decision under §3 rule 4; the window reports it rather than editing
`pyproject.toml` or `uv.lock`.

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
edit [`../THREAT-MODEL.md`](../THREAT-MODEL.md). The two registration files
(`.github/ci-shards.json`, `tests/evaluation/manifest.py`) are commander-owned
at merge; this window reports its entries (§3 rule 3).

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
   showed, the provisional option adopted for the substitute set, and what a
   no-fidelity result does.
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

**The corpus is identified; the sample is picked.** On 2026-11-09 the
owner confirmed the uploaded micro-nano-bubble reference batches as this
direction's corpus and named batch A (the two MSc papers whose
advisor-annotated versions carry the advisor's comments and tracked
revisions) as the initial advisor-material batch. All four batches were
fingerprinted the same day into an operator-side registry **outside the
repository** (111 `.docx` files: sha256, byte size, comment/revision/media
counts; structure-only, no prose extracted, no file enters the tree — the
no-material policy and its CJK ceiling hold). Later the same day the owner
picked the real sample from batch A's fingerprint ranking: the file behind
sha256 `9154e56c5fe47da151fdb636b3cc4f8170965a8ccdbca94f292390254607652d`
(4 443 105 bytes; 4 comments, 270 insertions, 119 deletions, 10 media
parts), the green-algae inhibition paper's advisor-annotated version. The
project's own structure survey, run on the picked file the same day,
carries `BODY_TEXT`, `TRACKED_REVISIONS`, `COMMENTS`, `TABLES`,
`EQUATIONS`, `IMAGES`, `COMMENT_PART` and `MEDIA`, and blocks nothing — a
wider structural coverage than most synthetic samples. The file itself
stays outside the repository; the tree records its digest and counts,
never its name or its content. The named-gap label above stands unchanged:
the real-sample half is `NOT RUN` until the full loop runs on this file
and is recorded.

**5.10 The empty row, and who watches it.** A record may leave a cell empty
because the evidence for it has not been taken. That is honest only while a
witness watches the row: a test that fails if the row disappears, if the empty
cell is read as a result, or if the label changes from "not run" to a verdict.
An empty row with no witness is not a pending measurement; it is a claim the
tree cannot tell from a pass. The reopen checklist's human cells are empty and
`tests/test_docx_edit_records.py` watches them; the real-sample row carries the
exact label §5.9 names, and the same witness reads that label.

---

## 8–14. The Phase 3 work orders after G1: `LC-P3-03` … `LC-P3-08`

Issued 2026-11-09 on the owner's ratification of the drafting round
(`P302-NEXT-WORK-ORDERS-DRAFT-2026-11-09.md`, drafted by an independent agent
session against main `571e4346…`). The drafts' scope is the execution plan's
own; §14's owner decisions were answered by the owner on 2026-11-09 (items
1–7; each answer is recorded in place under its item), and a ticket whose
decision is unanswered stays `NOT STARTED`/`BLOCKED` exactly as §1 states.
Board rows move when a window is dispatched, not by this issuance.

## 8. `LC-P3-03` — project authorisation and versioned writes (Phase 3 G2)

**1.1 Purpose.** Execution plan §3: *"Import, read-only original, independent
copy, content hash, publication receipt and recovery path. Real file
operations prove that cross-project access, path escape, stale approval and
duplicate requests are refused."* Execution plan §6's gap-register row for
this ticket names the measured state and the gap to close: task/stage/operation,
recovery, allowed roots, path canonicalisation, untrusted-text boundaries and a
source-root read-only guard exist — *"No project-scoped import receipt that
binds the read-only guard, independent-copy transaction and publication
receipt into one revision loop. `LC-P3-03` must add and witness that
integration."*

**1.2 What kind of ticket this is.** An integration ticket with refusal
evidence: the pieces exist (gap register's own wording); what does not exist
is one revision loop that binds them, proven by real file operations — not
mocked filesystems — to refuse the four named refusal classes.

**1.3 Scope boundaries — what it is NOT.**

- Not the proposal-to-approved-edit-to-response-table binding and not the
  quality report (`LC-P3-04`).
- Not any desktop shell, installer or lifecycle work (`LC-P3-05`).
- Not the provider, and no outbound call of any kind (`LC-P3-06`; §3 rule 1).
- Not a re-litigation of the write seam's path-length repair: the MAX_PATH
  fix landed in the G1 batch (merge `2c782ed`, with
  `tests/test_workspace_path_length.py`), and this ticket *consumes* a
  repaired seam. If a deep-path refusal surfaces during 03's own runs, it is
  reported, not re-fixed here.
- Not the fidelity experiment's support matrix (`LC-P3-02`'s record stands).
- No real model, no real advisor material (there is none in this ticket's
  scope to begin with).

**1.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the integration's own modules under `src/labcairn/application/` and their tests | The import receipt, the transaction binding, the publication receipt, the recovery path. Module names are the window's to record, not pre-decided here. |
| wiring across `src/labcairn/security/paths.py`, `src/labcairn/security/untrusted.py`, `src/labcairn/workspace/readonly.py` (named by the gap register as the pieces being bound) | The read-only-original guarantee joins the loop. Changes here are integration seams, not redesigns; a redesign is reported to the owner. |
| a record under `docs/acceptance/` for the integration's substitute run | What was run, on which machine, what was refused, what is still open. |

It does not own `src/labcairn/papers/` (04's), `src/labcairn/providers/`
(06's), `web/` beyond whatever import surface the G2 dispatch split assigns
at the owner's word (§14 item 1 — answered 2026-11-09: no split, 03 and 04
run sequentially), or the registration files (§0 rule 3).

**1.5 Dependencies — named, one-directional.**

- **On `LC-P3-00`, satisfied as a record** (numbering, gate split, reviewer
  form) — same wording as G1 §4.6.
- **On the G1 batch as landed.** The independent-copy guarantee the edit loop
  assumes is this ticket's deliverable (G1 §5.6 says so in as many words);
  ADR-0021 carries G1's independent-copy mechanism marked **temporary** for
  exactly this hand-off. **Named open item:** at 03's landing, the temporary
  mechanism is either replaced by the product mechanism or absorbed into it,
  and 03's record states which happened. Whether that disposition may also
  touch ADR-0021's text, or waits for that ADR's final adoption (which §5.9
  binds to the real-sample run), is **a proposal for the owner** (§14 item 6).
  **Answered 2026-11-09 (§14 item 6): the disposition does not touch
  ADR-0021's text** — 03's own record states what happened to the temporary
  mechanism; the ADR's wording is settled at its final adoption.
- **Not on `LC-P3-04`** — the arrow runs the other way: 04's approved
  application is a write, and writes require the transaction and receipt this
  ticket delivers. Execution plan §3's sequence (`03 → 04`) is the order
  these drafts keep.
- **Not on the provider, not on the advisor sample.** Nothing here is real
  material or outbound.

**1.6 Deliverables.**

1. The project-scoped **import receipt** that binds the read-only guard, the
   independent-copy transaction and the publication receipt into one revision
   loop.
2. **Content-hash evidence** that the original is unchanged through the loop.
3. **Refusal witnesses, from real file operations**, for the four refusal
   classes the scope sentence names: cross-project access, path escape, stale
   approval, duplicate request — each asserted before any file is touched,
   each with its counter-mutation (§0 rule 5).
4. A **recovery path** with a witnessed drill: an interrupted operation
   resolves to a recovered result or a safe retry, and receipts are not
   duplicated.
5. A **measured-gap list** (G1 §4.7 item 2's rule: *measured gaps are named,
   not assumed away*).
6. The disposition of ADR-0021's temporary independent-copy mechanism (§1.5).

**1.7 Acceptance evidence.** Done when every refusal class has a passing
witness against real file operations, the content hash of the original is
asserted unchanged by a witness that fails when a write to the original
succeeds, the recovery drill is recorded with its evidence addresses, the gap
list exists, and the record names the platform and whether each number came
from this machine or a runner. Mapping onto execution plan §4: this ticket is
the evidence basis for the **"Permission and privacy"** row's
local-file half (cross-project references, path escape, writes to the
original, forged or expired approvals have refusal evidence) and for the
**"Cancel, retry and recovery"** row's transaction half. The rows themselves
are judged at Phase 3 G4 on the installed build.

**1.8 Substitute-first / real-material split.** Not applicable — the ticket is
all-synthetic by nature. It can start with no new material (§0 table).

---

## 9. `LC-P3-04` — comment-to-revision loop (Phase 3 G2)

**2.1 Purpose.** Execution plan §3: *"The existing workbench and runtime carry
import, proposal, per-item review, approved application and the four
deliverables. A substitute model supplies reproducible input and output;
opinions needing an experiment or missing evidence stay unresolved as explicit
tasks."* Execution plan §6's gap-register row: replies, feedback chain, version
graph and on-demand role execution exist — *"No point-by-point
proposal-to-approved-edit-to-response-table binding, no quality report
separating file delivery from research quality, and no explicit
unresolved-evidence state for the new loop. `LC-P3-04` must wire these."*

**2.2 What kind of ticket this is.** The offline revision loop reproduced
end-to-end with a substitute model: this is what execution plan §3's stage
outcome names for G2 — *"G2 reproduces the offline revision loop."*

**2.3 Scope boundaries — what it is NOT.**

- Not a fidelity experiment and not a support-matrix re-decision: ADR-0021 and
  `LC-P3-02-support-matrix.md` are this ticket's *inputs*. Structures outside
  the support matrix are refused or handed to a person, using the refusal
  semantics LC-P3-02 delivered; 04 does not widen the matrix.
- Not the real model. The substitute model sits behind the existing provider
  gate, zero outbound, no spend, no credential (§0 rule 1; LC-P3-00 §4 keeps
  CI on substitutes).
- Not the desktop shell (`LC-P3-05`), not the installer, not trial logistics.
- Not the resolution of unresolved opinions: an opinion that needs an
  experiment or missing evidence **stays unresolved as an explicit task** —
  that is the deliverable's own vocabulary, not a failure state.
- Not a claim that ADR-0021 is adopted. The record stays `proposed` with
  adoption provisional until the real-sample run it must cite exists (G1
  §5.9). Whether building 04 on the *provisional* adoption is acceptable is
  **a proposal for the owner** (§14 item 5).

**2.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the loop's own modules over `src/labcairn/papers/replies.py`, `chain.py`, `versions.py` and `src/labcairn/roles/` (named by the gap register as the pieces being wired) and their tests | The point-by-point binding: proposal → approved edit → response table. |
| consumption of `src/labcairn/editing/` (LC-P3-02's seam) | Approved application goes through the edit seam the support matrix governs. 04 consumes the seam; it does not redesign it. |
| the response-table and quality-report render surfaces under `src/labcairn/reports/` | Two of the four deliverables. The existing report-only writer's library boundary (ADR-0013) governs. |
| the workbench wiring in `web/` for per-item review | The review surface the trial participant uses. |

It does not own `src/labcairn/application/`'s receipt/transaction modules
(03's) — it *wires onto* what 03 delivered, per the dispatch split the owner
names (§14 item 1). It does not own `src/labcairn/providers/`, the installer,
or the registration files.

**2.5 Dependencies — named, one-directional.**

- **On `LC-P3-03`.** Approved application is a write; the write rides 03's
  transaction and publication receipt. This is execution plan §3's own order
  (`03 → 04`), kept as written.
- **On ADR-0021 and the support matrix, as inputs.** The edit seam and its
  refusal semantics exist; 04 builds on the *provisional* adoption pending
  the owner's answer (§14 item 5).
  **Answered 2026-11-09 (§14 item 5): provisional is sufficient** — 04 builds
  on the provisional adoption; the ADR's record stays `proposed`, and final
  adoption still cites the real-sample run when it exists.
- **On `LC-P3-01`'s browser baseline, as an input.** The workbench surfaces
  04 wires have their real-browser evidence; 04 extends them, it does not
  re-measure them.
- **Not on `LC-P3-05`** — the arrow runs the other way: 05's build must carry
  a complete loop, so 04 lands before 05's installation drills.
- **Not on `LC-P3-06` and not on the provider.** The substitute model behind
  the gate is the whole point of a G2 that *reproduces the offline loop*.

**2.6 Deliverables.**

1. The **point-by-point binding**: every supported input opinion is either
   located or explicitly marked as a location failure; accepted, partly
   accepted, rejected and pending statuses exist; automatic edits link to the
   opinion, the evidence, the operator and the version; model suggestions and
   advisor confirmations are separate records. (This is the offline
   counterpart of execution plan §4's "Point-by-point response" row.)
2. The **four deliverables** — marked draft, clean draft, point-by-point
   response table, quality report — each bound to one task, one input version
   and one output version.
3. The **quality report** that separates file-delivery status from
   research-quality status.
4. The **explicit unresolved-evidence state**, with the sample's own three
   cases exercised: directly editable, needing further evidence, uncertain
   location (execution plan §4's "Research quality" row, offline).
5. **Refusal witnesses** for structures outside the support matrix, reused
   from LC-P3-02's semantics and re-witnessed at the loop's boundary (a guard
   inherited without its own witness at the new call site is a guard nobody
   watches).
6. A **measured-gap list**, and a record naming the substitute model's
   reproducibility properties (what "reproducible input and output" meant in
   this run).

**2.7 Acceptance evidence.** Done when the substitute loop runs import →
locate → propose → per-item review → approved application → four deliverables
with every claim witness-backed and counter-mutation-checked; the four
deliverables bind to one task, one input version and one output version as
asserted by a witness; unresolved opinions surface as explicit tasks and are
not silently dropped; and the record names machine-vs-runner per number.
Mapping onto execution plan §4: this ticket is the evidence basis for the
**"Import to delivery"** and **"Point-by-point response"** rows' offline
halves and the **"Research quality"** row's state machinery. The rows are
judged at Phase 3 G4.

**2.8 Substitute-first / real-material split.**

| Substitute-first — may start with no new material | Real-material-gated — held open as a named gap |
|---|---|
| The whole loop on synthetic comment-bearing samples, with a substitute model behind the provider gate | Nothing. The loop's *offline reproduction* is the ticket; the real advisor loop is `LC-P3-08`'s deliverable and `LC-P3-02` §5.9's held-open half, not 04's. |
| The four deliverables, the binding, the unresolved-evidence state | — |
| Refusal evidence (a refusal needs no real material to be a real refusal) | — |

---

## 10. `LC-P3-05` — desktop shell and installer (Phase 3 G3)

**3.1 Purpose.** Execution plan §3: *"Reuses the workbench, tightens preload
and IPC, navigation, file opening, runtime lifecycle and local API session
boundaries. A clean Windows environment proves install, launch, upgrade drill,
uninstall and rollback; support limits and signing status are recorded."*
Execution plan §6's gap-register row: a React/TypeScript workbench, wheel/sdist
release checks and web quality gates exist — *"No Electron/Tauri/PyInstaller
configuration, desktop process lifecycle, installer, signing or
upgrade/rollback drill. `LC-P3-05` is a selection and measurement stage before
implementation."*

**3.2 What kind of ticket this is.** Two stages in one ticket, in order: a
**selection and measurement stage** (the three shell candidates measured
against the workbench `LC-P3-01` baselined — the gap register's first row says
the browser baseline exists so a shell *can* be chosen), then implementation
of the chosen shell. The selection record is a deliverable whether or not
implementation proceeds; if the owner defers the shell choice, the selection
stage is still a complete result.

**3.3 Scope boundaries — what it is NOT.**

- **Not signing, not public distribution.** `LC-P3-00` §6: signing and public
  distribution remain deferred behind `W28` and are owner decisions at their
  own triggers. 05 *records* signing status; it does not produce a signature.
- Not the provider or any outbound call (`LC-P3-06`; §0 rule 1).
- Not a re-measurement of LC-P3-01's browser baseline — it is the input.
- **Not an automation channel into a DOCX host.** §0 rule 2 applies with
  special force: whatever shell is chosen must not become a COM/ProgID/UI-
  automation path to WPS or Word. If a candidate shell's only viable DOCX
  integration is automation, that is a recorded finding against the
  candidate, not an exception to the rule.
- Not a fidelity or support-matrix decision (ADR-0021's).

**3.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the shell configuration and lifecycle modules the chosen framework requires, under a layout the window records | Process lifecycle, runtime lifecycle, local API session boundaries. |
| `web/` preload and IPC tightening | The reuse half of the scope sentence. 04's review UI may share `web/` — see §0 table; the owner's dispatch split names who owns what. |
| the installer configuration | Install, upgrade drill, uninstall, rollback. |
| a selection-and-measurement record and an ADR at the next free number (**ADR-0023** as of this writing — ADR-0022 was taken on 2026-11-09 by the platform-conditional-code rule, §3 rule 3a; the window re-checks the directory before issuing) | The three candidates, what each measurement showed, which option the record adopts, what a candidate's refusal means. |
| a dated record under `docs/acceptance/` for the clean-Windows drill | Install, launch, upgrade, uninstall, rollback, support limits, signing status. |

It does not own `src/labcairn/application/`, `src/labcairn/papers/`,
`src/labcairn/editing/`, or the registration files.

**3.5 Dependencies — named, one-directional.**

- **On `LC-P3-01`, as an input, satisfied.** The browser baseline exists
  (execution plan §6's first row: measured *before a shell is chosen* — that
  precondition is met at the anchor commit).
- **On `LC-P3-04`.** The installed build must carry the complete loop; 05's
  drills are meaningless against a build whose loop is absent.
- **On the owner's shell choice and dependency approvals.** A new desktop
  dependency (an Electron, Tauri or PyInstaller line) is an owner decision
  under §0 rule 4: the window reports package, version, licence and lockfile
  change and edits no manifest.
- **Not on `LC-P3-06`.** The bounded validation exercises the proposal path
  on whatever build exists; 05 neither waits on it nor unblocks it.
- **Not on the advisor sample.** The clean-Windows drill uses the project's
  own synthetic material; the trial sample is `LC-P3-08`'s.

**3.6 Deliverables.**

1. The **selection-and-measurement record** and the selection ADR (the next free number, §3.4): candidates,
   measurements, the adopted option, the failure branch.
2. The **shell implementation** with tightened preload and IPC, navigation,
   file opening, runtime lifecycle and local API session boundaries, each
   boundary claim witness-backed (§0 rule 5).
3. The **installer** and the **clean-Windows drill record**: install, launch,
   upgrade drill, uninstall and rollback, with the evidence naming the commit,
   package hash, OS and host versions — the concrete matter execution plan
   §4's "Distribution and review" row demands of the gate.
4. **Support limits and signing status recorded** (signing: deferred, `W28`).
5. A **measured-gap list**.

**3.7 Acceptance evidence.** Done when the selection record exists, every
lifecycle and session-boundary assertion has a passing witness, the clean
Windows environment drill is recorded end to end (install → launch → upgrade →
uninstall → rollback preserving user data), and the record names machine-vs-
runner per number. Mapping onto execution plan §4: this ticket is the evidence
basis for the **"Distribution and review"** row's install-and-run half and the
**"Permission and privacy"** row's session-boundary half. The rows are judged
at Phase 3 G4.

**3.8 Substitute-first / real-material split.**

| Substitute-first — may start with no new material | Real-material-gated — held open as a named gap |
|---|---|
| The selection and measurement stage (all three candidates, against the existing workbench and its baseline) | Nothing — the trial participant's real machine experience is `LC-P3-08`'s, not this ticket's. The clean-Windows drill environment is a clean *environment*, not sample material. |
| Implementation of the chosen shell once the owner names it | — |
| The clean-Windows drill on synthetic project material | — |

**3.9 Open items inside this ticket.** Which side of `web/` the shell window
owns versus 04's review UI is a dispatch-time file-ownership decision (§7
item 2). Whether the shell runs the local API in-process or as a child
process is the window's first recorded decision — the scope sentence says
"local API session boundaries" without fixing the topology, and the
measurement stage is where that is decided.

---

## 11. `LC-P3-06` — one-model bounded validation (Phase 3 G3) — `BLOCKED` (seven fields answered 2026-11-09; the real half now waits on `LC-P3-04`, and the substitute-first half may start)

**4.1 Purpose.** Execution plan §3: *"One real model exercises the proposal
path within an owner-authorised scope. Records model, sample fingerprint,
outbound scope, budget, usage, refusal and repeatable acceptance evidence.
Credentials and raw samples remain in the authorised environment."*

**4.2 Blocker, restated with its current shape.** The board row's `BLOCKED`
rests on `LC-P3-00` §4 and the owner's decision of 2026-11-08 (§2 item 5 of
the G1 work orders): the seven provider fields are unnamed and the decision
was deferred until after G1. **G1 has now closed its batch** (PR #153, merge
`571e4346…`), so the deferral has run its course: the seven fields are due an
owner answer, and the decision-support package for exactly that answer exists
outside the repository — `PROVIDER-SEVEN-FIELDS-QUESTIONS-2026-11-08.md`
(seven self-contained questions, Q1–Q7) resting on
`PROVIDER-SEVEN-FIELDS-PREP-2026-11-08.md`, both under the operator's
plan-review directory on the trial machine. Those files decide nothing; this
draft does not summarise them into new claims — the owner reads them and
answers them.

**4.3 Scope boundaries — what it is NOT.**

- Not a Phase 2 rewrite. `real_model_smoke = NOT RUN` and the 35 unaccepted
  model-proposal edges keep their Phase 2 records verbatim (LC-P3-00 §4; G1
  §3 rule 1 cites them from their own records, not restated as current
  facts).
- Not a CI change. CI stays on substitute models (`LC-P3-00` §4); the real
  call is an operator-side, owner-authorised act, never a shard job.
- Not the trial (`LC-P3-08`). One controlled de-identified case is this
  ticket's scope; the advisor-to-student-to-advisor loop is 08's.
- No credential, no raw sample, no material sentence enters the tree
  (ADR-0018 C14 / D2: the route is a configuration, not code; the no-material
  policy and its CJK ceiling hold).

**4.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the real-route exercise surface over `src/labcairn/providers/` | The proposal path exercised for real, within the authorised scope the seven fields define. The adapter code exists; what 06 adds is the bounded exercise and its evidence machinery, not a new supplier route. |
| the de-identification and safe-fields surface for the controlled case | The model receives only approved, de-identified content; logs and receipts use safe fields (execution plan §4's "Permission and privacy" row, real-model half). |
| a dated record under `docs/acceptance/` for the bounded run | Model, sample fingerprint, outbound scope, budget, usage, refusal, repeatable acceptance evidence. |

It does not own `providers.json` (the operator's own configuration, never in
the tree), the credential store, or any other ticket's modules.

**4.5 Dependencies — named, one-directional.**

- **On the seven fields — the blocker.** Nothing real happens before the
  owner answers Q1–Q7. Fields 1–2 (provider, model) are one configuration;
  fields 3–7 (outbound scope, ceiling, credential holder, sample class,
  stop-loss) are the authorisation that configuration runs under (the
  questions package's own framing, quoted for structure only).
  **Answered 2026-11-09 (§14 item 3; the answers are tabled at §4.9).** The
  seven fields are named; what remains on this arrow is the substitute-first
  half starting (§4.8's left column) and the real call waiting for its
  sample-class preconditions, not for an answer.
- **On `LC-P3-04`.** What the real model exercises is the proposal path 04
  wires; a validation of a path that does not exist validates nothing.
- **On the authorised machine.** The questions package records that no
  record names the machine for credentials yet (`LC-P3-00` §5 names the trial
  machine for the §4 acceptance rows; the credential machine is Q5's unknown).
  **Answered 2026-11-09 (§4.9, Q5 row): the trial machine**, credentials held
  by the owner via `credential_file`, the file outside the repository.
- **On the de-identified, owner-authorised domain sample** — the second of
  the execution plan's three sample classes. Its supply is owner material.
  **Answered 2026-11-09 (§4.9, Q6 row): synthetic samples first**; the real
  advisor sample stays a named gap and is not promised.

**4.6 Deliverables.**

1. The **bounded real-model run record**: model, sample fingerprint, outbound
   scope, budget and usage as measured, refusals encountered, and repeatable
   acceptance evidence.
2. The **de-identification pipeline** and its witnesses, proven on synthetic
   material before the real case touches it.
3. The **degraded-path evidence**: budget or permission failures cause no
   outbound call; timeout and unavailability have explicit degraded paths
   (execution plan §4's "One real model" row's own wording).
4. A **measured-gap list**.

**4.7 Acceptance evidence.** Execution plan §4's "One real model" row is the
passing condition, quoted for the record: *"The installed build runs one
controlled de-identified case; the model returns at least one locatable,
reviewable revision suggestion, and a person reviews it before delivery.
Budget or permission failures cause no outbound call; timeout and
unavailability have explicit degraded paths. This result belongs to Phase 3
and does not rewrite Phase 2's `real_model_smoke = NOT RUN`."* Note the row's
own precondition — *the installed build* — which makes `LC-P3-05`'s output the
run's vehicle; whether 06 waits for 05 or runs earlier on the dev build is
**a proposal for the owner** (§14 item 3's second half).
**Answered 2026-11-09 (§14 item 3): 06 runs on the dev build**, before
`LC-P3-05`'s installed build exists; the record says so, and the migration
to the installed build is 05's acceptance business, not 06's rerun.

**4.8 Substitute-first / real-material split** — this ticket is the one whose
split is structural:

| Substitute-first — may start before the seven fields are named | Real-material-gated — starts only when the owner answers |
|---|---|
| The de-identification pipeline and its witnesses, on synthetic material | The real call itself, in any form |
| Rehearsal of the refusal ladder end to end with a substitute behind the gate: budget preflight fail-closed, probe-record gate, consent bridge, capability refusal — proving no unauthorised request can reach a wire | The capability probe, if a supplier other than the already-probed one is chosen (Q1 makes the probe a spend decision of its own) |
| The sample-class definition and the fingerprint record format | The de-identified domain sample's supply and use |
| The degraded-path witnesses (budget refusal, permission refusal, timeout) with the substitute | Usage and budget accounting against a real bill |

**4.9 Open items inside this ticket.** The seven answers themselves (Q1–Q7);
the authorised machine; whether the GitHub secret for the scheduled smoke is
wanted this phase (Q5's deferrable part — the questions package notes it can
be deferred indefinitely without blocking). All owner.

**Answered 2026-11-09 (§14 item 3) — the seven fields are now the ticket's
authorisation record**, and §11's heading drops its `BLOCKED` for the
substitute-first half (the real call stays gated on §4.8's right column):

| Field | The owner's answer (2026-11-09) |
|---|---|
| Q1+Q2 — supplier endpoint and model | The owner's own MiniMax endpoint, `anthropic` protocol, model `MiniMax-M3.1-Flash` — the route whose capability record (2026-10-28) is the only measured one; no new probe spend. |
| Q3 — outbound scope | Per-excerpt digest binding (the pilot's 2026-10-31 shape): each excerpt leaves only under its own digest-bound approval; `ExchangeRecord` carries digests and counts, never text. Real manuscript material stays off the outbound ladder. |
| Q4 — budget ceiling | 20 requests / 50 000 tokens per bounded run; the preflight refuses without the number, and stops at it. |
| Q5 — credential holder | The owner, on the trial machine, via `credential_file` — the file lives outside the repository (`E:\labcairn-local\secrets\` is the standing location); `providers.json` names the path, never the secret. Sub-decision: the scheduled `provider-smoke` GitHub secret stays **uncreated** this phase; the channel stays fail-closed. |
| Q6 — sample class | Synthetic samples first (the G1 sequencing decision stands); the real advisor sample is not promised and stays a named gap until supplied. |
| Q7 — stop-loss | Compound trigger watched by the operator per case: three consecutive failed requests, or a per-case proposal refusal rate above 50%, stops the run (the LC-P2-18 runbook's operator-side pattern). |

---

## 12. `LC-P3-07` — reliability and trial handover (Phase 3 G4)

**5.1 Purpose.** Execution plan §3: *"Fault drills on the installed build:
interrupted writes, locked files, network loss, model timeout and known
errors. Delivers local de-identified diagnostics, backup and rollback, known
limits and an operator manual."*

**5.2 What kind of ticket this is.** A drill ticket: it proves behaviour that
already exists under fault injection, on the build that will be handed to the
trial. It adds no refusal semantics and repairs nothing — a drill that exposes
a defect files the defect; the fix goes to its owning ticket or batch.

**5.3 Scope boundaries — what it is NOT.**

- Not new refusal or recovery *semantics* — those are `LC-P3-03`'s
  deliverable; 07 drills them under fault injection on the installed build.
- Not the trial itself and not trial logistics (`LC-P3-08`).
- Not the provider, not a real-model timeout drill unless the owner adds one
  after `LC-P3-06` unlocks (§5.8): the drill matrix's model-timeout row runs
  against the substitute first, and a real-model row is an owner addition,
  not scope smuggled in.
- Not signing, not distribution (`W28`, `LC-P3-00` §6).

**5.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the fault-injection harness and drills' own test modules | Interrupted writes, locked files, network loss, model timeout, known errors — each injected, each observed, each recorded. |
| the diagnostics packaging surface and its de-identification witness | Local, de-identified diagnostics: what is collected, what is proven absent. |
| the operator manual and known-limits record | The handover half of the ticket's name. |
| a dated record under `docs/acceptance/` for the drill run | Which fault, what behaviour, what evidence address. |

It does not own the installer (`LC-P3-05`'s deliverable — 07 drills *on* it),
`src/labcairn/application/`'s semantics, or the registration files.

**5.5 Dependencies — named, one-directional.**

- **On `LC-P3-05`.** "On the installed build" is a literal obligation; until
  the installer produces a build, the ticket has no execution surface. Drill
  matrix design and manual skeleton may be drafted earlier, but **a draft is
  not a deliverable until run** — this draft says so to keep a design document
  from being mistaken for a drill record.
- **On `LC-P3-03`.** Interrupted writes and recovery are drilled against the
  transaction and recovery semantics 03 delivered.
- **On `LC-P3-06`, bounded.** The model-timeout drill runs against the
  substitute; a real-model timeout row exists only if the owner adds it after
  06 unlocks.
- **Not on the advisor sample.** Fault injection needs no real material.

**5.6 Deliverables.**

1. The **drill matrix record**: each fault class, its injection method, the
   observed behaviour, the evidence address.
2. The **de-identified diagnostics** with a witness asserting what is
   collected and what is proven absent from the package.
3. The **backup and rollback drill**, matching execution plan §4's demand
   that a rollback preserve user data.
4. The **known-limits record** and the **operator manual**.
5. A **measured-gap list**.

**5.7 Acceptance evidence.** Execution plan §4's "Cancel, retry and recovery"
row is the passing condition's shape, quoted: *"Two side-effectful
interruption points around publication are exercised. Cancellation, duplicate
submission and restart resolve to a safe retry, a recovered result or a manual
check. The original is intact and output receipts are not duplicated."* 07
delivers the drill evidence for that row and the fault half of "Distribution
and review". The rows are judged at Phase 3 G4.

**5.8 Substitute-first / real-material split.**

| Substitute-first — the whole ticket until the owner adds a real row | Real-material-gated — owner addition only |
|---|---|
| Every fault class, injected locally on synthetic material | A real-model timeout drill, only if the owner adds it after `LC-P3-06` unlocks |
| The diagnostics de-identification, proven on synthetic content | — |
| The manual and known limits, written against the installed build's actual behaviour | — |

**Owner decisions answered 2026-11-10 (ground-truth revision).** This
section and §13 were issued on 2026-11-09; the board's row was stale, not
the orders themselves. The owner's answers below revise §12 and §13 against
what G2/G3 actually landed, and the draft that surfaced them stays outside
the repository until this publication. **Decision 1** (accepted option A):
publish this as a revision of the issued §§12–13, keep the 2026-11-09 owner
answers untouched, and move the board row in the same commit to name the
issued orders and their date while the tickets themselves stay
`NOT STARTED`. **Decision 8** (accepted option A): publish locally and join
the next owner-authorised batch — no push, no pull request and no CI run
belong to this publication.

- **Decision 2 — the sequencing against `LC-P3-05`.** Accepted option A:
  07 and 08 stay `BLOCKED` on 05's shell decision and installed build. The
  shell is now chosen (Electron, 2026-11-10; ADR-0023 accepted and its
  implementation plan written), but the installed build does not exist yet.
  Only substitute-first design work — the drill matrix, the manual
  skeleton, the trial protocol, the per-row mapping, the seam statement
  and its witness — may start now, and each such piece is
  **labelled design, not a deliverable until run**. A dev-build rehearsal
  is not authorised, and a rehearsal may never be entered in an execution
  plan §4 row. The wheel-only vehicle was not chosen.
- **Decision 5 — the `LC-P3-06` real-model row at G4.** No new decision:
  §14 item 7 stands verbatim. The real-model row remains a named gap at the
  exit decision and does not pass on a substitute; 06's real half has since
  been run under its own authorisation
  ([`LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md)),
  which changes what the gap names, not the owner's ruling.

---

## 13. `LC-P3-08` — internal-trial review and exit decision (Phase 3 G4)

**6.1 Purpose.** Execution plan §3: *"One advisor-to-student-to-advisor loop
on the candidate installer, with actual samples, versions, gate rows and a
named reviewer. The owner decides from the evidence whether Phase 3 is
closed."* This is the exit gate itself, executed: execution plan §2's trial
made concrete.

**6.2 What kind of ticket this is.** A trial-and-decision ticket, not an
implementation ticket. It writes records, not product code; product defects
found in the trial go back to their owning tickets. And it is the one ticket
**no substitute may stand in for**: `LC-P3-00` §3's reviewer form says the
internal-trial rows defined by real advisor use cannot be simulated by any
substitute — the disclosure sentence covers a reading, never an advisor.

**6.3 Scope boundaries — what it is NOT.**

- Not simulated advisor use. The trial's rows are defined by a real advisor
  supplying real material, a real participant running the loop, and the
  advisor reopening the outputs — the execution plan §2 description, verbatim
  in substance.
- Not a self-declared exit. **The owner decides from the evidence** whether
  Phase 3 is closed; the record presents evidence, the owner signs the
  decision.
- Not new scope for any other ticket. If the trial surfaces a gap, the gap is
  named with its evidence address and routed to the owner.
- Not a Phase 2 record edit. Phase 2's verdicts keep their own wording
  (execution plan §5's standing rule).

**6.4 Areas the window would own.**

| Area | What it is for |
|---|---|
| the trial protocol and per-row mapping under `docs/acceptance/` | Which evidence satisfies which execution plan §4 row, decided before the trial runs, so the trial does not grade itself after the fact. |
| the trial record and the exit-decision record | Actual samples (by fingerprint, never by content — no-material policy), versions, gate rows, reviewer name, the owner's decision. |

It writes no product code and owns no product module. Raw samples and replies
remain in the authorised environment; only de-identified evidence or synthetic
reproductions belong in the public repository (execution plan §4's closing
rule, quoted for the record).

**6.5 Dependencies — named, one-directional.**

- **On `LC-P3-05`.** The candidate installer is the trial's vehicle.
- **On `LC-P3-06`.** The §4 table's "One real model" row is one of the gate
  rows; if `LC-P3-06` is still `BLOCKED` when the trial is ready, how the
  trial proceeds — with that row held open as a named gap, or after 06
  unlocks — is **a proposal for the owner** (§14 item 7). This draft does not
  decide it, and does not let the row pass on a substitute: `LC-P3-00` §3
  forbids exactly that.
  **Answered 2026-11-09 (§14 item 7): the trial runs with the row held
  open** — the "One real model" row carries its named gap, the remaining
  rows run, and the trial does not wait on the provider.
- **On `LC-P3-07`.** The operator manual, backup/rollback and known limits
  are the handover products the trial participant operates from.
- **On owner material:** the real advisor sample (the same named gap G1 §5.9
  holds open — one supply serves both `LC-P3-02`'s real-sample half and this
  trial), and the trial participant.
- **On owner decisions:** the trial protocol, the named reviewer, and the
  exit decision itself.
- **Q77 and Q82 stay at their triggers** (owner decision §2 item 7 of G1);
  nothing in the trial infers from a source question whose original is
  missing.

**6.6 Deliverables.**

1. The **trial protocol record**: the §4 rows mapped to their evidence
   requirements, agreed before the trial runs.
2. The **trial record**: the loop as run — actual samples by fingerprint,
   versions, what each participant did, what each gate row's evidence shows.
3. The **named reviewer's independent review** at a named commit (execution
   plan §9's discipline; LC-P3-00 §3's reviewer form, including the literal
   disclosure sentence where an agent session stands in for one human
   reader).
4. The **exit-decision record**: the owner's decision, from the evidence.

**6.7 Acceptance evidence.** Execution plan §4's full table is the checklist,
row by row, with the two sample-class rules the plan states around it: raw
samples stay in the authorised environment, and rows defined by real advisor
use are not simulated. The gate's own standard — execution plan §2 — is that
the offline loop was proven by substitution first and the real model was
exercised once, bounded, under separate owner authorisation.

**6.8 Substitute-first / real-material split.**

| Substitute-first — permitted before the trial | Real-material-gated — the trial itself |
|---|---|
| The protocol record and the per-row evidence mapping | The advisor-to-student-to-advisor loop, in every part |
| A dry-run of the §4 mapping against the substitute build (a rehearsal is not a trial result and is labelled as one) | The advisor's real sample, the real reopen, the named reviewer's read, the exit decision |

**Owner decisions answered 2026-11-10 (ground-truth revision).** These
answers revise the issued §13 against the 2026-11-10 landings (`LC-P3-03`,
`LC-P3-04`, `LC-P3-05`'s selection and the O6 fix, `LC-P3-06`'s two
halves); the dependency on 05's installed build is named in §12's answer
block above.

- **Decision 3 — one supply, one run.** Accepted option A: `LC-P3-02`'s
  recorded real-sample loop is an **input** to 08's trial record; 08 still
  runs its own advisor-to-student-to-advisor loop and cites 02's result.
  The two records cross-reference each other, and 08 never claims a row
  from 02's evidence alone. A second real sample was not commissioned, and
  02's measurement does not stand in for 08's real-advisor row.
- **Decision 4 — the `root_kinds` seam.** Accepted option A: keep
  `root_kinds={"source"}`. The trial protocol names `binding.py`'s
  approval-record minting as the product's actual behaviour; the seam
  statement in the trial protocol carries its own witness, and the
  trajectory listing not showing output versions is a known limit, not a
  defect. Widening the
  capability's root kinds before the trial was not authorised (it remains
  an owner decision for its own ticket).
- **Decision 6 — who classifies a trial finding.** Accepted option A: the
  named reviewer classifies each finding (blocker / measured gap / routed
  defect) at a named commit; a disagreement goes to a third reader as
  arbiter (`LC-P3-00` §3); the owner signs the classification with the exit
  decision. A blocker keeps the decision blocked with its evidence
  address. No finding passes on a note alone.
- **Decision 7 — the named reviewer's form.** Accepted option A: one named
  human reviewer designated by the owner, plus one independent agent
  session with no project memory as a second reader, carrying the literal
  disclosure sentence where an agent stands in for a human reader. The
  arbiter of a disagreement is a third reader. The trial's real-advisor
  rows are not read by agents alone.

---

## 14. The owner decisions these drafts surface

Numbered so the owner can answer by number. Items already recorded as blocked
are restated for completeness, not re-decided. **Items 1–7 were answered by
the owner on 2026-11-09** (through the session's decision dialogs); each item
below carries its answer in place, with the question's original wording kept.

1. **G2 dispatch shape.** `LC-P3-03` and `LC-P3-04` both write into
   `src/labcairn/application/` (03 adds the receipt/transaction integration;
   04 wires approved application onto it) and both may touch `web/`. The G1
   pattern of two fully independent parallel windows does not repeat as-is.
   Options: run 03 → 04 sequentially (the execution plan's own order); or
   dispatch in parallel with a sub-area split named at dispatch. **These
   drafts recommend the sequence as written and propose no reordering** — the
   recommendation is stated once here so the owner can overrule it, not to
   decide it.
   **Answered 2026-11-09: sequential 03 → 04**, as the drafts recommended. No
   parallel sub-area split; a window for 04 is dispatched only after 03's
   work has landed.
2. **`LC-P3-05` shell and dependencies.** The selection stage can start with
   no new material; the shell choice (Electron/Tauri/PyInstaller or none) and
   the resulting desktop dependency approvals are owner decisions made on the
   selection record's measurements (§0 rule 4's process, which the window
   follows).
   **Answered 2026-11-09: the selection stage may start now**; the shell
   choice itself stays open until the selection record's measurements exist,
   exactly as the item's own process states.
3. **`LC-P3-06`: the seven fields, now due.** G1's batch has landed; the
   2026-11-08 deferral ("decided after G1") has run its course. The seven
   questions (Q1–Q7) are ready in the questions package. Sub-decisions: the
   authorised machine for credentials (Q5's unknown) and whether the GitHub
   secret is wanted this phase (Q5's deferrable part). Also for the owner:
   whether 06 runs on the dev build before `LC-P3-05` or waits for the
   installed build (§4.7).
   **Answered 2026-11-09 — all seven fields and the three sub-decisions**;
   the answers are recorded as the authorisation fields in §11.4 below. In
   short: the owner's MiniMax endpoint (`MiniMax-M3.1-Flash`, `anthropic`
   protocol, the one measured capability record); a budget of 20 requests /
   50 000 tokens; the scheduled `provider-smoke` GitHub secret stays
   uncreated this phase (the channel stays fail-closed); credentials held on
   the trial machine via `credential_file` (the file lives outside the
   repository, per ADR-0018 C14/D2); synthetic samples first, the real
   advisor sample staying a named gap; outbound scope bound per-excerpt by
   digest (the pilot's shape); a compound stop-loss (three consecutive failed
   requests, or a per-case proposal refusal rate above 50%) watched by the
   operator; and 06 runs on the dev build before `LC-P3-05` lands.
4. **The real advisor sample's supply date.** One supply serves three open
   items: `LC-P3-02` §5.9's real-sample half, ADR-0021's final adoption
   (which must cite the real-sample run), and `LC-P3-08`'s trial. A date
   unblocks all three in order; its absence keeps all three honestly held
   open as named gaps.
   **Answered 2026-11-09, in two parts.** (a) The material is identified:
   the owner confirmed the uploaded micro-nano-bubble reference batches as
   this direction's corpus and named batch A (the two MSc papers whose
   advisor-annotated versions carry the advisor's comments and tracked
   revisions) as the initial advisor-material batch. All four batches were
   fingerprinted the same day into an operator-side registry outside the
   repository (111 `.docx` files: sha256, byte size, comment/revision/media
   counts; no prose extracted, no file enters the tree — the no-material
   policy holds). (b) **The sample is picked** (later the same day): batch
   A's fingerprint ranking pointed at the green-algae inhibition paper's
   advisor-annotated version, the owner confirmed it, and its digest is
   recorded at §5.9 (`9154e56c…7652d`, 4 comments / 270 ins / 119 del / 10
   media parts; the project's structure survey carries eight classes and
   blocks none). What is still open is the loop itself: §5.9's real-sample
   half, ADR-0021's final adoption and `LC-P3-08`'s trial stay honestly
   held open as named gaps until that loop has run and been recorded.
5. **ADR-0021's provisional adoption as `LC-P3-04`'s foundation.** Whether 04
   may build on the provisional adoption (record `proposed`) or waits for
   real-sample evidence. The drafts' dependency tables assume provisional is
   sufficient for the *substitute* loop and flag the assumption for the owner
   to confirm or refuse.
   **Answered 2026-11-09: provisional is sufficient.** `LC-P3-04` builds on
   the provisional adoption; ADR-0021's record stays `proposed`, and its
   final adoption still waits for the real-sample run it must cite.
6. **ADR-0021's `temporary` independent-copy mechanism.** At `LC-P3-03`'s
   landing the temporary mechanism is replaced or absorbed; whether the
   disposition may edit ADR-0021's text or waits for final adoption is the
   owner's call (§1.5).
   **Answered 2026-11-09: the disposition does not touch ADR-0021's text.**
   `LC-P3-03`'s own record states what happened to the temporary mechanism
   (replaced or absorbed, and where it went); the ADR's wording is settled
   at its final adoption.
7. **`LC-P3-08` under an unlocked-or-not provider.** If the trial is ready
   while `LC-P3-06` is still `BLOCKED`: hold the "One real model" row open as
   a named gap and run the rest, or wait. The drafts state the row cannot
   pass on a substitute either way (`LC-P3-00` §3).
   **Answered 2026-11-09: run the trial with the row held open.** If
   `LC-P3-06` is still `BLOCKED` when the trial is ready, the "One real
   model" row carries its named gap and the remaining rows run; the trial
   does not wait on the provider.
8. **The §4.9 human dual-host reopen checklist (G1 leftover, owner
   personally).** Not a decision about these drafts, but it is the open item
   the G1 records name first, its inputs (`LC-P3-02`'s substitute-run
   outputs) exist, and the performer is the owner by the 2026-11-08 decision.
   Restated so it is not lost under the new tickets.

Standing constraints that need no new decision: Q77 and Q82 stay at their
triggers; signing and public distribution stay behind `W28`; CI stays on
substitutes; no push, no pull request, no CI run until the owner's word
(`CLAUDE.md`).

---
## 15. What this file does not do

It dispatches no window and opens no worktree. It authorises no push, pull request
or CI run. It writes no product source, no test, no migration and no workflow
file. It closes no gate and marks no ticket done. It quotes no commit other than
the two printed in the header. Its status rows are the truth at this commit,
and the board changes in the same commit as any evidence that moves one. **The
landing moves are commander-owned at merge:** the board rows, the registration
files §3 rule 3 names, and every live status pointer that moves with a row — the
two README banners, `README.zh-CN.md`, `docs/README.md`, `docs/ROADMAP.md`,
`docs/handoff/CURRENT.md`, `CHANGELOG.md`, `docs/REPOSITORY-MAP.md` and
`docs/plans/PHASE_3-execution-plan.md`. A window reports what its evidence says;
it does not move a row or a pointer, because the row and the pointer must move in
one commit and only the merge commit carries both.

The order is fixed: `LC-P3-02`'s substitute round-trip outputs and records land
before `LC-P3-01`'s row may move to `PASS` or `PASS WITH NOTES`, because §4.9's
human dual-host reopen checklist consumes those outputs and has not been
performed. `LC-P3-01`'s existing `IN PROGRESS` move (local `main`, the LC-P3-01
merge) did not violate this; a `PASS` move now would.

---

## 16. The repair this batch carries: the write seam's path-length budget

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
`src/labcairn/security/paths.py`, `tests/test_workspace_boundaries.py` and the
dedicated witness `tests/test_workspace_path_length.py` belong to this item while
the batch runs. The new file is separate because
`tests/test_workspace_boundaries.py` is a `no-unauthorized-write-or-disclosure`
blocker witness: a POSIX skip inside it would break the blocker denominator. The
new file carries its own `pytest.mark.integration`, registers in the shard and
manifest tables, and leaves the blocker file unchanged. `LC-P3-01` and `LC-P3-02`
do not edit these; both sequence against them.

---

## 17. Open gaps, with what each is waiting on

| Gap | Waiting on | Where it is stated |
|---|---|---|
| The real advisor sample and its full loop | The loop itself, run on the picked sample and recorded (the sample was picked 2026-11-09: batch A, digest at §5.9; the file stays outside the repository) | §5.9, §14 item 4 |
| `LC-P3-06`'s real-model row | `LC-P3-04`'s proposal path (the thing the real model exercises) and the de-identified domain sample; the seven authorisation fields themselves are answered (§14 item 3, tabled at §11's §4.9) | §1, §11, [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §4 |
| A Windows browser pass a runner has run | A runner run, which the owner starts | §3 rule 6, execution plan §6 last row |
| Which side carries the driver, and whether the witness is new or extended | The implementation window's first recorded decision | §4.12 |
| Which system-browser channel the trial machine has | A measurement at dispatch | §4.12 |
| Q77's per-layer rules and Q82's original | Their own triggers: a memory-interface design task, and a later requirements baseline only the owner can state | §1, [`LC-P3-00`](../acceptance/LC-P3-00-board-opening-decisions.md) §8 |
| Version switching in the workbench | A version-selection surface and a browser witness; named gap, not claimed | §4.8 |
| The §4.9 human dual-host reopen checklist | The owner personally performing the 44-row checklist (§14 item 8); the operation page and CSV inputs exist outside the repository | §5.8, §14 item 8 |

---
