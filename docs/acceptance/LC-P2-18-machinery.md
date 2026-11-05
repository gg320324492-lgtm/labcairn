# LC-P2-18 — The competitor baseline's machinery — acceptance

**Work order:** LC-P2-18 (the competitor baseline, row 6 of
[`PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md) §3) ·
**Brief:** [`LC-P2-18-competitor-baseline-brief.md`](../plans/LC-P2-18-competitor-baseline-brief.md) ·
**Preparation record:** [`LC-P2-18-preparation.md`](LC-P2-18-preparation.md) ·
**Status of the work order:** **the machinery is built, witnessed and
exercised dry end to end; the run has not happened.**

**What this is.** The three pieces of machinery that wait on nobody: the
task package (both sides' inputs, byte-identical), the paper-qa side's
runner (a call plan that spends nothing, and a live mode that is gated),
and the aligner (two sides' raw outputs into the six-condition shape, or
a refusal). Plus the runbook: the steps a real run follows once the owner
has filled in the budget and said yes.

**What this is not.** **No provider was called and nothing was spent.**
No credential was read; the only keys this machinery touched are the
committed answer keys. The dry pipeline ran against synthetic answers —
nothing in it is a claim about either side's capability.

---

## 1. What was built

### 1.1 The task package — `tests/evaluation/competitor_package.py`, `scripts/package_competitor_corpus.py`

One output directory holding every task file both sides consume, written
once and hashed in a manifest:

```
<out>/
  manifest.json                    # schema, per-face file counts, every file's SHA-256, its source in the tree
  tasks/
    numeric-extraction/            # the eleven CORPUS_FIXTURES, byte for byte
      fixtures/ answer-keys/ questions/
    unsupported-claim-detection/   # the no_evidence material, its key, its prompt
      material/ answer-keys/ questions/
    recovery-correctness/          # the four crash windows as task statements
      scenarios/ answer-keys/
```

The three task faces are the ones the frozen baseline carries numbers for
(brief §1): eleven numeric fixtures against their committed keys, the
public corpus's no-evidence question (extracted verbatim from
`tests/fixtures/public/MANIFEST.json`), and the four crash windows of
`labcairn.recovery.contracts.CrashPoint`, each written as a task
statement beside the invariant the specification requires (ADR-0003 C2
rows / AT-1, AT-5, AT-2/4, AT-3). The recovery keys state invariants,
not numbers; nothing in the package scores anything.

Rules the witnesses hold:

* **Two builds are byte-identical** — the manifest carries no timestamp,
  so the same tree produces the same bytes (`test_two_builds_are_byte_identical`).
* **The output directory is refused inside the repository** — runner
  input is runtime state, not a tree artifact
  (`test_a_package_inside_the_repository_is_refused`). The path is always
  `--out`; no default exists.
* **A package that does not match its own manifest is refused** by
  `validate_package`: every file present with the hashed bytes, nothing
  undeclared, all three faces in the manifest.

### 1.2 The paper-qa runner — `tests/evaluation/competitor_paperqa_run.py`, `scripts/run_paperqa_competitor.py`

Two modes:

* **`--mode dry`** validates the package and prints the **call plan**:
  every case the package holds, the question file it would be asked
  through, and a **lower bound** on provider calls — twelve (11 + 1) at
  one completion call per document-QA case. The recovery face is planned
  as **zero calls**, explicitly: paper-qa's interface is documents-in,
  answers-out, it has no executor to inject a crash into, and the brief
  rules (§1) that a competitor's zero on a face it has no surface for is
  a fact about the competitor's scope. The plan states that fact instead
  of inventing a question. Paper-qa's internal agent fan-out is a runtime
  verification (brief §4), never an assumption — the plan says
  *minimum*.
* **`--mode live`** actually runs, and is **gated before paper-qa is even
  imported**: without `--approval` pointing at the owner's approval file
  (JSON with a non-empty `budget`, `approved_by`, and `model`) it refuses
  and nothing happens. The approval file's model and budget are what the
  side's basis declares, so the run and its declaration cannot disagree.

Per-case artifacts carry the adapter's shape (`status`, `answer` — the
verbatim text, untrimmed) plus the alignment fields (`face`, `case`,
`scoring`), so `score_artifact` can re-score the recorded artifact from
the record alone. **The answer keys are never handed to the executed
system** — a case's inputs are its material bytes and its question text
(`case_input_files` refuses them to the keys); the keys go to the
aligner, which is where scoring lives. A side's output directory is:

```
<side>/
  run.json             # label, the package manifest's SHA-256, model, budget
  basis.json           # the six-condition declaration
  key-versions.json    # the answer-key pins as this side saw them
  answers/<face>/<case>.json
  recovery-correctness/surface.json   # the face's surface declaration
```

### 1.3 The aligner — `tests/evaluation/competitor_align.py`, `scripts/align_competitor_results.py`

Two sides' output directories plus the package in; one comparison
document out — two `ComparisonBasis` documents, the six-condition verdict
from `comparison.py::assess`, and the metric pairs. **The refusals are
the point**: an aligner that scored a lopsided input would be how a
broken run produces a number anyway. It refuses, with every reason
collected, when

* a task face is missing from either side (or from the package);
* a case is missing, extra, or **misfiled** — an artifact whose declared
  case is not the file it sits in;
* a side's key pins do not match the package's keys (a side that ran
  against other keys ran another corpus);
* a side's run record does not name this package's manifest hash;
* an artifact declares a scoring method outside the closed table, or a
  face mixes two methods.

The closed scoring table, per face:

| face | method | metric name | the rule |
|---|---|---|---|
| numeric-extraction | `numeric-cell-recall` | `numeric-extraction-recall` | the adapter's recall rule (`score_artifact`) over the captured text and the package's key |
| numeric-extraction | `numeric-cell-exactness` | `numeric-extraction-exactness` | counts the per-cell outcomes the artifact carries; a name per cell, no duplicates, no invented cell |
| unsupported-claim-detection | `abstention-mechanical` | `unsupported-claim-detection` | any of the key's `no_fabricated_value` numbers (50.0, 37.0) in the answer scores 0; anything else scores 1 |
| recovery-correctness | `recovery-surface` | `recovery-correctness` | absent surface → 0 over the package's cases; present surface → every case carried, each an observed boolean |

Two recorded honesty losses, neither hidden:

* **`abstention-mechanical` is strict against the competitor.** The rule
  cannot read prose intent, so an honest abstention that *mentions* a
  forbidden value in passing ("the material reports a 50 mM buffer, but
  no pH") also scores 0. The key's `citation_resolves` check has no
  mechanical reading for free text and is not scored. The verbatim answer
  stays in the artifact so a reviewer can re-read it and re-judge; the
  direction is the opposite of the recall rule's, and both directions are
  stated rather than averaged away.
* **Task 1's two methods map to different metric names on purpose.** Cell
  exactness and statistic recall have different denominators; one name
  over two denominators would be one number pretending to be another
  (the same ruling the comparison driver's stub metric already records).
  Tasks 2 and 3 measure the same thing on both sides and share their
  metric names, so `pairs()` pairs them; task 1 shows no pair.

### 1.4 The witnesses — `tests/test_competitor_machinery.py`

Eighteen witnesses, registered in the gate partition
(`tests/evaluation/manifest.py`, unit / numeric-extraction) and in
`.github/ci-shards.json` (both platforms' third shard). **The shard
costs are not re-measured here** — that requires a runner, and this work
spent none — so `tests/test_ci_shard_coverage.py`'s two cost checks fail
as expected: `test_the_recorded_costs_cover_every_test_file` (the new
file has no measured cost) and `test_the_costs_belong_to_the_tree_they_were_measured_on`
(whose anchor `a3093e3c` predates eight commits of `tests/`/`src/`
changes on this branch — it was already failing before this work began).
Both are re-measured by `python .github/remeasure_shards.py <run-id>` on
the next run, per the repository's rule.

## 2. The mutation checks

Each refusal behaviour was verified by mutating the aligner itself — the
witness must fail *for the property*, and each mutation broke exactly its
own witness while the other seventeen stayed green:

| mutation (one line in `competitor_align.py`) | witness that went red | how it failed |
|---|---|---|
| `_check_coverage` returns early (coverage check disabled) | `test_a_missing_task_face_refuses_the_alignment` | the refusal no longer names the missing case — the aligner said only "carries no artifacts to score" |
| `_check_key_versions` returns early (pin check disabled) | `test_a_key_pin_that_does_not_match_the_package_refuses_the_alignment` | `DID NOT RAISE` — the aligner scored the mutated pin silently, which is exactly the failure the witness exists for |
| the misfile check's condition replaced with `if False:` | `test_a_misfiled_artifact_refuses_the_alignment` | the misfiled artifact was scored instead of refused |

The coverage mutation also exposed a second layer now in place: with the
coverage check disabled, an empty face is still refused by
`_score_face` ("carries no artifacts to score") rather than crashing —
the aligner cannot be made to score a missing face by breaking one
check. Every mutation was applied by byte replacement with the file
backed up outside the repository and restored from the backup; the
restored file's witnesses pass.

## 3. The dry pipeline, exercised end to end

Built and run on this branch's tree, spending nothing:

1. **Packaged** to `E:/labcairn-local/lc-p2-18-runbook-demo/package` —
   33 + 4 + 8 task files, manifest SHA-256
   `b787c0a1d2ab4acc0454b930c8cf093f3601553d93f9800d93747f19caaee984`.
   Two builds three seconds apart are byte-identical — which required
   making the generated spreadsheets' bytes **deterministic**: openpyxl
   stamps each archive entry with the current time and writes the
   generation moment into the document properties inside, so two
   generations of the "same" file differed in bytes (measured), and the
   first byte-identity witness passed by luck — both of its builds
   happened to land inside one two-second zip tick. The packer now
   rebuilds each generated spreadsheet with pinned entry timestamps and
   a pinned core-properties timestamp, its cells untouched, and a
   witness holds the adapter's rendering ruling against the repacked
   bytes; the identity witness now separates its two builds by longer
   than a tick, so passing is a measurement again and not a coincidence.
2. **Planned** (`run_paperqa_competitor.py --mode dry`): 12 cases, 12
   minimum provider calls, recovery face declared absent.
3. **Aligned** (`align_competitor_results.py`) over synthetic both-side
   outputs: `comparable: True`, all six conditions met, our side 33/33
   exactness (demo cells), 1/1 abstention, 4/4 recovery; competitor side
   0/232 recall, 0/1 abstention (the answer stated 50.0), 0/4 recovery
   (absent surface). Pairs printed for the two scope faces; task 1
   prints none, by design.

The demo artifacts live outside the repository and are reproducible by
the runbook's own steps.

## 4. The runbook — the real run, once the owner approves

**Before anything below: the owner's five decisions (brief §6) must be
made.** The final competitor list (this machinery assumes paper-qa
`57e89f72` per the preparation record), the budget string, the model both
sides declare identically, the isolation scheme, and the moment. The
budget string is *the* budget — condition 4 compares it verbatim between
the sides, and clause 9 stops the run at it.

**One structural precondition is still machinery-shaped, and the record
says so rather than pretending:** our side's run must be a frozen
real-model run built the LC-P2-00 way (brief §1) — the LC-P2-01
model-call path driving the three tasks, its artifacts written in the
layout §1.2 defines, frozen into a basis before the competitor runs. That
driver is not built here; it is the run's first implementation step, and
it spends provider money only when it runs.

### Step 0 — re-pin the competitor at a full clone (brief §2's debt)

```
git clone https://github.com/Future-House/paper-qa E:/labcairn-upstreams/paper-qa-full
git -C E:/labcairn-upstreams/paper-qa-full rev-parse 57e89f7223b0960d5ee5ea048c69e3c47e088572^{commit}
```

A SHA that no longer resolves is an owner decision, never a silent
substitute. Record the verification in the run's record. **Never install
the `pymupdf` or `zotero` extra** into the competitor environment — the
AGPL boundary is measured in the preparation record and this rule keeps
it.

### Step 1 — write the approval file (the owner's act)

Outside the repository, beside the credentials (the credentials
themselves are read by the model layer, never by this machinery):

```json
{
  "label": "paper-qa 57e89f72",
  "model": "<the model string both sides declare, verbatim>",
  "budget": "<the budget string both sides declare, verbatim>",
  "approved_by": "<the owner>"
}
```

Say its path is `E:/labcairn-local/secrets/lc-p2-18-approval.json`. Until
this file exists, `--mode live` refuses and nothing is spent.

### Step 2 — package the tasks (either side, once)

```
python scripts/package_competitor_corpus.py --out E:/labcairn-local/lc-p2-18-run/<date>/package
```

Hand each side a **copy** (`competitor_package.copy_package`); the
original stays untouched. Record the manifest's SHA-256 — the run's
record and both sides' run documents must name it.

### Step 3 — our side: the frozen real-model run

Drive the LC-P2-01 model-call path over the package's three task faces,
writing our side's artifacts in §1.2's layout (numeric artifacts under
`numeric-cell-exactness`, the abstention case verbatim, the recovery
cases' observed booleans), then freeze the basis **before** the
competitor side runs. The frozen offline baseline cannot be our side —
its `model` is `""` (brief §1's structural fact).

### Step 4 — the competitor side, live

In the isolated environment from the preparation record
(`E:/labcairn-local/paperqa-venv-19b47f/venv`, Python 3.12):

```
E:/labcairn-local/paperqa-venv-19b47f/venv/Scripts/python.exe scripts/run_paperqa_competitor.py --mode live --package E:/labcairn-local/lc-p2-18-run/<date>/package --artifacts E:/labcairn-local/lc-p2-18-run/<date>/competitor --approval E:/labcairn-local/secrets/lc-p2-18-approval.json
```

**Calibration first (clause 9):** run one case, read its actual call
count and cost from the artifacts, project against the ceiling, and only
then continue. The runner does not enforce the ceiling itself — the
projection against it is reported, and over the ceiling the run stops as
fact. The live gate, the verbatim capture, and the surface declaration
are the runner's; the ceiling watch is the operator's, per case.

Call shape, per side: eleven numeric cases + one abstention case, each
one ingest (local, sparse embedder) and ≥1 completion call; zero calls
for the recovery face (declared absent). Minimum twelve completions; the
actual fan-out is a measured result of the run, not an assumption.

### Step 5 — align and read

```
python scripts/align_competitor_results.py --package E:/labcairn-local/lc-p2-18-run/<date>/package --ours E:/labcairn-local/lc-p2-18-run/<date>/ours --competitor E:/labcairn-local/lc-p2-18-run/<date>/competitor --out E:/labcairn-local/lc-p2-18-run/<date>/comparison.json
```

A refusal prints its reasons and stops — no score was produced. A
comparable result prints the six conditions and the pairs; the section
names no winner, and the report vocabulary rule
(`tests/test_evaluation_harness.py`'s word list) holds here as anywhere.

### Step 6 — write the record

The run's acceptance document lands in `docs/acceptance/`, naming the
bases, the re-pin verification, the failures-as-facts (clause 6), the
budget projection (clause 9), and the manifest hash both sides ran over.

## 5. What is still a runtime decision or a runtime verification

* The five owner decisions of brief §6, listed at §4's head.
* The re-pin verification (Step 0) — a SHA that no longer resolves is
  the owner's call.
* Our side's run driver (Step 3) — the one implementation step the real
  run adds; its artifact layout and its scoring method are already fixed
  by this machinery.
* Paper-qa's actual per-case fan-out and cost (Step 4's calibration) —
  measured, never assumed.
* The abstention rule's strictness on real answers (§1.3's recorded
  loss) — the artifacts keep every verbatim answer so the owner can
  re-judge any case the mechanical rule scored 0.
