# LC-P3-01 — the real-browser baseline, measured

**Date:** 2026-11-08. **Type:** dated window record for `LC-P3-01`
(`docs/plans/PHASE_3-work-orders.md` §4). It records what the G1 window
measured, names the witness that carries each row, and names the boundaries
the run did not cross. It is **not** the G1 acceptance record: that is written
at the gate's end, from measured rows, by the gate. It claims no ticket status
— neither PASS nor PASS WITH NOTES — and it dispatches nothing.

**Anchors, printed live while this record was written.** The window's
implementation commit is `15fb9382f17c2a0cde00c4a74bcebdabca1ba80b`; its parent
is the commit that issued the G1 work orders, local `main`
`f24aad68b91938e7e93954726363a99785215fa4`; `origin/main` is
`d38010e9b8cf270beb19c38d6979ea14284c318d`. This record, the browser witnesses'
follow-up and the threat-model rows land in a later commit on the same branch,
whose id is printed live at review — a record cannot cite the commit that first
carries it.

## 1. What was measured, and what carries it

Every row below was measured **locally, on 2026-11-08, on the development
machine** — Windows 11 Pro 10.0.26300 x64, Playwright 1.64.1 in a
project-owned venv, Edge 156.0.4314.58 through the `msedge` channel, `web/dist`
built from the frozen lockfile. No runner was involved. The environment rows
(§4.2 of the work orders) are recorded, with the exact commands, in the
window's environment record outside the repository:
`E:\labcairn-local\phase3-g1-evidence\LC-P3-01\2026-11-08-environment-and-run-record.md`.

| Work-order row | What the run did | Witness |
|---|---|---|
| §4.4 row 2 — the serve start/stop helper | The helper starts the real `labcairn serve` console script in a temporary workspace, on an operating-system-chosen port, and stops it; the socket stops answering | `test_workbench_serve_helper.py` (five arrangement witnesses) |
| §4.4 row 3 — the build served from the service's own origin | The served `/` is byte-identical to the build's `index.html`; its hashed asset is served as JavaScript, byte-identical to the file in the tree; the API still answers under it; a build that is not there is refused | `test_workbench_serve_helper.py` (three build witnesses) |
| §4.4 row 4 / §4.6 row 11 — the session token | `GET /session` serves the token at the service's own origin, refused (403, `origin_refused`) for a foreign one over a real socket; the page names the token file in its footer and never the token | both test files |
| §4.6 rows 1–5 — driver, browser, channel, cache, platform | Named by the run itself: driver 1.64.1, Edge 156.0.4314.58, `msedge`, the project's cache in force and the machine's inherited value recorded | `test_workbench_real_browser.py::test_the_run_names_the_browser_the_channel_and_the_cache_it_actually_used` |
| §4.6 row 9 — the page's reads against the real service | Every path `web/src/api/paths.ts` declares was requested by the page and answered 200 — except the stream, which is §2's first gap | `test_the_page_makes_every_read_the_workbench_declares`, `test_no_request_the_page_made_left_the_machine` |
| §4.6 row 10 / §4.8 bullet 1 — the two surfaces agree | The page renders the task the CLI reports; the page's selection is followed by the workspace pointer and the CLI reports the moved task; `GET /task` equals `task status --json` after the switch | `test_the_page_shows_the_task_the_cli_reports_for_the_same_workspace`, `test_the_page_moves_the_service_s_selection_and_the_cli_reports_it` |
| §4.4 row 10 / §4.8 bullet 2 — the comment, visible | A synthetic comment written through the chain's own doors (`record_feedback`, then `set_issue_key` — a key is given, never derived) is listed by the Issues panel and drawn, words and version, by the Trajectory panel | `test_a_chain_comment_is_visible_in_the_view_that_reads_it` |
| §4.4 row 13 / §4.8 bullet 3 — the approval | A consent question asked through the product's own layer is pending; the page grants it; the recorded state is `granted`; the page offers no second grant; a direct second grant is refused (403, `approval_refused`) | `test_an_approval_answered_from_the_page_is_recorded_and_a_second_answer_is_refused` |
| §4.6 row 9's stream read, §4.7's gap list | The stream gap and the panel's `live` sentence, asserted as measured (§2) | two gap witnesses (§2) |
| §4.8 bullet 1's rendered-state comparison | The rendered header, goal and success criterion match the CLI's JSON for the same task | `test_the_page_shows_the_task_the_cli_reports_for_the_same_workspace` |

## 2. The measured-gap list (§4.7 deliverable 2)

1. **The CLI-served service has no event source, and the refusal never reaches
   the client.** `GET /events` refuses (403, `not_implemented`);
   `GET /events/stream` sends its own `200` and `text/event-stream` headers
   first, then raises — the client gets an empty stream, the server logs
   `RuntimeError: Caught handled exception, but response already started.`
   Evidence: `test_the_event_stream_the_page_reads_is_unwired_in_the_service_the_cli_starts`;
   `src/labcairn/api/events.py` (`UnwiredEventSource`);
   `src/labcairn/cli/commands.py` (`serve`, which passes no source).
2. **The Events panel reports the stream live on that service.** *"The event
   stream is live; the service has sent no event for this task yet"* — honest
   about the stream it saw, wrong about the service. Evidence:
   `test_the_events_panel_reports_the_stream_live_on_a_service_that_has_none`
   (a gap witness that goes red when either side changes). Both fixes are
   outside the window's file area (§4.5); they are reported, not applied.
3. **A consent question cannot be asked over the wire on a fresh workspace.**
   `POST /approvals` with the service's own token and origin refused
   `source.read` with `permission_denied … default_deny` on a bound source
   root (`root_id: "source:0"`, `resource_key: "note.md"`), and
   `root_kind_not_permitted` for the workspace root. Row 13's *answer* was
   still witnessed by asking the way the product asks it in its own layer
   (`request_approval`) before the service started, and granting from the
   browser.
4. **The bounds of the browser run itself.** One machine, one run, one channel
   (§6.1 of `docs/THREAT-MODEL.md`, updated in the same commit as this
   record): not a runner, not a downloaded browser, not every platform. The
   web tests CI runs still stop at the `fetch` boundary, because the browser
   witnesses skip where no driver is installed.
5. **The shard costs of the two new test files are not runner-measured.** They
   carry apportioned costs and `measured_at` was not moved;
   `test_ci_shard_coverage.py::test_the_shards_are_balanced` fails on
   `windows-latest` as the witness is designed to, and the fix is one
   owner-authorised run (`python .github/remeasure_shards.py <run-id>`). No
   run id exists: this window started no CI.

## 3. What this record does not carry

- **The §4.9 dual-host reopen checklist.** It is a human act at the machine
  (WPS as judge, Word 2010 as reference, no COM automation), and it examines
  files `LC-P3-02` produces, which did not exist while this window ran. It
  stays open for the owner; the hosts and procedure are named in
  `G1-ENV-EVIDENCE-PREP-2026-11-08.md` §2.
- **A ticket status.** §1 carries rows, not a verdict; the gate decides.
- **Any change to the shared records.** The work orders' board, README,
  CHANGELOG, CURRENT and ROADMAP were left untouched for the commander to
  reconcile after review.
- **Material words.** The only comment the chain witnessed is a synthetic
  sentence written by the fixture; no advisor material entered the tree.
