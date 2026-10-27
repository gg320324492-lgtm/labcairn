# G5 — Gate review, scope: product behaviour and measurement

**Gate:** G5 — the public alpha. Work orders **LC-P1-13** (evaluation, fault
injection and competitor baseline) and **LC-P1-14** (the public alpha handoff
and review dossier).
**Exit test:** *"outsider fresh install, 3 fixtures, fault injection, docs and
real-provider smoke."*
**Verdict:** **FAIL** — see [The verdict](#the-verdict).
**Reviewed against:** `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f`
**Reviewer:** the independent reviewer dispatched for **scope "product behaviour
and measurement"** (the answers, the crash, and the fresh install). **This
reviewer wrote no fix into this repository.** Every change described below was
made in a scratch state of the reviewer's own worktree and reverted; the only
file this review added to the tree is this one.

## Why this gate needed a review of its own

The board's rule (`docs/PHASE_1_WORKORDERS.md`) is that **a gate is closed only
when an independent review at a named commit says so**. G3 and G4 were closed
that way: a reviewer that wrote **none** of the gate's fixes broke each
property in turn and reported what survived.

**The commit this review measures is the gate's delivery, not a closed gate.**
At `72154cd` the board still reads `NOT STARTED` for LC-P1-13 and LC-P1-14,
and `CHANGELOG.md` describes G5 as *"in flight"* with five items open. This
review therefore says what the delivered work does and does not hold, so that
the gate can be closed on a tree that holds.

## The method — mutation checking

For every property the gate claims, the property's implementation is broken on
purpose, one at a time, and the tests that should catch it are run. **A
mutation that survives is a finding**: it means the property is *stated* but
*not watched*.

Three rules were held to, and they are the repository's own:

- **A mutation that changes nothing is not a mutation.** If the edit is a
  no-op, that is a finding about the test, not a survivor.
- **A mutation whose anchor did not match is not a survivor either.** It means
  nothing was tested. Every surviving mutation below has a **control** that
  must go red, and the control is reported with it.
- **The test's name is reported**, not "the suite went red". A suite that goes
  red for an unrelated reason proves nothing. One mutation below initially
  went red for a line-ending reason rather than the property under test; that
  run was discarded and the mutation was re-made with LF endings before the
  result was recorded.
- **A survivor is checked by hand before it is called a finding.** Every
  surviving mutation below carries a **control** that must go red (so the
  anchor matched), and F1's survivor was additionally driven step by step with
  the file's bytes printed at each step, so that the claim could be read
  rather than inferred.

The **narrow** attack was preferred to the broad one: *"can the answer key
being computed from the material be fooled by copying the product's own
output?"* was tried before *"can every fixture's locator resolve be fooled by
one bad locator?"*.

### The measurements were taken under this repository's rules

| Rule | How it was honoured |
|---|---|
| `--basetemp` outside the repository | `E:\labcairn-local\bt-g5-product\…`, a **different** directory per pytest run (pytest clears its base temp on the way in, so two runs must not share one) |
| one `TEMP`/`TMP`/`MPLCONFIGDIR` per process | `E:\labcairn-local\tmp-g5-product`; the harness makes a directory of its own under it per class and per process id |
| the worktree's own virtualenv | `uv sync --frozen` created `.venv` **in this worktree**; `labcairn.__file__` resolves to `…\agent-a4a95e5071effc6d9\src\labcairn\__init__.py` and the interpreter is the pinned 3.12.13 |
| the harness's report goes outside the tree | `E:\labcairn-local\tmp-g5-product\eval-run\` |
| status read from the command, not from a pipe | every run's exit status was read separately from its output |
| the upstream tree is not read | `../labcairn-upstreams/` was never opened; upstream observations were read only from `docs/UPSTREAM_REFERENCES.md` |
| no push, no pull request | none was made |

**The commit was confirmed before any measurement.** `git rev-parse HEAD` was
`72154cd27fc99005ab1ee22c6d5e58608e6b5b2f` at the start of the review and at
the end, and every number below was measured on that tree.

## What the gate's exit test required, and what I measured

The exit test has five items and the review was given seven clauses from
`docs/plans/LC-P1-13-14-task-breakdown.md` §4.1 and §4.2. The clauses and
their outcomes:

| # | The clause under review | Where it is claimed | What I measured |
|---|---|---|---|
| 1 | the three fixtures' answer keys are independent of the product; the negative fixture cannot be answered | `docs/acceptance/LC-P1-13-fixtures.md` §5 | **F2, F4** — the key can be the product's own output and the corpus still passes; the negative fixture *is* watched |
| 2 | every locator in the answer keys resolves | same, §4 | **held** — two named tests go red on one bad locator, and on all of them |
| 3 | the harness's denominators are real; a small denominator says so; no test file is in no class | `docs/acceptance/LC-P1-13-evaluation.md` §4–§5 | **F7, F8** — the partition holds; two narrower denominators do not |
| 4 | the protocol's blocking tests are not skipped | same, §6 | **held** — the blocker rule is watched, and the real run's blockers are reported honestly |
| 5 | the crash matrix covers "no repeated side effect" | `tests/test_recovery_crash_matrix.py` | **F1** — a surviving mutation: the recovery path may write and nothing notices |
| 6 | the forced restart continues the task | `tests/test_recovery_resume.py`, `scripts/outsider_path.py` | **held** — two named tests go red |
| 7 | the outsider's path really runs in a clean clone | `scripts/outsider_path.py` | **held** — two refusals by name |

### The gate's own numbers, measured at `72154cd`

`python -m tests.evaluation --out E:\labcairn-local\tmp-g5-product\eval-run`
(one command, the harness's own; **exit code 2**):

| Class | Files | Passed / collected | Skipped | Rate |
|---|---:|---:|---:|---:|
| Unit | 46 | 1510 / 1511 | 1 | 0.999 |
| Integration | 29 | 1131 / 1134 | 3 | 0.997 |
| Negative | 19 | 361 / 364 | 3 | 0.992 |
| E2E | 3 | 102 / 102 | 0 | 1.000 |
| Real-model smoke | 0 | **NOT RUN** | — | — |
| Repository gates | 11 | 368 / 368 | 0 | 1.000 |

**3479 collected, 3472 passed, 7 skipped, 0 failed.** Every collected case
entered exactly one class's denominator, and the class denominators sum to the
run's total — the partition holds in the run as well as on the page.

| Phase 1 blocker | Status | Why |
|---|---|---|
| New user cannot complete a task from a clean environment following README | **FAILED** | two skipped witnesses in `tests/test_earlier_exit_demos.py` — **F3** |
| Any unauthorized file write/escape or unconsented private-network disclosure | **FAILED** | three skipped witnesses in `tests/test_security_paths.py` |
| Fake citation presented as verified or unsupported numerical fact presented as measured | HELD | every witness collected and passed |
| A crash silently repeats unknown file side effects | HELD | every witness collected and passed — **but see F1** |
| Report claims a verified scientific result based solely on schema or rendering checks | HELD | every witness collected and passed |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance | HELD | every witness collected and passed |

| Metric | The protocol's value | The witnesses' score |
|---|---|---|
| End-to-end task success | **NOT MEASURED** | 114 / 116 |
| Evidence locator validity and citation support precision | **NOT MEASURED** | 145 / 145 |
| Numeric-cell extraction exactness and unit consistency | **84 / 84** (also 77 / 77, 14 / 14) | 256 / 256 |
| Unsupported-claim detection and appropriate abstention | **NOT MEASURED** | 34 / 34 |
| Revision consistency | **NOT MEASURED** | 126 / 126 |
| Recovery correctness / duplicate side effects | **8 / 8** — *"yes — the denominator is 8, under 10"* | 40 / 40 |
| Latency, model usage/cost | 1912688 / 3479 | 47 / 47 |

### The rest of the tree, measured at `72154cd`

| Run | Result |
|---|---|
| `tests/test_public_fixtures.py` + `tests/test_evaluation_harness.py` + `tests/test_recovery_crash_matrix.py` | **89 passed** |
| `tests/test_outsider_path.py` (on a tree confirmed clean) | **16 passed** in 179 s |
| the whole suite, via the harness above | 3472 passed, 7 skipped, 0 failed |

## The findings

Each finding names the mutation, the tests that went red by name, and — for
every survivor — the **control** that shows the mutation reached the mechanism
rather than missing it.

---

### F1 — the crash matrix does not watch whether the recovery path performs a side effect

**Severity: high. It sits directly under the protocol's fourth blocker.**

`src/labcairn/recovery/probes.py` says of itself:

> **Read-only. Never creates, writes, truncates or removes anything.**
> A probe that repaired as it went would be a second writer on the exact path
> where a second writer is most expensive.

`tests/test_recovery_crash_matrix.py`'s AT2b says:

> One write total, from the original counter: reconciliation rewrote nothing.
> … a probe that rewrote the file would leave a receipt

**Neither claim is watched.** The mutation: make the probe **write the file**
when it finds it absent, and keep its verdict.

```python
if not present:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"repaired by the probe\n")
    return ProbeVerdict(resolution=ReconciliationResolution.REPLAY_SAFE, …)
```

**Result — the mutation survives.**

| Run | Result |
|---|---|
| `test_recovery_crash_matrix.py`, `test_store_atomicity.py`, `test_recovery_resume.py`, `test_recovery_approvals.py` (the protocol's fourth blocker's own witnesses) | **40 passed** |
| the same plus `test_recovery_support.py`, `test_recovery_stage_bridge.py`, `test_store_persistence.py` | **51 passed** |

**The control, so the survivor is not a missed anchor.** The same probe, writing
*and* claiming `CONFIRMED`, goes red:

> `tests/test_recovery_crash_matrix.py::test_at5_reconciliation_detects_absent_write` —
> `AssertionError: assert <ReconciliationResolution.CONFIRMED> is <ReconciliationResolution.REPLAY_SAFE>`

So the probe's absent branch **is** reached in AT5, and the probe's *verdict*
is watched. What is not watched is **the write**.

**Why it matters, and why the counter cannot see it.** The matrix's evidence
is `WriteCounter`, and `WriteCounter.calls` counts `effect.apply()`
invocations only (`tests/test_recovery_support.py:109`). A recovery path that
writes the file *directly* is invisible to it. AT5 is the case that should
catch exactly this — it crashes *after the intent, before the write*, so the
file must be absent, reconciliation must conclude `REPLAY_SAFE`, and the
replay must be the first and only write. AT5 asserts `counter.calls == 1`
("replay is the first and only write") and **never asserts that the file is
absent after the reconciliation**. So the sequence

> probe writes `outputs/report.md` → reconciliation says `REPLAY_SAFE` → the
> replay writes it again

is a **repeated side effect performed by the recovery path**, exactly the shape
the protocol's fourth blocker forbids, and **the matrix does not notice**. The
probe's write also puts *wrong bytes* at the path for as long as it takes the
replay to land.

**Nothing else in the tree watches it.** `grep` over `tests/` finds
`FileSystemProbe` used only by `tests/test_recovery_support.py` (the scenario
helper) and the crash matrix; there is no test of the form "the probe does not
write". And the harness reports the protocol's fourth blocker as **HELD** on
the strength of that matrix.

**The survivor was checked by hand, and the claim really was unearned.** AT5's
own scenario was driven step by step, printing what was on disk at each step —
once on the committed tree and once with the mutation:

| | the committed tree | with the mutation |
|---|---|---|
| after the crash, the file exists? | `False` | `False` |
| **after the reconcile**, the file exists? | **`False`** | **`True`** — and its bytes are `b'repaired by the probe\n'` |
| the write counter's calls | 0 | **0** |
| the replay's outcome | `confirmed`, counter **1** | `confirmed`, counter **1** |
| the file's bytes at the end | `b'# Findings\n\nThe observation holds.\n'` | `b'# Findings\n\nThe observation holds.\n'` |

So the file was written **twice** — once by the recovery path, with the wrong
bytes, and once by the replay — the counter recorded **one** write, the
verdict said `replay_safe`, and **the matrix's forty witness cases were
green**. That is the protocol's fourth blocker, unheld.

**How to reproduce.** Apply the mutation above to
`src/labcairn/recovery/probes.py`, then run:

```
uv run pytest tests/test_recovery_crash_matrix.py tests/test_store_atomicity.py \
    tests/test_recovery_resume.py tests/test_recovery_approvals.py
```

**What fixing it looks like.** A witness that asserts the file is **absent**
after a `REPLAY_SAFE` reconciliation (AT5's own precondition), and one that
asserts the probe left the tree byte-identical (a digest of the workspace
before and after `reconcile`). Either would have caught this mutation by name.

---

### F2 — the public fixture corpus is not an oracle: nothing compares a report with its answer keys

**Severity: high. It is the gate's headline deliverable, and it discharges nothing.**

The protocol asks for fixtures that *"have actual source locators, hashes and
answer keys; do not use generated outputs as their own oracle"*, and the
work order's acceptance (LC-P1-14 clause 2) asks that *"the canonical task is
a fixture with an answer key, and **the reproduced report's answers are
compared with the key**"*.

**Measured: no produced report is ever compared with any public fixture key.**

| Search over the tree (excluding `docs/`) | Where it lands |
|---|---|
| `expected_artifact_checks`, `no_fabricated_value`, `citation_resolves`, `number_present`, `abstains` | `tests/test_public_fixtures.py` and `tests/fixtures/public/MANIFEST.json` — **nowhere else** |
| `fixtures/public`, `MANIFEST.json`, `public-fixtures` | `tests/test_public_fixtures.py` — **nowhere else** |
| the harness's corpus measurement | `tests/evaluation/corpus.py:217` reads **`tests/fixtures/analysis/*.expected.json`** — the *other* corpus |
| the outsider path's research folder | `scripts/outsider_path.py:1074,1080` reads **`tests/fixtures/papers/*.pdf`** and **`tests/fixtures/analysis/groups.csv`** — again the other corpus |

So the four public fixtures' `expected_artifact_checks` — the `abstains`, the
`no_fabricated_value`, the `number_present`, the `citation_resolves` — are read
by one test file, and that test file checks them against **each other and
against the material**, never against a report the product produced.

**The consequence is visible in the harness's own report**, and it is a
measurable one: the protocol's metric *"unsupported-claim detection and
appropriate abstention"* is reported **NOT MEASURED**, and the reason the
report prints is

> the tree holds **no no-evidence fixture to abstain over**, so the numerator
> would count nothing.

**`tests/fixtures/public/no_evidence/` is in this tree**, and the fixture
record says outright that this fixture is the one that *"makes abstention
measurable"*. The metric is unmeasured because the harness measures the wrong
corpus — not because the input is missing.

**How to reproduce.**

```
git ls-files tests/fixtures/public
grep -rn "expected_artifact_checks" --include=*.py . | grep -v test_public_fixtures
grep -rn "fixtures/analysis" tests/evaluation/corpus.py scripts/outsider_path.py
```

**What fixing it looks like.** Either the harness's corpus measurement reads
`tests/fixtures/public/MANIFEST.json` as well, or the outsider path binds a
public fixture as its research folder and compares the produced report's
answers with that fixture's key. Until one of those happens, the corpus is a
**well-witnessed set of materials**, and the protocol's abstention metric has
nothing to measure against.

---

### F3 — the protocol's **first** blocker reports FAILED at this commit because of a skip whose defect is fixed

**Severity: high. It is the gate's own exit-test item, and the reason it gives is no longer true.**

The harness reports *"New user cannot complete a task from a clean environment
following README"* as **FAILED**, and the two witness cases that did not pass
are the two `tests/test_earlier_exit_demos.py` cases that skip G1's exit
demonstration on Windows:

> g1_exit_demo is skipped on Windows until the product's 8.3 short-name
> comparison is fixed — docs/plans/LC-P1-13-14-task-breakdown.md section 2.6

**The defect is fixed at this commit.** Measured, not read off a record:

| Measurement | Result |
|---|---|
| `git merge-base --is-ancestor 6220a08 HEAD` (`6220a08` = *"A new file under a short-spelled root is under the root"*) | **it is an ancestor of `72154cd`** |
| the product's own path layer, a **new** file declared with the **short** spelling under a short-spelled root, on a volume that has 8.3 names (`C:\Users\pc\AppData\Local\Temp` → `A-VERY~1`) | **accepted**, key `outputs/summary.md` — the defect's shape is REFUSED no more |
| the same probe on the `E:` volume | NOT MEASURED — that volume generates no 8.3 short names, which is why the repository's own tests skip there |
| **the skip removed** (`KNOWN_DEFECT_ON_WINDOWS` emptied) and `tests/test_earlier_exit_demos.py` run | **6 passed** — G1's, G2's and G2-uncertain demonstrations all hold on Windows at this commit |

So the skip is **stale**, and its own comment says why it is there: *"It is
G5's first piece of work"*. The fix landed; the skip did not.

**Why it matters.** A skip in a blocker witness fails the blocker, by the
harness's own rule — which is the right rule. But here it makes the gate's
own exit-test item fail **for a reason that has been fixed**, and it does so
on **every Windows runner**, because the skip is conditioned on
`os.name == "nt"` and not on the defect being present. The harness is
reporting a truth about *the tree* and a falsehood about *the product*.

**How to reproduce.** Remove the two `pytest.skip` guards (or empty
`KNOWN_DEFECT_ON_WINDOWS`) in `tests/test_earlier_exit_demos.py` and run that
file: **6 passed**. Then read the harness report's blocker row: it becomes
**HELD**.

**What fixing it looks like.** Delete the skip, and let the two 8.3 witnesses
in `tests/test_security_paths.py` — which skip on *this* volume for a
machine reason and would run on a runner — carry the property they were
written for.

---

### F4 — the answer key's independence from the product is not witnessed: a key that *is* the product's own output passes every check

**Severity: medium. The protocol forbids exactly this and nothing watches.**

`docs/acceptance/LC-P1-13-fixtures.md` §5 is headed **"The answer key is not
the product's own output"**, and the protocol's fixture clause says *"do not
use generated outputs as their own oracle"*.

**The witness re-derives the key with the product's own machinery** — the
tabular answers through `labcairn.analysis.operators.descriptive.MEAN`, the
prose answers through `labcairn.sources.quantity.read_number`. So the check
establishes that **the key agrees with the product's reading of the
material** — which is exactly what a key copied out of the product's output
also satisfies.

**The mutation, in two steps.**

1. Break the product's mean: `statistics.fmean(values)` →
   `statistics.fmean(values[:-1])` in
   `src/labcairn/analysis/operators/descriptive.py`.
2. Recompute the three tabular answers with the product's own machinery and
   write them into `MANIFEST.json` (and into the matching `number_present`
   checks): `412.0 → 415.45`, `7.68 → 7.62`, `0.000374 → 0.0003625`.

**Result — the corpus is green.**

```
tests/test_public_fixtures.py  →  41 passed
```

**The control, so the survivor is not a missed anchor.** The same broken
operator is caught by **13 tests elsewhere** in the tree — including
`tests/test_evaluation_harness.py::test_the_corpus_measurement_reports_no_failure`
and `tests/test_analysis_descriptive.py::test_the_operators_compute_what_the_corpus_says[basic.csv]`
— because the *other* corpus (`tests/fixtures/analysis/*.expected.json`) was
computed with Python's `statistics`, *"an implementation that is not
LabCairn's"*. So the **product** is protected and the **public corpus** is
not: the corpus whose key is supposed to be independent has no independent
witness, and the corpus that has one is not the gate's new one.

**What is and is not true here.** The corpus's *material*, *hashes* and
*locators* are strongly witnessed — see the mutation table below. What is not
witnessed is the one thing the protocol names: that the key is not the
product's own output. The fixture record's own §9 limit 1 says the key and the
witness *"both use the product's own reading of the material"*, which is
closer to the truth than the §5 heading is; but the limit as written is about
*a shared misreading*, and the thing measured here is stronger: the key can be
**the product's output verbatim** and every check in the file passes.

**A note on `test_a_corrupted_answer_key_is_caught`.** The record presents it
as one of the two *"permanent tests"* that keep the corpus from losing the
mutation. It is not a tautology — its final assertion does compare the
material's value with the key — but **the corruption step is inert**: the
corrupted key is never fed through any checking code, because the test
recomputes the material's value a second time and compares *that* with the
corrupted key. So it re-witnesses what
`test_the_tabular_answers_are_re_derived_by_the_products_own_operator`
already witnesses, and it goes red under a corrupted manifest **at its
precondition** (line 1102, *"the untouched answer does not agree with the
material"*), not at the corruption check.

**How to reproduce.**

```
# 1. break the operator
#    src/labcairn/analysis/operators/descriptive.py:
#      statistics.fmean(values)  ->  statistics.fmean(values[:-1])
# 2. recompute the three tabular answers with the product's own machinery and
#    write them (and their number_present checks) into
#    tests/fixtures/public/MANIFEST.json
uv run pytest tests/test_public_fixtures.py      # 41 passed
```

**What fixing it looks like.** Re-derive at least one answer per fixture with
an implementation that is not the product's — `statistics.fmean` over the
material's own cells, the way the analysis corpus's key was computed — so the
key and the witness cannot share a bug.

---

### F5 — the fault injection **through the surfaces** — one of the gate's five exit-test items — is not delivered

**Severity: medium. It is declared, so it is a scope fact rather than a defect,
but it is a gate item.**

The breakdown's §2.3 is explicit about what G5 adds over what G1 and G2 left:

> **What G5 adds is the surfaces.** The matrix is tested at the layer; G5's
> fault injection runs a crash **through the CLI and the service**, with the
> task's state on disk, and shows that the surfaces come back to a state the
> user can reason about: no repeated operation, no duplicated side effect, and
> the report either regenerated from the recovered state or refused with a
> reason.

and §3 gives T02 the file `tests/test_fault_injection_e2e.py`.

**Measured: that file does not exist, and no test injects a crash through the
CLI or the service.** `grep -rln "CrashPoint|InjectedCrash" tests/ scripts/
examples/ src/` returns `tests/test_recovery_crash_matrix.py`,
`tests/test_recovery_support.py`, `examples/g2_uncertain_demo.py` and the
recovery package itself — **all at the layer**.

The delivery says so itself, in `CHANGELOG.md`:

> **Still open in this gate** — and named rather than glossed: the fault
> injection run **through the surfaces**, and the two exit demonstrations that
> were run by nothing

The second half of that line is closed — `tests/test_earlier_exit_demos.py`
now runs both demonstrations — and the first half is not.

**Why it matters.** "fault injection" is one of the board's five exit-test
items. The matrix itself is real, tested and (subject to **F1**) honest about
what it covers; what is missing is the half that puts the crash through the
surfaces the gate's exit test names.

---

### F6 — the harness prints two reasons that are false at the commit it measures

**Severity: medium. A report that says a false thing about its own tree is
the report's whole failure mode.**

`tests/evaluation/aggregate.py::NOT_MEASURED_REASONS` carries two strings that
the report prints **verbatim** under two metrics. At `72154cd` both are false:

| The report prints | The truth at `72154cd` |
|---|---|
| *"The public fixtures that would be that corpus are LC-P1-13 T00's deliverable and **are not in this tree**."* | they are: `tests/fixtures/public/` holds `MANIFEST.json` and eight material files |
| *"the tree holds **no no-evidence fixture to abstain over**, so the numerator would count nothing."* | it holds one: `tests/fixtures/public/no_evidence/` |

Both reasons were true when the harness was written and were carried forward
past the merge that delivered the fixtures. **A reason that says an input is
missing when the input is present and unused is worse than a missing reason**:
it tells a reader that a measurement is impossible when the real reason is that
nothing measures it (F2).

The record `docs/acceptance/LC-P1-13-evaluation.md` has the same lag: its
status line reads *"the work order is **NOT STARTED**"*, its numbers were
measured at `37ae3663` rather than at the gate commit, and its §11 says the
partition *"is now 103 files"* where it is 108.

---

### F7 — an unmarked test file can be moved into a protocol class and the protocol's denominator silently grows

**Severity: medium.**

The harness's rule is that the repository's own gates *"are not one of the
protocol's five mandatory gate classes, so they are counted apart from them"*,
and that counting them in *"would inflate that class's denominator with checks
the protocol never asked for"*.

**The partition is complete and the rule that protects the classification only
covers files that declare a marker.** Two mutations:

| Mutation | Result |
|---|---|
| remove `test_public_fixtures.py` from the partition | **RED** — `test_the_partition_files_every_test_file_exactly_once` |
| move `test_public_fixtures.py` (declares `unit`) into `repository` | **RED** — `test_the_partition_agrees_with_the_markers_a_file_declares` |
| **move `test_review_dossier.py` (declares no marker) from `repository` into `unit`** | **40 passed — the mutation survives** |

With the third mutation, the protocol's own "Unit" class denominator gains
`test_review_dossier.py`'s cases — checks the protocol never asked for — and
the report's "Repository gates" row shrinks, and **nothing goes red**.

**The control.** The third mutation is not a missed anchor: the file is
genuinely filed (the partition test passes), genuinely declares no marker (so
the marker rule has nothing to say), and its clause (`typed-contracts`) is in
the vocabulary (so the clause test passes). The partition's own docstring
records the limit — *"Where a file declares no marker, the classification is a
judgement"* — and the record's §10 repeats it. What the limit does not say is
that the judgement is **silent in both directions**, and that one of the two
directions contradicts a rule the harness states in its own report.

**How to reproduce.**

```
# tests/evaluation/manifest.py
#   "test_review_dossier.py": (REPOSITORY_CLASS, "repository-gate"),
# becomes
#   "test_review_dossier.py": ("unit", "typed-contracts"),
uv run pytest tests/test_evaluation_harness.py     # 40 passed
```

**What fixing it looks like.** A witness that the `repository` class holds
**only** files whose clause is `repository-gate`, and that no protocol class
holds one.

---

### F8 — the report's "small denominator" note is never rendered, and nothing notices

**Severity: low.**

The protocol asks for *"transparent denominators"*, and the harness's own
docstring says *"A **small denominator is said out loud**, in the row,
because a rate over four cases and a rate over four hundred are not the same
claim."*

**The mutation:** make `tests/evaluation/report.py::_small` return `""`
always.

**Result — 40 passed, the mutation survives.** The model property
(`Measurement.denominator_is_small`) is watched by
`test_a_small_denominator_is_said_so`, and `grep` over `tests/` finds the
rendered text (`"yes — the denominator is 8, under 10"`) **nowhere**. The same
is true of the class row's own small-denominator note.

This is the shape the harness's own file already warns about elsewhere — *"The
watch is on the **rendered** text, not on the intent"* — applied to a second
rendered text that has no watch.

---

### F9 — the board says LC-P1-13 and LC-P1-14 are `NOT STARTED` at the commit that delivers them, and the watch cannot see it

**Severity: low.**

`docs/PHASE_1_WORKORDERS.md` reads:

```
| LC-P1-13 | P0 | G5 | NOT STARTED | |
| LC-P1-14 | P0 | G5 | NOT STARTED | |
```

**The declared vocabulary has a status for this** — `Status vocabulary:
NOT STARTED · IN PROGRESS · PASS · PASS WITH NOTES · BLOCKED · FAIL` — and the
gate's own `CHANGELOG.md` calls G5 *"in flight"* while delivering six of the
nine subtasks in this very commit.

**The watch that is supposed to notice cannot.** `tests/test_status_consistency.py::test_a_not_started_work_order_has_no_merged_work`
matches on **merge-commit subjects**, on the reasoning that the branch
convention (`feat/lc-p1-08-…`) puts the work-order id in the subject. The G5
delivery's merge subjects are:

```
Merge pull request #116 from gg320324492-lgtm/delivery/g5
Merge pull request #115 from gg320324492-lgtm/delivery/g5-first-four
```

Neither contains `lc-p1-13` or `lc-p1-14`, so **the witness passes while the
row is stale**. The same sentence is in
`docs/plans/LC-P1-13-14-task-breakdown.md` line 5 (*"the work orders are
**NOT STARTED**"*), which is one of G5's own deliverables.

**How to reproduce.**

```
git log --merges --format="%s" | grep -i "lc-p1-1[34]"   # no output
grep -n "LC-P1-1[34]" docs/PHASE_1_WORKORDERS.md        # NOT STARTED
```

---

### F10 — the recovery metric's denominator is labelled as a thing it does not count

**Severity: low.**

`tests/evaluation/aggregate.py::_recovery_measurement` reports `8 / 8` and
says what the denominator counts:

> the fault-injection scenarios the crash matrix ran, over the scenarios it
> holds; **one collected test case is one injected fault**

**Measured in `tests/test_recovery_crash_matrix.py`:** 8 collected test cases,
**10 injected faults** (7 in-process `arm(CrashPoint.…)` calls plus the 3
subprocess kills AT7 performs), of which **4** are distinct `CrashPoint`
values. Two of the eight cases — AT2b and AT3b — re-run an earlier fault
rather than injecting a new one.

So 8 is neither the number of injected faults nor the number of distinct
faults; it is the number of test functions. The protocol asks for denominators
whose unit is stated, and this one states a unit that is wrong.

The matrix's *coverage* is complete at the layer — all four `CrashPoint`
members are injected somewhere in the file — and that is the fact the metric
should be counting.

## The mutation table

Every mutation below was applied to the tree at `72154cd`, the named tests were
run alone, and the tree was restored. **The survivors are checked by hand and
each carries a control.**

| # | The mutation | What went red | Killed? |
|---|---|---|---|
| M1 | one fixture's citation points at a line that does not exist (`l=2:15` → `l=2:99`) | `test_every_cited_locator_resolves_to_the_text_the_manifest_expects[physical_tension]`, `test_the_prose_answers_are_re_derived_from_the_resolved_text` | **yes** |
| M2 | every fixture's citation points at an address that is not there | all four `…resolves_to_the_text…` cases + `test_the_prose_answers_are_re_derived_from_the_resolved_text` | **yes** |
| M3 | `tension.mean_peak_stress_b2`'s answer `412.0 → 999.0` (the check left alone) | `test_the_tabular_answers_are_re_derived_by_the_products_own_operator`, `test_every_number_present_check_matches_its_question_s_answer`, `test_a_corrupted_answer_key_is_caught` | **yes** |
| M4 | the same answer **and** its `number_present` check changed together | `test_the_tabular_answers_are_re_derived_by_the_products_own_operator`, `test_a_corrupted_answer_key_is_caught` | **yes** |
| M5 | the product's mean broken **and** the three tabular answers replaced by the product's new output | *nothing* — **41 passed** | **NO — F4** (control: the same broken operator is caught by 13 tests elsewhere) |
| M6 | `a pH of 7.2` written into the negative fixture's prose (LF, hash re-recorded) | `test_the_negative_fixture_really_does_not_answer_the_question`, `test_the_negative_fixture_states_no_ph_value_while_naming_the_quantity` | **yes** |
| M7 | a test file removed from the partition | `test_the_partition_files_every_test_file_exactly_once` | **yes** |
| M8 | a marker-declaring file moved to the wrong class | `test_the_partition_agrees_with_the_markers_a_file_declares` | **yes** |
| M9 | an **unmarked** file moved from `repository` into the protocol's `unit` class | *nothing* — **40 passed** | **NO — F7** (control: the file is filed, declares no marker, and its clause is in the vocabulary) |
| M10 | the rendered "small denominator" note removed | *nothing* — **40 passed** | **NO — F8** (control: the rendered text exists today and appears in no test) |
| M11 | a skipped witness counted as a pass | `test_a_skipped_witness_fails_its_blocker` | **yes** |
| M12 | **the probe writes the file** when it finds it absent (verdict unchanged) | *nothing* — **40 passed** (51 with three more recovery files) | **NO — F1** (control: the same probe claiming `CONFIRMED` turns `test_at5_reconciliation_detects_absent_write` red; hand-check: the file exists with `b'repaired by the probe\n'` after the reconcile, and the counter still says 0) |
| M13 | `plan_resume` treats a checkpoint whose material moved as still verifying | `test_resume_refuses_to_skip_a_stage_whose_material_moved`, `test_a_deleted_source_fails_the_verification` | **yes** |
| M14 | an extra file planted in the clone | the script's own check: *"the clone's working tree is clean"* — exit 1 | **yes** |
| M15 | the walk run under the developer's interpreter | the script's own check: *"the walk runs the clone's own code, not the developer's"* — exit 1 | **yes** |
| M16 | the `KNOWN_DEFECT_ON_WINDOWS` skip removed | *nothing* — **6 passed** (the skip was stale) | the skip is the defect — **F3** |

**One discarded run, and why.** An earlier form of M6 wrote the mutated
material with `Path.write_text`, which on this platform translated the line
endings to CRLF. The run went red with **four** failures — two of them
(`test_every_material_file_is_byte_identical_to_its_recorded_hash[no_evidence]`
and `test_no_material_file_carries_a_carriage_return[no_evidence]`) from the
line-ending artefact and not from the property under test. **That run was
discarded**, the material was rewritten as raw bytes with LF endings, and M6
was re-measured. The two reds reported above are the clean ones.

## What I did not test, and why

- **The real-model smoke.** It needs a real provider's credential and spends
  money, and §1.4.2 of the breakdown makes both the owner's decision. **NOT
  MEASURED.** The harness reports the class as **NOT RUN** with the reason and
  exits **2**, which is the honest outcome; I did not supply a credential.
- **The competitor baseline (T09).** Not delivered in this tree, and the
  protocol's rule forbids a comparison that is not like-for-like, so there was
  nothing to measure.
- **The README's six `pnpm` commands.** The outsider path runs in **witness**
  mode, which *records* the web commands as not runnable rather than running
  them (the script's own output says so: *"the web package's commands are the
  web-quality workflow's job, and this is the witness mode; the reviewer mode
  runs them"*). Node 24.16.0 and pnpm **are** available on this machine, so
  the reviewer mode would have run them; I did not run it, because the
  reviewer mode also runs the whole suite and would have recursed into the
  suite that runs it. **NOT MEASURED** for the web half of LC-P1-14 clause 4.
- **The 8.3 short-name property on this volume.** The `E:` volume generates no
  8.3 short names, so `tests/test_security_paths.py`'s two 8.3 witnesses skip
  here. I measured the property directly against `C:\Users\pc\AppData\Local\Temp`,
  which does have them, and against the product's own `canonicalize`.
- **The documents, the NOTICE, the release contents, the review dossier and
  the font licence audit (T06–T08).** These are outside the clauses this
  review was given (§4.1 and §4.2, product behaviour and measurement) and
  outside the brief's seven items.
- **The whole suite as one serial pytest run.** The harness ran it as six
  class-scoped subprocesses, which is the project's own way of running it; the
  numbers in this report are the harness's, and they sum to 3479 collected.
- **The two mutations I could not run end to end.** M14 and M15 were run as
  the script rather than through `tests/test_outsider_path.py`, because the
  script refuses at the point of the defect and the test's own assertions are
  on the report the script writes. The refusal is the script's own, by name.

## What I recommend fixing

**I wrote none of it.** In severity order:

1. **F1.** Add a witness that the file is **absent** after a `REPLAY_SAFE`
   reconciliation (AT5's own precondition), and one that asserts the probe
   left the workspace byte-identical. Without one, the protocol's fourth
   blocker is HELD on a matrix that does not watch it.
2. **F2.** Make the harness measure `tests/fixtures/public/` — either by
   extending `tests/evaluation/corpus.py` to the public manifest, or by
   binding a public fixture in the outsider path and comparing the produced
   report with that fixture's key. Until then the corpus is an input, not an
   oracle, and LC-P1-14 clause 2 is not discharged.
3. **F3.** Delete the skip in `tests/test_earlier_exit_demos.py`. The defect
   it names is fixed at this commit, and the six cases pass on Windows
   without it. The protocol's first blocker then reports **HELD**, honestly.
4. **F4.** Re-derive at least one answer per fixture with an implementation
   that is not the product's, the way `tests/fixtures/analysis/*.expected.json`
   was computed with Python's `statistics`.
5. **F6.** Make the two `NOT_MEASURED` reasons **derive** their input
   statement from the tree rather than from a string — the same discipline
   `tests/evaluation/protocol.py` applies to the protocol itself, which is
   read at run time precisely so that a copy cannot go stale silently.
6. **F7.** Add a witness that the `repository` class holds only
   `repository-gate` files, so a repository gate cannot be moved into a
   protocol class without notice.
7. **F8.** Watch the **rendered** small-denominator note, as the rendered
   winners-language note is already watched.
8. **F9.** Put LC-P1-13 and LC-P1-14 on the board as `IN PROGRESS` with their
   evidence, and widen the status watch so a delivery branch that names the
   gate rather than the work order cannot hide behind it.
9. **F10.** Say what the recovery denominator counts — injected faults, or
   distinct crash points — and count that.
10. **F5** is a scope decision rather than a fix: the fault injection through
    the surfaces is one of the gate's five exit-test items, and either it is
    delivered before the gate closes or the exit test says in those words
    that it was not.

## The verdict

**FAIL.**

**One sentence.** The tree's product behaviour is largely sound and its
witnesses are unusually careful, but **the crash matrix does not watch whether
the recovery path performs a side effect** (a hole directly under the
protocol's fourth blocker, which the harness's own report calls HELD), **the
public fixture corpus is not an oracle for anything** (no produced report is
compared with any of its answer keys, and the protocol's abstention metric is
unmeasured for a reason the report states falsely), and **the protocol's first
blocker reports FAILED at this commit because of a skip whose defect this gate
already fixed**.

**Why not PASS WITH NOTES.** G4's own record is the precedent, and it is the
right one here: **five FAILs, then a pass**, and every one of the five failed
on a property table that was entirely clean. The shape this review found is
the shape that record is about — *a property table can be entirely clean and
the review still fail*. Three of the seven clauses in scope are held by named
tests that go red when the property is broken; **one of the remaining four is
not watched at all** (F1), and one is watched only in the part that is not the
claim (F4, and F7/F8 in the same shape). A note is for a limit the review
confirms; these are properties the gate states and the tree does not hold.

**Why not BLOCKED.** BLOCKED is for a review that could not be done — the
material was not there, or the gate could not be measured. **Everything in
scope was measured**: the corpus was re-derived, the locators were broken, the
partition was broken, the blocker rule was broken, the crash matrix was broken,
the resume was broken, the clone was broken, and the harness was run end to
end. The review reached a verdict, and the verdict is a negative one.

**What would move it.** F1, F2, F3 and F4 are the four that carry the verdict.
Fixing them is a small, well-specified piece of work: one witness for the
probe's silence, one measurement of the public corpus, one deleted skip, and
one independent re-derivation. **F5** is then a scope decision for the owner,
and **F6–F10** are the record's own lag.

**And the gate's own exit test still has two items that are not discharged at
this commit**, both named in the delivery itself and neither hidden: the
**real-provider smoke** (NOT RUN, exit code 2, the owner's credential) and the
**fault injection through the surfaces** (F5). A gate closed on this tree
would close on an exit test that says five items and delivers three.

---

*Measured on `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f` by the independent
reviewer for G5's product-behaviour-and-measurement scope, in a worktree of
this repository, on Windows 11 (AMD64) with Python 3.12.13. This reviewer
wrote no fix into this repository; every mutation above was reverted, and the
only file this review added is this one.*
