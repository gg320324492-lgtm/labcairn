# LC-P2-16 — The issue-key outlet — acceptance

**Work order:** LC-P2-16 (the workbench for the guidance line) · **Piece:**
the contract's outlet that lists the chain's issue keys, and the trajectory
panel's drawing of that list · **Task breakdown:**
[`../plans/LC-P2-16-task-breakdown.md`](../plans/LC-P2-16-task-breakdown.md)
· **Status:** landed in this branch.

**Status of the work order:** **implemented and measured**, and **not independently reviewed**. The outlet answers the four
questions its work order named, and **the project's rule is that a work
order is accepted on an independent review at a named commit** — that
review has not happened.

**What this is.** The work order's T02 says, in its own words: *"there is
**no outlet that lists the chain's keys**, so the view can draw only the
trajectory of an issue the caller already names — **a panel that cannot list
what there is to look at is a panel with no way in**, and whether that needs
an outlet is the owner's call, not this plan's."* The owner decided it does,
and this is the outlet: a read in the application layer that answers *which
issues there are*, a route that serves it, and a panel that draws the list
and says where the order came from.

**What this is not.** It is **not the whole of LC-P2-16's acceptance
record.** The work order's §3 T06 owns the demonstration and the record of
the whole work order — the rules' door, the proposals panel and the loop.
This file records the one piece above and nothing else, so that the two do
not claim each other's ground.

---

## 1. The outlet, and the four questions it had to answer

`read_issue_keys(context, *, project_id, version_ids=())` in
`src/labcairn/application/chain.py`, beside the chain's other reads.

| # | The question | The answer, and where it is held |
|---|---|---|
| 1 | **Which keys?** | **The keys the chain's own rows carry.** A key is a person's judgement and it is *given*, never derived — the same wording is not the same issue — so a comment nobody keyed is *uncategorised* and is not in the list. A key nobody has named is not in the chain, so it is not in the list either: **the chain's rows are the only source**, and a key that lives in another table is a name *about* the chain, not a key *of* it. |
| 2 | **How is a key ordered?** | **Sorted.** The chain's rows carry **no time and no sequence**, so there is no chronology in the chain to read an order out of: an order taken from the rows would be the *storage engine's* and not the chain's, and the same chain would then be two lists. **Sorting is an order of the names themselves** — the same set of keys answers the same list, on every machine, however the rows happened to come back. |
| 3 | **What does it refuse?** | **A project the chain does not hold** (`chain_project_not_found`), and **a version that does not belong to it** (`chain_version_not_found`). Both are refused by name rather than answered about: an empty list for a project nobody holds would say *the project has no issues*, which is a different fact from *there is no such project*; and a version outside the project would answer about a chain that is not this one. Naming no version means the project's whole chain — the one scope a caller reaches before it knows which versions it wants. |
| 4 | **Does it leak?** | **No: the list is names, and the names are all it carries.** A key says *which problem*, not *what the advisor wrote* — no comment's words, no anchored text, no author, no date and no grade travel with it. The layer's own comment does carry them, and that is a different answer to a different question. |

## 2. Where it surfaces

| Where | What |
|---|---|
| `GET /trajectory/issue-keys` | the route. It takes `project_id` and, optionally, `version_id`; it reads nothing itself and calls the layer once |
| `IssueKeys` (`src/labcairn/api/contracts.py`) | the body: the project, and the keys. **Two fields, and the composition adds no member of its own** — the keys are the layer's answer and the project is the scope they are about |
| `web/src/api/generated.ts` | regenerated from the models; the drift test compares the checked-in file with what the models produce now |
| `web/src/api/paths.ts` | `API_PATHS.issueKeys` and `issueKeysPath(projectId)`, in the web's own single list of the paths the service serves — and `paths.test.ts`'s drift check compares every one of them with a route the service declares |
| `web/src/views/TrajectoryView.tsx` | the panel draws the list, says **where the order came from**, and offers each key as the way into that issue's trajectory |

**The panel's rule about the order, and what this list does to it.** The
chain's rows carry no time and no sequence, so the panel draws the order the
service answered in — and **this list does not change that**. The layer sorts
the keys, so the contract carries an order, and the panel draws it as it
arrived; the panel keeps **no order of its own** (it sorts the *versions*,
and says so, because the contract carries a set for them and carries an
order for the keys).

**What the panel does not draw.** The key is a name and the panel draws the
name: the comments' words, the anchored text and the author are not in the
contract's body, so the panel has nothing to draw. A key the contract did
not carry is not drawn either — **the panel keeps no list of its own**.

## 3. The witnesses, and the mutations that reddened them

Every mutation below was applied, the tree was measured, and the file was
restored byte-for-byte.

| # | The mutation | The witness it reddened |
|---|---|---|
| 1 | the listing stops filtering by project, so another chain's keys come back | `test_the_layer_lists_this_project_s_keys_and_not_another_project_s` — exactly one |
| 2 | the list is sorted the other way round | `test_the_layer_lists_the_chain_s_own_issue_keys` — exactly one |
| 3 | the versions named no longer narrow the answer | `test_the_layer_narrows_the_listing_to_the_versions_named` — exactly one |
| 4 | the comments nobody keyed are no longer excluded, so `None` becomes a key | `test_the_layer_lists_the_chain_s_own_issue_keys` — exactly one |
| 5 | an unknown project is no longer refused | `test_the_layer_refuses_a_project_the_chain_does_not_hold` — exactly one |
| 6 | a version outside the project is no longer refused | `test_the_layer_refuses_a_version_that_is_not_the_project_s` — exactly one |
| 7 | the route stops passing the versions the caller named | `test_the_issue_keys_route_refuses_a_version_that_is_not_the_project_s` — exactly one |
| 8 | the route names a project the store **holds** instead of the caller's — a fixed id the store does not hold is refused by the same refusal and leaves the witness green | `test_the_issue_keys_route_refuses_a_project_the_chain_does_not_hold` — exactly one (re-measured 2026-11-02 with the fixture's `proj-1`) |
| 9 | the panel draws a key of its own beside the contract's | `draws the keys the answer carried, and none it did not` and `draws the order the service answered in, and no order of its own` — two |
| 10 | the panel sorts the list itself | `draws the order the service answered in, and no order of its own` — exactly one |
| 11 | the panel draws the advisor's words in the issues panel | `draws no comment’s words, because the contract carries none` — exactly one |

**And the witnesses themselves, for the record.**

- The layer (`tests/test_feedback_events.py`): the keys are the chain's own
  and sorted; the comment nobody keyed is not in the list; another
  project's keys are not in the list; an unknown project is refused; a
  version outside the project is refused and the project's own version is
  served; the versions named narrow the answer, and naming none means the
  whole project.
- The contract (`tests/test_api.py`): the route carries the keys, and **the
  body carries names and nothing else** (`set(body) == {"project_id",
  "issue_keys"}`); an unknown project is refused with
  `chain_project_not_found`; a version outside the project is refused with
  `chain_version_not_found`, and the project's own version is served.
- The panel (`web/src/views/TrajectoryView.test.tsx`): it asks the service
  for the keys and asks for nothing until a project is named; it draws the
  key and calls it a key; it draws the keys the answer carried and none it
  did not; it draws the order the service answered in and no order of its
  own; it says where the order came from; it draws no comment's words; and
  the way into an issue draws it.

## 4. What was measured, and on what tree

**Local, incremental, at the delivery branch's tip `0656a6e` plus this
record's own commit.** The files this piece touched, under the suite's
environment rules (`TEMP`/`TMP`/`TMPDIR` at `E:\labcairn-local\tmp`, a fresh
`--basetemp` per run, statuses read from the command and not from a pipe),
with this worktree's `src` first on `PYTHONPATH`:

- `tests/test_api.py` — **89 passed, 1 skipped** (the skip is POSIX
  permission bits, and it is skipped on Windows).
- `tests/test_feedback_events.py` — **18 passed**.
- `web`: `pnpm exec vitest run` — **115 passed in 12 files**;
  `pnpm exec tsc --noEmit -p tsconfig.json` — **clean**.
- `ruff check`, `ruff format --check` and `mypy` (strict) — **clean** on
  every file this piece changed.

**No CI was started and no pull request was opened**, per the standing
decision of 2026-10-24. The local run is the evidence until a runner says
otherwise.

## 5. What was deliberately not done

- **The route is not in the CLI.** The layer's operation is there for any
  caller, but this piece builds the outlet the *workbench* needed, and no
  CLI command was asked for.
- **`src/labcairn/application/__init__.py` was not touched.** The route
  imports `read_issue_keys` from `labcairn.application.chain`, the way the
  same file already imports `StageRequest` from
  `labcairn.application.stages` and `ApprovalRequest` from
  `labcairn.application.approvals`. The package's own export list is a
  **shared file** — the delivery branch had already changed it — and the
  work order's ownership map does not give it to this piece. **The
  consequence is named here rather than left for the next reader**: the
  operation is reachable, but it is not yet on the layer's public surface,
  and a piece that owns `application/__init__.py` should add it.
- **No new test file.** A new test file needs a runner-measured shard cost,
  so the witnesses went into the two files that already exist and are
  already sharded.
- **The panel was not given a project of its own.** The project id is the
  caller's to name, as it already was for the version graph; the new
  outlet lists the keys of the project named and refuses a project nobody
  holds.
