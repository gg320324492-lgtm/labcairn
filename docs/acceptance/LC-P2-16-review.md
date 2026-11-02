# LC-P2-16 — independent review of the issue-key outlet's acceptance record

**Record reviewed:** `docs/acceptance/LC-P2-16-acceptance.md` (the outlet that
lists the chain's issue keys: the layer read, the route, and the panel), as it
stands in this branch.
**The tree reviewed:** `e10359e`, the branch tip this review worked in.
**Platform:** Windows 11 (10.0.26300) AMD64.
**Interpreters:** the repository's virtualenv at `E:\LabCairn\.venv` (CPython
3.12) with `PYTHONPATH` pointed at this worktree's `src/` — `import labcairn`
verified to resolve to this worktree before any run; and the web suite's
vitest, for which `node_modules` was installed in this worktree (`pnpm
install --frozen-lockfile`) before the panel's witnesses were run. Each
pytest run had its own `--basetemp` under `E:\labcairn-local\tmp`; the
statuses were read from the commands themselves, not from a pipe.

**Method.** All eleven mutations of §3 were re-applied one at a time; every
mutation's diff was read before its witness ran, and the file was restored
with `git checkout -- <file>` after, with `git status` checked clean. One
mutation's first application did not take (the anchor matched three places
in the file); that run was discarded and the mutation was re-applied with a
unique anchor — no result is reported from an unapplied mutation.

## 1. What was re-applied, and what happened

**Baseline.** `tests/test_api.py` + `tests/test_feedback_events.py` —
141 passed, 1 skipped (the POSIX permission-bit skip). The web panel's
`TrajectoryView.test.tsx` — 23 passed. (The record's own §4 numbers — 89+1
and 18 — are the trees it was measured on; this tree is further along, so
its baselines are larger. Nothing in this review depends on that difference.)

| # | The mutation, as the record states it | Witness run | Result |
|---|---|---|---|
| 1 | the listing stops filtering by project | `test_the_layer_lists_this_project_s_keys_and_not_another_project_s` | **Red** — exactly its own assertion |
| 2 | the list is sorted the other way round | `test_the_layer_lists_the_chain_s_own_issue_keys` | **Red** |
| 3 | the versions named no longer narrow the answer | `test_the_layer_narrows_the_listing_to_the_versions_named` | **Red** |
| 4 | comments nobody keyed are no longer excluded | `test_the_layer_lists_the_chain_s_own_issue_keys` | **Red** |
| 5 | an unknown project is no longer refused | `test_the_layer_refuses_a_project_the_chain_does_not_hold` | **Red** |
| 6 | a version outside the project is no longer refused | `test_the_layer_refuses_a_version_that_is_not_the_project_s` | **Red** |
| 7 | the route stops passing the versions named | `test_the_issue_keys_route_refuses_a_version_that_is_not_the_project_s` | **Red** |
| 8 | the route names a fixed project instead of the caller's | `test_the_issue_keys_route_refuses_a_project_the_chain_does_not_hold` | **Red only in the effective form — see finding 1** |
| 9 | the panel draws a key of its own beside the contract's | `draws the keys the answer carried, and none it did not`; `draws the order the service answered in, and no order of its own` | **Both red** — as the record states ("two") |
| 10 | the panel sorts the list itself | `draws the order the service answered in, and no order of its own` | **Red** |
| 11 | the panel draws the advisor's words in the issues panel | `draws no comment's words, because the contract carries none` | **Red** |

## 2. Findings

1. **(Finding, description-level) Mutation 8's stated form does not redden
   its witness; only the *existing*-project form does.** Applied literally —
   the route answers `"fixed-project"` instead of the caller's id — the
   witness `test_the_issue_keys_route_refuses_a_project_the_chain_does_not_hold`
   **stays green**, because the refusal is the layer's (`CHAIN_PROJECT_NOT_FOUND`
   for a project the store does not hold), and a fixed id that does not exist
   is refused exactly as an absent caller id is. The mutation reddens the
   witness only when the fixed id is **one the store holds** (this review
   applied it as the fixture's own `proj-1`, and the witness reddened with
   the route answering `200` for an absent project). The record's table row
   says only "names a fixed project"; a reviewer who re-applies the literal
   form will report a survivor where the record reports a red. The property
   itself is witnessed and holds; the description of what broke it is one
   qualifier short of reproducible.
   **Resolved 2026-11-02:** the record's mutation-8 row now says the fixed id
   must be one the store **holds**. Re-applied on the tree at `c19a83d`
   before the correction landed (source files byte-identical):
   `"fixed-project"` left the witness green; the fixture's `proj-1` reddened
   it with `200` and the absent project's list answered by `proj-1`'s keys.
2. No claim was found with nothing behind it:
   - The `IssueKeys` contract is two fields
     (`src/labcairn/api/contracts.py:271`), and the body-shape claim
     `set(body) == {"project_id", "issue_keys"}` is asserted in
     `tests/test_api.py:2275`.
   - `web/src/api/paths.ts` carries `issueKeys` (`:51`) and
     `issueKeysPath` (`:143`), and its drift check compares them with routes
     the service declares.
   - The panel keeps no order of its own: it draws `answer.issue_keys` as it
     arrived (`src/views/TrajectoryView.tsx:359`) and sorts only the
     *versions* (`:441`), which is what the record says.
   - The layer's sorting, blank-key exclusion, project filtering and the two
     refusals are in `read_issue_keys` (`src/labcairn/application/chain.py:367-427`)
     and each was separately proven to be load-bearing by mutations 1-6.

## 3. What could not be checked, and why

- Nothing in this record is a claim about a store or a file outside the
  tree; every claim it makes was checked here. The only numbers that were
  not re-measured are §4's own baseline counts, which belong to the tree
  the record was measured on (`0656a6e` plus its commit) and which the
  record does not offer as evidence about any later tree.

## 4. Verdict

**Holds, with one note.** Ten of the eleven mutations reddened their
witnesses exactly as the record states. The eleventh (mutation 8) reddens
only in the *existing*-project form; the record's one-line description does
not carry that qualifier, which is a reproducibility gap in the description,
not a gap in the property — the property (an unknown project is refused by
name, not answered with an empty list) is witnessed and holds on this tree.
