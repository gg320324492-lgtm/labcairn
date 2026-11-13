# LC-P3-01 — the workbench's version-selection surface, landed 2026-11-14

**Line numbers.** The `file:line` pointers in this record name the lines as
they stood at the revision they were measured against; the tree may move since.
Follow the sentence, not the number.

**Date:** 2026-11-14. **Type:** dated evidence record for the gap
`docs/plans/PHASE_3-work-orders.md` §17 names as "Version switching in the
workbench" (§4.8). It records what was built, what was measured, and — as the
plan's own rule requires — what was **not** covered.

**Anchors, printed live while this record was written.**

| what | value |
|---|---|
| base commit (what everything here was measured against, before this record) | `39c53c793e62328e4d13782872032f3147eb38eb` |
| branch carrying this work | `claude/cranky-curran-8ef0b5` (a worktree branch; nothing pushed, no PR, no CI) |
| web suite at this record | `web/` vitest: **142 passed / 142** (16 files), `tsc -b --force` clean, `eslint` clean, `prettier --check` clean, `pnpm build` clean |
| wire-level witness at this record | `tests/test_workbench_live_service.py`: **3 passed / 3** |
| platform | Windows 11 Pro 10.0.26300 x64 — the development machine, **not a runner** |

## 1. What the gap was, and what this batch did about it

§4.8's first bullet says the workbench "has no version-control surface;
version switching is recorded as a named gap in §8, not claimed as exercised",
and §17's row asks for "a version-selection surface and a browser witness".
The service side of versions already existed: every report render is written
as a **new revision** under its own `report/v{N}/` path
(`src/labcairn/reports/revisions.py`), the receipts at `GET /artifacts` carry
the revision number and the content hash, and `GET /artifacts/{id}/content`
serves each revision's bytes. What did not exist was **any way for the person
at the workbench to see the versions and choose one**.

What this batch adds is that viewing surface, and it is deliberately a
**view**:

- `web/src/app/versions.ts` — the versions of a report, grouped by the
  receipts' own revision number (oldest first), read from `GET /artifacts`.
- `web/src/views/VersionSelect.tsx` — the "Version select" panel: it lists the
  revisions with each one's document hash, shows the newest by default, and
  switches on the reader's choice. The chosen revision's forms are fetched by
  the browser from `/artifacts/{id}/content` — the same sandboxed route the
  artefact preview uses, never inlined into the page.
- `web/src/views/ArtifactPreview.tsx` — an optional `label` for the preview's
  accessible name, so the version panel's frames do not collide with the
  artefact panel's when both show the same report.
- `web/src/app/Workbench.tsx`, `web/src/index.css` — the panel is mounted
  beside the Revisions panel and styled.

**What the panel says about itself, in its own words:** "Choosing one changes
what this page shows; the service holds no 'current version' of its own, and
nothing is written by choosing." That sentence is load-bearing: the service
has **no route that stores a current version** (asserted by a witness below),
so a selection that looked like a write would be the screen claiming what the
service does not do.

**What was NOT built, on purpose.** No server-side selection endpoint, no
`current_version` pointer, and no change under `src/labcairn/` at all — the
wire layer already serves everything a viewing surface needs, and adding a
selection *write* is the owner's call, not this batch's. The panel's honesty
sentence and the OpenAPI witness are the two halves of that boundary.

## 2. The wire-level witnesses (`tests/test_workbench_live_service.py`)

Extended in place (no new test file, per the owner's no-new-CI-file rule).
Two witnesses were added; both drive the same `create_app` the `serve`
command builds, through the in-process ASGI transport, in a workspace the
CLI itself made.

### 2.1 `test_the_report_has_two_revisions_and_both_are_served`

The versioned writes §8 promises, read over the wire the workbench reads:

1. A claim is recorded through the layer (`record_claim`, as
   `labcairn task claim` runs it) against CSV material the task holds.
2. The report is rendered **twice** through `POST /report` — the same route
   the workbench's Render button sends.
3. Four assertions, each failing for its own breakage:
   - the two renders left **two revisions** of the report (`revision == [1, 2]`
     on the `/artifacts` receipts), with different paths and different hashes;
   - each revision's document bytes are served at `/artifacts/{id}/content`
     and **hash to their own receipt**;
   - the two revisions' bytes **differ**;
   - revision 1's receipt and bytes are **unchanged** after the second render,
     re-read from the service — the immutability the revision machinery
     claims, checked where a reader would check it.

   The workspace's policy file carries one added allow rule (read and list on
   the task's outputs), because the default policy denies every read and the
   content route answers `permission_denied` under it — that refusal is the
   permission boundary working, and it is recorded in §4 below rather than
   worked around in product code.

### 2.2 `test_the_workbench_has_no_version_selection_route`

The honest boundary, watched: the service's own OpenAPI document (the one the
TypeScript types are generated from) declares **no route** whose path names a
version selection. If one is ever added, this witness fails with the route's
name and the sentence that the panel's truth claim must be rewritten with it.

### 2.3 Mutation checks (each applied to the tree, then reverted; the tree is
byte-clean afterwards)

| mutation | what it broke | witness that caught it |
|---|---|---|
| every render forced to `revision=1` | "two renders → two revisions" | `test_the_report_has_two_revisions_and_both_are_served` **failed** (the second render was refused by the revision-immutability guard, so the assertions never saw two revisions) |
| the content route made to serve the newest revision's bytes for every receipt | "each revision's bytes hash to their own receipt" | the same witness **failed**: `revision 1's bytes do not hash to its receipt` |
| a `/version/select` route added to the app | "no route selects a version" | `test_the_workbench_has_no_version_selection_route` **failed**, naming the route |

After each revert the file ran green again (3/3). The web suite's own
witnesses were mutation-checked the same way: forcing the version grouping to
file every receipt under revision 1 failed three cases; making the panel's
Show button POST to `/task/select` failed the no-write case.

## 3. The page-level witnesses (`web/src/views/VersionSelect.test.tsx`)

New vitest file, driven against the fake of `fetch` at the network boundary —
the same arrangement `workbench.test.tsx` uses, so the page, the client, the
paths and the session scheme are the things exercised. Five cases:

1. the revisions are listed oldest-first, each with its receipt's hash;
2. the newest revision is shown first; choosing another switches what the
   page shows **without any write request** (the non-GET request count is
   asserted unchanged), and the chosen frame is fetched from the content
   route;
3. the panel's own sentence — that the service holds no current version and
   choosing writes nothing — is on the screen;
4. when the service lists a new revision, the page shows it (the page holds
   no remembered choice);
5. a task with no report yet says so.

These are the assertions a **browser** witness would carry; they run in jsdom
here, and §4 names the browser run as the remaining step.

## 4. Measured gaps — what this batch did not cover

Named, with the boundary each sits behind, per the plan's rule that measured
gaps are named, not assumed away:

1. **No real-browser run of the new panel.** The five page-level cases run in
   jsdom through faked `fetch`. The browser-driving file
   (`tests/test_workbench_real_browser.py`) is another window's file in this
   batch, so the assertion that the built page shows the chosen revision's
   bytes in a real Edge tab is **written and ready** (§5) but not merged into
   that file by this window. Until it runs there, the render half of §4.8's
   first bullet is witnessed in jsdom only.
2. **No server-side version selection.** The service has no route that stores
   a current version (witnessed), so "switching versions" in the workbench is
   switching what the page shows. Whether the product wants a persisted
   current-version pointer — and what it would bind to (a report key? a
   revision? a version-graph node?) — is the owner's decision, and §8's
   versioned-write promises do not require it.
3. **The content route is permission-gated, and the default policy denies
   it.** Measured live in this batch's smoke run: under the workspace's
   default policy, `GET /artifacts/{id}/content` answers `403 permission_denied`
   on `report/v1/report.json` (`default_deny`), because the default rules'
   `pattern="output"` matches a workspace-relative spelling while the
   artifact content is addressed by its output-area-relative key. The
   witness workspace therefore carries one operator-written allow rule. An
   operator who has not written that rule sees the panel's previews refused
   with the service's own reason — which the panel shows, but which is a
   real usability boundary worth an owner's look.
4. **Only the report kind is versioned today.** The receipts carry revision
   numbers for the revision machinery's outputs; figures and manifests carry
   `revision: 1` or none. The panel groups what the receipts say and invents
   no versions for other kinds.
5. **The version *graph* is a different surface.** `paper_versions` /
   `version_edges` (the advisor-loop's version graph, drawn by the Trajectory
   and Version graph panels) are a separate notion of "version" from the
   report revisions this panel lists. This batch touches only the report
   revisions, and the two vocabularies are not merged anywhere.

## 5. The browser assertion this window did not land

For the window that owns `tests/test_workbench_real_browser.py`, to merge
when that file is free. It assumes the fixtures of that file (`workbench`,
`_load`, `support`) and the panel's reachable wording:

```python
def test_the_version_panel_shows_the_revision_the_reader_chooses(
    workbench: WorkbenchRun,
) -> None:
    """§4.8's first bullet, version half: the chosen revision, on the page.

    The service is driven to two report renders first (the same `POST /report`
    the page's own button sends), so the workspace genuinely holds two
    revisions before the browser opens. The page must list both revisions,
    show the newest by default, and switch to the one the reader chooses —
    by the frames the content route serves, with no write request anywhere,
    because no route stores a current version.
    """
    page, _requested, _answered = _load(workbench)
    try:
        token = workbench.served.session_token()
        for _ in range(2):
            reply = workbench.served.post(
                "/report",
                body={"path": "report", "template_id": "default"},
            )
            assert reply.status_code == 200, reply.body

        versions = page.get_by_role("heading", name="Version select").locator(
            ".."
        )
        rows = versions.get_by_role("listitem")
        assert rows.count() == 2, (
            f"the page listed {rows.count()} revisions for a task that holds two"
        )
        assert "revision 1" in rows.nth(0).inner_text()
        assert "revision 2" in rows.nth(1).inner_text()

        chosen = versions.get_by_title("Revision 1: reports/v1/report.html")
        assert chosen.count() == 1, "the newest revision was not the default view"
        versions.get_by_role("button", name="Show").click()
        page.wait_for_timeout(500)

        switched = versions.get_by_title("Revision 1: reports/v1/report.html")
        assert switched.count() == 1, (
            "the page did not switch to the revision the reader chose"
        )
    finally:
        page.close()
```

It fails for its own property: if the panel does not render the chosen
revision's frame (or lists the wrong revisions), the `get_by_title` lookups
find nothing and the assertions fail. It must be adjusted to the actual
markup of the merged panel (the `get_by_title` strings are the panel's
accessible names for the preview frames), and the second render must be
reached through the page or the service with the workspace's policy allowing
content reads — the same allow rule §2.1 records.

## 6. What the work left on this machine

- The worktree's `web/node_modules/` (installed with
  `pnpm install --frozen-lockfile`) and `web/dist/` (built for verification);
  both are git-ignored.
- `E:/labcairn-local/tmp/lc-version-smoke/` — the CLI smoke workspace the
  measurements above were taken in (outside the repository), with a
  `labcairn serve` process that was **stopped** after the smoke run.
- Nothing pushed, no PR opened, no CI started. The changes live on the
  worktree branch `claude/cranky-curran-8ef0b5` for review and merge by the
  conductor.
