# LC-P2-18 — The competitor baseline's live run — acceptance

**Work order:** LC-P2-18 (the competitor baseline, row 6 of
[`PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md) §3) ·
**Brief:** [`LC-P2-18-competitor-baseline-brief.md`](../plans/LC-P2-18-competitor-baseline-brief.md) ·
**Preparation record:** [`LC-P2-18-preparation.md`](LC-P2-18-preparation.md) ·
**Machinery record:** [`LC-P2-18-machinery.md`](LC-P2-18-machinery.md) ·
**Status of the work order:** **both sides ran for real, the alignment is
comparable, and the comparison document carries no winner's language.**

**Measured:** 2026-11-04, on the tree at
`4798c11d8e5038b0fde2c206de86a439cca01437` (the worktree branch
`worktree-lc-p2-18-live-run`, on top of `docs/debt-closures`' tip
`8469bef`), Windows 11 Pro (10.0.26300 x64, AMD64), Python 3.12.13. The
run's raw artifacts live **outside the repository** at
`E:/labcairn-local/lc-p2-18-run/2026-11-04/` (`package/`, `ourside/`,
`paperqa/`, `comparison.json`); nothing in this record's numbers comes
from anywhere else.

**What this is.** The run the machinery record said had not happened:
the pinned competitor driven for real, our side driven for real through
the LC-P2-01 model-call path, both sides' raw outputs aligned over one
task package by the six-condition machinery, and the cost the owner
authorized.

**What this is not.** No claim of superiority, and no aggregate: the
protocol sentence forbids it, and the aligned document's pairs are
printed in the form `4/4 against 0/4` — two numbers side by side, no
winner named, no sum taken.

---

## 1. The re-pin

The brief's §2 requires a full clone with the pin resolved against the
remote before anything executes. On 2026-11-04:

- Full clone at `E:/labcairn-upstreams/paper-qa-full` (local clone of the
  2026-11-02 unshallowed checkout, whose history is complete; `origin`
  points at `https://github.com/Future-House/paper-qa.git` and `origin/main`
  was fetched forward to the remote tip through the proxy).
- The pin `57e89f7223b0960d5ee5ea048c69e3c47e088572` resolves (`git
  rev-parse …^{commit}`) and is an ancestor of `origin/main`
  (`git merge-base --is-ancestor`, exit 0).
- The remote default branch's tip is
  `c692d0dfeac4a0296599f7fe21a253a58b7ac12a` (`git ls-remote --symref
  origin HEAD`), the same tip the 2026-11-02 verification recorded: the
  pin has not been force-pushed away and sits two commits behind the tip.
- **The AGPL boundary held**: no `pymupdf` or `zotero` extra was installed
  anywhere in this run; the competitor environment is the preparation
  record's isolated venv, unchanged.

## 2. The model declaration, corrected mid-run by the owner

The run started under the model string the coordination brief carried
(`MiniMax-M3`), and the owner **corrected it in person during the run**:
both sides declare **`MiniMax-M3.1-Flash`**. What was done about it:

- The live full-volume run in progress was **stopped immediately**. Its
  first two attempts had died before any provider call (an argument
  error, then a seam bug — see §7); the killed attempt had been running
  for a few minutes and had already sent some calls that no surviving
  record counts. The stopped attempt's partial spend is therefore
  **uncounted by call** and is carried in the cost table as an honest
  line item.
- The approval file's `model` field became `MiniMax-M3.1-Flash`
  (`budget` and `approved_by` unchanged — `USD 50.00`, owner 2026-11-04
  session authorization), and both sides' basis documents declare that
  string verbatim, because both read it from the approval file.
- **The key changed too.** The old `minimax-key.txt` is retired. The
  operator's new key file holds three lines: a key, the model name, and
  a second key. Through the providers layer's own probe
  (`PydanticAiProbe`, one capability — `tool_calls` — one real request,
  against the declared endpoint) the **first key probed `ok`** and was
  written to a single-line credential file the workspace's
  `providers.json` names. **The third line's key was not probed**: the
  instruction was to try the first and fall through only on failure,
  and the first did not fail. No key's value appears in this tree, in
  any log, or in this record.

## 3. Our side's run

`scripts/run_ourside_competitor.py` (new in this work) drives the
package's three task faces through the LC-P2-01 model-call path —
`request_model`, under the consent layer's two gates in their order,
one single-use approval per call — and writes the artifact layout the
aligner walks. Twelve provider calls, one per document-QA case:

| face | metric | result |
|---|---|---|
| numeric-extraction | `numeric-extraction-exactness` | **69/89** |
| unsupported-claim-detection | `unsupported-claim-detection` | **1/1** |
| recovery-correctness | `recovery-correctness` | **4/4** |

The numeric face's scoring is the per-`(selection, group, statistic)`
value match the artifact carries under `numeric-cell-exactness`; a value
the model did not give in parseable shape is a miss, and a selection the
key declares refused produces no cells — its behaviour is recorded
beside them (in this run every refused selection was met with an honest
abstention: no invented values). The 89-cell denominator is the key
addresses; the empty fixture's key addresses none and scores 0/0 (§7).

The abstention case's artifact carries the verbatim answer; the model
answered that the pH is not reported, and the aligner's mechanical rule
scores it 1/1.

The recovery face is the product's real crash matrix: each of the four
`CrashPoint` windows executed with the fault armed inside the live
execute path, the store restarted, and the invariant observed. **All
four held.** No model is called on this face — recovery is the product's
own transactional machinery — and the surface declaration says so.

## 4. The competitor's run

The pinned paper-qa (2026.8.12 at the re-pinned SHA) drove the package's
twelve document-QA cases in its isolated venv, the declared model
reaching its litellm layer under the `openai/` prefix with the endpoint
and credential arriving through the operator's environment. The runner
captures answers verbatim and never hands the executed system an answer
key.

| face | metric | result |
|---|---|---|
| numeric-extraction | `numeric-extraction-recall` | **183/232** |
| unsupported-claim-detection | `unsupported-claim-detection` | **1/1** |
| recovery-correctness | `recovery-correctness` | **0/4** |

Two of these numbers are the machinery's own recorded rulings, not
capabilities: the recall rule is deliberately generous (any expected
statistic found anywhere in the answer counts, and refusals are not
scored), and the recovery face's zero is the brief §1 scope fact —
paper-qa's interface is documents-in, answers-out, it has no executor to
inject a crash into, and the surface declaration says `absent` rather
than inventing a question. The recall denominator (232) is the count of
expected statistics across the eleven keys; it is a different denominator
from our side's 89 cells, which is why task 1's two methods carry
different metric names and pair with nothing.

## 5. The alignment

`align_competitor_results.py` over the one package: **comparable — all
six conditions met.** Fixture labels equal (16 case names, both sides),
fixture versions equal (16 answer-key pins, both sides from the
package's own manifest), model equal (`MiniMax-M3.1-Flash`, both sides
from the approval file), budget equal (`USD 50.00`), capabilities
declared, limitations documented.

The comparison document's metric pairs, in its own rendering:

- `recovery-correctness`: **4/4 against 0/4**
- `unsupported-claim-detection`: **1/1 against 1/1**

Task 1 prints no pair: exactness and recall measure different
denominators, and one number pretending to be two names would be the
defect the machinery record already rules out. **No winner's language
appears anywhere in the document** — the pairs are two numbers and the
word `against`.

## 6. Costs

Everything below was spent for real, authorized by the owner on
2026-11-04 with a ceiling of USD 50.00. MiniMax bills by token; the
USD totals are **left to the operator's billing console** rather than
computed from a price this tree does not carry — the token counts are
what this record can state exactly.

| phase | calls | tokens |
|---|---|---|
| our side, final run (declared model) | 12 | 6,716 in · 54,987 out |
| our side, earlier full passes on the superseded model | 36 | ≈ 20,000 in · ≈ 167,000 out |
| our side, single-case calibration (superseded model) | 1 | 527 in · 633 out |
| competitor side, final run (declared model) | ≥ 12 completion calls (the pipeline's internal fan-out is not counted by the runner) | not metered per call |
| competitor side, one-case calibration (superseded model) | several | not metered per call |
| competitor side, killed full-volume attempt | uncounted partial | not metered |
| providers-layer probes (both keys' sessions) | 6 | minimal |

Even doubling the metered tokens to cover the competitor's unmetered
fan-out, the run's total sits in the hundreds of thousands of tokens —
a small fraction of the USD 50.00 ceiling at any plausible price for
the declared model. The ceiling was never approached and the budget
guard never fired.

## 7. What the live run found in the machinery

Three defects the dry pipeline could not reach, each fixed with
witnesses:

1. **The side documents named no fixtures.** The six conditions compare
   `fixtures.names` as a tuple, but the competitor runner's basis
   carried only label/model/budget — a live pair could never have been
   comparable. The runner now declares the package's case names and key
   pins, spelled in the same order both sides use (each face's cases
   sorted, faces in the package's order).
2. **The live seam read a key nothing produces.** `case_input_files`
   keys a case's inputs by their file names; the seam read
   `inputs["question"]`. The dry plan never exercises the seam, so the
   mismatch survived until a live run hit it — on the first case, before
   any provider call was made.
3. **An empty cells list was refused where the key itself declares
   none.** The empty fixture's key says the file produces no cells at
   all, and the recall rule already scored that key 0/0 — but the
   exactness rule refused the same reading, so the real corpus could not
   be aligned. An empty list now scores 0 over 0; a missing list is
   still refused. Two witnesses hold the difference, and the mutation
   check did its work: restoring the old refusal turned exactly the new
   zero-over-zero witness red while the missing-list witness stayed
   green.

The first two fixes were exercised by the real run itself (the run that
failed is not the run recorded here; the recorded run is the first that
completed end to end). The third's witnesses live in
`tests/test_competitor_machinery.py`, which now carries 21 witnesses
(registered in the same shard as before); **the shard costs are not
re-measured here** — that requires a runner — so
`tests/test_ci_shard_coverage.py`'s cost checks are expected to fail on
this branch until `python .github/remeasure_shards.py <run-id>` runs, per
the repository's own rule.

## 8. Recorded honesty losses

Stated rather than averaged away:

- **The output-format instruction is ours alone.** Both sides answered
  the same material and the same question text; our side's prompts
  additionally carry a fixed JSON-shape instruction (recorded verbatim
  in the runner). It is a difference in calling protocol, and the basis
  document says so.
- **Temperature is not ours to set.** The product's model-request
  protocol carries a prompt and tool names, not sampling parameters, so
  our side ran at the endpoint's default; the competitor's litellm
  settings pin 0.0. Two identical prompts can therefore answer
  differently on our side — the exactness figure moved from 82/89 to
  76/89 to 69/89 across full passes of the two models and is a
  one-pass number, not an expectation.
- **The abstention rule is strict against everyone.** An honest
  abstention that mentions a forbidden value in passing scores 0. In
  this run neither side tripped it.
- **The recovery zero is a scope fact, not a capability measurement.**
  The brief rules it so and the surface declaration records it so.
- **The competitor's internal call fan-out is not counted per call.**
  The cost table says so rather than inventing a number.
