# LC-P3-07 — operator manual (skeleton)

> **DESIGN — not a deliverable until run on the installed build.**
> `LC-P3-07` stays `BLOCKED` on `LC-P3-05`'s installed build (work orders
> §12 decision 2, 2026-11-10). This is the manual *skeleton* §5.5 names as
> early-startable design. It carries **no measured behaviour**: every sentence
> that would describe what the installed build does is a placeholder marked
> **[fill after run]**. The skeleton's purpose is to fix the manual's shape now
> — so that the drill run fills sections rather than inventing a structure
> under time pressure — and to keep the writing honest: a section that has not
> been observed is visibly empty, not plausibly filled.

Companion designs: [drill matrix](LC-P3-07-drill-matrix-design.md),
[diagnostics](LC-P3-07-diagnostics-design.md),
[backup/rollback](LC-P3-07-backup-rollback-design.md). Work order:
[PHASE_3-work-orders.md](PHASE_3-work-orders.md) §12; the manual is §12
§5.6 deliverable 4, paired with the known-limits record (§6 below).

## How the skeleton is written

- **[fill after run]** is a load-bearing marker: the section's shape is decided
  here, its content waits for the installed build's observed behaviour
  (§12 §5.8: *"The manual and known limits, written against the installed
  build's actual behaviour"*). An implemented manual that still carries the
  marker is an unfinished deliverable — that is the point of the marker.
- Commands named below are the ones that exist in the CLI today
  (`src/labcairn/cli/commands.py`: `init`, `doctor`, `serve`, the `task` group
  with `create` / `status` / `run` / `resume` / `report` / `claim` /
  `claim-attest` / `proposal-confirm` / `approval-request` / `approval-grant`
  / `reconcile`, the `sources`, `artifacts` and `guidance` groups). Whether
  the installed build's shell *exposes* these or replaces them with window
  actions is the installed build's fact — **[fill after run]** wherever a
  section names a command.
- No screenshot, no timing, no wording of an error message, no "click X" step
  appears in this skeleton. Where a real manual will need one, the section says
  what the step must establish and leaves the wording to the run.

## Manual structure

### 0. About this manual

- Who it is for: the trial participant running the loop, and the person
  supporting them (§12 §5.4; the trial itself is `LC-P3-08`, work orders §13).
- What it is not: not the architecture
  ([../ARCHITECTURE.md](../ARCHITECTURE.md)), not the security model
  ([../THREAT-MODEL.md](../THREAT-MODEL.md)).
- **[fill after run]** the build identity line: which installed build this
  manual describes — version, package hash, OS and Word versions, the commit
  (execution plan §4's evidence row demands exactly these five, "names the
  commit, package hash, OS and Word versions").

### 1. Getting the build onto the machine

- Install, launch, first run. **[fill after run]** — every step: the installer
  file, what Windows says during install (SmartScreen / signing status is
  `W28`-deferred territory — work orders §12 §5.3; the manual records the
  *observed* state, not a promise), where the data lands, how to start the
  task surface.
- Uninstall and rollback exist in this build (`LC-P3-05`'s drill); their
  **steps** belong here and their **preservation claims** live in
  [backup/rollback design](LC-P3-07-backup-rollback-design.md).
  **[fill after run]**.

### 2. The loop, start to finish

The manual's spine is one revision loop as the operator performs it. Each step:
the action, the confirmation the operator sees, and — where the design says a
consent is spent — the consent's question in the operator's terms.

| Step | What the design fixes here | What the run must supply |
|---|---|---|
| 2.1 pick the source | the source roots and what "read-only door" means for the operator's files (`labcairn.workspace.readonly`) | **[fill after run]** the shell's wording |
| 2.2 the import | the import receipt exists and *names the original's hash* (`open_loop` / `ImportReceipt`) — the manual shows where the operator sees it | **[fill after run]** |
| 2.3 the copy, and its consent | the copy spends one approval bound to the original's bytes (`request_loop_approval`, `bound_sources`) | **[fill after run]** the consent prompt's text |
| 2.4 edit | where the edited file lives (`revisions/<receipt_id>/copy.bin` in the task output area) | **[fill after run]** which app the person edits in |
| 2.5 publish, and its consent | the second approval; the publication receipt derived from two derivations (`publish_revision`); a second publication of the same loop is refused by name (`loop_already_published`) | **[fill after run]** |
| 2.6 the review half | the binding half (`labcairn.papers.binding`: opinions, suggestions, decisions, handover) as far as the trial's loop reaches | **[fill after run]** |

### 3. When something goes wrong — what the build says, and what to do

The section is organised by **what the operator sees**, keyed to the five
drill classes ([drill matrix](LC-P3-07-drill-matrix-design.md)), so that the
drill's evidence feeds this manual row-for-row:

| What you see | What it means (design answer, from the landed refusals) | What to do |
|---|---|---|
| the run stopped mid-write / a file is half there | shouldn't happen by design — writes are atomic (`TaskOutputArea.write`) — the drill proves it; if observed, it is a defect report | **[fill after run]** the observed behaviour and the operator's action |
| "file in use" / a lock | the refusal names it and lands before any write (`refusal.py`'s `path_refused` family; the read-only door's refusals) | **[fill after run]** the observed message and action |
| the network went out mid-request | the failure is typed and retryable (`FailureKind.PROVIDER_TRANSIENT` / `TIMEOUT` with the retry action in `errors.py`'s classification); local results already confirmed stay confirmed | **[fill after run]** what the shell shows |
| the model took too long | the run has a ceiling and a stop-loss (three consecutive failures ends it — `bounded_run.py`'s `CONSECUTIVE_FAILURE_LIMIT`); nothing is published from a timed-out suggestion | **[fill after run]** what the operator sees, including the stop |
| a refusal naming itself (`cross_project_access`, `approval_refused`, `source_drifted`, …) | each is a design refusal with a reason; `describe_abandoned`'s style — refusal *and* remedy in one message — is the pattern the manual's rows copy | **[fill after run]** one row per refusal the build actually surfaces |
| "a crash left operations whose outcome the record cannot state" | the recovery path: the CLI's own command is printed in that message (`labcairn task reconcile <operation_id> --expected-sha256 <hash>`); the hash is *not in the store* — the CLI's own help already names today's source for it (`labcairn sources inspect` prints the material's content hash) | **[fill after run]** which source the installed build's operator actually uses |

### 4. Getting diagnostics out

- How to collect the package
  ([diagnostics design](LC-P3-07-diagnostics-design.md)), and what the package
  does and does not contain — the manual's job is the "does not" half in the
  participant's words: **your material is not in it**, proven the way the
  design's witness proves it. **[fill after run]** the exact command/button and
  the observed refusal text when a package is refused.
- **[fill after run]** where a participant sends it (trial logistics are
  `LC-P3-08`; signing/distribution is `W28`-deferred).

### 5. Backups and rollback

- Which backup points the build takes (§3 of the
  [backup/rollback design](LC-P3-07-backup-rollback-design.md)), where they
  live, and the operator's role at each. **[fill after run]**.
- Rollback: what it restores, what it deliberately never rewrites (the ledger,
  published receipts), and how an operator *checks* a rollback did what §2 of
  that design claims. **[fill after run]**.

### 6. Known limits

§12 §5.6 deliverable 4 pairs the manual with a **known-limits record**; the
manual carries the operator-facing half and links to the record. Skeleton rows
— each deliberately a question the trial answers, not an answer:

- model behaviour limits the build makes visible (timeouts, refusals,
  stop-loss): the substitute machinery is landed
  ([../acceptance/LC-P3-06-substitute-first-2026-11-10.md](../acceptance/LC-P3-06-substitute-first-2026-11-10.md));
  the real-model row stays a named gap per §12 decision 5 — the limits section
  states the gap plainly rather than covering it.
- platform limits: which Windows, which Word versions the trial evidence will
  name. **[fill after run]**.
- the loop's deliberate refusals as limits (no second publication; a stale
  original is refused rather than patched).
- **[fill after run]** whatever the drill matrix's drill record found —
  §12 §5.6 deliverable 5's measured-gap list lands here as its operator-facing
  sentences.

### 7. Where the details live

Links, not restatements: the work order §12; the drill record under
`docs/acceptance/` **[name it after the run]**; the diagnostics,
backup/rollback and drill-matrix designs in this folder; the ADRs the manual
touches
([ADR-0002](../adr/ADR-0002-model-and-tool-execution-boundary.md),
[ADR-0003](../adr/ADR-0003-event-and-permission-model.md),
[ADR-0023](../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md)).

## What the run has to do to finish this manual

1. Replace every **[fill after run]** with observed behaviour, each row citing
   the drill record's evidence address (§12 §5.6 deliverable 1's format:
   fault, injection, observed behaviour, evidence address).
2. Add the §0 build-identity line only once an installed build exists — the
   five evidence values execution plan §4 names (commit, package hash, OS,
   Word versions, results).
3. A section that the run could not fill becomes a named gap in the
   known-limits record — an empty placeholder is allowed to stay empty **only
   when the limits record says why** (a silent empty section is the failure
   mode this skeleton's markers exist to prevent).
4. The finished manual is a document under `docs/` (location decided at run —
   the manual has no file yet, so nothing links to it yet; link witnesses are
   safe).
