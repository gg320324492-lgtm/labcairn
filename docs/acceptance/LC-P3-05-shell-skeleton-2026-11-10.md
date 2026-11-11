# LC-P3-05 — the Electron shell skeleton: dev-build closure, the drain rule, and what is still open

Anchors, printed live while this record was written (every value here was
produced by the command named under it; none is carried from another record):

| what | value |
|---|---|
| branch | `claude/awesome-nash-b42e44` (worktree `awesome-nash-b42e44`) |
| base commit (local `main` at dispatch) | `a1174ae2ff91263ea593f2596743e5b650ff0976` |
| commits this record describes | listed commit by commit in §1 |
| Electron (installed, `shell/node_modules/electron/package.json`) | 45.2.3 |
| Node running the rehearsals | v24.16.0 |
| Python / fastapi / uvicorn / starlette / anyio / pydantic (`.venv`) | 3.12.13 / 0.151.0 / 0.54.0 / 1.8.0 / 4.15.1 / 2.14.1 |
| platform | Windows 11 Pro, one machine, one run per measurement unless a row says otherwise |
| run type | **locally measured, dev build**. No CI run was started, no pull request was opened, nothing was pushed (`CLAUDE.md`; `docs/plans/PHASE_3-work-orders.md` §3 rule 7) |

**What this record is.** It is the implementation stage's first dated record for
`LC-P3-05`: the shell skeleton described by
[`LC-P3-05-shell-implementation-plan.md`](../plans/LC-P3-05-shell-implementation-plan.md)
steps T02, T03 and T07, run end to end on this machine. It claims a **skeleton**,
not a ticket status: the board row for `LC-P3-05` is **not moved here**, and no
acceptance criterion is claimed as fully held (§8 names which are partial and
which are untouched).

**Current pointer (2026-11-10, later batch).** §1–§8 above are the skeleton
batch's own dated evidence and are left as written. A later batch on branch
`claude/sweet-varahamihira-7d5899` measured its code at
`6c0007e547711c0637edfaf518eaca70b33205c5` and was delivered at
`6a53644eff8ed1b2edd6c0bb251a6c00689b1ef5`. The delivery commit is
documentation-only; the measured tree is unchanged. The batch closed the
T05 live-401 half, T06's three unwitnessed lifecycle arms, AC-7 and AC-8
(static halves only), and added a dated measurement in §10. **The gaps that
remain are named in §10.4**: the signed installer and T09 clean-Windows drill,
AC-6, AC-2's Windows graceful-ask arm (owner's decision: leave as a measured
gap), the second-instance focus half, Arm C in full, and the `file://`
counter-mutation at the pure layer. §8 below is the skeleton batch's dated
`not implemented` list, not a current pointer; §10.4 is the current state,
where T08's minimal unsigned packaging configuration has landed. The board
row is still not moved.

**Independent review, 2026-11-10.** A read-only independent critique of the
eight-commit branch found claims that the tree does not carry, including
shell witnesses that no gate or ledger watches, two comments naming a
witness file that does not exist, an unwitnessed post-readiness pipe-error
arm, and no-orphan rehearsals that ignore `tasklist`'s exit status. The
critique records the drain-log location/ceiling, redirect handling, shape
margins and counter-mutation harness reproducibility as open limits. They
are named gaps here, not passing rows; the full findings and their evidence
addresses stay in the external report
`E:/labcairn-local/phase3-g1-evidence/shell-skeleton-independent-critique-2026-11-10.md`.

**Where the rehearsal stands, stated plainly.** The two runs in §4 and §5 are
`LC-P3-05`'s own dev-build verification of a shell this window wrote. They are
not a §12/§13 mapping dry-run, and they are **not entered in any execution plan
§4 row** — the owner's ruling of 2026-11-10 in `PHASE_3-work-orders.md` §12
("A dev-build rehearsal is not authorised, and a rehearsal may never be entered
in an execution plan §4 row") is about the `LC-P3-07`/`LC-P3-08` mapping
rehearsal, and this record keeps them apart rather than borrowing the term.

---

## 1. What was built, commit by commit

| commit | subject |
|---|---|
| `f5523ec0f96f381dd89b22d4db5b5a0d3dde0ba1` | the shell: `shell/` with the supervisor, window, preload, config, main |
| `00582e36ce18082ef3da83c1cda0b3fa9e94e2be` | the drain witness and the closure rehearsal |
| `7b6b7b18eebb6fd38ed67fcfd03b46a310590678` | the rehearsal picks its own debug port and cleans up after itself |
| `d6dab39b97fb6c8a34a6747e8b6de2620e365cfa` | the baseline witnessed inside a real window; refusals printed |
| `fe7bb122dfb965cc329bd3e4fbfc9e5a05975dea` | unused capacity fixtures deleted; diagnostic fixture paths fixed |
| `6203aafb9b2745f21bf7bc058a10f6d59be9f565` | the dev-mode rehearsal against the real Vite arrangement; shared window reader |
| `5651744` | the allow-list read back from the service in arm C |
| `f387a55` | this record, and the CHANGELOG entry |
| `0a2841f001d750ccc9932c2f8c31e43047b762fa` | the tree kept English: the socket error named by its code (§9) |

The table lists the commits the **work** consists of. The commits that amend this
record after it exists are not in it, and cannot be: a list of this record's own
commits would have to include the commit that adds the list. §9's two-run
comparison arrived that way.

**Files, and the ownership line.** Everything lands in a new top-level `shell/`
beside `web/`. **No file under `src/labcairn/` was touched** — `git diff
a1174ae..HEAD --stat` lists `shell/` and this record only. The plan proposed
`desktop/` and named it "decided in T01"; this window's dispatch named `shell/`,
so the directory is `shell/` and the difference is recorded here rather than
silently resolved. The `web/` tree is unmodified: the dev rehearsal runs Vite
through `shell/scripts/vite.dev-rehearsal.config.mjs`, which imports
`web/vite.config.ts` and overrides one number (§5).

**A dependency was added, and it needs the owner's signature.**
`shell/package.json` pins `electron` **45.2.3** (MIT), the version the selection
record measured
([`LC-P3-05-selection-measurement-2026-11-10.md`](LC-P3-05-selection-measurement-2026-11-10.md)
§3). `shell/pnpm-lock.yaml` is committed so the change can be read rather than
described. Under §0 rule 4 the *approval* is the owner's: the package, version,
licence and lockfile are reported here, and this window did not edit
`pyproject.toml`, `uv.lock`, `web/package.json` or `web/pnpm-lock.yaml`. The
binary arrives at first `require` as the selection record measured — 357 MB
extracted `dist/` here as well, same order of cost.

---

## 2. The drain rule as code

`shell/src/service-supervisor.mjs` implements the plan's §3 requirements 1–6:

| requirement | where it is |
|---|---|
| both streams captured, never `inherit`, never a hidden default | `stdio: ['ignore', 'pipe', 'pipe']` in `spawnChild`, the one spawn path |
| readers attached at spawn | `child.stdout.on('data')` and `child.stderr.on('data')` before the child can write |
| a bounded log file outside the repository | `LogSink`, `E:\labcairn-local\shell-logs\service.log`, ceiling `LOG_CEILING_BYTES` 4 MiB, truncation recorded as dropped bytes |
| a reader error is surfaced, not swallowed | the `pipeErrors` list; `start()` re-raises it and stops the child |
| no orphan after the shell | `stop()` asks, waits `STOP_GRACE_MS`, then forces the group, and confirms the exit — a child that survives the force is an exception |
| its own process group on Windows | `detached: true` with `windowsHide: true`, the group addressed by pid |

The test-only switches the witness needs (`drain`, `commandOverride`,
`argsOverride`, `readiness`) are parameters of `start()`. `main.mjs` passes none
of them and `config.mjs` reads no environment variable for them.

---

## 3. The dose had to be measured, and the measurement is the finding

The plan's Arm A says the dose must exceed the pipe's **measured** capacity and
that 4,096 is "this machine's number, not a constant". The first run of the
witness carried 4,096 + margin, and **the undrained arm answered the dose** —
`spawn`'s pipe is much larger than an anonymous pipe, so the arm that exists to
prove a stall stalled nothing, and the drained arm would have proven nothing
either. Three measurements, all on this machine on 2026-11-10, say how large:

| arrangement | measured |
|---|---|
| an anonymous `os.pipe()` (the O6 record's §4 measurement) | **4,096** bytes |
| the child's own fd 1, non-blocking `os.write`, in the `spawn` arrangement (`shell/scripts/diag6.mjs`) | **88,064** bytes |
| the same `spawn` pipe, written in the fixture's blocking buffered style (`shell/scripts/diag2.mjs`) | **114,688 fits / 131,072 stalls** |
| the ladder the witness now runs (`PROBE_TIMEOUT_MS` 4 s, 100 ms poll) | `8192:fits 16384:fits 32768:fits 65536:fits 131072:stalls` |

The witness therefore sizes its dose from a ladder it runs itself
(`measureStallThreshold()`), and asserts `dose > threshold` before either arm
executes — the plan's "a dose too small to overflow fails the test rather than
passing quietly". At the head commit the measured run reports:

```
measured stall ladder: 8192:fits 16384:fits 32768:fits 65536:fits 131072:stalls
✔ the dose (139264) exceeds the spawn-pipe stall threshold measured here (131072)
```

**Why the writer child is Python.** The stall needs a *synchronous blocking*
write. Node's `process.stdout` buffers pipe writes asynchronously and its event
loop keeps serving, so a Node writer shrugs off a full pipe and the undrained
arm proves nothing. Python's `sys.stdout.flush()` blocks in the write when the
pipe is full and parks the single-threaded `HTTPServer` handler — which is the
shape O6 measured (the service wrote its traceback into its own output and its
loop served nothing). `shell/test/fixtures/writer_child.py` says this in its own
docstring so the choice is not mistaken for an accident.

---

## 4. The drain witness (AC-3): three arms, one counter-mutation

`node --test "shell/test/drain-witness.test.mjs"` at `5651744`, status read
from the command (`STATUS=0`):

```
✔ the dose (139264) exceeds the spawn-pipe stall threshold measured here (131072)
✔ drained arm: the same child and dose answer before, during and after
✔ undrained arm: the same child and the same dose reproduce the stall
✔ the real service answers the production path with the readers attached
✔ a foreign listener on the chosen port is a refusal, not a page to load
ℹ tests 5 / pass 5 / fail 0
```

- **Drained arm.** Same child, same 139,264-byte dose, `drain: true`: the
  pre-dose read, the dose request itself and three post-dose reads all answer,
  and `sink.writtenBytes >= dose` — the bytes are *in* the bounded log, so the
  arrangement kept the bytes as well as the pipe moving.
- **Undrained arm.** Same child, same dose, `drain: false`: the dose request
  times out, an ordinary read times out, `child.exitCode === null &&
  child.signalCode === null` (it is *parked*, not dead), and
  `sink.writtenBytes === 0` (it is the arm it claims to be). This arm is the
  control that makes the drained arm mean something.
- **Real service, no injection.** `labcairn serve` in a scratch workspace
  outside the repository (`E:\labcairn-local\shell-test-tmp\arm-c-ws-…`),
  started by the production command with the production readiness read:
  `/health`, `/tasks` and `/openapi.json` all answer 200, `ServiceStarting.origins`
  and `GET /health`'s origins both name exactly the service's own origin plus the
  two development spellings (AC-1's unwidened-list half, read back from the
  service), and the drained log is non-empty.
- **Occupancy arm.** A deliberate `node` listener on the chosen port; the
  supervisor rejects with "the service child did not start", and the assertion
  that the port still answers `foreign` is made *before* the foreign listener is
  stopped — a refusal must not become a takeover.

**Counter-mutation, run on a committed tree (`git status --porcelain` was 0
lines first).** The production reader was switched off with
`if (false && drain)` in `spawnChild`, then the witness re-run:

```
✖ drained arm: … the 139264-byte dose stalled although the pipes are drained
✖ the real service answers the production path with the readers attached:
  the production path drained nothing into the log
STATUS=1
```

Reverted with `git checkout --` (0 lines dirty again) and re-run:
`STATUS=0`, 5 pass. The mutation took effect, so it is evidence — the drained
arm is red when the reader is gone.

**Second counter-mutation (AC-1's `file://` arm).** The packaged page URL in
`main.mjs` was swapped to a `file://` page, and the rehearsal went red on the
first origin assertion:

```
act 1 connected state: {"location":"file://", …}
AssertionError: the loaded page is not on the service origin
STATUS=1
```

Reverted; the rehearsal is green again. The `file://` swap is caught.

---

## 5. The closure, both modes, end to end

### 5.1 Packaged-shaped closure (`shell/scripts/rehearse-loop.mjs`), three acts

The service carries the built bundle (`--static-dir web/dist`), so page and API
share the service's own origin and no dev switch is involved. `STATUS=0`.

- **Act 1 — the service dies, the window says so.** `loaded
  http://127.0.0.1:<port>/`; read from inside the page over CDP, `location`
  equals `ServiceStarting.origin`; the page's own `fetch('/health')` answers 200;
  the strip and the bridge both say `connected`. The service child is then force
  -killed from outside the shell, and the same window shows:
  `"stripStatus":"disconnected"`, `"bridgeStatus":"disconnected"`, label
  `LabCairn — disconnected: the service stopped`. No respawn: the child's `exit`
  handler only reports.
- **Act 2 — the window closes, the service follows.** The window is closed from
  outside through CDP; the shell exits **0**, the service pid is absent from the
  process table (`tasklist /FI "PID eq <pid>"`), and nothing listens on the port.
- **Act 3 — the baseline inside the window.**

  ```
  act 3 renderer surface: {"hasProcess":false,"hasRequire":false,"hasIpcRenderer":false,
   "hasModule":false,"bridgeKeys":["status"],"bridgeStatusType":"function",
   "bridgeStringValues":[]}
  refused window-open http://labcairn.example.invalid/escape
  refused will-navigate http://labcairn.example.invalid/escape
  act 3 navigation refused: …; the page stayed on http://127.0.0.1:<port>
  ```

  No `process`, no `require`, no `ipcRenderer`, no `module` in the renderer; the
  bridge's enumerable surface is exactly `['status']` and carries no string value
  the page could read as data. `window.open` to a foreign origin returns no
  window; a `location.assign` to one is prevented with the page staying on the
  service origin. Each refusal is **printed** by the main process, so the
  rehearsal asserts the refusal rather than inferring it from an absence.

### 5.2 Dev-mode closure against the real Vite arrangement (`rehearse-dev-vite.mjs`)

`STATUS=0`. `web/vite.config.ts` fixes its proxy target at `http://127.0.0.1:8000`,
and port 8000 on this machine belongs to `com.docker.backend.exe` (`netstat
-ano` LISTENING, PID 33364, measured 2026-11-10). The rehearsal neither
displaces a listener it does not own nor edits another window's file: it starts
Vite with `shell/scripts/vite.dev-rehearsal.config.mjs`, which **imports** the
real config, spreads it, and overrides the target port and nothing else. The
run prints what it inherited:

```
inherited proxy: mounted at /api, target http://127.0.0.1:8000 -> http://127.0.0.1:58316,
 changeOrigin=false, host=127.0.0.1, port=5173, strictPort=true
```

The config **refuses to load** if `web/vite.config.ts` ever stops leaving
`changeOrigin` at `false` or the proxy `headers` empty, so a widening of the
product's own proxy breaks this rehearsal loudly. The mount used for the page's
fetch comes from the inherited proxy's own key, not a second copy of
`DEV_API_BASE`.

```
loaded http://127.0.0.1:5173; service origin http://127.0.0.1:58316; service pid 60636
dev connected state: {"location":"http://127.0.0.1:5173","stripStatus":"connected", …}
dev page reached /api/health: 200; the service reports port 58316
dev disconnected state: {"location":"http://127.0.0.1:5173","stripStatus":"disconnected",
 "stripLabel":"LabCairn — disconnected: the service stopped", …}
dev closure result: Vite page + proxied API -> connected -> service killed -> disconnected -> clean exit, port free
```

**Act 2 (same environment, dev switch off)** asserts from inside the page that
no dev origin was loaded and the page is the service origin — compared **by
origin, not by spelling**, which is also what catches a `file://` load (origin
`"null"`) and a dev page under any spelling.

**The name of what is measured here.** The dev page is served by Vite from
`http://127.0.0.1:5173`, and the service answers to that origin because
`DEVELOPMENT_ORIGINS` already names its two spellings
(`src/labcairn/cli/commands.py:2110`), not because the shell asked. The shell
passed no `--origin`: `ServiceStarting.origins` read back in §4's arm C shows
exactly the service's own origin plus those two.

---

## 6. Two things the measurements corrected in the plan's own assumptions

1. **The capacity the witness must beat is the `spawn` pipe, not `os.pipe()`.**
   §3's witness design names `_pipe_capacity` as the shape to copy and says 4,096
   is not a constant; the run showed the two numbers differ by a factor of ~27
   in this arrangement, and a witness sized from the smaller one stays green in
   both arms — exactly the failure the plan warns about.
2. **On Windows, Node's `child.kill()` does not deliver the G1 helper's signal.**
   `shell/scripts/diag6.mjs` ran every combination of the four spawn arrangements
   × `SIGBREAK` / `SIGTERM` / `SIGINT` against a Python child that installs
   handlers for all three. **No combination reached the handler**:

   ```
   (b) detached+windowsHide + kill(SIGBREAK): exit=null signal=SIGKILL exitedWithinGrace=true asked=true handler=no handler ran
   (b) windowsHide + kill(SIGTERM):          … handler=no handler ran
   (b) plain + kill(SIGINT):                 … handler=no handler ran
   ```

   (twelve rows, the same outcome). Node terminates rather than signalling on
   Windows, and console-control events do not reach a `windowsHide` child. The
   G1 Python helper's graceful ask (`send_signal(CTRL_BREAK_EVENT)` followed by
   `outcome.forced is False`) has no Node equivalent reached by this route.

   **What the witness therefore does and does not claim.** It asserts the child
   ends, the port releases and no pid survives — and it *prints* the outcome
   (`{"exitCode":null,"signal":"SIGKILL","forced":false,"askedWith":"SIGBREAK",
   "asked":true}`) without asserting `forced === false`. `forced: false` here
   means "the exit landed inside the grace window", not "the ask was the thing
   that worked"; the plan's graceful-ask assertion — AC-2's normal-close half —
   needs a stop mechanism this window did not find, and it is named as open in
   §8 rather than asserted.

Two smaller measurement-shaped fixes, recorded because a record that hides them
hides the reason the code looks the way it does: Vite's banner puts colour codes
*inside* the phrase being matched (`Local` + `ESC[22m` + `:`), so the rehearsal
strips the escape including the `\u001b` byte before matching; and `pnpm dev`
resolves to a `.cmd` that Node 24 refuses to spawn (`spawn EINVAL`), so the
rehearsal runs `web/node_modules/vite/bin/vite.js` with `process.execPath`.

---

## 7. Witness inventory at `5651744`

| surface | count | what it watches |
|---|---|---|
| `node --test "shell/test/*.test.mjs"` | **13 tests, 13 pass, 0 fail** (`STATUS=0`) | drain arms ×3 + occupancy (5); run-mode resolution and the packaged/dev difference (4); the `webPreferences` object, the allow-list's decisions, `file://`/custom-scheme refusal, the guards' attachments and their refusal log (4) |
| `rehearse-loop.mjs` | **24 assertions**, three acts | origin equality, same-origin `/health`, connected → disconnected, exit 0, no pid, port free, the four `typeof` refusals, the bridge surface, both navigation denials |
| `rehearse-dev-vite.mjs` | **28 assertions**, two acts | inherited-proxy settings, the dev URL only in dev, proxied `/api/health` naming the service port, the disconnection, no dev origin in a packaged-shaped run |
| counter-mutations | **2, both effective** | reader removal reddens the drained arm and arm C; the `file://` swap reddens the rehearsal |

`ruff check .` and `ruff format --check .` both exit 0 at this head (statuses
read from the commands). An earlier run of that same check was read through
`| tail` and reported success while ruff reported three errors — the failure
mode `CLAUDE.md` names, walked into and then corrected in the same window.

**No registration in `tests/`, `.github/ci-shards.json` or
`tests/evaluation/manifest.py` was needed and none was made:** every shell test
is a Node test under `shell/`, not a pytest file. `pyproject.toml`'s
`norecursedirs` keeps `web` out of collection and `shell/` holds no
`test_*.py`; the `tests/`-side witnesses this batch could have disturbed were
run and are reported in §9.

---

## 8. Named gaps — what is skeleton, what is untouched

**Not implemented (the plan's own later steps).**

- **T01's approval landed 2026-11-10.** The owner approved Electron 45.2.3 /
  MIT / `shell/pnpm-lock.yaml` (dialog of that date); the dependency is
  adopted, and the approval is recorded at the plan's §4.4. This paragraph
  was `outstanding` when the skeleton batch was written and was corrected
  by the conductor on the owner's word. `pyproject.toml`, `uv.lock` and the
  `web/` manifests remain untouched.
- **T05's preload/IPC half.** The preload shows a status strip and exposes one
  getter. The plan's AC-4 half — a *live* mutation request refused `401
  session_required` from inside the shell — is **not** implemented or witnessed;
  the token-reachability half is (§5.1 act 3).
- **T06's lifecycle arms.** Implemented but **not all witnessed**: the startup
  refusal diagnostic path (window on `about:blank` with the diagnostic) and the
  single-instance lock are in `main.mjs` with **no witness**; the main-process
  crash arm is hooked (`uncaughtException` / `unhandledRejection` → stop →
  exit) with **no witness**; the graceful-ask assertion is blocked on §6.2.
- **T08 (built bundle from the shell) and T09 (installer, clean-Windows drill,
  signing, support limits) are untouched.** AC-6 is untouched; signing stays
  behind `W28`.
- **AC-7 is not held yet.** The shell's only dependency is Electron (MIT), and
  nothing in `shell/` names a remote host, but no witness reads the shell's
  dependency set the way `web/src/api/bundle.test.ts` reads the bundle. AC-8's
  static COM/ProgID witness is likewise not written; nothing in `shell/` opens a
  COM, ProgID or UI-automation route.
- **Arm C in miniature, not in full.** The plan's full arm adds a token-carrying
  `POST /task/select` and a bounded burst of ordinary reads; the witness here
  does three guard-free reads.
- **No `file://`-swapping counter-mutation was run against the pure-layer guard
  tests** — the `file://` swap was run against the rehearsal (§4).

**Environment facts a later run needs.** Port 8000 belongs to Docker Desktop on
this machine; `python` on `PATH` here is 3.10.11 while the project's interpreter
is the `.venv`'s 3.12.13, so the shell's scripts resolve the interpreter and the
console script as a pair (`tests/workbench_serve_support.py`'s `console_script()`
rule) rather than from `PATH`. Scratch lives at `E:\labcairn-local\shell-scratch`
and `E:\labcairn-local\shell-test-tmp`; drained logs at `E:\labcairn-local\shell-logs`
— all outside the repository, no token value and no corpus text in any of them.

---

## 9. Repository-side checks run against this tree

Five repository witnesses that a new top-level directory could plausibly disturb
were run as a subset, twice, with `--basetemp` and
`TEMP`/`TMP`/`TMPDIR`/`MPLCONFIGDIR` outside the repository, `COLUMNS=200`, one
run at a time, and the status read from the command rather than a pipe:
`tests/test_readme_accuracy.py`, `tests/test_no_reference_leakage.py`,
`tests/test_ci_shard_coverage.py`, `tests/test_scaffolding.py`,
`tests/test_outsider_path.py`. The two runs differed in **one** thing — whether
`PYTHONPATH` pointed at this worktree's `src`.

| run | `PYTHONPATH` | result | failing set |
|---|---|---|---|
| injected | `<worktree>/src` | `PYTEST_STATUS=1` — 6 failed, 176 passed (247.03 s) | `test_no_reference_leakage::test_wheel_installs_clean_and_imports`; all four `test_outsider_path` tests; `test_no_reference_leakage::test_the_tree_carries_no_more_chinese_than_was_measured` |
| control | not set | `PYTEST_STATUS=1` — **1 failed, 181 passed** (159.44 s) | `test_scaffolding::test_core_resolves_inside_the_source_tree` |

**The two failure sets do not intersect, and that is the finding.** Per
`CLAUDE.md` (*compare the sets, not the counts*):

- **Five of the six are this window's run configuration, not the tree.** An
  injected `PYTHONPATH` leaks into the tests that build their own clean clone or
  clean-room virtualenv precisely so that they cannot be shadowed by the
  developer's checkout, and they refuse when it arrives anyway. Their own words:
  *"labcairn resolved to …worktrees\awesome-nash-b42e44\src\labcairn\__init__.py,
  outside the clean venv … The editable install of the working tree shadowed the
  wheel, so this assertion proved nothing"*, and *"[FAIL] the walk runs the
  clone's own code, not the developer's"*. All five are green in the control run.
- **The one control-run failure is the known worktree condition**, and it is the
  reason the injection exists in the first place: `labcairn.core resolved to
  E:\LabCairn\src\labcairn\core\__init__.py, outside
  E:\LabCairn\.claude\worktrees\awesome-nash-b42e44` — the in-process import
  reaches the main checkout without `PYTHONPATH`. So the two configurations each
  break the other's tests: **no single `PYTHONPATH` setting runs this subset
  green in a worktree.** What a later run needs is per-test scoping — the
  in-process importers want the worktree's `src`, the clone-and-clean-room
  witnesses must not inherit it — which is a repository-side arrangement this
  window does not own and does not change.
- **The Chinese-count witness caught a real defect of mine, and the fix is
  witnessed.** It named `shell/scripts/rehearse-loop.mjs`, where a comment quoted
  Windows' localised bind-refusal message in Chinese — against `CLAUDE.md`'s rule
  that everything landing in the tree is English. Commit `0a2841f` names the
  socket code (10048) in English instead, and that test **passes in the control
  run** (the control run was made after the fix, so the witness was watching the
  fixed tree).
- `test_readme_accuracy.py` and `test_ci_shard_coverage.py` passed in both runs:
  no README command was disturbed, and no test file entered a shard it should
  not — consistent with §7's point that this batch added no pytest file.

`ruff check .` and `ruff format --check .` exit 0 at this head (§7). No board row
moved, nothing was pushed, no pull request opened, no CI run started.

**What these five files are not.** The whole suite is of the order of five
thousand tests (`5176 tests collected in 22.44s` is what the outsider walk
printed, in the injected run's report), and this window ran a five-file subset
chosen for the witnesses a new top-level directory could plausibly disturb —
README command accuracy, reference/path leakage, shard coverage, the scaffolding
import, the outsider walk. **The whole suite was not run for this batch**, and
that is the honest shape of what §9 claims: five witnesses that could reasonably
have been broken were run, twice, and their results are reported with their
cause. A whole-suite pass is not claimed and was not measured here.

---

## 10. The 2026-11-10 follow-up batch: the named gaps that were closed, and those that remain

**This section is a later, dated addition**, written on branch
`claude/sweet-varahamihira-7d5899`. §1–§9 are the skeleton batch's evidence and
are left as written, including §8's `not implemented` wording: it was true of
that tree and is a historical fact about it. This section names what changed
after it. Nothing below moves the board row, opens a pull request, starts CI or
pushes a branch.

| what | value, printed live for this section |
|---|---|
| measured code head | `6c0007e547711c0637edfaf518eaca70b33205c5` |
| delivered branch head | `6a53644eff8ed1b2edd6c0bb251a6c00689b1ef5` (documentation-only eighth commit) |
| branch | `claude/sweet-varahamihira-7d5899` (worktree of the same name) |
| Node running the witnesses | `v24.16.0` |
| Electron | `45.2.3` (owner-approved 2026-11-10, unchanged) |
| platform | Windows 11 Pro, one machine; live rehearsals run one at a time |
| run type | **locally measured, dev build**. No CI run, no pull request, no push (`CLAUDE.md`; `PHASE_3-work-orders.md` §3 rule 7) |
| scratch | `E:\labcairn-local\tmp\lc-p305-shell` — outside the repository; no token value or corpus text in it |

### 10.1 What landed, commit by commit

| commit | subject |
|---|---|
| `58e71ea` | T05: the live 401 half-loop, in a real window and witnessed |
| `423c6a5` | T06: the three unwitnessed lifecycle arms get witnesses |
| `74a20f1` | fix the live-guard rehearsal's own grant pattern |
| `38062a7` | AC-7 and AC-8: the dependency set and native surface, witnessed |
| `09c5e9a` | the live probe's mutation had no witness on the code that makes it |
| `6b21d03` | one Electron userData per shell run, so a stale lock cannot forge a failure |
| `6c0007e` | the guard IPC decisions moved where a witness can run them |
| `6a53644` | record the follow-up batch, and the gaps it still leaves open |

The first seven are the commits whose code and measurements this section
describes; the eighth is this record's own documentation-only commit. Three
of the seven are corrections the measurements forced; §10.3 records them
because a record that hides them hides why the code looks the way it does.

### 10.2 Measured, and held

**T05 / AC-4's live half.** A real Electron window loads the service's own
origin; the sandboxed preload asks the main process for permission, is granted
by sender **origin**, and makes one fixed tokenless `POST /task/select` of its
own. The real service's `SessionGuard` answers **401 `session_required`**; the
main process validates the report's sender origin before printing and echoing
the verdict; the status strip and the enumerable bridge both show
`401 session_required`. Witnessed three ways: `test/live-guard.test.mjs` (5
tests over the request the page actually builds and both IPC decisions),
`scripts/rehearse-live-guard.mjs` (the real window, read over CDP: strip,
bridge and the main process's own line), and the counter-mutations below.
No main-process `net.fetch` is involved (ADR-0023's out-of-shape list), the
token never crosses the boundary, and no shell-added origin appears in
`ServiceStarting.origins`. The `about:blank` startup-refusal page is a
*refused* sender (`refused guard-request origin null`), not a page that can
talk to the service.

**T06 / AC-2's three unwitnessed arms.** `scripts/rehearse-lifecycle.mjs`
runs each against the real shell with a real service child on an OS-chosen
port:

- **startup refusal** — an uninitialised workspace produces the CLI's own
  `workspace_not_initialised`; the window ends on `about:blank` with strip and
  bridge both `failed` and the reason in the detail, exactly one page target,
  and the page is a refused sender.
- **main-process crash** — an uncaught exception is injected into the *real*
  main process over its own `--inspect`, not by editing the shell to throw on a
  timer; exit 1, the handler's diagnosis printed, the child gone from the
  process table, the port released.
- **second instance** — a second launch exits 0, starts no service of its own,
  and leaves the first shell and its child running. Both shells are given the
  same `--user-data-dir` on purpose: Electron's single-instance lock lives in
  userData, and a shared lock is the property this arm witnesses.

The other three rows of §4.3 keep their existing witnesses: normal close and
crash-after-readiness are `rehearse-loop.mjs` acts 1–2, and the
foreign-listener occupancy arm is `test/drain-witness.test.mjs`.

**AC-7 (static half).** `test/dependency-surface.test.mjs` (3 tests) reads the
runtime surface: every absolute URL in `shell/src/` names a loopback host; the
lockfile's packages are exactly the thirteen the owner's approval was measured
over; `package.json` declares only `electron@45.2.3`. An introduced remote
host reddens the same scan (positive control). The file also records rather
than hides that `@electron/get` names `github.com` — Electron's
*install-time* binary download, measured in the selection record and plan
§4.4. The runtime scan is scoped to `src/` for that reason; it does **not**
claim that no installer-time channel exists.

**AC-8 (static half).** `test/native-surface.test.mjs` (6 tests) scans the
surface a renderer or main-process caller can actually use: the two
`contextBridge` getters, the `webPreferences` object the window is built with,
the supervisor's two spawn call sites (service child and the recorded
`taskkill /T /F` group kill), and routes for `shell.openExternal`, COM
activation, DOCX-host ProgIDs, ActiveX, WScript, UI automation, native FFI and
host executables. A real `shell.openExternal(...)` plus a `'Word.Application'`
ProgID reddens it; a sentence naming the same routes does not. **This is the
static witness the plan names; §0 rule 2's review in a dated acceptance record
is still T09's work.**

`node --test "shell/test/*.test.mjs"` → **27 tests, 27 pass, 0 fail** at this
head. No pytest file was added, so §3 rule 3's three registrations are not
owed; `tests/`, `.github/ci-shards.json` and
`tests/evaluation/manifest.py` were not touched. No file under
`src/labcairn/` was touched: this batch's diff names `shell/` and
documentation only.

### 10.3 Counter-mutations: 13/13 effective, after three harness defects were repaired

A counter-mutation is evidence only when the witness goes red **for the
property**. The final single run, at the head named above, held the lock from
start to release, required a clean tree, ran each witness on the clean tree
first (a red baseline is `ENV-BROKEN`, not `CAUGHT`), checked each patched
source file parses **before** writing it into the tree, compared every file
against `git HEAD` before the patch and after the restore, and kept each
witness's full output at
`E:\labcairn-local\tmp\lc-p305-shell\witness-output\`. Its summary:

```
CAUGHT   M1  the sender-origin grant check is removed
CAUGHT   M2  the sender-origin report check is removed
CAUGHT   M3  any non-server error counts as guarded
CAUGHT   M4  the live probe stops being a mutation (POST -> GET)
CAUGHT   M5  the crash path no longer stops the service child
CAUGHT   M6  the single-instance lock is assumed rather than taken
CAUGHT   M7  the startup-refusal diagnostic is suppressed
CAUGHT   M8  a remote host appears in the shell's runtime code
CAUGHT   M9  a dependency outside the approved set enters the lockfile
CAUGHT   M10 a DOCX-host route appears in the shell's surface
CAUGHT   M11 the preload gains a token-carrying getter
CAUGHT   M12 the window loses its sandbox
CONTROL-GREEN M13 a comment-only change leaves the witness green
13/13 effective
```

M2's first run reported **SURVIVED**. That was a real gap, not a flaky
environment: the only thing watching the report-side origin check was an
assertion that counted occurrences of `senderIsAllowed(` in `main.mjs`, which
cannot be imported by a test. `6c0007e` moved both decisions into
`createGuardIpc` and replaced the count with four driven cases, and M2 now
reddens with *"a frame that skipped the grant had its report believed"*.
M1 reddens with a real `guard-request granted origin null` on the diagnostic
page; M5 with *"the service child pid … outlived the crashed main process"*;
M6 with *"the second instance never exited — the lock is not doing its job"*;
M7 with the absence of `status failed` from a shell that otherwise starts;
M8/M9/M10/M11/M12 with the named assertion. M4's honest boundary: with GET
(and no body, since `fetch` refuses a GET with a body outright), the service
answers **405** because `/task/select` is a POST-only route — so the mutation
proves the half-loop no longer shows the measured 401 refusal, **not** that the
guard would admit a read. A claim about reads needs a route that exists for
reads; it is not made here.

Three defects of the measurement harness itself were found and repaired; each
changed a number, and each is recorded so that a later run does not repeat it:

1. **Two harness processes ran concurrently** at 16:59:24 and 17:00:51 — the
   first `TaskStop` ended the wrapper shell but not the Node child. They wrote
   one output file and mutated one working tree. That result is **not
   attributable** and is archived as
   `E:\labcairn-local\tmp\lc-p305-probe\counter-mutations.NOT-ATTRIBUTABLE-2026-11-10-concurrent.out`.
   The harness now takes a lock (outside the repository, because `.git` in a
   worktree is a *file*), checks the holder's pid against the process table so
   a killed holder's stale lock is taken over rather than blocking forever,
   and refuses to start on a dirty tree.
2. **`spliceOne` was off by one.** `parts.slice(0, k)` returns nothing at
   `k === 0`, so every mutation deleted all text before its anchor. The
   patched module began inside a function, Electron reported
   `App threw an error during load / SyntaxError: Illegal return statement`,
   and four witnesses went red with `the shell never printed …` — recorded as
   CAUGHT, which was false. This, not the concurrency, is what truncated
   `shell/src/main.mjs` to four lines. A validity check that reads the patched
   text from `git HEAD` without touching the tree now reports **13/13
   PATCH-PARSE-OK**; the harness consults the same `spliceOne` before writing
   anything.
3. **Electron's single-instance lock was shared across all runs.** It lives in
   the app's userData directory, which defaults to the app *name*, and each
   rehearsal force-kills its shell with `taskkill /T /F`, leaving a stale
   `SingletonLock`. A later shell then exited quietly and its witness reported
   `the shell never printed loaded`. `6b21d03` gives every run its own
   `--user-data-dir` under scratch, except the second-instance arm where a
   shared directory is the property under test.

### 10.4 Named gaps that remain (owner decisions and external conditions)

- **T08's minimal packaging config has landed; T09 and AC-6 remain open.**
  `shell/electron-builder.yml` now declares an unsigned, per-user NSIS
  configuration; its files ship the main process, preload and manifest, and
  its extraResources ship the built `web/dist`. Its output directory is
  `${env.LABCAIRN_SHELL_DIST_DIR}`, so a build whose caller names no directory
  fails loudly rather than writing products into the tracked tree.
  `shell/package.json` carries the `dist` script.
  `shell/test/packaging-config.test.mjs` has nine tests: product/output/
  `extraMetadata.dependencies: null`/unsigned NSIS target and flags; the
  packaged `files`, `extraResources` web-dist and declared files' existence;
  the `dist` script, `electron-builder@26.18.0`, the lockfile entry,
  `electron@45.2.3` and the `minimatch@>=7 <11 → 11.0.7` override; a
  mutation test feeding signing, portable-only target and in-tree-output
  variants back through the same readers; and five cases for the packaging
  guard — the configuration names it, it is shaped the way electron-builder
  resolves a hook, the hook it calls throws on a missing bundle and returns
  true on a good one, and the script form refuses a missing bundle and
  accepts a complete one. The approved
  273-key lockfile set is witnessed separately in
  `shell/test/dependency-surface.test.mjs`.
  **The packaging was run, not only configured.** Measured on 2026-11-11 in
  an isolated worktree, electron-builder 26.18.0 produced the per-user NSIS
  installer `LabCairn Setup 0.0.0.exe` (124,536,512 bytes, SHA-256
  `da483fd949efba5e603bd8b47d0f57dfedd26f61b6469c69a59dac3e6e1241ea`); the
  signature was measured `NotSigned` on both the installer and the
  unpacked executable; the app.asar carried eight entries outside
  `node_modules` (`package.json` and the seven files under `src/`), and
  `resources/web-dist` carried the three bundle files byte for byte. The
  build printed `default Electron icon is used`, so the artifact wears
  Electron's icon. The products and the raw logs live outside the tree, in
  `E:\labcairn-local\phase3-g1-evidence\installer-build-2026-11-11`. The
  packaging is not byte-reproducible: a second build of the same
  configuration produced 124,536,585 bytes, so the SHA-256 names a product
  rather than the configuration.
  **That run also found a defect, and closing it took two attempts.** A build
  with no `web/dist` exited 0 and produced an installer whose `resources/`
  carried no `web-dist` at all — electron-builder prints one line for a
  missing source and keeps going. The first attempt at the guard was wrong,
  and it was a build that caught it rather than a test: it ran its check at
  module load and exported no default, so electron-builder's
  `resolveFunction` fell back to the module object and the packaging died
  with `beforeBuild is not a function` — with the bundle present. The guard
  now exports the hook as a default, has no top-level side effect, and
  returns `true`, because a falsy return would make electron-builder treat
  the dependencies as handled elsewhere and skip its own rebuild. Both sides
  were then measured on the real command: with the bundle present the build
  exited 0, produced the installer, carried `@electron/rebuild` in its log
  and put the three bundle files in `resources/web-dist`; with the bundle
  moved away the build exited 1, said `the packaging guard refuses this
  build`, and left its output directory empty. The five cases above watch
  the hook in the shape electron-builder calls it, and their mutation check
  reddens when the default export is removed, when the hook lets a missing
  bundle through, or when it returns a falsy value. An untracked, ignored
  `app.asar` packaging leftover remains in an old worktree directory, so no
  claim is made that every build leftover is outside the checkout. A signed
  installer (`W28`) and the clean-Windows drill (install → launch → upgrade
  → uninstall → rollback preserving user data, support limits, §0 rule 2
  review) have not been performed. The owner decided on 2026-11-10 that the
  batch may land
  with these gaps, and that they are recorded as named gaps rather than
  written as passing. The O3 runtime-arrangement measurement (frozen service /
  bundled interpreter / sidecar) and O5's import finding remain unmeasured.
- **AC-2's Windows graceful-ask arm stays the measured gap of §6.2, by the
  owner's decision.** Twelve measured combinations of `child.kill` reached
  none of a Windows child's handlers; the assertions cover what is measured
  (child ends, port releases, no pid survives) and the wording in §6.2 is
  unchanged. This batch did not attack it and does not soften it.
- **The focus half of §4.3's second-instance row is unmeasured.**
  `Browser.getWindowForTarget` answers *"wasn't found"* through this Electron's
  remote-debugging endpoint, so the witness asserts the lock's observable
  consequences (second process exits, starts no service, first shell and child
  stay alive) and names the focus half rather than inferring it.
- **Arm C remains in miniature** (§8), and **no `file://` counter-mutation was
  run against the pure-layer guard tests**. Neither was changed by this batch.
- **AC-7's install-time channel is a recorded fact, not a green claim.** The
  remote-host witness covers `shell/src/` and the declared dependency set;
  the build job's reachability of Electron's binary channel is an owner/CI
  fact (plan §4.4), not something a Node test on this machine holds.
- **No whole-suite pytest run was made for this batch**, and no repository-side
  witness was added for `docs/REPOSITORY-MAP.md`'s file count: §9 remains the
  skeleton batch's five-file subset. The count in that map was re-measured for
  the new row (`git ls-files | wc -l` → **821** at the head above), not carried
  forward from 2026-11-07; the repository has no witness watching that number.

### 10.5 Post-merge measurement: the same witnesses in a normal checkout

The branch's 27 Node witnesses were measured in its
`.claude/worktrees/<name>` checkout. After the batch was merged into local
`main`, a repeat in the **normal checkout** failed two real-service arms:
`shell/test/drain-witness.test.mjs` resolved its Python by climbing three
directory levels from `REPO_ROOT`, which only finds `.venv` from a worktree.
In a normal checkout the console-script path was `null`, so `spawnSync` raised
`ERR_INVALID_ARG_TYPE`; the suite reported 25 pass / 2 fail. Setting
`LABCAIRN_SHELL_CLI` and `LABCAIRN_SHELL_PYTHON` explicitly made all 27 pass,
which showed that the product was sound but the path rule was not.

The test now resolves those paths through
`shell/scripts/lib/shell-paths.mjs`, the module that handles both checkout
shapes, instead of carrying its own worktree-only rule. Without either
environment override, `node --test shell/test/*.test.mjs` measured **27 pass
/ 0 fail** in the normal checkout and **27 pass / 0 fail** in the branch
worktree. Three targeted Python test files measured **528 passed** after the
merge. No whole-suite pytest run, runner run, push, pull request or CI run was
started. This is a measured repair of the witness's own checkout assumption,
not a change to the product's drain rule.
