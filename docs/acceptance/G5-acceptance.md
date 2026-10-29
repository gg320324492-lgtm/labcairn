# G5 — Gate review

**Gate:** G5 — Public alpha. Work orders **LC-P1-13** (evaluation, fault
injection and the competitor baseline) and **LC-P1-14** (the public alpha
handoff: the delivery documents, the release contents, the review dossier and
the licence audit).
**Exit test:** *"outsider fresh install, 3 fixtures, fault injection, docs and
real-provider smoke"*.
**Subject:** `main` @ `72154cd27fc99005ab1ee22c6d5e58608e6b5b2f` — the merge of
PR #116, which carries the whole of G5.
**Verdict:** **PASS WITH NOTES** — four of the exit test's five clauses delivered and
watched; the fifth, the real-provider smoke, has not run and is the owner's decision.
The reasoning is in "The verdict" below, and the notes it carries are in "The
decisions that are still the owner's".
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
| 5 | **real-provider smoke** | T04 | **Not run as a standing witness.** No credential is configured in this tree, and `tests/test_provider_credentials.py:285` is skipped with its reason written into the test. **The project has made one live call in its history** — `b237751`, 2026-10-16, on a credential the owner supplied, which is the run that discharged LC-P1-03's own *"real smoke on at least one provider"*. A manual probe that ran once is not the protocol's real-model smoke **class**, and the harness reports it NOT RUN with exit code 2. Whether a declared, reported skip is a blocker that failed is the judgement the independent review had to make — see below. **Corrected 2026-10-28:** the class now has the witness file T04 named and never wrote — `tests/test_real_provider_smoke.py` — and **it ran, twice, on a credential the owner supplied for this purpose**: model `MiniMax-M3.1-Flash`, protocol `anthropic`, endpoint `https://api.minimax.cn/anthropic`, fingerprint `db47efa5986d25d9bae6a7d9788a5b0b7d5db0240a83c29aefb42ac0420f385c`. `tool_calls` **ok**, `usage_reporting` **ok**, `structured_output_native` **unsupported** (*probe raised UserError*), `structured_output_prompted` **unsupported** (*probe raised KeyError*); the two records were identical but for `observed_at`. Those two refusals are pydantic-ai's profile declining **before a request is sent**, so the capability remains **unmeasured**, not absent — §2.14 of the release notes stands. **What has not changed:** the *required* checks still name no credential, so the default harness run reports the class NOT RUN and exits 2 — and one never will, because a required check that can only pass where a secret exists is a check branch protection waits on forever. **What did change afterwards:** the credential is now configured on the repository, and `.github/workflows/provider-smoke.yml` spends it — on a schedule and on demand, and **it has run there**: dispatch 40663728369 at `0adfbe3`, 2026-10-28 09:22 UTC, green, printing the same endpoint fingerprint as the two local runs above. The gate class is therefore discharged by that workflow, not by every pull request; §1.4.2's remaining half is whether that shape satisfies the protocol's intent, which is the owner's call. |

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
the evidence it produced. **This document first said "two of them are narrower
than the sentence says"; that undercounted its own record.** Reading the walk's
§5, §6 and §7 against the sentence, **five of its clauses are narrower than it
says**, and each is listed here with the finding that measured it:

- **"configures an eligible LLM provider"** — Phase 1's **default offline run**
  reads no environment variable, so on a fresh workspace there is no provider to
  configure. The deterministic fixture path is what ran. The record says which
  steps were made against a fixture
  (§5), and the protocol's own rule — that a mock-only run is insufficient —
  is why the real-provider smoke is still owed.
- **"receives a report and deterministic scientific plot"** — **neither had a
  surface of its own when the walk ran**: no CLI command rendered a report or
  drew a figure, and the service had no route for either, so the last two steps
  of the sentence needed a Python import rather than a command. The record's finding
  [§7.1](LC-P1-14-outsider-path.md) is the evidence, and
  [`RELEASE-NOTES.md`](../RELEASE-NOTES.md) §2.1 carries it into the handoff.
  **Corrected 2026-10-27:** both now have surfaces — `labcairn task report` and
  `POST /report`, `labcairn task figure` and `POST /analysis`, the figure behind
  the `task approval-request` / `task approval-grant` chain — so the clause is
  reachable without a Python import. **The workbench's Figure panel is a third
  entry point** — ask, grant, draw — and the walk's own run was made through the
  layer before the commands existed.
- **"an evidence ledger"** — the ledger, its checks and its gate are real and
  witnessed, **but no surface operation writes a record or an anchor**: the walk
  writes the claim's address and the record that rests on it itself. So the
  report carries a real claim cited to a real cell, and **the claim was made by
  the walk, not by the product** (§7.3, §2.2).
  **Corrected 2026-10-27:** the layer's `record_claim` writes the anchor and the
  `extracted` record now, and the surfaces reach it — `labcairn task claim` and
  `POST /claims`, with `labcairn sources addresses` and
  `GET /sources/{source_id}/addresses` listing the addresses — so the walk
  records through the product. **What is still the caller's is the claim's
  words**: nothing extracts, proposes or verifies them, and no surface runs C1,
  C2 or C3. [§7.3](LC-P1-14-outsider-path.md), [§2.2](../RELEASE-NOTES.md).
- **"requests a revision"** — a second revision **is** produced and v1's bytes are
  unchanged, but the attempt to recompute the report from the revised material is
  **refused** (the chain names the material twice with different hashes), so the
  second revision still rests on the material the claims were read from
  (§7.2, §2.3). This is a Phase 2 finding, recorded rather than fixed.
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
the tree at `c362317`. **Its exit code was 2** — the protocol's real-model
smoke class was *selected*, could not be run, and is reported NOT RUN with
the reason. The tool did its job; the protocol is not satisfied by this
tree.

**Five of the six Phase 1 blockers hold.** The one that does not is the
second, and it does not hold because of three **skipped** witness cases —
the POSIX half of a platform pair, and the two 8.3 short-name witnesses,
which a volume that generates no short names skips. **No single runner of
the CI matrix carries all of it**, and that is the question §1.4.1b asks.

**Three of the protocol's metrics are measured, and one of them was not
measured before the gate.** The **abstention metric is 1/1** — the
no-evidence fixture's honest *"the material does not say"* — where it was
NOT MEASURED before, because the harness measured the wrong corpus. The
**recovery metric's denominator is 4**, the number of distinct crash points
the matrix injects, **read out of the matrix itself** rather than counted
from a number somebody wrote down; and the numeric extraction is **84/84**.
Four metrics remain NOT MEASURED, and the report names the missing input
for each.

**And the report says what the exclusions are.** The sixth blocker's row
carries the excluded required tests **by name, with their reasons**, and
says that whether a declared skip fails the blocker is the owner's ruling
and not the harness's.

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

### The product-and-measurement scope — verdict FAIL, and PASS after the re-verification

**The report:** [g5-review-product.md](g5-review-product.md). **First
measured at** `72154cd`, and **re-verified at** `598e788`. **First verdict:
FAIL. Verdict after the re-verification: PASS.** The first verdict's reason
is G4's reason again: *a property table can be entirely clean and the review
still fail.*

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
| **R11** | the residual of R7: the clause is the bound, and the clause is unwatched prose | **the mutation re-run**: moving a file into a protocol class **and taking its clause with it** was green across fifty-eight tests | yes — and the **fix's own control settles it**: the same table edit, with the *file* declaring its class as well, is green, because the declaration is a statement and the table is not — so the anchor really is outside the table |
| **R12** | the fix for R11 landed **red**: the markers went in after the import block, and six files' import order stopped satisfying the linter | **two independent readings found it** — the coordinator's own check of the fix, and the reviewer's, and the tree's own witness found it first: the README's own command list is *run*, and `uv run ruff check .` did not pass | yes — and **the gate could not have closed on the commit that introduced it** |

### The documents, claims and release scope — verdict PASS WITH NOTES

**The report:** [g5-review-records.md](g5-review-records.md). **First
measured at** `72154cd`, and **re-verified at** `8c0eb40`. **Verdict: PASS
WITH NOTES**, and the report says plainly that this verdict **does not close
the gate**, because the exit test names the real-provider smoke and it has
not run.

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

### The four the re-verification found, and what became of them

**The re-verification is where the gate's own record was caught saying
something false.** R26 is the example: this document said the `TMPDIR` hole
was fixed *"in the conftest, in the harness's runner, and in the outsider's
own environment"* — **and the third of those three was not fixed**, because
the window that was to fix it was interrupted. **The reviewer measured it
rather than reading it**, and it is fixed now, with a witness of its own.

| # | The finding | Fixed |
|---|---|---|
| **R25** | the superiority watch's unit is a line, and a line break defeats it | yes — the unit is the **paragraph, joined**, so a wrap cannot hide a claim, and a sentence that **denies** is not a claim: the review dossier's own *"no claim that LabCairn is better than any upstream project"* is what the first attempt called a claim |
| **R26** | the walk's own environment still does not set `TMPDIR` | yes — and **this document had said otherwise** |
| **R27** | the quickstart still said seven, and a record said the wrong number was gone | yes — and that record's sentence **is** true now, because the fifth document says six |
| **R28** | the blocker table was corrected in one document and not in the two that carry it | yes — the table is in both acceptance records now |

### What the two reviews found that this gate had found on its own

**S3 and R3 are the same defect, found twice, by different parties, on
different trees.** The coordinator found it by running the gate's own CI and
reading the blocker table; the reviewer found it by breaking the product's
path layer on a volume that has 8.3 short names and putting the old code
back. **That is the strongest kind of evidence there is** — a defect that
two independent readings produce from different directions is not one
person's blind spot.

## The verdict

**The gate is closed. The verdict is PASS WITH NOTES.**

**The exit test names five things, and four of them are delivered, measured
and watched.** The fifth — the real-provider smoke — **has not run as a standing
witness**, and it cannot here: no credential is configured in this tree, and the
in-suite witness that would run it is skipped with its reason in the test. **The
one live call this project has made** — `b237751`, 2026-10-16, on an owner-supplied
credential against a live Anthropic-protocol endpoint — discharged **LC-P1-03's
acceptance clause**, and it is not the protocol's real-model smoke **class**, which
the harness still reports NOT RUN with exit code 2. **That is the owner's decision
and this document does not make
it**; §1.4.2 asks it and §1.4.1b asks the neighbouring one, and the
harness answers neither on the owner's behalf.

**Corrected 2026-10-28 — the sentence above is now half stale.** The class has
a witness file (`tests/test_real_provider_smoke.py`, the one
`manifest.REAL_MODEL_SMOKE_FILE` had named since T04 without existing), and it
**ran twice** on a credential the owner supplied for this purpose, against
`MiniMax-M3.1-Flash` on an Anthropic-protocol endpoint: `tool_calls` and
`usage_reporting` **ok**, both structured-output capabilities **unsupported**
because pydantic-ai's profile declines before a request is sent. The in-suite
witness is no longer unconditionally skipped — it skips when no credential is
named, which is still every CI run — so **the harness still reports the class
NOT RUN offline, and §1.4.2 is still the owner's to answer**. What changed is the
kind of the gap: it was "there is nothing to run", and it is now "the thing to
run needs a secret this repository does not hold".

**Both reviewers wrote none of the gate's fixes.** The first one's verdict
was **FAIL** — on a property table that was entirely clean, which is G4's
reason again — and after every finding was fixed it **re-ran its own eleven
mutations against the fixed code and passed**. The second one's verdict was
**PASS WITH NOTES**, and every one of its fourteen was re-run by the
reviewer that wrote them.

**And the gate found things on its own.** Six defects the gate's own CI
found (S1–S6), and one the gate's own end-to-end test found while it was
being written — the surfaces never run the recovery pass — which is **handed
over rather than fixed**, because §1.3 says G5 measures and hands over.

**What is not claimed.** The gate did not run a real model, so nothing here
is a measurement of model quality. It did not compare against another
system, so nothing here is a comparison. And the real-model smoke class of
the protocol **is still owed**.

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
reported NOT RUN with the reason. No credential is configured in this tree, and
`.env.example` says Phase 1's **default offline run** reads none — the provider
layer reads one, but only where a workspace's `providers.json` names it.

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

**The harness does not answer it, and that is deliberate.** It reads the
excluded required test out of the CI's own shard list and **states the
exclusion in the blocker's own row**, naming the file and saying that
whether a declared skip fails the blocker is the owner's ruling. **The
harness did not make the ruling for the owner, in either direction.**

**What the owner's two answers would each cost.**

- **"A declared skip does not count, and the protocol says so."** Then the
  protocol is amended — the sixth blocker says what a declared, recorded
  skip is — the amendment is recorded, and the harness's exclusion becomes
  the protocol's own wording rather than a note beside it. **The cost:** the
  gate's exit test then says five classes ran when one of them did not, and
  the report has to carry the exception everywhere it says "ran".
- **"A declared skip counts, and the gate waits for the credential."** Then
  the harness's sixth blocker is **FAILED** on this tree, in writing, and
  the gate does not close. **The cost:** the licence question of §1.4.1 and
  the provider question of §1.4.2 both become blocking for the alpha, and
  a machine with no credential cannot close a gate about a research alpha.

**Ruled 2026-10-28, after this gate closed and after PR #119 merged.** The
credential is configured on the repository; the probe file `T04` named exists
and has run — locally and, dispatch 40663728369 at `0adfbe3`, on GitHub, with
the same endpoint fingerprint each time. `provider-smoke.yml` spends it on a
schedule and on demand. **The owner's answer to §1.4.2 is that this shape
discharges the fifth gate class:** a required check that could pass only where
a secret exists is a check branch protection waits on forever, and amendment
C-1 forbids dressing that up with a path filter. The default offline harness
run still reports the class NOT RUN, and that stays on the record as what the
offline path actually says, not as a claim that the class ran. **§1.4.1b —
whether a declared skip fails the sixth blocker — is a different question and
remains the owner's.** The two are neighbours and have been treated as one in
earlier drafts of this file; the ruling above speaks to the class, not the
blocker, and the blocker's row still carries the platform-conditional skips
this section names.

**Ruled 2026-10-29, and the harness carries the answer now.** The paragraphs
above stand as what was true when this gate closed; the owner's ruling has
since landed in `tests/evaluation/aggregate.py`, and it is **neither bullet
above whole**:

- A skip whose reason names **a fact of the machine** — an OS, a filesystem, a
  volume that generates no 8.3 short names — **does not fail** a blocker. Nor
  does a test in a class the owner ruled discharged outside the offline run,
  nor a file a partial run simply did not select, which is scope and not a
  skip.
- **Any other skip fails it**, by name and with the reason the test gave — for
  a blocker's own witness cases and for the sixth blocker's required CI tests,
  which are read out of the CI's own shard list.
- The accepted exclusions are **named in the row, case by case, in the tests'
  own words.** An acceptance that hides what it accepted is the same
  invisibility this blocker exists to close.

**Which is why the second blocker's status changes.** It was FAILED on Windows
because three of its witness cases skip for platform facts — the POSIX half of
a pair, and the two 8.3 short-name witnesses — and no single runner of the
matrix carries all of them. The owner was asked whether the ruling covers
witness cases and not only the sixth blocker's required tests, and chose **all
blockers**. [The evaluation record](LC-P1-13-evaluation.md) carries the run
this was measured on.

**What this is not.** It is not an amendment of `EVALUATION.md`, whose sixth
blocker still reads *"Required CI tests are skipped, ignored or only pass by
mocking the actual behavior under acceptance"*. The protocol is the ruler; this
is the harness's reading of one clause in it, recorded so the reading can be
checked against the ruling.

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
