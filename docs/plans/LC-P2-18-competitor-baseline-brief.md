# LC-P2-18 — The competitor baseline's task brief

**Work order:** [`PHASE_2-work-orders.md`](PHASE_2-work-orders.md) §3 row 6 ·
**Status:** **BRIEF — this document runs nothing.** A real run spends
provider money on both sides, so the run is executable only on the
owner's approval, and the budget and the final competitor list are
**runtime decisions** (§6). What this document supplies is the rest:
what is compared, which upstream systems qualify, the like-for-like
basis, the cost's shape, and the acceptance clauses the eventual run is
held to — written **before** there are tests to carry them, which is the
project's rule for a claim that does not exist yet.

Everything here is traceable to a record already in the tree: the
protocol sentence ([`EVALUATION.md`](../EVALUATION.md)), the comparison
mechanism (`tests/evaluation/comparison.py`), the frozen baseline
([`LC-P2-00-baseline.md`](../acceptance/LC-P2-00-baseline.md) and its
JSON), and the pinned upstream references
([`UPSTREAM_REFERENCES.md`](../UPSTREAM_REFERENCES.md)). Statements that
could not be anchored that way are marked as **estimates** or as
**needing verification at run time**. No claim in this document has been
measured against a live provider, because no provider call was made.

---

## 1. What is compared

**The three tasks**, the same ones whose numbers the frozen baseline
carries, and the ones the protocol sentence names when it forbids
unmatched comparisons:

1. **Numeric extraction** — the eleven corpus fixtures of
   `tests/evaluation/corpus.py` (`CORPUS_FIXTURES`: nine CSV and two
   XLSX), scored cell by cell against the committed answer keys in
   `tests/fixtures/analysis/*.expected.json`. The frozen baseline's
   figure is 84/84 (`numeric-extraction-exactness`).
2. **Unsupported-claim detection** — one case
   (`unsupported-claim-detection`, 1/1 in the baseline).
3. **Recovery** — four cases (`recovery-correctness`, 4/4 in the
   baseline).

The fourth metric the baseline carries, `latency-usage-cost`, is a
cross-cutting measurement, not a task; it is reported per side and not
compared as a task. Sixteen task cases per side per pass (11 + 1 + 4)
is the unit the budget in §4 is built on.

**What each side must produce.** A side of the comparison is *one basis
document plus the run's raw artifacts*, in the shape
`tests/evaluation/comparison.py::load_baseline` reads —
`label`, `fixtures.names`, `fixtures.versions`, `model`, `budget`,
`verified_capabilities`, `limitations`, `confidence_intervals`,
`metrics`. The six conditions `assess` checks are, in order:

| # | condition | what it demands of a competitor side |
|---|---|---|
| 1 | fixture labels equal | the side ran the same eleven fixtures, by name |
| 2 | fixture versions equal | the side's version labels match — on the run side these are recomputed as the sha256 of each fixture's answer key (`tests/evaluation/cli.py`), so the label is a content pin, not a string |
| 3 | model equal | the side declares *the* model, version and parameter set, as one string, identical on both sides |
| 4 | budget equal | the side declares the budget, as one string, identical on both sides |
| 5 | verified capabilities declared | the side names the capabilities it verified (the baseline declares `unit, integration, negative, e2e, repository`) |
| 6 | limits or intervals declared | the side documents its confidence intervals or its limitations — a side that cannot state its uncertainty is not a side |

A comparison that fails any one is refused: `assess` returns
`comparable: False` with reasons, and the report prints the reasons
instead of the numbers. The mechanism exists and is witnessed; the run
does not get to argue with it.

**The structural fact the brief must state rather than paper over: the
frozen offline baseline cannot be our side of this comparison.** Its
`model` field is `""` — the honest record of a run on the deterministic
`FakeProvider`, which declares no model — and its own limitations
sentence says its numbers "are a measurement of the repository's own
tests and not of a model's behaviour". A competitor side declares a real
model, so condition 3 (model equality) cannot hold against it. Row 6
says the same thing from the other end: *"Its precondition is now met —
LC-P2-01 landed, so a run basis naming a model is no longer a
fabrication."*

**So our side is a new frozen run, built the LC-P2-00 way:** a real-model
run of the same three tasks through the LC-P2-01 model-call path, on the
same eleven fixtures and the same answer keys, frozen into a basis
document **before** the competitor side runs — with its commit, platform,
model declaration, budget and exit code recorded as LC-P2-00's were.
What the frozen offline baseline contributes is its *shape and its
anchoring*: the fixture name list and version pins, the
verified-capabilities declaration, the precedent that a basis is frozen
and carries its own honesty (`model=""` was recorded, not invented), and
the six-condition verification a fresh basis must pass the same way.
"Our side's numbers come from the frozen baseline" means *from a run
frozen by that procedure* — never from numbers gathered ad hoc on
comparison day.

**A note on fairness that belongs in the brief, not in a footnote.**
Task 1 (numeric extraction from a table) is a shape a retrieval-and-QA
system can be asked honestly. Tasks 2 and 3 (unsupported-claim
detection, recovery) are LabCairn's own capability faces; a competitor
may have no corresponding surface at all. That is not a disqualification
of the comparison — the protocol's requirement is *matched tasks*, and
asking every side the same question is what matched means. It does mean
a competitor's zero on a task it has no surface for is a **fact about
the competitor's scope**, reported as such (§5, clause 6), and the
rendered section still carries no ranking word either way.

---

## 2. Which upstream systems qualify

**The four criteria a competitor must meet to be comparable:**

1. **Openly runnable locally** — the pinned tree can be installed and
   executed on this machine class without a hosted service the run does
   not control.
2. **Accepts a fixed corpus** — the side can be pointed at the eleven
   fixtures (through an adapter, §3) instead of sourcing its own
   documents.
3. **Produces artifacts the harness can score** — the side's output per
   case can be parsed into the shape the answer key scores, by a
   translation layer that contains no task logic.
4. **License permits the run** — the root license (verified at the pin
   in `UPSTREAM_REFERENCES.md`) permits executing the system on our
   corpus and reporting the numbers.

**The pinned candidates, measured against the criteria** (SHAs as
recorded in `UPSTREAM_REFERENCES.md`'s table, all *must-study*, all
cloned 2026-10-15):

- **`paper-qa`** (`57e89f7223b0960d5ee5ea048c69e3c47e088572`, Apache-2.0
  at root) — **qualifies, plausibly**. A pip-installable library that
  accepts supplied documents and produces answers with citations; it is
  also one of the two systems the protocol sentence names. Open
  questions it must answer at run time, each a verification, not an
  assumption: whether the default install pulls the AGPL-3.0
  `packages/paper-qa-pymupdf/` subpackage (the run's dependency
  closure is recorded so the license boundary is auditable); whether its
  ingest can be adapter-fed XLSX (it is PDF/text-first); and what its
  per-case call fan-out is (§4's cost shape depends on it).
- **`paperspine`** (`42312b8d9c76ab25990cddfd76e3622276854118`, MIT) —
  **disqualified as it stands, and the reason is recorded rather than
  quiet.** The pinned tree is a skill distribution package, not an
  installable library: it drives a host agent rather than running as
  one, and its distribution carries an installer the upstream study
  treated as untrusted (`UPSTREAM_REFERENCES.md`). Running it would mean
  running a host agent plus an untrusted installer path — a different
  and larger execution surface than criterion 1 contemplates. It is the
  other system the protocol sentence names, so it is **not silently
  dropped**: if the owner wants it compared, that is an owner decision
  (§6) that also decides the host-agent question.
- **`pydantic-ai`**, **`openhands-sdk`**, **`deepagents`** (all MIT,
  all pinned) — **disqualified by category, not by quality.** They are
  a framework, an SDK and a framework: building blocks with no task
  behaviour of their own. Driving one to complete the three tasks means
  writing an agent ourselves and comparing our agent to our product,
  which is not a competitor baseline. (`deepagents` carries the
  additional recorded finding that its advertised planning does not
  ship at the pin.)
- **`gpt-researcher`**, **`storm`**, **`ai-scientist-v2`**, **`opencode`**
  — **not assessable, because no pin exists** (`not cloned` in the
  table — the record's own rule is that an invented SHA is worse than a
  blank). They are additionally wrong-shaped as pinned candidates would
  need to be shown otherwise: open-web research synthesizers (a corpus
  they fetch themselves breaks criterion 2), an experiment orchestrator
  under a custom research-only license, and a coding agent. If the
  owner wants any of them assessed, the run begins with clone, pin and
  license verification, not with a comparison.

**The likely outcome the brief states plainly: the qualifying list may
be one system long.** A comparison against one competitor that meets the
criteria is a comparison; a comparison padded with disqualified systems
is theatre, and the protocol sentence's "others" does not oblige us to
manufacture one.

**The shallow-clone debt, and what it costs the run.** Every pinned SHA
in `UPSTREAM_REFERENCES.md` was read from a **local shallow clone**
(`--depth 1 --single-branch`), and the record says so: a fresh clone of
the default branch is not guaranteed to reproduce the SHA, and upstream
force-push or garbage collection can invalidate it. `PHASE_2-work-orders.md`
§5 carries this as debt precisely because it contradicts this work
order's acceptance clause that *a reader can re-run one side*. **So the
run requires, for every competitor that makes the final cut, a re-pin at
full clone before anything executes**: full `git clone`, the SHA
resolved against the remote (`git ls-remote` and a fetch of that exact
commit), the re-pinned SHA and its verification date recorded in the
side's basis document, and — if a SHA no longer resolves upstream — that
reported as a fact and the competitor re-pinned at a new SHA **by an
owner decision**, never silently. A run executed against a shallow-clone
SHA is not the run this brief describes.

---

## 3. The like-for-like basis

**Environments are declared, not identical.** The competitor side runs
on the environment its own tree requires; ours runs on the frozen
baseline's machine class. What makes the comparison like-for-like is
that **each side's environment is written into its record** (OS, Python,
the competitor's own pinned dependency versions) and that **scoring
happens in exactly one place**: the same harness, on the same machine,
against the same answer keys, reads both sides' artifacts. Execution may
differ; judgement does not.

**What "a run" is, per side.** For our side: one invocation of the
harness over the sixteen task cases with the declared model — the same
shape of run LC-P2-00 froze, exit code and all, honest NOT RUN entries
included. For a competitor side: the side's system, driven once per task
case through the adapter, its per-case output captured as an artifact
the scorer reads. A case that a side cannot run at all is a **reported
fact with its reason** (§5, clause 6), never a silent drop and never a
substituted case — the corpus is identical for every system, which is
row 6's own cost line.

**The adapter, and why it is the comparison's main honesty risk.** A
competitor does not natively speak LabCairn's task interface, so
something translates: corpus files in, answers out. That translation is
where a comparison quietly becomes rigged — an adapter that paraphrases
the question into the competitor's favourite shape, or that cleans up
its output before scoring, has already decided the result. The rule the
run holds: **the adapter contains no task logic** — no prompt
engineering toward an answer format, no post-hoc repair of what the
competitor produced beyond mechanical parsing, no retry the product
side does not also get. It is the smallest honest I/O translation, its
code lands in the repository, and it is exercised identically in
spirit on both sides. Where a translation choice is genuinely open
(how an XLSX becomes the competitor's input format), the choice is
recorded in the basis document, and the honest default is the dumbest
one that parses.

**Scoring, identically.** Both sides are scored by the same scorer
against the same committed answer keys — the keys whose sha256 are the
frozen baseline's `fixtures.versions`. The scorer is deterministic, so
a re-score of the same artifacts yields the same figure; model-side
nondeterminism is handled where it belongs, in the repetition and
aggregation the side's `confidence_intervals` or `limitations` field
declares. **Neither side's numbers are retyped into the other's
document**: each side's `metrics` come from its own scored artifacts.

**Where our side's numbers come from.** From the frozen real-model run
of §1 — prepared the LC-P2-00 way (clean tree at a recorded commit,
declared environment, recorded exit code), frozen into a basis document
before the competitor runs, and re-verified against the six conditions
the same way `tests/test_baseline_document.py` verifies the offline
baseline. The offline baseline's numbers are never printed beside a
competitor's.

---

## 4. The cost

**This section is an estimate, marked as such, and no number in it has
been measured.** Prices change and call fan-outs are the competitor's
own; the run re-measures both from its first case before it spends the
rest (§5, clause 9).

**The shape.** Per side per pass: 16 task cases. A case is one task
invocation; a task invocation is several model calls (retrieval rounds,
generation, — on the competitor side, whatever its pipeline does). For
planning: **5–20 model calls per case** on a retrieval-style system,
**2–20k tokens per call**, giving roughly **0.2–6M tokens per side per
pass**; a pass repeated enough to state uncertainty (three passes) puts
each side at **0.5–19M tokens** for the full comparison. At listed
provider rates as of drafting (2026-11-02) that is, **order of
magnitude only: tens to a few hundreds of US dollars per side**, both
sides together plausibly under ~$500. The honest error bar on this
paragraph is wide: it is a shape, not a quote.

**What the budget request will ask for.** A single figure covering both
sides — our side's real-model run (the frozen basis of §1) plus every
competitor side that makes the final cut — computed at the provider's
prices **on the day of the request**, with: three passes per side as
the default uncertainty basis, a 25% margin for retries and the
un-runnable cases that turn out to be runnable, and the first-case
calibration of clause 9 as the mechanism that keeps the total honest
mid-run. The request names the model tier for both sides, because the
six conditions make the model a joint declaration: the sides must run
*the same* declared model for the comparison to render at all (§1,
condition 3).

**What happens if the owner declines.** Nothing runs, and nothing is
owed: this brief remains the preparation, the phase's exit gate keeps
the same shape it has today, and the comparison stays in
`PHASE_2-work-orders.md` §3 as the row it is. A decline is not a
failure of the brief; a run without one would be. There is no cheaper
version that preserves the claim — a comparison with our side
unmeasured, or the competitor's side mocked, is exactly what the
protocol sentence and the six conditions exist to refuse.

---

## 5. The acceptance clauses for the eventual run

Written here, before any test exists to carry them, because a claim
that is stated and not watched is not held. Each clause is a test
waiting for its mechanism; the run is not accepted while any is
unwitnessed.

1. **Frozen-before-compared.** Every side's basis document exists,
   frozen, before its numbers are compared: fixture name list and
   version pins (answer-key sha256), model declaration, budget
   declaration, verified capabilities, and its uncertainty statement.
   A basis assembled after its competitor's numbers were seen is not a
   basis.
2. **The six conditions decide renderability, mechanically.** The
   comparison renders only what `assess` calls comparable on all six
   conditions; a refused comparison prints its reasons and no numbers.
   This is the existing mechanism doing its existing job — the run
   adds no bypass.
3. **The rendered section names no winner.** Pairs, one metric at a
   time, no aggregate, no ranking word — the word list
   `tests/test_evaluation_harness.py` watches is the run's vocabulary
   limit too, and a competitor report is held to the same rendered
   section as a baseline report.
4. **A reader can re-run one side.** For every competitor in the final
   cut: the re-pinned full-clone SHA (verified against the remote at
   run time, §2), the declared environment, the adapter code as
   committed, and the recorded artifacts are together sufficient for a
   reader to re-execute that side and re-score it to the same figure —
   up to the nondeterminism the side's own uncertainty statement
   declares. Our side re-runs the same way from its frozen basis.
5. **The adapter carries no task logic.** The translation layer is
   committed, minimal, and does nothing the product side does not also
   get: no question rewriting toward an answer, no output repair
   beyond mechanical parsing, no private retries. A witness fails if
   scoring depends on anything but the answer keys and the artifacts.
6. **A competitor's failure to run is its own fact.** An install
   failure, an API refusal, a case the system cannot accept, a
   fixture it cannot ingest — each is reported as *that side's* fact,
   with its reason, in the section. It is never counted as our gain,
   never silently dropped from the corpus, never substituted with
   another case. The honesty clause, in one line: **the rendered
   section names no winner, and a competitor's absence from a case is
   not our presence on it.**
7. **Untrusted data stays untrusted.** Upstream trees carry agent
   instruction files (139 of them, per ADR-0002's count) and the
   competitor's output is model-generated text the run did not write.
   Neither is ever executed or followed by the harness, the scorer, or
   the report; instruction-shaped text in a competitor's artifacts is
   data, and the report treats it as data.
8. **Executing upstream code is an authorized act, scoped and
   recorded.** Every upstream execution in this repository's history
   has been read-only (ADR-0002); a competitor run breaks that pattern
   on purpose, so it carries its own approval: the owner's authorization
   to execute *this pinned tree*, an isolation scheme recorded before
   the run (dedicated environment, secrets exposed at the minimum the
   declared model needs), and the executed SHA in the basis document.
9. **The budget is declared and the run stops at it.** The declared
   budget string (condition 4) carries a call and spend ceiling; the
   first case of each side is a calibration point — its actual cost is
   measured before the rest runs, and the projection against the
   ceiling is reported. Over the ceiling, the run stops and reports
   where it got, as fact. A comparison that rendered only by
   overspending is a refused comparison.
10. **The record is written where records go.** The run's acceptance
    record lands in `docs/acceptance/` as its own document, naming the
    bases, the re-pins, the failures-as-facts, and the cost actually
    spent — and `docs/acceptance/LC-P2-00-baseline.md`'s precedent
    stands: an honest NOT RUN entry with its reason is part of a
    complete record, not a hole in one.

---

## 6. What this brief does not settle

Decisions that are the owner's, asked at run time and only then:

- **The final competitor list.** Whether `paper-qa` runs alone; whether
  `paperspine` is compared by way of a host-agent arrangement (which
  also decides how an untrusted distribution gets executed, §2); whether
  any unpinned candidate is cloned and assessed first.
- **The budget figure**, at the prices of the day the request is made —
  this brief supplies the shape (§4), not the number.
- **The model both sides declare** — the joint declaration the six
  conditions require, and with it our side's real-model run's
  parameters.
- **The isolation scheme** for executing upstream code (§5, clause 8):
  what runs in what, and which secrets go where.
- **When.** The comparison's place in the phase's remaining order —
  relative to the blind evaluation and ablation (row 2), whose budget
  pool it shares — is a sequencing decision, not this brief's.
- **Whether the run happens at all.** The brief is executable only on
  approval; a decline leaves it as preparation, with nothing owed
  (§4).
