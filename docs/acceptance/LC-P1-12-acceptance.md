# LC-P1-12 — Acceptance review

**Work order:** LC-P1-12 — the Typer CLI and the local FastAPI + React
workbench.
**Verdict:** **PASS WITH NOTES**.
**Reviewed against:** the merged state of `main` at `8fe7466` (PR #92) with
the ingestion operation (PR #93) —
the one application layer the three surfaces call, the Typer CLI, the local
FastAPI service with its three guards, the React workbench, and the
end-to-end smoke path that demonstrates them agreeing.
**And, at the gate's close, against the tree the gate's independent
reviewers verified:** the four round-five fixes composed at `9a6319e`, at
**`9381036af0104172f16fe94a6edd2e8cb6d9ae04`**.
**Reviewer:** Claude, the same party that specified the work, dispatched the
implementation and wrote the fixes. **This is not an independent review** —
see "Reviewer independence" below, and the same caveat LC-P1-09's,
LC-P1-10's and LC-P1-11's reviews carry. **The board's rule is discharged by
the gate's independent review**, which covered this work order; see
"Reviewer independence" below.

## The clause

> **Acceptance:** clean clone developer launch with working smoke path; Web
> refresh recovers DB snapshot, no repeated operation; request approval
> cannot be spoofed from another origin; CLI and UI show identical Task
> state.

## Verification actually run

- **The whole suite on the gate's tree**, at the four round-five fixes
  composed in `9a6319e` and verified by the gate's own reviewers at
  **`9381036af0104172f16fe94a6edd2e8cb6d9ae04`**: **3289 passed, 3 skipped and 1 failed**, 29 min 32 s, of
  **3293 collected** — **fourteen more than the previous round's 3279**, and
  the fourteen are the witnesses the gate's round-five fixes added; none was
  removed. **The one failure is not the tree's**: it is the `--basetemp`
  trap the gate's reviewers warn about —
  `tests/test_cli.py::test_a_source_dir_outside_the_workspace_is_refused`
  asserts on a sentence the CLI renders through Rich at `COLUMNS=200`, and a
  long base temp directory pushes the wrap inside the phrase the assertion
  looks for, so **the test is red on the unmutated tree** and says nothing
  about the tree. **This is the gate's reviewers' measurement of that
  commit, and not this review's**: a number belongs to the tree it was
  measured on, so this review's own figure is kept below and the two are not
  merged.
- **The whole suite on the tree that closes the gate**, at the four round-five
  fixes and the gate's final record: **3292 passed and 3 skipped, with no
  failure**, 22 min 46 s, of **3295 collected**. The three skips are the
  same three — a POSIX permission-bit assertion that is meaningless on
  Windows, a provider credential this machine does not have, and a
  Windows-drive assertion that is meaningless on POSIX — and **the tree
  that closes the gate is green**, where the tree the reviewers measured had
  one red that was the `--basetemp` trap and not the tree.
- **The whole suite on the merged tree this review names** (`6035dbf`):
  **3173 passed, 3 skipped**, 990 s, and **no xfails left** — the ingestion
  gap's strict xfail came off with its fix. The three skips are pre-existing
  and explain themselves: a provider credential this machine does not have,
  a POSIX permission-bit assertion that is meaningless on Windows, and a
  Windows drive assertion that is meaningless on POSIX.
- **`ruff check`, `ruff format --check` (258 files), `mypy` (strict —
  *"Success: no issues found in 242 source files"*)
  source files):** clean.
- **Independent mutations written by the reviewer** against the merged
  branches, and not from the branches' own reports:

  | Area | Mutations | Caught | What the survivors were |
  |---|---|---|---|
  | the API's two guards | 7 | 5 | **two were real gaps**: the session guard's **token identity** was never checked by a test — `SessionToken.verify` is the only thing that establishes that a presented token is *this service's* token, and no test presented a wrong one, so replacing `verify(presented)` with `bool(presented)` turned the suite green; and *"the token is read from one place only"* was pinned on `read_bearer`'s **scheme parsing** rather than on **which headers are read**, so reading a second header as well changed nothing |
  | the API's two guards, **re-run against the merged `main`** | 7 | **7** | none — the two gaps are closed: the wrong token is now refused by a named test, and the header set `SessionGuard.read` reads is now watched |
  | the end-to-end demonstration | 6 | 0 | **all six survived**: the demonstration's own checks are load-bearing against *product* defects — if the surfaces disagree, its check fails and the demo exits non-zero — but nothing watches the *check* being narrowed while it still prints its line. Narrowing the field-by-field comparison to **nothing** still printed *"237 field(s) compared, 0 differing"*, and the test file still passed 8/8 |
  | the demonstration, against its **new** shape | 8 | 7 | the one survivor weakens the demonstration's *own* insistence that a control found exactly one difference — **not a gap in the property**, because the line that watches it is the test's own count assertion: weakening the *comparison* makes the count zero and the test fails, while weakening the insistence alone changes nothing. Recorded as a stated limit |
  | the web workbench | 4 | 4 | none — the workbench's own claims are watched: caching the answer so a changed one is never drawn, scheduling the read once so a reload shows a cached copy, leaving the token out of the `Authorization` header, and letting the artefact preview's frame run scripts were each caught by a named test |

  Each surviving mutation was checked **by hand** before it was called a
  finding: the narrowed comparison was applied and the demonstration's own
  output read, not inferred from a red test.
- **The status board's own consistency test** after every change to the
  board, the handoff file and the plan.

## What the review found

Eleven things. Ten of one class — **a property stated and not watched**, or a
capability that did not exist. Each is stated with what it would have let
through, and with where it was fixed.

**The eleventh is not of that class, and it is the one that mattered most.**
It was found by this review and not by either independent reviewer, and it is
recorded here because the gate's exit test is this work order's exit test: **the
demonstration failed after 13:00 UTC**, because it asked for an approval
expiring at a fixed 13:00 and then had the **service** grant it — and the
API's grant route takes no moment, so `granted_at` was the real wall clock.
The ledger's own constraint (`expires_at > granted_at`) correctly refused the
grant. **No CI run had ever run after 13:00**, so nothing had ever caught it,
and the demonstration's own claim that *"nothing in this file reads the wall
clock"* was the thing that hid it: the one place that did read the wall clock
was the one the claim did not cover.

| # | What was found | What it would have let through | Fixed in |
|---|---|---|---|
| 1 | **The service held SQLite's write lock between requests.** Every transaction opens `BEGIN IMMEDIATE`, a read is a transaction too, and the session the service holds lives as long as the process does | the CLI refused with *"database is locked"* while the service ran — **the two surfaces G4's exit test compares could not be used together** | the session per request |
| 2 | **The service shared one database session across concurrent requests.** FastAPI runs a plain `def` handler in a threadpool, and every handler read the same context — and a SQLAlchemy `Session` is not thread-safe. The workbench reads eight paths at once | `403 task_not_found` for a task that existed, a **segfault**, and — worst — `UNIQUE constraint failed: events.task_id, events.seq`, **two threads allocated the same sequence number** | the session per request |
| 3 | **The CLI's `doctor` looked for a token file the service never writes** — `api-token` against `session-token` | the doctor reported no live session while the service was running with its token on disk | one name for one file |
| 4 | **The session guard's token *identity* was never checked by a test.** The only `Authorization` header the API tests sent was the *right* one, so replacing `verify(presented)` with `bool(presented)` turned the suite green | the token would have become *"is a token present"* — and the token is the only barrier between a local process and the store's mutations, because **a local process is not a browser** and can send any `Origin` | a test that presents a wrong token |
| 5 | **"The token is read from one place only" was pinned on the wrong thing** — the test watched `read_bearer`'s *scheme parsing*, not *which headers are read* | a second header could have become a second source of a credential | a test that watches the header set |
| 6 | **Nothing in the repository started the local API service.** `serve()` had no caller, and the web development server proxies to `127.0.0.1:8000` | **the web workbench could not be used at all**, and LC-P1-12's first clause — *"clean clone developer launch"* — had no server in it | `labcairn serve` |
| 7 | **No surface could bind a material to a task.** `create_task` took `bound_source_ids` and nothing ever supplied a non-empty value | a report built from a CLI-made task could carry only **disclosures**, never a **claim** | the ingestion operation, and a CLI command |
| 8 | **The demonstration's own comparisons were unwatched.** Narrowing the field-by-field comparison to *nothing* still printed *"237 field(s) compared, 0 differing"* | the gate's **evidence record** could report a comparison that had not happened | negative controls |
| 9 | **The package's own list of its commands was wrong twice** — it said "Eight commands" and named them, and the number was only ever compared with the reader's memory | a reader who trusted the count was told the wrong thing | the count is gone and a **test compares the list with the application** |
| 10 | **The service's session was shared with the transaction-ending middleware** — a middleware that rolled back the *shared* session was the right idea against the wrong shape | dead code that claimed a mechanism that was no longer the mechanism | the middleware is gone; the session is closed where it is opened |
| 11 | **The demonstration failed after 13:00 UTC, and no CI run had ever run after 13:00.** It asked for an approval expiring at a fixed 13:00 and then had the **service** grant it — and the API's grant route takes no moment, so `granted_at` was the real wall clock. The ledger's own constraint (`expires_at > granted_at`) correctly refused the grant | **the gate's exit test did not run at all** for half of every day, and said so nowhere | the grant outlives any hour |

**None of the ten was found by the work that produced it.** The gate's
independent review of the **report path** — the other half of this gate —
found two defects of the same class *there*, and one of them was **an
acceptance clause of LC-P1-11's own that had not been discharged**: a
report carrying claims and no figure or table could never be marked
`STALE`, because its chain did not name the material and the staleness
walk is one hop. **This review's own acceptance review had passed
LC-P1-11 with notes and missed it.** That is the case for an independent
review: the same party's review has a systematic blind spot.

## Clause 1 — clean clone developer launch with working smoke path

**The demonstration.** `examples/g4_exit_demo.py` makes a temporary
workspace and database **outside the repository** — no network, no
credential — and walks eight steps: `labcairn init`; `labcairn doctor`; a
task with material ingested and bound to it; the layer's `render_report`
producing the document, the manifest and the four forms as revision v1,
recorded in the ledger; the three surfaces compared; a refresh that changes
nothing and repeats nothing; the origin and session guards refusing; and
the material changed, **the repository's own walk** marking the report
`STALE` with its own reason, and a re-render as v2 whose predecessor's
bytes are unchanged. **Sixty checks, exit 0**, and **the figure was
measured, not carried**: the demonstration was run on this tree and printed
*255 field(s), 0 differing* and *60 checks passed*, with no check red. **The
number moves when the tree moves** — a scratch tree with one field added to
the task state printed 256, and one with the manifest's six material
entries removed printed 237, which is where the figure of 237 in this
record's history comes from. The demonstration runs in about fifteen seconds
and the test that runs it in about twenty-one.

**The launch.** `labcairn init` and `labcairn doctor` are driven as
subprocesses, so the demonstration exercises the console script a
developer types rather than an import.

**No network, no credential — and the claims are made carefully.** The
launch is run with every proxy variable pointed at a **closed port**; a
library that honours the proxy variables cannot reach anything through them,
so a launch that succeeded made no outbound request through one. The test
that does this says exactly what it is: *"It is not a proof that no socket
was opened — nothing short of a sandbox proves that — but it is the check the
project's own 'no network' claim can be made against."* The environment is
**scrubbed** rather than merely emptied for the no-credential claim, because
a key inherited from the developer's shell would otherwise make a launch
that needs it look like one that does not.

**What the demonstration says it did not exercise,** in its own output: the
React application was not run in a browser; the API's event stream is not
consumed by the workbench; the workbench cannot switch the selected project,
because the API has no such operation; the DOCX and the PDF are not
byte-reproducible, so their bytes were compared as stored against served
and not across two renders; and a report carrying a claim needs an evidence
record and the anchors it cites, which nothing in the product writes yet.

**That last one is the demonstration standing in for a product operation that
does not exist, and the gate's independent review named it as such.** The
review measured that `evidence.store.append_record` is called from inside
that module and from nowhere else, and that no layer operation writes a
`SourceAnchorRow` — so the demonstration writes the claim's own address and
the record that rests on it itself. The report carries a real claim, cited to
a cell of the material the CLI ingested, but **the claim was made by the
demonstration, not by the product**. That is a limit of the product, not a
defect in the demonstration, and it is a limit of its own kind — the other
three are the event stream, the project selection, and the workbench never
being driven against the live service — so the board records **four**.

**That fourth limit is closed after this acceptance.** The layer now has
`record_claim` and `list_source_addresses`, reached by `labcairn task claim`
and `POST /claims` and by `labcairn sources addresses` and
`GET /sources/{source_id}/addresses`; the outsider walk records its claims
through the operation. The demonstration is unchanged, because it is this
acceptance's record at its commit. The remaining limit is that the claim's
words are the caller's and no surface runs C1, C2 or C3 —
[`LC-P1-14-outsider-path.md`](LC-P1-14-outsider-path.md) §7.3.

**The three things this clause needed, and the three that were missing
when it was first read.**

1. **A server to launch.** `serve()` existed and **nothing called it**, so
   the workbench had nothing to talk to. `labcairn serve` now starts the
   service: loopback only, its own session token written to the workspace and
   never printed, the development server's origin answered to, and the
   port it binds the one its own origin is computed from.
2. **A way to put material in the ledger.** The application layer had no
   ingestion operation, so **no surface could bind a material to a task** and
   a report built from a CLI-made task could carry only disclosures. The
   layer has one now, and the CLI calls it.
3. **A service the CLI can use while it runs.** The service held SQLite's
   write lock between requests and shared one database session across
   concurrent requests, so the two surfaces G4's exit test compares could
   not be used together — and the workbench's first load fires eight
   concurrent requests at it.

**All three are fixed, and the demonstration is run by a test.**

## Clause 2 — Web refresh recovers DB snapshot, no repeated operation

**The refresh.** The workbench **holds no state of its own**: every fact it
shows is the API's answer, read again on every render rather than kept as
the page's own copy, and the reads are scheduled by the render rather than
by a dependency list. A hook that fetched once and kept the result would be
a cached copy, and a cached copy is a second source of truth about the task.

**No repeated operation.** The layer reuses the operation already planned
for a piece of work — a stage run that follows an approval, or that
follows a crash, binds to the operation the approval was bound to, because
two operations for one piece of work would make the audit log say it
happened twice. The demonstration drives it at the surface: an approval is
asked for and granted, and **the same grant again is refused**, so the
operation was applied once; and the ledger holds one grant.

**A note on the evidence's directness.** The web package's tests drive a
**fake at the `fetch` boundary**, so the component, the client, the paths
and the session scheme are exercised exactly as they are in a browser — but
**the real service is never driven by a browser.** The workbench's answers
are typed by the contract generated from the service's own OpenAPI
document, so the shapes agree at compile time, but no value the real
service sends is ever compared with a value the workbench draws. The clause
"CLI and UI show identical Task state" is therefore discharged **through
the API** — the CLI and the service are compared field by field against the
real store, and the UI shows what the service says — and not by a
comparison of the UI with the CLI. This is a stated limit of the evidence,
not a defect in the product.

## Clause 3 — request approval cannot be spoofed from another origin

**Three guards, each with the property stated in its own docstring.**

- **The origin check.** A request whose `Origin` is not the service's own is
  refused, **whatever it asks for** and **even with a valid token** — a
  token is not a pass to a page on another site. The check is on every
  request rather than only on the ones that change something, and a test
  asserts that it covers *every route*.
- **The fetch-metadata rule.** A request that carries **no** `Origin` — a
  browser's subresource load — is judged by the browser's own
  `Sec-Fetch-Site: cross-site` and `Sec-Fetch-Mode`, and refused unless the
  mode is `navigate`. A navigation is something the user did; a subresource
  load is something a page did to the user. A cross-site navigation is
  served, and an allow-listed origin is judged by the origin check alone.
- **The session check.** A request that **changes** something and did not
  present the session token is refused, and a read needs none. The token is
  read from the `Authorization` header only, never from a URL, and each
  service gets its own token.

**What the demonstration shows at the surface:** a foreign origin is refused
with and without a token; a request from the right origin without the token
is refused; and a spent approval is refused.

**Two properties that were stated and not watched**, both found by the
reviewer's own mutations and **not** by the demonstration:

1. **The token's identity was never checked by a test.** The only
   `Authorization` header the API tests ever sent was the *right* token, so
   replacing `SessionToken.verify(presented)` with `bool(presented)` — which
   turns the session check into "is a token present" — turned the suite
   green. **The product was correct**; the observation was missing. It
   matters more than it looks: the origin guard trusts a header that only a
   browser sets honestly, and **a local process is not a browser** — it can
   send any `Origin` it likes. The token is therefore the only barrier
   between a local process and the store's mutations, and the barrier's
   identity check was the part with no test on it.
2. **"The token is read from one place only" was pinned on the wrong
   thing.** The test that appeared to watch it watched `read_bearer`'s
   *scheme parsing* — `"Bearer abc"` → `"abc"`, `"Basic abc"` → `None` —
   and said nothing about **which headers are read**, which is what the
   docstring claims.

## Clause 4 — CLI and UI show identical Task state

**The CLI and the service are compared field by field**, from the same
store: the CLI's `task status --json` against the API's `GET /task`, two
hundred and fifty-five fields, none differing. The comparison is made by
the **test** as well as by the demonstration, because a comparison made
inside the demonstration is a comparison the demonstration could get wrong;
the test asks each surface and compares what comes back, so a product in
which they disagree fails even if the demonstration's own comparison were
narrowed.

**The CLI's contract holds.** `--json` prints the same model the rendered
output draws, byte for byte — the tests compare the JSON against the
layer's own model, not against a transcription of the prose — and the exit
codes are part of the contract: `0` a result, `2` a usage error, `3` a
refusal by the application layer, `1` a crash, so a script tells a refusal
from a crash by the exit code alone.

**The UI shows what the API says**, by construction and by its own tests:
the workbench holds no state of its own, and its own suite changes the
service's answer between reads and looks at the screen again, which is how
"the UI holds no state" is checked rather than asserted.

**One thing the evidence does not do,** stated in clause 2 above: the UI
is never driven against the real service, so the equality is carried
through the API rather than measured between the UI and the CLI.

## The layer is the only way to the store

`test_no_module_outside_the_layer_reaches_past_it` parses every module in
the package and fails if one outside the layer imports the store's readers
or its rows. The exceptions are **recorded in the test**, not tolerated, so
the set is a decision somebody made rather than a drift nobody noticed.

## Reviewer independence

**This record is not an independent review, and it never was going to be
one.** The reviewer specified the work, dispatched the implementation, wrote
the fixes and reviewed them — the same party in all four roles, as with
LC-P1-08, LC-P1-09, LC-P1-10 and LC-P1-11 before it. What the review *can*
claim is that its mutations were written against the merged branches and not
from the branches' own reports, that every surviving mutation was checked by
hand before it was called a finding, and that the findings it reports are
ones it demonstrated by breaking the code and watching a named test fail —
or, in the two cases above, by reading the demonstration's own output and
seeing a claim it had not earned.

**Independence is the gate's business, and the gate discharged it.** The
board's rule is that a row is marked done only when an **independent** review
at a **named commit** says so. **This work order's own acceptance review is
not that review and never was** — it is this work order's evidence, and it
carries the same caveat LC-P1-08's, LC-P1-09's, LC-P1-10's and LC-P1-11's
carry. **The independent review that discharges the rule is the gate's**, it
covered this work order, and the two are **different roles and each is its
own**: this record says what this work order's own review found and fixed;
the gate's review says whether the gate's properties are watched, and it says
so on the strength of mutations written against the tree rather than against
anyone's report.

**How the gate discharged it.** Two reviewers were dispatched for G4, one for
the report path and one for **the three surfaces this work order owns**, and
**neither of them wrote a fix into this repository** — a reviewer that fixes
what it finds has stopped being independent. The fixes were made by other
parties, and **each reviewer was then asked to re-run its own mutations
against them**, which is the second half of the independence: a reviewer that
wrote the fix is no longer a reviewer.

**The three surfaces' review came back BLOCKED**, on two blockers and six
notes, one of the blockers sitting directly under the gate's own exit test —
**and its re-verification came back BLOCKED again**, on **two mutations that
survive**: the witnesses for one of the blockers **had been deleted by this
gate's own composition**, and the demonstration's own comparison of the two
surfaces was unwatched. It was re-verified four more times — **BLOCKED**,
**BLOCKED**, **FAIL**, and **BLOCKED** again at `47259e0`, where the four
fixes in that commit were real and three of them were unwatched.

**Every finding is fixed, and the reviewer re-ran its own mutations against
the fixed code.** The [gate review](G4-acceptance.md) carries the whole
ledger — every round, every mutation count, every finding and the named
witness that holds it — and it names the commit this gate closed on:
**`9381036af0104172f16fe94a6edd2e8cb6d9ae04`**. **The gate is closed, with the verdict PASS WITH NOTES**,
and this work order's row can be marked done on the strength of **that**
review and not of this one.

## Not covered by this review

- **The report path.** LC-P1-11's own acceptance review covers it.
- **What the workbench looks like to a reader.** The renderers' output was
  read back, not read as a person would read it.
- **The browser.** No test drives the workbench in a browser, and the
  demonstration says so.
