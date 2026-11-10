# Changelog

**Format:** [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
**Versioning:** the package declares `0.1.0` in `pyproject.toml`.

**No tag has been cut and no release has been published.** Everything below
is **unreleased**. LabCairn original code is granted under MIT by the root
[`LICENSE`](LICENSE) file; third-party terms are in `NOTICE`. See the
[licence status](docs/RELEASE-NOTES.md#4-licence-and-security-status).

The changelog is organised by **gate**, because the gates are how this
project is organised: each one closed on a review, and each has a record.
The links are the records.

---

## [Unreleased]

### The real-sample machine half lands, with the human half held open (2026-11-10)

- `LC-P3-02`'s owner-picked advisor sample ran its 42-arm machine loop:
  42/42 arms, 14 produced, 28 refused, 0 errors, 0 expectation mismatches,
  8 artifacts, and report digest
  `a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`.
  The dated record is
  [`LC-P3-02-real-sample-2026-11-10.md`](docs/acceptance/LC-P3-02-real-sample-2026-11-10.md),
  with a JSON summary and three append-only ledger digests. A read-only
  independent critique found that partial records printed a false zero
  artifact count, used final/completion wording too early, lacked a ledger
  digest and attributed batch exits without a measured status. The generator
  was repaired and the final record re-rendered; the append-only ledger was
  not rewritten.
- The substitute-run record, its `test_docx_edit_records.py` witness, the
  board's `LC-P3-02` row and §17, and `LC-P3-08`'s evidence map were
  re-targeted in one batch to the measured machine-half state. That state
  closes no human half: the dual-host reopen remains `NOT RUN` and no
  ticket verdict is transferred from the machine loop to the gate.

### Owner decisions on the in-flight G3/G4 batch (2026-11-10)

Two rounds of decisions were answered by the owner through the session's
dialogs while the implementation windows and their background measurements
were in flight. The first round covered the shell attribution lines, the
42-arm loop and named gaps. The second round ruled that the shell's 17
independent-critique findings are listed as gaps at the gate rather than
repaired in this batch; that stale records and `pyproject.toml`'s
`norecursedirs` are corrected now; that the accumulated local commits stay
unpushed until a later owner-authorised delivery; and that the remaining
40 dual-host checklist rows are collected through dialogs from the owner's
own observations. None changes a measured result or authorises a push, pull
request or CI run.

A later dialog narrowed the 44-row checklist's personal verification to the
WPS host only. That ruling applies to the 44-row checklist and not to the
real-sample half-loop's separate 16 human-reopen rows. Word 2010 rows stay
`PENDING-HUMAN`; a WPS observation is never copied into them or treated as a
Word result. If the owner supplies a WPS screenshot, the conductor reads only
the visible structure's presence and waits for a separate confirmation before
filling any form value. Screenshots and material words do not enter the
repository.

- The four Electron shell follow-up commits already made at the time of the
  decision keep the
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` line injected
  by the harness. The static audit of `main` at `1670e73` measured fifteen
  such commits there: eleven earlier Electron shell commits and four
  `LC-P3-07` design commits. Since that audit, the four shell follow-up
  commits and one `LC-P3-02` real-sample re-render commit entered the
  accumulated range with the same harness-injected line: **twenty commits in
  the current range**, none amended. New commits use the current
  `Co-Authored-By: Claude Code <noreply@anthropic.com>` line. The count was
  re-measured after the later merges rather than carried forward.
- `LC-P3-02`'s real-sample half-loop continues to all 42 arms. A 33/42
  append-only ledger is a partial measurement, not a completed loop; the
  substitute-run record and its witness are re-targeted together only after
  the final acceptance record lands.
- The Electron shell batch may be reviewed and merged locally with its
  measured `T08`, `T09` and Windows graceful-shutdown gaps named as gaps.
  Those gaps are not converted into passing rows; their classification is
  signed by the owner at the gate's exit decision.

### The Electron shell skeleton runs, and the drain rule is witnessed (2026-11-10)

- A new top-level `shell/` (beside `web/`, nothing under `src/labcairn/`
  touched) carries the main process the plan describes: a service supervisor
  that attaches `data` readers to both child pipes at spawn and drains them
  into a bounded log file outside the repository, readiness as the
  `ServiceStarting` line **and** a `GET /health` 200, a window built with
  `nodeIntegration: false` / `contextIsolation: true` / `sandbox: true`, a
  CommonJS preload exposing one status getter and no token, and a config module
  that refuses a dev page URL in a packaged configuration.
- The drain witness (`shell/test/drain-witness.test.mjs`) is O6's control pair
  — the same injected writer child and the same dose run drained and undrained,
  the undrained arm reproducing the stall — plus a real-`labcairn serve` arm and
  a foreign-listener refusal arm. **The dose is measured, and the measurement
  corrected an assumption:** the witness's first run carried the record's
  4,096-byte anonymous-pipe number and the undrained arm answered the dose,
  because `spawn`'s own pipe measures 114,688 fits / 131,072 stalls here; the
  file now runs its own ladder (`8192…131072:stalls`) and asserts
  `dose > threshold` before either arm executes. Two counter-mutations were run
  and both reddened what they should: removing the production reader, and
  swapping a `file://` page load into the packaged path.
- Two rehearsals close the loop on a real window: the packaged-shaped run
  (service carries `web/dist`, page asserts its own origin over CDP, service
  force-killed from outside, the same window shows `disconnected`, no respawn;
  closing the window exits 0 with no orphan and a free port) and the dev-mode
  run against the repository's **own** Vite arrangement — Vite started with a
  config that imports `web/vite.config.ts` and overrides only the proxy target,
  because port 8000 belongs to Docker Desktop on this machine and the rehearsal
  neither displaces a foreign listener nor edits another window's file. The
  dev page reaches the API through the inherited proxy; a packaged-shaped run
  loads no dev origin, asserted from inside the page.
- A measured finding that changes what a later step must build: on Windows,
  Node's `child.kill('SIGBREAK' | 'SIGTERM' | 'SIGINT')` reaches none of a
  Python child's handlers in any of four spawn arrangements (twelve runs, all
  `handler=no handler ran`), so the G1 helper's graceful-ask assertion
  (`outcome.forced is False`) has no Node equivalent by that route. The witness
  asserts what is measured — the child ends, the port releases, no pid survives
  — and prints the outcome rather than claiming the ask worked. Record:
  [`LC-P3-05-shell-skeleton-2026-11-10.md`](docs/acceptance/LC-P3-05-shell-skeleton-2026-11-10.md).
- `electron` **45.2.3** (MIT) is added to `shell/package.json` with a committed
  lockfile, matching the selection record's measured version. **Correction,
  2026-11-10**: the owner approved Electron 45.2.3 / MIT /
  `shell/pnpm-lock.yaml` by dialog that day — the approval is no longer
  outstanding. `pyproject.toml`, `uv.lock` and the `web/` manifests remain
  untouched. The skeleton-batch wording below this line is left as written;
  the follow-up batch's dated section (§10 of the acceptance record) names
  which of the gaps it closed. No board row moves.

### The shell skeleton's named gaps, closed where they could be (2026-11-10)

- **T05's live 401 half**: a real Electron window sends one fixed tokenless
  `POST /task/select` from its sandboxed preload; the real service's
  `SessionGuard` refuses **401 `session_required`**; the main process validates
  the IPC sender's **origin** before printing or echoing the verdict, and the
  status strip shows it. The diagnostic page (`about:blank`, origin `null`) is a
  refused sender. `shell/test/live-guard.test.mjs` (5 tests) reads the request
  back out of the file that builds it and drives both IPC decisions;
  `shell/scripts/rehearse-live-guard.mjs` reads strip, bridge and the main
  process's line back over CDP.
- **T06's three unwitnessed arms**: `shell/scripts/rehearse-lifecycle.mjs`
  witnesses startup refusal (visible diagnostic on `about:blank`, no foreign
  page), a main-process crash injected over the real `--inspect` (no service
  orphan, port released), and the single-instance lock (second launch exits 0,
  starts no service, first shell and child stay alive). Each run gets its own
  `--user-data-dir`, except the second-instance arm where a shared directory
  is the property under test.
- **AC-7 / AC-8 static halves**: `shell/test/dependency-surface.test.mjs`
  (3 tests) watches the runtime surface and the approved dependency set, with
  an introduced remote host as positive control;
  `shell/test/native-surface.test.mjs` (6 tests) watches the enumerable
  preload surface, `webPreferences`, the two spawn call sites and
  COM/ProgID/UI-automation routes, with a real `shell.openExternal` plus a
  `'Word.Application'` ProgID as positive control. Both record what they do
  **not** cover: Electron's install-time binary channel and §0 rule 2's
  human review.
- `node --test "shell/test/*.test.mjs"` → **27 pass / 0 fail**. Thirteen
  counter-mutations, run singly with a clean-tree baseline and a parse gate,
  were all effective (12 red, one comment-only control green). Three defects
  in the measurement harness itself — two concurrent runs, an off-by-one
  splice, and a shared Electron `SingletonLock` — were found, repaired and
  recorded in §10.3 of the acceptance record.
- **Still named gaps, by the owner's 2026-11-10 decision**: T08 (packaging /
  O3 runtime arrangement), T09 and AC-6 (clean-Windows drill, signing behind
  `W28`, support limits, §0 rule 2 review), and AC-2's Windows graceful-ask
  arm (§6.2's measured gap, not attacked). No installer tooling, WiX/NSIS/
  Inno or `signtool` exists on this machine; no green is claimed for them.
  Evidence: [`LC-P3-05-shell-skeleton-2026-11-10.md`](docs/acceptance/LC-P3-05-shell-skeleton-2026-11-10.md)
  §10. Nothing pushed, no PR opened, no CI run started.

### Phase 3 G4 owner decisions and the Electron shell choice (2026-11-10)

- The G4 drafting round found that the board's `LC-P3-07`/`LC-P3-08` row
  was stale: §§12–13 were already issued work orders (2026-11-09), not
  missing ones. The owner answered eight decisions the same day through
  the session's dialogs, and the answers are published in place at the end
  of §12 and §13, with the board row corrected in the same commit: this
  is a ground-truth revision of the issued orders against the 2026-11-10
  G2/G3 landings, not a first issuance and not a re-decision of §14's
  answered items. 07/08 stay `NOT STARTED`, blocked on `LC-P3-05`'s
  installed build; design work is labelled design, not deliverable until
  run; one real sample supplies both 02 and 08; the `root_kinds` seam is
  named, not widened; the named reviewer is a human plus an independent
  agent second reader with a third-reader arbiter; publication joins the
  next owner-authorised batch, with no push, PR or CI run of its own.
- [ADR-0023](docs/adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md)
  is **Accepted** on the owner's Electron choice (the only candidate
  buildable on this machine in the selection measurement), and
  [`LC-P3-05-shell-implementation-plan.md`](docs/plans/LC-P3-05-shell-implementation-plan.md)
  carries nine implementation steps. O6's measured lesson — a traceback
  written into a pipe nobody drains stops the event loop — is a hard rule
  of the main process with a witness design attached. The O6
  precondition in the selection record is discharged.
- The real-model half of `LC-P3-06` ran bounded on synthetic samples:
  5 requests, 0 refused, 0 failed, 5,136 of 50,000 authorised tokens,
  stop-loss never fired, dry reconciliation MATCHED before the spend;
  record [`LC-P3-06-real-half-2026-11-10.md`](docs/acceptance/LC-P3-06-real-half-2026-11-10.md).
  The record names seven measured gaps, including that the ladder's
  four-request layout produced no locatable suggestion, that no timeout
  was actually drilled, and that its audits are operator self-review.
  No key, response prose or advisor material entered the tree.
- **The owner closed the follow-up question the same day:** on the five
  decisions surfaced by the bounded follow-up design (kept outside the
  repository), the owner chose no real-call follow-up now (D1). The
  remaining 15 requests / 44,864 tokens stay unspent; G4's structural
  question is routed to `LC-P3-08`'s suggestion path and G5 stays witnessed
  by the landed substitute rehearsal. D2 (G5 first) is recorded as the
  conditional answer only; D3–D5 (arm caps, G4's allowed change, consent and
  review) were not triggered, and no credential was read.
- The Electron shell skeleton (plan steps 1–3) landed with 13 Node
  witnesses, the drain rule wired before the child can write, and a record
  that names the whole Python suite as not run: see
  [`LC-P3-05-shell-skeleton-2026-11-10.md`](docs/acceptance/LC-P3-05-shell-skeleton-2026-11-10.md).
  The synthetic dry run of `LC-P3-08`'s reviewer form (report outside the
  repository) found 12 observations; the two that made the form
  mechanically unusable were repaired in the tree — a classification
  precedence carve-out for owner-authorised named gaps, and F-11's dead
  `F-20` reference — while the other ten stay for the gate's form review.
- The batch delivery's first CI run failed five shard jobs on the
  shard-cost freshness witness, as designed: six test files had joined
  the suite since the previous measurement. The costs were re-measured
  from that run's own `--durations=0` log (run `42733499009`, Windows
  balance 1.000 / Ubuntu 1.274). That run's clean-room evidence also
  caught a dead `LC-P3-03` record link, fixed in the board and here.

### Phase 3 G2/G3 batch: three windows land locally (2026-11-10)

Three windows reviewed and merged into `main` by the conductor session, each
on its own branch, one ledger run per merge (`LOST -- none` in all three):

- **`LC-P3-03` — the project revision loop lands** (merge `4855ea6`).
  `src/labcairn/application/revision_loop.py` carries the loop from import
  receipt through read-only original, independent copy and publication
  receipt to the recovery path; four refusal classes
  (`cross_project_access`, path escape, stale approval,
  `loop_already_published`) are witnessed, and all four counter-mutation
  families were caught. 17 new witnesses registered in three places; the
  acceptance record is
  [`LC-P3-03-revision-loop-2026-11-10.md`](docs/acceptance/LC-P3-03-revision-loop-2026-11-10.md).
- **`LC-P3-06` substitute-first half lands** (merge `7d5be74`).
  `src/labcairn/providers/deidentify.py` (8-word n-gram pipeline, outbound
  CJK ceiling, named-secret scrub; three sample classes) and
  `src/labcairn/providers/bounded_run.py` (the refusal ladder harness,
  per-excerpt digest binding, the Q7 two-arm stop-loss, the
  digests-and-counts run record). 33 witnesses, 12/12 counter-mutations;
  every ladder tier fails to zero calls on budget or consent. The
  acceptance record is
  [`LC-P3-06-substitute-first-2026-11-10.md`](docs/acceptance/LC-P3-06-substitute-first-2026-11-10.md).
  The real half was still waiting on `LC-P3-04` and the sample when this
  entry was written; it ran the same day and is recorded in the
  2026-11-10 G4 entry above.
- **O6 — the event-stream stall is fixed** (merge `9cdb19a`). The mechanism
  is measured, no longer open: a refusal raised after the `200` and
  `text/event-stream` headers were sent became a traceback written into the
  service's own output, and a caller holding it in an undrained pipe
  blocked the event loop (pipe capacity 4,096 bytes, measured; one short
  stream wrote 6,205 bytes). The fix refuses an unwired stream at the route
  entry, before the headers; `events.py` holds the refusal sentence as the
  single source for both paths. The record is
  [`o6-event-stream-stall-2026-11-10.md`](docs/acceptance/o6-event-stream-stall-2026-11-10.md).
  The browser-gap row it replaced was re-measured, not deleted: the old
  witness asserted a contradiction that the fix removes, and the new one
  keeps the service-side half of the old assertion.
- **`LC-P3-04` — the binding loop lands** (merge `2dce121`).
  `src/labcairn/papers/binding.py` carries the loop's five rings — opinion →
  locate → suggest → apply → dossier — with the model's suggestion and the
  human's judgement held as separate records and the unresolved-opinion
  state an explicit three-way task; `reports/response_table.py` and
  `quality_report.py` render it inside ADR-0013's boundary, and the
  workbench gains a per-item review panel (`web/src/views/ReviewView.tsx`)
  consuming the existing artifacts/content endpoints. 17 Python witnesses
  (12 integration, 5 negative) and 5 web witnesses; 6 counter-mutations
  caught. The acceptance record is
  [`LC-P3-04-binding-loop-2026-11-10.md`](docs/acceptance/LC-P3-04-binding-loop-2026-11-10.md).
  The real-model half of `LC-P3-06` is what this unlocks; the shard costs
  of the day's four new test files wait on the batch runner run.
- The selection stage's O6 row was cross-referenced to the fix record, and
  `docs/THREAT-MODEL.md` gained the stall's own entry.

### Phase 3 G1 aftermath: work orders and platform rule (2026-11-09)

- [ADR-0022](docs/adr/ADR-0022-platform-conditional-code-keeps-one-reachable-body.md)
  accepted: platform-conditional code keeps one reachable body on both checker
  platforms — guards route through helper calls, Windows-only attribute reads
  carry scoped ignores, runtime semantics are preserved exactly. The five CI
  repair rounds it records were PR #153's own history.
- `docs/plans/PHASE_3-work-orders.md` carries the ratified work orders for
  `LC-P3-03` … `LC-P3-08` (§8–§14, drafted against main `571e4346` by an
  independent session and issued on the owner's selection). `LC-P3-06` stays
  `BLOCKED` on the provider's seven fields; every ticket whose §14 decision is
  unanswered stays `NOT STARTED`. The trailing sections renumbered to §15–§17.
- `PHASE_3-work-orders.md` §3 rule 3a names the ADR's shape as a standing rule.
- **The §14 owner decisions were answered the same day** (items 1–7, through
  the session's decision dialogs; answers recorded in place under each item):
  G2 runs `LC-P3-03` → `LC-P3-04` sequentially; the `LC-P3-05` selection
  stage may start; all seven provider fields are answered and tabled as the
  authorisation record at §11's §4.9 (MiniMax endpoint and model, 20-request
  / 50 000-token budget, per-excerpt digest-bound outbound scope,
  `credential_file` on the trial machine, the scheduled-smoke GitHub secret
  uncreated this phase, synthetic samples first, compound operator-watched
  stop-loss, dev build before the installed build); ADR-0021's provisional
  adoption suffices for `LC-P3-04`; `LC-P3-03`'s temporary-mechanism
  disposition leaves the ADR's text alone; `LC-P3-08` runs with the
  "One real model" row held open. The real advisor sample stays a named gap:
  the owner named batch A of the uploaded micro-nano-bubble corpus as the
  initial advisor material, and the whole corpus (111 `.docx` files) was
  fingerprinted into an operator-side registry outside the repository —
  structure-only, no prose in the tree, §5.9's label unchanged until the
  single sample file is picked.
- **The sample was picked the same day**: from batch A's fingerprint ranking
  the owner chose the green-algae inhibition paper's advisor-annotated
  version (sha256 `9154e56c…7652d`, 4 comments / 270 ins / 119 del / 10
  media parts; the project's structure survey carries eight classes, blocks
  none). Its digest and counts are recorded at §5.9 and §14 item 4; the file
  itself stays outside the repository, and the real-sample half's `NOT RUN`
  label stands until the full loop runs on it. The selection stage's ADR
  number was corrected the same day: ADR-0022 is taken, so `LC-P3-05`'s
  selection ADR names ADR-0023 as of this writing and re-checks at issuing.

### Since the gates closed

### Phase 2 final closeout (2026-11-06)

- PR #148 merged as `0d654b2038051805eb0ab410783ea2fe90545506`; its delivery
  branch was deleted locally and on the remote.
- Batch 11's two-paper version graph, approved real-store write and three
  negative witnesses landed locally; both scratch refs were deleted.
- The owner confirmed the holder and authority to grant MIT. The root
  `LICENSE` carries `Copyright (c) 2026 Tonghe Du`;
  `LICENSE.PENDING.md` was deleted, and the current-state documents,
  release metadata and licensing witnesses were updated together.
- Phase 2 administrative closeout is CLOSED; the final open items are in
  [`LC-P2-28-phase2-open-items.md`](docs/acceptance/LC-P2-28-phase2-open-items.md).
  Phase 3 has not started.
- The owner authorised a Phase 3 scoping / ADR pack only. It records
  boundaries, dependencies and owner decisions; it creates no work order and
  starts no Phase 3 implementation.
- The owner's follow-up decisions archive `ADR-0020` and `LC-P2-28` as
  historical Phase 2 design, defer every candidate Phase 3 scope family, and
  leave the real-provider smoke NOT RUN with no credential configured. The
  local record commits were initially held locally.
- An operator-side WSL measurement of the POSIX-only path and session-directory
  witnesses is recorded outside the repository. It does not change the frozen
  Phase 2 gate record.

### Repository tidy (2026-11-06)

- A read-only classification found 727 tracked files, 199 Python test files,
  3,419 declared test functions and no exact-byte duplicate groups. The
  [`REPOSITORY-MAP.md`](docs/REPOSITORY-MAP.md) records where each class
  lives; no witness, fixture or historical acceptance record was removed.
- Current-state pointers in the bilingual READMEs, documentation index,
  roadmap, handoff and `web/package.json` now agree with MIT and the CLOSED
  Phase 2 closeout. Dated gate snapshots keep their original wording.
- The GitHub repository description no longer says licensing is pending.
- The owner authorised one tidy delivery PR and one runner run to carry the
  local records online. This changelog claims no runner result before the
  pull request reports one.

### Phase 3 planning proposal (2026-11-06)

- The owner accepted a proposed Phase 3 exit gate: a Windows research-group
  internal trial with one complete DOCX revision loop, substitute-first
  validation and one bounded real-model check. Multi-platform public
  distribution moves to a later work package. This is a planning direction,
  not an approved work order.
- Two Chinese working drafts were found untracked and were not delivered.
  Byte-for-byte copies and the owner-supplied Word/PDF source stay outside
  the repository. They were replaced by an English
  [`PHASE_3-execution-plan.md`](docs/plans/PHASE_3-execution-plan.md) and
  [`PHASE_3-design-traceability.md`](docs/plans/PHASE_3-design-traceability.md),
  both marked `Proposal — not approved, not dispatched`.
- The execution proposal adds a code-facing gap register that names real
  entry points and missing capabilities. No product source, test, workflow
  or migration file is changed by this planning proposal.
- A dated [`PHASE_3-planning-decisions-2026-11-06.md`](docs/acceptance/PHASE_3-planning-decisions-2026-11-06.md)
  records the four owner decisions and the decisions that remain open.
  Q76, Q77, Q81, Q82, Q86, Q87 and Q96 stay unresolved.
- The owner authorised one planning-delivery PR and one runner run. No
  provider credential, real-model request, signing, tag, release or Phase 3
  implementation is authorised, and no runner result is claimed before the
  pull request reports one.

### Phase 3 gap-register correction (2026-11-07)

- Two independent read-only session audits checked the delivered Q1-Q96
  traceability and the code-facing gap register. The Q1-Q96 status table
  passed with all 96 rows and all seven unresolved source questions intact.
- The gap register now distinguishes a fidelity-preserving manuscript edit
  from the existing report-only DOCX writer, names the existing source-root
  read-only guard and `RetrievalTelemetry`, states that existing tests do not
  all carry `pytestmark`, and records that the web workflow is Ubuntu-only.
- No product source, test, workflow or migration file is changed by this
  correction. It remains a planning proposal, not a work order.

### Board answers and the multisource supplement (2026-11-07)

- The owner answered the board-opening decision dialogs. Confirmed: the
  `LC-P3-00`…`LC-P3-08` numbering, the Windows internal-trial exit gate with
  the §4 checklist as written, and the existing reviewer rules (agent
  stand-ins disclose literally; the arbiter is a third reader; the G4 row
  needs real advisor use). Deferred: the real-model provider fields stay
  unnamed, so `LC-P3-06` cannot start. Frozen from live measurement on the
  machine the owner named as the trial machine: Windows 11 Pro 26H2
  (build 26300) and Microsoft Office 2010 (14.0.7252.5000), verified via
  App Paths, the WOW6432Node InstallRoot and the ProgID. Reaffirmed: the
  desktop shell stays as scoped (`LC-P3-05`; signing deferred with W28) and
  the historical public-boundary entries stay untouched.
- The seven source gaps were ruled: Q76/Q81/Q86 recommendations adopted as
  owner decisions; Q86 and Q87 additionally received fresh owner segments;
  the project-workspace row closes by the owner's reverse-infer instruction
  (stem and options were preserved in the extraction with the selection
  recorded); Q77's per-layer rules and Q82's original remain open at their
  triggers. The in-tree traceability rows are unchanged until the drafted
  upgrade lands as its own batched commit on the owner's word.
- `docs/plans/MULTISOURCE-research-learning-plan.md` lands: the owner's
  research-event learning supplement (meeting audio, presentation,
  manuscript and paper as one project case; reviewed learning project-only
  by default; group publication behind advisor review and a separate
  sharing grant; a later phase for production ingestion). Its status
  sentences were aligned with this record before landing — the board is not
  open and nothing is dispatched.
- The §6 gap register gained a measured path-length row: the workspace
  atomic write names a 46-character temp file under a deep output layout;
  the 259/260-character Windows ceiling switch was reproduced with and
  without project code. The repair is an implementation-stage decision, not
  part of this proposal.
- The full-suite local recheck finished: 4964 passed, 1 failed, 14 skipped.
  The single failure was measured to the recheck run's own long
  `--basetemp` prefix — three green reruns at a short one, two red at a
  long one — not to these commits, and the witness ledger reported
  `LOST -- none`. These changes land as a third local documentation commit
  of the batch; no push, PR or CI run is authorised by them.

### LC-P3-00 board record and the WPS-primary baseline (2026-11-07)

- The board-opening decision record lands at
  [`docs/acceptance/LC-P3-00-board-opening-decisions.md`](docs/acceptance/LC-P3-00-board-opening-decisions.md)
  with the traceability status upgrades in the same commit: five of the
  seven recorded source gaps close by the owner's rulings of the day
  (recommendations adopted for Q76/Q81/Q86, fresh owner segments for Q86
  and Q87, the project-workspace row closed under the owner's
  reverse-infer instruction from preserved stems and options), while Q77
  and Q82 — for which nothing survived to reconstruct — stay unresolved
  at their triggers. The ticket numbering is adopted; adoption is not
  dispatch.
- The DOCX host baseline is corrected the same day, after the owner asked
  whether WPS was present: this machine carries WPS Office 12.1.0.29690
  (App Paths for wps/et/wpp, ProgIDs `KWPS.Document` and
  `KWPS.Application`) alongside Microsoft Office 2010. The owner ruled
  WPS the primary acceptance host, Word 2010 the compatibility
  reference; the §4 reopen rows and `LC-P3-02` are judged accordingly.
  The entry above naming Word 2010 alone stands as the dated text of its
  moment; this entry is the correction.
- The write-seam path-length row remains registered in §6 for the
  implementation batch, reaffirmed by the owner. No dispatch, no push,
  no PR, no CI run.

### Repository map re-anchored (2026-11-07)

- The current index is re-measured from the tracked tree: 733 files against
  the 727 of the 2026-11-06 scan. The six files since are the map itself and
  five Phase 3 planning and decision records; Markdown is the only class
  that moved, from 163 to 169. The 199 Python test files, 3,419 declared
  test functions, 38 fixtures and zero exact-byte duplicate groups were
  re-measured and are unchanged.
- `docs/plans/` now names the execution plan and the multisource supplement;
  `docs/acceptance/` now names dated owner decision records as a class.
  This is a current-pointer correction, not a rewrite of a dated snapshot.
  No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Current pointers re-anchored (2026-11-08)

- A read-only freshness scan of the current pointers found seven live claims
  that lagged the tree, and all seven are corrected here. The handoff and the
  roadmap no longer say `main` and `origin/main` are aligned at the tidy
  delivery's merge, and no longer describe the Phase 3 planning proposal as a
  later, separate delivery: that proposal has been delivered, and `main` now
  sits ahead of `origin/main` by the batched local documentation commits,
  unpushed and un-pull-requested by the owner's choice. The pointer labels
  above the corrected paragraphs are re-read to 2026-11-08.
- The roadmap's status line no longer says no board is open. `LC-P3-00`
  opened the board record; it authorises no implementation and dispatches
  nothing, which is what the rest of that line continues to say.
- `CONTRIBUTING.md` said six shards per platform, and that a push therefore
  starts twelve Python jobs. The workflow's matrix is the authority —
  `shard: [0, 1, 2, 3, 4]` — so the rule now says five shards and ten
  python jobs, matching `CLAUDE.md`, `.github/CI.md` and the repository
  map, all of which already said five.
- A further lag surfaced after the scan, from measuring the two things it
  had to leave open: the roadmap's live position stated
  `tests/test_no_reference_leakage.py` as `99 tests`, where `--collect-only`
  on this tree reports 110. The count is dropped rather than updated, because
  a collected number moves with every witness added and a live position is
  not where a run's number belongs; the figure stays in the dated records
  that measured it, where it is true of that commit. The other open item
  resolved the same way: `tests/test_ci_shard_coverage.py` passes 16 nodes
  here, since a change only forces a re-measurement when it could unbalance
  the partition.
- A post-repair re-scan found two further live lags, both corrected in the
  same batch. The changelog's own account of the shard rule used the test
  runner's name where `CONTRIBUTING.md` and `CLAUDE.md` say "ten python
  jobs"; the quotation — not the arithmetic — is corrected. The LC-P1-11
  and LC-P1-12 task breakdown's status line said four decisions in §1.4
  where the same file's §1.4 names five and the two other live pointers
  already say five; it now says five. The re-scan's third claim, that the
  A1/A6 labels have no in-tree definition, was refuted by `LC-P3-00` §7,
  which defines them, and nothing was changed for it.
- No merge identifier and no runner tally is written into these pointers: the
  A1/A6 ruling of 2026-11-07 keeps post-merge CI evidence operator-side. No
  dated snapshot is rewritten — one pre-existing malformed table row in the
  roadmap's 2026-11-05 historical section is left as landed and recorded
  outside the repository instead. No product source, test, workflow or
  migration file is changed; no push, PR or CI run is authorised.

### C4–C8 wording corrections (2026-11-08)

- The five wording and coverage judgements the freshness scan left to the
  owner are applied. `docs/README.md`'s current-phase row is dated
  (2026-11-07; re-read 2026-11-08) and no longer carries the batch ordinal;
  the same ordinal is removed from `docs/ROADMAP.md` and
  `docs/handoff/CURRENT.md`.
- The English and Chinese README banners now say the Phase 3 board is open
  (`LC-P3-00`, decisions of 2026-11-07), that implementation has not started,
  that no ticket is dispatched and no delivery is authorised, and point at
  the roadmap's current position.
- `docs/handoff/CURRENT.md` says "at the local commit of that date" instead
  of "at this local commit", so the 2026-11-06 WSL measurement no longer
  reads as a claim about the current tip.
- `CONTRIBUTING.md` no longer calls eleven commands "the README's command
  table": it names the ten fenced commands together with the
  `uv run labcairn --help` line as the eleven `VERIFIED_COMMANDS` entries.
- The upstream clone count paragraph now says five cloned projects, six
  clone directories (`paper-qa` is cloned twice), 139 files re-walked on
  2026-11-08, and three of the five projects ship 21, 22 and 26 `SKILL.md`
  files. The same correction is carried in `docs/UPSTREAM_REFERENCES.md`
  and `docs/REVIEW-DOSSIER.md`; the "22–26" range was wrong at 21.
- No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Eleventh-commit audit follow-ups (2026-11-08)

- The independent audit of `8aaea7b` found one live lag and two wording
  tails, all corrected here. `docs/UPSTREAM_REFERENCES.md` now says
  `Updated: 2026-11-08` and dates the 139-file walk in the sentence that
  carries it; `CONTRIBUTING.md` drops a redundant "each"; and the upstream
  checklist now says five cloned projects rather than five clones. No
  product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### P2-AMD-01 §10.5 pointer annotated (2026-11-08)

- `docs/plans/P2-AMD-01-provider-and-data-options.md` now says, in both
  places where it cites "the adjustment's §10.5", that §10.5 is the
  owner-side P2-AMD-01 adjustment of 2026-10-30 and that its four decisions
  are transcribed in `P2-AMD-01-impact-matrix.md` §5. The reference was
  correct but unnamed; the annotation makes the external owner-side section
  and the in-tree transcription distinguishable. No product source, test,
  workflow or migration file is changed; no push, PR or CI run is
  authorised.

### Rescan and rendering fixes (2026-11-08)

- The 13-commit live-pointer re-scan found six live lags. The mechanical
  ones are corrected here: `CONTRIBUTING.md` names the in-repo
  `scripts/witness_ledger.py`; `docs/ROADMAP.md` uses "at the local commit
  of that date" and limits its Phase 3 authorisation sentence to the
  2026-11-05 snapshot; the roadmap's current-direction label is dated
  2026-11-07; the LC-P1-11/12 task breakdown says "was then six shards".
- `README.md` and `README.zh-CN.md` no longer claim the two Chinese texts
  are identical; the standalone Chinese document is still the independent
  translation.
- `.github/CI.md`'s Ubuntu slow-file section is dated 2026-11-02 and its
  old anchor is described as "then the commit recorded" rather than as the
  current one.
- The merge-authority rule is made consistent: the producer-never-merges
  sentence in `docs/README.md` and `CONTRIBUTING.md` is marked historical
  (through 2026-10-24), and the executing-agent rule in `docs/README.md`
  remains current.
- `docs/ROADMAP.md`'s 2026-11-05 historical row is rejoined onto one
  physical line (content unchanged), because the seven-line form rendered
  as a broken table row.
- No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Phase 3 G1 work orders issued (2026-11-08)

- [`docs/plans/PHASE_3-work-orders.md`](docs/plans/PHASE_3-work-orders.md) is the
  Phase 3 board's first work-order file: the official G1 work orders for
  **`LC-P3-01`** (real-browser baseline) and **`LC-P3-02`** (dual-host DOCX
  fidelity), written from the owner-approved preparation package. Both board
  rows read **`NOT STARTED`**. No implementation has begun, no window was
  opened, no witness ran, no real browser and no desktop host was started, and
  no Phase 3 gate is claimed closed.
- The owner's decisions of 2026-11-08 are recorded with them, each with where it
  binds: **Playwright** with the system-browser channel where one exists; **COM
  and ProgID automation not allowed**, so the WPS and Office reopen checks are
  human checklist steps with recorded evidence; the **real advisor sample after**
  the synthetic and substitute-first work, held as a named gap until it arrives;
  the **§4 checklist split** — `LC-P3-01` carries the real-browser baseline and
  the dual-host reopen checks, `LC-P3-02` the DOCX revision loop and the
  real-sample half; the **provider's seven fields after G1**, so `LC-P3-06` stays
  `BLOCKED`; the **write-seam path-length (MAX_PATH) repair rides this batch**;
  and **Q77 and Q82 stay at their triggers**.
- The file names the gate-label collision the tree needs: Phase 3's `G0` … `G4`
  are not Phase 1's five closed gates, and a row that says "G1" there means
  Phase 3 G1.
- Two items the preparation draft carried were corrected against this tree rather
  than copied. The "never `EventSource`" sentence belongs to
  `docs/THREAT-MODEL.md` **§6.2**, not §6.1; and the draft's raw-Windows
  long-path direction did not reproduce in its own freshness review, so the seam
  is stated through `src/labcairn/security/paths.py`'s deliberate refusal rather
  than as an errno.
- The current pointers move in the same commit: `docs/ROADMAP.md`,
  `docs/handoff/CURRENT.md`, `docs/README.md` and `docs/REPOSITORY-MAP.md`.
  `docs/README.md`'s status line no longer says that no work order exists, and
  the roadmap's `2026-11-07` direction row is now an earlier dated row.
- No product source, test, workflow or migration file is changed; no push, PR or
  CI run is authorised.

### G1 work-order audit corrections (2026-11-08)

- The independent audit of the G1 work orders found three structural gaps and
  two environment-fact errors. The work orders now name the commander as the
  owner of `.github/ci-shards.json` and `tests/evaluation/manifest.py` at merge
  (windows report their entries instead of editing those files), state that
  the shard-balance witness is expected red on `windows-latest` until the
  batch's own runner run supplies the costs, require a browser witness to skip
  with a named reason when Playwright or a system browser is absent, and name
  the project owner as the human-checklist performer.
- The Chinese README status line now matches the English one: the two G1 work
  orders are issued and both read `NOT STARTED`.
- The operator-side environment preparation report records the corrected facts:
  `PLAYWRIGHT_BROWSERS_PATH` is User-scope only, the WPS App Paths read uses
  `HKCU`, and the project's uv cache is `E:\LabCairn\.local\uv-cache`.
- No product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### G1 work-order NOTE fixes (2026-11-08)

- The remaining G1 work-order audit NOTEs were triaged. The §4 checklist split
  is now labelled a re-decision, not a confirmation; a new product dependency
  is an owner decision (a window reports package, version, licence and
  lockfile change and does not edit the lockfiles); and the §4.8
  version-switch claim is recorded as a named gap — the workbench has no
  version-control surface, so task selection is what is witnessed. The
  baseline record and the §8 gap table carry the same statement.
- The operator-side environment preparation report reconciles the uv cache
  path with the project cache (`E:\LabCairn\.local\uv-cache`).
- The merge-time items (#6/#9/#11) and the dated notes (#1/#8) remain as the
  triage lists them.
- No product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### Phase 3 G1 batch: LC-P3-01, the write seam and LC-P3-02 land locally (2026-11-08)

- `LC-P3-01`'s real-browser baseline merged locally; its row moved to
  `IN PROGRESS` in the merge commit and its record is
  [`docs/acceptance/LC-P3-01-browser-baseline.md`](docs/acceptance/LC-P3-01-browser-baseline.md).
- The write seam's path-length repair (the MAX_PATH batch item, §2 decision 6)
  merged locally, with its witness reading the product's own naming function.
- `LC-P3-02`'s DOCX editing seam merged locally: `src/labcairn/editing/`, the
  substitute corpus, the four test files and the helper
  `tests/evaluation_docx_edit_fidelity.py`; the editing ADR is
  [`docs/adr/ADR-0021-manuscript-editing-rewrite.md`](docs/adr/ADR-0021-manuscript-editing-rewrite.md)
  (`proposed`, adoption provisional), and the two dated records are
  [`docs/acceptance/LC-P3-02-support-matrix.md`](docs/acceptance/LC-P3-02-support-matrix.md)
  and [`docs/acceptance/LC-P3-02-substitute-run-2026-11-08.md`](docs/acceptance/LC-P3-02-substitute-run-2026-11-08.md).
  Both G1 rows read `IN PROGRESS`, and the live pointers moved in the same commit.
- What remains open: the §4.9 human dual-host reopen checklist (`NOT RUN` in both
  records), the real advisor sample (§5.9), the ADR's final adoption, and the
  runner-measured shard costs — locally `test_the_shards_are_balanced` and
  `test_the_recorded_costs_cover_every_test_file` are red by expectation, not by
  defect.
- No `PASS`, no gate closed, no ADR adopted, no push, pull request or CI run.

**Added**

- **The manuscript read ceiling is 96 MB, raised from 64 MB.** The third
  pilot's late drafts are 71.4 MB — full-resolution figures embedded — and
  the 64 MB ceiling refused **seven versions of one real manuscript**,
  including its final English version, at ingestion. The four ceilings
  (`feedback`, `replies`, `revisions`, and the read-only source port's
  default) carry the same number deliberately, and a file is still
  **measured before it is read**: the ceiling is a measurement, not a
  caller's claim.

- **Two acceptance records now name the witness the mutation actually
  reddens.** LC-P2-10's M22 row names
  `test_every_item_has_two_annotations_and_a_resolution` for the
  deleted-count form; the completion-check witness it used to name reddens
  only under the *mis*-counting form (`!= 1`), because this tree's manifest
  is finished and that witness takes its finished branch. LC-P2-16's
  mutation-8 row now says the fixed project must be one the store **holds**:
  a nonexistent id is refused by the same 403 as the absent caller id and
  leaves the witness green. Both forms were re-applied and measured before
  the records were corrected; both review files carry a resolved note.

- **Three support modules no longer wear the `test_*` glob.**
  `tests/test_store_support.py`, `tests/test_recovery_support.py` and
  `tests/test_skill_support.py` were shared fixture modules — 47 test files
  import them — that pytest collected and found no case in, on every shard
  of both platforms. They are now `tests/store_support.py`,
  `tests/recovery_support.py` and `tests/skill_support.py`; their shard and
  cost entries and their evaluation-manifest rows are gone, and the
  collected-nothing mechanism keeps its witness through a synthetic
  selected-and-empty run. `python .github/make_ci_shards.py` re-balanced
  both partitions from the existing runner costs (Ubuntu 1.231, Windows
  1.000) without a CI run.

- **ADR-0006's outbound-consent bridge — a Phase 1 debt closed.** The
  provider layer can no longer send without a permission decision: an
  `OutboundConsent` port is a **required constructor argument**, and
  `send` calls it after the local pre-flights and **before the
  transport**, so an approval that is missing, pending, expired or
  already spent refuses the request with the wire never reached. The
  permission decision crosses the boundary **as a value, not as an
  import** — the two capability vocabularies stay disjoint (ADR-0006
  statement 1), and the approval's single use is spent only by a call
  that will actually be made. 8 witnesses; 5 self-reported mutations
  and 4 independent ones, all caught.
  [LC-P1-03 outbound bridge](docs/acceptance/LC-P1-03-outbound-bridge.md).

- **The blind evaluation's mechanical preparation (LC-P2-14).** Four
  pieces under `tests/evaluation/`: the protocol's five arms as data a
  configuration is measured against; a by-paper leak check that names
  every leak shape it knows (a paper on both sides, an entry with no
  side, an entry on the wrong side, a rule built on an evaluated paper,
  a side the checker does not know); an anonymous blind sheet that
  **refuses** a document carrying an arm key rather than cleaning it;
  and an exact paired sign test whose **not-significant verdict is a
  first-class outcome** — a small denominator is not significant by
  rule with no p-value computed, all-ties says "no evidence either
  way", and every significant row carries its denominator. 64
  witnesses; 47 mutations self-reported and all caught; 4 further
  mutations applied independently, all caught.
  [LC-P2-14 preparation](docs/acceptance/LC-P2-14-preparation.md).

- **Five acceptance records carry an independent review.** Every
  mutation in the reviewed records re-applied by a session that built
  none of them, every witness watched: LC-P2-02/07/09 hold;
  LC-P2-10/16 hold with notes. The reviews are records of the checking
  (`docs/acceptance/LC-P2-{02,07,09,10,16}-review.md`), not of new
  work.

- **The P1 baseline is frozen.** The phase's exit gate — *"measured
  capability gain against a frozen P1 baseline"* — had no denominator:
  the harness could read a baseline document and nothing supplied one.
  The baseline is now committed at
  [`docs/acceptance/LC-P2-00-baseline.json`](docs/acceptance/LC-P2-00-baseline.json),
  measured on `main` at `81babd5` (Windows 11, offline): five gate
  classes, four measured metrics, the real-provider smoke honestly
  recorded as NOT RUN, and `model: ""` rather than an invented name.
  **A run on the same tree compares on all six conditions**, a doctored
  run and a doctored baseline are each refused by name, and the record
  says what the numbers do not establish.
  [LC-P2-00 baseline](docs/acceptance/LC-P2-00-baseline.md).

- **The settlement over a reply — the peer-review loop's judgement
  half.** The reply was a record of what was said and nothing judged it;
  `reply_settlements` (migration `0020`) and `settle_reply` add the
  judgement. **A response whose claimed experiment the manuscript does
  not contain is refused or held, by name**; an unjudged reply stays on
  the unsettled listing; the change is placed in the manuscript or the
  settlement says it could not be; and a disagreement between the
  chain's judgement and a settlement is shown as **two sides**, not
  resolved by recency. A model may put a settlement forward and may not
  decide one.
  [LC-P2-09 acceptance](docs/acceptance/LC-P2-09-acceptance.md) §10.

- **The reader reports one tracked change once.** A paragraph whose run
  carries a drawing — Word's `mc:AlternateContent`, a `Choice` and a
  `Fallback` each wrapping a text box — had its inner revisions reported
  a second time by the outer paragraph's walk: **243 events where the
  file holds 239 addresses**. The walk now reports a revision only from
  the nearest containing paragraph, and **the corpus carries the shape**
  (fixture 30), so the corpus-wide witnesses catch the defect by
  construction. Verified on the real file both ways: 243 before, 239
  after; the pilot's chain was checked unpolluted.
  [LC-P2-07 fidelity baseline](docs/acceptance/LC-P2-07-fidelity-baseline.md).

- **The mentor's own material, in the product — and the chain's four
  rings.** The second corpus is a second paper with a second advisor, and
  the two of them are in the product as two pilot projects: **twenty
  versions, eighty comments, 1528 recorded changes** and the owner's own
  judgements on ten of the correspondences the operator put forward. **The
  chain's second ring holds one row per change a manuscript's file
  records** — `edit_actions`, 1439 of them, because the other 89 are the
  marks an operation at a point leaves behind and **the chain records
  changes and not marks** — and **the third ring holds the
  correspondences and their judgements**: the operation that puts a link
  forward **has no state to decide it with**, because the third ring is
  filled by a person or a rule. **The memory serves one rule of sixteen
  and reports the other fifteen**, and the reason it serves one is the
  material's own answer: of the mentor's forty-six comments on the first
  paper, the ones a later version really answered are few. **A memory that
  served all sixteen would be serving rules the chain cannot show to have
  been applied** — which is the difference between absorbing a mentor's
  judgement and arranging it. The owner ruled twice on what the material
  forced: **a judgement on the chain is a fact** (a second judgement does
  not undo the first, and a wrong judgement is corrected on the rule), and
  **the retrieval's threshold does not move**.
  [LC-P2-09 acceptance](docs/acceptance/LC-P2-09-acceptance.md) ·
  [the second corpus](docs/acceptance/second-corpus-absorption.md).

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

- **The phase's work orders, folded into one ticket.**
  [`docs/plans/PHASE_2-work-orders.md`](docs/plans/PHASE_2-work-orders.md)
  merges the phase's two work-order lists into one ticket: **what is built,
  where each piece's record is, and the six pieces that are left** — the
  frozen P1 baseline the exit gate's denominator needs and does not have,
  the blind evaluation that is written and not run, the peer-review loop's
  judgement half, citation identity, retrieval quality beyond three papers,
  and the competitor comparison whose precondition has now been met. The two
  drafts it came from stay in the tree as the record of how the phase was
  planned, and every acceptance clause and file-ownership map in them is
  still the one its piece was built under.

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
