# G5 — Gate review

**Gate:** G5 — Public alpha. Work orders **LC-P1-13** (evaluation, fault
injection and the competitor baseline) and **LC-P1-14** (the public alpha
handoff: the delivery documents, the release contents, the review dossier and
the licence audit).
**Exit test:** *"outsider fresh install, 3 fixtures, fault injection, docs and
real-provider smoke"*.
**Subject:** `main` @ `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f` — the merge of
PR #116, which carries the whole of G5.
**Verdict:** *(settled by the independent review below — to be filled in)*
**Reviewed against:** `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f`

## Why this gate needed a review of its own

The board's rule — `docs/PHASE_1_WORKORDERS.md` — is that **a gate is closed
only when an independent review at a named commit says so**. G3 was closed
that way and so was G4: in each case the reviewers wrote **none of the gate's
fixes**, and a mutation that survived was a finding.

**This review is that review for G5.** Two reviewers were dispatched, one per
scope, and neither of them wrote a fix into this repository — a reviewer that
fixes what it finds has stopped being independent.

**The two work orders' own acceptance reviews were not independent, and this
document says so rather than implying otherwise.** LC-P1-13's and LC-P1-14's
acceptance records were written by the party that specified the work,
dispatched it, wrote its fixes and reviewed them — the same party in all four
roles, exactly as G4's document said of LC-P1-11 and LC-P1-12. Those records
are evidence; they are not this gate's independence.

## What the exit test required, and what carries each part of it

The milestone table's exit test names five things. Here is where each one is
carried and what carries it, in this repository, at the subject commit.

| # | The clause | Carried by | The thing that carries it |
|---|---|---|---|
| 1 | **outsider fresh install** | T03, T06 | `scripts/outsider_path.py` runs in a **clean clone** and follows the README in that clone; the witness is `tests/test_outsider_path.py` (16 test functions). [The record](../acceptance/LC-P1-14-outsider-path.md) |
| 2 | **3 fixtures** | T00 | `tests/fixtures/public/` — three fixtures with answer keys and locators, **plus one that must find nothing**; the witnesses are `tests/test_public_fixtures.py` and the manifest in `tests/evaluation/manifest.py`. [The record](../acceptance/LC-P1-13-fixtures.md) |
| 3 | **fault injection** | T02 | `tests/test_recovery_crash_matrix.py` (AT1–AT7) and `tests/test_earlier_exit_demos.py`. [The record](../acceptance/LC-P1-13-evaluation.md) |
| 4 | **docs** | T06 | `README.md`, `README.zh-CN.md`, `docs/QUICKSTART.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/RELEASE-NOTES.md`; the README's commands are extracted and run by `tests/test_readme_accuracy.py`. [The record](../acceptance/LC-P1-14-outsider-path.md) §4 |
| 5 | **real-provider smoke** | T04 | **Not run.** No credential exists on this machine and `.env.example` says Phase 1 reads no environment variable. Whether a declared, reported skip is a blocker that failed is the judgement the independent review had to make — see below. |

### The Phase 1 deliverable, clause by clause

The board's own statement of what Phase 1 delivers is one sentence, and it is
the sentence the exit test is meant to discharge:

> An unrelated researcher installs LabCairn, configures an eligible LLM
> provider, binds a research folder containing a text PDF, CSV/XLSX and
> Markdown, creates a task, receives a report and deterministic scientific plot
> with source locators and an evidence ledger, requests a revision, and reopens
> that same task following a simulated restart. CLI and local Web use the same
> application services. The original materials remain unchanged.

The walk in `docs/acceptance/LC-P1-14-outsider-path.md` §3 measures **ten**
steps against it, in the order the sentence names them, and each step names
the evidence it produced. **Two of them are narrower than the sentence says
they are**, and the record says so rather than letting the sentence stand:

- **"configures an eligible LLM provider"** — Phase 1 reads no environment
  variable, so there is no provider to configure. The deterministic fixture
  path is what ran. The record says which steps were made against a fixture
  (§5), and the protocol's own rule — that a mock-only run is insufficient —
  is why the real-provider smoke is still owed.
- **"the original materials remain unchanged"** — the product wrote **nothing**
  into the research folder, every file it produced is under the task's own
  output area, and the pristine corpus is byte-identical afterwards; but the
  table's bytes do move, because **the walk changed it and the product did
  not**. Reading it the other way would make the deliverable's own two
  clauses — "requests a revision" and "the original materials remain
  unchanged" — contradict each other (§3.1).

## The two work orders' own acceptance clauses, clause by clause

The board states each work order's acceptance as a sentence, and the task
breakdown maps every clause onto the thing that carries it. **The mapping is
reproduced here with the witness that exists at the subject commit**, because
a clause with no witness named is a clause nobody is looking at.

**The counts below are counts of test *functions*, not of collected
cases.** A parameterised test collects as several cases, so the two numbers
are not the same, and **a record that gives one and calls it the other is a
record with a wrong number in it.** The reviewers' reports give case counts
because they ran the files; this table gives function counts because it
names the files.

### LC-P1-13 — *"transparent denominators, scores and failure cases; no
invented superiority, no skipped blocking tests; forced-restart task
continuation demonstrated; no unsafe file/network permissions"*

| # | The clause | The witness at `72154cd` |
|---|---|---|
| 1 | **transparent denominators** | `tests/evaluation/manifest.py` files **every** `tests/test_*.py` in a gate class, and `tests/test_evaluation_harness.py` (39 test functions) refuses a file that is in no class — the failure that caught this round's own new witness, and the reason a file's cases cannot enter no denominator |
| 2 | **scores and failure cases** | the harness **lists** the failures rather than averaging them away, and records the denominator's own count beside every rate |
| 3 | **no invented superiority** | T09 made **no** external comparison, on five checked facts, and `docs/acceptance/LC-P1-13-baseline.md` says what was measured and what was not — no ranking is printed |
| 4 | **no skipped blocking tests** | `tests/evaluation/aggregate.py`: *"a skipped witness is a failed blocker, not a neutral one"* — the protocol's sixth Phase 1 blocker, enforced rather than stated |
| 5 | **forced-restart task continuation demonstrated** | `tests/test_recovery_crash_matrix.py` (AT1–AT7) and `tests/test_recovery_resume.py` (13 test functions) |
| 6 | **no unsafe file/network permissions** | `docs/THREAT-MODEL.md` with `tests/test_threat_model.py` (34 test functions), checked against the outsider's own run |

### LC-P1-14 — *"an external reviewer can start fresh using docs and
reproduce the canonical task with own provider, or deterministic fixture
without provider; `uv run` and `pnpm` commands documented and actually
tested; artifact examples real; commit SHA and …"*

| # | The clause | The witness at `72154cd` |
|---|---|---|
| 1 | **an external reviewer can start fresh** | `scripts/outsider_path.py` in a **clean clone**, and `tests/test_outsider_path.py` (16 test functions) |
| 2 | **reproduce the canonical task** | `tests/test_public_fixtures.py` (22 test functions): the fixtures' answer keys are compared with what the product produced, and the keys are **not** the product's output |
| 3 | **with own provider, or deterministic fixture without** | the deterministic path ran; **the provider path did not** — T04 waits on the owner's answer (§1.4.2), and the judgement on the declared skip is the review's |
| 4 | **`uv run` and `pnpm` commands documented and actually tested** | `tests/test_readme_accuracy.py` (18 test functions) extracts the README's commands and **runs** them — a command in the README and not in the extraction is a failure |
| 5 | **artifact examples real** | `tests/test_paper_fixtures.py` (10 test functions) and `tests/test_analysis_report_render.py` — the examples are the fixtures' real artefacts |
| 6 | **commit SHA and …** | `tests/test_review_dossier.py` (12 test functions): every reference in the dossier resolves to a file this repository owns, at a line that is in it |

## What the evaluation harness measured

**The command:** `python -m tests.evaluation`, run on this machine against
the tree at the subject commit. **Its exit code was 2** — the protocol's
real-model smoke class was *selected*, could not be run, and is reported
NOT RUN with the reason. The tool did its job; the protocol is not
satisfied by this tree.

| The class | Result |
|---|---|
| Unit | 1510/1511 passed, 0 failed, **1 skipped** |
| Integration | 1133/1134 passed, 0 failed, **1 skipped** |
| Negative | 361/364 passed, 0 failed, **3 skipped** |
| E2E | 102/102 passed, 0 failed, 0 skipped |
| Repository gates | 369/369 passed, 0 failed, 0 skipped |
| **Real-model smoke** | **NOT RUN** — no real provider credential is configured in this environment and the run would spend money. **A mock-only success is insufficient under the protocol, so this class is reported as NOT RUN and is not counted as a pass.** |

| The Phase 1 blocker | Status |
|---|---|
| `clean-environment-readme` | **HELD** |
| `no-unauthorized-write-or-disclosure` | **FAILED** — 3 of 114 witness cases did not pass; a skipped witness counts against the blocker |
| `no-fake-citation-or-unsupported-number` | **HELD** |
| `no-repeated-side-effect-after-crash` | **HELD** |
| `no-verified-claim-from-rendering-checks` | **HELD** |
| `no-skipped-required-tests` | **HELD** |

**Five of the six hold, and the first one holds because of F6 below.** The
one that does not is a **skip**, and the three cases are the POSIX half of
a platform pair and the two 8.3 short-name witnesses — **a volume that
generates no short names skips the two, and no single runner of the CI
matrix carries all of it.** §6 of
[`LC-P1-13-evaluation.md`](LC-P1-13-evaluation.md) asks whether a declared
platform conditional should fail a blocker on the runner it does not apply
to, and **answers it nowhere**: the harness does not soften the rule,
because that is a judgement about the protocol and the protocol is the
ruler. **This document does not soften it either.** It is the owner's
question, and it is listed below.

**Four of the protocol's metrics are NOT MEASURED** — end-to-end task
success, evidence-locator validity, unsupported-claim detection and
revision consistency — and the report says which input each one is
missing. **A number with a denominator and a number that could not be
measured are different things, and the report keeps them apart.**

## What the gate measured that is missing, and handed over

**§1.3 says G5 measures and hands over, and that what the evaluation finds
missing is a finding for Phase 2 — recorded, not fixed inside the gate.** One
such finding came out of this gate's own exit-test item, and it is recorded
here with a witness, because **an observation nobody watches is a sentence,
and a sentence is not evidence.**

**The finding: the recovery pass exists at the layer and not at the
surface.** The crash matrix exercises it in-process; **nothing under
`src/labcairn/application/` calls `mark_uncertain` or `reconcile`.** So an
operation a crash left `ATTEMPTING` is never reconciled, and the next
`task run` plans a **second** operation for the same work — the abandoned
one stays `ATTEMPTING` for ever, and the audit log says the work was planned
twice.

**Measured, not read off a record.** A crash through the CLI in the window
*after the effect and before the confirmation* leaves one operation in
`ATTEMPTING`; the run that follows it exits 0 and leaves **two** — the
abandoned one, still `ATTEMPTING`, and a new confirmed one. **The side
effect is not duplicated**: the ingestion is idempotent, so the second run
writes no rows for material already on disk, and the store holds no second
copy. **So the repetition is of the operation, not of the bytes** — and the
gap between those two words is where the finding lives.

**The witness.**
`test_the_surfaces_do_not_reconcile_an_abandoned_operation` asserts the
current behaviour, **deliberately**. When Phase 2 gives the surfaces a
recovery pass, **that assertion fails** — and that failure is the signal to
replace it with one that says the abandoned operation was reconciled and no
second one was planned. **A test that is quietly deleted when the defect is
fixed is a test that was only ever a description.** Its own mutation is on
record: making the application layer adopt an `ATTEMPTING` operation — one
line — turns that witness red and leaves the other six green.

**What this means for the gate's own claim.** §2.3 asks the surfaces to come
back to a state the user can reason about: *no repeated operation, no
duplicated side effect*. **The second half holds; the first half holds only
when the crash came before the attempt was durable.** The breakdown's clause
is therefore **not discharged at this commit**, and this document says so
rather than rounding it off. The gate's exit-test item — *fault injection* —
**is** discharged: the injection runs through the CLI, and what it found is
the finding this section hands over.

## What this gate's own CI found, and what it cost

**Five defects, all of them found by running the gate rather than by reading
it, and all of them fixed at the subject commit.** They are listed here
because a gate review that only reports what the reviewers found would hide
the part of the gate that was broken while it was being built.

### S1 — the release gate had never been green, and one line of `env:` was the reason

**Found by:** the run of 2026-10-25. Both licence-audit legs failed, on
`ubuntu-latest` and on `windows-latest`, with
`FileNotFoundError: 'release-requirements.txt'` — a file nobody in this
repository has ever heard of, named by an error that said nothing about the
thing that was actually wrong.

**The mechanism.** The step that exports the runtime closure sets
`RELEASE_REQUIREMENTS` **in its own `env:`**, and an environment variable set
in one step is not set in the next. The step that audits the closure read the
variable, found it unset, fell back to a relative name, and looked for the
file in the working tree — where the export had deliberately *not* written it,
because the workflow keeps the tree clean at build time.

**What it would have let through.** The gate is a required status check, and
it had failed on every run it had ever been on. A reader of the release
record would have seen "the licence audit is a gate of its own" written in
prose and had no way to know the gate had never passed.

**Fixed, and watched.** The auditing step names the file, and
`tests/test_release_workflow.py` reads **every** workflow in the repository and
refuses a step that reads an environment variable nothing declared — the
step's own `env:`, the job's, the workflow's, or the platform's own set. The
witness is fed a step that is missing a declaration and required to name the
variable, so it cannot be a checker that passes everything. **The gate was
green on CI for the first time on 2026-10-25**, on both platforms.

### S2 — the witness on the shard costs passed without having looked at anything

**Found by:** reading the re-measure command while the witness was red.

**The mechanism, in two parts.** The re-measure command recorded the **run
id** as the commit the costs were measured at. A run id is not a git
revision, so `git diff` refused it, the changed-file list came back as
nothing, and the check read that as "nothing changed since the measurement" —
**and passed.** And the check itself had the same shape of hole: when the
commit could not be found it returned a sentence instead of a list, every
file's cost was read as zero, and the assertion passed. The comment in the
code said *"saying so is better than passing"*; the code passed.

**What it would have let through.** Every cost in the table would have become
unverified while the witness that exists to notice that stayed green. The
witness was the *only* thing standing between a stale partition and a slow
CI, and it had been switched off by a one-word mistake in a command.

**Fixed, and watched.** The command records the run's **head commit**, and the
check **fails** when it cannot look. A test says so: it feeds the check a
commit that is not in the checkout and requires the failure.

### S3 — six shards could not satisfy the balance limit, and the partition they produced was the best the costs allowed

**Found by:** the re-measurement, which reported a balance factor of 1.608
against a limit of 1.6 — and the arithmetic says no arrangement of six shards
does better.

**The mechanism.** One file is the floor: `tests/test_cli.py` takes 216
seconds on the Ubuntu runner, and no arrangement of the other files makes the
shard it is in shorter. With six shards the remaining 675 seconds spread over
five, so the ratio is 216 against 135 — **1.603, where the limit is 1.6.**

**What it would have let through.** The slack the re-measure rule works from
is `shortest × limit − longest`, and it had come out **negative**. A negative
slack says that *any* change to any file needs a CI run to re-measure, so the
tree could not be changed at all — and the partition that could not be
improved was the one being rejected.

**Fixed.** Five shards: the same costs give 216 against 169, a ratio of 1.28,
a slack of 53 seconds, and **ten jobs instead of twelve**.

### S4 — the re-measure command could not be run on the machine it was written on

**Found by:** running it.

**The mechanism.** `subprocess` with `text=True` decodes with the **locale's**
encoding, and this machine's locale is not UTF-8 — so reading a CI log died
with a `UnicodeDecodeError` on a byte no GBK sequence contains. The command
that is documented as "one command" could not be run at all here. It also
gave up on the first transient API failure, and the failure it died of said
nothing about what had gone wrong.

**Fixed.** The logs are read as UTF-8 whatever the locale says, with
`errors="replace"` so that one undecodable byte loses the byte rather than the
measurement, and a transient failure is retried.

### S5 — a type error only one of the two platforms could see

**Found by:** the Ubuntu job.

**The mechanism.** `ctypes.windll` exists on Windows and nowhere else, and
the type checker knows that. A `# type: ignore` would have been right on one
platform and wrong on the other — "unused" where the attribute is there, and
"missing" where it is not — and the wrong one is a red build on the other
platform. **This machine is Windows, so the local `mypy` was green and only
Ubuntu was red.**

**Fixed, and checked both ways.** The attribute is read the way a platform
that may not have it has to be read. `mypy --platform linux` now reproduces
the CI job locally, and the old code still fails it — which is the check that
settles it, rather than a local run that happens to be green.

### S6 — the skip that waited for a defect outlived the defect

**Found by:** running the evaluation harness on the subject tree, and then
reading what it skipped.

**The mechanism.** `tests/test_earlier_exit_demos.py` skipped G1's exit
demonstration on Windows, and the skip's own message named the defect it was
waiting for: the product compared a directory's two spellings and refused a
**new** file under a short-spelled one — a defect in
`src/labcairn/security/paths.py`. **That defect was fixed in G5's own first
piece of work** (§2.6 of the task breakdown), with two witnesses of its own in
`tests/test_security_paths.py`. **The skip did not notice.**

**What it would have let through.** The harness counts a skipped witness as a
**failed blocker**, and G1's demonstration is a witness of the protocol's
**first** Phase 1 blocker — *"a new user cannot complete a task from a clean
environment following the README"*. So the first blocker **did not hold on a
Windows runner, for a reason that had already been fixed**, and the record
said so as a known gap with a known owner (§1.4.1b). **A gate that waits for
a defect, and does not notice when the defect is fixed, keeps a closed gate
closed on a claim that is no longer being measured.**

**This is the third shape of the same hole.** G3's review found the
mechanism that does the watching unwatched; G4's found a rule that reads the
tests unwatched; this one is a **skip that names the defect it waits for and
is not itself watched**, so the name goes stale and the wait goes on. **The
skip said which defect it was waiting for, which is exactly what made the
stale skip look deliberate.**

**Fixed.** The skip is removed, and the demonstration is watched on every
platform: **six tests, zero skipped, on this machine** — and **the Windows
runner, which is the only place the defect showed, is where the removal is
proved.** Its log for the shard that carries the file reads
`tests\test_earlier_exit_demos.py ......` — six dots, no `s` — where the
same line read `s..s..` before, and the `g1_exit_demo` cases carry a real
`call` duration rather than none. **The demonstration that had been dark
since G1 closed ran, on the runner where it fails, and it passed.** The
first blocker is no longer held down by a defect that is gone.

## The independent review

**Two reviewers, one per scope, and neither wrote a fix into this repository.**
Both measured the gate commit `72154cd` in a worktree of their own, and both
reported.

**The numbers below are the coordinator's, not the reviewers'.** Every
finding was re-checked before it was acted on, and the four that carry the
verdict were re-checked by **re-running the mutation** rather than by
reading the report's account of it. **The reviews' own numbering is kept**,
so `R1` is the first finding of the first review and `R11` the first of the
second; this document's own findings are `S1`–`S6`, above.

### The product-and-measurement scope — verdict FAIL

**The report:** [g5-review-product.md](g5-review-product.md). **Measured at**
`72154cd`. **Verdict: FAIL.** Its reason is G4's reason again: *a property
table can be entirely clean and the review still fail.*

| # | The finding | The coordinator's re-check | Fixed |
|---|---|---|---|
| **R1** | the crash matrix does not watch whether the recovery path performs a side effect | **the mutation re-run**: the probe writes the file, **40 of the protocol's fourth blocker's own witnesses stay green**, and 51 with three more recovery files. The control turns `test_at5_reconciliation_detects_absent_write` red, so the branch is reached and the *verdict* is watched — **the write is not** | yes — three witnesses, and the coordinator re-ran the mutation against them |
| **R2** | the public fixture corpus is not an oracle: no produced report is compared with any of its answer keys | **re-checked**: `expected_artifact_checks` is read by one file, and the harness measures the *other* corpus. The abstention metric is NOT MEASURED for a reason the report prints and the tree contradicts | yes — the harness measures the public corpus, and the metric is measured over it |
| **R3** | the protocol's **first** blocker reports FAILED because of a skip whose defect is fixed | **re-checked**: the defect is fixed, the skip is not | **yes — and this is S6 below: the coordinator found it first, and the reviewer found it independently** |
| **R4** | the answer key's independence from the product is not witnessed | **the mutation re-run**: the product's mean broken and the key replaced with the product's own output, **41 green**. The control: the same break reds 8 tests elsewhere, because *that* corpus's key was computed with Python's `statistics` | yes — **twice**. The first fix still read the derivation, so a derivation moved with the key passed; the second takes the target from the question's id and cross-checks it against the prompt |
| **R5** | the fault injection **through the surfaces** is not delivered | **re-checked**: the file does not exist and no test injects a crash through the CLI or the service | yes — a new end-to-end file, and it **found a finding of its own** (see "What the gate measured that is missing") |
| **R6** | the harness prints two reasons that are false at the commit it measures | **re-checked**: the public fixtures are in the tree and the no-evidence fixture is in the tree | yes — the reasons are read out of the tree |
| **R7** | an unmarked test file can be moved into a protocol class and the denominator silently grows | **the mutation re-run**: the file moved from `repository` into `unit`, **40 green** | yes |
| **R8** | the report's "small denominator" note is never rendered and nothing notices | **the mutation re-run**: the note never rendered, **40 green** | yes |
| **R9** | the board says the two work orders are `NOT STARTED` at the commit that delivers them, and the watch cannot see it | **re-checked, and it was worse than reported**: the watch was reading the SHA out of the merge's *subject*, so every comparison failed, every candidate was discarded, and **the watch had never looked at anything** | yes — and it now fails, on the board, correctly |
| **R10** | the recovery metric's denominator is labelled as a thing it does not count | **re-checked**: 8 collected cases, 10 injected faults, 4 distinct crash points | yes — the denominator is read out of the matrix |

### The documents, claims and release scope — verdict PASS WITH NOTES

**The report:** [g5-review-records.md](g5-review-records.md). **Measured at**
`72154cd`. **Verdict: PASS WITH NOTES**, and the report says plainly that
this verdict **does not close the gate**, because the exit test names the
real-provider smoke and it has not run.

| # | The finding | The coordinator's re-check | Fixed |
|---|---|---|---|
| **R11** | §1.4.1b misattributes which skip failed which blocker, and the blocker table it cites is stale | **re-checked**: the provider-credentials file witnesses **no** blocker, and the second blocker's recorded reason was incomplete | **yes — and this is S6's other half** |
| **R12** | the sixth blocker's "HELD" is not earned: a required CI test is skipped and none of its three witnesses looks | re-checked | yes |
| **R13** | nothing watches a shipped document for superiority language | **the mutation re-run**: a sentence in a record, **nothing red** | yes — and the new watch **caught this gate's own review report**, which quotes the sentence it planted |
| **R14** | the parallel-run temp isolation is defeated by `TMPDIR`, and its own witness does not watch for that | **re-checked**: `tempfile.gettempdir()` consults `TMPDIR` first on every platform, and **this machine's `TMPDIR` points at another project's directory** | yes — in the conftest, in the harness's runner, and in the outsider's own environment |
| **R15** | the release gate's font check is by file name, and the font audit's own list names an extension it does not know | re-checked: the GPL font's bytes as `.sfd` and as `.woff2` both passed the gate | yes |
| **R16** | the README's command extraction misses commands outside a shell fence and inside an inline span, and the gate's two extractors disagree | re-checked | yes — one extractor now, read from the walk script |
| **R17** | the threat model's enumeration of the writes in `src/` is not watched | **the mutation re-run**: a seventh write in a module the list has never heard of, and the witness **does** red | yes |
| **R18** | the protocol's blocker count is wrong in five shipped documents | re-checked: the protocol lists six | yes — five one-word corrections |
| **R19** | a citation is outside the watching regex's extension list | **the mutation re-run**: `.toml` dropped from the list and the witness **does** red | yes |
| **R20** | two in-page anchors cannot resolve, and no test checks any in-page anchor | **re-checked**, and it is worse than a count: the **English README is bilingual**, and the broken anchors are in its Chinese half | yes — the check is written, and the Chinese heading now has the spaces the English one has |
| **R21** | the release notes carry a limitation that was fixed before this commit | re-checked | yes |
| **R22** | `.env.example` says Phase 1 reads no environment variable, and the provider layer reads one | re-checked | yes |
| **R23** | the outsider walk's database reported a disk I/O error under concurrent load | **not reproduced**, and the reviewer did not isolate it either: the failing run had `TMPDIR` set **and** a build running into a second virtualenv on the same volume. The same sixteen tests passed alone | the `TMPDIR` half is fixed (R14) |
| **R24** | the evaluation report asserts that the public fixtures are not in the tree | re-checked | yes — the same fix as R6 |

### What the two reviews found that this gate had found on its own

**S3 and R3 are the same defect, found twice, by different parties, on
different trees.** The coordinator found it by running the gate's own CI and
reading the blocker table; the reviewer found it by breaking the product's
path layer on a volume that has 8.3 short names and putting the old code
back. **That is the strongest kind of evidence there is** — a defect that
two independent readings produce from different directions is not one
person's blind spot.

### The verdict

*(to be settled — see "The verdict" below)*

## The verdict

*(to be filled in)*

## The decisions that are still the owner's

**Four decisions, and none of them is an engineering task.** They are
stated in [`docs/plans/LC-P1-13-14-task-breakdown.md`](../plans/LC-P1-13-14-task-breakdown.md)
§1.4 with what each one costs, and this gate did not settle any of them.
**What follows is what each one is waiting on, as the gate measured it.**

### 1 — The copyright and the root licence (§1.4.1)

`LICENSE.PENDING.md` says in its first line that it is not a licence, and
**nothing in this repository is licensed to anyone.** The NOTICE says so too
and grants nothing. **The font half of this is measured and it is not the
obstacle**: no third-party font file reaches any artefact, so the GPL font
reportlab bundles does not attach to what a user receives
([the font audit](LC-P1-14-font-licence-audit.md)). **The copyright half is
the owner's, and until it is settled no open-source claim may be made
anywhere.**

### 2 — Which provider, and whose credential, for the real smoke (§1.4.2,
with §1.4.1b)

**The measurement the decision needs is above.** The harness's exit code was
**2**: the real-model smoke class was selected, could not run, and is
reported NOT RUN with the reason. No credential exists on this machine, and
`.env.example` says Phase 1 reads no environment variable at all.

**§1.4.1b is the same decision seen from the other side**, and the
measurement has sharpened it. The protocol's six Phase 1 blockers: **five
hold.** The one that does not is the second, and it does not hold because
of three **skipped** witness cases — the POSIX half of a platform pair, and
the two 8.3 short-name witnesses, which a volume that generates no short
names skips. **No single runner of the CI matrix carries all of it.** So the
question is not only "does a declared skip count" but "**does a skip that
is the platform's own conditional count**", and the harness answers neither
because **that is a judgement about the protocol and the protocol is the
ruler.**

### 3 — The competitor baseline's scope (§1.4.3)

**The work was done to Option C — no external comparison — on five checked
facts, and it prints no ranking.** **That choice was the work's, not the
owner's**, and this gate does not record it as settled. What the baseline
record does say is what was measured and what was not, with the
denominators, and the four task-level metrics are **NOT MEASURED** with the
missing input named.

### 4 — Whether G1 and G2 get a retro-review (§1.4.4)

**Both gates closed on a review by the party that also wrote the fixes**,
and the board's rule was applied to G3 and G4 and not to them. **This gate
does not change that**: the two G5 reviewers were dispatched for G5, and
they wrote none of G5's fixes — but a reviewer of G5 is not a reviewer of
G1. **Either the two gates get a retro-review from someone who wrote none
of their fixes, or their rows say that they did not get one.** The second is
cheaper and the first is honest, and **the board says the second is not
enough** — which is why it is the owner's to take.
