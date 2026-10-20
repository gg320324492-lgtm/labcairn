# LC-P1-10 — Acceptance review

**Work order:** LC-P1-10 — bounded statistics and deterministic plots.
**Verdict:** **PASS WITH NOTES**.
**Reviewed against:** the merged state of `main` at `7c816a2` (PR #59) — all
eleven subtasks merged, from the chart library's decision to the exit
demonstration.
**Reviewer:** Claude, the same party that specified the work and dispatched the
implementation. **This is not an independent review** — see "Reviewer
independence" below, and the same caveat LC-P1-09's review carries.

## Verification actually run

- **The whole suite on the merged `main`:** 2600 passed, 2 skipped, 361 s
  (`uv run pytest -q --basetemp=…/lcp110-accept2`, exit 0). The two skips are
  pre-existing and explain themselves: a provider credential this machine does
  not have, and a Windows-drive assertion that is meaningless on POSIX.
- **`ruff check`, `ruff format --check`, `mypy` (strict, 184 files):** clean.
- **Seventy-one independent mutations** written by the reviewer against the
  merged branches, and not from the branches' own reports:

  | Subtask | Mutations | Caught | What the survivors were |
  |---|---|---|---|
  | T05, the grouped aggregate | 15 | 14 | one was a **no-op mutation** (an absent cell's text is `None`, so the mutation changed nothing) and one **survived only because the reviewer had picked one test** — a second test in the same file caught it |
  | T06, the chart recipe | 15 | 11 | two were bad mutations (one swapped one refusal for another; one hit a method the test never calls) and one was a **real gap**: a malformed operator reference was refused by no test |
  | T07, the renderer | 8 | 8 | none |
  | T09, the run path | 19 | 17 | two were **real gaps**: a policy denial's *message* was unobserved, and the manifest's `parameters` field was unobserved |
  | the declared-unit check | 6 | 6 | none |
  | the four unobserved properties | 4 | 4 | none |
  | T10, the exit demonstration | 4 | 3 | the fourth is **not catchable by the repository**: a check made vacuous still prints, still counts and still exits zero, so nothing in the repository can notice. The review's mutation table is what records it |

  Each surviving mutation was then checked **by hand** before it was called a
  finding. Two of the five were the reviewer's own mistakes, and one of those
  mistakes had been reported to the user as a gap before it was found to be
  wrong; the corrections are recorded in the pull requests.
- **The exit demonstration**, run end to end: 19 checks, six steps, exit 0.
- **The status board's own consistency test** (112 tests) after every change
  to the board, the handoff file and the plan.

## The clause

> **Acceptance:** numerics recalculated from source with controlled fixtures;
> dimensions/units checked; charts match data and captions; missing/invalid
> data reported, not silently imputed. Deterministic output on identical
> inputs as applicable.

## What the review found

**Three things were not delivered when the review began, and all three were
closed before this verdict.**

1. **The units check was vacuous for the common case.** The only unit check
   that existed compared the *cells'* unit tokens with each other, and the
   function that computes a column header's **declared** unit had no caller in
   the production code at all — exported, documented, unit-tested, and dead. A
   table that keeps its units in the header, which is what a real table does,
   therefore found nothing to check and passed. The plan's own §3 names that
   failure: *"a check that only ever looked at cell text would find no unit to
   check and pass vacuously … a check that looks like a check and is not one."*
   Closed by PR #56: the declared unit is now checked against that column's own
   cells, per column, in the selection layer, so every operator inherits it; a
   cell with no token leaves the declaration **unverified** rather than
   contradicting it; and the refusal names both tokens.
2. **Four properties no test observed** — the excluded-row count's agreement
   with the table, the filtered-row count outside its zero case, the
   grammar refusal of a malformed operator reference, and a group carrying a
   value and a reason at once. Closed by PR #57.
3. **The figure's caption was drawn across the x-axis tick labels**, so a
   reader could not tell which bar was which group. Found by the exit
   demonstration, confirmed by rendering the demonstration's own recipe, and
   fixed in the pull request that carries the demonstration.

**Two gaps remain, and both are limits of the work order rather than defects
in the implementation.** They are recorded in the task breakdown's §5 and
repeated here, because a limit that is only written down in a plan is not a
limit anybody is told about.

## Clause 1 — numerics recalculated from source with controlled fixtures

**DISCHARGED.** The corpus under `tests/fixtures/analysis/` is eight committed
CSVs with hand-written expected values beside them, and a test that recomputes
those values with Python's `statistics` — an implementation that is not
LabCairn's, so an expectation cannot share a bug with the code the operators
are written against. The operators read the **ingested representation** bound
to the file's hash, not the file, and the run path refuses a source whose
bytes have moved since the ingest.

The reviewer did not take the corpus on trust: the operators' outputs are
compared against those hand-written values by the corpus test, and a mutation
that made the grouped aggregate compute over the whole selection instead of
the measured column was caught only by the tests the reviewer added.

## Clause 2 — dimensions/units checked

**DISCHARGED, and it was not discharged until PR #56.** Three rules, all now
implemented and observed:

- a cell that carries a unit token must carry the **same** token as every
  other cell in the selection, or the operator refuses and names both;
- a column header of the form `name (unit)` declares a unit for that column,
  and **the declared unit is checked against that column's own cells** — a
  differing token is a conflict, refused, naming both tokens; and the
  **recipe's** declared unit must match the header's, and the recipe's own
  axis label must not contradict the data's unit;
- a cell with **no** token leaves the declared unit **unverified** rather
  than contradicting it, and the result's unit stays `None`.

Units are compared **as written and never converted** — the owner's decision,
inherited from C3 — and the known false negative (`kilograms` and `kg` are
one unit spelled two ways) is stated rather than hidden.

The reviewer's own mutation check confirmed that the check is not vacuous: the
mutation that makes the declared unit unconsulted, the one that lets a
no-token cell contradict a declaration, the one that folds case, the one that
inverts the comparison, and the one that drops a token from the refusal are
each caught by a named test.

## Clause 3 — charts match data and captions

**DISCHARGED.** The renderer plots **the operator's result object**: it does
not re-read the file and does not re-implement the aggregate, so the plotted
values *are* the operator's values. The chart operator that does the drawing
is a **catalogue entry**, and the renderer dispatches to it through the
catalogue, so *"a vetted chart operator renders"* is code rather than
convention.

The captions are checked too, and the check is the acceptance clause's own:
**a caption that states a number the data does not hold is refused**, naming
what was wrong; a caption that states no number is fine, because a caption
says what is plotted and is not a claim of a value; and the **interpretation**
is a separate field that is never checked, because ADR-0004 A10 holds that an
interpretation is never machine-verified — so the renderer emits it with an
explicit *"interpretation not machine-verified"* marker, and a recipe with no
interpretation carries no marker.

The caption's readability was a real finding: the caption was drawn across
the axis tick labels. The fix measures the space the labels occupy rather
than assuming it, and a test observes that the two bands do not overlap.

## Clause 4 — missing/invalid data reported, not silently imputed

**DISCHARGED.** Every result carries `n_used`, `n_empty`, `n_absent` and
`n_invalid`; a blank cell is never `0`; the mean of an empty selection is
undefined with a reason and never `0.0`; a group with no quantity has **no
statistic** and its reason names **that group** rather than the selection; and
a count that the format does not permit is `Unknown` with a reason, never `0`.

The reviewer's mutation check confirmed the two that matter: a group with no
statistic drawn as a zero, and an undefined group's reason blaming the
selection instead of the group, are each caught.

## Clause 5 — deterministic output on identical inputs

**DISCHARGED, with its scope stated.** Two renders of one recipe in one
environment are byte-identical, and the **salt** is what governs stability
*across* processes — left unset, matplotlib generates a fresh random salt per
interpreter, so a test that renders twice in one process cannot see it at all.
**PNG needs neither control**: two PNG renders in two separate processes are
byte-identical with the salt unset, and matplotlib's PNG metadata carries a
constant `Software` string and no date. The `rcParams` come from a **declared,
hashed** defaults file, so an ambient `matplotlibrc` is not an input nobody
put in the manifest, and a hostile one cannot change the bytes.

The manifest records the environment fingerprint that scopes the claim, and
the **six fields** the work order names: the input file's hash, the
selection, the operator and its version, the parameters, the recipe, and the
output hash.

**The scope, stated plainly:** the manifest records **no version for the
renderer**. The size, the histogram's bin count and the digest of the
declared settings are facts about the renderer's build, and the manifest
carries neither them nor the renderer's version. So two figures whose
manifests name the same operator, the same recipe and the same environment
can still differ in their bytes because the renderer changed between them.
Two ways to close that are named in the task breakdown's §5 — record the
renderer's version and its published digest alongside the operator's, which
is narrow, or widen `RenderEnvironment` into a place for drawing parameters,
which is wide and is a decision about what the work order promises — and
**this work order chooses neither**. The byte-identity claim is therefore
scoped to *one renderer's build* as well as to one recorded environment, and
the figure's own hash is what records the bytes.

## The twelve conditions of ADR-0004 Contract 4

| # | Condition | Verdict here |
|---|---|---|
| A1 | Every claim is traceable to a source | **DISCHARGED for analysis.** Every value the operators produce is a cell the selection names, and the run path reads the ledger's own text for it; the figure's chain runs file → result → manifest → figure, and nothing names a document that has not been written |
| A2 | Hash drift → fail, derived artefacts stale | **PARTLY DISCHARGED, and this is where the part is.** A changed file makes the run refuse (`source_drifted`) and the manifest's input hash stop matching, and the repository's own invalidation walk marks the figure and the manifest `STALE` with a reason. What is *not* discharged is the general "every derived artefact is marked stale" — that is an artefact-graph walk, and LC-P1-10 marks **its own** outputs, not the whole graph |
| A3 | An evidence record states what was found, not what was concluded | **DISCHARGED.** An aggregate is a **derivation** and is recorded as a manifest, not as an evidence record; the manifest states the input's hash, the selection, the operator and its version, the parameters, the recipe and the output's hash, and nothing concludes anything |
| A4 | Nothing is silently imputed | **DISCHARGED.** See clause 4 |
| A5 | Conflicting numbers → both `conflicted` | **NOT TOUCHED.** The grouped aggregate is not a ledger record, so it cannot be `conflicted`. Two different analyses of the same cells are two derivations with two manifests, and the disagreement is visible in the manifests — not in the state machine |
| A6 | Every source is recorded with what was extracted from it | **DISCHARGED.** The manifest's input hash is the source's own `content_sha256` — one lineage, not two — and the selection names the cells the numbers came from |
| A7 | Unreadable source excluded and uncitable | **DISCHARGED for analysis.** A source whose `readability` is not `readable` is refused by the run path, so it can be neither analysed nor cited, and an unreadable source is not an empty one |
| A8 | Unknown is not zero | **DISCHARGED for statistics.** An undefined mean and an undefined stdev are `None` with a paired reason, never `0.0`; a count that the format does not permit is `Unknown` with a reason; and an unmeasured unit is absent rather than blank. A spreadsheet's blank cells are not recoverable from the ledger, and the analysis says so rather than counting them as zeros |
| A9 | Every record is bound to its source | **DISCHARGED.** The manifest's input hash is the file's own hash, computed by one of the two functions that already implement it; the third implementation the plan warned against was not added |
| A10 | Interpretation always unverified | **DISCHARGED for figures.** The recipe separates the caption from the interpretation, and the renderer marks the interpretation. The *report*'s marker for ledger records is still LC-P1-11's |
| A11 | Retrieved text is data | **DISCHARGED for figures.** Untrusted cell text and group names are escaped in the SVG, asserted by a test with an instruction-shaped and a script-shaped value. The stronger half — that a model does not *read* it as instruction — is not claimed, for the same reason LC-P1-09 did not claim it |
| A12 | Fabricated source fails | **NOT TOUCHED**, and unchanged from LC-P1-09's note: a fabricated **DOI** still has no implementation, and nothing in LC-P1-10 makes it closer |

## What the fixes were, and how they were checked

| Finding | Fix | How it was checked |
|---|---|---|
| The declared unit was never consulted | `units.declaration_disagreement`, applied by `resolve_selection`, per column | The reviewer's six mutations, each caught by a named test; the grouped aggregate's inheritance pinned at the grouped level as well |
| Four properties no test observed | Four new tests, in the grouped and recipe test files | The reviewer's four mutations, plus the old test files restored to show that two of the properties really were unobserved |
| A policy denial reported with the message an unanswered question gets | The reason's docstring widened, and the translation pinned **by type** rather than by raise site | The reviewer's two mutations, now caught |
| The manifest's `parameters` field was unobserved | The six-fields test now runs an operator that *has* a parameter, and a new test requires the parameters to be the operator's own arguments | The reviewer's mutation, now caught |
| The caption covered the axis tick labels | The text block starts below the measured label band | A geometric test that fails when the old layout is restored |
| The plan's T07 table said the creation date is written into PNG metadata | The table corrected, and the correction recorded in the plan's §3b | Re-measured: two PNG renders in two processes are byte-identical, and the PNG's only text chunk is a constant `Software` string |

## Reviewer independence

**There is none, and this is the review's most important caveat.** The work was
specified by the reviewer, dispatched by the reviewer to agents the reviewer
instructed, and reviewed by the reviewer. The mutation checks are independent
of the agents' own reports — the reviewer wrote the mutations rather than
reading them, and two of the three "gaps" the agents reported were corrections
to the reviewer's own findings — but independence from the *implementers* is
not independence in the sense ADR-0004 and LC-P1-09's review mean. The
requirement that this work be reviewed by someone other than the party that
wrote it is **not discharged**, and it is the same open item LC-P1-09's
acceptance carries.

## Not covered by this review

- **The aggregate's numbers are not re-checked by C1, C2 or C3.** They are
  traceable to the file and to the manifest, and the manifest is the audit
  trail, but nothing recomputes them at gate time. This is the work order's
  most important limitation and it is a narrowing of the product's central
  promise.
- **The "fabricated DOI" half of LC-P1-09's clause**, and **source provenance
  preserved through report generation** — both are LC-P1-09's and LC-P1-11's,
  and neither is LC-P1-10's.
- **The renderer's version**, as clause 5's scope paragraph says.
- **The earlier exit demonstrations.** `g1_exit_demo.py` and
  `g2_exit_demo.py` are run by nothing — no test, no CI job — so they can
  rot without anyone noticing. LC-P1-10's demonstration is covered by a test;
  the earlier ones are not, and nothing here fixes that.
- **A second opinion.** The review is one party's, and a reader who wants a
  different one has not had one.
