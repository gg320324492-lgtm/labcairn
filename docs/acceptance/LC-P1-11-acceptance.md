# LC-P1-11 — Acceptance review

**Work order:** LC-P1-11 — report assembly, export and artefact versioning.
**Verdict:** **PASS WITH NOTES**.
**Reviewed against:** the merged state of `main` at `2e485b0` (PR #81) — the
report's document model, the four renderers, the artefact manifest, the
revisions, the content checks, the document builder and the application
layer's report operation.
**And, at the gate's close, against the tree the gate's independent
reviewers verified:** the four round-five fixes composed at `9a6319e`, at
**`9381036af0104172f16fe94a6edd2e8cb6d9ae04`**.
**Reviewer:** Claude, the same party that specified the work, dispatched the
implementation and wrote the fixes. **This is not an independent review** — see
"Reviewer independence" below, and the same caveat LC-P1-09's and LC-P1-10's
reviews carry. **The board's rule is discharged by the gate's independent
review**, which covered this work order; see "Reviewer independence" below.

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
- **The whole suite on the merged `main` at `2e485b0`:** 3050 passed, 3
  skipped, 610 s. The three skips are pre-existing and explain themselves: a
  POSIX permission-bit assertion that is meaningless on Windows, a provider
  credential this machine does not have, and a Windows-drive assertion that is
  meaningless on POSIX.
  **An earlier measurement of this suite was red**, and its number is not the
  one above: `test_readme_commands_run` failed on a decode — a byte this
  machine's encoding could not read killed the reader thread and truncated the
  capture. That run reported *2720 passed, 1 failed*; the fix is on `main`
  since `99c3d49` (PR #76), and the figure quoted here is a run that was
  green, re-measured on the merged `main` rather than taken from a report.
- **`ruff check`, `ruff format --check` (251 files already formatted), `mypy`
  (strict, 235 source files):** clean.
- **One hundred and thirty-six independent mutations** written by the reviewer
  against the merged branches, and not from the branches' own reports:

  | Subtask | Mutations | Caught | What the survivors were |
  |---|---|---|---|
  | T00, the document model | 6 | 6 | none |
  | T01, the four renderers | 30 | 30 | four were **real gaps** and one was the reviewer's **own error**: the PDF form escaped every value **twice** and so printed `&amp;` where the model said `&`; the escape table's eighteen characters were pinned for only the fourteen a test happened to use; the Markdown's title and ids were not observed to be escaped; and a narrative beginning with four spaces became an indented code block. The reviewer's error was calling a second guard "unreachable" — it is reached exactly when the first guard fails to fire, and it is that guard's distinct wording that makes the first observable |
  | T02, the artefact manifest | 34 | 34 | six were **real gaps**: the writer accepted `revision`, `producer_id`, `produced_by` and `receipt_id` and dropped all four, and the tests asserted only the defaults, so "honoured" and "hardcoded" were indistinguishable; a figure's manifest link's id was unpinned; a caller's supplied upstream for a figure was silently dropped; the chain's own contradiction refusal was unobserved; the document part's path was not proved to be the caller's; and the manifest was not observed to be written inside the task's output area. A seventh was the module docstring **overstating** rule 1 |
  | T03, the revisions and the staleness | 8 | 8 | none |
  | T04, the content checks | 34 | 34 | five were **real gaps**: the report could **overstate a record's verification state**, because nothing compared the status the report *prints* with the ledger's; the record's kind and the disclosure's kind and text were compared in the code and compared by nothing in the tests; an artefact outside the workspace was accepted; an unresolved record need not be in the snapshot; and an anchor the ledger had never heard of was accepted |
  | T12, the document builder | 10 | 10 | none |
  | T13, the layer's report operation | 7 | 7 | none |
  | the layer's event read | 7 | 5 | **two were not findings**: one replaced a `load_task` call with a fallback the store never returns — it raises — and one asserted a property the layer could not satisfy, the *identity* of the events, which is impossible because the store's readers read the log afresh on every call |

  Each surviving mutation was checked **by hand** before it was called a
  finding, and three of the reviewer's own mistakes were corrected in the
  process — one of them had been reported to the owner as a gap before it was
  found to be wrong. The corrections are recorded in the pull requests.
- **The escape table holds eighteen characters, and this review said
  nineteen.** The independent review of the gate counted them and found the
  off-by-one: the table is the seventeen CommonMark ASCII punctuation
  characters that can open a span or a block, plus `&`. **The set is
  complete** — the reviewer checked the fourteen ASCII punctuation characters
  that are *not* in the table against seven attack shapes each, and none of
  them opens structure — so the defect this review reported was the
  *unpinned* characters, not a missing one, and the count was the reviewer's
  own miscount. The number in this document is corrected, and so are the
  three other records that repeated it.
- **The table above was re-run against the merged `main` after the review was
  written**, so that the figures are not the reviewer's recollection of its own
  work: **T12's ten** — seven in the builder, three in the interpretation —
  and **T13's seven**, and every one was caught again. The re-check also
  closed a gap in the reviewer's own bookkeeping: T13's seventh mutation, the
  `artifact_recorded` event without which the receipts would be rows nobody
  had been told about, had never been written down, so it was written for the
  re-check rather than the count being edited down to six.
- **The status board's own consistency test** — 116 tests on `main` at
  `2e485b0`, 117 with this review's own document added to the tree, since the
  test checks every document under `docs/` — after every change to the board,
  the handoff file and the plan.

## The clause

> **Acceptance:** exports are openable; numeric values agree with ledger,
> figures/captions intact, links resolve, output hash/lineage retained.
> Re-rendering after material change invalidates stale output.

## What the review found

**The report path had two pieces missing between the pieces that were
planned**, and neither was visible from any single subtask:

- **Nothing assembled a `ReportDocument` out of what a task actually has.**
  T00 built the report's *classes*; T01 through T04 built the renderers, the
  manifest, the revisions and the checks. Every one of them was correct on its
  own, and none of them noticed that the document they all talk about had no
  producer. The model could hold any content at all, and the checks could
  only say whether that content agreed with the ledger. The builder
  (T12) is what makes the content **the ledger's**: a record that may be
  stated becomes a claim and one that may not becomes a disclosure, a figure
  carries its caption and its own manifest, a citation names the address the
  record was read from, and the snapshot names exactly what the report
  carries. It **refuses** rather than guessing — a record that cannot be
  cited refuses the build, because dropping it would omit a verified finding
  and disclosing it would state a conflict that is not one.
- **The application layer's `render_report` was a stub that refused
  everything**, with a docstring saying *"LC-P1-11's T00 and T01 have not
  landed"* — which was true when it was written and false afterwards. It now
  gathers, builds, checks, renders the four forms **from that document**,
  writes the revision with the chain as a flat ancestor closure, and records
  the receipts and the event (T13).

**And four defects of the review's own class — a property stated and not
watched** — were found in the pieces that had been reviewed already, and all
are fixed:

- the PDF form escaped every value **twice**, so a report printed `&amp;`
  where the model said `&`. Every assertion about escaping was true — the
  value *was* escaped — so no source-level check saw it; only reading the
  rendered text back did.
- the Markdown's escape table named eighteen characters and the tests
  exercised fourteen of them, so `~`, `!`, `=` and `\` could each be deleted
  with nothing noticing.
- the report could **overstate a record's verification state**: the status the
  report prints was never compared with the ledger's, and the report's own
  status is what a reader weighs the finding by.
- the manifest's writer accepted four parameters and dropped all four, and
  the tests asserted only the defaults — so a parameter that is accepted and
  ignored was indistinguishable from one that is honoured.

**One defect was found outside this work order entirely**: the source id was
declared a UUIDv7 while the ingestion path minted `src-<hex>` and the source
model said the id was text. So a task could never bind a material that
exists, and the repository read a bound id back with `UUID(...)`. It was
found while reviewing this work order's tests, fixed as its own change, and
recorded here because the review found it.

## Clause 1 — exports are openable

Each of the four forms is parsed back by something that is not the writer —
the DOCX and the PDF by a reader, the Markdown and the HTML by a parser — and
the content it reads back is the model's.

**Satisfied.** T01's four renderers, and the review's thirty mutations
against them, which found the double escaping and the unpinned escape table
above. The DOCX and the PDF are **not** byte-reproducible, and nothing claims
they are: the report says so on its own face.

## Clause 2 — numeric values agree with ledger

Every number in the report is compared with the ledger record it came from,
and a report that says 4.25 where the ledger says 4.5 is refused.

**Satisfied — but the evidence for it was one form's worth, and this review
did not say so.**

T04's check compares the value and the unit **exactly** — the comparison is
the claim, and a tolerance would be a second opinion about the ledger's
number. And the number in the report is the record's, because T12 is what put
it there.

**The correction.** The check runs on the **document**, before any form is
rendered, so the clause is discharged once and centrally — but the test that
witnessed it, `test_no_number_appears_that_the_model_does_not_hold`,
**read the PDF only**. The independent review of the gate mutated the
**HTML**, the **DOCX** and the **Markdown** so that each carried a number the
model does not hold, and **all three survived**: nothing watched whether a
*renderer* put a number of its own into a form. **The clause was not
violated — the product enforces it on the document — but the evidence for it
was thinner than this review said it was.**

**The gap is closed**: the test now reads **all four forms** back and asserts
each carries exactly the numbers the model holds. **This is the second time
this review missed something the gate's independent review caught**, and the
shape is the same both times — a property that holds centrally, and whose
*evidence* was read at one place rather than everywhere it applies.

**What would have caught it here:** asking, of every property, *where the
evidence for it is read* — not only where the property is enforced.

## Clause 3 — figures/captions intact

The figure's bytes in the report are the figure artefact's bytes, and the
caption beside it is the caption in the model.

**Satisfied.** T04's artefact check **opens the file and hashes it** — for a
figure and for a table alike ✓ — and refuses an artefact that is not there
or that resolves outside the workspace ✓.

## Clause 4 — links resolve

Every link in the report points at a locator that the index can resolve, and
the check is a resolution, not a string comparison.

**Satisfied.** T04 resolves each citation through the index and acts on the
answer the material gives ✓ — and it refuses a citation that names an
address the record was not read from ✓, which a string comparison would not
have noticed.

## Clause 5 — output hash/lineage retained

The manifest records each part's hash and its lineage, and the receipt records
the manifest's hash, so the chain from the ledger to the exported file is one
line of hashes.

**Satisfied.** T02's manifest is built **from the document** rather than
beside it ✓, so it cannot disagree with the report it describes ✓; and T03's
chain is a **flat ancestor closure** ✓ — the material's hash is directly in
the report's own `derived_from` ✓, because the staleness walk that already
exists is **one hop** ✓ and a chain naming only its parent would never see
the material move ✓.

## Clause 6 — re-rendering after material change invalidates stale output

The invalidation walk marks the report `STALE` with a reason, and the re-render
is a new revision that does not alter the old one.

**Satisfied.** T03 writes each revision under its own path ✓, refuses to
rewrite a revision that has been written ✓ — a DOCX is a ZIP whose entries
carry timestamps and a PDF carries a creation date ✓, so a second render of
revision 1 would produce different bytes for one number ✓ — and puts the
material's hash in the chain ✓ so the repository's own walk marks the report,
the manifest, the figure and the four forms in one pass ✓, with the
repository's own reason ✓ and no change to G3's accepted code ✓.

## The conditions of ADR-0004 Contract 4 that this work order touches

| Condition | Verdict |
|---|---|
| A3 — a record states what was found, not what was concluded | **Discharged.** A claim names the ledger record it rests on ✓, and a record that may not be stated becomes a **disclosure** rather than a finding ✓, with a reason composed from the record's own verification log and never invented ✓ |
| A6 — every source is recorded with what was extracted from it | **Discharged.** A report's citations carry the source, the locator and the content hash ✓, and the citation is the address the record was actually read from ✓ |
| A10 — interpretation is always unverified | **Discharged.** The figure's own reading travels into the report as an `InterpretationBlock` ✓ and the renderers mark it with the same constant the figure's renderer uses ✓; and a claim may not restate an interpretation as a finding ✓ |
| A11 — retrieved text is data | **Discharged.** The report renders retrieved text ✓, and it escapes it ✓ — the Markdown through one table of the characters that can open a span or a block ✓, the HTML through `html.escape` at every interpolation ✓, the PDF through reportlab's own markup escaping ✓, and the DOCX not at all ✓, because OOXML text is not a markup language ✓. The review's own mutations are what found the double escaping ✓ |
| A12 — a fabricated source fails | **Partly, and the owner's decision says how far.** A report cites locators ✓, so a fabricated source cannot be cited by identifier ✓; but nothing *verifies* an identifier that the material itself carries ✓, and the report says so on its own face ✓ |

## What the fixes were, and how they were checked

Every fix above was made on the subtask's own branch, pushed as its own
commit, and **checked by the reviewer re-running the mutation that found it**
— not by the author saying it was fixed. The corrections that were *not*
defects are recorded too: the review's three mistakes are in the pull
requests' histories, with the reasoning that corrected them.

## Reviewer independence

**This review is not an independent review, and it never was.** The reviewer
specified the work, dispatched the implementation, wrote the fixes and
reviewed them — the same party in all four roles, as with LC-P1-08,
LC-P1-09 and LC-P1-10 before it. What the review *can* claim is that its
mutations were written against the merged branches and not from the
branches' own reports ✓, that every surviving mutation was checked by hand
before it was called a finding ✓, and that the findings it reports are ones
it demonstrated by breaking the code and watching a named test fail ✓.

**The board's rule is discharged by the gate's independent review, and it is
discharged.** The rule is that a row is marked done only when an
**independent** review at a **named commit** says so, and this work order is
covered by the gate's review of the report path.

**How it was discharged.** Two reviewers were dispatched for G4, one for the
report path and one for the three surfaces, and **neither of them wrote a fix
into this repository** — a reviewer that fixes what it finds has stopped being
independent. The fixes were made by other parties, and **each reviewer was
then asked to re-run its own mutations against them**, which is the second
half of the independence: a reviewer that wrote the fix is no longer a
reviewer.

**The report path's review failed the gate five times**, and the reason is
the same each time: **a property table can be entirely clean and the review
still fail.** The first was on two open defects and five unwatched refusals;
the second on one unwatched refusal the first fix had introduced, and on an
acceptance clause witnessed for one of the four forms; the third on **fourteen
surviving mutations out of a hundred and sixteen**; the fourth — after the
fix that generalised the comparison of the four forms — on **eight**, in a
class the fix's mechanism could not reach, **what a form says about itself
outside its own text**; and the fifth on **four**, in a hole in that fix's
own mechanism, **the list-item witnesses compared a count and a count cannot
see a substitution**. **Every one of those findings is fixed**, and the
reviewer that found each one re-reviewed the fix.

**The three surfaces' review came back BLOCKED**, on two blockers and six
notes, one of the blockers sitting directly under the gate's own exit test —
**and its re-verification came back BLOCKED again**, on **two mutations that
survive**: the witnesses for one of the blockers **had been deleted by this
gate's own composition**, and the demonstration's own comparison of the two
surfaces was unwatched.

**All the findings are fixed, and both reviewers re-ran their own mutations
against the fixed code.** The gate's own record — the
[gate review](G4-acceptance.md) — carries every round, every mutation count
and every finding, and it names the commit this gate closed on:
**`9381036af0104172f16fe94a6edd2e8cb6d9ae04`**. **The gate is closed, with the verdict PASS WITH NOTES**,
and this work order's row can be marked done on the strength of **that**
review and not of this one — this record is the work order's own review, and
it says so on its own face.

## Not covered by this review

- **The exit demonstration.** G4's demonstration is T09's ✓ and is shared
  with LC-P1-12 ✓; it is not part of this work order's clauses ✓ and this
  review does not run it ✓ — **the gate's own review runs it**, because it
  is the gate's exit test ✓.
- **The surfaces.** The CLI, the local API and the workbench are LC-P1-12's
  ✓, and they are reviewed in *its* acceptance review ✓.
- **The report's own interpretation.** The report carries the **figure's**
  reading ✓, because that is the reading the ledger holds ✓; a reading about
  the report as a whole has no source in Phase 1 ✓, and the model's
  machinery for one waits for a phase that has one ✓.
- **What the report looks like to a reader.** The renderers' output was read
  back ✓, not read as a person would read it ✓.
