# The twelfth batch, reviewed — 2026-11-25

**Base:** `14b6189` (the tree before the batch's four windows) → `d92ebed`.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
items R1–R7.
**Status:** `REVIEWED TWICE — the first pass found fourteen findings, an independent reader found more; both tables are here`.

---

## What was reviewed

The batch's four windows, merged into `main` and then reviewed on the merged
tree — each window's own tree was intact, which is why three of the tree's
own gates had to be repaired afterwards:

| Slice | What it changed | Review |
|---|---|---|
| A | the citation path's liveness check (`cite_rule`) | reviewed by a dispatched window; the findings re-checked by hand and repaired |
| B | the refusal enumeration's candidate granularity | reviewed twice: the first pass added the mechanism's own witness, and an independent reader found the hole below |
| C | Phase 4's gates in the release notes and the review dossier | read against the tree; the numbers carry their anchors |
| D | the denied write's trace | reviewed twice: the first pass read the implementation by hand, and an independent reader measured the transactions |
| — | the pilot's two tools and revision 0032 | reviewed twice: the first pass checked the boundary and the anchors by hand, and an independent reader compared the migration's constraint bodies against the models' |

## R1–R7

**R1 — a witness must not depend on a build artifact the runner lacks. Pass.**
No file this batch touched in `src/` or `tests/` names `shell/build/`,
`dist*/`, the frozen backend or `site-packages` (checked mechanically over
the diff's file list). Every new witness builds what it needs: the pilot's
tools write synthetic documents into their own temp directory; revision
0032's witness builds a store in a temp directory; the role-run fixtures
build their own chain.

**R2 — no assertion hard-codes one platform's facts. Pass.** The diff's
added `src/` lines contain no drive letter, no backslash path and no
`.exe`; the pilot's tools use `pathlib`, the enumeration's rule reads the
console-script names out of `pyproject.toml` rather than naming one, and
0032 is SQLite DDL.

**R3 — a guard needs a witness at the call site and one on the effect.
Pass, with the caveat named.** There is no injection-shaped guard in this
batch. The connected claim the batch makes — *the citation path refuses a
rule the memory does not serve* — is witnessed on both sides: statically
(`cite_rule` asks `serves_rule`, and moving the call turns a witness red)
and by effect (a rule whose source is withdrawn, unreachable or unjudged
is refused, and a rule the memory serves is cited).

**R4 — external material is paraphrased in English with its provenance.
Pass.** The diff's added lines contain **no** CJK character (checked
mechanically: 0 of 159 non-ASCII added lines carry one, and every one of
those is a typographic mark). The two pilot scripts' regular expressions
name the Chinese words a material path can contain, written as escapes so
the files carry no characters of their own. The acceptance record carries
digests, counts and verdicts, and no sentence of the manuscript; the one
external quotation it holds is the acceptance record's own line, with its
file and line.

**R5 — a documented rule matches what the code enforces, in both
directions. Pass after repair.** Three claims in the batch's own words did
not match the code, and each is now true rather than merely stated: the
citation path's docstring said a source the reader may not reach is left
alone "because the chain read drops it" — the chain read applies no
permission filter at all; the docstring said a caller "has no parameter to
thin" a citation's cases with, and a caller could in fact build a
citation the memory never held; and the refusal vocabulary gave two
different conditions one member, so a caller could not tell them apart.
ADR-0002's two rows and ADR-0003's vocabulary and state machine were
corrected to say what the tree does.

**R6 — a value that can change is re-measured, not carried forward. Pass
after repair.** The acceptance record quoted the first copy's character
and paragraph counts without naming the copy they were taken on; it now
does. The batch's three new test files carry a shard cost of `0.0`, which
is not a measurement and says so. The release notes' snapshot carries its
date and the commit it was measured at.

**R7 — a witness that builds what it observes cannot see its absence.
Pass, with the finding that matters.** The revision 0032 witness starts
from the older shape by downgrading — the migration is the product's, so
what is asserted is the product's behaviour and not the test's. The
enumeration's granularity rule was witnessed against **real** test files
rather than against a synthetic tree, so a rule that read the file rather
than the test would have been caught. And the batch's own claim about the
role run was false in the way this item is about: the two role-run
fixtures built a rule the memory reports as invalidated, so the run was
citing a rule the memory does not serve, and no witness could have said
so.

## The findings, and what closed them

| # | Severity | Finding | Closed by |
|---|---|---|---|
| 1 | high | the citation path's check was narrower than ADR-0016 C10: it detected one way a rule dies, while the retrieval layer's answer covers three, and the role run puts a citation's statement into the excerpts that leave the machine | `0e4c4d0` — the retrieval layer now answers "does the memory serve this rule?" in one place (`serving_sources` / `serves_rule`), the citation path asks it, and the second, weaker definition is deleted |
| 2 | medium | the citation path's docstring said the chain read drops an unreachable source; the chain read applies no permission filter | `0e4c4d0` — the false sentence went with the deleted helper |
| 3 | medium | a card could cite a rule the memory never held: `RuleCitation` was a plain public dataclass | `0e4c4d0` — a citation carries a token only `cite_rule` can present, and the card refuses one without it |
| 4 | medium | "no such rule" and "its material was withdrawn" shared one refusal member | `0e4c4d0` — each has its own member, and both render |
| 5 | low-medium | the "card path" assertion put `cite_rule` inside the lambda, so `build_card` was never reached | `0e4c4d0` |
| 6 | low-medium | the role run's wiring had no witness | `0e4c4d0` — driven through the run, and the two fixtures' rule now judged |
| 7 | low | ADR-0016's C10 row still said "a witness for that path is owed" | `0e4c4d0` |
| 8 | low | "a source nobody judged is not withdrawn" was witnessed only as a side effect of a fixture's state | `0e4c4d0` |
| 9 | high | **revision 0001 was amended to carry the new event type, so only a store built afterwards would accept it** — measured: a store built with the pre-amendment first migration and then upgraded to head still refused `operation_denied`, because alembic does not run the first migration again | `64fcd66` — revision 0032 rebuilds the `events` table with the vocabulary the models already carry, with its own witness |
| 10 | high | **the enumeration's candidate rule had no witness of its own**: a mechanism that reads the tests could be neutered while the tree stayed green | `f1b72a6` — a witness that names a test whose file reaches the CLI and which does not, and that goes red when the rule reads the file |
| 11 | medium | the merge broke three of the tree's own gates — the evaluation harness's partition did not know the three new test files, three anchored pointers drifted, and the tree carried more Chinese than was measured | `752efa6` |
| 12 | low | the acceptance record quoted a reading without the digest it was taken on | `fadc4e4` |
| 14 | medium | **the checked-in TypeScript was not regenerated** when the event vocabulary grew, so the tree's own witness — *the checked-in TypeScript is what the Python models produce* — was red at fourteen per cent of the suite; the same shape as finding 11, from the same merge | `5fae156` |
| 13 | medium | **the two role-run fixtures confirmed a rule without ever judging the change the rule cites**, so the memory reported it as invalidated and the run was citing a rule the memory does not serve — the repair in finding 1 made 15 tests red, which is how this showed | `d92ebed` |

Each repair carries a witness, and each witness was mutation-checked: the
production line was broken and the witness that watches it was seen to go
red. The four mutations the review ran against the enumeration's rule, the
citation path's refusal, the citation's minting and the role run's wiring
are recorded in the commit messages that carry them.

## The second reader's findings

A reader with no stake in the design read the three slices that had none.
It worked on a copy of the tree, so the live checkout was never written to,
and it measured rather than inferred: baseline **57 refusals, 53 groups,
163 witnesses, 0 unwatched**, and the pairing's digest was compared across
five hash seeds.

| # | Severity | Finding | State |
|---|---|---|---|
| 15 | high | **the gate can be neutered.** `_pieces` (`tests/test_cli_refusal_enumeration.py:305`) resolves a string literal, an f-string or a call to a function of the same module — and **not a name**, while `_value_text` (`:298`) does follow bindings. Hoisting a refusal's message to a module constant takes it out of the watch set; **deleting its witness as well leaves the gate green** (measured: 10 passed), where the control — message inline, witness deleted — is red | to repair |
| 16 | medium | **a candidacy rule that is too wide.** One of the three ways `_witness_reaches_the_cli` (`:807`) recognises a test as reaching the CLI is *it says one of the CLI's refusal reasons*. Any new test that asserts a CLI refusal reason therefore becomes a candidate, and a refusal that interpolates no value cannot be narrowed to one — so the gate goes **red on a tree whose product did not change** | to repair |
| 17 | high | **the trace of a denial is three transactions, not one.** `_record_denial` (`src/labcairn/application/stages.py:205-241`) calls `ensure_run`, then `ensure_stage`, then `deny_operation`, each in its own unit of work. Measured with the event write failing: `operations` is empty, but `runs` holds a `running` row and `stages` an `entered` one — **a trace that could be mistaken for a partial success**, which the records module's own comment says a refusal must not leave, while the record says "one transaction" | to repair |
| 18 | low | the operation row and the `operation_denied` event **are** one transaction — measured by making the event write raise: no operation row survives — but **no witness shows it**, and there is no fault-injection point to write one against | witness owed |
| 19 | low | "a refusal for another reason leaves nothing at all" is witnessed for the ASK case only; the recovery-uncertain and approval-consumed refusals also leave nothing, and unwitnessed | witness owed |
| 20 | medium | **revision 0032's carries are unwitnessed.** Its witness inserts its row *after* the upgrade, so nothing checks that rows written *before* it survive a rebuild that copies all fourteen columns; and the plain indexes (`ix_events_run_id`, `ix_events_task_id_type`) are compared nowhere | witness owed |
| 21 | low | the records say *a `DENY` from the policy layer is recorded*, and that holds **on one path only**: `consent.decide` — the function that returns a verdict a caller can record — has one caller (the stage layer), while the other thirty consent calls go through `consent.evaluate`, which raises and writes nothing | **the owner decided**: a denial is recorded on the path that writes, so the ADR's wording is what changes |
| 22 | low | two paths plan an operation outside the stage layer: `approvals.request_approval` (`src/labcairn/application/approvals.py:189-200`) and the recovery executor (`src/labcairn/recovery/executor.py:157-192`, which **never consults the policy at all**) | recorded |

**What the second reader confirmed, by measurement.** The four constraint
bodies revision 0032 writes are equal, after whitespace normalisation, to
the ones `src/labcairn/db/models.py` renders from the frozen `EventType`
enum; the downgrade restores the pre-amendment shape exactly (columns,
nullability, defaults, unique constraints, CHECK bodies, indexes and
foreign keys: 5 of 5); the boundary holds — every literal in the pilot's
tools and its two records is a digest, a count, an id, a timestamp or a
path, and the redaction refuses to run on a copy carrying an author its map
does not name; and the enumeration's pairing is identical across five hash
seeds, with `WATCHED_BY` load-bearing (removing an entry turns three
tests red).

**Two decisions the owner made.** A policy denial is recorded **on the path
that writes** — so ADR-0002's wording is what changes, not the code. And
the measurement record's mention of the advisor's folder stays: it is a
descriptive label, not material.

## What the checklist does not ask, and should

The second reader's findings are not only about this batch. Six things fall
between the lines of R1–R7:

1. **A gate whose scope is derived by a parser has a syntax-shaped blind
   spot.** R1–R7 ask what a witness *asserts*; none asks what a gate
   *decides to look at*. Finding 15 is exactly that. The generalisable
   question: for every rule of the shape "every X is watched", what change
   to X's syntax drops it out of the watch set, and is that change one the
   project would accept?
2. **R3 covers a skipped arm; nothing covers an admission rule that is too
   wide.** Finding 16. The question: for every rule that admits a
   candidate by a proxy — a string, a name, a path — what unrelated code
   can satisfy the proxy and be admitted by mistake?
3. **R6 covers numbers; it does not cover digests as claims, and it does
   not ask that a measurement carry the command that produced it.** The
   pilot's boundary rests on digests being unquotable, and the measurement
   record's counts of the advisor's material are exactly the kind R6 would
   ask to be anchored to a command.
4. **Nothing asks whether a schema rebuild preserves the data.** Revision
   0032 is a destructive operation on a user's store, and its witness
   exercises it with zero pre-existing rows.
5. **Nothing asks whether the transaction boundary a record claims matches
   the transactions the code opens.** Finding 17 is exactly that.
6. **Nothing makes an enum's fan-out enumerable.** The vocabulary grew and
   two derived artefacts had to follow — the migration's four constraint
   bodies, and the web client's union type. Each has a witness; nothing
   enumerates what else derives from the enum.

## What this review did not cover

**The three slices that had no independent reader now have one**, and the
second reader's findings are in the table above. What it did not do is
finish the job it was given: it reported eight findings and did not repair
them, because repairing them changes the tree the review is about.

**The whole-suite run on the merged tree was not completed** when this
record was written; a run started against `548e849` afterwards, and its
result is not in this record either.

**The shard costs for the three new test files are not measured.** They
carry `0.0` and wait for a runner.

**The pilot's own trial has not run.** Nothing in this record says the
product works in the hands of a participant; it says the tree holds the
properties the witnesses claim, on this machine, at these commits.
