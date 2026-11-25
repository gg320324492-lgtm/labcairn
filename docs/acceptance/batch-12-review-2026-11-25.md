# The twelfth batch, reviewed — 2026-11-25

**Base:** `14b6189` (the tree before the batch's four windows) → `d92ebed`.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
items R1–R7.
**Status:** `REVIEWED, with three slices not finished — see "What this review did not cover"`.

---

## What was reviewed

The batch's four windows, merged into `main` and then reviewed on the merged
tree — each window's own tree was intact, which is why three of the tree's
own gates had to be repaired afterwards:

| Slice | What it changed | Review |
|---|---|---|
| A | the citation path's liveness check (`cite_rule`) | reviewed by a dispatched window; the findings re-checked by hand and repaired |
| B | the refusal enumeration's candidate granularity | the mechanism's own witness was added and mutation-checked; a full R1–R7 pass was **not** completed |
| C | Phase 4's gates in the release notes and the review dossier | read against the tree; the numbers carry their anchors |
| D | the denied write's trace | read; the core implementation was checked by hand; a full R1–R7 pass was **not** completed |
| — | the pilot's two tools and revision 0032 | checked by hand against R1, R2, R4 and R6; a full R1–R7 pass was **not** completed |

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

## What this review did not cover

**No slice got a second, independent pair of eyes except slice A.** The
dispatched reviewers for slices B, D and the pilot's tools were stopped
before they reported, so each of those three was reviewed **in this
session, by hand and by measurement**, and that is a weaker thing than a
dispatched reviewer's independent read. What was done for each:

- **Slice B (the enumeration).** Every item of R1–R7 was answered here.
  The pairing was read as a whole: a candidate pool, then `WATCHED_BY` if
  the record names one, else the unique candidate, else the value-narrowed
  candidate, and **no name at all** otherwise — which is what makes the
  gate red. `WATCHED_BY`'s three checks (the witness exists, it compares a
  phrase the refusal says, and every witness the derivation offers is
  written down) cover the two failure modes the gate exists for: a refusal
  nobody watches, and a witness that has gone. The mechanism's determinism
  was measured across three hash seeds (0, 1, 12345) with the same result.
  The mechanism's own witness was added and mutation-checked (finding 10).
  **Not done:** an independent reader with no stake in the design.
- **Slice D (the denied write's trace).** R1, R2 and R4 were answered
  mechanically over the diff; R3 by the eight mutation-checked witnesses
  that cover both directions (a denial leaves a trace, a refusal for any
  other reason leaves nothing); R5 by reading the module's own docstring
  against its code — *"it leaves an operation in state `denied` carrying
  the reason the permission layer produced … Every other refusal still
  leaves nothing at all"* — which is what the code does; R6 by finding no
  unanchored number in the diff; R7 by the fact that the witnesses drive
  the product's own stage path rather than writing rows by hand.
  **Not done:** an independent reader, and no second reading of the
  transaction's rollback behaviour under a failure.
- **The pilot's tools and revision 0032.** R1, R2 and R4 were answered
  mechanically over the diff (no build artifact, no platform fact, no CJK
  character); R5 by checking the acceptance record's claims against the
  tool's own output — 14 pass, 7 undecided, 0 fail, and the seven are the
  ones whose evidence is a person's reading; R6 by the repair in finding
  12 and by the three new test files carrying an explicitly unmeasured
  shard cost; R7 by the fact that the witnesses assert the tool's and the
  migration's behaviour, while their inputs (a synthetic document, a
  store built by the chain itself) are inputs rather than the thing under
  test. **Not done:** an independent reader, and no third-party reading of
  the constraint bodies against the models' rendering beyond the parity
  witness the repository already carries.

**The whole-suite run on the merged tree was not completed** when this
record was written; the run started afterwards, against `d92ebed` and the
commits that followed it. Its result is not in this record.

**The shard costs for the three new test files are not measured.** They
carry `0.0` and wait for a runner.
