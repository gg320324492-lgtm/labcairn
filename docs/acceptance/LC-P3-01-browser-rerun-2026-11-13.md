# LC-P3-01 — the real-browser witnesses re-run on 2026-11-13: the driver installed, every case green

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the revision they were measured against; the tree may move since.
Follow the sentence, not the number.

**Date:** 2026-11-13. **Type:** dated follow-up to
[`LC-P3-01-browser-baseline.md`](LC-P3-01-browser-baseline.md) (2026-11-08).
It records the re-run of the browser witnesses this window's owner selected on
2026-11-13 (`docs/plans/PHASE_3-work-orders.md` §2 item 1, §4.4, §4.5, §4.8,
§4.9, §4.12). It claims no ticket status — neither PASS nor PASS WITH NOTES —
and it dispatches nothing.

**Anchors, printed live while this record was written.**

| what | value |
|---|---|
| base commit (what everything here was measured against, before this record) | `794327bf552ab2579a0ea06db757caf635228b80` |
| branch carrying the re-run | `claude/elastic-colden-673b63` (a worktree branch; this record and the threat-model rows land in a later commit on it, whose id is printed live at review) |
| last change to `tests/test_workbench_real_browser.py` before this window | `4afb82969bcc0a69dadce5cc823a57499655a6d4` (2026-11-10) |
| driver installed for this run | Playwright **1.65.1** (Python side) |
| browser channel measured | `msedge` — **Microsoft Edge 157.0.4341.46**, `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`, probed with `msedge.exe --version` |
| build the browser loaded | `web/dist` built 2026-11-13T22:33 (+0800 local) by `pnpm install --frozen-lockfile && pnpm build`, pnpm 9.15.9, Node v24.16.0 |
| browser cache in force | `E:\labcairn-local\tmp\labcairn-ms-playwright` (project-owned, outside the repository), replacing the inherited `E:\microbubble-agent\data\ms-playwright` |
| platform | Windows 11 Pro 10.0.26300 x64 — the development machine, **not a runner** |

## 1. The two decisions §4.12 asks this window to make and record

**Decision 1 — the driver is carried on the Python side.** Playwright 1.65.1
was installed with `uv pip install playwright --python .venv/Scripts/python.exe`
into the project's own virtualenv at `E:\LabCairn\.venv`. It is **not** added
to `pyproject.toml`'s `dev` group, and `web/package.json`/`web/pnpm-lock.yaml`
are untouched.

*Why the Python side.* The witnesses that need the driver
(`tests/test_workbench_real_browser.py`, `tests/workbench_serve_support.py`)
are Python files in this project's own suite; the driver's consumer is pytest,
not the web app. The web side already carries its own test stack (Vitest,
jsdom); adding a Node-side driver there would mean a second install of the
same tool, a second place to pin its version, and a `web/package.json` entry
for something the web build never imports. The suite's own rule — the driver
is *not* a declared dependency of the product, and a runner without it skips
with a named reason — is preserved by leaving `pyproject.toml` untouched:
the driver is an environment capability, measured and recorded here, not a
product dependency. **Consequence, stated plainly:** on a fresh clone without
this install, the browser file still skips; CI still never runs it.

**Decision 2 — the witness is the existing file, extended by nothing and
split by nothing.** `tests/test_workbench_real_browser.py` already carried
every §4.8 assertion this re-run needed — that was the state the 2026-11-08
window left, and the re-run's job was to make it *run*, not to write a second
witness beside it. No new test file was created, so no shard or manifest
registration was touched, and no runner cost re-measurement is owed from this
window.

## 2. The system-browser channel, measured rather than assumed

The plan (§2 item 1, §4.12, §17's gap table) requires the channel to be a
measurement at dispatch. Measured on this machine, 2026-11-13:

| channel | result |
|---|---|
| `msedge` (system Edge) | **present** — Microsoft Edge 157.0.4341.46, `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |
| Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`, and the x86 spelling) | **absent** |
| Firefox (`C:\Program Files\Mozilla Firefox\firefox.exe`) | **absent** |
| Playwright-managed browser for driver 1.65.1 | **absent** — no download was performed for this run; the only Playwright cache on the machine is another project's (`E:\microbubble-agent\data\ms-playwright`, holding `chromium-1234`, which driver 1.65.1 does not use) |

The run therefore used **Edge 157.0.4341.46 through the `msedge` channel,
headless**, exactly the channel the helper pins
(`tests/workbench_serve_support.py` — `BROWSER_CHANNEL = "msedge"`,
`BROWSER_HEADLESS = True`). No browser was downloaded and none was added to
this machine for the product's sake.

## 3. What ran, and what it asserted

```
$ TEMP/TMP/TMPDIR=E:/labcairn-local/tmp MPLCONFIGDIR=E:/labcairn-local/tmp/mpl \
  COLUMNS=200 .venv/Scripts/python.exe -m pytest tests/test_workbench_real_browser.py \
  -q --basetemp E:/labcairn-local/tmp/p3-browser-1
..........                    [100%]
10 passed, 2 warnings in 71.33s (0:01:11)
```

Re-run once more after the mutation self-checks, same command shape
(`--basetemp .../p3-browser-full2`): **10 passed in 67.03 s**. The ten cases,
each with its §4.8/§4.6 row:

1. `test_the_workbench_renders_in_a_real_browser_at_the_service_s_own_origin`
   — the built page loads from the service's own origin (host must be the
   service's, not `localhost` spelled differently), renders a real title (not
   the placeholder), and draws at least eight panels.
2. `test_the_page_shows_the_task_the_cli_reports_for_the_same_workspace`
   — §4.6 row 10: the page and `task status --json` agree.
3. `test_the_page_makes_every_read_the_workbench_declares` — §4.6 row 9:
   every read `web/src/api/paths.ts` declares was requested and answered 200
   (the stream excepted, per the plan's own exception).
4. `test_no_request_the_page_made_left_the_machine` — the footer's
   *local API and nothing else* promise, checked on the wire: every request
   scheme `http`, every host `127.0.0.1`.
5. `test_the_page_reads_the_session_at_the_service_s_own_origin` — §4.6 row
   11: `/session` read and answered 200; the token file named by the footer;
   the token itself never on the page.
6. `test_the_page_moves_the_service_s_selection_and_the_cli_reports_it` —
   §4.8 bullet 1: a selection made from the page is followed by the workspace
   pointer, reported by the CLI without `--task`, and `GET /task` equals
   `task status --json` after the switch.
7. `test_the_run_names_the_browser_the_channel_and_the_cache_it_actually_used`
   — §4.6 rows 1–5 / §4.2: driver version, channel, browser version, the
   cache in force, the inherited value it replaced, and the driver's own
   resolution of its browser path all recorded by the run.
8. `test_an_approval_answered_from_the_page_is_recorded_and_a_second_answer_is_refused`
   — §4.8 bullet 3: the page's grant is the recorded `granted` state, the
   panel shows it, no second Grant is offered, and a second grant over the
   API is refused `403 approval_refused`.
9. `test_the_events_panel_says_the_stream_was_refused_on_a_service_that_has_none`
   — §4.8 bullet 4's precondition on this service: the stream is unwired, the
   page's read answers 403, and the Events panel does not claim `live`.
10. `test_a_chain_comment_is_visible_in_the_view_that_reads_it` — §4.8
    bullet 2: a chain comment written through the product's own layer is
    listed under its key and drawn verbatim by the Trajectory panel.

Two caveats, named rather than glossed:

* **§4.8 bullet 4 (event reconnection) is *not* exercised by this re-run.**
  Its precondition — a service with a live event source — does not exist:
  `labcairn serve` passes no event source, so there is nothing to interrupt
  and resume. What this run witnessed is the honest degraded state (case 9
  above). The reconnection property remains carried by the component-level
  witness `web/src/views/EventsView.test.tsx` and named as a gap in §5.
* **The versions moved since the 2026-11-08 baseline.** Playwright 1.64.1 →
  1.65.1, Edge 156.0.4314.58 → 157.0.4341.46. The re-run is a re-measurement,
  not a carry-forward: the baseline record's numbers describe 2026-11-08's
  tree and run, and this record's describe today's.

## 4. Mutation self-check — each property was seen to fail

Every mutation was applied to the worktree, the targeted witness was run, and
the tree was restored byte-identical afterwards (`git status` clean; the
full file re-run green after the last restore). The mutations that *weakened
an assertion* are reported as the lesson they taught — the assertion's
absence was indeed invisible to the rest of the suite, which is exactly the
property a mutation check of a witness demonstrates:

| mutation | expected | observed |
|---|---|---|
| `pin_browser_cache` made a no-op (the inherited `PLAYWRIGHT_BROWSERS_PATH` stays in force) | the env-record case goes red: the driver resolves into the other project's cache | **red** — `AssertionError: the driver resolved its browser to E:\microbubble-agent\data\ms-playwright\... — the inherited PLAYWRIGHT_BROWSERS_PATH won` |
| page loaded from `http://localhost:<port>/` (same socket, wrong origin spelling) | the origin case goes red | **red** — the netloc assertion failed |
| the selection's click removed | the selection case goes red | **red** — `the page still shows 'Browser baseline second' after the selection request` |
| the approval's grant click removed | the approval case goes red | **red** — `the Approval panel shows ['blocked'], not the recorded state` |
| the duplicate-grant `403` assertion dropped | no case notices | **stayed green** — the weakening is invisible to the rest of the file, which is the expected reading for a removed assertion; the property itself (server refuses) is separately witnessed by the API-side guard tests |
| the foreign-origin filter neutralised (`if False`) | no case notices | **stayed green** — same reading: the weakened assertion's property is not re-asserted elsewhere in this file; the loopback claim's real defence is the socket guard in `src/labcairn/api/guards.py` |
| `/task` dropped from the file's declared-reads list | no case notices | **stayed green** — the list is the file's own expectation, not the product's; the product's declared reads are witnessed from `web/src/api/paths.ts` by the helper's own tests |

The three green results are recorded as findings, not as failures of the
self-check: a witness's mutation check must target the property's *carrying*
assertion, and where a weakened line turned out to be a restatement rather
than the carrier, that is what the check found. No mutation left the tree
dirty; after every restore the full file was re-run green.

## 5. Measured gaps — what this re-run did not cover

Named, per §4.8's rule, not assumed away:

1. **The runner half of the baseline is still unmeasured.** Everything in
   this record is local. The fifteen required checks do not include a browser
   leg, the browser file is in `windows-latest` shard 1 and `ubuntu-latest`
   shard 2 of `.github/ci-shards.json`, and on a runner without the driver it
   skips with the named reason. §3 rule 6's *Windows browser pass is a
   runner's* remains open — see §7.
2. **Event reconnection (§4.8 bullet 4) is unexercised.** No event source is
   wired to the `labcairn serve` service, so there is no stream to interrupt;
   the degraded 403 path is what ran. Wiring a source is the owner's call
   (`THREAT-MODEL.md` §6.2's standing gap).
3. **No second browser, no second channel.** One channel (`msedge`), one
   browser (Edge 157.0.4341.46), one machine. Chrome and Firefox are absent
   here; nothing was measured about WebKit or any other engine.
4. **No downloaded-browser path.** Playwright's own chromium build was never
   launched; the `msedge` channel resolved through the pinned
   `PLAYWRIGHT_BROWSERS_PATH` without needing one. What a run looks like on a
   machine with *no* system browser and a downloaded cache is unmeasured.
5. **Headless only.** Every case ran `headless=True` (the helper's pin). The
   headed path, and anything a real window manager does differently, is
   unmeasured.
6. **One workspace shape.** Two synthetic tasks, one synthetic approval, one
   synthetic chain comment. No real material, no DOCX-bearing workspace, no
   source-root consent refusal *drawn on the page* (that refusal is
   witnessed at the API layer by `test_workbench_serve_helper.py` and at the
   application layer by its own tests; the page's rendering of a refusal was
   not driven).
7. **No timing or performance reading.** Page settle was given a 3 s ceiling;
   nothing was measured about load time, stream latency or render cost, and
   §4.3 makes that out of scope for this ticket.
8. **The shard costs of the browser file are still apportioned, not
   re-measured.** This window opened no CI run, so
   `.github/ci-shards.json`'s `measured_at` and per-file seconds are
   unchanged; no test file was added or moved, so no re-measurement was
   *owed* by this window.

## 6. What changed in the tree because of this window

| file | change |
|---|---|
| `docs/acceptance/LC-P3-01-browser-rerun-2026-11-13.md` | this record (new file) |
| `docs/THREAT-MODEL.md` §6.1 | the 2026-11-13 re-measurement added beside the 2026-11-08 baseline: driver 1.65.1, Edge 157.0.4341.46, the Python-side carrier decision, all-ten-cases-green (no skip), and the bounds restated for both runs |
| `docs/THREAT-MODEL.md` §6.1 (fetch boundary) | the "every web test still stops at the fetch boundary" paragraph now says the component tests still do and the browser witnesses no longer have to where the driver is installed — CI still never runs them |
| `docs/THREAT-MODEL.md` §6.2 | the unwired stream's refusal is now witnessed from the page itself, with the 2026-11-13 rerun named |

`tests/test_workbench_real_browser.py`, `tests/workbench_serve_support.py`,
`tests/test_workbench_live_service.py`, `pyproject.toml`, `uv.lock`,
`web/package.json`, `web/pnpm-lock.yaml` and every shard/manifest file are
**unchanged** by this window. Nothing under `src/` changed.

## 7. What only the owner can do next

1. **The Windows runner pass of the browser witnesses (§3 rule 6).** The run
   this record describes is local; the plan requires the Windows browser
   pass to have been run by a runner before the gate closes. What that needs:
   a CI run on a `windows-latest` runner whose environment has
   `playwright` installed (it is not a declared dependency, so the runner
   needs one `uv pip install playwright` step, or the owner adds it to the
   `dev` group), a system Edge for the `msedge` channel (runners carry Edge),
   and `LABCAIRN_BROWSER_CACHE_DIR` pointed somewhere runner-writable. The
   witnesses themselves are already shard-registered, so the run needs no
   workflow change — only the driver install.
2. **Deciding whether the driver becomes a declared dev dependency.** This
   window installed it into the project venv and left the declaration
   untouched (Decision 1). If the owner wants CI to run the browser cases
   rather than skip them, the declaration — and a shard-cost re-measurement —
   follow from that decision; neither is made here.
3. **The §4.9 human dual-host reopen checklist** remains open, as the
   baseline record already records: it examines files `LC-P3-02` produces and
   is a human act at the machine.

## 8. What this window left on the machine

| left | where | clean-up |
|---|---|---|
| Playwright 1.65.1 (+ greenlet 3.5.6) | `E:\LabCairn\.venv` (the project's shared venv) | one `uv pip uninstall playwright greenlet` removes it; leaving it is what makes future local runs of the browser file green — the owner's call |
| a project-owned Playwright browser cache | `E:\labcairn-local\tmp\labcairn-ms-playwright` | empty unless a download is ever requested (nothing was downloaded for this run); safe to delete |
| two pytest scratch trees | `E:\labcairn-local\tmp\p3-browser-1`, `...-full2`, and one per mutation | disposable; outside the repository by the suite's own rule |
| `web/dist` + `web/node_modules` in this worktree | the worktree's own `web/` | git-ignored build outputs; the worktree is disposable with them |
| no browser downloaded, no service left running, no branch pushed, no PR opened | — | the worktree branch carries only the two documentation files |
