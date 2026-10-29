# LC-P1-13 — The evaluation harness, and what it measured

**Work order:** LC-P1-13 (evaluation, fault injection and competitor
baseline) · **Subtask:** T01 — the evaluation harness.
**Status of the work order:** **NOT STARTED**, and this document does not
change that. It records the harness, what it measured, and what the
protocol still asks for.
**Measured:** 2026-10-25 on the tree at `37ae3663d28555b6b760416f10630a81b3ec1ecb`, on Windows 11 (AMD64), Python 3.12.13, by
`python -m tests.evaluation --out E:\labcairn-local\evaluation-t01`.

**What this is.** `docs/EVALUATION.md` is the protocol this gate measures
against, and it is a document: it names five mandatory automated gate
classes, seven metrics to report with denominators and failure cases, and
the Phase 1 blockers. **Nothing in the repository ran it.** This is the
thing that runs it — one command, and a report in which every number
carries its denominator.

**And the headline, before anything else:** the protocol is **not
satisfied** by this tree, and the report says so rather than rounding it
up. **Three** things are unmet, and they are three different kinds of
thing:

1. **The real-model smoke class was not run.** It needs *"at least one
   real supported provider under declared model/version/parameters"*,
   there is no credential for one, and **mock-only success is
   insufficient under the protocol**. The harness reports the class as
   **NOT RUN** with the reason, and does **not** count it as a pass: a
   class that was not run has no rate, and a rate of zero would say
   *"every case failed"*, which is a different fact.
2. **One of the six Phase 1 blockers did not hold, in that run.** The one —
   *"A new user cannot complete a task from a clean environment following
   README"* — because the base branch's own witness skipped G1's exit
   demonstration on Windows while the product's 8.3 short-name comparison
   was unfixed. **That was that tree's state, and it was a finding rather
   than a defect of the harness.** *The defect was fixed and the skip was
   removed, so the first blocker holds now; **the table the gate closes on
   is below**, and it is this row that has changed.*
3. **Four of the seven metrics were not measured**, and each says which
   input is missing.

The command therefore exits **2** — a code that means *"a selected class
could not be run"*, not *"the tool failed"*.

---

## 1. The one command

```
python -m tests.evaluation --out <directory>
```

It runs the protocol's gate classes, reads pytest's own JUnit XML for the
outcomes, measures what else it can measure, and writes **two renderings
of one run**:

| File | What it is for |
|---|---|
| `<out>/evaluation-report.md` | what a reviewer reads |
| `<out>/evaluation-report.json` | what a later run or a comparison reads |

They are rendered from the same run object and **neither is derived from
the other**, so a bug in one does not quietly become a fact in the other.

**The exit codes**, and what each one means:

| Code | Meaning |
|---|---|
| `0` | every **selected** class ran, every case passed, and every Phase 1 blocker held |
| `1` | a case failed, errored or was skipped, or a blocker did not hold |
| `2` | a **selected** class could not be run |

**The other options:** `--classes a,b,c` narrows the selection (the exit
code then speaks only about what was selected); `--baseline <file>` offers
a baseline document to compare against; `--list` prints the partition and
exits without running anything; `--timeout <s>` bounds one class.

**Where the report goes.** Outside the repository by default, under the
system's temporary directory. The repository's own rules are that runtime
artefacts do not live inside the checkout, and a harness that wrote its
report into the tree it measures would dirty the tree it measures.

---

## 2. The protocol is read, not restated

The harness **parses `docs/EVALUATION.md` at run time**. It does not carry
a copy of the protocol's list, because a copy goes stale the moment the
protocol changes and it goes stale *silently* — the copy keeps answering,
and the answer is about a protocol that is no longer the one in force.

What the parser found in this tree:

| The protocol names | Count | The harness's use |
|---|---:|---|
| Mandatory automated gate classes | 5 | the classes it runs, each with the protocol's own definition in the report |
| Metrics to report with denominators and failure cases | 7 | one row each, with the protocol's own wording |
| Phase 1 blockers | **6** | one row each, with the protocol's own wording |

**On the count of blockers.** The protocol's `## Phase 1 blockers` section
lists **six** bullets. The task breakdown for this gate
([`docs/plans/LC-P1-13-14-task-breakdown.md`](../plans/LC-P1-13-14-task-breakdown.md)
§2.1) called them *"seven Phase 1 blockers"* and then quoted six. **The
harness counts what the protocol lists — six — and the report says six.**
The protocol is the ruler and it has not been edited here. **The
discrepancy was recorded rather than resolved, and this gate's own review
found it again; the five shipped documents that repeated the wrong number
now say six, and the wrong number is gone.**

The two sentences the protocol attaches to the metrics are carried into
every report verbatim:

> Results are benchmarks only when measured on immutable fixture/version
> labels.

> Do not claim superiority over PaperQA2/PaperSpine/others without
> like-for-like matched-task baselines, verified capabilities, and
> documented confidence intervals or limitations.

The second one is **enforced**, not quoted: see §7.

---

## 3. What it ran, and what it did not run

| The protocol's class | The protocol's own definition | Files | Passed / collected | Failed | Errored | Skipped | xfail | Rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Unit** | model/provider-independent typed contracts, state transitions, permission resolution, path traversal/symlinks, dataset locators, numerical extraction and report serialization. | 45 | **1469/1470** | 0 | 0 | 1 | 0 | 0.999 |
| **Integration** | SQLite migrations, transactional event append, restart recovery, approvals, artifact hashes, local API auth and provider redaction. | 29 | **1131/1134** | 0 | 0 | 3 | 0 | 0.997 |
| **Negative** | fabricated citation, missing material, conflicting numeric values/units, insufficient evidence, outdated checkpoint, simulated crash between file change and operation confirmation, untrusted document instructions. | 19 | **361/362** | 0 | 0 | 1 | 0 | 0.997 |
| **E2E** | fresh install + CLI task, local Web task, resume and revise, Markdown and DOCX/PDF export, source click-through. | 2 | **86/86** | 0 | 0 | 0 | 0 | 1.000 |
| **Real-model smoke** | at least one real supported provider under declared model/version/parameters; results and costs documented. Mock-only success is insufficient. | 0 | **NOT RUN** | — | — | — | — | — |
| **Repository gates** | the repository's own gates — the shard list, the README's accuracy, the reference-exclusion check, the repo-root guard, the status board, the suite's temp isolation and the packaging smoke. They are run and reported, and they are not one of the protocol's five mandatory gate classes, so they are counted apart from them. | 8 | **305/305** | 0 | 0 | 0 | 0 | 1.000 |

**The class that was not run.** The real-model smoke needs a real
provider's credential and a declared model, version and parameter set, and
**the repository has no credential for one** — `.env.example` and the
`requires_provider` marker exist for exactly this. The harness reports the
class as **NOT RUN**, gives the reason in the class's own row, and does
**not** count it as a pass: a class that was not run has no rate, and a
rate of zero would say *"every case failed"*, which is a different fact.

**The sixth class, which the protocol does not name.** The repository's own
gates — the shard list, the README's accuracy, the reference-exclusion
check, the repo-root guard, the status board, the suite's temp isolation
and the packaging smoke — are run and reported, and they are **counted
apart** from the protocol's five. Counting them into a class the protocol
did not name would inflate that class's denominator with checks the
protocol never asked for.

---

## 4. The partition, and how it is watched

The repository's test files are not filed under the protocol's names, so
somebody has to say which file belongs to which class, and the answer has
to be written down. `tests/evaluation/manifest.py` is that table: every
`tests/test_*.py` under **exactly one** gate class, with the **protocol
clause** it checks beside it.

Two rules, and a watch for each:

1. **Where a file declares a marker, the marker decides.** 33
   files carry `unit`, `integration` or `e2e`, and the partition may not
   contradict them. `test_the_partition_agrees_with_the_markers_a_file_declares`
   is that watch — and it is not decoration: during the build it caught
   `tests/test_earlier_exit_demos.py` being filed under `e2e` when the
   file declares `integration`.
2. **A file in no class is a hole.** `test_the_partition_files_every_test_file_exactly_once`
   fails if a test file is in no class, because such a file's cases enter
   **no denominator** — the same hole the harness exists to close, seen
   from the other side.

**The partition's limit, stated.** The other 70 files
declare no marker, and their class is **this harness's judgement**. It is
recorded per file so a reviewer can argue with a specific entry rather
than with the whole run, and the clause column says which protocol
property each file checks.

**The limit of a file-level partition.** A file whose own tests span two
classes lands in one of them. `tests/test_earlier_exit_demos.py` is the
case in point: two of its tests declare `integration` and the rest do not
declare anything.

---

## 5. The metrics — each with its numerator and its denominator

**The distinction the table keeps.** A metric's **value** is what the
protocol asks for. A metric's **witness score** is how many of the tests
that check that property passed. **They are different numbers, and the
witness score is never presented as the value.**

| The protocol's metric | The value | The witnesses' score | Small denominator? |
|---|---|---|---|
| End-to-end task success (successful verified deliveries / attempted tasks). | **NOT MEASURED** | 114/116 |  |
| Evidence locator validity and citation support precision (human-checked sample). | **NOT MEASURED** | 145/145 |  |
| Numeric-cell extraction exactness and unit consistency. | **84/84** — 77/77 — 14/14 | 256/256 |  |
| Unsupported-claim detection and appropriate abstention. | **NOT MEASURED** | 34/34 |  |
| Revision consistency; no stale figure/caption/reference retained after source change. | **NOT MEASURED** | 126/126 |  |
| Recovery correctness / duplicate side effects across fault-injection runs. | **8/8** | 40/40 | yes |
| Latency, model usage/cost with model name, dataset revision and seeds where meaningful. | **1337062/3357** | 47/47 |  |

- **End-to-end task success (successful verified deliveries / attempted tasks).**
  - **The witnesses:** test_smoke_path.py, test_analysis_demo.py, test_cli.py, test_service_launch.py, test_earlier_exit_demos.py — 114/116 passed
- **Evidence locator validity and citation support precision (human-checked sample).**
  - **The witnesses:** test_cite_c1.py, test_cite_c2.py, test_cite_c3.py, test_evidence_anchor_registry.py — 145/145 passed
- **Numeric-cell extraction exactness and unit consistency.**
  - **How the value was measured:** the cells the committed answer key addresses, compared cell by cell against the classification the product's own selection code gives them (a quantity, an empty cell, an absent cell, or text that is not a number)
  - **Also measured:** the addressed cells the answer key says carry a quantity, compared against the cells the product read as a quantity
  - **Also measured:** the selections whose answer key states a unit, checked against the distinct unit tokens the product's own selection code reports for the cells it used
  - **The witnesses:** test_analysis_fixtures.py, test_analysis_selection.py, test_analysis_descriptive.py, test_analysis_grouped.py, test_cite_c3.py — 256/256 passed
- **Unsupported-claim detection and appropriate abstention.**
  - **The witnesses:** test_evidence_gate.py, test_refusal_witnesses.py, test_skill_quality.py, test_fake_provider_invariants.py — 34/34 passed
- **Revision consistency; no stale figure/caption/reference retained after source change.**
  - **The witnesses:** test_analysis_report_revisions.py, test_analysis_report_checks.py, test_analysis_report_manifest.py, test_recovery_resume.py — 126/126 passed
- **Recovery correctness / duplicate side effects across fault-injection runs.**
  - **How the value was measured:** the fault-injection scenarios the crash matrix ran, over the scenarios it holds; one collected test case is one injected fault, and a scenario counts as correct when the matrix's own expected behaviour is what happened
  - **The witnesses:** test_recovery_crash_matrix.py, test_store_atomicity.py, test_recovery_resume.py, test_recovery_approvals.py — 40/40 passed
- **Latency, model usage/cost with model name, dataset revision and seeds where meaningful.**
  - **How the value was measured:** the wall-clock milliseconds the harness's own gate-class runs took, over the test cases they collected — a mean per case, and not the protocol's task latency, which needs a task corpus and a provider that answers it
  - **The witnesses:** test_fake_provider_usage.py, test_fake_provider_usage_transcripts.py, test_provider_budget.py — 47/47 passed
  - cost: NOT MEASURED — no real provider ran, so there is no cost to report. The protocol says mock-only success is insufficient, so this is stated rather than filled in.
  - model name: NOT MEASURED for a real provider — the offline run used the deterministic FakeProvider, which is not a declared model, version and parameter set.

**The four that were not measured, and why.** Each reason names the
**missing input**, not a missing feature:

| The protocol's metric | Why it was not measured |
|---|---|
| End-to-end task success | the protocol counts *successful verified deliveries over attempted tasks*; this run counts test cases, and the tree holds no corpus of attempted tasks with verified deliveries. The public fixtures that would be that corpus are LC-P1-13 T00's deliverable, and they are **not in the tree at the commit this record was measured at**. |
| Evidence locator validity and citation support precision | the protocol asks for a **human-checked sample**; the tree records none, and a machine count is not a substitute for one. |
| Unsupported-claim detection and appropriate abstention | abstention only shows up where the answer is **not** there; the tree holds no no-evidence fixture to abstain over, so the numerator would count nothing. |
| Revision consistency | the protocol's metric is the rate over **source changes**; the tree records no corpus of source-change runs with their outcomes. |

**What the corpus measurement is, exactly.** The protocol's *"numeric-cell
extraction exactness and unit consistency"* **is** measured, and not by a
test-pass count. The harness takes the committed answer key beside the
corpus (`tests/fixtures/analysis/*.expected.json`), runs the product's
**own** selection code over the same cells, and compares **cell by cell**.
The key is the right judge because of what it is: written by hand beside
the data, not generated by anything in this repository, and computed with
Python's `statistics` — an implementation that is not LabCairn's.

Two numbers are reported and **neither stands in for the other**: the
exactness figure counts every addressed cell (reading a cell as *empty*
is a correct reading), and the quantity-extraction figure counts only the
cells that carry a number, which is the narrower claim the protocol's word
*"numeric-cell"* makes.

**Nothing is re-implemented for the measurement.** The two refusal points
are the product's own: a column whose *header* declares a unit the cells
contradict is refused by `resolve_selection`, and a selection whose *cells*
carry two unit tokens is refused by the operator. The harness calls both
and reports what they did. A second implementation of the refusal rule
would be a second answer to the same question.

---

## 6. The failure cases

**A failure that is averaged into a rate is a failure that is not
reported.** The protocol asks for the failure cases themselves, so the
report lists them: node id, status, and the message pytest recorded.
**A skip is listed among them**, because a skipped test did not run and a
test that did not run is not a pass.

| The class | The case | Status | The message pytest recorded |
|---|---|---|---|
| Unit | `tests/test_provider_credentials.py::test_real_provider_smoke_records_capabilities_and_usage` | **skipped** | NOT RUN. Requires the project owner's explicit authorisation to spend money and a credential they supplied for that purpose. LC-P1-03 must not use a credential found in this machine's environment. |
| Integration | `tests/test_api.py::test_the_session_directory_can_still_be_entered` | **skipped** | POSIX permission bits |
| Integration | `tests/test_earlier_exit_demos.py::test_an_earlier_gates_exit_demonstration_still_holds[g1_exit_demo-steps0]` | **skipped** | g1_exit_demo is skipped on Windows until the product's 8.3 short-name comparison is fixed -- docs/plans/LC-P1-13-14-task-breakdown.md section 2.6 |
| Integration | `tests/test_earlier_exit_demos.py::test_the_demonstrations_exit_code_still_means_something[g1_exit_demo-steps0]` | **skipped** | g1_exit_demo is skipped on Windows until the product's 8.3 short-name comparison is fixed -- docs/plans/LC-P1-13-14-task-breakdown.md section 2.6 |
| Negative | `tests/test_security_paths.py::test_windows_drive_path_is_refused_on_posix` | **skipped** | the Windows drive form is meaningless on POSIX |

**A skip is listed here as a failure case, and that is deliberate.** A
skipped test did not run, so it is not a pass, and the report does not let
it disappear into a rate. The table above gives each one with the reason
pytest recorded.

**The skips are not the same fact, and the report says which is which.**
The brief this harness was built to says that *a blocking test that is
skipped counts as a failure in the run, not a neutral*, and the harness
does exactly that: **no skip is ever neutral.** But there are three kinds
of skip here, and they are worth keeping apart:

| The skip | How it is declared | What it means |
|---|---|---|
| `tests/test_provider_credentials.py::test_real_provider_smoke_records_capabilities_and_usage` | `@pytest.mark.requires_provider` plus `@pytest.mark.skip(reason=...)` | **It never runs, on any platform.** The protocol's own gate, seen from the inside: the real-provider smoke needs the owner's authorisation and a credential issued for the purpose. |
| `tests/test_api.py::test_the_session_directory_can_still_be_entered` | `@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")` | **A declared platform conditional.** The case is about POSIX permission bits, and this run was on Windows. |
| `tests/test_security_paths.py::test_windows_drive_path_is_refused_on_posix` | `@pytest.mark.skipif(os.name == "nt", reason="the Windows drive form is meaningless on POSIX")` | **A declared platform conditional**, and the POSIX half of a pair whose Windows half runs here. |
| `tests/test_earlier_exit_demos.py::test_an_earlier_gates_exit_demonstration_still_holds[g1_exit_demo-steps0]` and `…::test_the_demonstrations_exit_code_still_means_something[g1_exit_demo-steps0]` | a skip whose reason **names the defect it is waiting for** | **A known product defect, open on this platform.** G1's exit demonstration fails on a Windows runner because the product compares a short-spelled and a long-spelled path — the defect the gate's own breakdown records at §2.6, and T02's to fix. |

**The third kind is the one that matters, and the harness's rule catches
it.** The base branch's new witness skips G1's demonstration on Windows
**until the product's 8.3 short-name comparison is fixed**, and it says so
in the skip's own reason — *"it is not a hole with a shape nobody can
see"*. And the harness agrees: **a Phase 1 blocker that is waiting on an
open defect has not held.** The protocol's first blocker — *"A new user
cannot complete a task from a clean environment following README"* —
**FAILED in this run**, because the demonstration of a clean environment
does not run on this platform while the defect is open. That is the
blocker rule doing its job, and it is the first time this tree has been
told that a Phase 1 blocker does not hold.

**The second kind is the one that is a judgement, and it is not settled
here.** A declared platform conditional is skipped on the runner it does
not apply to and runs on the other runner of the CI matrix, so the
property it checks *is* exercised — but the harness does not soften the
rule to say so, because deciding that a skip is benign is a judgement
about the protocol, and the protocol is the ruler and this record does not
edit it. The rule as the brief states it is applied, the case is named,
and the reason pytest recorded is quoted, so a reader has everything the
decision needs.

**Two questions for the owner, both named rather than settled here:**

1. *Should a declared platform conditional — a `skipif` that is false on
   the runner in question — fail a Phase 1 blocker on that runner?* The
   harness's answer today is **yes**, because a skip that is never neutral
   is the rule the brief gave, and because a rule that cannot be softened
   by a reader is a rule that cannot be quietly ignored. The alternative —
   a skip that counts only when the test is skipped *everywhere* — needs
   both platforms' runs to decide, which a single run does not have.
2. *Should a skip that names an open defect count the same way?* The
   harness's answer today is **yes**, and this record's §8 shows what that
   costs: the protocol's first blocker does not hold while the 8.3
   short-name defect is open. The alternative — a blocker that waits, and
   says what it is waiting for — is a rule that is easier to live with and
   easier to forget, and the difference between the two is a decision
   about the gate rather than about the measurement.


---

## 7. The comparison: what the protocol permits, and what was done

**Nothing was compared.** The protocol allows a comparison only when it is
like-for-like — matched tasks at matched versions, the same model and
budget, verified capabilities, and documented confidence intervals or
limitations — and **no baseline exists in this tree**.

The mechanism is built and it works, and the report says why it refused:

- no baseline document was given, so no comparison was made. The protocol permits a comparison only when it is like-for-like, and an unasked-for comparison is not one.

**No ranking is printed, ever, and that is structural rather than
promised.** The comparison renders **pairs** — one metric at a time — and
has no aggregate for a reader to be handed. `tests/test_evaluation_harness.py`
watches the **rendered** section for the words a verdict would be made of
(`better`, `worse`, `best`, `worst`, `superior`, `outperform`, `beats`,
`winner`, `loses`, `ahead`); a section that says one of them has claimed
something, however carefully the code meant it.

**A further refusal, which is the protocol's own rule producing the
answer.** This run used the deterministic `FakeProvider`, which is not
*"a declared model, version and parameter set"*, so the run **declares no
model**. A baseline that declares one therefore cannot be matched against
it, and the harness says exactly that rather than declining on its own
initiative.

---

## 8. The Phase 1 blockers

**The rule.** A blocker is held when every one of its witnesses was
collected **and passed**. A witness that was **skipped** is a witness that
did not hold: the protocol's own sixth blocker is about required tests that
do not run, and a skipped witness *is* a required test that did not run.
The rule is applied to **every** blocker, not only to the sixth — the
sixth is the one the protocol names it for. A witness that was not part of
the run at all cannot be evaluated, and a blocker that could not be
evaluated **has not held**.

| The protocol's blocker | Status at `37ae366` | Witnesses | What the status means |
|---|---|---:|---|
| New user cannot complete a task from a clean environment following README. | **FAILED** | 4 | 2 of 51 witness cases did not pass; a skipped witness counts against the blocker |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **FAILED** | 4 | 1 of 112 witness cases did not pass; a skipped witness counts against the blocker |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | **HELD** | 4 | every witness was collected and passed |
| A crash silently repeats unknown file side effects. | **HELD** | 3 | every witness was collected and passed |
| Report claims a verified scientific result based solely on schema or rendering checks. | **HELD** | 3 | every witness was collected and passed |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | **HELD** | 3 | every witness was collected and passed |

**New user cannot complete a task from a clean environment following README.** — the witness cases that did not pass:

- `tests/test_earlier_exit_demos.py::test_an_earlier_gates_exit_demonstration_still_holds[g1_exit_demo-steps0]` — **skipped** — g1_exit_demo is skipped on Windows until the product's 8.3 short-name comparison is fixed -- docs/plans/LC-P1-13-14-task-breakdown.md section 2.6
- `tests/test_earlier_exit_demos.py::test_the_demonstrations_exit_code_still_means_something[g1_exit_demo-steps0]` — **skipped** — g1_exit_demo is skipped on Windows until the product's 8.3 short-name comparison is fixed -- docs/plans/LC-P1-13-14-task-breakdown.md section 2.6

**Any unauthorized file write/escape or unconsented private-network disclosure.** — the witness cases that did not pass:

- `tests/test_security_paths.py::test_windows_drive_path_is_refused_on_posix` — **skipped** — the Windows drive form is meaningless on POSIX

**In that run, two of the six blockers did not hold, and both of them were
skips.** They are the two kinds §6 separates:

* **The protocol's first blocker** — *"A new user cannot complete a task
  from a clean environment following README"* — **FAILED**, because the
  base branch's new witness skips **G1's exit demonstration on Windows**
  while the product's 8.3 short-name comparison was unfixed
  ([the breakdown's §2.6](../plans/LC-P1-13-14-task-breakdown.md)). The
  demonstration of a clean environment does not run on this platform, so
  the blocker that names a clean environment cannot be said to hold. **This
  is a finding, not a defect of the harness**: the product really does
  refuse a write under a short-spelled directory on a Windows runner, and
  the rule that a skipped witness fails its blocker is what makes that
  visible against the protocol's own words. It is T02's to fix, and until
  it is fixed the harness will keep reporting this blocker as failed.
* **The protocol's second blocker** — *"Any unauthorized file write/escape
  or unconsented private-network disclosure"* — **FAILED**, because of
  the **declared platform conditional**: one of its witness cases is about
  the POSIX half of a pair and is skipped on Windows. The property *is*
  exercised, on the other runner of the CI matrix. **Whether that should
  fail the blocker on this runner is the owner's question**, and it is
  asked in §6 rather than answered here.

**The other four blockers held**, and so did the one about skipped required
tests — which **did not always**. The harness's **first** run on this tree,
before the shard list was fixed, found **two failing cases** in
`tests/test_ci_shard_coverage.py`, both of them the same hole:

> on ubuntu-latest, these test files are in no shard, so CI never runs
> them: `['tests/test_earlier_exit_demos.py', 'tests/test_evaluation_harness.py']`

That is **the hole this whole package exists to close, found by the
package itself**: two test files that no CI job would ever have run. One
of them had arrived with the gate's base branch; the other was the file
this work adds. Both are now filed, the shard file is regenerated, and
the run recorded in this document is **after** the fix — which is why the
sixth blocker holds here. The earlier run's numbers are not carried
forward: a number belongs to the tree it was measured on.

---

### The table, re-measured on the tree the gate closes on

| The Phase 1 blocker | Status at `c362317` | Witnesses | What the status means |
|---|---|---|---|
| New user cannot complete a task from a clean environment following README. | **HELD** | 4 | every witness was collected and passed |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **FAILED** | 4 | 3 of 114 witness cases did not pass, and **all three are skips**: the POSIX half of a platform pair, and the two 8.3 short-name witnesses, which a volume that generates no short names skips. **No single runner of the CI matrix carries all of them.** |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | **HELD** | 4 | every witness was collected and passed |
| A crash silently repeats unknown file side effects. | **HELD** | 4 | every witness was collected and passed |
| Report claims a verified scientific result based solely on schema or rendering checks. | **HELD** | 3 | every witness was collected and passed |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | **HELD** | 3 | every witness passed, **and the row names the excluded required tests with their reasons** — whether a declared skip fails this blocker is the owner's ruling, not the harness's |

**The real-model smoke class was selected, could not be run, and is reported
NOT RUN with the reason**, so the harness's exit code is **2**. The three
metrics that are measured are the **abstention metric at 1/1** — the
no-evidence fixture's honest *"the material does not say"* — the **recovery
metric at 4/4**, its denominator being the distinct crash points the matrix
injects, read out of the matrix itself, and the **numeric extraction at
84/84**. Four metrics remain NOT MEASURED and the report names the missing
input for each.

---

### The table, re-measured after §1.4.1b was ruled and the harness was told

**Corrected 2026-10-29.** The two rows above describe the second blocker as
FAILED for three platform skips, and the sixth blocker's row said whether a
declared skip fails it *"is the owner's ruling, not the harness's"*. The owner
has ruled, and `tests/evaluation/aggregate.py` now acts on it rather than
describing it:

- a skip whose reason names **a fact of the machine** — an OS, a filesystem, a
  volume that generates no 8.3 short names — does not fail a blocker;
- a test in a class the owner has ruled is discharged outside the offline run
  (§1.4.2) does not fail it either; neither does a file this run did not select
  (scope, not a skip), nor one it asked pytest for in which no case was
  collected;
- **any other skip fails it**, by name and with the reason the test gave;
- and every accepted exclusion is **named in the row**: a witness case by its
  node id and the reason pytest recorded, a required CI test by its file under
  the standing category it fell in.

The owner was asked whether the ruling covers witness cases and not only the
sixth blocker's required CI tests, and chose **all blockers** — which is what
the second blocker's row needed.

At `22e2f2d`, on a clean tree (`--out` under the system temp directory,
**1788.3 s**, exit code **2**):

| The Phase 1 blocker | Status at `22e2f2d` | Witnesses | Cases that did not pass | What the status means |
|---|---|---|---:|---|
| New user cannot complete a task from a clean environment following README. | **HELD** | 4 | 0 | every witness was collected and passed |
| Any unauthorized file write/escape or unconsented private-network disclosure. | **HELD** | 4 | 3 | **accepted, and named**: three witness cases skipped for a platform or filesystem fact |
| Fake citation presented as verified or unsupported numerical fact presented as measured. | **HELD** | 4 | 0 | every witness was collected and passed |
| A crash silently repeats unknown file side effects. | **HELD** | 4 | 0 | every witness was collected and passed |
| Report claims a verified scientific result based solely on schema or rendering checks. | **HELD** | 3 | 0 | every witness was collected and passed |
| Required CI tests are skipped, ignored or only pass by mocking the actual behavior under acceptance. | **HELD** | 3 | 0 | every witness passed, and the row names the six required test **files** it accepted, in the three categories: two skipped for a fact of the machine, one in a class discharged outside the run, three in which pytest collected no case |

**All six hold, and the second one holds by being told what to accept.** Its row
carries the three cases verbatim, because an acceptance that does not say what
it accepted is indistinguishable from a hole:

> `tests/test_security_paths.py::test_windows_drive_path_is_refused_on_posix` —
> the Windows drive form is meaningless on POSIX;
> `tests/test_security_paths.py::test_a_new_file_under_a_short_spelled_root_is_not_refused`
> and `…::test_a_path_outside_a_short_spelled_root_is_still_refused` — this
> machine's volume has no 8.3 short names.

**The exit code is still 2, and it is 2 for the reason it has always been 2.**
The real-model smoke class is selected, cannot run offline, and is reported NOT
RUN. The ruling changes which blockers hold; it does not make the fifth gate
class run, and this sentence is here because the two are easy to lose in each
other.

**The sixth blocker's row, verbatim, is the ruling made visible:**

> This run accepted 2 required CI test(s) as a platform or filesystem fact,
> which the CI matrix's other platform carries (§1.4.1b): test_api.py,
> test_security_paths.py. This run accepted 1 required CI test(s) as a test in a
> class the owner has ruled is discharged outside it (§1.4.1b):
> test_real_provider_smoke.py. This run accepted 3 required CI test(s) as a test
> this run asked pytest for and in which no case was collected, which is not a
> skip and is not a check either (§1.4.1b): test_recovery_support.py,
> test_skill_support.py, test_store_support.py.

**Two defects in the harness's own numbers were found by reading the tree to
check this ruling, and both are witnessed.**

- **A test class's cases were keyed to a file that does not exist.** pytest
  writes the module and the test class in one dotted `classname`, and the JUnit
  reader assumed there was no class: `tests.test_skill_ledger.TestDigests` became
  `tests/test_skill_ledger/TestDigests.py`. Six files in this suite hold their
  cases in classes, so **their cases entered no denominator at all** — and the
  metric that names one of them as a witness, `unsupported-claim-detection`,
  reported a witness score of **34/34** when the same suite was read by the old
  reader, where the tree actually held **82** cases behind it. The run above,
  read by the fixed reader, reports **82/82**. The split is now taken from the
  tree (the longest dotted prefix that is an actual file is the module), and
  `test_a_real_run_keys_a_test_class_to_the_file_it_lives_in` runs the real
  pytest subprocess over `tests/test_skill_ledger.py` to hold it.
- **Three files in the CI's own shard list collect nothing.**
  `test_store_support.py` and `test_recovery_support.py` say so in their own
  docstrings (*"Not a test module — it defines no `test_*` functions"*), and
  `test_skill_support.py` describes itself as *"shared fixtures and honest stage
  bodies"*; other test files import them for their builders. They are filed in a
  gate class, they are in every shard, CI pays to collect them, and no case comes
  out. The row used to report them as files *"this run did not select"*, which is
  false — the run selected them; nothing was there. `test_ci_shard_coverage` and
  the partition's own witnesses cannot see this, because both ask *"is every test
  file in a class?"* and never *"is there a test in it?"*.
  **Whether a required test file that carries no case belongs in the shard list
  is a question this record does not settle**, and it is carried to Phase 2.

## 9. The witnesses, and the mutation table

`tests/test_evaluation_harness.py` — **74 test functions, 75 test cases** (one
of them is parameterised), and each one names the property it holds. **The table
below is re-read from the file, not remembered**:
`test_the_evaluation_record_names_every_witness_in_this_file` fails if a witness
this file defines has no row in it, or if the count above is not the number of
`def test_` in the file — which is the only way a table like this one stays true.
It had drifted by thirty functions before that witness was written.

A mechanism that nobody watches can be neutered, and then the tree stays
green while the evaluation stops measuring anything.

| The witness | The property it holds |
|---|---|
| `test_the_partition_files_every_test_file_exactly_once` | No test file is in no class, and none is in two |
| `test_every_file_the_partition_names_exists` | A filed file that is not there is a class that quietly runs less |
| `test_the_partition_agrees_with_the_markers_a_file_declares` | Where a file declares a marker, the partition may not contradict it |
| `test_a_file_that_declares_no_protocol_marker_is_in_no_protocol_class` | A file that says nothing about its class may not be filed into one |
| `test_every_clause_the_partition_names_is_in_the_vocabulary` | A clause outside the vocabulary is a clause the report cannot place |
| `test_the_repository_class_is_not_one_of_the_protocols_five` | The repository's own gates are reported separately from the protocol's |
| `test_the_parser_reads_the_protocol` | The protocol's classes, metrics and blockers are found |
| `test_the_parser_refuses_a_protocol_that_is_not_there` | A document without the protocol's sections is an error, not an empty result |
| `test_the_parser_refuses_an_item_it_has_no_witness_key_for` | A protocol item with no witness key is an error, not a silent omission |
| `test_every_metric_the_protocol_names_has_witnesses` | A metric with no witness is a metric this repository does not check |
| `test_every_blocker_the_protocol_names_has_witnesses` | A blocker with no witness is a blocker nobody is watching |
| `test_every_witness_file_is_one_the_partition_files` | A witness outside the partition would never run, and would look like a pass |
| `test_a_real_pytest_run_is_read_as_outcomes` | The runner and the JUnit reader work on a real pytest run |
| `test_a_real_run_keys_a_test_class_to_the_file_it_lives_in` | A case in a class belongs to the file the shard list names |
| `test_a_file_attribute_still_keeps_the_test_class` | A report that names the file still has the class in its classname |
| `test_the_blockers_table_says_what_its_cases_column_counts` | A HELD blocker can carry cases that did not pass, and the column says so |
| `test_the_junit_reader_tells_a_skip_from_an_expected_failure` | A pytest.skip and an xfail are both <skipped> elements |
| `test_the_junit_reader_refuses_a_report_that_is_not_there` | A missing report is an error, not an empty result |
| `test_the_runner_refuses_a_temporary_directory_inside_the_repository` | A temporary directory inside the checkout makes the run depend on the tree |
| `test_a_platform_conditional_witness_skip_is_accepted_and_named` | §1.4.1b: a witness skipped for a fact of the machine does not fail |
| `test_a_witness_skip_outside_the_accepted_categories_still_fails` | The control the witness above needs: the same skip, a different reason |
| `test_every_platform_phrase_is_carried_by_a_skip_in_the_tree` | A phrase no skip carries is a dead entry in the ruling |
| `test_a_skipped_witness_fails_its_blocker` | A required test that did not run is a blocker that did not hold |
| `test_a_failed_witness_fails_its_blocker` | A failing witness fails its blocker, and the case is listed |
| `test_a_witness_that_did_not_run_leaves_the_blocker_unevaluated` | A blocker that could not be evaluated has not held |
| `test_a_blocker_whose_witnesses_all_passed_holds` | The positive case, so the three above are not passing vacuously |
| `test_a_class_that_collected_nothing_has_no_rate` | No cases is not zero cases |
| `test_a_small_denominator_is_said_so` | A rate over a handful of cases is called small, in the row itself |
| `test_the_report_carries_the_denominators` | The rendered report states each rate as numerator over denominator |
| `test_the_corpus_measurement_agrees_with_the_committed_answer_key` | The measurement's denominator is the corpus's own, counted twice |
| `test_the_corpus_measurement_reports_no_failure` | Every cell is read exactly as the key says, and every refusal refuses |
| `test_a_like_for_like_baseline_is_comparable` | The positive case: everything the protocol names is present |
| `test_a_baseline_missing_a_requirement_is_refused` | A baseline that does not meet the protocol's rule is not compared |
| `test_a_baseline_on_different_tasks_is_refused` | Matched tasks are the first requirement, and it is not optional |
| `test_the_offline_run_refuses_a_competitor_on_the_model_alone` | §5.1's blocker, executed rather than described |
| `test_a_model_declaring_run_makes_that_same_competitor_comparable` | The control: the refusal above is our empty basis, not a broken compare |
| `test_the_comparison_prints_pairs_and_never_a_verdict` | The structure stops a ranking, not a disclaimer |
| `test_the_rendered_comparison_carries_no_winners_language` | The report's comparison section names no winner |
| `test_a_baseline_document_is_read_with_its_numbers` | A baseline file carries its basis and its numbers |
| `test_the_real_model_smoke_is_reported_as_not_run_with_its_reason` | The class that needs a credential says so, and says why |
| `test_the_real_model_smoke_class_has_a_file_that_carries_it` | The fifth class is not runnable, which is not the same as has no witness |
| `test_the_real_model_smoke_is_not_counted_as_a_pass` | A class that did not run has no rate, and is not a pass |
| `test_the_command_lists_the_partition` | --list prints the partition and runs nothing |
| `test_the_command_refuses_a_class_it_does_not_know` | An unknown class is refused rather than silently ignored |
| `test_the_command_writes_a_report_and_says_what_it_found` | The command's whole path, with the run stubbed out |
| `test_the_default_run_reports_the_real_model_class_as_not_run` | The default run refuses the class that spends money, and says so |
| `test_a_class_named_on_the_command_line_is_run_rather_than_refused` | Naming the fifth class makes the harness run it, not decline it |
| `test_the_report_and_the_json_say_the_same_thing` | Both renderings come from one run, and neither is derived from the other |
| `test_the_measurement_carries_its_denominator_and_its_reason` | A measurement that is not a number says why, and says so in the model |
| `test_the_harness_runs_on_the_pinned_interpreter` | The harness runs under the interpreter the project pins |
| `test_the_public_corpus_measurement_reads_the_manifest` | The harness's corpus measurement reads the public corpus as well |
| `test_the_public_corpus_measurement_agrees_with_the_material` | Every question the corpus asks, the product answers as the key says |
| `test_the_public_corpus_measurement_can_fail` | The measurement can fail, and this is how it is shown |
| `test_the_abstention_metric_is_measured_over_the_public_corpus` | The protocol's abstention metric is measured, and over this corpus |
| `test_a_not_measured_reason_may_not_contradict_the_tree` | A reason that names a missing input has to be true of this tree |
| `test_a_reason_about_a_tree_that_is_not_there_is_still_true` | A tree without the public corpus gets the reason that fits it |
| `test_the_repository_class_holds_only_the_repository_gates` | The repository class is the repository's own gates, and nothing else |
| `test_the_rendered_report_says_a_small_denominator_out_loud` | The rendered text, not the model attribute, is what is watched |
| `test_the_recovery_metric_counts_crash_points_and_not_cases` | The denominator is the crash points, and the sentence says so |
| `test_the_recovery_metric_drops_when_a_crash_point_behaves_wrongly` | A crash point whose case failed is not a crash point that held |
| `test_the_crash_matrix_coverage_is_read_from_the_matrix` | The coverage is read out of the matrix's own source |
| `test_the_report_says_when_the_tree_it_measured_was_dirty` | A revision names a commit; the tree the run happened on may differ |
| `test_the_rendered_report_names_the_tree_it_measured` | The report says which tree it measured, and the JSON carries it too |
| `test_a_platform_conditional_skip_is_accepted_and_named` | A required test skipped for a fact of the machine holds, and is named |
| `test_a_skip_that_names_no_standing_category_fails_the_blocker` | A required test skipped for a reason outside the categories fails it |
| `test_the_real_model_smoke_file_is_accepted_as_ruled_elsewhere` | The offline run's absence of the smoke class is not a skipped test |
| `test_a_required_test_the_run_did_not_select_is_not_called_a_skip` | Leaving a required test out of a run is scope, not a skip |
| `test_a_required_test_that_collected_nothing_is_named_as_that` | Selected-and-empty is neither "not selected" nor a pass |
| `test_one_file_with_three_skips_is_counted_as_one_file` | The row counts files, and says so in the number it prints |
| `test_the_exclusion_is_in_the_rendered_report` | The exclusion is on the page, not only in the model |
| `test_the_required_tests_are_read_out_of_the_shard_file` | The required tests come from the CI's own shard list |
| `test_no_published_record_claims_superiority_over_another_system` | The documents a reader reads are watched for a superiority claim |
| `test_the_inner_run_gets_its_own_temporary_directory_everywhere` | TMPDIR is set as well, because it is the one that is read first |
| `test_the_evaluation_record_names_every_witness_in_this_file` | The record's witness table is re-read from this file, not remembered |

### The mutation table

**A witness that does not fail for the property it holds is not a
witness.** Each mutation below breaks **one** mechanism, and the test that
watches that mechanism must go red. Every mutation was applied to the
committed tree, the named witness was run alone, and the tree was
restored.

| # | The mutation | The witness that went red, and what it said |
|---|---|---|
| M1 | a skipped witness counts as a pass (the blocker's failure test becomes `status == "failed"`) | `test_a_skipped_witness_fails_its_blocker` — **RED**: `assert 'HELD' == 'FAILED'` |
| M2 | a test file leaves the partition | `test_the_partition_files_every_test_file_exactly_once` — **RED**: *"these test files are in no gate class, so their cases enter no denominator: `['test_capability_namespaces.py']`"* |
| M3 | a file's class contradicts its own markers | `test_the_partition_agrees_with_the_markers_a_file_declares` — **RED**: *"test_provider_adapter.py declares ['unit'] and the partition files it under 'negative', which its own markers rule out"* |
| M4 | a class that collected nothing reports a rate of zero | `test_a_class_that_collected_nothing_has_no_rate` — **RED**: `assert 0.0 is None` |
| M5 | the comparison always allows itself | `test_a_baseline_missing_a_requirement_is_refused` — **RED**: `assert not True`, *where True = ComparisonOutcome(comparable=True, reasons=(), deltas=())* |
| M6 | the comparison section claims a winner | `test_the_rendered_comparison_carries_no_winners_language` — **RED**: *"the comparison section says 'better'"* |
| M7 | the corpus's row reader mis-reads a range | `test_the_corpus_measurement_agrees_with_the_committed_answer_key` — **RED**: *"the harness counted 74 cells and the answer key holds 84"* |
| M8 | the real-model smoke is claimed to be runnable offline | `test_the_real_model_smoke_is_reported_as_not_run_with_its_reason` — **RED**: `assert not True` |
| M9 | the parser forgets the blockers | `test_the_parser_reads_the_protocol` — **RED**: the parser refuses outright — *"the protocol at …/docs/EVALUATION.md names no blocker"* — and a parser that answers with nothing is what the watch is for |
| M10 | an unrunnable class exits zero | `test_the_real_model_smoke_is_not_counted_as_a_pass` — **RED**: `assert 0 == 2` |

### The mutation table, extended for §1.4.1b (2026-10-29)

| # | The mutation | The witness that went red, and what it said |
|---|---|---|
| M11 | the runner stops naming the tree to the JUnit reader | `test_a_real_run_keys_a_test_class_to_the_file_it_lives_in` — **RED**: a real pytest subprocess over `tests/test_skill_ledger.py` keyed its 22 cases to `tests/test_skill_ledger/TestDigests.py` |
| M12 | a file that collected nothing is reported as one the run never selected | `test_a_required_test_that_collected_nothing_is_named_as_that` — **RED**: `assert 'not-in-this-run' == 'selected-and-collected-nothing'` |
| M13 | the accepted listing counts cases instead of files | see M21 — the same mutation, applied again after its witness was written |
| M14 | the witness acceptance is removed | `test_a_platform_conditional_witness_skip_is_accepted_and_named` — **RED**: `assert 'FAILED' == 'HELD'` |
| M15 | every skipped witness is accepted, whatever its reason says | `test_a_witness_skip_outside_the_accepted_categories_still_fails` — **RED**: `assert 'HELD' == 'FAILED'` |
| M16 | a phrase nothing in the tree says is added to the list | `test_every_platform_phrase_is_carried_by_a_skip_in_the_tree` — **RED**: *"these phrases match no skip in the tree: ('a phrase nothing says',)"* |
| M17 | the platform branch of the classifier is dropped | `test_a_platform_conditional_skip_is_accepted_and_named`, `test_a_platform_conditional_witness_skip_is_accepted_and_named`, `test_a_required_test_the_run_did_not_select_is_not_called_a_skip` and `test_one_file_with_three_skips_is_counted_as_one_file` — **four RED**, every row that was HELD became FAILED |
| M18 | "this run did not select" is folded into "undeclared" | `test_a_required_test_the_run_did_not_select_is_not_called_a_skip` — **RED**: `assert 'FAILED' == 'HELD'` |
| M19 | "a class discharged outside this run" is folded into "undeclared" | `test_the_real_model_smoke_file_is_accepted_as_ruled_elsewhere` — **RED**: the row no longer named `test_real_provider_smoke.py` under that standing |
| M20 | a required test skipped with no standing category no longer fails the blocker | `test_a_skip_that_names_no_standing_category_fails_the_blocker` and `test_the_exclusion_is_in_the_rendered_report` — **RED**: `assert 'HELD' == 'FAILED'`, and the rendered page carried no **FAILED** row |
| M21 | the accepted listing counts cases instead of files | `test_one_file_with_three_skips_is_counted_as_one_file` — **RED**: the row said *"accepted 3 required CI test(s)"* and named one file three times |
| M22 | the JUnit reader drops the class when the XML names the file | `test_a_file_attribute_still_keeps_the_test_class` — **RED**: two cases in two classes collapsed to one node id |
| M23 | the blockers table's column header is the bare word "Cases" | `test_the_blockers_table_says_what_its_cases_column_counts` — **RED**: the header carried no statement of what the number counts |
| M24 | the function count above is put back to the stale `**39 test functions**` | `test_the_evaluation_record_names_every_witness_in_this_file` — **RED**: *"the record says 39 test functions; this file defines 74"* |
| M21 | a row of the witness table above is renamed, then deleted | `test_the_evaluation_record_names_every_witness_in_this_file` — **RED** both times: *"the evaluation record's witness table has no row for these witnesses"* |

**M21 needed two tries to become a witness.** Its first version asked whether the
name appears **anywhere in the record**, and with the table row deleted the check
stayed green — the prose two sections above still quoted the name, and a mention
is not a row. Read against the table's own lines it goes red for a rename and for
a deletion, which is the property the sentence claims. **The weak version is the
finding, not the footnote**: a check written against a document has to say which
part of it it reads, or it reports the document's memory rather than its contents.

**M13 survived its first attempt, and that is the finding.** The dedupe was
applied before any witness was aimed at it: the mutation ran, the whole file
stayed green, and nothing said *"three facts in one file is not three files"*.
The witness was written after, and the same mutation then went red. **A
mechanism change that no witness answers to is not measured, however sensible
it looks** — which is the reason §8's rulings now arrive with their witnesses in
the same branch rather than after the fact.

**Two mutations were tried and corrected before the table above**, and
both corrections are worth recording because they are what a mutation
table is for:

* **M1 was first aimed at the wrong site.** It was applied to the
  *witness-failure* computation rather than the *blocker* computation,
  and the witness stayed **green** — which says the mutation did not
  reach the mechanism, not that the witness is weak. Re-aimed at the
  blocker's own rule, it went red.
* **M3 was first aimed at a file that declares no marker.**
  `tests/test_scaffolding.py` declares none, so no marker contradicts
  anything and the witness had nothing to say. Re-aimed at
  `tests/test_provider_adapter.py`, which declares `unit`, it went red.

**A mutation that survives is a finding, and it was not papered over.**
The two corrected mutations are the finding: the first attempt at M1
changed a computation the mechanism does not use, and the first attempt at
M3 changed a file that had nothing to contradict. **A mutation that does
not reach the mechanism proves nothing about the witness**, and a witness
that has not been shown to fail is not a witness.

---

## 10. What this does not deliver

- **The protocol's task-level metrics are not measured**, and the report
  says so. Four of the seven are **NOT MEASURED**, with the missing input
  named. A number that is not a measurement of the product is a number
  with a denominator and no numerator.
- **Nothing was compared against anything.** The mechanism works and
  refuses; there is no baseline in this tree to compare against.
- **The real-model smoke did not run**, and no mock was passed off as one.
- **Two Phase 1 blockers did not hold**, and this work does not fix them:
  the 8.3 short-name defect is T02's, and whether a declared platform
  conditional should fail a blocker is the owner's question. §6 and §8
  name both.
- **The partition is a judgement** for the 70 files that declare no
  marker, and it is a **file-level** partition, so a file whose own tests
  span two classes lands in one of them.
- **One cost in the CI shard list is a local measurement**, not a runner
  measurement — see §11, which also carries the command that replaces it.
- **This is not an independent review.** The same party wrote the harness
  and wrote the witnesses that watch it. The mutation table is the
  mitigation, and it is a mitigation rather than a substitute: a reviewer
  who wrote none of these fixes is still owed one.

---

## 11. The CI shard list

**A test file in no shard is a test CI never runs**, and
`tests/test_ci_shard_coverage.py` is the watch that says so. Two files
were in no shard when this was written: `tests/test_earlier_exit_demos.py`
— which arrived with the gate's base branch — and
`tests/test_evaluation_harness.py`, which this work adds. **The base
branch has since filed the first of them**, and this work files the
second: the partition is now **103 files** on each platform, and
`make_ci_shards.py` rebuilds it from the measured costs.

### The shard file changed shape while this was being written

The base branch brought **three** things with it, and this record is
written against all of them:

* **The shard file carries `measured_at`** — the commit whose tree the
  costs describe — and a witness says so: *"the costs must still describe
  the tree, or the shards are lopsided"*. A change under `src/` or
  `tests/` moves the tree away from the anchor and the witness fails,
  which is the project's own rule (*a value that can change is
  re-measured, not carried forward*) in the form of a test.
* **The balance check is no longer a threshold.** It is now *"no file
  could be moved to shorten the wait"*, because a threshold on how equal
  the shards are is arbitrary when one file is the floor — and
  `tests/test_cli.py` is.
* **`.github/remeasure_shards.py` is the fix**: it reads the per-file
  seconds out of a CI run's log — where pytest's `--durations=0` puts
  them — writes the costs and the commit they were measured at, and
  rebuilds the partition.

### What this branch did to it, and what it could not do

**The merge conflict on the shard file was resolved onto the base
branch's costs**, not this branch's. The base's table is a CI run's
measurement; this branch's was an older table plus one local
measurement. **Taking the older table would have carried a stale value
forward**, which is the thing the project's rule forbids, so the base's
costs were kept and the one file this branch adds was filed with a
measured cost.

**And that one cost was measured on a development machine, not on a
runner**, because no runner has run this branch — pushing a branch does
not start a CI run, and starting one is the owner's call. The number is
**3.6 s**, the sum of the file's own per-test call durations. The
difference is not small and the repository's own record says so: one file
took **383 seconds on Windows and 45 on Ubuntu**, and another took **153
on Ubuntu and 288 on Windows** — not the same total, a different *order*.
**The fix is the base's own command**, run against a CI run of the merged
pull request:

```
python .github/remeasure_shards.py <run-id>
```

**One caveat about that command, found while using it.** With a run id
and no `--measured-at`, the script writes the **run id** into
`measured_at` — and the witness resolves that field with
`git diff <measured_at>..HEAD`, which fails on anything that is not a
commit. The witness then reports *"the commit <run-id> is not in this
checkout, so the costs cannot be checked"*, and the file it just wrote is
one its own witness rejects. **Pass `--measured-at <commit-sha>`**, which
the script accepts and which the witness can resolve.

**And the anchor this branch moved.** The costs were anchored at the base
branch's `08a554e`; they are now anchored at the merge commit, whose tree
the costs do describe — the hundred and two files the CI run measured are
byte-identical there, and the one file this branch adds carries a cost
measured against it. **Moving the anchor is not the same as
re-measuring**, and the difference is recorded here rather than buried: a
runner's number for the new file is still owed, and the command above is
what replaces it.

## 12. How to reproduce

```
# the harness's own witnesses
uv run pytest tests/test_evaluation_harness.py --basetemp=<outside the repo>

# the whole protocol run
uv run python -m tests.evaluation --out <outside the repo>

# the partition, without running anything
uv run python -m tests.evaluation --list
```

**The temporary directory rules apply to the harness too**, because the
harness runs the whole suite and inherits every one of their failure
modes: `--basetemp` goes **outside** the repository, the temporary
directory goes **outside** the repository and not merely off the C drive,
and two runs must not share one temporary directory. The harness makes a
directory **of its own** under the ambient temporary directory, points
`TEMP`, `TMP`, `MPLCONFIGDIR` and `LABCAIRN_TEMP_ROOT` at it, and
**refuses to run** if that directory turns out to be inside the checkout.
