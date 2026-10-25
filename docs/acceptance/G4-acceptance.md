# G4 — Gate review

**Gate:** G4 — Usable application. Work orders **LC-P1-11** (report
assembly, export and artefact versioning) and **LC-P1-12** (the Typer CLI
and the local FastAPI + React workbench).
**Exit test:** *"CLI and Web produce same versioned report"*.
**Verdict:** **PASS WITH NOTES** — the gate is closed, and the reasoning is in
[The verdict](#the-verdict) below.
**Reviewed against:** `9381036af0104172f16fe94a6edd2e8cb6d9ae04` — the tree the
gate's independent review measured.

## Why this gate needed a review of its own

The board's rule — `docs/PHASE_1_WORKORDERS.md` — is that **a gate is
closed only when an independent review at a named commit says so**. G3 was
closed that way: a reviewer that wrote **none** of the gate's fixes broke
each of the gate's fourteen fixes in turn, and no mutation survived.

**This review is that review for G4.** Two reviewers were dispatched, one per
scope, and **neither of them wrote a fix into this repository** — a reviewer
that fixes what it finds has stopped being independent. They broke each
property in turn and reported what survived.

**The two work orders' own acceptance reviews were not independent, and this
document says so rather than implying otherwise.** LC-P1-11's review was
written by the party that specified the work, dispatched it, wrote its fixes
and reviewed them — the same party in all four roles. Those reviews are
evidence; they are not this gate's independence.

## The method — mutation checking

For every property the gate claims, the property's implementation is broken
on purpose, one at a time, and the tests that should catch it are run. **A
mutation that survives is a finding**: it means the property is *stated* but
*not watched*.

Three rules make the result trustworthy, and every reviewer was held to
them:

- **A mutation that changes nothing is not a mutation.** If the edit is a
  no-op, that is a finding about the *test*, not a survivor.
- **A mutation whose anchor did not match is not a survivor either.** It
  means nothing was tested.
- **The test's name is reported**, not "the suite went red" — a suite that
  goes red for an unrelated reason proves nothing.

And every surviving mutation was **checked by hand** before it was called a
finding. Two of this review's own findings were found that way — the
reviewer read the demonstration's output and saw a claim it had not earned,
rather than inferring it from a red test.

## What this gate's exit test required, and what it needed

The exit test is *"CLI and Web produce same versioned report"*. Three
things had to be true for it to mean anything:

1. **the three surfaces could be used at all** — the CLI, the local service
   and the workbench;
2. **the comparison had to be of the same report**, byte for byte, and not a
   re-render compared with a re-render;
3. **the comparison had to have happened** — and this is the one that turned
   out to be watchable only with care.

The third is where most of this gate's findings are.

## The findings

Every one of these is a property that was **stated** and **not watched**,
or a claim in a record that had stopped being true. Each is stated with
what it would have let through.

### F1 — the service held the store's write lock, and the CLI and the API refused each other

**Found by:** the gate's own exit demonstration (LC-P1-12's T09), which
drove both surfaces against one workspace and was refused.

**The mechanism**, traced and then **measured** by the reviewer rather than
assumed: `src/labcairn/db/session.py` issues `BEGIN IMMEDIATE` on every
transaction (ADR-0003 C3's deliberate clause, and a **write** transaction
must keep it); the layer's read operations all go through
`context.store.session`, which is **one long-lived `Session`** the service
holds for the life of the process; SQLAlchemy opens a transaction on a
session's first query; and nothing ends that read transaction. A read
transaction issued as `BEGIN IMMEDIATE` takes SQLite's **write** lock.

So **from the service's first read until its next commit, the service held
the write lock** — and a second process, the CLI, was refused with *"database
is locked"*. The reviewer's measurement went further than the report of the
symptom: **the reader blocks another process's write, not only its read**.

**Why it mattered for the gate:** the exit test compares what the CLI and
the API say. The two surfaces that are to be compared could not be used at
the same time.

**Fixed**, with the write path's `BEGIN IMMEDIATE` unchanged and ADR-0003
C3's guarantee intact.

### F2 — the CLI's `doctor` looked for a token file the service never wrote

**Found by:** the same demonstration.

`src/labcairn/cli/workspace.py` read the service's token from
`<workspace>/.labcairn/api-token`; `src/labcairn/api/session.py` wrote it
to `<workspace>/.labcairn/session-token`. **Two names for one file**, so
`labcairn doctor` reported no live session even when the service was running
and its token was on disk.

**Fixed**: one name for one file.

### F3 — nothing in the repository started the local API service

**Found by:** the reviewer, while waiting for the gate's own demonstration.

`src/labcairn/api/app.py` has a `serve(app, *, host, port)` function, and
**nothing called it** — not the CLI, not the web package, not the
demonstration, not the documentation. The web development server proxies the
API to `http://127.0.0.1:8000`, so a developer's intended sequence was
`pnpm dev` plus a service on port 8000, and **no command put the service
there**.

**Why it mattered for the gate:** LC-P1-12's first acceptance clause is
*"clean clone developer launch with working smoke path"*. A launch with no
server in it is not the launch the clause names, and the workbench could not
be used at all.

**Fixed**: a command that starts the service, bound to loopback only, with
the token minted at start-up and never printed.

### F4 — no surface could bind a material to a task, so a report could never carry a claim

**Found by:** the demonstration, and confirmed by the reviewer.

`src/labcairn/application/tasks.py`'s `create_task` takes
`bound_source_ids`, and **nothing anywhere ever supplied a non-empty
value**. The CLI's `task create --source-dir` bound the *directories*. The
application layer had no ingestion operation at all, so no surface could put
a material in the ledger — and a report built from such a task could carry
only **disclosures**, never a **claim**.

**The owner's decision, 2026-10-21: ingestion is in G4's scope.**

**Fixed**: an application-layer operation that ingests through the
permission boundary and binds what it ingested, a CLI command that calls
it, and a demonstration that goes through the surface.

### F5 — the session guard's token **identity** was never checked by a test

**Found by:** the reviewer's own mutations against `src/labcairn/api/guards.py`.

`SessionToken.verify` — `secrets.compare_digest` over the bytes — is the
**only** thing that establishes that a presented token is *this service's*
token. Replacing `verify(presented)` with `bool(presented)` turns the
session check into *"is a token present"*, and **no test in
`tests/test_api.py` failed**: the only `Authorization` header the API tests
ever sent was the **right** token. No test presented a wrong one.

**The product was correct** — the reviewer called the guard directly and a
wrong token was refused. The **observation** was missing.

**Why it mattered:** the origin guard trusts a header that only a browser
sets honestly, and **a local process is not a browser** — it can send any
`Origin` it likes. The token is therefore the only barrier between a local
process and the store's mutations, and the barrier's identity check was the
part with no test on it. The clause *"a local authenticated session/token
even if launched on loopback"* rested on it.

**Fixed**: a test that presents a wrong token, at the service level, through
a request.

### F6 — "the token is read from one place only" was pinned on the wrong thing

**Found by:** the same mutations.

`SessionGuard.read`'s docstring says *"The only reading of the
`Authorization` header in the service, so there is one place to look when
asking where a token could come from."* The test that appeared to watch it
watched `read_bearer`'s **scheme parsing** — `"Bearer abc"` → `"abc"`,
`"Basic abc"` → `None` — and said nothing about **which headers are read**.
Reading a second header as well changed nothing.

**Fixed**: a test that the token is read from the `Authorization` header and
from nowhere else.

### F7 — the demonstration's own checks were unwatched

**Found by:** the reviewer's own mutations against
`examples/g4_exit_demo.py`. **All six survived.**

The demonstration's checks are load-bearing against **product** defects: if
the surfaces disagree, its check fails and the demonstration exits non-zero,
which the tests catch. What was unwatched was the **check being narrowed
while it still printing its line**. The reviewer verified it by hand rather
than inferring it from a red test: with the field-by-field comparison
narrowed to **nothing** — `if False` — the demonstration still printed

```
[ok] the CLI's task state and the API's task document are the same, field by field  - 237 field(s) compared
  compared   : 237 field(s), 0 differing
```

**a claim about 237 fields it had not compared**, and the test file still
passed 8/8.

**Why it mattered:** the demonstration's output *is* the gate's evidence
record. A gate review citing "237 field(s) compared, 0 differing" would be
citing a number the demonstration was free to print without doing the work.

**Fixed** by **negative controls**: the demonstration now shows that its
comparators **can fail** — it plants a difference and asserts the comparison
finds it — and the test witnesses that the control ran and found it.

### F8 — one of the demonstration's own xfails was passing for the wrong reason

**Found by:** the reviewer fixing F1.

The xfail that stood for F1 was supposed to demonstrate that the service
held the lock. Its probe issued **two** `BEGIN IMMEDIATE`s — the engine's
`begin` event fires on the connection's autobegin, and the test's own
explicit `BEGIN IMMEDIATE` landed inside it — and died with *"cannot start
a transaction within a transaction"*, **with no service running at all**. It
also never made the service touch the store.

**A test that xfails for the wrong reason is worse than no test**: it is
green, and it proves nothing about the defect it names. The reviewer's own
earlier claim that the xfails "confirmed the defects are real" was true only
at the level of the marker, and this one did not even reach the defect.

**Fixed**: the probe now means what its name says.

### F9 — three subprocesses in the packaging test could hang a CI job for six hours

**Found by:** the reviewer, while measuring a CI job it had first misread.

`tests/test_no_reference_leakage.py` runs a **real** `uv build`, a real `uv
venv` and a real `uv pip install` — the module's point is that *"not
packaged"* is proven by reading real archive members. **Three of its six
subprocess calls reach the network, and none had a timeout.** A fetch that
stalled on a runner held the job until GitHub's six-hour limit: no output,
no failure, and nothing in the log saying what was waiting for.

**Fixed**: a ceiling on every subprocess in the module, and a timeout
reported as a **named failure** rather than as an hour of a runner.

### F10 — eight records had rotted, and two of them were false sentences

**Found by:** the records refresh, and by the reviewer reading the documents
the refresh was scoped out of.

`README.md` said *"there is no server and no research feature to use yet"*
and that the local API and the web workbench *"will call"* the application
layer. **ADR-0012** said the renderer *"does not exist yet"*, that the
hostile-`matplotlibrc` risk was *"designed against, not measured"*, and that
*"no figure has been produced yet"*. **ADR-0013** said the export libraries
were *"not in `pyproject.toml` or `uv.lock`"*, that the Markdown escape
table was *"specified, not written"*, and that *"no report has been
exported yet"*. **ADR-0009** said LC-P1-08 *"does not exist yet"*.

**Fixed**, each correction keeping the ADR's own purpose — what the decision
fixed and what it did not — and saying what is true now.

### F11 — this review's own acceptance review quoted a red run as a green one

**Found by:** the reviewer, re-measuring its own figures.

LC-P1-11's acceptance review quoted *"2720 passed, 2 skipped, 386 s (exit
0)"*. The run it came from reported **1 failed** — and the exit code had
been read off a pipe, so it was the pipe's and not pytest's. The suite on
the merged `main` is **3050 passed, 3 skipped**.

**A review that quotes a measured number has to re-measure it against the
commit it names.** This one did not, and the correction is in the document
rather than left to a reader who diffs it later. The review's mutation table
was re-run at the same time, against the merged `main`, and every mutation
was caught again — which also closed a gap in the reviewer's own
bookkeeping: T13's seventh mutation, the `artifact_recorded` event, had
never been written down, so it was written rather than the count being
edited down.

### F12 — the service shared one database session across concurrent requests, and the process could crash

**Found by:** the reviewer, after the defect-fixing agent reported that the
service shares **one** `Session` across requests while FastAPI runs its sync
handlers in a threadpool — and that SQLAlchemy sessions are not thread-safe.

**The reviewer measured it against the real service**, not a mock and not the
web package's fake: eight concurrent reads, fifty rounds.

- **Sequential reads: all eight return 200.** The task is there.
- **Concurrent reads: `403 task_not_found` — "no Task row for 01a15b5b-…" —
  for a task that exists.** Another thread's rollback had discarded this
  thread's read.
- **And the process segfaulted.** The SQLite C driver used from two threads
  at once.
- **The control is decisive:** the same fifty rounds, serialised by a
  `threading.Lock` around the request, had **zero failures**. The shared
  session is the cause, and nothing else is.

**Why every test in the repository missed it:** the web package's tests
drive a **fake at the `fetch` boundary**; the API's own tests use
`TestClient`, which is **sequential**; and the end-to-end demonstration
makes **sequential** requests. **Nothing drove the real service
concurrently** — and the workbench's first load does exactly that, firing
eight paths at once through `Promise.all`.

**And it was visible to a user, not only to a test.** While the service
held the lock, `labcairn task status` against the same workspace died with
an **unhandled `OperationalError`, a Rich traceback and exit code 1**. The
CLI's own contract reads that situation correctly — a refusal is rendered
and carries `EXIT_REFUSED`, and *anything else that fails is a bug* — but a
database locked by another process is neither a refusal nor a bug in the
program, and **the two surfaces that G4's exit test compares could not be
used together at all.**

**Why it matters for the gate:** G4's exit test is about the surfaces
agreeing, and the workbench is one of them. A service that loses the task
row and dies under the workbench's first load is not a surface that can be
demonstrated.

**Fixed** by giving **each request its own session** — the service holds the
engine, the session factory and the request-independent facts, and every
request opens and closes its own — with the event stream owning a session
for its own life. The alternative that the reviewer's own control had
proved workable, a **lock around each request**, was rejected: the
server-sent-event stream with `follow=true` never ends and polls the store
every quarter-second, so a request-level lock would be held for the life of
the connection and the service would be dead to everything else while one
stream was open.

**And the corruption was worse than a wrong answer.** The fix's own
regression test, run against the unmodified base, failed with
`sqlite3.IntegrityError: UNIQUE constraint failed: events.task_id,
events.seq` — **two threads allocated the same sequence number.** That is
the event log's own counter being handed out twice, which is not a wrong
answer but a **corrupt ledger**. The same test's other assertion failed
with *"the concurrent burst did not survive: exit 3221225477,
STATUS_ACCESS_VIOLATION (0xC0000005), the Windows name for a
segmentation fault."*

**The reviewer's own reproduction, run against the fix:** eight concurrent
reads all 200; **fifty rounds of eight concurrent reads with no failure**;
the session left holding no transaction; exit 0.

**And the regression test drives the real service concurrently**, in a
subprocess — a segfault in the C extension takes the whole pytest process
with it, and a CI job that dies with a signal has a log that says nothing.

### F17 — the package's own list of its commands was wrong, twice, and a number cannot be checked

`src/labcairn/cli/__init__.py` said *"Eight commands — `init`, `doctor`, … — and
the plumbing they share"* and named them. It was right when it was written and
wrong **twice over** after two more commands arrived — `serve` and
`sources ingest` — and **nothing noticed**, because a number in a docstring is
only ever compared with the reader's memory, and it was read as "Eight" long
after it had stopped being true.

**The count is gone and the list is the claim.** A test now compares the
names the docstring gives with the commands the console script registers, in
both directions, so a command that arrives without being named fails there
and a name that no longer names a command fails there too. **The test was
proved to fail** — removing one name from the list turns it red.

### F18 — the mechanism that fixed the write lock became dead code

The two-defects fix ended the *shared* session's transaction after each
request. The per-request session **superseded it**: with a session per
request there is no shared transaction to end, and the middleware went on
rolling back a session nobody used — **dead code whose docstring described a
mechanism that was no longer the mechanism.** It is gone, and the account in
`api/app.py` now describes what actually happens.

### F19 — the material walk recorded a path the model says is not one

`Source.relative_path` is **workspace-relative** — the contract the model
states and the one the layer's readers resolve against the workspace root.
**The walk wrote the key it was given, and that key is root-relative.** So a
row the walk wrote resolved into the wrong root, the `source.inventory`
capability **refused it**, and *a material ingested through the walk could
not be listed or inspected at all*. And because `sources.relative_path` is
UNIQUE and root-relative paths are not unique across roots, **two source
roots each holding `notes.md` collided** and the second failed to ingest.

The ingestion operation added for LC-P1-12 compensates — it walks one root at
a time and moves each root's rows to the contract's path — and its own
docstring says the fix belongs in the walk and that the compensation was
written to become a no-op once it does. **Fixed in the walk**, and the
compensation is now a no-op.

### F20 — G3's accepted code states a narrower contract than the walk keeps

`recovery/resume.py`'s `invalidate_on_source_change` says the walk matches a
`MATERIAL_FILE` citation, while `_derives_from`'s own contract is *"any
derivation that carries a hash"*. **The report's material link is a `SOURCE`
link**, so the report's invalidation relies on the broader contract while the
docstring says the narrower one. **G3's file, and not touched** — the
contract that matters is the one `_derives_from` states, and the two agree in
behaviour.

### F21 — a read still takes SQLite's write lock, and the window is now one request

`db/session.py` opens **every** transaction with `BEGIN IMMEDIATE` — ADR-0003
C3's clause, and the right one for a write. **A read is a transaction too**,
so a read takes SQLite's **write** lock for as long as it is open. The
per-request session bounds that window to one request, where before it was
the life of the process; but it does not remove it, and the code's own
comment — *"Readers do not block the writer"* — is true of WAL and **not of
the application's own reads**.

**The proper fix is a read connection whose transactions are deferred**, so a
read is a reader and WAL does the rest. That is a change to `db/session.py`
and to the store's readers, and it was considered and **not taken** while
the gate was closing: it is structural, it re-opens G2's accepted code, and
nothing about the gate's exit test needs it. **It is a stated limit, not a
defect** — a request in flight can still refuse a writer, for the length of
that request.

### F22 — a stated limit: the demonstration's own insistence is a second line of defence that no test watches

**The reviewer's own mutations against the demonstration's new shape: eight, seven caught.** Neutering the field comparison, removing the difference it is given, dropping the file on disk from the byte comparison, and skipping any of the six controls — each is caught by a named test.

**The one that survived** weakens the demonstration's *own* insistence that the field control found exactly one difference (`len(planted) == 1` → `len(planted) >= 0`). It is not caught, and **it is not a gap in the property either**: the property is *"a comparison that compares nothing cannot pass unnoticed"*, and the line that watches it is **the test's own count assertion** — the test requires the demonstration to report exactly one difference found. Weakening the comparison makes the count zero and the test fails; weakening the demonstration's insistence alone changes nothing, because the comparison still works and the test still reads the same count.

**So the demonstration's insistence is redundant with the test's assertion, and it is the second of the two that nothing watches.** The cost is small and stated: the demonstration could print *"ok"* for a control that found nothing, and the suite would still go red on the other assertion. A defect of the same shape as the ones this gate has been finding all night, and recorded rather than left to be discovered.

### F23 — a ledger written before the walk's fix still holds the old spelling

The walk now records the path the contract names. **A row written before the
fix still holds the root-relative spelling**, so that material is still
unlistable — and it is still *findable*, because the source id did not move,
so the next ingestion finds the old row and puts it right.

**In Phase 1 there are no ledgers to migrate** — the product has no users yet
— so this is a note rather than a migration. It is recorded because the
alternative would have been to move the id with the path, and **that would
have orphaned the recorded text, the recorded hash and the drift detection
that reads them**, which is the one thing the fix must not do.

### F24 — the store alone never repairs a row's path

`db/materials.py::put_source` does not update `relative_path` when it
refreshes a row. So a ledger written before F19's fix keeps the old spelling
**until the ingestion operation relocates it** — the store on its own never
does. **The ingestion operation is what repairs it**, and it can find the row
only because the source id did not move.

### F25 — a source root that is the workspace root yields nothing, and says nothing

`Workspace.bind` accepts a source root that **is** the workspace root. The
permission boundary then refuses the listing — **correctly**, since the
workspace root is not a source root — and the walk ingests nothing, with
`WalkReport.failures` **empty**. The boundary's refusal is right; the silence
is in the *report* of it. The CLI's own output says zero files, so a person
would see it; **a caller reading the report would not.**

### F26 — a failure key does not say which root it came from

`WalkReport.failures` and `WalkReport.skipped` carry the **root-relative**
key, and with two source roots a failure key does not say which root it came
from. **Deliberate** — the defect F19 was about the *recorded* path, not the
report's keys — and recorded rather than left to be discovered.

### F27 — a refusal the fix itself introduced, and nobody watches

`reports/manifest.py::_the_material` refuses a report that **cites the same
source twice with different bytes**. It is **reachable** — the model accepts
such a document — and **load-bearing**: without it, the chain names the
source with one of the two hashes and **silently drops the other**. **No test
observes it.** The independent reviewer's sweep of all ninety-nine refusal
branches in Scope A finds three unwatched: this one, and two it confirms
**cannot fail** — a part's receipt looked up in the same ledger the builder
read it from.

### F28 — the clause "numeric values agree with the ledger" is witnessed for one of the four forms

**An acceptance clause, and the evidence for it is one form's worth.**
`test_no_number_appears_that_the_model_does_not_hold` **reads the PDF**. The
reviewer mutated the **HTML**, the **DOCX** and the **Markdown** so that
each carried **a number the model does not hold** — **all three survive.**

**The product enforces the clause once and centrally**, on the document,
before the first byte is rendered, and the four forms are drawn from that one
document. So the clause is not violated; **what is unwatched is that each
form carries the document's numbers** — a renderer that drew a number of its
own, or mis-mapped one, would put a number in the report that the model does
not hold, and nothing would notice for three of the four forms.

**Fixed** by a test that renders **all four** forms and asserts each carries
exactly the model's numbers, each read back the way its own test reads it
back.

### F29 — the DOCX and the PDF are not compared with the canonical document

**The third time the same shape appeared, and the last one open.** "The four
forms are four renderings of one model" is the `render/` package's own reason
to exist, and the layer's docstring says the forms are rendered *"from the
document this operation just built"*. **The layer's own test
`test_the_four_forms_are_drawn_from_the_canonical_document` compares the
canonical document with the Markdown and the HTML — and with nothing else.**

**Four mutations, all surviving:** the PDF says a different moment than the
document; the DOCX says a different moment; the PDF names no records at all;
the DOCX names no records at all. **They are not no-ops** — the reviewer read
the export back with the mutation applied and saw the difference in the file
a reader opens.

**Why nothing noticed:** the two lines at issue are the **snapshot** — the
moment the report is a view of — and the **records** the report names. Neither
is in `EXPECTED_LINES`, which is what `test_the_four_forms_say_the_same_words`
checks in all four forms. **The one test that does compare a form with the
canonical document stops at two forms.**

**A verification gap, not a live defect** — all four renderers draw from the
same `resolve(document)` walk, so the product says the right thing today, and
making a form carry a wrong value takes a change *to the renderer*, which no
renderer makes. **The test is a lock, not a repair.**

### The independent reviewer's own findings — Scope A, the report path

The reviewer of Scope A wrote **no fix** into the repository, which is what
makes the review independent, and it left its mutation scripts and probes
outside it, at `C:\Users\pc\AppData\Local\Temp\g4rev\`, so that whoever
fixed the findings could re-run the exact things that produced the report.

**Its property table was clean: fifty mutations for A1–A21, fifty caught,
each by a named test.** The four defect classes this gate had already been
bitten by — the PDF's double escape, the escape table's unpinned set,
overstating a verification state, and the manifest writer's dropped
parameters — are closed and pinned. **Its verdict was FAIL anyway**, and
narrowly: not on the property table, but on two open defects and five
unwatched refusals.

#### F13 — a report that carries claims and no figure or table cannot be marked stale when its material moves

**This one is an acceptance clause.** LC-P1-11's *"Re-rendering after
material change invalidates stale output"* is **not discharged for that
shape**, and the owner's §1.4.5 decision is not honoured.

The report's chain reaches the material **only through the report's figure
and table artefacts**: `application/reports.py::_the_upstreams` maps *parts*
to their receipts' `derived_from`, and `_the_parts` returns only figures
and tables. A task with evidence records but no analysis artefacts
therefore produces a report whose `derived_from` names nothing but the
report's own files. And the staleness walk is **one hop** — so such a
report **can never be marked `STALE`**. The reviewer's probe printed:

```
the material's hash appears in the chain: False
… and for all six receipts: holds the material's hash: False
```

**Why nothing noticed:** every staleness test builds a document that has
**both a figure and a table**; the shape *"claims, no figure, no table"* is
never built.

**Three places state the opposite, and they are right to** — two docstrings
in `reports/revisions.py` and `application/reports.py`, and the owner's
decision.

**The fact that is there but is not where the walk looks:** the material's
hash **is** in the report's canonical document. **The document carries the
fact; the receipt does not, and the receipt is where staleness lives.**

**Fixed** so that the material's hash reaches the report's **own**
`derived_from` for a report with no parts as well as one with — and **the
owner's fifth decision kept**: a flat ancestor closure, the material's hash
**directly** in the chain, because the walk is one hop.

**The reviewer's own probe, re-run by the reviewer against the fix:**
*"the material's hash appears in the chain: **False**"* became **True**, for
all six receipts.

#### F14 — a figure's caption or interpretation can open an indented code block in the Markdown form

**The same shape as the double-escape defect this gate already fixed: a
source-level assertion was true, and only reading the rendered text back
found the failure.**

CommonMark opens an **indented code block** with four spaces or a tab at
the start of a line that follows a blank line. The escape table covers
punctuation; **whitespace is not covered**. `_protect_leading_indent`
protects only the **leading** indent, and a figure's caption and
interpretation are the two values that reach the file at the start of a
line — neither protected against an **internal** blank line.

The reviewer's probe printed a caption containing `"\n\n    "`, carried it
through the builder into the document, and read the parsed Markdown back:
`code_block token: True`.

**Two docstrings in `render/markdown.py` assert that it cannot** — *"a
caption, a claim and a citation are prefixed by the writer and cannot open
one"* — and a caption is prefixed on its **first** line only.

**Fixed**, with the rendered Markdown **parsed back** and the parsed
document asserted to carry no code block the text opened — the same
read-back discipline the escape table's own test already uses, applied to
whitespace. **The reviewer's own probe, re-run against the fix:**
*"code_block token: **True**"* became **False**, and the offending four
spaces are now written as `&#32;&#32;&#32;&#32;`.

The two docstrings that said a caption "cannot open one" were corrected
whichever way the fix went — **a docstring that claims a boundary the code
does not enforce is a finding of its own.**

#### F15 — five refusals the suite never exercised

Each a guard the code states and no test observes. The reviewer proved each
mutation real — not a no-op — with a probe that printed **FIRE** on the
pristine tree and **SILENT** on the mutated one.

| Id | The guard | Where |
|---|---|---|
| B1 | two artefacts at one path at one revision are refused | `reports/build.py::_current_artifacts` |
| B2 | one path claimed by two artefact kinds is refused | `reports/build.py::_current_artifacts` |
| B3 | the figure's chain and the manifest artefact must agree about the manifest | `reports/build.py::_figure_for` |
| B4 | a caption or interpretation naming a non-figure is refused | `reports/build.py::_refuse_readings_that_no_figure_names` |
| B9 | a figure's chain must name exactly one manifest — **without the guard the builder raises `IndexError` where it should raise a named refusal** | `reports/build.py::_manifest_receipt_for` |

**Why nothing noticed:** none of the five refusal messages appears anywhere
under `tests/`. The build test file exercises the *neighbouring* refusals —
no caption, no manifest, two artefacts with one receipt id — but not these.

**Fixed**, and the sweep the reviewer did was carried further: **every
refusal branch in the modules in scope was mutated, one at a time — 98
branches, 66 watched, 32 unwatched.** Thirty of the thirty-two now have a
named test; the two left are a part's receipt looked up in the same ledger
the builder read it from, and **they cannot fail**. The reviewer's five are
among the thirty, and so are **twenty-seven more the reviewer had not
found** — which closes the limit the reviewer named for its own sweep.

**The reviewer's own probe, re-run against the fix:** b1, b2, b3, b4, b5 and
b9 all still **FIRE**. The guards stand.

#### F16 — the DOCX's creation date is only right in UTC

`reports/render/docx.py` says *"The creation and modification dates are set
to the moment the report is a view of"*. python-docx writes
`strftime('%Y-%m-%dT%H:%M:%SZ')`, so an aware datetime of
`2026-01-01T12:00:00+08:00` is written as `2026-01-01T12:00:00Z` — **eight
hours wrong**.

The product's default (`datetime.now(UTC)`) is unaffected, so this is not a
live wrong answer — **but the docstring holds only under an unstated
condition, and no test observes the dates at all.**

**Fixed**: the moment is converted to UTC before python-docx writes it, and
**a test observes the dates for the first time** — "no test observes the
dates at all" was the finding.

### The independent reviewer's own verdict, and what this gate did with it

**The reviewer's own report is a document outside this repository** — as
G3's was — and what it holds is recorded here, so that the review the gate
closes on can be read in the repository.

**The Scope A review's verdict was FAIL, with a clean property table.** Fifty
mutations for A1–A21, **fifty caught, each by a named test** — and the four
things above open, outside the table. Its own words: *"If the scope were
only that, this would be a PASS."*

**The fixes were made by someone else** — the review wrote no fix into the
repository, which is what makes it independent — and **the reviewer was
asked to re-review its own findings.** That is the second half of the
independence: a reviewer that wrote the fix is no longer a reviewer.

**What "independent" means here, in the repository's own words.**
`docs/README.md` is explicit: *"Two-layer review is internal cross-verification,
not external independent audit. Where older acceptance records say
'independent review', they mean 'a reviewer who did not implement the work' —
independent of the implementation, not of the project. The two senses must not
be confused: an internal reviewer is not an external auditor."* **These two
reviewers are sub-agents that wrote none of G4's fixes** — independent of the
implementation in the sense the repository means, **and nothing more than
that.** Neither layer substitutes for an outside auditor, and this document
does not describe one.

#### And a number three records had wrong

The reviewer's §5.1: the escape table holds **eighteen** characters, and
this gate's records said **nineteen** — the review's own miscount, repeated
in the status board, in ADR-0013 and in the LC-P1-11 acceptance review. **The
set is complete** (the fourteen unlisted ASCII punctuation characters open no
structure, checked against seven attack shapes each), so the defect the
reviews reported was the *unpinned* characters, not a missing one. Corrected
in all four places.

## Verification actually run

- **The whole suite on the merged tree this review names** (`6035dbf`):
  **3173 passed, 3 skipped**, 990 s, and **no xfails left**. The three
  skips are pre-existing and explain themselves: a provider credential this
  machine does not have, a POSIX permission-bit assertion that is
  meaningless on Windows, and a Windows drive assertion that is meaningless
  on POSIX.
- **The three surfaces' own reviewer, at `6035dbf`:** `ruff check` clean ·
  `ruff format --check` 259 files already formatted · `mypy` (strict) clean,
  242 source files · the whole suite **3173 passed, 3 skipped**, exit 0,
  1024 s · the web package `pnpm lint` clean, `pnpm typecheck` clean,
  `pnpm test` **62 passed**, `pnpm build` succeeded · `uv run python
  examples/g4_exit_demo.py` exits 0 with **54 checks**.
- **`ruff check`, `ruff format --check` (258 files), `mypy` (strict —
  *"Success: no issues found in 242 source files"*):** clean.
- **The merged tree this gate closes on, at `5dcd6d0` — the commit the
  independent reviewers verified:** `ruff check` **All checks
  passed** · `ruff format --check` **260 files already formatted** · `mypy`
  (strict) **"Success: no issues found in 243 source files"** · the whole
  suite **3216 passed, 3 skipped** on Windows (42 min) and **3195 passed, 24
  skipped** on Ubuntu (13 min), of **3219 collected** — the difference is the
  platform and nothing else: on Windows the three skips are a provider
  credential this machine does not have, a POSIX permission-bit assertion, and
  a Windows drive assertion; on Ubuntu the twenty-four are that same
  credential and **twenty-three assertions that are Windows-specific** —
  nineteen on Windows path semantics, two on junction creation, two on
  directory junctions · `uv run python examples/g4_exit_demo.py`
  exits 0 with **60 checks** and prints *"255 field(s) compared, 0
  differing"*.
- **The reviewer's own mutations, re-run by the reviewer against the fixed
  code:** every one of the fifty property mutations **still caught**, and
  **no property that used to be caught had stopped being caught** — which is
  the thing a fix can quietly break.
- **The reviewer's own end-to-end staleness probe**, which is not the
  fixer's test: it writes a claims-only revision, changes the source, and
  runs the repository's own walk. **Before the fix: `stale artefact ids: []` —
  "CURRENT, the defect". After: all six receipts stale.**
- **The executing agent's own mutations,** re-run against the merged `main`:
  the API's two guards, **seven of seven caught**; the demonstration against
  its new shape, **eight of seven caught** (the survivor is the
  demonstration's own insistence, which the test's count assertion already
  watches — F22); the material walk's recorded path, **five of five
  caught**; and the two defects' own properties, **six of six caught**.
- **A failure this review caused, and the fix for it.** Drafting this
  document and the records that go with it made
  `tests/test_status_consistency.py::test_a_closed_gate_has_no_unaccepted_work_order`
  **fail**, for both `CURRENT.md` and the plan: the drafts say the gate is
  closed while the board's own work-order rows still read `IN PROGRESS`.
  **The failure was the project's own guard doing its job** — a record that
  announces a closed gate before the gate is closed is exactly the defect
  this board exists to prevent. With the drafts set aside, the same file's
  **119 tests all pass**. **The lesson is recorded rather than quietly
  corrected: the records are finalised only after both reviews have returned
  and the fixes have merged, and the work-order rows are changed in the same
  commit as the gate's status.**

## The independent reviewers

### Scope A — the report path

**Reviewed at `15344b4`** by a reviewer that wrote **no fix** into this
repository. Its mutation scripts and probes were left outside it, at
`C:\Users\pc\labcairn-g4\g4rev-probes\`, so that whoever fixed the
findings could re-run the exact things that produced the report.

**Its property table was clean: fifty mutations for A1–A21, fifty caught,
each by a named test.** The four defect classes this gate had already been
bitten by — the PDF's double escape, the escape table's unpinned set,
overstating a verification state, and the manifest writer's dropped
parameters — are closed and pinned.

| Subtask | Properties | Mutations | Caught | Survivors |
|---|---|---|---|---|
| the report's document model | A1 | 10 | 10 | none |
| the four renderers | A2 | 4 | 4 | none |
| the Markdown escape table | A3 | 2 | 2 | none |
| the artefact manifest | A4–A7 | 5 | 5 | none |
| the revisions and the staleness | A8 | 2 | 2 | none |
| the content checks | A9–A15 | 7 | 7 | none |
| the document builder | A16–A19 | 9 | 9 | none |
| the layer's report operation | A20–A21 | 4 | 4 | none |
| **the refusals it hunted for beyond the table** | B1–B9 | 9 | 4 | **five** — B1, B2, B3, B4, B9 (§3.3 above) |

**Its verdict was FAIL**, and narrowly: not on the property table, but on
**two open defects** (F13, F14), **five unwatched refusals** (F15) and one
**unstated condition** (F16). Its own words: *"If the scope were only that,
this would be a PASS."*

**The no-ops it listed separately**, so they are not mistaken for survivors:
one mutation whose anchor had eight spaces of indentation where it had
twelve (**nothing was tested**); one that left an empty `if` body and
broke collection (**a false survivor from a broken edit**); one that
deleted an assignment and failed 196 tests; and four that survived because
the guard they removed is **redundant defence in depth** — the neighbouring
guard refuses the same state first. **A survivor that is not a survivor is
still worth naming**, and the reviewer named it.

**Its caveat about its own sweep:** *"There may be further guards whose
messages do appear in the tests but whose branches are not distinguished by
the match string; I did not exhaustively enumerate those."* The fix carried
that sweep further.

### Scope A — the report path, re-reviewed after the fixes

**The verdict: FAIL**, on the report path, at `25bad72`. **It is not a verdict
on the gate** — the gate's exit test is Scope B's.

**It is the third FAIL on this scope, and the reason is the same each time:
the property table can be entirely clean and the review still fail.** The first
was two open defects and five unwatched refusals; the second was one unwatched
refusal the first fix had introduced, and an acceptance clause witnessed for
one of the four forms. **This one is fourteen surviving mutations.**

**One hundred and sixteen mutations** were measured against the report path at
`25bad72` — **102 caught by a named test, 14 survived, 0 measured nothing.**

| Property broken | Mutations | Caught | Survivors |
|---|---|---|---|
| §2.3 "the renderers draw; they do not decide" | 4 | 0 | **Q8, Q9, Q10, Q11** |
| "the four forms are drawn from the canonical document" (the layer's wiring) | 8 | 3 | **Q16, Q17, Q20, Q21, Q23** |
| "a form carries the document's section heading" | 5 | 3 | **Q13, Q15** |
| the fix's own comparison (moments compared as a set) | 1 | 0 | **Q12** |
| the layer's two part-refusals | 2 | 0 | **B6, B7** — both **measured unable to fire** |
| every other property (A1–A21, B, F, N, P, X) | 96 | 96 | none |

**The finding that decides it: the fix under review generalised the comparison
of the four forms from two forms to four — for two of the document's claims
(the moment and the record ids) — and left every other claim where it was.**
**The one-form/two-form pattern that F29 was about survives in a new shape.**

**What the survivors would have let through, in the reviewer's words:**

- **Q8–Q11 — a renderer may compose prose of its own.** One line added to
  each of the four renderers, appending *"The catalyst therefore did not
  improve the yield."* It would have let through **a report carrying a finding
  the ledger does not support** — here the negation of the model's own
  finding, which the same document also states as *"The catalyst therefore
  improves yield."* **Why the suite misses it:** the only "nothing extra"
  check is `test_no_number_appears_that_the_model_does_not_hold`, which
  matches `\d+\.\d+`. The sentence has no decimal point. **Every other
  comparison in the suite is *containment* — the model's line is in the form —
  never *absence*.**
- **Q16, Q17, Q20, Q21, Q23 — the layer's wiring is unwatched for the DOCX
  and the PDF.** `_the_four_forms` renders one form from a document that is
  not the canonical one; the caption is changed, or the interpretation is
  changed **to the opposite conclusion**, leaving the moment and the record
  ids alone so the fix's own comparison cannot see it. It would have let
  through **a DOCX or a PDF that contradicts the canonical document.** The
  controls that make this a finding rather than a method artefact: Q18
  (Markdown, same mutation, same place) CAUGHT by two named tests; Q19
  (HTML, caption) CAUGHT by one; Q22 (Markdown, conclusion) CAUGHT by one;
  **Q23 (HTML, conclusion) SURVIVED.** So the layer's test compares the
  moment and the record ids in all four forms, the caption in the Markdown
  and the HTML, and the interpretation in the Markdown only — **and nothing
  about the heading, the claims' statements, the narrative, the artefact line,
  the table's line or the footnote's line in any form.**
- **Q13, Q15 — a form may carry a heading that is not the document's.** The
  shared resolver draws "Results" instead of the document's "Findings", or
  the Markdown alone does. **Honest scope:** the heading's *presence and
  escaping* are watched in all four forms, so what this would let through is a
  defect conditioned on the heading's *value*. The control **Q14** (the title,
  same place, same method) is CAUGHT by four named tests, so the method is
  sound and the difference is the property.
- **Q12 — the moment comparison reads a set, so a duplicate is invisible.** The
  DOCX states the moment twice. It would have let through a form stating the
  right moment twice; **it does not let through a wrong moment.** This
  characterises the fix's comparison, not the product's output.

**The reviewer's honest ledger, which is part of the result.** Two anchors
that missed and tested nothing, both re-run with the correct anchors and both
CAUGHT. One survivor that was not one — a mutation that left the module
syntactically invalid, and the driver read the collection error as a
survival. And **a mutation caught by an accident of placement**: Q1–Q5 are
caught by the *escaping* tests, which say "the hostile text is missing", not
"the form carries the document's heading"; Q13 and Q15 are the same mutations
in a **neutral place**, and they **survive**. **It reported the accident
rather than the convenient result**, and re-ran it where the accident could
not happen.

**Two methods it discarded, and why:** plain file copies of the tree — not
hermetic, because the suite reads the git checkout for the board's SHAs, the
tracked PDF fixtures and the repo-root guard; and its own first attempt under
the machine's system Python (3.10), where `datetime.UTC` does not exist, so
it died with an `ImportError` before measuring anything.

**The two refusals at `application/reports.py:725` and `:733` are still
unreachable at `25bad72`, and the fix did not change them** — the fix touched
only test files, so `reports.py` is byte-identical. **"Byte-identical" is an
argument, so the measurement was repeated by two independent methods:**
instrumentation over the whole suite (the condition never became true, twice)
and mutation (B6 and B7 remove those refusals outright; the whole Scope A
suite passed). A report that says *"defence in depth with no test, and not
reachable"* is therefore true at the commit the gate names.

**The baseline it measured, and the cause of the twelve failures.** The whole
suite: **12 failed, 3162 passed, 3 skipped** — and **all twelve are in
`tests/test_smoke_path.py`, with one cause: the hard-coded clock in the exit
demonstration** (F39 below). The reviewer confirmed the same twelve in a
clean `git clone --shared` at the same commit. **This is a real, reproducible
defect at `25bad72` — in the exit demonstration, not in the report path.**
### Scope A — the re-verification at `5dcd6d0`

**The verdict was FAIL, with eight mutations surviving.** The reason is the
same one the three earlier FAILs on this scope had, and it is the gate's own
bar: **a mutation survived.** And the reason is the same one too — **a
property table can be entirely clean and the review still fail.**

**The fix was a real and large improvement, and that is on the record before
the failures: thirteen of the previous round's fourteen survivors are now
caught by named tests, the generalisation is genuine — it caught three
mutations nobody had listed — and the two refusals the fix did not touch are
unchanged.** **All sixteen of the previous round's Q-series mutations are
caught**, the layer's wiring for the DOCX and the PDF included, which is where
that round said the gap was.

**The failures are all in one class, and it is a class the fix's mechanism
cannot reach** — F47 above: what a form says about itself outside its own
text.

| property broken | mutations | caught | survivors |
|---|---|---|---|
| §2.3 — the form's **text** | 4 | **4** | — |
| §2.3 — the form's **own name and metadata**, outside its text | 4 | 0 | **T10, T11, T15, T16** |
| "the four forms are drawn from the canonical document" (the layer's wiring) | 5 | **5** | — |
| …its controls | 3 | **3** | — |
| "a form carries the document's section heading" | 2 | **2** | — |
| …its control | 1 | **1** | — |
| the fix's own comparison (moments compared as a set) | 1 | **1** | — |
| "a finding is a list item" (the shape the fix asserts for the PDF) | 3 | 1 | **T17, T18** |
| the layer's two part-refusals | 2 | 0 | **B6, B7** — both **measured unable to fire** |
| the citation names the address the record was read from | 1 | **1** | — |
| the fix author's own two claims | 2 | **2** | — |
| **the nine applied together** | one run | **4** | — |

**The nine applied together:** `4 failed, 3212 passed, 3 skipped` — the four
failures are the four comparison tests. **The previous round's own combined
run was not evidence for this**: at `25bad72` its twelve failures were all in
`tests/test_smoke_path.py`, which was broken then. At `5dcd6d0` the smoke
path is green, so the four are attributable to the mutations.

**And the two layer refusals, B6 and B7, are unchanged — and now measured.**
The unreachability probe instruments each guard so that its **condition** —
not the branch — writes a marker when it is true, and runs the whole suite:
five of the seven unwatched branches **fired**; **725 and 733 never became
true**. So both are **defence in depth with no test**, and **neither can be
reached by the tree as it stands**. That is a limit of the evidence, and it is
recorded as one.

**The baseline the re-review measured, at `5dcd6d0`:** the whole suite
**3216 passed, 3 skipped, 0 failed** in 44:49 · `ruff check` All checks passed
· `ruff format --check` 260 files already formatted · `mypy` **Success: no
issues found in 243 source files**.

**The reviewer's own ledger, because the result is only worth what the method
is.** Two anchors that missed and measured nothing, and were re-run. A
**discarded method**: the carrier measurement prints "NO_OP" for three
mutations although they did change the form, and the reviewer says so rather
than letting the label stand. **A measurement invalidated by the machine, not
by the code**: C: reached 100% during the first wave of runs, and every
whole-suite run in flight at that moment was discarded and re-run. **A defect
in the reviewer's own harness**: two concurrent runs shared one `--basetemp`
and locked each other's SQLite files — 1357 `PermissionError` errors — and
every affected run was re-run. **A contamination of the reviewer's own
making**: two drivers ran in one worktree at once, and one survivor first
reported "CAUGHT" because the other's mutation was in the tree; re-run in an
exclusive worktree, it survives. **Two survivors that were not one, caught by
accident of placement**: a first mutation wrote `if False:` and was caught by
the project's own `mypy` (which runs `warn_unreachable`), and another left
`BlockKind` unused and was caught by `ruff` — **for reasons with nothing to
do with the property**; rewritten type-clean and lint-clean, **both survive
the whole tree**. And a whole-suite "catch" that was not a catch: a SQLite
CHECK-constraint test the DOCX's title property has no path to, which passes
on a clean tree when run alone.

**A thing worth keeping from the ledger:** a red test is not a catch unless
the red test is about the property. **Three separate times in this one review
— the harness's encoding, the project's own mypy, the project's own ruff — a
test went red for a reason that had nothing to do with the mutation, and
every one of them read as "the mutation was caught" until the run was
repeated.** That is the same lesson F46 records, in a third form.

**What the re-review did not check:** the 75 sweep branches in `model.py`,
`manifest.py`, `revisions.py`, `checks.py` and `build.py`, which it inherited
from the previous round on the ground that neither those modules nor their
mapped test files differ between `25bad72` and `5dcd6d0`; the CLI, the API,
the store, the ingestion, the approvals and the stages; the `web/` tree and
the other `examples/` scripts; **flakiness under repetition** — each mutation
was run once, at one seed, with `pytest-randomly` disabled, and the unrelated
failures above show the rate is not zero on a loaded machine; the new
fixture's coverage of every block kind the model allows; Windows' non-UTC
handling beyond the existing DOCX UTC test; and `describe_locator`'s other
four locator kinds.

### Scope A — the re-verification at `86e0226`

**The verdict was FAIL, with four mutations surviving the whole tree.** The
fix under review is a real and large improvement, and that is on the record
before the failures: **F47's fix caught all six of the previous round's
survivors**, each by the witness that is about the property — the DOCX's
title property, the PDF's title, the PDF's producer, the DOCX's description,
and the list-item shape in the Markdown and in the DOCX.

**What is left is a hole in the fix's own mechanism.** The list-item
witnesses compare a **count**, and the rule they state has two halves — F51.
**And the two layer refusals the record already carried are still open**,
re-measured and unchanged: defence in depth, unwatched, and **unreachable in
the tree as it stands**.

**Fifty-two mutations, forty-seven caught. The survivors are five** — the two
layer refusals (725 and 733), the two list-item swaps (N1 and N3), **and N7,
the HTML's own shape, whose property this record says is unstated** and which
the reviewer counts separately: *"If the gate counts N7 as a survivor because
the mutation survives, the count is five."*

**The prose of this section said "forty-three mutations, forty caught" while
the table beneath it said fifty-two and forty-seven. The table is right, and
the prose was written before the table was finalised. A number that disagrees
with the ledger beside it is the defect this gate exists to catch, and it
caught it here.**

| property | mutations | caught | survivors |
|---|---|---|---|
| §2.3 — the form's **text** | 4 | **4** | — |
| §2.3 — the form's **own name and metadata** | 4 | **4** | — |
| the two container forms name the same producer | 1 | **1** | — |
| the two container forms carry the report's own limit | 2 | **2** | — |
| the two container forms name the report | 2 | **2** | — |
| the four forms are drawn from the canonical document | 4 | **4** | — |
| …the opposite conclusion | 4 | **4** | — |
| the heading, the title, the moment, the records (the controls) | 11 | **11** | — |
| the citation names the address the record was read from | 1 | **1** | — |
| the fix author's own two claims | 2 | **2** | — |
| a section heading is a heading of the second level (the HTML) | 1 | **1** | — |
| a finding is a list item | 2 | **2** | — |
| …**which** items are list items (the DOCX) | 3 | 2 | **N1** |
| …(the PDF) | 1 | 0 | **N3** |
| …(the Markdown) | 2 | 2 | — |
| the HTML's own shape of a finding | 1 | 0 | *N7 — an unstated property* |
| the layer's two part-refusals | 2 | 0 | **725, 733** — both **measured unable to fire** |
| the layer's other refusals | 5 | **5** | — |
| the sweep — the 24 branches whose mapped test file changed | 24 | 17 caught, 5 re-caught | 725, 733 |
| the sweep — the 75 branches in model/manifest/revisions/checks/build | 75 | **75** (inherited, on measured ground) | — |
| **the survivors applied together** (N1+N3+N7) | one run | 0 — `3233 passed, 3 skipped` | — |

**The baseline the re-review measured, at `86e0226`:** the whole suite
**3233 passed, 3 skipped, 0 failed** in 24:52.

**The two layer refusals, re-measured and unchanged.** The unreachability
probe — each guard instrumented so that its **condition** writes a marker,
the whole suite run — had 504/516/556/579/790 **fire**, and **725 and 733
never become true**. **Neither of the two refusals is witnessed.** The phrase *"is not the
artefact the ledger recorded"* **does** appear in the test tree, at
`tests/test_analysis_report_checks.py:1547` — but it witnesses **the manifest
artefact's refusal at `application/reports.py:504`**, a different guard with a
different condition. **The shared phrase is not what makes a guard
watched.** They are defence in depth with no test, and they cannot be reached
by the tree as it stands.

**And the head's movement, measured rather than reasoned.**
`git diff --name-only 5dcd6d0 86e0226 -- src/labcairn/reports
src/labcairn/application src/labcairn/sources` is **empty**: the report
path's product is byte-identical, so every anchor and every measurement of
the product's behaviour is the same measurement. The *test* tree changed in
thirteen files, and the reviewer **counted the test names in every mapped
file at both commits**: `test_analysis_report_render.py` 67→74 (7 gained, 0
lost), `test_application_layer.py` 74→78 (4 gained, 0 lost),
`test_smoke_path.py` 19→20 (1 gained), `test_analysis_report_model.py` 60→60
(the same names). **No test file was added or deleted.**

**One the head could have reached and did:** the sweep's mapped set for the
layer is `test_application_layer.py` alone, but
`test_analysis_report_checks.py` watches four of the layer's refusals. The
reviewer re-checked the survivors against **the whole tree** instead, and
790 was caught there, by a named test the mapped set would have missed.

**The reviewer's own ledger, and one of its entries is the sharpest thing in
this round.** A **catch that is not a catch**: with the whole tree as the
sweep's re-check set, the README's own test goes red for two of the layer's
branches — and **its red is the tree's own gates, not a witness**: with 725
neutralised the README's `uv run mypy` step fails with `union-attr`, and with
790 neutralised its `uv run ruff check .` step fails with `F841`. **Both are
artefacts of the neutralisation, and neither was read as a catch.** Also: a
measurement of the reviewer's own that was wrong (a mutation labelled
"NO_OP" because its carriers were the forms' *text* and a heading level is
not in the text — the fix was to add the forms' *shapes* to the measurement),
a broken mutation of the reviewer's own (a dropped parenthesis, a
`SyntaxError`), a discarded method (the predecessor's driver does not measure
whether a mutation changed anything, so a no-op could be read as a survivor),
and **no run invalidated by the machine** — the two survivors were each run
twice, in two worktrees, and both reproduce.

**What the re-review did not check:** the 75 sweep branches in
`model.py`, `manifest.py`, `revisions.py`, `checks.py` and `build.py`
(inherited, on the measured ground above); flakiness under repetition, except
for the two survivors, which ran twice; the carriers the record names and
does not change (`docProps/app.xml`, the PDF's `/Creator`, the DOCX's
`dc:subject` and the rest) — **confirmed by grep that no test reads them**;
the CLI, the API, the store, the ingestion, the approvals and the stages; the
`web/` tree; Windows' non-UTC handling beyond the existing DOCX UTC test;
and **the content of F47's witnesses beyond mutation** — the expectations
were not re-derived from the specification.

### Scope B — the three surfaces

**Reviewed at `6035dbf`** by a reviewer that wrote **no fix** into this
repository. It began at `8fe7466` and reviewed B1–B20, B22 and B23 there;
when the second commit landed it **re-ran every mutation against `6035dbf`**
and added B21. B21 was no longer held, and it is watched.

**What it ran at `6035dbf`:** `ruff check` clean · `ruff format --check` 259
files already formatted · `mypy` (strict) clean, 242 source files · the whole
suite **3173 passed, 3 skipped**, exit 0, 1024 s · the web package `pnpm
lint` clean, `pnpm typecheck` clean, `pnpm test` **62 passed**, `pnpm build`
succeeded · `uv run python examples/g4_exit_demo.py` exits 0 with **54
checks**, and prints *"the task holds the material the CLI was told about"*,
*"compared : 255 field(s), 0 differing"*, *"the CLI and the service were used
against one workspace at the same time"* and *"the report carries the claim,
and cites the address it rests on"*.

**Seventy-two runs** in all, one property at a time, implementation only —
never a test. **Eight properties survive the whole suite at `6035dbf`.** Two of
them the reviewer made **blockers**; the other six are notes.

| | Result |
|---|---|
| the whole table, B1–B23 | **64 of 72 runs caught**, each by a named test |
| **the two blockers** | **B7** — a stage run that follows an approval plans a second operation; **B10** — the demonstration's exit code is not load-bearing |
| **the six notes** | the token is not compared in constant time; the CLI's prose form and its JSON form can disagree; the event stream's session ownership is asserted against the wrong session; and three of the demonstration's comparisons can be narrowed |

**What "seventy-two" counts, said plainly, because the number is quoted and
the re-review recovered it.** **Seventy-two is the number of *runs*; the
number of distinct mutations is forty-nine, over thirty-five distinct
properties.** A property run against several selections, and at two commits,
is several runs of one mutation — and the re-review could not reproduce
seventy-two exactly, and says so rather than rounding it into a number it
cannot produce. **Both tallies are recorded here, and neither is called the
other.**

**How the survivors were confirmed.** All eight were applied **together** to the
worktree and the **whole suite** was run: **3171 passed, 3 skipped, 2 failed —
the identical two failures the unmutated baseline showed** (an intermittent
flake in LC-P1-10's analysis demo, F38 below). A clean run of the same suite
is **3173 passed, 3 skipped, 0 failed**. So no test in the suite catches any
of the eight.

**The blockers, in the reviewer's own words.**

#### F30 — the demonstration's exit code is not load-bearing

> **What I broke.** `examples/g4_exit_demo.py::check()` no longer raises:
> `raise AssertionError(f"FAILED: {label} {detail}")` →
> `print(f"  [!!] {label} {detail}")`. I then planted a claim that is false.
>
> **Why nothing noticed.** The whole of `tests/test_smoke_path.py` — **13
> tests** — stayed green. The test asserts the demonstration's exit code is 0,
> but the demonstration now exits 0 *with a claim failed*; it asserts
> `len(checks) >= 30` and that the printed count matches the summary (a failed
> claim prints `[!!]` and is not counted in either, so the two still agree);
> and it asserts eight *control labels* are in the output, but a failed check
> prints its label too.
>
> **Why this is the gate's exit test, not a detail.** I ran the mutation
> **together with a real product defect**: `api/routes.py::get_artifact_content`
> serving `content.content + b"!"` — the API serving bytes that are not the
> stored file's bytes, which is exactly "CLI and Web produce same versioned
> report" failing. **The whole of `tests/test_smoke_path.py` stayed green (13
> passed).** The demonstration's *field-by-field* comparison is separately
> witnessed (the test reads `compared : N field(s), 0 differing`), but the
> **byte** comparison — §1.4.2's "same bytes", the one the exit test is named
> for — is witnessed only by the label *"the report.md the CLI names is the
> bytes the API serves"* and by a control over the comparator.
>
> **The property that is unobserved:** *a failing claim in the demonstration
> must fail the run.* The demonstration's own docstring says *"A failure
> raises rather than prints a warning, so this exits non-zero if a guard stops
> working"*; `tests/test_smoke_path.py`'s docstring says *"**The exit code is
> the assertion that matters.** … A test that only read the output would be
> testing the prose."* The test does read the output, and the exit code is not
> load-bearing.
>
> **The test that should have caught it:** one that runs the demonstration with
> a claim planted false and requires a **non-zero exit** — the converse of
> what is asserted today. Equivalently, a test that asserts the
> demonstration's `check()` raises. Nothing asserts the converse.

**This sharpens F7.** F7 was *"the demonstration's own checks were unwatched"*,
and its fix gave eight comparisons a control. **The mechanism those controls
share was never watched**: a control cannot be swallowed by a check that does
not raise, and nothing said the checks raise at all. A gate whose exit test
can fail a guard and still report success is not an exit test.

#### F31 — a stage run that follows an approval plans a second operation

> **What I broke.** `application/stages.py::_find_operation`, the branch that
> reuses the operation an approval was bound to:
> `if operation.operation_id == approval.operation_id` → `!=`.
>
> **Why nothing noticed.** Nothing in the suite looks.
> `test_application_layer.py::test_a_parked_stage_completes_when_the_approval_arrives`
> asserts the stage completes and the operation is confirmed — both true of
> the *new* operation. The recovery and skill suites do not go through this
> path.
>
> **What it does, measured.** With the mutation applied, the store holds
> **two operation rows** for one piece of work — the approval's
> (`awaiting_approval`) and a fresh one (`confirmed`) — and the approval is
> spent against an operation it was never bound to. That is the property's
> own words: *"two operations for one piece of work would make the audit log
> say it happened twice."*
>
> **The property that is unobserved:** *a stage run that follows an approval
> reuses the operation already planned for that piece of work.*
>
> **The test that should have caught it:** one that runs a stage after an
> approval and asserts the store holds **exactly one** operation row — the
> property the scope table states and the code's docstring states.

**The reviewer's verdict on the gate, in its own words:**

> **BLOCKED** — not because the review could not be done, and not because the
> product's behaviour is wrong: every property I broke was either caught by a
> named test or left the product behaving as it should, and the gate's exit
> test *is* demonstrated (255 fields compared, 0 differing; the report's bytes
> compared by hash; the material ingested through the CLI; the CLI and the
> service driven against one workspace at the same time). The blockers are the
> **guards**, and one of them sits under the exit test itself.
>
> This is not the G3 shape — G3 closed on *"no mutation survived"* — so the
> board's rule is not discharged by this review as it stands.

**The six notes, each with the shape of the missing witness.**

#### F32 — the CLI's prose form and its JSON form can disagree

> `cli/render.py::render_task_state` draws the title `"a task"` instead of
> `model.task.title`. The JSON form *is* watched
> (`test_task_status_json_is_the_layers_task_state` compares it field for field
> with the layer's model). The **text** form is not cross-checked against the
> JSON anywhere — except for `doctor`, which has
> `test_doctors_prose_says_what_its_data_says`. `task status` has no such
> test, and `README.md`'s claim that *"`--json` prints the same model the
> rendered output draws, byte for byte"* is not watched for it.

#### F33 — the token is not compared in constant time

> `api/session.py::SessionToken.verify`: `secrets.compare_digest(...)` →
> `self.value == candidate`. `secrets.compare_digest` appears **once in the
> whole repository** — in the implementation.
> `tests/test_api.py::test_the_session_token_compares_in_constant_time_over_bytes`
> is *named* for the property and checks only the boolean result and that a
> non-ASCII candidate does not raise. It is a test whose name claims a
> property it does not check. The same shape appears in `api/session.py`'s own
> docstring.

#### F34 — the event stream's session ownership is asserted against the wrong session

> `api/routes.py::get_event_stream`:
> `session = context.store.fork().session` → `session = context.store.session`.
> `tests/test_api_concurrency.py::test_the_event_stream_owns_its_session_for_the_life_of_the_stream`
> asserts `session is not context.store.session` — but `context` there is the
> **fixture's** context (the service's), while the stream reads on the
> **request's** forked context. The assertion therefore cannot see the
> substitution. The test's own docstring says *"**It is not the service's
> shared session.** … the defect this whole change is about"* — which is true
> and checked; the *other* half, that the session is the stream's own, is not.
>
> **Honest measure of the harm.** With the mutation, the stream's second poll
> still finds its session open and not in a transaction, and the request's
> session is closed when the request ends. The substitution is behaviourally
> equivalent in the paths the suite exercises, because the request's session is
> per-request and is not shared between requests. The risk it guards is real
> but small.

#### F35 — three of the demonstration's comparisons can be narrowed with no notice

> **The workbench's re-read is the task it read before** — `first == second`
> narrowed to `first == first` survives the whole suite. (The same step's
> *other* check — the CLI's read against the API's second read — is not a
> tautology, so the step is partly watched; the refresh comparison itself is
> not, and it has no control, unlike the eight that do.)
>
> **and the first revision's bytes are unchanged** — `before == after`
> narrowed to `before == before` survives. And **with the repository's own
> reason, and not one invented here** — `all(is_stale(receipt) for receipt in
> stale)` narrowed to `True` survives.
>
> The last two are **declared** by the demonstration itself — *"a check whose
> own requirement was narrowed would still print its line, and no control would
> notice"* — so they are known limits, honestly printed. The first is not
> declared.

**This sharpens F7 twice over.** Its fix added controls to eight comparisons
and left three without one; and F30 shows that even a control can be
swallowed, because the mechanism the controls share was unwatched.

#### F36 — the binding's docstring states a distinction the code cannot express

> `MaterialIngested`'s docstring says: *"bound_source_ids is the task's binding
> after the operation, and source_ids is what this run ingested. They are the
> same set on a first ingestion and **differ when the task already held
> material this run did not touch** — the binding is the task's, and the
> ingestion is this run's."* Both fields are the same tuple in the code, and
> `tests/test_cli.py` asserts `report["bound_source_ids"] == report["source_ids"]`
> — the test pins the equality the docstring says cannot hold. The underlying
> behaviour: `TaskStore.bind_sources` **replaces** the row's list, so the
> task's binding is not accumulated. Measured: after the operator removes a
> file from the workspace and re-ingests, the task **silently loses that
> material** from its binding, and nothing in `MaterialIngested` says the
> binding shrank (`source_ids`, `files`, `failures`, `skipped`,
> `bound_source_ids` and the three totals — none of them reports a loss). A
> `TASK_REVISED` event records that the binding moved, so the log knows, but
> the operation's report does not.

**The same class as F20, F23 and F24**: a docstring that states a rule the
code does not enforce. Here the rule is worth enforcing rather than
correcting — a task that rests on material should not forget it because the
operator's filesystem changed.

#### F37 — a module docstring that denies a thing the module does

> `src/labcairn/cli/commands.py`'s module docstring says: *"this module
> imports nothing at module level but the standard library and Typer"* — the
> module imports `from labcairn.api.bind import DEFAULT_BIND_HOST,
> DEFAULT_BIND_PORT` at module level. The property the sentence argues for (the
> layer is not loaded) is true and watched by
> `test_loading_the_cli_does_not_load_the_layer`; the sentence itself is
> false.

**The no-ops it listed separately**, so they are not mistaken for survivors —
this is the part of the report that makes the rest trustworthy:

1. **B6 (the session directory's mode) is a no-op on this platform.**
   `_restrict(path.parent, 0o600)` applied cleanly, but Windows' `chmod` does
   not set POSIX bits, so nothing changes here, and the guarding test
   `test_api.py::test_the_session_directory_can_still_be_entered` is
   `@pytest.mark.skipif(os.name == "nt")` — **skipped on this machine**. On
   POSIX it would catch it. **Not a survivor.**
2. **B7's crash half is a no-op, and that is a coverage hole.**
   `return matches[-1] if matches else None` → `return None` changed nothing:
   a probe that raises when the match list is non-empty showed **`matches` is
   empty in every test in the suite**. So the branch that reuses an operation
   after a crash is **never exercised at all**. Not a survivor — but the
   property is unwatched because it is never reached.
3. **B17b's first run was a selection gap, not a survivor.** The first
   selection omitted `tests/test_material_pdf.py`, so "unreadable recorded as
   readable" appeared to survive. Redone with the whole material suite:
   **CAUGHT**.
4. **B18's first attempt matched its anchor twice** (`ANCHOR_AMBIGUOUS`);
   nothing was tested. Redone with a longer anchor: CAUGHT.
5. **B14's first attempt still contained the phrase "event stream"**, so the
   property was untouched. Redone: CAUGHT.
6. **B10 as a single mutation is a no-op.** Weakening `check()` alone changes
   nothing, because no claim fails. It only becomes meaningful with a planted
   failure, and that combination survived (F30).
7. **B11's "compared against a re-render" substitution could not be expressed
   as a text mutation** — the demonstration renders the report once and has no
   re-render to compare against at that point. The nearest faithful mutation
   (the API serving bytes that are not the stored file's) was **CAUGHT** by a
   named test.
8. **A discarded method.** The reviewer first ran the survivors against the
   whole suite in plain *file copies* of the tree. The copies are not
   hermetic — the suite reads the git checkout for the board's SHAs, the
   tracked PDF fixtures and the repo-root guard — so every case reported
   "CAUGHT" for reasons unrelated to the mutation. **It discarded those
   results**, redid the check in `git clone --shared` checkouts, and finally
   ran it in the worktree itself. The numbers above come from the worktree.

**What it found beyond the guards** — the part that is not a mutation at all:

- **The product has no operation that writes an evidence record or an
  anchor.** `labcairn.evidence.store.append_record` is called from inside
  that module and from nowhere else, and no layer operation writes a
  `SourceAnchorRow`. The demonstration therefore writes the claim's own
  address and the record itself, and says so in its own output: *"the product
  has no operation that writes an evidence record or an anchor, so the
  demonstration wrote the claim's own address and the record that rests on it
  itself. The report carries a real claim, cited to a cell of the material
  the CLI ingested — but the claim was made by the demonstration, not by the
  product."* **That is the right thing to do, and it is the third limit this
  work order carries** — the board named only two (the event stream and the
  project selection) and should name this third.
- **The board was behind the merged state** when the review ran.
- **An intermittent flake outside its scope.** `tests/test_analysis_demo.py`'s
  two demonstration tests failed in two of three whole-suite runs and passed
  in the third and in isolation. It is not caused by the reviewer's mutations
  — the baseline and the mutated run showed the identical two failures — but
  **the suite is not reliably green on this machine** (F38).

#### F38 — the suite is not reliably green on this machine

**Found by this review, not by either independent reviewer, and it is a defect of
the gate's own verification, not only of the machine.**

`tests/test_analysis_demo.py::test_the_exit_demonstration_runs_and_every_check_holds`
and `..._refuses_what_it_must_refuse` — **LC-P1-10's demonstration**, not this
gate's — failed in two of the reviewer's three whole-suite runs and passed in
the third and in isolation. The reviewer reported it as a fact about the
machine rather than as a defect of the gate. **It is a fact about the gate
too**: a suite that is green only sometimes cannot witness "the whole suite
passes", which is what this gate's verification claims.

**The cause, reproduced and measured.** Four concurrent runs of
`uv run python examples/analysis_demo.py`:

```
run 1 exit=0
run 2 exit=0
run 3 exit=1     <- the failure
run 4 exit=0
```

**It is not a crash.** The two renders *in the same process* differ in their
bytes — same length, different content:

```
  run    : 26365 byte(s), 5880fc275cbb8d66f626dbb06549ed726a81c11fa2cb4cdc04a2b1b16826d96a
  render : 26365 byte(s), 5880fc275cbb8d66f626dbb06549ed726a81c11fa2cb4cdc04a2b1b16826d96a
  render : 26365 byte(s), 5499bef330bdffbd4c2a195465188dfdfc8a7385299d1a45143f1fe2d82b0c17
AssertionError: FAILED: two renders of one recipe are byte-identical
```

**It is not a timing factor.** Six *sequential* runs of the same command: all
six exit 0. The failure needs concurrency.

**It is the render environment's shared directory.**
`src/labcairn/analysis/chart/render.py` pins the render environment in a
directory under the system temp dir — `MPL_CONFIG_DIR` — and
`MatplotlibFigureRenderer.prepare()` writes the declared settings there and
reads them back:

```python
declared = MPL_CONFIG_DIR / "labcairn-matplotlibrc"
declared.write_text(RC_PARAMS_SOURCE, encoding="utf-8")
matplotlib.rc_file(str(declared))
```

**`write_text` truncates and then writes; it does not replace atomically.** A
second process calling `prepare()` at the same moment truncates the file the
first process is about to read, so the first reads an rc file whose settings
did not all arrive — `svg.hashsalt` and its neighbours fall back to
matplotlib's defaults for that one render, and the figure's element ids
change. The font cache in the same directory is written the same way.

**The decisive experiment.** With each process given its own
`tempfile.gettempdir()` — a `sitecustomize.py` that calls
`tempfile.mkdtemp()` and points `tempfile.tempdir` at it — the same four
concurrent runs are **all green**. The shared directory is the cause and the
per-process isolation removes it.

**Why the directory is shared is a decision, and the fix must keep it.** The
renderer's own docstring says why the location is pinned at all: the ambient
`matplotlibrc` and the font cache are *inputs*, and *"an input at an unrecorded
location is an input the reproducibility claim cannot cover"*. The directory
is pinned so a render reads a font list and a settings file **this project
chose where to keep**. A fix that moved the directory somewhere unrecorded
would break that intent; a fix that makes the writes atomic, or that stops
one process's *preparation* from depending on what another process is writing
at that instant, keeps it.

**And that is the fix: the files are put into place whole.** The bytes go to
a temporary file **beside** the target and are moved onto it with
`os.replace`, which is atomic within a volume — a reader sees the whole
settings or the whole of what was there before, **never half of either.** The
other side of the same rule bites too: on Windows a file another process has
open **cannot be replaced**, and while a replacement is under way the file is
marked for deletion and an open of it in that moment is refused as well, so
both the write and the read **wait for the other process** rather than
failing a render over a file that is being shared on purpose.

**And the witness is the race, not a claim about it.** The preparation is
done by several interpreters **at once**, and the bytes they draw are
compared. They are released together round by round, because the window is a
few microseconds wide and processes that merely ran side by side would be
testing luck. The recorded settings file is **watched while they work**,
because that file is where the failure happens: a file caught holding less
than the whole declaration is a file a process could have read, and the render
that process went on to draw is not the declared one. The environment
directory is **their own**, because the property is about two processes
sharing one environment, and sharing the machine's would make the test depend
on whatever else on the machine is rendering.

#### F39 — the gate's exit demonstration fails after 13:00 UTC, and no CI run had ever run after it

**Found by this review, not by either independent reviewer, and it is a defect
in the gate's own exit test.**

The demonstration declares a fixed moment — `NOW: datetime = datetime(2026, 10,
21, 12, 0, tzinfo=UTC)` — and says of it: *"A fixed moment. Nothing in this
file reads the wall clock, so two runs of it differ only in what it measured."*
In step 4 it asks for an approval through the application layer, with
`expires_at = NOW + timedelta(hours=1)` — so the approval expires at 13:00. In
step 7 it asks the **service** to grant an approval, and the API route takes no
moment:

```python
@router.post("/approvals/{approval_id}/grant", response_model=ApprovalGranted, tags=["approval"])
def post_approval_grant(
    approval_id: ApprovalId, context: Annotated[ApplicationContext, Depends(_context)]
) -> ApprovalGranted:
    return grant_approval(context, approval_id)
```

so `grant_approval` falls back to `datetime.now(UTC)`
(`application/approvals.py:199`), and `granted_at` is the **real wall clock**.
The ledger's own constraint is `"granted_at IS NULL OR expires_at > granted_at"`
(`ck_approvals_expiry_after_grant`), so a grant made after 13:00 is refused by
the database — **correctly**, and the demonstration dies:

```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) CHECK constraint failed: ck_approvals_expiry_after_grant
[parameters: ('granted', '2026-10-21T15:34:39.271833+00:00', 1)]
```

**It is not caused by any change of this gate.** It fails at `origin/main`
(`d65254d`) exactly as it fails on the branches. **And no CI run had ever run
after 13:00 UTC** — the run history's last green run is at `11:10:54Z`, and
every run since has failed. A gate whose exit test stops working at a fixed
hour of the day is a gate with a time bomb in it, and **the demonstration's own
claim that nothing in it reads the wall clock was the thing that hid it**: the
one place that *did* read the wall clock was the one the claim did not cover.

**The shape of the defect, measured.** The demonstration reads no wall clock
at all — `grep` for `datetime.now`, `utcnow` and `time.time` in
`examples/g4_exit_demo.py` returns nothing, so **its claim is true of the
file**. The clock is read one boundary away, in the code the demonstration
*calls*: `application/approvals.py` reads it in three places — asking for an
approval, granting one, and consuming one — and each reads it only when the
caller passes no `now`. The demonstration passes `NOW` to the first (it asks
through the application layer) and to the third, and **cannot** pass it to the
second, because the grant goes through the service, whose route takes no
moment.

**So the defect is at a boundary, not in the file that declares the claim.**
The layer takes a moment (`render_report`, `run_stage` and `ingest_material`
all take `now=None` and use it); the API does not. That difference is the
whole of it, and **a file's claim about itself cannot cover what happens
after the file hands over.**

**The fix keeps the boundary where the project already draws it.** The
demonstration cannot name the moment the service will record a grant with —
**a client that could name it could grant an approval that had already
lapsed** — so the approval it asks the service for is the one value that
follows the clock, and every other moment the demonstration chooses is still
the fixed one. The docstring now says that, instead of denying it.

**And the witness does not wait for the hour to come.** The demonstration is
run **twice**, with every clock in it — the demonstration's own and the
product's — pinned to instants **eighteen hours apart** that straddle the
instant at which a window fixed to the demonstration's own moment closed for
good. A demonstration that still fixed its window there would pass at the
first and fail at the second. The pinned clock **moves**, because the clock a
real service stamps a grant with moves on: the question and the answer are
never the same instant. And the pin is **checked, not assumed** — the program
that pins the clocks refuses to run unless the clock the service records a
grant with really was pinned, and says which instant it pinned at. A run that
said nothing about the hour would be evidence about nothing.

#### F40 — finishing a stage that had been parked raised a raw `IntegrityError`

**Found while the fixes for F31 were being made, and it is in the store's
rules rather than in the gate's exit test.**

The stages table pairs a stage's status with its reason —

```python
"(status = 'blocked') = (blocked_reason IS NOT NULL)",
```

— and it is a **two-way** constraint: a stage that is not `BLOCKED` must not
carry a `blocked_reason`. `records.block_stage` and the function that parks a
stage awaiting an approval both set the status **with** the reason, correctly.
**But the two functions that finish a stage changed the status without taking
the reason with it** — `complete_operation` and `fail_operation` both used
`model_copy(update={...})`, and **`model_copy` does not run the model's
validators**. So completing or failing a stage that had been parked wrote a
row the schema refuses, and the caller got `IntegrityError: CHECK constraint
failed: ck_stages_reason_only_when_blocked` out of the middle of the
transaction, **after the effect had already run**. Reachable through the API:
`POST /approvals` (which parks the stage) and then `POST /stages` with the
same `run_id` and `stage_name` (which runs it).

**The fix puts the reason where the status is set**, and re-validates through
the model rather than copying around it, so the `Stage` model's own validator
takes part. The constraint and the schema are untouched: they are the last line
of defence, and a layer that refuses correctly should never reach them.

#### F41 — a run that followed a crash could attempt an effect nobody authorised

**Found while the fixes for F31 were being made, and it is the same finding as
F31 seen from the other side.** The reviewer had said the crash-reuse branch
was unwatched, and this is what it was hiding.

`stages.py::_find_operation`'s crash branch accepted two states —
`AWAITING_APPROVAL` and `AUTHORIZED` — and then took the **newest** match. So
when a run died between its intent and its attempt (two transactions, so the
product reaches that state on its own), leaving an operation `AUTHORIZED` and
never attempted, and a question was then put about the same work and left
unanswered, leaving a second operation `AWAITING_APPROVAL` with a `PENDING`
approval — **the resumed run adopted the awaiting one.** It wrote
`operation_intent` for it, promoting a question to "authorised" with no
approval granted; then `operation_attempted`; and **the work ran on an
operation nobody authorised.** The approval stayed `PENDING`, bound to an
operation already attempted.

**The ledger says what should have happened.** ADR-0003 C2's crash table:
`AUTHORIZED` → *"safe to attempt"*; `AWAITING_APPROVAL` → *"nothing was
performed … resume the stage"* — **not** "adopt the operation". And C4: an
approval is valid only once granted. The `operation_intent` the old code
wrote on a question was a false record under C3.

**The fix is one line of behaviour and a rule stated rather than assumed.** The
crash branch filters `AUTHORIZED` only. When two authorised operations for
one piece of work exist — a state the product should not reach — the newest
is taken, because **the store's order is the ledger's only order**; and it is
*not* the order the authorisations happened in, so neither the older nor the
newer is reliably the one authorised last. The other is left where it was,
visible in the ledger as an operation that was authorised and never attempted.

#### F42 — a grant of a lapsed approval reached the database as a raw `IntegrityError`

**Found while the fixes for F39 were being made, and it is F39's cause: F39 is
what the defect did to the gate's own exit test, and this is why it did it.**

The approvals table pairs a grant with its window, and the store holds that as
a constraint — `granted_at IS NULL OR expires_at > granted_at`. The constraint
is right; the code was wrong. `grant_approval` stamped the grant with the wall
clock and never asked whether the window was still open, so a client whose
question had gone stale got a raw `IntegrityError` out of the middle of the
transaction — **a 500 through the API**, and a message that said the service
was broken rather than that its answer was too late. **The layer already had
the refusal it should have raised**: `ApplicationRefusal.APPROVAL_REFUSED`.

**The refusal now belongs to the layer, and the layer asks the model rather
than the store.** `model_copy` does not run the model's validators, and the
`Approval` model's two timestamp rules — the window must outlive the grant,
and a consumption must not precede the grant — are the layer's own copy of the
store's two constraints. Asking the model through `model_validate` puts both
back in force, in one place, and the constraint and the schema stay exactly as
they are: **the last line of defence, which a layer that refuses correctly
never reaches.**

**And the refusal arrives before anything is spent.** The consume side has the
same shape and the same reachability — spending an approval at a moment before
it was granted reached `ck_approvals_consume_after_grant` the same way — so
the row is read and checked **before** the ledger is spent, and a refusal
cannot spend the approval and refuse the request at the same time.

**The refusal names the approval and the moment its window closed**, because
"your approval expired" is only actionable if it says *which* one.

**Nine tests say so**, in `tests/test_application_approvals.py`. The one that
witnesses the fix asserts the named refusal, and **on the unfixed code it
fails with the raw `IntegrityError` and says that the raw error is the
defect.** The others witness the boundaries (the window is half-open, and the
grant instant is not before itself), that a refusal writes nothing and grants
nothing, that the row carries the moment it was given, and that the store
still refuses the row the model would never build.

**Eight mutations were broken one at a time, each against the named test that
is supposed to observe it**: the refusal removed; the refusal's reason
replaced with a different `ApplicationRefusal`; the refusal ceasing to name
the approval; the refusal ceasing to name the moment the window lapsed; the
row written being the approval as it was rather than the granted one; the
consume-side refusal removed; and the model's own two timestamp rules
weakened, once each. **Every one was caught by a named test, and every one
was put back.**

**Two things are named here and not changed, because they are the owner's to
decide.** `ApplicationRefusal` has no `EXPIRED` member — the one with that
name is the domain's `ApprovalRefusal`, in `runtime/operation.py` — so the
layer refuses with `APPROVAL_REFUSED`, the reason it already uses for every
approval-shaped refusal including an expiry at the moment of use, and says
"expired" in the message; a distinct machine-readable reason would be one
line in `application/refusal.py`, and the API's refusal body and the CLI's
refusal line both carry the reason as a string, so nothing else would have to
change. And the API requires `expires_at` on an approval request, where the
recovery layer already defaults one from its injected clock, so a client has
to compute an expiry itself and **nothing in the contract tells it whose
clock to use**; making it optional, and defaulting it in the layer from the
moment the question is asked, is a change to the API's contract.

#### F43 — the gate's own exit demonstration printed one sentence twice

**Found by this review, in the gate's own exit test, and it was introduced by
the batch of fixes this gate had just made.** It is recorded here rather than
quietly corrected, because a finding in the exit test that is fixed without
being written down is a finding nobody will look for again.

The demonstration ends by saying plainly what the run did not exercise. One of
those bullets is the one about its own controls — and the batch's merge
resolved a conflict by keeping **both** versions of the bullet's opening
line:

```
  * The demonstration's own controls are not exhaustive. Each
  * The demonstration's own controls are not exhaustive. Every
    comparison is run once over something that must answer the other
```

The first line ends on a dangling "Each" and names a bullet that is not
there. **The demonstration is the gate's exit test, and what it prints is
part of what it says** — the same rule this gate holds the report path to,
where a form that carries a sentence the document does not hold is a finding.

**It is one line, and it is fixed in `5dcd6d0`.** Nothing else in the tree
differs from the commit the reviewers were asked to verify, and the
demonstration's exit code, its **60 checks** and every comparison it makes are
untouched by a line of prose in its list of what it did not exercise.

#### F44 — the batch's own composition deleted the witnesses for F31

**Found by the three surfaces' re-verification, and it is this gate's own
doing.** The property F31 was fixed for — a stage run that follows an approval
reuses the operation the approval was bound to — **had a witness, and the
witness was correct.** The composition commit `2f7ffc5`, which rewrote
`tests/test_application_layer.py` to hold three agents' additions at once,
**deleted four test functions** that its parents had:

| the witness | written in | lost at |
|---|---|---|
| `test_a_run_that_follows_an_approval_reuses_the_operation_it_was_bound_to` | `07c0710` | `2f7ffc5` |
| `test_a_run_that_follows_a_crash_reuses_the_operation_that_was_authorised` | `07c0710` | `2f7ffc5` |
| `test_a_stage_that_runs_twice_plans_two_operations` | `500f9cc` | `2f7ffc5` |
| `test_a_run_that_follows_an_approval_reuses_that_approvals_operation_and_not_another` | `07c0710` | **`b30dea4`** |

**Two different merges lost witnesses, and neither of them said so.** The
fourth was lost earlier still — at `b30dea4`, the merge of
`fix/g4-stage-reason-with-status` — and the other three at `2f7ffc5`, the
composition. **A merge that resolves a conflict by keeping both sides can
also keep both sides of a *deletion*.** The merge's resolution produced a file that
parsed, passed every test, and was green in CI — and had quietly lost the
tests that watched two of the gate's own properties. **Nothing in the suite
noticed, because the thing that was lost was the noticing.**

**What it would have let through:** a stage run that follows an approval
planning a **second** operation and spending the approval against an operation
it was never bound to — the blocker the three surfaces' review named, alive
again, with the whole suite green.

#### F45 — the demonstration's own comparison of the two surfaces is unwatched

**Found by the three surfaces' re-verification, in the gate's own exit test.**

The demonstration compares the CLI's task state with the service's task
document, field by field, and that comparison **is** the gate's exit test. It
also has a **control**: the demonstration copies the service's document,
plants a difference in the copy, and insists the comparison finds it.

**The control does not watch the check it was made for.** The control calls
the comparison with **different arguments** — the copy rather than the real
document — and the mutation that survives changes **which arguments the check
passes**, not the function. So:

```python
differing = the_differences(cli_state, api_state)   # the check
planted   = the_differences(cli_state, planted_state)  # the control
```

becomes, under the mutation, a demonstration that compares the CLI with
**itself** and reports *"0 differing"* — and **the whole suite stays green**,
because the control is untouched.

**A control proves the comparison can fail; it does not prove the check asked
it the right question.** The demonstration's own limitations text already says
this in the abstract, and this is the instance of it: *"What no control would
notice is a check that stopped asking its comparison a question and answered
for itself."*

**What it would have let through:** the demonstration's claim that the CLI's
state and the service's document are the same becomes **vacuous** — a
comparison it did not make, reported as one it did. The *product's* property
is watched, by a test that asks each surface itself; what is unwatched is the
demonstration's own comparison of them.

#### F46 — a test's pass or fail depended on the machine's locale

**Found by the three surfaces' re-verification, as a note, and reproduced here
before it was written down.**

Several tests run a subprocess with `text=True` and **no `encoding=`**, so the
child's output is decoded with the **parent's locale encoding** — whatever
the machine happens to be. The demonstration the tests read prints UTF-8
em-dashes, so the bytes on the wire are not ASCII, and the two sides can
disagree.

**The disagreement is reproducible, and it is not a flake:**

```
$ PYTHONIOENCODING=utf-8 uv run pytest tests/test_analysis_demo.py -q
FAILED tests/test_analysis_demo.py::test_the_exit_demonstration_runs_and_every_check_holds
FAILED tests/test_analysis_demo.py::test_the_exit_demonstration_refuses_what_it_must_refuse
UnicodeDecodeError: 'gbk' codec can't decode byte 0x94 in position 11: illegal multibyte sequence
```

**The test passes on CI, because CI's locale is UTF-8. That is the whole
defect: a test that is green or red depending on the machine's locale is not
watching the product.** It is the same class as the F38 flake and a different
class from it — F38 was a race, this is a **mismatch of two encodings that
both have a reason and neither of which is the product's**.

**And it is the kind of thing that makes a reviewer's number wrong.** The
re-verification's first two whole-suite runs reported two survivors as
"caught" — **and the catch was its own harness.** The harness set
`PYTHONIOENCODING=utf-8` for the pytest process; the child inherited it and
wrote UTF-8; the parent decoded with `cp936`; the test failed with a
`TypeError` that said nothing about the demonstration — **and a red test read
as "the mutation was caught".** The harness was corrected and both runs
repeated, and both mutations survive.

**A test that fails for a reason of its own is not a witness, and a reviewer
that reads a red test as a catch is wrong in the direction that flatters the
code.** The fix pins the child's output encoding *and* the parent's decoding,
because fixing only the parent's decoding turns the failure around rather
than fixing it.

#### F47 — what a form says about itself, outside its own text

**Found by the report path's re-verification, and it is a class the fix's own
mechanism cannot reach.**

The fix that closed the third round of this scope did something general: it
reads each of the four forms back **with the reader its own test uses** and
compares it with the model's own claims as an equality. **It worked** — it
caught **thirteen of the fourteen** mutations the previous round left
surviving, and it caught three nobody had listed. But the comparison reads
the form's **text**, and **a form also says things about itself that are not
in its text.** Six mutations there survive the whole tree, each measured:

| | the mutation | the carrier | whole-tree result |
|---|---|---|---|
| **T10** | the DOCX's own title property names a report the document does not hold | `docProps/core.xml`'s `dc:title` | 3216 passed, 3 skipped, **0 failed** |
| **T11** | the PDF's `/Title` | the PDF's document information dictionary | 3216 passed, 3 skipped, **0 failed** |
| **T15** | the PDF's `/Author` is not "LabCairn" | the same dictionary | 3216 passed, 3 skipped, **0 failed** |
| **T16** | the DOCX's `dc:description` is not the first-pass notice | `docProps/core.xml` | 3216 passed, 3 skipped, **0 failed** |
| **T17** | the Markdown draws a finding as a paragraph, not a bullet | the `- ` marker | 3216 passed, 3 skipped, **0 failed** |
| **T18** | the DOCX draws a finding as a plain paragraph, not a "List Bullet" | the paragraph's style | 3216 passed, 3 skipped, **0 failed** |

**What T10 would have let through, in the reviewer's own words:** *"A DOCX
whose own title property says A final report, in a product whose every export
opens 'This is a first-pass report produced by LabCairn. It is not
journal-ready.' A reader who opens the file in Word sees 'A final report' in
the title bar."* **That is §2.3 broken in the same sentence the earlier
survivors broke: the renderer decided the document's name instead of drawing
it.**

**Why nothing can see them, measured rather than assumed:** `dc:title` is
written in exactly one place and read nowhere; `docProps/core.xml` is read by
exactly two tests and **neither checks the title or the description**; **no
test in the tree reads a PDF's document information dictionary**; and **no
test reads a DOCX paragraph style**.

**The precise statement, which F57 makes sharp: the witnesses say *which*
items are list items, and not *how* a form marks one.** The Markdown's `- `
and the DOCX's "List Bullet" are free — the product says the shape is the
renderer's business — while the PDF's bullet glyph is watched only
incidentally, by the reader's glyph-reference pattern.

**Two of the four forms already carry the witness this class needs, and they
are the model for it.** The **HTML**'s title element is watched — *"a title
element that named another report would give a reader a tab that lied about
what was in it"* — and the DOCX's title property is **the same lie in the
same kind of carrier**. The **PDF**'s list-item marker was believed to be
watched too, and the Markdown's `- ` and the DOCX's "List Bullet" were said
to be the same property in the other two forms.

**That sentence was half true, and the next round measured the half that was
not** — F57 below. The PDF's marker is watched **by a property of the font
rather than by a witness**: of twelve candidate bullet glyphs, **U+2022 is the
only one the PDF's face leaves unmapped**, so any other bullet is drawn as a
character the reader can see and the marker count breaks. **The Markdown's
`- ` and the DOCX's "List Bullet" are not watched at all.** All three writers
state the rule in their own words (*"a finding and a disclosure are bullets,
because they are entries in a list"*), and only the DOCX's own docstring
says *bullets* rather than *list items* — which is what the mutation
contradicts.

**And the product contradicts itself here, which is worth naming.** The
Markdown's own code says the *shape* of a block *"is the renderer's business"*
— while the PDF's test asserts that a finding **is** a list item. **The fix
resolved that contradiction for one form only.**

#### F48 — the repository's own root guard crashes instead of answering

**Found while F46 was being fixed, in the product, and it is the same shape
as F46 one level down.**

`scripts/check_repo_root.py` exists because, in this project's own words,
*"the single highest-severity operating hazard in this project is a `git init`
rooted above the repository"* — `.gitignore` applies only to its own directory
and below, so a checkout beside unrelated projects is exactly how a whole
directory tree becomes tracked content. **The script exists so that habit is
one command**, and it performs no Git write operation.

**It runs `git rev-parse --show-toplevel` with `text=True` and no
`encoding=`.** On a machine whose locale encoding is `cp936` and whose
checkout path contains non-ASCII characters, git writes the path as UTF-8 and
the script decodes it as cp936.

**And the failure is silent, which is the worst of it.** `subprocess.run`
decodes in a reader thread; the `UnicodeDecodeError` there is swallowed and
the stream comes back as **`None`**, so the script goes on to call `.strip()`
on it and dies with

```
AttributeError: 'NoneType' object has no attribute 'strip'
```

— a message that says nothing about the cause. **A guard that cannot answer
is worse than no guard**, because it is the one thing a person runs before
doing something irreversible.

#### F49 — the same guard, on the other end of the pipe

**Found while F48 was being fixed, and it is F48's mirror image.**

F48 was the guard's **read** side: git writes a path as UTF-8 whatever the
locale is, and the guard decoded it with the machine's encoding. Fixed, and
the guard now answers at a path it could not spell.

**The write side was not fixed, and it is the same defect from the other
end.** The guard prints the path it found, and the machine's stdout encoding
may not be able to represent it — a checkout under a path with an ideograph
in it, printed on a console whose code page is Western. `print` raises
`UnicodeEncodeError` there, and **the guard died before it answered**, with a
traceback and exit code 1: **the same exit code as a legitimate refusal, so
the crash read as an answer.**

**And the asymmetry has a reason, and it is worth stating.** Git's path
output is UTF-8 unconditionally — there is no switch for it — so the read
side must be UTF-8. But the guard's own output goes to a **console**, and what
a terminal can display is the machine's business, not this script's. So the
encoding is left alone and only the *failure* is removed: a character the
console cannot show is replaced rather than raised. **A console that can show
the path shows it; a console that cannot shows the characters it can and
marks the rest; and the guard answers either way.**

**The witness is the other half of the one F48 left.** That one narrows the
**decode**; this one narrows the **console** — the guard's own standard
output is forced to an encoding that cannot represent the path. **The unfixed
guard dies there on every machine; the fixed one answers**, with the exit
codes and the messages it always had.

#### F50 — the four forms do not draw a finding alike, and the fix made three of them agree

**Found while F47 was being fixed, and it is carried as a note rather than as
a verdict — the re-verification is what says whether it is a defect.**

F47's fix asserted the list-item rule for the Markdown, the DOCX and the PDF:
*"a finding, a disclosure and a citation are list items, and a narrative, an
interpretation, a figure and a table are not"*, with the count compared
against the model's own.

**The HTML does not follow that rule.** It draws a claim as
`<p class="claim">` — a **labelled paragraph** — where the other three draw it
as a list item. And the product says of itself, in the Markdown's own
`_draw_item`, that *"the shape … is the renderer's business"*, while the PDF's
test asserts the opposite about the same shape.

**The independent review ruled on it, and the ruling is that the product does
not contradict itself — the *reading* does.** Four reasons, in the reviewer's
own order:

1. **The requirement does not say it.** The task breakdown's §2.3 says the
   renderers *"draw; they do not decide… the renderer's only freedom is how
   it draws them"*, and LC-P1-11's acceptance states the clause as *"the
   content it reads back is the model's"* — **content, not shape**.
2. **The product states each renderer's own rule, and they do not conflict.**
   The Markdown's says the shape *"is the renderer's business"*; the DOCX's
   says *"a finding and a disclosure are bullets… and a narrative is a
   paragraph"*; the PDF's says the same; the HTML's says *"the shape is
   decided on the item's kind"*. **Each is a statement about *that*
   renderer, and a renderer that says the shape is its own and then says
   what it does is not contradicting itself.**
3. **The witnesses are per form by construction.** Each of F47's seven reads
   its own form's carrier with its own form's reader, and the HTML's own
   carrier for the report's name — its `<title>` — is watched.
4. **The PDF's test cannot be read as a statement about the document.** It
   is a test of the PDF, in the PDF's carrier, with the PDF's reader. **Read
   as a document-level rule it is violated by the HTML — and that is where
   the contradiction this record named comes from: in the reading, not in
   the product.**

**So the HTML's `<p class="claim">` is not a defect, and F50 stays a note.**
**But the wording of the note changes, and one residual is added:** the
HTML's shape is **unwatched as well as unlike**. The mutation that draws the
HTML's finding as a `<ul><li>` survives the whole tree, because the HTML's
readers extract text and drop the structure. And the HTML's stylesheet has
**no `.claim` rule**, so in the HTML a finding is not merely a different
shape: **it is visually identical to the prose.** That is a fact about the
product and a product decision — a CSS rule, or a list — and it is carried
here rather than fixed.

**What is not in doubt:** a reader comparing the four forms of one report
finds the finding drawn three ways. **The other three carriers the fix left
alone** — the DOCX's `docProps/app.xml`, which still says *"Microsoft
Macintosh Word"* and *"Normal.dotm"*, the PDF's `/Creator`, which is
reportlab's *"(unspecified)"*, and the producer's name, which is a literal in
two renderers rather than one constant — are **named here and not changed**,
because no rule states what they should carry, and an assertion would be my
assumption rather than the product's.

#### F51 — the list-item witnesses compare a count, and a count cannot see a substitution

**Found by the report path's re-verification, and it is a hole in F47's own
fix.**

F47's fix asserted the list-item rule for the Markdown, the DOCX and the PDF
with a **count**: the number of list items the form draws, against
`len(claims) + len(unresolved_records) + len(footnotes)`.

**And the rule it states has two halves.** *"A finding, a disclosure and a
citation are list items, **and a narrative, an interpretation, a figure and a
table are not**."* The count only sees the first half.

**The mutation that survives the whole tree — measured twice, in two
worktrees:** draw the report's **narrative** (the background paragraph) as a
list item, and the **citation** (the Provenance footnote) as a plain
paragraph. **The count is unchanged (4 = 4), the text is unchanged, the
report's own words are unchanged**, and the whole tree stays green —
**3233 passed, 3 skipped, 0 failed.**

| | the form | what the mutation does |
|---|---|---|
| **N1** | the DOCX | its list items go from `[clm-1, clm-2, rec-9, fn-1]` to `[clm-1, clm-2, rec-9, "The dataset contained 120 rows."]` |
| **N3** | the PDF | the same move: the citation carries no marker and the narrative does |

**The controls prove the hole is only the coordination:** N9 (the citation as
prose alone) and N10 (the narrative as a bullet alone) are each caught by the
very same witness. **It is the swap that is invisible.**

**The Markdown is not a survivor, and the reason is worth naming.** The same
move there (N2/N4) *is* caught — but by
`test_no_text_value_can_open_an_indented_code_block`, **a test about the code
block**, for a reason outside the list item: moving a kind between bullet and
paragraph changes the number of `<ul>`s, and that test notices. **The
Markdown's list-item identity is watched by accident, by a test about
something else; the witness F47 added does not watch it.**

**What it would have let through:** a DOCX in which the report's **background
paragraph is bulleted like a finding** and the **provenance citation is a
flat line** — a reader cannot tell the findings from the prose. The DOCX's
own code says the opposite: *"a finding and a disclosure are bullets, because
they are entries in a list, and a narrative is a paragraph, because it is
prose."*

#### F52 — the three surfaces' own refusals: ten of them are unwatched

**Found by the three surfaces' re-verification, in a sweep the earlier
reviews never ran.**

The two earlier reviews of this scope measured **properties**. The
re-verification also swept **every refusal branch the three surfaces own** —
the API service's own guards (origin, cross-site subresource, session token,
bind address) and the **CLI's own workspace-configuration and policy
refusals**.

**The API's five are watched. The CLI's ten are not.** All ten applied at
once, the whole suite stays green: **3233 passed, 3 skipped, 0 failed** —
the baseline's own numbers.

| | the refusal | what it would have let through |
|---|---|---|
| **RS-6** | a missing workspace configuration is not refused | **the worst group**: a configuration this build cannot read is silently replaced by a default (`schema_version=1, database='labcairn.db', source_dirs=()`) — the operator's source roots and current task are dropped, and the run continues against **a different workspace than the one on disk**, with nothing said. The code's stated reason is *"A configuration this build cannot read is refused rather than guessed at."* |
| **RS-7** | a configuration that is not JSON is not refused | as RS-6 |
| **RS-8** | a configuration that is not an object is not refused | as RS-6 |
| **RS-9** | a configuration with an unknown schema version is not refused | a configuration written by **another build's schema** is read as if this build understood it; the refusal is the only thing separating the two schema versions |
| **RS-10** | a policy file that is not JSON is not refused | the posture stays safe (deny everything) but the operator's own grants are replaced by blanket denials, and the reason given is *"denied"* rather than *"your policy file is broken"* |
| **RS-11** | a policy file without a `"rules"` list is not refused | as RS-10 |
| **RS-12** | a policy rule that is not an object is not refused | the rule is dropped and the policy now **denies** what it used to allow |
| **RS-13** | an unknown key in a rule is silently dropped | a typo in `capabilities` / `root_ids` / `effects` / `task_ids` now **changes what the rule covers**, and nothing says so. The code's stated reason: *"a typo in a rule's scope would otherwise widen what the rule covers."* |
| **RS-14** | a rule with no effect, or an unknown effect, is not refused | a rule meant to be ALLOW is a DENY; a rule meant to be **ASK** never asks, and the capability is refused instead |
| **RS-15** | a source directory outside the workspace is not refused | **the most serious of the ten**: a source root the workspace does not contain is bound, and the walk reads material from **outside** the workspace — a boundary the workspace's permissions do not cover. The code's stated reason: *"A source root the workspace does not contain is a root the operator's selection does not govern."* |

**And the reviewer's judgement is explicit, which is what the gate's bar
asks for: all ten are findings, and RS-15 and RS-13 are the two that would
have let something real through.** Six of the ten fall back to a safe default
and lose the *report*; RS-13 loses a *scope*; RS-15 loses a *boundary*.

**The probes that measured them are worth noting, because they are the
control that makes the list a list:** each mutation was shown to disable
**exactly its own refusal** and leave the other nine intact — for RS-15, the
clean tree refuses with *"the source directory '../outside' resolves to … which
is outside the workspace …"* and the mutated tree answers *"NOT REFUSED. the
paths returned: ['…\outside']"*.

#### F53 — the table of refusals was counted by hand, and it was wrong

**Found by the three surfaces' re-verification, and it is a finding about
the gate's own bookkeeping.**

The sweep of the surfaces' refusals covered **fifteen** branches: five the
API service owns and **ten the CLI's**. **And the three surfaces own
twenty-three** — five in the API, **eighteen in the CLI** — and
`src/labcairn/cli/workspace.py` alone raises `WorkspaceSetupError` at
thirteen sites. The new file of witnesses watches ten of them, and its own
preamble says *"The four configuration refusals — missing, unparseable, wrongly
shaped, of another schema version — each use a different sentence, and each is
watched by a different test"*.

**There are five configuration refusals, not four, and "wrongly shaped" is in
fact the not-an-object check.** So the count was wrong twice over: the number
of sites, and the shape of one of them.

**The eight branches the sweep did not name were found by reading the code,
not by luck** — and six of them survive, each leaving the whole suite at the
baseline's exact numbers (**3244 passed, 3 skipped, 0 failed**):

| id | the refusal | where | what it would have let through |
|---|---|---|---|
| **X1** | a configuration that is not one this build understands | `cli/workspace.py:242` | **exit 0.** `doctor` reports the workspace as initialised with **`source_dirs: []`** — the operator's source roots and current task are dropped and the run continues against **a different workspace than the one on disk**, saying nothing |
| **X2** | a policy rule that could not be read | `cli/workspace.py:355` | exit 3, but **`permission_denied`** instead of `workspace_unusable` — a rule meant to ALLOW is read as a blanket DENY, and *"your policy file is broken"* becomes *"denied"* |
| **X3** | `bind_workspace`'s *"the workspace at X could not be bound: …"* | `cli/workspace.py:427` | **the layer's error escapes and the CLI prints a traceback instead of a refusal** — this is F54, and it is the worst of them |
| **X5** | the providers file cannot be read as JSON | `cli/commands.py:596` | **exit 0.** `doctor` reports **no providers** — the operator's configured model providers silently disappear |
| **X6** | the providers file holds no `"providers"` object | `cli/commands.py:598` | **exit 0.** Same |
| **X7** | the **command's** own source root outside the workspace | `cli/commands.py:838` | exit 3, but **`workspace_unusable`** instead of `invalid_arguments` — the same sentence, but the **module's** refusal answers instead of the command's. The state is still refused; **a client branching on the reason sees a different answer** |
| **X8** | a source root that is not a directory | `cli/commands.py:846` | **exit 0.** The task is created and the non-directory source root is **silently dropped** |

(X4, the eighth, is the API's unknown-capability refusal, and it is caught by
`test_an_unknown_assumed_capability_is_refused`.)

**Two kinds, and they are different findings.** The reviewer instrumented each
branch so that **its condition** — not the branch — writes a marker, and ran
the whole tree:

> **fired: X4, X7.  did not fire: X1, X2, X3, X5, X6, X8.**

- **X1, X2, X5, X6, X8 — the refusal is never exercised.** No test ever
  presents the bad input, so the mutation is a no-op for the suite.
- **X7 — the refusal is exercised, and the suite cannot tell it apart from
  its neighbour.** The test drives exactly that command; the mutation changes
  the refusal's **reason** and the test still passes. **The machine-readable
  reason is the thing to assert, because the reason is what a client
  branches on.**

**And the lesson is bigger than the six.** The review's verdict was that
*"the enumeration is wrong, and that is the correction"* — **a table counted
by hand is wrong the moment the code moves.** So the fix cannot be six more
witnesses; it has to be **an enumeration that cannot be got wrong by hand:**
a test that reads the module, finds every site that raises
`WorkspaceSetupError`, and asserts that **each one is watched.** That is the
same idea as the ledger this gate now uses to check that a merge has not
deleted a witness — **a table that is right by construction rather than right
by counting.**


#### F54 — the CLI crashes where its own docstring promises a refusal

**Found by the three surfaces' re-verification, and it is a defect in the
product, not a missing witness.**

`src/labcairn/cli/workspace.py::bind_workspace` states, in its own docstring:

> *`:raises WorkspaceSetupError: a root could not be bound — the workspace is
> not there, **or a configured source directory is missing**.`*

**That refusal never fires.** `Workspace.bind` refuses a root it cannot bind
with `PathRefusedError`, which is a **`ValueError`**
(`src/labcairn/security/paths.py:146`), and `bind_workspace` catches
**`(WorkspaceError, OSError)`** — `WorkspaceError` is a *different* `ValueError`
subclass (`src/labcairn/workspace/roots.py:54`), and `PathRefusedError` is
**not** an `OSError`. **So the exception escapes the CLI's handler entirely.**

**Measured on the clean tree, through the installed console script, with
`materials` — the directory `init` itself creates and records in the
configuration — deleted:**

| command | exit | refused? | traceback? |
|---|---|---|---|
| `doctor --json` | 0 | — | no — **and it says the workspace is fine** |
| `task create --json` | **1** | no | **yes** |
| `task status --json` | **1** | no | **yes** |
| `sources ingest --json` | **1** | no | **yes** |

Reproduced in **three shapes** — the directory missing, the path a **file**,
the path a **dangling symlink** — and with the path *renamed* rather than
deleted.

**And the CLI's own rule says what this is.** `src/labcairn/cli/commands.py`:

> *"**A refusal is rendered, not raised.** … A script tells a refusal from a
> crash by the exit code alone: `EXIT_REFUSED` is a refusal, and **anything
> else that fails is a bug**."*

Exit 1 is not `EXIT_REFUSED` (3). **By the program's own words, this is a
bug** — and it is the same shape as F42, where a lapsed approval reached the
database as a raw `IntegrityError` and the message said the service was
broken rather than that its answer was too late.

**Three things make it a finding rather than a nit:** the module's docstring
names this exact case and promises a `WorkspaceSetupError`; the trigger is an
ordinary operator action — delete or move the materials directory — on a
workspace `init` made; and `doctor` exits 0 and reports nothing, **so the
operator gets no warning before the crash.**

**It is pre-existing, not a regression from this gate** — `src/` is
byte-identical between the commits the review ran against — and it is in
Scope B, because the CLI is one of the three surfaces.

#### F55 — a witness that a nearly-right refusal satisfies

**Found by the three surfaces' re-verification, in the witnesses themselves.**

The witnesses are **substring** assertions: they assert that the product's
message *contains* the expected words. That pins the substance, and it does
not pin the sentence.

**And here is a refusal that is nearly the right one and satisfies the
witness anyway:** the unknown-effect refusal says *"'permit' is not a valid
Permission (the key is 'effect')"* — **the right value, and a false clause
blaming the key for it** — and **all eleven witnesses pass.**

**A refusal that says something false about the operator's policy, in the
middle of a sentence that is otherwise correct, is not the refusal the
operator is owed.** The witness for it has to be about what the refusal is
*for*.

#### F56 — a witness that was not bound to the site it named

**Found by the three surfaces' re-verification, and the record's own claim
about it is wrong.**

The RS-15 witness asserts the sentence of `source_paths` — *"the source
directory '…' resolves to …, which is outside the workspace …"*. **And
`commands.py::_resolve_source_dirs` speaks a byte-identical sentence** (only
the variable differs). The new file's preamble says the `--source-dir` option
refuses it *"in the command's own words"*; **that is wrong — they are the same
words.**

**They are still two properties** — two sites, two inputs, and two reasons
today (`workspace_unusable` against `invalid_arguments`) — and the command
line's site *is* separately watched, but weakly, by an exit code and a
substring. **And the new witness is not bound to the site it names:** once
the other site carries the same reason, it satisfies the witness too.

**A witness that names a site in its name and is satisfied by another site
is a witness of a sentence, not of a site.**

#### F57 — which marker a form draws a list item with

**Found by the report path's re-verification, and it is a hole in F47's fix
that the fix's own words invited.**

F47 asserted the list-item rule for the Markdown, the DOCX and the PDF, and
the record said the PDF's marker was watched while the Markdown's `- ` and
the DOCX's "List Bullet" were *"the same property in the other two forms"*.

**The PDF's marker is watched by a property of the font rather than by a
witness** — of twelve candidate bullet glyphs, **U+2022 is the only one the
PDF's face leaves unmapped**, so any other bullet is drawn as a character the
reader can see and the marker count breaks. **A property of a font is not a
witness**, and the record said "watched" as if it were.

**And the other two are not watched at all:**

- **N17 — the DOCX.** Drawing the findings as **"List Number"** instead of
  **"List Bullet"** survives the whole tree (`3244 passed, 3 skipped, 0
  failed`). The witness's DOCX reader asks only *"is this paragraph
  numbered?"* — **it accepts any numbered style.**
- **N20 — the Markdown.** Drawing the findings as **`1. `** instead of
  **`- `** survives the whole tree. The witness's Markdown reader says *"this
  is a list item"* **without saying which marker.**

**No test in the tree names "List Bullet"** — grep confirms the literal
occurs only in the product's own renderer.

**What it would have let through:** a report whose findings are a *numbered*
list. **And under the mutation the DOCX contradicts its own docstring** —
*"a finding and a disclosure are **bullets**"* — which is the contradiction
F50's ruling turns on. **A rule that says *bullets* and a witness that asks
only *numbered* are not the same rule, and only one of them was being
enforced.**

#### F58 — the list-item witnesses read a fixture that cannot tell "the first" from "them all"

**Found by the report path's re-verification, and the tree says so itself.**

- **N18 — the DOCX drawing the *second section's* findings as prose**
  survives (`385 passed` in the report path's own suite; `3244 passed` in the
  whole tree).
- **N19 — the *second citation* as prose** survives.

**The cause is the fixture.** The list-item witnesses read the **one-of-each**
fixture. The tree's own fixture docstring says that a comparison reading one
of each *"cannot tell a form that carries the first from a form that carries
them all"* — and **names the two cases**: *"the second citation"* and *"the
second section"*. **The tree's "more than one of everything" fixture is read
by the completeness witness and not by the list-item witnesses.**

**And the reviewer's judgement is explicit, which is what the record should
carry rather than smooth over:** *"this is a coverage gap in the witness's
fixture, not an absent witness — the property IS watched, by three named
tests — and it is less severe than the previous round's survivors; but it is
the tree's own named failure mode, and the fix is one line."*

**A fixture that cannot tell the first from the rest cannot watch the
property it is used for, however good the comparison is.** The comparison was
the previous round's work; this is the input's.

#### F59 — the enumeration's third check is not a check

**Found by the three surfaces' re-verification, by testing the enumeration the
way the product is tested.**

The gate's record said the enumeration "checks the pairing three ways — a
site added without a witness, a ledger entry left behind by a changed
sentence, and **a witness that stopped asserting its refusal are all
caught**."

**The first two are caught. The third is not.** The enumeration's check is
`any(phrase in text for text in compared)`, where `compared` is every string
constant in the witness's body. **That is "mentions", not "compares".**

**Measured:** a witness that **keeps** the refusal's phrase and stops
comparing it — `_ = expected` — **survives the whole tree.** The phrase is
still there, so the enumeration's check passes; the witness no longer
compares it, so nothing else fails.

**And there is a fourth way the enumeration does not check either**, found by
the same reviewer: a refusal that is **removed** together with its ledger
entry and the count lowered leaves the enumeration with nothing to say — and
the tree still holds the property, because the witness that asserts the
refusal's own sentence is still there. **That one is not a defect** — it is
the limit of any enumeration written in the same tree as the thing it
enumerates, and the enumeration does not claim otherwise. **It is worth
stating, because the record's row said "three ways" and the truth is two and
a half.**

#### F60 — the enumeration's boundary is a gap of nine

**Found by the three surfaces' re-verification, and the claim the enumeration
made about its own boundary is false.**

The CLI raises **35** refusal sites: **18** `WorkspaceSetupError` — 15 in
`cli/workspace.py`, 3 in `cli/commands.py` — and **17** command-level
`_refuse(...)` calls. The ledger enumerates the first eighteen, and the
reviewer swept **all eighteen: eighteen of eighteen caught, each by its own
witness.** The second enumeration, which parses the whole CLI package, covers
the `_refuse` refusals as well.

**But the ledger's own docstring says of the seventeen:**

> *"They are watched by the command's own tests."*

**That sentence is false, and the measurement says so: the suite's own text
was searched for each refusal's sentence, and nine of the seventeen appear in
no test file at all.**

**And the two that *are* watched are watched in a way that cannot tell their
neighbours apart.** Nine of the seventeen carry the reason
`invalid_arguments`, so a witness that asserts the reason is satisfied by any
of them:

| the refusal | the clean tree says | with that refusal removed |
|---|---|---|
| `_check_origin` (`commands.py:1488`) | *"An origin is a scheme, a host and a port"* | the **neighbouring** refusal answers: *"An origin carries no path, no query and no fragment"* — the same reason, a different sentence, and the witness passed |
| `_resolve_static_dir` (`commands.py:1518`) | *"is not a directory, so there is no built workbench there to serve"* | the **bind** refusal answers — *"the service could not bind 127.0.0.1:8000 …"* — the same reason again, and the witness passed |

**And one of them is machine-dependent**, which is a finding about the method
as much as about the product: the second `_check_origin` refusal
(`commands.py:1495`) survived on the reviewer's machine only because **port
8000 was busy**, so the bind refusal answered instead. **Re-measured on a
free port, the CLI starts the service and publishes the path-carrying origin
in its own allow-list**, and the test would then fail by **hanging** rather
than by the property. **A green test on a busy machine is not a survival** —
and a witness that only fails when the machine is idle is not a witness.

#### F61 — the diagnostic still calls a workspace fine that no command can use

**Found by the three surfaces' re-verification, and it is the shape F54 was
raised for, in the two sibling cases.**

F54 was raised because *"the operator gets no warning before the crash"*,
and the round's answer was a field saying which configured source roots are
not directories on disk. **It covers one of the three ways a source root can
be unusable.** Measured, through the installed console script:

| the configured source root | what `doctor` says | what the commands say |
|---|---|---|
| **missing** (deleted) | `(initialised, but a source root is missing) … missing: materials` | exit 3, `workspace_unusable`: *"the source directory 'materials' is missing: …"* — **the two agree** |
| **a file** | `(initialised, but a source root is **missing**) … missing: materials` | exit 3: *"… **which is not a directory**. A source root is a directory."* — **the two disagree** |
| **outside the workspace** (`../outside`) | **"(initialised)"** — no warning at all | exit 3: *"… **which is outside the workspace** …"* — **the doctor says fine** |

**The first row is the fix working. The second row is the field named for one
condition and computed for another**: the model says *"`missing_source_dirs`
are the configured source roots that are **not a directory on disk**"* and the
prose says *missing*, so **the operator is told the root is gone when it is
there and is a file.** The third row is the gap the field was added to close,
still open in the sibling case — and it is the more serious of the two,
because the file-root case at least produces a warning.

**Neither is watched.** The witness asserts the JSON field names `["materials"]`
and that the prose contains *"missing"* — **a substring that survives both
defects.** The mutation that makes the prose stop naming the root survives;
the mutation that makes the finding report only a *missing* root and not a
*file* root survives; and the control — the mutation that makes the finding
name nothing at all — **is** caught, so the method is sound and the
property is simply unwatched.

#### F62 — the source root's name is checked by the filesystem before the spelling guard

**Found by the three surfaces' re-verification, as the fix for F54 is ordered.**

`source_paths` asks the filesystem whether the directory is there, and only
then whether the name is one the product can speak. **The order is the
wrong way round:** a name the product cannot speak should be a **refusal**,
and it should be refused by the guard that owns the question, before any
filesystem answer is consulted. The reviewer's conclusion, in its words:
*"the CLI's source-root handling has to ask the product's own spelling guard
before it asks the filesystem, so that an unusable name is a refusal and not
a `ValueError`."*

#### F63 — the rule that does the watching was not itself watched, and it is now

**Found by the three surfaces' re-verification, and it is F30's shape in the
place F30 was raised for.**

F59's fix is a module, `tests/refusal_witnesses.py`, that reads a witness's
**compared** words. **That module was not watched.** Measured against the whole
suite at `47259e0`:

| the rule neutered | the result |
|---|---|
| to *"mentions"* (every string constant counts) | **the whole suite is green — 3276 passed, 3 skipped** |
| to *"mentions"*, and a witness stops comparing as well | **the whole suite is green** |

Its only consumers in the whole repository are
`tests/test_cli_refusal_enumeration.py` and
`tests/test_cli_workspace_refusals.py`, so the whole suite cannot be greener
than those two. **The measurement is not an accident of the selection.**

**"The mechanism that does the watching is not itself watched"** — that is
what F30 was raised for, and the fix that closed F30 put the same shape back
in the same place. **A rule that reads the witnesses needs a witness of its
own.**

**And it has one now.** The fix adds **one file** — `tests/test_refusal_witnesses.py`,
**nine tests** — and **leaves the rule itself byte-for-byte alone**:
`tests/refusal_witnesses.py` is unchanged, its `sha256` at `affedb9` being
`a1c16386f9ceb4b4ffc5dc4aed1afaf66afb2c1860d0299378c28d70179ff7e1`, the
digest it had at `47259e0`. **The rule is not changed; it is watched.**

**The two neuterings that once left the whole suite green, re-measured on the
tree this record ships with — the first against the rule's own file, the
second against that file and the two enumerations together:**

| the rule neutered | the result |
|---|---|
| to *"mentions"* (every string constant counts) | **CAUGHT — 3 failed, 6 passed, 0.17 s** |
| to *"mentions"*, and a witness stops comparing as well | **CAUGHT — 3 failed, 40 passed, 139.48 s** — **the two enumerations go green again**, and the rule's own file is what catches it |

**And the three that went red — the same three in both rows — name the
property rather than the mechanism** —
`test_a_phrase_the_witness_only_holds_is_not_read`,
`test_a_witness_that_compares_and_one_that_only_holds_are_read_differently`
and `test_a_witness_that_stops_comparing_is_not_read_as_comparing` — and the
failure says what is wrong in the terms the property uses:

> *"the phrase the witness compares does not separate the two witnesses: […] A
> rule that reads a mention would read them the same way."*

> *"the rule reads a witness that has stopped comparing as one that compares:
> […] Holding the refusal's phrase is not comparing it."*

**And the second mutation is caught twice over, which is what makes it
survive neither half.** A witness that stops comparing is caught by the two
enumerations **while the rule is intact**; the neutered rule is caught by the
rule's own file. **The two halves together leave the mutation that used to
green the whole suite with nowhere to go.**

**And one more guard, because a shared rule two files could each copy is the
same shape of hole one level down**:
`test_both_enumerations_read_the_shared_rule_and_not_a_copy_of_it` reads both
enumeration files and fails if either stops importing `compared_texts` from
`refusal_witnesses` — or binds it itself.

#### F64 — one command-level refusal was watched by nothing, and the one-line fix did not close it

**Found by the three surfaces' re-verification, and it is F60's shape, one
site further on.**

`src/labcairn/cli/commands.py:1590` — the refusal the `except BindRefusedError`
handler raises, the one whose whole message was `str(error)`, raised when the
service could not bind. **With the refusal removed, the whole suite was
green.**

**And the fix the review suggested is in the tree's own vocabulary.** The
sibling branch (`commands.py:1592`, the `except SystemExit` handler) is watched
by `test_the_failures_that_cannot_happen_are_still_there`, because `SystemExit`
is in the enumeration's `UNREACHABLE_FAILURES`. **`BindRefusedError` is not in
it**, so the refusal that carries the layer's words is the one the enumeration
declines — and nothing else watches it.

**Of the eighteen `_refuse` sites, the enumeration covered fourteen; the other
four were watched by the failures-cannot-happen list and by one command's own
test — and this one was watched by nothing at all.**

**The one-line fix does not close the hole. It was measured.** Adding
`"BindRefusedError"` to `UNREACHABLE_FAILURES` **and** deleting the refusal at
1590, on the baseline `47259e0`:

| the tree | the result |
|---|---|
| `UNREACHABLE_FAILURES` + `"BindRefusedError"`, and the refusal at 1590 deleted | **SURVIVED — 32 passed, 211.72 s** |

**Because that list keeps its books by the failure's *name*, and
`BindRefusedError` has two sites** — `commands.py:1454`, which is reachable
and has its own test, and `commands.py:1590`, which is not. The name is still
handled at 1454, so the staleness check cannot see the removal at 1590.
**A name is not a site.** (For contrast: the same one-line fix *does* catch a
removal at **1454**, because then the name is handled nowhere at all.)

**And the reachability was measured too, because it says what kind of watch the
site can have.** `ensure_loopback` is **a pure function of the address**, and
the CLI asks it the same question about the same address three times:

| # | where | the guard is asked |
|---|---|---|
| 1 | `commands.py:1452` — `_check_host` | the address the operator named |
| 2 | `api/app.py:270` — `create_app` | the same address |
| 3 | `api/app.py:325` — `serve` | the same address — **the call the handler wraps** |

**A routable address is refused at the first question** — the address check's
own refusal answers, the service is never started, and the 1590 site is never
reached. **A loopback address is approved by all three**, so the third cannot
refuse. **The branch cannot be reached through the CLI's own path.** And the
sibling refusal at 1454 deliberately says the layer's words — its docstring
says *"the service's own check is asked first and its own words are used"* —
while this one said nothing of the CLI's own, which is the whole of the hole:
**a refusal that carries no words of the CLI's own is another component's
refusal passing through**, and the enumeration declines it by rule.

**So the fix is at the site, not at the name.** Two parts.

- **The refusal now carries the command's own sentence** — *"the service's own
  guard refused the bind: {error}"* — instead of the layer's words alone. The
  address is deliberately not named: the command asked for one address and the
  service may have been handed another, so a sentence naming the command's
  address would be a claim about an address the refusal is not about. The
  visible wording of this one refusal changes, and **no other refusal's wording
  or reason was touched**.
- **The witness injects the layer's refusal where the layer raises it.** The
  command's `run_service` is replaced with one that asks the layer to serve an
  address the command never checked — `0.0.0.0` — so **the layer's own guard**
  refuses it and the tree is asked what the command does with that. **The
  failure is the layer's own, produced by the code that produces it**, not a
  hand-written error that only looks like one.

**The witness is `tests/test_cli_serve_bind_refusal.py`, one test —
`test_the_command_refuses_a_bind_the_service_would_not_make`** — and the port
is one the operating system says is free, never the machine's 8000.

**Measured — the refusal deleted:**

| the tree | the result |
|---|---|
| the `except BindRefusedError` handler at 1590 deleted | **CAUGHT — 1 failed, 66 passed, 443.04 s** |

**and the failure says what went wrong:** *"the command exited 1 rather than
refusing; the exception was BindRefusedError(…)"*

**And the site is watched twice.** The witness holds the behaviour — a refusal
and not a crash — and the enumeration holds the pairing: with the witness file
deleted the enumeration goes red on *"these refusals have no witness of their
own"*, naming `src/labcairn/cli/commands.py:1604`. **That is the same site the
finding named at 1590; the fix's own lines moved it down, and the enumeration
finds it by what it says rather than by where it is.**

**And a coverage claim the record was carrying is now false.** *"Of the
eighteen `_refuse` sites the enumeration covers fourteen … and this one is
watched by nothing at all"* — **the enumeration now covers fifteen of the
eighteen**, and the three it still declines are `commands.py:365` and
`commands.py:1606` (the failures-cannot-happen list) and `commands.py:1450`
(the address check's own test).

#### F65 — "a witness of its own" was false for five of the thirty-three, and the pairing was unwatched

**Found by the three surfaces' re-verification, and it is a hole in the
*pairing* rather than in the refusals.**

**Two groups hold more than one refusal**, so the enumeration's central claim
cannot hold for five of the thirty-three, and for four of the five the
witness it names is the group-mate's. **The tree still holds every refusal**
— each of the four is caught by a different witness — so no refusal is
unwatched. **What is unwatched is the pairing.**

**And the tree cannot notice the pairing either:** deleting the command's own
witness left **the whole suite green** — 3275 passed, 3 skipped — and two
further witness deletions left **the five CLI-driving files green**, not
merely the two enumerations green.

**So two of the record's claims were false as they stood:** *"a refusal added to
the product is noticed"* and the enumeration docstring's *"a witness removed is
noticed too"*. **What was true was the weaker thing: a refusal added without a
witness is noticed.**

**Both are true now, and the pairing is decided by the value and not by the
phrase.**

**The root cause was that the enumeration matched refusals to witnesses by
*phrase* alone — and a phrase is owned by a *group*, so inside a group every
member had the same candidates and the matching could only *count*, never say
who was who. **The witnesses' values were thrown away, and the values are
exactly what tell the configuration's refusal from the policy's.**

**So a witness is bound to a refusal by the value that refusal names** — the
configuration's path, the policy's path, the providers file's path — and
**where the value cannot decide, the pairing is written down and checked**
rather than left to a count. Four refusals are recorded in `WATCHED_BY`, and
every name in that record must exist in the suite, must compare a phrase its
refusal says, and every witness the derivation offers must be written down.
**The product's wording did not change by one word** — `src/` is untouched by
this fix — and **the enumeration names the witness the ledger names**, which
two new tests check:
`test_the_witnesses_that_are_recorded_are_in_the_suite` and
`test_the_two_enumerations_watch_the_same_refusals_the_same_way`.

**The enumeration's own numbers, read out of the tree at `affedb9`:**

| | |
|---|---|
| refusals | **37** |
| watchable | **34** |
| paired | **34** |
| unpaired | **0** |
| groups | **33** |
| witnesses read | **102** |

**And the thirty-four fall three ways: 27 by "exactly one candidate", 3 by the
value, 4 by the record.**

| how the pairing was decided | how many | which |
|---|---|---|
| exactly one candidate | **27** | — |
| by the value the refusal names | **3** | `workspace.py:236`, `workspace.py:315`, `commands.py:665` — the three that say *"could not be read as JSON"* |
| by the record | **4** | `commands.py:923`, `workspace.py:343`, `workspace.py:535`, `workspace.py:547` |

**And the fix's own report said 26 and 33. Those numbers were right on the
branch they were measured on — where the refusal at 1590 was still not
watchable — and they are wrong on the tree this record ships with, because the
composition changed the count. **They were recomputed, and the record carries
the recomputed ones: 27 and 34.** The witness count moves the same way: it is
**102** at `affedb9`, **101** at `fafb81c`, and **99** at `90d2053` —
**a count is a count of the tree it is counted in**, and the tree the F63
fix made is one where **nine tests were added and no witnesses were**: the
file that watches the rule imports no CLI and names no refusal of the CLI's,
so it is **not a witness module** and its tests are **not** witnesses of a
refusal. **That is what the count says, and it is what the design intends.**

**Measured — the deletions that used to leave the tree green:**

| the deletion | the result |
|---|---|
| the command's own witness | **CAUGHT** — narrow selection: **2 failed, 41 passed, 162.37 s**; **the whole suite: 3 failed, 3287 passed, 3 skipped, 1972.48 s** |
| the module's source-dir witness | **CAUGHT — 1 failed, 99 passed, 843.77 s** |
| the doctor's source-root witness | **CAUGHT — 2 failed, 97 passed, 703.46 s** |

**And that the two narrower deletions turn one or two tests red, and not the
main enumeration, is right rather than a weakness.** The deleted witness is
**one of two** that watch that refusal — the other is still there — so that
refusal is still watched, and **what changed is the record**: *"the ledger and
this enumeration disagree about which witness watches which refusal"*. **That
the record notices the inconsistency is the evidence that the pairing can now
be said out loud.**

**And the last row's run had a third red that this mutation did not cause** —
it is the path-length false failure this record already carries: the refusal's
sentence is split by Rich's wrap at `COLUMNS=200`, so a phrase a test asserts
on does not survive a long `--basetemp`. **A red that is not the mutation's is
read as the mutation's only if the control was not run.**

**And the record's own sentences are watched, because a hand-written table is
wrong the moment the code moves — which is F53's shape, and this fix ends with
one.** The reviewer wrote the guard for the record itself:

| the record changed | the result |
|---|---|
| a phrase in the record changed to one the product no longer says | **CAUGHT — 3 failed, 31 passed, 180.20 s** |
| a witness left out of the record | **CAUGHT — 2 failed, 32 passed, 194.08 s** |

**and the failures say what has to happen next:**

> *"the record names a refusal in src/labcairn/cli/workspace.py::source_paths
> that the product does not raise… The sentence the site writes has changed,
> and the record has to be told."*

> *"these witnesses could watch a recorded refusal and are not recorded for
> it"*, and *"the ledger and this enumeration disagree about which witness
> watches which refusal"*

**So the two false sentences are true now.** *"A refusal added to the product
is noticed"* — **and a *witness* removed is noticed too**, which is what the
enumeration's docstring claimed before it was.

**And the limit that cannot be fixed is still stated rather than hidden:** an
enumeration written in the same tree as the thing it enumerates cannot catch
a refusal that is removed **together with** its ledger entry and the count.
The tree still holds the property in that case, because the witness that
asserts the refusal's own sentence is still there — but the enumeration has
nothing left to say, and it does not claim otherwise.

#### F66 — the crash fix's catches were load-bearing and unwatched, and they are watched now

**Found by the three surfaces' re-verification, as a note.**

The `PathRefusedError` catches the crash fix added to `bind_workspace` and to
the CLI's refusal handler are **load-bearing** — with the catch, a refusal;
without it, a crash — **and the whole suite was green without them.** The F54
witnesses watch the refusals, not the catch.

**And the catches could not be reached through the CLI's own path**, so there
was nothing for a witness to drive — but **a future change to `source_paths`
could have made them reachable, and nothing would have noticed.** That was the
shape of a defence in depth nobody was watching, and it is carried here rather
than left implicit.

**Both halves of that are false now: the catches are reachable, and they are
watched.**

**The reachability is made by injecting the layer's own refusal where the
layer raises it.** The layer's own root binder — `bind_root`, defined in
`src/labcairn/security/paths.py` and used by `labcairn.workspace.roots` — is
substituted with a binder that raises **the layer's own exception, carrying
the layer's own reason code** (`PathRejection.CANONICALISATION_FAILED`).
**The product's own code path is not bypassed: only the layer's leaf function
is replaced, and everything above it runs unmodified** — `Workspace.bind` →
`bind_workspace`'s `try`/`except` → `application_context` → the command body →
`_refusals`' `except` clauses → `emit_refusal` → the exit code. **There is no
equivalent scenario hand-built in the test**, and the injection is a
substitution rather than a race: nothing depends on a directory vanishing at
the right moment or on what this machine's filesystem happens to do.

**And the two catches are told apart by the product's own words.** The same
layer refusal, arriving two ways, is answered two ways:

| the path | the catch that answers it | the sentence |
|---|---|---|
| `task status` → `application_context` → `bind_workspace` → `Workspace.bind` | `bind_workspace`'s | *"the workspace at <root> could not be bound: …"* |
| `task create` → `create_task` → `Workspace.bind` | the CLI's `_refusals` | *"the workspace could not be bound: …"* |

**The phrase *"at <root>"* is the difference, and it is written inside the
`except` clause** — which is the proof that the test did not bypass it: under
the mutation that removes `PathRefusedError` from that catch, witness 1's
message changes from *"the workspace at <root> could not be bound: …"* to
*"the workspace could not be bound: …"*. **If the test had gone around that
clause, the mutation could not have changed the sentence.**

**The witness is `tests/test_cli_path_refused_catch.py`, two tests:**

| the witness | the catch it holds |
|---|---|
| `test_a_refusal_the_workspace_binds_is_answered_with_the_root_named` | the catch in `bind_workspace` |
| `test_a_refusal_that_skips_the_workspace_is_answered_by_the_cli` | the catch in the CLI's own refusal handler |

**Measured — the CLI's catch deleted (CRASH-10):**

| the tree | the result |
|---|---|
| the CLI's `_refusals` loses `PathRefusedError` | **CAUGHT — 1 failed, 102 passed, 617.83 s** |

**and the failure says what the operator would have seen:** *"the layer's
refusal escaped the command as a crash: PathRefusedError(…)"*

**And the two witnesses are deliberately narrow, because a witness that held
both paths could not tell which catch was broken.** Measured on the fix's own
branch, against the eight CLI-driving files:

| the tree | the result |
|---|---|
| the clean tree (the control) | **1 failed, 166 passed** (1232.07 s) — **the pre-existing path-length false failure only** |
| `bind_workspace` loses `PathRefusedError` | **2 failed, 165 passed** (1042.07 s) — the `bind_workspace` witness and the same false failure |
| the CLI's `_refusals` loses `PathRefusedError` | **3 failed, 164 passed** (1177.30 s) — the CLI's witness, **the project's own lint** (`F401 … imported but unused`) and the same false failure |
| **both** lose `PathRefusedError` | **4 failed, 163 passed** (1085.82 s) — both witnesses, the lint, and the same false failure |

**The green half is the measurement.** Removing `PathRefusedError` from
`bind_workspace` cannot affect the CLI's witness, because that refusal is
raised inside `create_task` and never reaches `bind_workspace`; removing it
from the CLI's handler cannot affect the other, because on that path
`bind_workspace` converts the refusal into a `WorkspaceSetupError` before the
CLI's handler ever sees it. **Two witnesses that both went red on one broken
catch would not say which catch was broken, and the blast radius of the
mutation would go unmeasured.** The lint is not a witness — the reviewer's own
earlier finding was that it alone turned red — and the control run is what
establishes that the path-length failure was already there.

### Scope B — what this gate did with the verdict

**The reviewer's verdict was BLOCKED, with two blockers and six notes.** The
two blockers were not of the same kind as the notes, and the difference
matters: **a note is a property stated and not watched, and a blocker is the
watching itself missing.** F30 sat *under* the gate's exit test — the
demonstration's `check()` could be a `print` and the whole of
`tests/test_smoke_path.py` stayed green. F31 was a product defect: a run that
followed an approval planned a second operation, and the approval was spent
against an operation it was never bound to.

**The fixes were made by someone else** — the review wrote no fix into the
repository, which is what makes it independent — and **the reviewer was asked
to re-run its own mutations against them.** That is the second half of the
independence: a reviewer that wrote the fix is no longer a reviewer.

**What each finding got, and the witness that now holds it:**

| | The fix | The witness that holds it |
|---|---|---|
| **F30** | the demonstration's exit code is load-bearing | the demonstration is run three ways as **subprocesses whose exit code is the assertion** — clean, with a claim planted false, and with the service answering with the wrong bytes; **both faults are planted from outside**, by a driver that wraps the demonstration's own `check()` or the API route's own read of the artefact. **The demonstration's source is never edited and it grows no hook** — a test hook inside the gate's exit test would be a new way for it to lie — and the planted run must exit non-zero **and name the planted claim**, so a run that died for some other reason cannot pass |
| **F31** | a run that follows an approval reuses the operation the approval was bound to; a run that follows a crash reuses the operation that was **authorised but never attempted** | the crash branch filters `AUTHORIZED` only, so with an authorised operation *and* an unanswered question for the same work, the run cannot adopt the question; when two authorised operations exist the newest is taken, because the store's order is the ledger's only one |
| **F32** | the CLI's prose form and its JSON form cannot disagree | `task status` is run in **both forms** and the rendered table is read row by row against the field the JSON carries — a swapped label is caught too |
| **F33** | the token is compared in constant time | the comparison is **intercepted** rather than timed — a timing test would be flaky and is the wrong tool — and a second test reads the module's source and requires that `verify` contain no `ast.Compare` at all |
| **F34** | the event stream's session ownership is asserted against the **request's** session | the stream's session is compared against the request's, found by **watching the fork the request makes** |
| **F35** | three of the demonstration's comparisons could be narrowed with no notice | each now has a **control**: the comparison is run once over something that must answer the other way, and the demonstration insists it finds the difference |
| **F36** | the binding's docstring stated a distinction the code could not express | the binding **accumulates** now — the task's binding after the operation is the union of what it held and what this run ingested — and the report says which is which |
| **F37** | a module docstring denied an import the module made | the docstring states what the module imports at module level, in **one marked sentence**, and the test reads the names out of it — so a denial cannot sit beside the truth, whichever way it is worded |

**And the fixes were not the only things the fixing found.** Five more defects
came out of the work — F39 to F43 — and one of them was an authorisation
bypass (F41). **And the reviewer's own re-run found two more** — F44 and F45 —
one of them in the batch's own composition. **The re-run is the last word, and
it is recorded below.**

### Scope B — the re-verification at `5dcd6d0`

**The verdict was BLOCKED, with two mutations surviving the whole suite.** The
gate's exit test is now properly witnessed — the compound case is caught by
name — **but G3 closed on "no mutation survived", and two survive here, so the
row cannot be marked done.**

**Fifty-eight mutations over fifty-four distinct properties, all re-run at the named
commit: fifty-six caught, two survived, none not run.** (The second number was
wrong at first: N1, N2, N4 and N5 each carry **two** anchors — the first
review's case verbatim and a reconstruction — so the mutations outnumber the
properties.) The set adds the four
properties the fix introduced, the four the demonstration gained, the two the
lost witnesses were for, and the first review's own originals wherever they
were recoverable from its own case files. **Seven of the first review's eight
survivors are now caught** — S2↔F33, S3↔F32, S5↔F35a, S6↔F30, S7↔F35b,
S8↔F35c, N3↔F34 — **and S4↔F31 is not.**

#### The first survivor: F31, and its witness was written and then lost

**This is the gate's own composition's fault, and the record says so.** The
witness existed and was correct — and the composition commit `2f7ffc5`, which
rewrote `tests/test_application_layer.py` (501 insertions, 141 deletions),
**deleted four test functions** that its parents had:

| the witness | written in |
|---|---|
| `test_a_run_that_follows_an_approval_reuses_the_operation_it_was_bound_to` | `07c0710` |
| `test_a_run_that_follows_an_approval_reuses_that_approvals_operation_and_not_another` | `07c0710` |
| `test_a_run_that_follows_a_crash_reuses_the_operation_that_was_authorised` | `07c0710` |
| `test_a_stage_that_runs_twice_plans_two_operations` | `500f9cc` |

**The reviewer's own experiment, in a clone:** the witnesses put back from
`07c0710` — the commit that wrote them, not a whole-file swap, which does not
parse against the head's code — leave the control **green** (2 passed, so the
catch is the property and not the restore) and make the mutation **fail with
the property's own words**: `AssertionError: the store holds 2 operations for
one piece of work: [...]`. The probe's own words on the two runs:

```
clean:   the approval was bound to 01a15ff8-445a…   the stage run attempted 01a15ff8-445a…
         operations in the store: 1     TWO OPERATIONS FOR ONE PIECE OF WORK: False
mutated: the approval was bound to 01a15ff8-445a…   the stage run attempted 01a15ff8-4468…
         operations in the store: 2     TWO OPERATIONS FOR ONE PIECE OF WORK: True
```

**And the two properties the other two dropped witnesses were for — R-C1 and
R-C2 — are watched at the head**, by the crash tests that survived. So the loss
was of *witnesses*, not of *properties*, and the two that were lost outright
are the ones above.

#### The second survivor: the demonstration's own comparison is not witnessed

The mutation: `examples/g4_exit_demo.py` compares the CLI's task state **with
itself** — `the_differences(cli_state, api_state)` becomes
`the_differences(cli_state, cli_state)` — and reports "0 differing". **The
whole suite stays green.**

**Why the control does not catch it, which is the point.** The demonstration
already has a control for this comparison: it copies the API's document,
plants a difference in the copy, and insists the comparison finds it. But the
control calls the comparison with **different arguments** —
`the_differences(cli_state, planted_state)` — and the mutation changes
**which arguments the check passes**, not the function. **A control proves the
comparison can fail; it does not prove the check asked it the right question.**
The demonstration's own limitations text already says this, in the abstract:
*"What no control would notice is a check that stopped asking its comparison a
question and answered for itself."*

**What it would have let through:** the demonstration's claim *"the CLI's task
state and the API's task document are the same, field by field"* becomes
vacuous — it reports a comparison it did not make. **The product's property is
watched**, by the test that asks each surface itself; what is unwatched is
the demonstration's own comparison of them.

**And the first review's "caught" for this property does not bear it.** That
verdict came from a run whose suite was **already red for reasons unrelated to
the mutation**, and the demonstration at `6035dbf` **cannot run at this hour**
— the reviewer's own probe: exit 1, `sqlite3.IntegrityError: CHECK constraint
failed: ck_approvals_expiry_after_grant`, at 20:41 UTC. **Every verdict
measured against `tests/test_smoke_path.py` at that commit is measured against
a red file**, so the reviewer discarded the method rather than report it.

#### The compound case for F30 — caught, in four shapes

| | exit | `[ok]` | `[!!]` | says "checks passed." |
|---|---|---|---|---|
| A. the demonstration as it is | 0 | 60 | 0 | yes |
| B. the defect alone | **1** (`FAILED: the report.md the CLI names is the bytes the API serves`) | 25 | 0 | no |
| C. `check()` neutered alone | 0 | 60 | 4 | **yes** |
| D. **the compound case** | **0** | 60 | 4 | **yes** |

D is exactly the defect the first review named, and the new test catches it,
as does the same compound case with the defect in the layer rather than in the
route, and the first review's own two compound mutations, verbatim.

#### The baseline the re-review measured, and the branch head's one line

| command | result |
|---|---|
| `uv run pytest` | **3216 passed, 3 skipped, 0 failed** (33:04) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 260 files already formatted |
| `uv run mypy` | Success: no issues found in 243 source files |
| `pnpm run lint` / `typecheck` / `test` / `build` | exit 0 · exit 0 · **62 tests passed** · built |

**The one-line change between the commit the reviewers were first asked to
verify and the one they verified was checked, not assumed:** it is not a
`check(...)` call, so the count of `[ok]` lines is 60 at both commits and the
exit code cannot be affected by a print; the only test that reads that text
asserts a substring the surviving copy still carries; and **all fifty-four
Python anchors and four web anchors hit exactly once at `5dcd6d0`**.

#### The reviewer's own ledger, because the result is only worth what the method is

1. **The first baseline came back with errors in more than half the suite** —
   the harness's `--basetemp` parent did not exist. Mine, not the product's.
   Fixed, and re-run.
2. **The first R-X7 mutation was a no-op** — it renamed the workbench's mount
   instead of moving it. The harness reported `MUTATION_SURVIVED`, the honest
   answer for a no-op. The case was rewritten, and the rewrite is caught.
3. **Four cases came back as survivors from lanes that were stopped**, because
   a `git checkout -- .` of the clone ran while those lanes were in flight and
   took the mutation out of the tree before pytest read it. Re-run in lanes of
   their own: all four are **caught**.
4. **Two whole-suite runs first reported F31 and R-S1 as "caught" — and the
   catch was the harness's own.** It set `PYTHONIOENCODING=utf-8` for the
   pytest process, and `tests/test_analysis_demo.py` runs a subprocess with
   `text=True` and **no `encoding=`**, so this machine's cp936 codec could not
   read the demonstration's UTF-8 em-dashes; the decode failed and the test
   failed with a `TypeError` that says nothing about the demonstration. The
   harness was corrected and both runs repeated: **both mutations survive.**
   **That is a latent fragility in the suite itself, and it is reported as a
   note.**
5. **The first attempt at restoring the dropped witnesses swapped the whole
   test file**, and that version does not parse against the head's code, so
   the control run was red. **The method was discarded**; the witnesses were
   taken from the commit that wrote them, whose control is green.
6. **The disk filled twice** and killed several runs; those runs were
   discarded and repeated.
7. **The demonstration at `6035dbf` cannot run at this hour**, so that
   comparison is void and is **reported as void**.

#### What the re-review did not check

- **The report path** — no verdict on the gate; that is the other reviewer's.
- **The per-run records behind the first review's "72 runs / 64 caught"**: the
  reviewer recovered forty-nine names over thirty-five properties and could
  not reproduce seventy-two exactly.
- **The F38 catch *rate*** — it was caught on the first attempt, with the
  property's own words (*"80 renders of one recipe in 4 processes preparing the
  environment at once came out as 4 different figures"*), but the rate over
  repeated runs was not measured.
- **Whether the product is *right*, as against whether its properties are
  *watched*.** A mutation table answers the second question only.
- `pnpm format:check` (not in the CI).

**The reviewer wrote no fix into the repository**: its worktree is clean, and
every mutation was applied in a clone outside it.

### Scope B — the re-verification at `86e0226`

**The verdict was BLOCKED, and the block is not where the last round's
blockers were.**

**The 58-mutation matrix is now clean: 58 caught, none survived** — and that
includes the two that survived the last round, each caught by a named test
and with the property's own words:

- **F31** → caught, whole suite, **exactly two failures**:
  `test_a_run_that_follows_an_approval_reuses_the_operation_it_was_bound_to`
  and `test_a_run_that_follows_an_approval_reuses_that_approvals_operation_and_not_another`,
  with *"the store holds 2 operations for one piece of work"*.
- **R-S1** → caught, whole suite, **exactly one failure**:
  `test_the_demonstration_fails_when_the_two_surfaces_really_disagree`. The
  disagreement is planted from outside, and the test requires a non-zero exit,
  the comparison's own label, and `.task.title` — **so a run that died for
  another reason does not pass it.**

**The block is the refusal sweep**, which the earlier reviews never ran: of
the fifteen refusal branches the three surfaces own, **five are caught and
ten survive** — F52 above, and all ten applied at once leave the whole suite
**3233 passed, 3 skipped, 0 failed**, byte-for-byte the baseline.

**What was measured, and against what.** Nine clones via
`git clone --shared --no-checkout`, each checked out at `86e0226` and every
SHA verified; **every mutation applied in a clone**, never in the review
worktree. The baseline: `uv run pytest tests` → **exit 0, 3233 passed, 3
skipped, 0 failed** (1540.8 s); the web package `pnpm test` → **exit 0, 62
passed**. **All 55 case anchors hit exactly once** at `86e0226` — and
exactly once at `5dcd6d0` too. F46 re-measured: **all 24** subprocess calls
in the test tree that decode bytes now name an encoding, and **0** do not.
F48/F49 re-measured before and after at a non-ASCII checkout path: the
`5dcd6d0` guard **crashes** with `AttributeError: 'NoneType' object has no
attribute 'strip'`; the `86e0226` guard **answers** — exit 0, *"OK: repository
root is this LabCairn checkout."* The compound case for F30 reproduced
identically to the record's table.

**And the head's movement, measured rather than reasoned.** `5dcd6d0 →
86e0226` changes sixteen files. `src/` is **byte-identical**, so **0** of
the 54 Python mutations edits a changed file, **0** files changed under
`web/`, and the compound probe's three files are unchanged — and the web's
four mutations and the compound case were re-run anyway. **23 mutations have
a *selection* that changed** — exactly the cases whose witness set moved — and
all 23 were re-run. **No witness was lost:** 94 test files at each commit,
none added or removed, **0 test functions removed and 17 added**. **The
failure mode that produced last round's F31 — the composition deleting a
witness — does not recur.**

**The reviewer's own ledger, and it is the sharpest thing in this round: a
long `--basetemp` broke a test that had nothing to do with the property.**
The CLI renders its refusals through Rich, which wraps at `COLUMNS=200`, and
the rendered path is in the message — so a long basetemp pushes the wrap
inside the phrase `test_init_refuses_an_existing_workspace` asserts on.
**Measured on a clean tree, same clone, nothing mutated: long basetemp → the
test fails; short basetemp → it passes.** That produced **five false
"catches" in the first sweep run** and a false failure in the first two
whole-suite runs; both sets were discarded and repeated. Also: two whole-suite
runs at once **raced on the shared matplotlib configuration directory** —
nineteen `test_analysis_service.py` tests failed, and that file passes 38/38
run alone; both runs were discarded and repeated one at a time. Also: a
sweep lane stopped mid-case, leaving its mutation in the clone, and the next
case failed with a catch that was not its own; the runner now checks the tree
is clean before and after every case. Also: **the project's own `ruff` caught
a mutation, not the property** — three sweep mutations had a 112-character
line, and the README's test runs `uv run ruff check .`, so the combined
run's single failure was `E501 Line too long`; all three were rewritten to
the form `ruff format` itself proposes, and **all fifteen sweep mutations
are now lint-clean**, and the fourteen ruff-dirty matrix mutations were each
checked to have a property-specific witness.

**What the re-review did not check:** the report path (Scope A's); the 75
sweep branches in `model.py`, `manifest.py`, `revisions.py`, `checks.py` and
`build.py` (inherited); the application layer's own refusals (Scope A's
territory); **flakiness under repetition** — each mutation ran once at one
seed, and the F38 catch *rate* is still unmeasured; whether the product is
**right**, as against whether its properties are **watched**; `pnpm lint` /
`typecheck` / `build`; the application-layer properties other than the
material-ingestion and approvals ones, which are in the 58 and are watched.

### Scope B — the re-verification at `15cd63d`

**The verdict was BLOCKED. The refusal sweep closed; the enumeration behind
it did not.**

**Ninety-one mutations measured: eighty-six caught, five survived.** And the
shape of the result is worth stating plainly, because it is the shape the
gate exists to produce:

| | mutations | caught | survived |
|---|---|---|---|
| **the refusal sweep** — fifteen branches, **each against the whole suite** | 15 | **15** | — |
| **the 58-mutation matrix** (54 Python against their own selection, 4 web under vitest) | 58 | **58** | — |
| **the three the sweep did not know about** | 3 | 0 | **GAP-B, GAP-C, GAP-D** |
| the five survivors' *wording* — thirteen near-misses | 13 | 11 | **NEAR-8, RS15-C** |
| the web package | 4 | **4** | — |

**The sweep closed, and the implementer's gap was the thing that closed it.**
The previous round's sweep selected `tests/test_cli.py` and
`tests/test_developer_launch.py` — **which does not name the new witness
file**. Re-measured in isolated clones, **RS-15 and RS-6 both survive that
selection** (62 passed, exit 0) while both are caught by the whole suite.
**Had the sweep been re-run with its old selection, the ten CLI refusals
would still have looked unwatched.** The whole-suite run is what closes the
block — and it does close it: **fifteen branches, fifteen caught, each by
exactly its own witness, the other ten green.**

**The five that survived are the enumeration's, not the witnesses'.** F53,
F54 and F55 above. **The three refusals nobody watched are three the table
never counted**, because the table was counted by hand and was wrong about
what the module raises. **And the two loose witnesses are loose in the way a
substring assertion is loose** — one satisfied by a refusal that says
something false about the operator's policy, one not bound to the site it
names.

**The head's movement, measured rather than reasoned.** `86e0226 → 15cd63d`
changes **exactly two files, both under `tests/`**; `src/` and `web/` are
**byte-identical**, and **0 of the nineteen files the mutations edit**
changed. 122 → 123 test files, **0 test functions removed and 11 added** —
**the F31 failure mode does not recur.** It cannot reach any mutation's
subject; it changes only the whole suite's composition.

**The reviewer's own ledger, and it is a list of ways to fool yourself:**

- **Two lanes shared a clone**, and one's restore pulled the other's mutation
  out of the tree before pytest read it — producing **two false survivors**
  (NEAR-4 and F35g). Both re-measured clean: **caught**.
- **CRLF in the lane list files** made every path carry a `
`, and one
  round was lost to it.
- **A runner flag was missing**, so a sweep round ran file-local rather than
  whole-suite. Re-run.
- **`uv run` spawns pytest rather than exec'ing it**, so killed lanes left
  orphaned suites that starved the machine; **six whole-suite runs died
  part-way at 24–28%** of the way through. The wrapper was removed.
- **The machine is memory-starved** — 63 GB total, 1–5 GB free, other
  sessions running about seventeen suites — and the long-`--basetemp` trap
  was **re-measured** rather than remembered: long → `test_init_refuses_an_existing_workspace`
  fails; short → passes. Matplotlib's machine-global configuration directory
  was isolated per lane.
- **A clone under a running baseline was deleted** by the setup script; that
  baseline was discarded and re-run.
- **One of the reviewer's own mutations was invalid** (a `NameError`); it was
  rewritten rather than reported as a survivor.

**And the two facts about the product that the witnesses uncovered, which the
record carries rather than smooths over:** `source_paths` and
`_resolve_source_dirs` speak **byte-identical sentences**, so the new file's
preamble was wrong; and the unknown-effect refusal can carry **a false clause
blaming the key** while still satisfying a witness that checks for the right
value.

**What the re-review did not check:** the report path (Scope A's); the
application layer's own refusals; `pnpm lint` / `typecheck` / `build`;
whether the product is *right* as against whether its properties are
*watched*; flakiness under repetition; the five API refusals' *wording*
tightness; and the CLI's usage-error refusals in `commands.py` beyond the
two it probed.

### Scope A — the re-verification at `15cd63d`

**The verdict was PASS WITH NOTES — the first time this scope has not failed,
and the fix under review closed the hole it was made to close.**

**One sentence for the reason: every mutation that breaks a stated property of
the report path is caught, each by a named test — 143 of 149 — and the five
that survive break none.**

**What was measured, and against what.** Everything below was measured
against **`15cd63d`** in four clones each **verified byte-identical to the
commit** (394 tracked files, 0 differ) — a byte check, not `git status`, and
the reason is in the ledger.

| | mutations | caught by a named test | survivors | measured nothing |
|---|---|---|---|---|
| the Q-series (the previous round's survivors) | 19 | **19** | — | — |
| the T-series and the N-series (the matrix) | 31 | **27** | **3** — N7, N17, N20 | **1** — N19, a no-op |
| the refusal sweep (every `raise` in Scope A) | 99 | **97** | **2** — 725, 733 | — |
| **total** | **149** | **143** | **5** | **1** |

**Every survivor was re-run against the whole tree**, not only the Scope A
subset.

**F51's witnesses caught the swap they were made for, and caught six more
besides.** The predecessor's N1 (the DOCX), N2 (the Markdown) and N3 (the PDF)
are each caught by the witness that is about them, and the multiset's own
blind spots — a duplicate, a text in another's bullet, an exchange, a section,
two texts in one bullet, a dropped narrative — are caught too.

**The baseline the re-review measured, at `15cd63d`:** the whole suite
**3244 passed, 3 skipped, 0 failed** (32:28), exit 0 · `ruff check` All checks
passed · `ruff format --check` 261 files already formatted · `mypy` **Success:
no issues found in 244 source files**.

**And the five survivors, with the reviewer's judgement on each stated rather
than smoothed over.**

- **N7 — the HTML draws a finding as a list item.** The HTML's text is
  unchanged; only the shape differs. **Why it is not a defect:** the HTML's own
  `_draw_item` says *"The shape is decided on the item's kind"*, and §2.3 gives
  the renderer *"the renderer's only freedom is how it draws them"*. This is
  the residual F50's ruling already carries, and the ruling still stands: **the
  HTML's stylesheet has no `.claim` rule**, so in the HTML a finding is
  **visually identical to the prose**.
- **N17 — the Markdown draws its findings as an ordered list.** The words, the
  count of list items and the multiset of their texts are identical. **Why it
  is not a defect:** the rule the witnesses state is that a finding *is* a
  list item, and **an ordered list's entries are list items in CommonMark**,
  which is the parser the witness itself uses. The DOCX witness says the same
  in its own words: *"The counting is structural rather than by the name of a
  style, because the shape is the renderer's business."* **The product states
  this freedom; N17 exercises it.**
- **N20 — the DOCX draws its findings as a numbered list.** `"List Bullet"`
  becomes `"List Number"`. The same argument, the same class as N17.
- **725 and 733 — the layer's two part-refusals.** Unwatched, **and
  unreachable**, measured twice by two methods: the unreachability probe
  instrumented each guard so that its **condition** — not the branch — writes
  a marker, and 504, 516, 556, 579 and 790 **fired** while **725 and 733 never
  became true**. And they are **structurally** unreachable: `_the_upstreams`
  receives **the same `receipts` tuple** the builder used, and `_the_parts`
  takes each part's path and hash **out of the document the builder made** —
  which copied them from the same receipt the guard consults. The guard's own
  docstring says so. **What removing them would have let through: nothing
  observable.**

**The two rulings the review was asked for.**

- **F50 — does the record misstate the ruling? No.** The rule is per form; the
  HTML's `<p class="claim">` is not a defect; the residual is that the HTML's
  shape is unwatched as well as unlike. **The record's four reasons are the
  product's own sentences, and all four check out against the source** — the
  Markdown's *"the shape … is the renderer's business"*, the DOCX's *"a
  finding and a disclosure are bullets… and a narrative is a paragraph"*,
  the PDF's *"A finding and a disclosure are drawn as bullets, because they
  are entries in a list"*, the HTML's *"The shape is decided on the item's
  kind"*.
- **725 and 733 — can the gate close on a tree carrying them? Yes.** **Under
  the gate's own first rule they are not survivors** — *"a mutation that
  changes nothing is not a mutation"* — and removing either changes **no
  observable behaviour**. They are not the class the gate has been finding
  all night: F27 was a finding because its refusal was **reachable and
  load-bearing**, and these two are the opposite. **But they are not nothing,
  and the record says so: the property they state has no witness.** The tree
  is safe today because **the builder cannot produce the state**, not because
  a test forbids it — **and the moment `_the_parts` or the builder's
  copy-from-receipt rule changes, these two guards become the only thing
  standing between a report and a part the ledger never recorded.** That is
  the moment they must be watched, and it is said here so that the successor
  is told.

**The corrections the review asked the record to make — and they are made.**
The prose of this section said *"Forty-three mutations, forty caught"* while
the table beneath it said fifty-two and forty-seven; the table is right. The
row for the layer's two part-refusals now reads *"measured unable to fire"*,
the way the `25bad72` table reads for B6/B7 — as it stood, "2 | 0 | 725, 733"
read as *unwatched and therefore a survivor*, while the prose said they cannot
fail, **and both could not stand as written**. F47's sentence about the
markers now says that the witnesses say **which** items are list items and not
**how they are marked** — the marker is watched only in the PDF (N21 is
caught), and the Markdown's `- ` and the DOCX's "List Bullet" are free,
deliberately. And the claim that *"neither message appears in any test file"*
is now precise: the phrase *"is not the artefact the ledger recorded"* **does**
appear, at `tests/test_analysis_report_checks.py:1547` — but it witnesses **the
manifest artefact's refusal at `application/reports.py:504`**, a different
guard with a different condition.

**The head's movement, measured rather than reasoned.** `86e0226 → 15cd63d`
changes **two files and no product file**: one added
(`tests/test_cli_workspace_refusals.py`) and one changed
(`tests/test_analysis_report_render.py`), **none removed**, and **none under
`src/`** — the report path's product is byte-identical, so every measurement
of the product's *behaviour* is the same measurement it was last round. **In
the changed file, 0 test functions lost, 11 added (all helpers) and 3
witnesses strengthened in place** — the Markdown's 18 → 37 lines, the DOCX's
17 → 35, the PDF's 21 → 40. **The failure mode the record calls F44 — a merge
resolving a conflict by keeping both sides of a deletion — did not recur.**
And the 75 sweep branches the previous round inherited **were not
inherited: all 99 of Scope A's branches were re-swept at this commit.**

**The reviewer's own ledger, and it is a list of ways to fool yourself.**

- **The round's own earlier attempt was still running when this one began**,
  sharing the harness directory and **mutating the trees under measurement** —
  found because twenty DOCX anchors reported "occurs 0 times" against lines
  the reviewer had just read. **Every lane was discarded and re-run from
  scratch**, and the discarded logs are kept beside the good ones with
  `-contaminated` in the name.
- **`Path.write_text` on Windows rewrites a mutated source as CRLF**, and
  `.gitattributes` says `* text=auto eol=lf`, so git's diff normalises it
  away: **`git status` reports the file clean and `git checkout --` skips
  rewriting it.** The tree under measurement was therefore **not the commit's
  bytes**, and every LF-anchored mutation missed. Fixed by byte-exact
  `read_bytes`/`write_bytes` throughout, and by a **byte-level** check —
  because `git status` cannot answer the question.
- **Two pytest runs sharing one `--basetemp` destroy each other's test
  tree**: pytest erases the basetemp at the start of a run. The first
  baseline came back **3243 passed, 3 skipped, 1 error** — a test whose
  `init` fixture had made the workspace and whose next command found it
  *gone*. **Re-run with a private path: 3244 passed, 3 skipped, 0 failed.**
- **A catch that is not a catch.** The whole-tree "catch" of **725** is the
  README's own test, and its red is **the tree's own gate refusing the
  reviewer's own edit**: with 725 neutralised, `mypy` reports three
  `union-attr` errors. **733's neutralisation type-checks, so 733's
  whole-tree green is a genuine measurement.**
- **Two mutations caught by the project's own `mypy`** (a tuple assigned to a
  `list[str]`), rewritten type-clean and re-run.
- **A measurement invalidated by the machine**: one whole-suite run was
  killed at 64%, and the sweep's whole-tree re-check **produced no summary
  line**, which the predecessor's driver would have read as *"nothing
  noticed"*. **Every run must now produce a summary or it is INVALID and
  retried; a run with no summary is never read as a survival.**
- **A contamination between the reviewer's own runs**: another session
  restored the tree under a running measurement, and one case first reported a
  survivor while its own witness run had gone red — **the two runs
  contradicted each other.** The driver now writes bytes, re-applies and
  verifies the mutation before and after every run, and **treats a
  witness/scope disagreement as a contradiction to be re-run.**
- **A mutation that measured nothing**, and is not called a survivor: N19 is
  a **no-op** — the fixture the witnesses read holds one disclosure, so the
  mutation changes nothing. The driver measured the change and said so.
- **A survivor checked by hand, not inferred from a red**: for N7, N17 and N20
  the driver measured *what* changed — in all three the **text is identical**
  and only the shape differs.

**What the re-review did not check:** **whether the product is *right*, as
against whether its properties are *watched*** — a mutation table answers the
second question only; flakiness under repetition (each mutation ran once, at
one seed, with `pytest-randomly` disabled); the CLI, the API, the store, the
ingestion, the approvals, the stages and the `web/` tree; the DOCX's
`docProps/app.xml`, the PDF's `/Creator` and the producer's name as a literal
in two renderers — **confirmed by grep that no test reads any of them**; and
**the content of F51's witnesses beyond mutation** — the expectation is read
out of the **model** and never re-derived from a renderer's output, the
comparison is a **multiset**, so a duplicate is visible, and each of the three
readers reads its own form with a standard library and not with the writer.


### Scope B — the re-verification at `eed91fa`

**The verdict was FAIL, and the sentence for it is the one the gate's own bar
gives: the matrix is clean and the sweep is clean, and neither of those is
enough.** Three things were measured that the record says are done and are
not — F59, F60 and F61 — plus the ordering F62 names.

**The matrix holds.** The record's headline number — *fifty-eight mutations
over fifty-four distinct properties* — is **confirmed by this re-run**: 58
mutations, **58 caught, none not run**, and the four duplicated properties are
N1, N2, N4 and N5, each carrying two anchors, exactly as the record says.
**The ledger's site coverage is complete and honest too**: all **eighteen**
of its entries were swept, one mutation per site, and **eighteen of eighteen
were caught, each by its own witness.**

**What the review measured this round: 121 mutations** — the 58-mutation
matrix, the 23-case refusal sweep, 22 further cases against the enumeration
itself, the crash fix and the new diagnostic, and **the 17 command-level
refusals the enumeration does not count** — plus the baseline, a byte
verification of every clone, and four behavioural probes.

**The crash fix works, and the before and after were measured, not argued.**
At `15cd63d`, with `materials` — the directory `init` itself creates —
deleted, `task create`, `task status` and `sources ingest` all exited **1
with a traceback**. At `eed91fa` the same three commands exit **3** with
`workspace_unusable` and no traceback.

**And the review's own ledger is part of the record, because the result is
only worth what the method is.** Two of its entries are worth naming here:
**a static audit of the `_refuse` sites was written, used, and discarded** —
chunk matching is not sound — so the measurements are the mutation
measurements and the static work is a cross-check labelled as one. And **one
measurement was machine-dependent and had to be redone**: the first reading
of the origin refusal said the mutation *survived*, and it survived because
**port 8000 was busy on that machine**, so a different refusal answered.
**A green test on a busy machine is not a survival**, and the report says so
in the place where it matters rather than reporting the first number.

**What the review did not check:** the report path (Scope A's); the
application layer's own refusals; the 75 sweep branches in `model.py`,
`manifest.py`, `revisions.py`, `checks.py` and `build.py` (inherited); the
`web/` package beyond its four mutations; **flakiness under repetition** —
each mutation ran once at one seed, and the F38 catch *rate* is still
unmeasured; **whether the product is right, as against whether its
properties are watched**; the carry-level witnesses of F47 and F51; and
**whether the two `PathRefusedError` catches would ever fire** — they cannot
be reached through the CLI's own path today, and a future change to
`source_paths` could make them reachable, and nothing would notice.

### Scope A — the re-verification at `eed91fa`

**The verdict was PASS WITH NOTES, and it did not move.** The sentence for
the reason: **the report path's product is byte-identical to the commit the
review passed last time**, and the strengthening under review closes the two
holes it named — the marker and the fixture — while catching everything it
caught before **and two more**.

**What was measured, and against what.** Everything was measured **against
the commit**, in clones checked out at it and **byte-verified** against it,
never in a working tree that happened to have the changes.
`git diff 15cd63d eed91fa -- src/labcairn/reports src/labcairn/application/reports.py
src/labcairn/sources/locators.py` is **empty**: **so the only thing that
could change this round was the witnesses** — which is exactly what the brief
says is new, and what the review measured hardest.

| | the lane | what it is |
|---|---|---|
| **Q** | the Q-series | the previous round's 19 survivors, re-run |
| **T/N** | the matrix | 31 mutations — the carriers and the list-item rules |
| **sweep** | the refusal sweep | **every one of the 99 `raise` branches in Scope A**, one at a time |
| **probe** | the witness probe | the three strengthened witnesses, broken hard — 24 cases, 15 of them new |
| **probe** | N25, N26 | **a disclosure drawn as prose**, in the DOCX and in the Markdown — the one kind of list item the multiset carries that no case had singled out |

**166 distinct mutations** in all (19 + 31 + 99 + 15 + 2), each applied
byte-exactly, with the tree byte-checked before and after every case.

**The survivors, and what the review says about each.**

- **N7 — the HTML draws a finding as a list item.** The text is
  byte-identical; only the shape differs. **Why it is not a defect:** the
  HTML's own `_draw_item` says *"The shape is decided on the item's kind"*,
  and §2.3 gives the renderer *"the renderer's only freedom is how it draws
  them"* — **F50's ruling, which stands and which this round did not
  disturb.** **The residual F50 already carries:** the HTML's stylesheet has
  **no `.claim` rule**, so in the HTML a finding is *visually identical to
  the prose* today. The mutation would not have made that worse; it would
  have made it *different in a way nobody watches*.
- **B6 and B7 — the statement and every drawing site move together**, and
  **B9 and B10 — the statement is loosened to name both kinds.** Both
  survive, and both leave the product self-consistent. **So the binding is
  one-directional: a statement may name more than it draws, but not less.**
- **725 and 733 — the layer's two part-refusals.** Nothing observable
  today; the builder cannot produce the state they refuse. **Re-measured at
  `eed91fa`, not inherited from the record:** 725's Scope A suite is green
  (*385 passed*) and the whole tree's **only** red is the README's own test —
  **and that red is not a catch of the property**, because with the guard's
  narrowing gone `mypy` reports three `union-attr` errors on the mutated
  source and the README's test really runs `uv run mypy`. **The tree's own
  gate refused the reviewer's own edit.** 733's Scope A suite is green and
  **the whole tree is green, byte-for-byte the baseline** — **a genuine
  unwatched branch**, and the same one the previous round found.

**The baseline it measured, at `eed91fa`:** the whole tree **3257 passed, 3
skipped, 1116 warnings** — and N7 against it is green **byte-for-byte the
baseline**, which is what "survived" means here.

### Scope B — the re-verification at `47259e0`

**The verdict was BLOCKED, and the sentence for it is: the four fixes in
that commit are real, and three of them are unwatched.** The spelling
guard's place in the order, the diagnostic's field, the `_refuse` boundary
and the enumeration's "compares, not mentions" are all **measured working,
from outside, at `47259e0`**. What is not there is the watching on three of
them: **five mutations survive the whole suite**, and the gate's own bar —
G3 closed on *"no mutation survived"* — is not met.

**Why not PASS, and why not PASS WITH NOTES:** a survivor is a failure, and
there are five of them against the whole suite, not against a selection.

**What the review measured this round:** the 58-mutation matrix **clean**
again; the sweep, read **against the enumeration** rather than against a
counted list; the enumeration itself, asked the questions its docstring
claims; **all fourteen** watchable `_refuse` sites; the crash fix and the
diagnostic, **each of the four ways a source root can be unusable**; and the
machine-dependent case re-measured **on a free port** (52234), where the
witness now **fails for the property in 4.59 s** and does not hang — while
with the refusal removed the CLI **starts the service** and publishes the
path-carrying origin in its own allow-list.

**And it found the shape the whole gate keeps finding:** the rule that reads
the witnesses is not watched, one refusal is watched by nothing, and the
**pairing** between a refusal and its witness is unwatched — F63, F64 and F65.

### What the re-verifications found, and what the gate did with that

**Both re-verifications came back negative, and every finding they named is
fixed.** The table below is the fixes' ledger; each row's witness is a
**named** test, and each was checked by breaking the property in the
implementation and watching that test fail.

| | the finding | the fix | the witness that holds it |
|---|---|---|---|
| **F44** | **this gate's own composition deleted the witnesses for F31** — four test functions gone from `tests/test_application_layer.py`, and a fifth gone earlier at `b30dea4` | the four are back, adapted to the head's own helpers (`_die_between_the_intent_and_the_attempt`, `_a_stage_request_in`, `_the_operations`), and `_use()` takes the resource key again so a test can ask about a second file | `test_a_run_that_follows_an_approval_reuses_the_operation_it_was_bound_to` — *"the store holds 2 operations for one piece of work"* |
| **F45** | the demonstration's own comparison of the two surfaces was unwatched — its control calls the comparison with *different arguments*, so changing which arguments the **check** passes left the control untouched | a witness that plants the disagreement **from outside**: a third mode in the test file's driver wrapping `routes.read_task_state`, requiring the demonstration to exit non-zero **and name the differing field**. **The demonstration's source is never edited and it grows no hook**, and its check count stays 60 | `test_the_demonstration_fails_when_the_two_surfaces_really_disagree` |
| **F46** | a test's pass or fail depended on the **machine's locale encoding** | the encoding is stated on **both** sides of every subprocess that decodes — pinning only the parent's decoding turns the failure around rather than fixing it | the two analysis-demo tests pass with `PYTHONIOENCODING` set to utf-8, gbk, latin-1, cp1252 and unset |
| **F47** | **what a form says about itself, outside its own text** — the DOCX's title property and description, the PDF's `/Title` and `/Author`, and the list-item shape of the Markdown and the DOCX | seven witnesses, each reading its carrier **with the reader its own form is read by** (`zipfile`+`ElementTree`, `pdfplumber`, `markdown-it-py`) and comparing it with **the document's own value** — no literal in the test, and **no product change**: the carriers already hold what they should | `test_the_docx_carries_the_title_in_its_own_title_property`, `test_the_pdf_carries_the_title_in_its_own_title`, `test_the_pdf_names_the_producer_the_docx_names`, `test_the_docx_carries_the_limit_in_its_own_description`, `test_the_markdown_draws_a_finding_as_a_list_item`, `test_the_docx_draws_a_finding_as_a_list_item`, `test_the_pdf_marks_one_list_item_for_each_of_the_report_s_list_items` |
| **F48** | **the repository's own root guard** crashed instead of answering at a path it could not spell — git writes the path as UTF-8, the guard decoded it as the machine's encoding, the decode failed in subprocess's reader thread, and the capture came back as `None`, so the guard died on `None.strip()` with **exit code 1: the same code as a legitimate refusal** | the guard states the encoding it decodes with, and `errors="replace"` is the promise that it always answers | three tests in `tests/test_repo_root_guard.py`, one of which runs the guard at a non-ASCII checkout path under a wrapper that forces every unstated text stream to be decoded as ASCII — **a machine no UTF-8 locale has**, so the witness works on every machine |
| **F49** | the same guard, **the other end of the pipe** — the guard prints the path it found, and the machine's stdout encoding may not be able to represent it | the encoding is left to the machine (a console that can show the path should show it) and only the *failure* is removed: a character the console cannot show is replaced rather than raised | a second wrapper that narrows the **console** rather than the decode — the unfixed guard dies there on every machine; the fixed one answers |
| **F51** | **the list-item witnesses compared a count, and a count cannot see a substitution** — draw the narrative as a list item and the citation as prose, and the count is unchanged | the witnesses now compare **which** items are list items, as a **multiset** of the texts the form draws against the texts the model holds. The DOCX's reader carries the identity in the paragraph's `w:t` runs; the PDF has no paragraph mark, so the paragraph behind a bullet is recovered from the page's **geometry** | the same three witnesses, now saying *"the form does not draw […]; the form draws […]"* |
| **F52** | **the three surfaces' own refusals: ten of them unwatched** — the CLI's configuration and policy refusals | ten witnesses, each presenting the bad input and asserting **the product's own refusal**, with each distinguished from its neighbours (the missing, the unparseable, the wrongly shaped and the unknown-version configuration; the four policy-file refusals) | `tests/test_cli_workspace_refusals.py` — a new file, because the CLI's own test module is being added to by other changes at the same time |

| **F53** | **the table of refusals was counted by hand, and it was wrong** — the sweep named fifteen of the twenty-three refusal branches the three surfaces own, and six of the eight it missed survived the whole suite | the six now have witnesses, each asserting the product's own **reason** as well as its sentence, and each told from its neighbours. **And the remedy the finding names — an enumeration that cannot be got wrong by hand — is built**: a test that reads the CLI's own source, finds every site that refuses, and checks that **every refusal has a witness of its own**. **A refusal added to the product is noticed whether or not anyone remembers to come and write a witness for it — and a *witness* removed is noticed too, which the enumeration's docstring claimed before it was true.** **The enumeration landed in two commits, and this row was written about the second while the tree carried the first** — which is what the three surfaces' re-verification caught, and it is recorded here rather than tidied away | **two enumerations, in two files**: `test_every_refusal_site_in_the_cli_is_watched` in `tests/test_cli_workspace_refusals.py` (the *ledger* — it finds every `raise WorkspaceSetupError` and checks the pairing three ways) and `tests/test_cli_refusal_enumeration.py` (the *derived* one — it parses the whole CLI package, covers **fifteen of the eighteen** the command's own `_refuse(...)` refusals — **and the refusal that used to be watched by nothing is watched now**: it carries the **command's own sentence** rather than the layer's words alone, and a witness injects the layer's refusal where the layer raises it — and it binds a refusal to a witness **by the value that refusal names**, so that a witness of the configuration's refusal cannot answer for the policy's. **Thirty-seven refusals, thirty-four watchable, thirty-four paired, none unpaired**, and **a witness removed is noticed**: the derivation says which witness watches which site, and the four pairings the value cannot decide are **written down and checked**). **The third of the ledger's three ways is false — see F59 — and the derived one's boundary is what F60 is about** |
| **F54** | **the CLI crashes where its own docstring promises a refusal** — a configured source directory the workspace cannot bind let `PathRefusedError` (a `ValueError`, and not an `OSError`) escape the CLI's handler, and `task create`, `task status` and `sources ingest` died with a traceback and **exit 1, which is the same code as a legitimate refusal** | the CLI now refuses a missing source directory and a source root that is not a directory **itself**, naming the directory the operator named; and `bind_workspace` catches `PathRefusedError` beside the two it already caught, so the layer's refusal becomes a refusal rather than a crash. **All three commands now exit 3 with a payload and no traceback** | `test_a_configured_source_directory_that_is_missing_is_refused` and the six beside it — **and the two that watch the catches**: `test_a_refusal_the_workspace_binds_is_answered_with_the_root_named` (the catch in `bind_workspace`) and `test_a_refusal_that_skips_the_workspace_is_answered_by_the_cli` (the catch in the CLI's refusal handler) |
| **F55** | a witness that a nearly-right refusal satisfies — the unknown-effect refusal says *"the right value, and a false clause blaming the key for it"*, and all eleven witnesses passed | **carried as a note, not fixed.** A refusal that says something false about the operator's policy, in the middle of a sentence that is otherwise correct, is not the refusal the operator is owed; the witness has to be about what the refusal is *for* | — |
| **F56** | a witness that was not bound to the site it named — the RS-15 witness asserts the sentence of `source_paths`, and `commands.py::_resolve_source_dirs` speaks a **byte-identical** sentence, so the file's own preamble was wrong | **carried as a note, and the preamble corrected.** They are still two properties — two sites, two inputs, and two reasons today (`workspace_unusable` against `invalid_arguments`) — and the command line's site is separately watched. **A witness that names a site in its name and is satisfied by another site is a witness of a sentence, not of a site** | — |
| **F57** | the witnesses say *which* items are list items, and not *how* a form marks one | **carried as a note, and F47's sentence corrected to say so.** The Markdown's `- ` and the DOCX's "List Bullet" are free — the product says the shape is the renderer's business — while the PDF's bullet glyph is watched only incidentally | — |
| **F58** | the list-item witnesses read **one fixture**, and that bounds what they can see — a mutation on a second disclosure is a no-op on that fixture | **carried as a note.** A witness is a witness of the document it reads; the bound is knowable, and a reader of this record should know it rather than assume the fixture away | — |

| **F59** | **the enumeration's third check is not a check** — it looked for the refusal's phrase among the witness's string constants, which is *"mentions", not "compares"*; a witness that keeps the phrase and stops comparing it survived the whole tree | a shared module, `tests/refusal_witnesses.py`, reads a witness's **compared** words — the sentences the test puts beside the product's output **inside an assertion**, an operand of a comparison or an argument of a call. A string merely held in a constant is not compared. **Both enumerations use it, so they cannot drift apart — and that is now a test rather than a hope:** `tests/test_refusal_witnesses.py::test_both_enumerations_read_the_shared_rule_and_not_a_copy_of_it` reads both files and fails if either stops importing the shared rule. **And the rule has a witness of its own**, because a rule that reads the witnesses is a mechanism, and a mechanism nobody watches can be neutered — which it was, twice, with the whole suite green. The mutation `_ = expected` is now caught by both, each naming the witness and the site | `tests/test_cli_workspace_refusals.py::test_every_refusal_site_in_the_cli_is_watched` and `tests/test_cli_refusal_enumeration.py::test_every_refusal_the_cli_raises_has_a_witness_of_its_own` |
| **F60** | **the enumeration's boundary was a gap of nine** — the CLI raises 35 refusal sites (18 `WorkspaceSetupError`, 17 command-level `_refuse(...)`), and the enumeration's docstring said the second kind "are watched by the command's own tests"; **nine of the seventeen appeared in no test file at all**, and two more were watched only by their exit code and a reason that **nine refusals share** | the derived enumeration parses the whole CLI package and covers the `_refuse` refusals as well — **37 refusals, 34 watchable, 34 matched, none unpaired**, and a refusal is bound to a witness **by the value that refusal names** rather than by a phrase a group owns. **Every watchable `_refuse` site is caught by the witness the enumeration names**, and the four pairings the value cannot decide are **written down and checked** — so a record that goes stale, or that leaves out a witness the derivation offers, is caught by name. The two that were watched only by their reason now quote their **own sentence**, and the `serve` witnesses **hold a port of their own**, so a neighbouring refusal cannot answer in their place — **the one whose witness passed only because port 8000 was busy on this machine now fails for the property — in 4.59 s by the pytest summary, 5.8 s of wall clock, and it does not hang** | the fifteen `_refuse` witnesses, plus `_a_taken_port` in `tests/test_cli.py` |
| **F61** | **`doctor` still called a workspace fine that no command can use** — a source root outside the workspace drew no warning at all, and a source root that is a file was reported as *missing* while the refusal said *not a directory* | the field became **`unusable_source_roots`**: one entry per root, **with the way it is unusable**, computed by the same function the refusals use — *missing*, *not a directory*, *outside the workspace*, or *unusable name*. The prose names the root and the way: *"(initialised, but a source root cannot be used), … unusable: '../outside' (outside the workspace)"*. **And the count the gate turns on moved 18 → 19, because the spelling refusal is a new site** — it was written down rather than adjusted quietly | `test_doctor_names_a_source_root_that_is_a_file_as_not_a_directory`, `…_outside_the_workspace`, `…_whose_name_cannot_be_spoken`, and the rewritten `test_doctor_does_not_call_a_workspace_with_a_missing_source_root_fine` |
| **F62** | **the source root's name was checked by the filesystem before the spelling guard** — a name the product cannot speak reached `stat` and came back a `ValueError`, with a traceback | the order is now **spelling guard → resolve → inside-the-workspace → `exists()` → `is_dir()`**, in one shared function, asked through a new public `labcairn.security.paths.check_spelling`. **The module's route and the command's `--source-dir` route ask the same question.** Before: `source_dirs=["materials\0"]` → `ValueError: stat: embedded null character in path`, exit 1 and a traceback. After: exit 3, *"the source directory 'materials\x00' is not a name this build can use: nul_byte"*. **The missing-root case is unchanged: exit 3, no traceback** | `test_a_configured_source_directory_that_is_missing_is_refused` and the spelling witnesses beside it |
| **F63** | **the rule that does the watching was not itself watched** — the shared module `tests/refusal_witnesses.py`, which reads a witness's **compared** words, had no witness of its own: neutered to *"mentions"* it left **the whole suite green — 3276 passed, 3 skipped**, and neutered together with a witness that stops comparing it, green again | **one new file — `tests/test_refusal_witnesses.py`, nine tests — and `tests/refusal_witnesses.py` is byte-for-byte unchanged** (`sha256 a1c16386f9ceb4b4ffc5dc4aed1afaf66afb2c1860d0299378c28d70179ff7e1`): **the rule is not changed, it is watched.** The neutering is now **CAUGHT — 3 failed, 6 passed, 0.17 s** — *`test_a_phrase_the_witness_only_holds_is_not_read`*, *`test_a_witness_that_compares_and_one_that_only_holds_are_read_differently`* and *`test_a_witness_that_stops_comparing_is_not_read_as_comparing`* go red, and they name the property: *"A rule that reads a mention would read them the same way"*. **And a witness that stops comparing is caught twice over** — by the two enumerations while the rule is intact, and by the rule's own file once it is neutered — so the mutation that used to green the whole suite has nowhere to go, and the two together are **CAUGHT — 3 failed, 40 passed, 139.48 s** | `tests/test_refusal_witnesses.py` — the three above, and `test_both_enumerations_read_the_shared_rule_and_not_a_copy_of_it`, which fails if either enumeration stops importing the shared rule |
| **F64** | **one command-level refusal was watched by nothing** — `src/labcairn/cli/commands.py:1590`, the `except BindRefusedError` handler whose whole message was `str(error)`; **with the refusal removed the whole suite was green**. And the one-line fix the review suggested — `BindRefusedError` into `UNREACHABLE_FAILURES` — **SURVIVED — 32 passed, 211.72 s**, because that list keeps its books **by the failure's name** and the name has two sites: **a name is not a site** | **the refusal now carries the command's own sentence** — *"the service's own guard refused the bind: {error}"* — and **the witness injects the layer's refusal where the layer raises it**: the command's `run_service` is replaced with one that asks the layer to serve `0.0.0.0`, an address the command never checked, so **the layer's own guard refuses it**. **The reachability was measured first**: the guard is asked the same question about the same address three times (`commands.py:1452`, `api/app.py:270`, `api/app.py:325`), a routable address is refused at the first question and the service is never started, so **the branch cannot be reached through the CLI's own path** — and the fix is therefore at the site, not at the name. **CAUGHT — 1 failed, 66 passed, 443.04 s** — *"the command exited 1 rather than refusing; the exception was BindRefusedError(…)"*. **And the coverage claim changed with it: the enumeration now covers fifteen of the eighteen `_refuse` sites, and this one is watched** | `tests/test_cli_serve_bind_refusal.py::test_the_command_refuses_a_bind_the_service_would_not_make` — and the enumeration holds the pairing too, so deleting the file turns `test_every_refusal_the_cli_raises_has_a_witness_of_its_own` red |
| **F65** | **"a witness of its own" was false for five of the thirty-three, and the pairing was unwatched** — two groups hold more than one refusal, so the phrase a group owns cannot tell its members apart, and the witnesses' **values** — the very thing that distinguishes them — were thrown away; deleting the command's own witness left **the whole suite green — 3275 passed, 3 skipped** | **a witness is bound to a refusal by the value that refusal names** — the configuration's path, the policy's path, the providers file's path — and **where the value cannot decide, the pairing is written down in `WATCHED_BY` and checked**: every name must exist in the suite, must compare a phrase its refusal says, and every witness the derivation offers must be written down. **The product's wording did not change by one word** (`src/` untouched). **The enumeration's own numbers, read out of the tree: 37 refusals, 34 watchable, 34 paired, 0 unpaired, 33 groups, 102 witnesses read** — and the thirty-four fall **27 by exactly one candidate**, **3 by the value** (`workspace.py:236`, `workspace.py:315`, `commands.py:665`), **4 by the record** (`commands.py:923`, `workspace.py:343`, `workspace.py:535`, `workspace.py:547`). **The fix's own report said 26 and 33; those were right on the branch they were measured on and are wrong after the composition, so they were recomputed.** **And the record's own sentences are watched**, because a hand-written table is wrong the moment the code moves: **RECORD-1 — 3 failed, 31 passed, 180.20 s**; **RECORD-2 — 2 failed, 32 passed, 194.08 s**. The deletions that used to green the tree are now **CAUGHT** — the command's own witness: **2 failed, 41 passed, 162.37 s** narrow, and **3 failed, 3287 passed, 3 skipped, 1972.48 s** at the whole-suite width; the module's source-dir witness: **1 failed, 99 passed, 843.77 s**; the doctor's source-root witness: **2 failed, 97 passed, 703.46 s** | `tests/test_cli_refusal_enumeration.py::test_the_witnesses_that_are_recorded_are_in_the_suite` and `…::test_the_two_enumerations_watch_the_same_refusals_the_same_way`, beside `…::test_every_refusal_the_cli_raises_has_a_witness_of_its_own` and the ledger's `test_every_refusal_site_in_the_cli_is_watched` |
| **F66** | **the crash fix's two `PathRefusedError` catches were load-bearing and unwatched** — with the catch a refusal, without it a crash, and **the whole suite was green without them**; and the catches could not be reached through the CLI's own path, so **there was nothing for a witness to drive** | **the layer's own root binder is substituted with one that raises the layer's own exception and the layer's own reason code** (`PathRejection.CANONICALISATION_FAILED`) — **the product's code path is not bypassed, only the layer's leaf function is replaced**, and everything above it runs unmodified — and **the two catches are told apart by the product's own words**: *"the workspace at <root> could not be bound: …"* against *"the workspace could not be bound: …"*, a phrase **written inside the `except` clause**, so the test cannot have gone around it. **CRASH-10 — CAUGHT: 1 failed, 102 passed, 617.83 s** — *"the layer's refusal escaped the command as a crash: PathRefusedError(…)"*. **And the two witnesses are deliberately narrow**: a witness that held both paths could not say which catch was broken, so one broken catch leaves the other witness green by construction | `tests/test_cli_path_refused_catch.py::test_a_refusal_the_workspace_binds_is_answered_with_the_root_named` (the catch in `bind_workspace`) and `…::test_a_refusal_that_skips_the_workspace_is_answered_by_the_cli` (the catch in the CLI's refusal handler) — the F54 row's witness column names both |

**And the reviewer's own ledger is part of the record, because the result is
only worth what the method is.** In these two rounds: a **long `--basetemp`
broke a test that had nothing to do with the property** (the CLI renders its
refusals through Rich, which wraps at `COLUMNS=200`, and the rendered path is
in the message — so a long basetemp pushes the wrap inside the phrase a test
asserts on: **measured on a clean tree, same clone, nothing mutated, long
basetemp → the test fails, short basetemp → it passes**), which produced
**five false "catches"** in one sweep; **two whole-suite runs at once raced on
the shared matplotlib configuration directory** (that file passes 38/38 run
alone); **the project's own `ruff` caught a mutation, not the property**
(`E501 Line too long`, because the README's test really runs `uv run ruff
check .`); **the project's own `mypy` caught one too** (`warn_unreachable` on
an `if False:`); **a stopped sweep lane left its mutation in the clone** and
the next case failed with a catch that was not its own; and a reviewer's own
anchor checker **reintroduced a `unicode_escape` bug** that mangled an
em-dash in two anchors.

**Every one of those read as "the mutation was caught" until the run was
repeated.** That is the round's most portable lesson, and it is the same one
in three different clothes: **a red test is not a catch unless the red test
is about the property.**

### What this gate did with the fourth round's verdict

**Nine findings came out of the two re-verifications, and all nine are fixed.
Six of them are witnesses, two are a product correction and a guard, and one
is a rule about which items a form draws.**

| | the finding | the fix |
|---|---|---|
| **F44** | this gate's own composition deleted four witnesses for F31 | the four are back, adapted to the head's own helpers — and the ledger that catches this (the set of test functions compared between two commits) is now part of how this gate merges |
| **F45** | the demonstration compares the CLI with itself and reports "0 differing" | a witness that plants the disagreement **from outside**, wrapping `routes.read_task_state`; the demonstration's source is never edited, it grows no hook, and its check count stays 60 |
| **F46** | a test's pass or fail depended on the machine's locale encoding | the encoding is stated on **both** sides of every subprocess that decodes — pinning only the parent's decoding turns the failure around rather than fixing it |
| **F47** | what a form says about itself, outside its own text | seven witnesses, each reading its carrier **with the reader its own form is read by** and comparing it with **the document's own value** |
| **F48** | the repository's own root guard crashed instead of answering on a non-ASCII path | it states the encoding it decodes with, and `errors="replace"` is the promise that it always answers |
| **F49** | the same guard, the other end of the pipe | the encoding is left to the machine — a console that can show the path should show it — and only the *failure* is removed |
| **F50** | the four forms do not draw a finding alike | **the independent review ruled it is not a defect** and the record's wording was corrected: the product does not contradict itself, the *reading of the PDF's test* as a document-level rule does. The residual is carried: the HTML's shape is **unwatched as well as unlike** |
| **F51** | the list-item witnesses compared a count, and a count cannot see a substitution | they now compare the **identity** of the list items, as a multiset, read out of each form with that form's own reader — and the count assertion is kept |
| **F52** | the CLI's ten own refusals were unwatched | eleven named witnesses, each asserting **a verbatim sentence of the product's own message**, with the neighbours told apart by the sentence they use *and* by the file they name |

**And the implementers' own claims were checked rather than accepted.** Each
witness was proved to bite by breaking the property in the **implementation**
and watching a **named** test fail with the property's own words; each
mutation was checked to be **type-clean and lint-clean**, because a mutation
that trips the project's own `mypy` or `ruff` produces a red that is not a
catch. **And the isolation was checked**: each mutation, applied alone,
failed **exactly its own** witness and left the others green.

**Two of the fixes are the product's own words, and that is the rule the
whole gate turns on:** a witness is the product saying it. The guard's
refusals are quoted sentences, not "something was raised"; the form's
carriers are compared with the model's own values, not with literals
copied out of a renderer.

## The verdict

**The gate is closed. The verdict is PASS WITH NOTES.**

**The exit test is met.** The three surfaces produce the same report bytes,
compared field by field — **255 fields, none differing** — and by hash, for
each of the four forms, against the file the report operation wrote and the
bytes the service serves. That was demonstrated at `15cd63d` and the
demonstration has been re-run against the tree this gate closes on.

**And the tree this gate closes on is green.** The whole suite, on the
closing tree, in **3292 passed and 3 skipped** with **no failure** — 3295
collected, of which **fourteen are the witnesses the round-five fixes
added** and none was removed. **Every whole-suite figure elsewhere in this
record is anchored to the tree it was measured on**, and this is the one
anchored to the tree that closes the gate.

**The condition that was outstanding is now discharged.** The board's rule is
that a row is marked done only when an **independent review at a named
commit** says so. Two reviewers did that work, one per scope, and **neither
wrote a single fix into this repository** — which is what made the review
independent and what let the same reviewer re-run its own mutations against
the fixed code.

**Scope A — the report path.** **Five FAILs, then a pass.** The first was
two open defects and five unwatched refusals; the second was one unwatched
refusal the first fix had introduced; the third was fourteen surviving
mutations out of a hundred and sixteen; the fourth was eight, in a class
the fix's mechanism could not reach; and the fifth, at `86e0226`, was four —
which the fix under review had closed down to, and which **found a real defect
of its own**, the list-item witness comparing a count rather than a marker.
**Every one of the five failed on a property table that was entirely clean** —
and that is the finding the whole gate turned on: *a property table can be
clean and the review still fail.* The report path's review now passes, and
its verdict is **PASS WITH NOTES**.

**Scope B — the three surfaces.** **Five BLOCKED and one FAIL, then a pass.**
The first, at `6035dbf`, was two blockers and six notes, one of the blockers
sitting directly under the gate's own exit test; the second, at `5cd6d0`, was
two surviving mutations, one of them **the witnesses for a blocker having been
deleted by this gate's own composition**; the third and fourth, at `86e0226`
and `15cd63d`, were BLOCKED again; the fifth, at `eed91fa`, was a **FAIL**; and
the sixth, at `47259e0`, was BLOCKED again, on four findings — **the shared
rule that reads the witnesses was itself unwatched**, **one command-level
refusal was watched by nothing**, **the pairing between a refusal and its
witness was unwatched**, and **the crash fix's two catches were load-bearing
and unwatched**. All four are fixed, and the re-verification that fixes them
**is this round**.

**And this round added a question the last one did not ask.** F65's fix ends
in a **hand-written record** — the four pairings the values cannot decide —
and a hand-written record is what F53 was raised about: *a table counted by
hand is wrong the moment the code moves.* So the record's **own** guard was
measured too, and a record that goes stale, or that leaves out a witness the
derivation offers, is caught by name. **A record nobody checks is a table; a
record that is checked is a witness.**

**What is carried forward is what the review confirmed as a limit rather
than a defect**, and it is listed in **"Open items carried beyond G4"**
below: the layer's two part-refusals, 725 and 733, which are **unreachable**
and so cannot be watched today, and which become the only thing standing
between a report and a part the ledger never recorded the moment `_the_parts`
or the builder's copy-from-receipt rule changes; the browser, which no test
drives; the API's event stream, which the workbench does not consume; and the
demonstration's own claim, which the demonstration writes rather than the
product. **That section also carries the four items the gate before this one
handed on and this gate did not deal with**, so that the next reader does not
have to assemble them from every section of this record.

## What this review did not cover

- **The report's own interpretation.** The report carries the **figure's**
  reading, because that is the reading the ledger holds; a reading about the
  report as a whole has no source in Phase 1, and the model's machinery for
  one waits for a phase that has one.
- **What the report looks like to a reader.** The renderers' output was read
  back and parsed, not read as a person would read it.
- **The browser.** No test drives the workbench in a browser. The web
  package's tests drive a **fake at the `fetch` boundary**, so the
  component, the client, the paths and the session scheme are exercised
  exactly as they are in a browser — but **the real service is never driven
  by the browser**, and the clause "CLI and UI show identical Task state" is
  therefore discharged **through the API**: the CLI and the service are
  compared field by field against the real store, and the UI shows what the
  service says. That is a stated limit of the evidence, not a defect.
- **The DOCX's and the PDF's byte-reproducibility.** Neither is claimed;
  §1.4.3 says so and the report says so on its own face.
- **Two limits the surfaces record themselves:** the API's event stream is
  **not consumed by the workbench** (`web/src/api/paths.ts` says so in
  prose), and the workbench **cannot switch the selected project**, because
  the API has no such operation.
- **The two work orders' own acceptance reviews were not independent**, and
  this document does not pretend otherwise. LC-P1-11's review was written by
  the party that specified the work, dispatched it, wrote its fixes and
  reviewed them. **The gate's own review is the independent one**, and its
  independence is stated above: two reviewers who wrote **no fix** into this
  repository.
- **What a reader of a report would conclude.** Not this review's business;
  the work order says so itself.

---

## Open items carried beyond G4

**What this gate confirmed as a limit rather than a defect, and what the
gate before it handed on.** G3 closed with a section by this name, and a
gate that closes without one leaves the next reader to assemble the list
from every section of the record. **This is that list.**

### Carried from G3, and not dealt with here

- **The fabricated-DOI half of LC-P1-09's clause** — still no
  implementation, and the gap is structural rather than a missing line. **This
  gate did not check it.**
- **The manifest names no version for the renderer** — and the recipe check
  compares the file's bytes rather than the parsed models. G3's review
  looked at this and found it a **stated limit rather than a defect**: the
  manifest carries no renderer version and none of the renderer's build
  parameters, and `RenderEnvironment` holds only matplotlib's version, salt,
  fonts and platform. **Both facts are written down, and the figure's own
  receipt carries its bytes' hash.** This gate did not re-examine it.
- **The exit demonstrations of G1 and G2 are run by nothing** — the claim
  holds. **No test and no CI job runs `examples/g1_exit_demo.py` or
  `examples/g2_exit_demo.py`**, and both `tests/test_analysis_demo.py` and
  `tests/test_smoke_path.py` say so on their own face. **G4's own exit
  demonstration is run by `tests/test_smoke_path.py`**, which is what makes
  this gate's exit test different from those two — and it is the reason the
  gap below is named rather than merely inherited.
- **A two-column page whose rival column holds less than 30% of the page's
  area** — G3's review found it and left it. **This gate did not re-check
  it.**
- **An aggregate's numbers are not re-checked by C1, C2 or C3** — they are
  traceable to the file and to the manifest, and not re-derived at gate time.
  **This gate did not re-derive them either.**
- **The repository still has no LICENSE file**, and matplotlib's bundled fonts
  oblige one. **That obligation is named in the plan as G5's**, so it is
  carried **to** the next gate rather than beyond this one — and the
  repository says so on its own face in `LICENSE.PENDING.md`.

**And one of G3's seven this gate touched, though it did not close it**:
**source provenance preserved through report generation** — the report's model
carries a provenance field (`src/labcairn/reports/model.py`), but that field
predates this gate (it came with the document model, `a9e7cf6`), and **what
G3 named is the *link* — the reason the ledger's records reach a report at
all**, which this gate did not build and this review did not check. **It is
carried, not closed.**

### Found by this gate's own review

- **The layer's two part-refusals, 725 and 733** — **unwatched and
  unreachable**, measured twice by two methods, and **the gate can close on a
  tree carrying them**: under the gate's own first rule they are not
  survivors, because removing either changes **no observable behaviour**.
  **They are not nothing, and the record says what they are for: the moment
  `_the_parts` or the builder's copy-from-receipt rule changes, these two
  guards become the only thing standing between a report and a part the
  ledger never recorded.**
- **The browser** — no test drives the workbench in a browser. The web
  package's four cases drive a **fake at the `fetch` boundary**, so the
  component, the client, the paths and the session scheme are exercised
  exactly as they are in a browser — but **the real service is never driven
  by the browser**, and the clause *"CLI and UI show identical Task state"*
  is therefore discharged **through the API**. That is a stated limit of the
  evidence, not a defect.
- **The API's event stream is not consumed by the workbench**, and **the
  workbench cannot switch the selected project**, because the API has no such
  operation. Both say so in prose where a reader will meet them.
- **The demonstration's own claim** — the claim in the report is **made by
  the demonstration, not by the product**: no layer operation writes an
  evidence record or an anchor, so the demonstration writes the claim's own
  address and the record that rests on it itself, and says so in its own
  output.
- **The report's own interpretation** — the report carries the **figure's**
  reading, because that is the reading the ledger holds; a reading about the
  report as a whole has no source in Phase 1, and the model's machinery for
  one waits for a phase that has one.
- **The DOCX's and the PDF's byte-reproducibility** — neither is claimed; the
  plan says so and the report says so on its own face.

### What the last review did not re-measure

**The last review re-ran the mutations that defeated the round before it, and
added two that attack the new mechanism itself. The other measurements were
not re-run** — and the review says so rather than letting the number stand
for a whole. Those are the last round's figures, anchored to the tree they
were measured on: **the fifty-eight-mutation matrix and the refusal sweep at
`47259e0`**, and **the report path's own hundred and sixteen mutations at
`25bad72`**. **What was not re-measured is the catch rate under repetition**
— every mutation ran once, at one seed — and **the seventy-five sweep
branches of the application layer**, the carry-level witnesses of F47 and
F51, and the API's five refusals, all inherited and all re-measured by nobody
since.
