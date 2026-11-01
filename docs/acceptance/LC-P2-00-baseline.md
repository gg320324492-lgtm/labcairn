# LC-P2-00 — The frozen Phase 1 baseline

**Work order:** LC-P2-00 (freeze the P1 baseline — the first row of
[`PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md) §3) ·
**Status:** **LANDED** — the baseline document is in the tree, and the
phase's exit gate (*"measured capability gain against a frozen P1
baseline"*) now has the denominator it was missing.

**Measured:** 2026-11-02 on the tree at
`81babd51685c5dc72152fb424b1543e74c787140` (main after PR #143), on
Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13, by

```
python -m tests.evaluation --out E:\labcairn-local\evaluation-baseline-freeze-canonical
```

which ran the harness's five offline gate classes and the repository's own
gates in one run of 2208.4 seconds and exited **2** — the exit code the
harness gives when a *selected* class could not run, and the honest one,
for the reason below.

**What this is.** The baseline is one evaluation run and one JSON document
that names its commit, its platform, its tree state, its model and its
cost: [`LC-P2-00-baseline.json`](LC-P2-00-baseline.json), in the shape
`tests/evaluation/comparison.py::load_baseline` reads. Every later
comparison this phase draws — *"a retrieval change moved the figure and
the frozen baseline shows it moved"* — is drawn against the numbers in
that file, and the file's basis is checked before any of its numbers are
printed beside a later run's.

## The run

The run recorded here is the **canonical** one: it ran on the main
checkout at `81babd5`, with no `PYTHONPATH` set, so the repository's
clean-room witnesses (the outsider path, the wheel install) ran the way
they are designed to run, importing the installed package rather than a
development tree. `git status --porcelain` was clean while the harness
measured, and the report records that: *clean — the commit is the tree
that was measured*. The full report (markdown and JSON) lives outside the
repository at `E:\labcairn-local\evaluation-baseline-freeze-canonical`,
because runtime artefacts do not live in the tree.

A second, earlier run on the same commit — made from this repository's
worktree with `PYTHONPATH` pointed at the worktree's `src/` — is recorded
here as a control, and it is why the canonical run is the one frozen: with
`PYTHONPATH` set, the clean-room witnesses resolve `labcairn` to the
development tree instead of the environment each of them builds for
itself, and four e2e cases (the outsider path) and the wheel-install
witness fail **as a consequence of that environment**, not of the tree.
The canonical run shows the same two classes at 140/140 and 688/688. The
five non-passes below, by contrast, appear in **both** runs; they belong
to the tree and the machine, not to the invocation.

## The basis

The basis is what `assess` checks before it prints any number. It is
recorded in the JSON document, and each field is what the harness's own
run declared:

| field | value | what it means |
|---|---|---|
| `model` | `""` | **The run declares no model.** The offline run used the deterministic `FakeProvider`, which is not *a declared model, version and parameter set*; the harness's own `_run_basis` declares the empty string, and the baseline carries what the harness actually declared — not an invented model name. The protocol's own rule (*mock-only success is insufficient*) is what produces this. |
| `budget` | `""` | No provider spend: the `FakeProvider` costs nothing, and nothing was spent. |
| `fixtures.names` | the 11 corpus fixtures | `tests/evaluation/corpus.py::CORPUS_FIXTURES`, in its order. |
| `fixtures.versions` | sha256 of each answer key | `tests/fixtures/analysis/<fixture>.expected.json`, hashed exactly as the harness hashes them. |
| `verified_capabilities` | unit, integration, negative, e2e, repository | The classes the run ran and collected cases in. The protocol's real-model smoke is **not** in this list. |
| `limitations` | the FakeProvider sentence | The harness's own limitation text, verbatim. |
| `confidence_intervals` | `""` | None are claimed. The measured metrics are deterministic over the committed answer keys; the one that is not (latency) is a single wall-clock reading, and the document does not dress it up as an interval. |

## The numbers

The metrics the harness measured, with their denominators and their
failure cases exactly as the protocol names them:

| metric | value | what the numerator and the denominator count |
|---|---|---|
| numeric-extraction-exactness | **84/84** | The cells the committed answer key addresses, compared cell by cell against the classification the product's own selection code gives them. |
| unsupported-claim-detection | **1/1** | The public fixture corpus's questions whose answer key says the material does not state the answer, over the questions that require an abstention. **The denominator is one**, and the report says so: a rate over one case is not a rate that means much on its own, and this document does not read it as one. |
| recovery-correctness | **4/4** | The distinct crash points the crash matrix injects and that behaved the way the matrix specifies, over the crash points the product defines — counted once per crash point however many cases inject it. |
| latency-usage-cost | **2208406/4467** | The wall-clock milliseconds the harness's own gate-class runs took, over the test cases they collected. The harness's `how` line says what this is and what it is **not**: a mean per case over the repository's own tests, not the protocol's task latency, which needs a task corpus and a provider that answers it. The **model name is NOT MEASURED** for a real provider — the offline run used the `FakeProvider`, and the report says so rather than filling the field in. |

Three of the protocol's seven metrics are **NOT MEASURED**, and the report
gives the reason for each rather than a zero:

* **end-to-end-task-success** — the protocol counts successful verified
  deliveries over attempted tasks; the run counts test cases, and a corpus
  of questions with known answers is not a record of deliveries.
* **evidence-locator-validity** — the protocol asks for a human-checked
  sample; the tree records none, and a machine count is not a substitute
  for one.
* **revision-consistency** — the protocol's metric is the rate over source
  changes; none of the tree's committed corpora records a source change
  with the outcome that followed it.

## What was not run

**The real-model smoke class was not run**, and that is the expected
outcome of this run, not a defect in it. The class needs *at least one
real supported provider under declared model/version/parameters*, no
provider credential is configured in this environment, and a run would
spend money. Mock-only success is insufficient under the protocol, so the
harness reports the class as **NOT RUN** with the reason, does not count
it as a pass, and exits 2. **No provider run was faked and no model name
was invented to fill the gap**; the baseline's `model` field carries the
empty string because that is what the harness declares. Real-provider
numbers enter this document, if ever, by a re-freeze against a run that
actually ran the class — this one cannot be stretched to cover them.

## What the baseline does not establish

* **Nothing about a model's behaviour.** Every number here is a
  measurement of the repository's own tests over its own answer keys, run
  through the deterministic `FakeProvider`. A capability the phase gains
  against this baseline is a capability *the tests can see*, and no
  sentence in this document may be read past that.
* **No confidence intervals.** The deterministic metrics are exact over
  the committed keys; the latency figure is one reading of one machine.
  Phase 2's comparisons inherit this uncertainty, and work order row 2
  (the blind evaluation and ablation) is where measured significance is
  supposed to come from.
* **Three metrics not measured at all** — end-to-end task success,
  evidence-locator validity and revision consistency have no number here,
  so no claim about them can be "a gain over the baseline". Making those
  measurable is rows 5 and 6 of the phase's task list.
* **One test case of the unit class failed in the harness's environment**
  — `tests/test_analysis_service.py::test_the_seam_draws_a_real_figure_from_a_grouped_aggregate`
  (a `FileNotFoundError` under the harness's own base temp directory). It
  passes when run alone, in both runs it failed, and it does not enter any
  metric's numerator or denominator. It is recorded rather than rounded
  away.
* **Four skips that belong to this machine**: one integration case
  (`POSIX permission bits`) and three security-path cases (`the Windows
  drive form is meaningless on POSIX`; two refusals of the 8.3 short-name
  comparison, whose witness is the known short-name defect recorded for
  G5's T02 — *this machine's volume has no 8.3 short names*). A rate
  frozen on this machine carries those skips; a rate frozen on a runner
  may not.

## How a later comparison is drawn

```
python -m tests.evaluation --baseline docs/acceptance/LC-P2-00-baseline.json --out <dir outside the repository>
```

The harness reads the document, checks the basis against the run with
`assess`, and prints numbers **only when all six conditions hold**: the
tasks and their versions match, the model and the budget match, the
baseline declares the capabilities it verified, and it documents limits.
When it prints, it prints **pairs** — `84/84 against 82/84` — and nothing
that could be read as a winner; the rendered section has no aggregate
verdict to render, and `tests/test_evaluation_harness.py` watches that it
never grows one.

## The witnesses

`tests/test_baseline_document.py` watches the document, each test for the
failure it is shaped against:

* **The document loads** — `load_baseline` reads it, the basis declares no
  model, the capability list and the limitations are non-empty, and every
  metric entry carries an int numerator and a positive int denominator.
* **A run on this tree compares on all six conditions** — the run side is
  rebuilt the way the harness builds it (the committed answer keys hashed
  as the harness hashes them, the empty model and budget, the capabilities
  the run reported), and `assess` accepts it with no reasons. Editing an
  answer key without re-freezing the baseline fails this test.
* **A doctored run or baseline is refused** — each of the six conditions,
  broken one at a time on the side that checks it, returns a refusal with
  a reason. This is the work order's *"the refusal witnesses stay red
  against a doctored basis"*.
* **The commit is what the numbers belong to** — the document's run block
  names a commit; the answer keys of that commit, read out of git itself,
  hash to exactly the versions the document declares. A commit swapped for
  one the numbers never belonged to fails before any comparison is drawn.
* **The run block reports the offline run it was** — the capabilities are
  a proper subset of the harness's classes, the real-model smoke is not
  among them and is recorded NOT RUN, and the exit code is 2.

**The shard costs will go red on purpose.** A new test file is a new cost
no shard has measured, and the shard-cost witness fails until the costs
are re-measured on a runner (`python .github/remeasure_shards.py <run-id>`
at merge time, by the coordinator). This document does not carry that
edit.
