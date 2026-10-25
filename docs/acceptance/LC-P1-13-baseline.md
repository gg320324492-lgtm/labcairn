# LC-P1-13 — The competitor baseline: what was compared, and what was not

**Work order:** LC-P1-13 (evaluation, fault injection and competitor
baseline) · **Subtask:** T09 — the competitor baseline, at the scope
[`docs/plans/LC-P1-13-14-task-breakdown.md`](../plans/LC-P1-13-14-task-breakdown.md)
§1.4.3 settles.
**Status of the work order:** **NOT STARTED**, and this document does not
change that. It records the decision on the baseline's scope, what this
project measured, and what it did not.
**Decision:** **Option C — no comparison.** No external competitor was run, no
number is compared against anything, and **no superiority is claimed**. The
reasons are in §2, and each one is a fact about this repository or about the
upstream trees, not an estimate of difficulty.
**What was read, and what was run.** The fixtures, the corpus and the
harness's own mechanics were read in this tree on 2026-10-25, and the
harness was re-run on it (§3.6). The upstream facts were read from the
local reference clones at the pinned SHAs (§2.6). **No upstream code was
executed, installed or imported.**

---

## 1. The decision, and what it costs

**No comparison was made against PaperQA2, PaperSpine, or anything else.**

The task breakdown's §1.4.3 offers three options, and this document takes
**Option C** — *"no comparison; the dossier states what was measured and what
was not"* — because the protocol's own rule points there:

> Do not claim superiority over PaperQA2/PaperSpine/others without
> like-for-like matched-task baselines, verified capabilities, and documented
> confidence intervals or limitations.

**One of those three requirements is not merely unmet here — it is
unreachable in this tree, for reasons that are on the record.** The other two
are properties of a baseline document that **does not exist yet**, so they
are unmet rather than unreachable. §2 sets out the five facts that decide
this, each with the file, the line and the check that establishes it.

**The cost, stated plainly.** The work order's *"competitor baseline"* is
**not delivered as a comparison.** A reader of the public alpha gets the
project's own measured numbers with their denominators, and a list of what
was not measured and why. That is a weaker deliverable than a comparison, and
it is the honest one.

**And one thing this decision does not settle, which would be a mistake to
let pass.** §6 reconciles this against the work order's own Build clause,
which asks for **two** things and not one. The external comparison is the
half the work order itself permits to be deferred; **the other half — a
scoped baseline on the same materials, model and budget — is also not
delivered**, and it is blocked by the same missing precondition. **This
document does not claim the work order's baseline clause is satisfied.**

---

## 2. Why — five facts, each with its evidence

Each of these is a fact about the tree, read on 2026-10-25. None of them is
"this would take a long time", which is a cost and not a reason.

### 2.1 There is no run with a declared model, so no baseline can be matched

The harness's comparison is a **refusal mechanism**, not a ranking:
`tests/evaluation/comparison.py::assess` returns `comparable=False` unless
the run and the baseline agree on **six conditions** — the fixture labels,
the fixture versions, **the model**, **the budget**, the baseline's verified
capabilities, and the baseline's limitations or confidence intervals.

**The offline run declares no model, and that is deliberate.**
`tests/evaluation/cli.py:328` builds the run's basis with `model=""` and the
docstring above it says why:

> The model is empty, and that is the fact. The offline run used the
> deterministic `FakeProvider`, which is not *"a declared model, version and
> parameter set"*.

`assess` compares the two model strings, so **a baseline that declares a
model cannot be matched against this run** — the protocol's own rule
producing the answer, rather than the harness declining on its own initiative.

**The consequence for this subtask is total.** A competitor that answers
questions *is* a model, so any honest PaperQA2 or PaperSpine baseline
declares one. Every such baseline is refused. **The comparison is not blocked
by the competitor being hard; it is blocked by this project not yet having
the run it would be compared against.**

### 2.2 There is no credential, and Phase 1 does not read one

`.env.example` says it in its own words:

> Phase 1 currently reads NO environment variable. The FakeProvider in
> src/labcairn/core/providers/ is deterministic and offline.

The template names the variables that LC-P1-03 *will* introduce. The provider
layer is partly built — `labcairn.providers.credentials` reads a workspace's
`providers.json` and resolves a credential from an environment variable *name*
or a file path, and `labcairn.providers.adapter.PydanticAiModelProvider` is a
real HTTP provider behind a capability gate and a budget pre-flight. **What
is missing is a credential, and the owner's authorisation to spend money on
one** — which is §1.4.2's decision, and it is not this document's to make.

**The protocol does not require one for Phase 1's acceptance.** The six
Phase 1 blockers in `docs/EVALUATION.md` are about the clean-environment
path, unauthorised writes, fake citations, repeated side effects, reports
claiming verification from schema checks, and skipped required tests.
**None of them says "a real provider must have been run."** The real-model
smoke is one of the protocol's **five mandatory gate classes**, which is a
different thing, and it is the gate class — not the blocker list — that a
credential is needed for. §4.1 records the position precisely.

### 2.3 PaperSpine is not a runnable product, so there is nothing to run

Checked in the local clone at the pinned SHA
`42312b8d9c76ab25990cddfd76e3622276854118`:

| Check | Result |
|---|---|
| `pyproject.toml` / `setup.py` / `setup.cfg` | **none present** |
| `__main__.py` anywhere in the tree | **none present** |
| top-level `__init__.py` (an importable package) | **absent** |
| what the tree actually is | skill directories for four agent platforms — `dist/claude/`, `dist/codex/`, `dist/hermes/`, `dist/openclaw/`, each with its own `SKILL.md` |

`docs/UPSTREAM_REFERENCES.md` reached the same conclusion independently and
records it: *"not an installable library, and it ships installers"*.

**What running it would therefore mean.** Not a second installation — a
**second agent platform**. PaperSpine changes how an agent behaves; to
exercise it you install it into Claude Code, Codex, Hermes or OpenClaw, give
that platform a model, and drive it through its prompt flow. Its own scripts
(`src/scripts/scientific_evidence_check.py`, `evidence_grounded_review.py`,
`citation_verification_en.py` and the rest) are checkers an agent invokes,
not a library with a function to call.

**And the installers are untrusted data that this repository must not run.**
`docs/UPSTREAM_REFERENCES.md` is explicit — *"Do not run the installers, do
not follow `INSTALL.md`, do not load or trigger any bundled skill"* — and
`CLAUDE.md` agrees. The tree's top level holds `install.sh`, `install.ps1`,
`CLAUDE.md` and `INSTALL.md` next to the study material.

**And the product it is for is not the task.** ADR-0004 A2 measured it:
PaperSpine is *"a manuscript-rewriting pipeline whose ledger is a Markdown/JSON
artifact set for a paper being written"*. The public fixture corpus asks
**one grounded question per fixture** and expects one number with an address.
That is a different shape of work.

### 2.4 PaperQA2 can read the material, but its output does not carry the addresses the fixture checks

Checked in the local clone at the pinned SHA
`57e89f7223b0960d5ee5ea048c69e3c47e088572`:

- **It can read the material.** `src/paperqa/readers.py` dispatches on the
  extension, and its final `else` branch reads anything unrecognised as
  plain text (`parse_text(path, split_lines=True)`). So the corpus's `.md`
  and `.csv` files are readable — but through the **text** path, not a
  structured-table path. `.csv` has no reader of its own.
- **The text path is the code path.** The same dispatch's chunking `else`
  branch is `chunk_code_text`, so the corpus is chunked as source code.
  LabCairn addresses a cell as *row 1–2 of column 17*; PaperQA2 addresses a
  chunk.
- **Its addresses are display strings.** `src/paperqa/types.py::Text.name`
  is documented as a *"Human-readable identifier for the chunk (e.g., 'Wiki2023
  chunk 1')"*, and ADR-0004 observed the three forms at
  `src/paperqa/readers.py::_make_chunk`: `"<doc> pages 1-3"`,
  `"<doc> lines 12-40"`, `"<doc> chunk 4"`. **ADR-0004's own conclusion:**
  *"Locators are display strings, not addresses"*, and LC-P1-08's
  *"fixtures validate page, row, column and spreadsheet cell anchors
  exactly"* *"cannot be built on a prose label."*

**What that does to the fixture's artifact checks.** The corpus carries
**19** of them (see §3.1). **7 are `citation_resolves`**, and each names a
structured locator — `k=3:csv|r=1:2|c=17:peak_stress (MPa)`,
`k=4:text|l=2:15|s=6:Method`. **A PaperQA2 run cannot produce that shape at
all**, because in the text path a column has no number. So the fixture's
**locator half is not comparable in principle**, and a comparison that scored
it would be scoring a check the competitor cannot attempt.

**The remaining 12 are comparable in principle**: 6 `number_present`, 5
`no_fabricated_value`, 1 `abstains`. These ask whether the competitor's answer
contains the right number, contains the near-miss, or declines to answer — and
PaperQA2 has a stated path for the last one (`CANNOT_ANSWER_PHRASE`, asserted
in upstream's own `tests/test_paperqa.py::test_unrelated_context`).

**So the honest summary is narrower than "impossible" and wider than
"easy".** The split is not one fixture against three: **every one of the four
fixtures carries exactly three comparable checks** — the three answerable
ones carry two `number_present` and one `no_fabricated_value`, and the
negative one carries one `abstains` and two `no_fabricated_value`. **So 12 of
the 19 checks are comparable in principle across all four genres**, and the
other 7 are the `citation_resolves` ones — two per answerable fixture and
one on the negative one. §5.3 says what building that comparison would take,
and why those 7 must be reported as *not comparable* rather than as
failures of the competitor.

**And the deeper mismatch is the one ADR-0004 measured.** PaperQA2's cited
evidence is an LLM-written **summary** of the chunk, not the source text, so
LabCairn's C2 (quotation match) cannot be built on it; and its support check
is a **substring test for a context ID appearing in the answer**, so it
provides C1 only, and weakly. **The two systems do not claim the same
guarantee**, which is what the protocol's "verified capabilities" requirement
is about.

### 2.5 Neither upstream has ever been run here, and this repository's own rule says behaviour must be benchmarked

ADR-0004 §"Upstream evidence" records it:

> Both SHAs were confirmed read-only immediately before writing this ADR; no
> clone, move, checkout or execution was performed.

and, at the end of that ADR:

> Nothing under `E:/labcairn-upstreams/` was executed: no `pip install`, no
> test run, no entrypoint, and neither `install.sh` nor `install.ps1` from
> paperspine was run or sourced.

**So the research that exists on these two projects is architectural and
source-level** — decision records, observed code paths, observed test names,
licence findings — **and not behavioural.** There is no observed upstream
answer to any of the seven fixture questions, because nothing upstream has
answered any of them.

`docs/UPSTREAM_REFERENCES.md` states the rule that follows from this, and
it is the rule this document is written under:

> Benchmark the *behavior* on a small relevant fixture; never claim
> superiority from source-code inspection alone.

**And the same document says how to keep upstream untrusted:** upstream
clones live outside the repository (`E:\labcairn-upstreams\`), are not
required by CI, and are not packaged. **They are reference material.** A
behavioural benchmark would be the first time this repository *executed* an
upstream tree, which is a decision with its own review, not a side effect of
writing a document.

### 2.6 What was actually read, and where

| Fact | Source | Read as |
|---|---|---|
| the protocol's rule and the six blockers | `docs/EVALUATION.md` | read-only |
| the three options and the work order's Build clause | `docs/plans/LC-P1-13-14-task-breakdown.md` §1.4.3; `docs/PHASE_1_WORKORDERS.md` | read-only |
| the harness's refusal mechanism and its six conditions | `tests/evaluation/comparison.py`, `tests/evaluation/cli.py:310-338` | read-only |
| the corpus measurement and its unit | `tests/evaluation/corpus.py` | read-only |
| the public corpus: 4 fixtures, 7 questions, 19 artifact checks | `tests/fixtures/public/MANIFEST.json` | parsed, counted |
| PaperQA2's packaging, readers, chunking and types | `E:\labcairn-upstreams\paper-qa` @ `57e89f7` | **text only; nothing executed** |
| PaperSpine's shape and its installer's nature | `E:\labcairn-upstreams\paperspine` @ `42312b8` | **text only; nothing executed; no installer read as instructions** |
| upstream's observed behaviours, licences and rejected-adoption reasons | `docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md` | read-only |
| the upstream catalogue, licences and the "study, do not run" rule | `docs/UPSTREAM_REFERENCES.md` | read-only |

**Nothing under `E:\labcairn-upstreams\` was executed, installed or imported**
— no `pip install`, no import, no entry point, no installer. §2.5 explains
why that is the rule and not an accident.

---

## 3. What this project measured

**Two corpora exist, and only one of them is measured as a measurement.**
Keeping them apart is the point of this section: the public corpus is the
one a reader would assume is the benchmark, and it is the one that has never
been driven as a task.

### 3.1 The public fixture corpus — delivered, witnessed, **never driven as a task**

`tests/fixtures/public/`, corpus version **`2026-10-25.1`**, schema
`labcairn.public-fixtures/1`.

| | Count |
|---|---:|
| fixtures (four genres) | **4** |
| questions | **7** |
| material files (all synthetic, all hash-bound) | **8** |
| expected artifact checks | **19** |

The four genres: `physical_tension` (physical sciences), `biomedical_panel`
(biomedical-style tabular measurements, no real patient data),
`computational_solver` (computational experiments), and `no_evidence` (the
negative one, whose honest answer is *"the material does not say"*).

The 19 checks decompose as **6 `number_present`, 7 `citation_resolves`,
5 `no_fabricated_value`, 1 `abstains`**; the 7 answers decompose as
**6 `numeric` and 1 `not_stated`**.

**Every byte is synthetic**, labelled `SYNTHETIC MATERIAL` in the material
itself, with a SHA-256 and a length per file in `MANIFEST.json` — so the
corpus carries the immutable version labels the protocol's benchmark clause
requires.

**And it has never been run as a task.** The only two places in the tree
that read `tests/fixtures/public/` are `tests/test_public_fixtures.py` (41
witnesses over the corpus's own soundness — locators resolve, hashes bind,
answers re-derive from the material) and
`tests/evaluation/manifest.py` (which files it under the `unit` class,
clause `dataset-locators`). **Nothing drives a task from it.** So:

> The public corpus is an **input**, delivered and witnessed. It is **not**
> a score, and no number in this repository is measured on it.

### 3.2 The analysis corpus — the one measurement that is a measurement

`tests/evaluation/corpus.py` is the only place in the repository that
measures a product behaviour against an answer key rather than counting
green tests. It takes the committed keys under `tests/fixtures/analysis/`,
runs the product's **own** selection code over the same cells, and compares
**cell by cell**.

**Its denominator: 11 fixtures — 9 committed CSVs plus 2 spreadsheets
derived from them** (`numeric.xlsx` ← `basic.csv`, `holes.xlsx` ←
`holes.csv`; the derived files are not committed, and a derived file is not
a fixture).

**The unit is the cell**, and the report says so, because a denominator whose
unit is unstated is not a transparent denominator. **The key is the right
judge** because it was written by hand beside the data, is not generated by
anything in this repository, and was computed with Python's `statistics` —
an implementation that is not LabCairn's.

**The measured value, and where it comes from.** The harness's recorded
run of this measurement is in
[`LC-P1-13-evaluation.md`](LC-P1-13-evaluation.md) §5, at the tree
`37ae3663d28555b6b760416f10630a81b3ec1ecb`:

| The protocol's metric | Value | Witnesses' score |
|---|---|---|
| Numeric-cell extraction exactness and unit consistency | **84/84** — 77/77 quantity cells, 14/14 unit-consistent, 2/2 refusals | 256/256 |
| Recovery correctness / duplicate side effects | **8/8** (small denominator, and the report says so) | 40/40 |
| Latency, model usage/cost | **1337062/3357** ms over cases | 47/47 |

**The three figures in the first row do not add up, because they are not
the same unit** — and that is the point of reporting them separately.
**84 is the count of addressed cells**, and it is the denominator of the
exactness rate. **77 is the subset of those cells the key says carry a
quantity** — the narrower claim the protocol's word *"numeric-cell"* makes.
**14 and 2 count *selections*, not cells**: 14 selections state a unit
expectation and 14 reported it consistently, and 2 selections the key says
must be refused were refused. **A reader who adds 77, 14 and 2 is adding
three different things**, which is why the report carries each one with its
own unit.

**A number belongs to the tree it was measured on**, and that measurement is
anchored to the commit above. §3.6 records a fresh measurement on this tree.

### 3.3 The gate classes, with their denominators

Also from the same recorded run:

| The protocol's class | Passed / collected | Skipped |
|---|---|---:|
| Unit | **1469/1470** | 1 |
| Integration | **1131/1134** | 3 |
| Negative | **361/362** | 1 |
| E2E | **86/86** | 0 |
| **Real-model smoke** | **NOT RUN** — no credential; a class that did not run has no rate | — |
| Repository gates (not one of the protocol's five) | **305/305** | 0 |

**The skips are not one fact.** The recorded run separates three kinds: a
test that never runs anywhere (`requires_provider`); declared platform
conditionals (`skipif(os.name == "nt")`); and **skips that name an open
defect** (G1's exit demonstration, waiting on the 8.3 short-name comparison
of the task breakdown's §2.6). **The third kind fails a Phase 1 blocker**,
and the recorded run reports two of the six blockers as FAILED for exactly
that reason.

### 3.4 The Phase 1 blockers

From the same recorded run: **four of six HELD**, and two did not — the
clean-environment blocker (waiting on the 8.3 defect) and the
unauthorised-write blocker (a declared POSIX-only conditional, skipped on
Windows). **Both readings are the owner's question** — the task breakdown's
§1.4.1b asks it and does not answer it.

### 3.5 What the comparison mechanism does with an absent baseline

The harness refuses, and the refusal is structural rather than promised:

- **No ranking is printed, ever.** The comparison renders **pairs**, one
  metric at a time, with no aggregate for a reader to be handed, and a
  witness greps the **rendered** section for the words a verdict is made of
  (`better`, `worse`, `best`, `worst`, `superior`, `outperform`, `beats`,
  `winner`, `loses`, `ahead`).
- **A baseline missing a requirement is refused**, not caveated: the
  `assess` function returns `comparable=False` and the report prints the
  reasons instead of the numbers.

**One limit of that mechanism is worth recording, because a reader may
notice it.** `assess` compares the model strings, and the offline run's model
string is empty. A baseline document that *also* declared no model would
therefore match on that field. **Such a document would be dishonest** — no
competitor answers questions without a model — and the repository does not
have one. **The mechanism's leniency here is the protocol's rule doing its
work: the dishonest document is the one that is never written.**

### 3.6 A fresh measurement on this tree

**The numbers in §3.2, §3.3 and §3.4 are anchored to T01's run at
`37ae366`.** This subtask re-ran the harness on the tree this document is
committed to, so those figures can be read against a tree that still
describes them rather than carried forward across a merge.

The command, and the rules it obeys:

```
TEMP=<outside the repo> TMP=<outside the repo> MPLCONFIGDIR=<outside the repo> \
  uv run python -m tests.evaluation --out <outside the repo>
```

<!-- MEASUREMENT-PLACEHOLDER -->

---

## 4. What was not measured

**The rule this section follows: a metric that was not measured is written
`NOT MEASURED` with the missing input named.** A number with a denominator
and no numerator is not a result, and rounding one up is the failure mode
this repository has spent two gates learning about.

### 4.1 The real-model smoke — NOT RUN

**The missing input: a provider credential and the owner's authorisation to
spend money on one.**

The class needs *"at least one real supported provider under declared
model/version/parameters"*. The repository has a `FakeProvider` and no real
provider configured; `.env.example` and the `requires_provider` marker exist
for exactly this, and the marker does what it says — **it never runs, on any
platform.** The harness reports the class as **NOT RUN** with the reason and
**does not count it as a pass**, because a class that did not run has no rate,
and a rate of zero would say *"every case failed"*, which is a different fact.
**The harness's exit code for that run is 2** — *"a selected class could not
be run"* — and not 0.

**What this does and does not block.** The protocol's five mandatory gate
classes include the real-model smoke, so **the gate class is not discharged**.
**None of the six Phase 1 blockers requires one** (§2.2). Whether a declared,
reported skip of the real-model smoke counts as a blocker that failed is
**§1.4.1b's open question**, and it is the owner's, not this document's.

**And cost and model name are NOT MEASURED for the same reason**: no real
provider ran, so there is no cost to report, and the offline run's model is
not a declared model, version and parameter set.

### 4.2 The four task-level metrics — NOT MEASURED

| The protocol's metric | The missing input |
|---|---|
| End-to-end task success | a corpus of **attempted tasks with verified deliveries**. The run counts test cases; the public corpus exists but has never been driven as a task (§3.1). |
| Evidence locator validity and citation support precision | a **human-checked sample**. The tree records none, and a machine count is not a substitute for one. |
| Unsupported-claim detection and appropriate abstention | a **no-evidence fixture to abstain over**. The corpus now has one (`no_evidence`), but it has not been driven as a task, so the numerator would count nothing. |
| Revision consistency | a corpus of **source-change runs** with their outcomes. The tree records none. |

### 4.3 The competitor comparison — NOT MEASURED, and why

**No PaperQA2 run exists. No PaperSpine run exists. No number in this
repository is compared against either.** §2 gives the five reasons; each is a
fact, and none is a guess about difficulty.

**And nothing was compared against anything else either.** The recorded run
carries the harness's own refusal: *"no baseline document was given, so no
comparison was made. The protocol permits a comparison only when it is
like-for-like, and an unasked-for comparison is not one."*

---

## 5. What a comparison would need

**Three preconditions, and then work.** The preconditions are the ones the
protocol names; the work is what stands between this tree and them. **The
estimates below are estimates and are labelled as such — they are not
measurements, and nothing in this repository has timed them.**

### 5.1 Precondition one — a run with a declared model, on this side

**What is missing:** a run whose basis declares a model, version, parameter
set and budget, so that `assess` has something to match.

**What it needs:**

1. **The owner's §1.4.2 decision** — which provider, whose credential, and
   the cost ceiling. Until then there is nothing to declare.
2. **A harness change that this subtask did not make and must not make.**
   `tests/evaluation/cli.py:310-338` builds the run's basis with `model=""`
   and `budget=""` hard-coded, because the offline run has none. A run that
   *does* have a provider needs the basis to carry it — the model name,
   version and parameters, and the budget — from the provider configuration
   that `labcairn.providers.credentials.load_providers_config` already
   reads. **That file belongs to T01, and the brief for this subtask
   excludes `tests/` from it.** It is named here as a required change, not
   made.
3. **A re-measurement.** The metrics a comparison would pair are the ones
   in §3.2, and they would have to be measured again on the real-provider
   run, on the same tree.

### 5.2 Precondition two — a baseline that verifies its own capabilities

**What the protocol asks for:** *"verified capabilities, and documented
confidence intervals or limitations"*. The harness checks for a non-empty
`verified_capabilities` and for a non-empty `limitations` or
`confidence_intervals`, and refuses otherwise.

**What a PaperQA2 baseline would have to carry:** which capabilities were
actually exercised — the ones ADR-0004 measured (chunking, retrieval,
summary-based context, citation-key emission) — and what it does **not**
guarantee (C2 quotation match and C3 numeric reconciliation are absent
there, and the baseline would have to say so rather than let a reader assume
otherwise).

**The intervals.** One run per fixture is not a distribution. The honest form
is a **stated limitation** — *"one run per fixture, no repetition, so no
interval is computable"* — which the harness accepts in place of an interval.
**Any number presented as a rate without that limitation attached would be
exactly what the protocol forbids.**

### 5.3 Precondition three — a task shape both sides can answer

**This is the one that decides how much comparison is even possible.** The
19 artifact checks split into two halves that are not comparable in the same
way:

| Check | Count | Comparable with PaperQA2? |
|---|---:|---|
| `number_present` | 6 | **Yes in principle** — does the answer carry the right number? |
| `no_fabricated_value` | 5 | **Yes in principle** — does it carry the near-miss? |
| `abstains` | 1 | **Yes in principle** — does it decline, via `CANNOT_ANSWER_PHRASE`? |
| `citation_resolves` | 7 | **No** — the addresses are `k=3:csv\|r=1:2\|c=17:...`, and PaperQA2's text path has no column to name (§2.4) |

**And the material is the same material only if it is not re-encoded.**
PaperQA2 has no `.csv` reader; the corpus's eight material files are four
`.md` and four `.csv`. Feeding them through means a conversion, and **a
converted file is a different file**: the manifest's SHA-256 would no longer
describe the bytes the answer key was derived from, and the protocol's
*"immutable fixture/version labels"* would no longer be speaking about the
thing that was measured.

**The honest resolution is to compare only what both sides can be asked the
same question about — and to publish the two halves separately**, with the
7 locator checks reported as *not comparable* rather than as failures of the
competitor. **That is §1.4.3's Option A in its fixture scope — every
answerable fixture, and the negative one — but on the 12 comparable checks
only.** It is a narrower comparison than Option A's name promises, it is the
most this tree can honestly reach, and it is still downstream of §5.1.

**And PaperSpine is not in this table at all.** §2.3 is not a difficulty
judgement: there is no entry point to call, and the product's shape is a
manuscript pipeline rather than a question-answerer. **A PaperSpine
comparison would mean driving an agent platform**, and its outputs would be
free prose against which a locator check could not be written at all.

### 5.4 The work, itemised — an estimate, not a measurement

**None of these numbers has been timed, and this repository does not time
them.** They are the size of the gap between the two trees, stated so the
owner can price it.

| Item | What it involves | Size |
|---|---|---|
| A declared-model run on this side | §1.4.2's decision, a credential, the harness basis change (§5.1), a re-measurement of §3.2's metrics | **Days**, and it is **blocked on the owner**, not on engineering |
| A PaperQA2 installation | `paper-qa` needs Python ≥3.11 and pulls `fhaviary[llm]`, `fhlmi`, `tantivy`, `paper-qa-pypdf`, `litellm`, `tiktoken` — **a second environment**, not the project's venv | **Hours**, plus a credential for both the LLM and the embedding model |
| A PaperQA2 baseline document | run the seven questions on the fixtures, record the answers, write the JSON baseline the harness reads, declare capabilities and limitations | **Hours to a day** |
| — of which the scripting is **not** the hard part | upstream exposes a programmatic `paperqa.agents.ask` and an async `paperqa.agents.main.agent_query`, so the seven questions can be answered by script rather than by driving the interactive `pqa` console | — |
| Deciding the material encoding | §5.3's question — same bytes, or a declared conversion with a new corpus version | **A decision, not a task**, and it changes what the corpus version means |
| A PaperSpine comparison | a second agent platform, a model, a prompt flow, and outputs that have no locator shape | **Not estimated here**, because §2.3 says it is a different product rather than a harder task |

**The task breakdown's own estimate** — *"Running PaperQA2 or PaperSpine over
the same three fixtures is days of work and a second installation"* — is
consistent with the above, and the item that dominates is **the run this
project does not yet have**, not the competitor's installation.

---

## 6. The work order's Build clause, reconciled

LC-P1-13's Build clause asks for two things, and this is where each stands.

> Compare at least one scoped baseline (e.g. model without evidence workflow),
> same materials/model/budget. **External competitor comparison may be
> deferred if not reproducible.**

| The clause's half | Status | Why |
|---|---|---|
| **External competitor comparison** — "may be deferred if not reproducible" | **Deferred.** The clause permits it, and it is not reproducible here: no credential (§2.2), PaperSpine has no entry point (§2.3), PaperQA2's addresses cannot meet the fixture's locator checks (§2.4), and this project has no declared-model run to compare against (§2.1). | §2 |
| **At least one scoped baseline, same materials/model/budget** | **NOT DELIVERED, and this document does not claim it is.** It is blocked by the *same* missing precondition — a run with a declared model (§5.1) — and it has one problem of its own: **the "model without evidence workflow" shape has no switch in this tree.** The evidence checks are part of a skill's declared stage graph, not a configuration flag: `labcairn.skills.declaration.SkillDeclaration` validates a stage graph and rejects a declaration that does not carry its guarded stages, and a search of `src/labcairn/` finds no setting that turns the checks off. **Producing this baseline would therefore mean designing and building a way to disable the evidence workflow, which is new product capability — and §1.3 of the task breakdown puts new capability out of G5.** | §5.1, §7 |

**The acceptance clause is honoured and it is worth reading against the
above.** LC-P1-13's acceptance says *"no invented superiority"* — and the
honest reading of that clause is satisfied: **nothing is claimed over
anything.** It also says *"transparent denominators, scores and failure
cases"*, which §3 and §4 carry. **But the Build clause's baseline half is
not satisfied, and the honest thing to do is say so rather than let Option C
be read as a completed baseline.**

**So the work order's baseline clause is, as of this document: half deferred
(by the clause's own permission) and half outstanding.** That is a different
statement from "delivered", and it is the one this document makes.

---

## 7. What this document does not do

- **It does not deliver a comparison.** No competitor was run, no number is
  paired with anything, and **no superiority is claimed** — neither of
  LabCairn over PaperQA2 or PaperSpine, nor of anything else.
- **It does not execute, install or import any upstream code.** Nothing under
  `E:\labcairn-upstreams\` was run; the upstream installers were not read as
  instructions (§2.3, §2.5).
- **It does not change the protocol.** `docs/EVALUATION.md` is the ruler and
  is unedited; the one discrepancy found — the task breakdown says *"seven
  Phase 1 blockers"* and quotes six, and the protocol lists six — is
  recorded, as the harness records it, rather than resolved here.
- **It does not change any test.** The harness's refusal mechanism, its
  witnesses and its mutation table are T01's, and this document adds no
  witness to them. **A claim in this document that is not measured is
  written `NOT MEASURED`** — §4.2's four metrics, §4.1's class and §4.3's
  comparison are the ones, and they are the ones a reader should check
  first.
- **It does not close the work order.** §6 is a reconciliation, not an
  acceptance.
- **It is not an independent review.** The same party wrote it and measured
  it. The mitigation is that every number it carries is anchored to a commit
  and to the command that produced it (§3.6), and that the one thing it
  asserts about the competitors is a set of **read-and-checked** facts about
  their source at pinned SHAs — not a claim about how well they perform,
  which is precisely the claim it refuses to make.
