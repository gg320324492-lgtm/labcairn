# Batch 16 review — what a removal releases, and a record that reads as sound over a row that is gone

**Date:** 2026-11-27
**Range reviewed:** `28cf0f1..5ec65b5` on `main` — two windows' work
merged, two registrations, the threat model's moved write range, and the
costs re-measured from the runner.
**Checklist:** [`docs/review-checklist-2026-11-14.md`](../review-checklist-2026-11-14.md),
R1–R7.

**What was reviewed.**

| Piece | Commit | What it is |
|---|---|---|
| the removal's scope | `57b79da` | [`tests/test_source_removal_scope.py`](../../tests/test_source_removal_scope.py) — what a removal releases when two tasks hold the material |
| the dangling source id | `1dc0197` | [`LC-P4-PILOT-dangling-source-ids-2026-11-26.md`](LC-P4-PILOT-dangling-source-ids-2026-11-26.md) and its witness — the id read back through the product's faces |
| the registrations | `68eef58` | both new files filed in the manifest and in a shard |
| the threat model | `28cf0f1` | §1.2's write range, moved with `init`'s three `mkdir` calls |
| the costs | `28cf0f1` | re-measured from the runner; the documents that print them carried with the table |

## R1. No witness depends on a build artifact the runner does not have

**Pass.** Both new witness files read only the tree: no path outside the
checkout, no real material, no build output. The scope witness builds
its own workspace from the product's own APIs; the dangling-id witness
builds the shape (a source holding addresses, removed) and then reads it
back through the product's faces — the CLI's console script and the local
API — **against a scratch workspace under `E:/labcairn-local/tmp/`**, and
the record says so.

**One thing the dangling-id record did that was worth doing.** It ran
through **this tree's own console script** (`uv run labcairn`), so the
code that ran is the code in the tree the record was written on. The
shared virtualenv's editable install points at the main checkout, which
is the defect `CLAUDE.md` records; **a reading taken through it would have
been a reading of somebody else's tree**, and the record names the tree
it was taken on.

## R2. No witness hard-codes one platform's facts

**Pass.** Neither new file holds an `os.name`, a `sys.platform`, a drive
letter or a backslash path. The record names the machine and the tree.

## R3. The guard of a guard needs its own witness, and a skipped arm proves nothing

**Pass.** Neither new file contains a `skip`, a `skipif` or an `xfail`:
**no arm of them can pass by not running.** Five witnesses between them
(three about the removal's scope, two about the dangling id), each
mutation-checked.

## R4. External material is paraphrased in English with provenance, never quoted in the original

**Pass.** The new record carries no Han character and no long quotation;
it holds ids, digests, counts and codes, and each says which command
produced it. The witness that watches the pilot's records for Chinese
covers this file by its glob, and it is green.

## R5. A documented rule and its implementation say the same thing, and both sides are witnessed

**Pass.** The scope witness holds the behaviour the application layer
states on purpose — the release goes to every task that held the
material — and says in its own docstring that the `--task` option does
not narrow it. **The witness does not contradict the product's words; it
states them, and the product's words are the same.**

## R6. A mutable number enters a record only after a fresh measurement, anchored to that measurement

**Pass.** The costs were re-measured from the second round's runner log
and the anchor moved to `486a71c`; the three documents that print costs
were carried with the table, and the floor witness confirmed the floor's
name and its figures against it.

**And the new numbers are worth reading.** The CLI's own request costs
**63.5 s on Ubuntu and 128.3 s on Windows** — more than any other CLI
test file, and the reason the e2e class grew. The names witness costs
0.15 s and 0.28 s. **The two newest witnesses still carry `0.0`** until
the next run supplies their numbers.

## R7. A witness that constructs the thing it watches cannot notice its absence

**Pass.** Both witnesses build the **premise** — two tasks holding one
material, a source holding addresses — and watch what the product does
with it. The dangling-id witness reads the product's own answers: the
CLI's exit code, the API's status code, the record's fields. **No
witness writes the answer it looks for.**

## The finding this batch produced

**A record can be certified as citable over a source row that is gone.**

The record was measured across the product's faces, and the faces split
three ways:

1. **The source faces refuse and name the id** — `sources addresses`,
   `sources inspect`, `GET /sources/<id>`, `GET /sources/<id>/addresses`,
   `task claim`: exit 3 on the CLI, **403** on the API.
2. **The report face refuses and names the id** — `task report` and
   `POST /report` answer `report_content_refused`, naming the anchor and
   the source it points at.
3. **The record face reads as sound while the row it names is gone.**
   `GET /records` answers **200** with the citing record intact —
   `status extracted`, its anchor ids, its `source_content_hash` — and
   still **200** after attestation, `status user_attested`. And
   `task claim-attest` **advanced that record into the citable set with
   exit 0, without asking of the anchor's source row a second time.**
   The observed hash is `None`, because there is no row to read it from,
   and no wired face runs the C1–C3 comparison that would notice.

**This is a product gap, measured and witnessed, and this batch does not
fix it.** The witness holds the behaviour as it is, so a face that
learned to check the source row again would turn it red — which is the
shape a fix takes when the fix is made. **The gap is recorded in the
handoff and in the record, and it is the next batch's work.**

## The second reader

**A reader who has never seen the pilot can check every claim.** The
scope witness builds its own ledger; the dangling-id record's numbers
each name the command that produced them; the material stays outside the
tree. **What a reader cannot repeat is the reading's own state** — the
scratch workspace it ran against is gone with the run, and the record
says so.

## What this review did not cover

- **The gap itself.** A citable record over a deleted source is measured,
  not fixed, and this review did not design the fix or say which face
  should refuse.
- **Whether the other faces are consistent with the two that refuse.**
  The reading followed the faces the record names; it did not enumerate
  every face in the tree.
- **The record's own claims about the API** — the reading took the
  status codes the API returned, and it did not read the API's own
  contract for what it should return.
- **The git history**, as batch 15 says.
- **The cost of the two newest witnesses**, which is `0.0` until a runner
  says otherwise.

## Where each finding went

| Finding | Where it went |
|---|---|
| A record can be certified citable over a source row that is gone | measured and witnessed in `1dc0197`; the fix is the next batch's work |
| What a removal releases with two holders | `57b79da` — three witnesses, and the record's "could not distinguish" is now distinguished |
| Two new test files were in no manifest and no shard | `68eef58` — filed, with their costs owed to the runner |
| The threat model's write range moved with the command | `28cf0f1` — 444-448 is now 473-477 |
| The costs and the documents that print them | `28cf0f1` — measured at `486a71c` and carried |
