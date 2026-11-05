# LC-P2-26 — The retrieval-quality metric's machinery, built ahead of its sample

**Work order:** [`PHASE_2-work-orders.md`](../plans/PHASE_2-work-orders.md)
§3 row 5 — *retrieval quality beyond three papers, measured rather than
asserted* · **Status:** **the mechanical half is LANDED and witnessed; the
metric itself remains NOT MEASURED**, because the human half — a person
reading produced reports and judging their citations — has not been done.

The work order's clause has three parts, and they are in different states
after this piece:

| The clause | State |
|---|---|
| *"the metric is measured with its denominator named and its sample size stated"* | the **machinery** measures it; the sample it runs on does not exist yet, so the report says NOT MEASURED |
| *"a retrieval change moves the figure and the frozen baseline shows it moved"* | the machinery feeds the comparison's pairs; the frozen P1 baseline carries no such key, so no pair prints until a later baseline is taken over a filled sample |
| *"a query the index cannot serve is reported as a miss, not as an answer"* | **already held** before this piece — implemented in `retrieve()` and witnessed by `test_evidence_retrieval.py`; this piece adds the mutation evidence |

## 1. What the machinery is

Four things, all under `tests/evaluation/` and
`tests/test_evaluation_harness.py`:

**The sample table's schema and loader**
([`citation_sample.py`](../../tests/evaluation/citation_sample.py)). A
human-checked citation-support sample is a JSON document: a `label` naming
the reading pass, and one row per citation a produced report makes. A row
carries exactly five fields — `sample_id`, `report`, `record_id`,
`anchor_id`, `verdict` — and **no sixth field, ever**. The loader refuses
any field beyond the five, and the refusal says why: a field for text — the
claim, the material's words, even the reader's reason — is how the owner's
unpublished manuscript leaks into a public tree. The refusal is the
mechanism, not a review convention. The other refusals: a verdict outside
`supported` / `unsupported` (a third value is a reader's hesitation wearing
the shape of a judgement), a row missing a field (a verdict about a
citation nobody can find again), and a repeated `sample_id` (one judgement
counted twice). All failures are reported together, one pass over the
reader's table.

**The measurement** (`measure_locator_validity`). The numerator is the
citations a human judged `supported`; the denominator is every citation
judged at all — unsupported ones included, because an unsupported citation
is a measurement, not a missing one. The `how` line states the sample size
and the number of reports. **An empty sample is NOT MEASURED, never 0/0**:
a rate over no judgements states a measurement that was not made, which is
the exact shape of fake green the work order forbids.

**The wiring** (`aggregate.py`, `cli.py`). The harness takes
`--citation-sample PATH`. Without it — which is every run until the human
pass happens — the `evidence-locator-validity` row is NOT MEASURED with a
derived reason saying where the table lives. With it, the row is measured,
and the row's context names the citations judged unsupported: the protocol
asks for *"denominators and failure cases"*, and an averaged-away failure
case is neither. A sample file that fails to load stops the run — a broken
input is a refusal, not a number.

**The comparison's entry.** `measure_locator_validity`'s output is a
`Measurement` with a numerator and a denominator, so it enters
`_comparison`'s `run_values` like every other metric's, and `pairs()` prints
it exactly when the baseline carries the same key. The frozen P1 baseline
([`LC-P2-00-baseline.json`](LC-P2-00-baseline.json)) was taken before this
machinery existed and carries no such key, so it prints no pair — the
intersection is the honest behaviour, and the first baseline taken after a
filled sample exists is where the pair starts printing.

## 2. What was already there: the miss, not an answer

The work order's negative clause needed no new code. `retrieve()`
([`evidence/retrieval.py`](../../src/labcairn/evidence/retrieval.py)) asks
the index `query_is_servable` before it searches, and a query the index
cannot serve — every term shorter than the trigram table's three
characters — comes back as `PROVIDER_FAILURE` carrying a
`ProviderFailure`, structurally distinct from `NO_HIT` (a search that ran
and found nothing) and from `FOUND`. `require_evidence` refuses both
negatives rather than handing a model empty evidence. The witness existed
before this piece: `test_a_query_the_index_cannot_serve_is_a_failure_not_a_miss`
(`tests/test_evidence_retrieval.py`), which asserts the failure status,
the empty excerpts, `may_proceed` false, and — against a served-but-absent
query — that a real miss is a different value.

## 3. The human path that completes it

The work order calls this the *labour*, and it is the only part not in
this tree. The steps, written down so they are a procedure and not an
intention:

1. Run the product over the evaluation corpus and collect the reports whose
   citations will be judged.
2. Read the material and, for each citation a report makes, judge whether
   the address it points at supports the claim it is attached to. Record
   one row per citation in the five-field schema — no text, no reasons.
3. Keep the table **outside this repository** — it carries addresses into
   the real corpus — and hand it to a run with
   `python -m tests.evaluation --citation-sample <path>`.
4. Take a new baseline over the filled sample; that document is the one a
   later retrieval change is compared against.

The tree carries the shape to fill:
[`tests/fixtures/retrieval/citation-support-sample.empty.json`](../../tests/fixtures/retrieval/citation-support-sample.empty.json),
whose `$comment` repeats the schema and the no-text rule.

## 4. Why NOT MEASURED still holds, and what the report says

No human pass over produced reports has happened, so the run has no sample
to measure. The report's row says so, derived from the run's own inputs:
without a `--citation-sample` the reason names the missing human labour and
where the table lives; with an empty table the reason names the 0/0 it
refuses to print. The derived reason is watched by
`test_a_not_measured_reason_may_not_contradict_the_tree` in
`tests/test_evaluation_harness.py`, which fails if the reason denies an
input the tree has.

## 5. The mutations

Every refusal above was mutation-checked on 2026-11-04, at this branch's
`04f2020`. The harness, for each row: apply the mutation to the committed
file (bytes-for-bytes, verified to have landed), run the witness, restore
the file. A mutation that does not apply is an error, not a surviving
mutant.

| # | The mutation | The witness that went red | What it said |
|---|---|---|---|
| M1 | `retrieve()`'s refusal branch deleted — a query the index cannot serve falls through to an ordinary search | `test_a_query_the_index_cannot_serve_is_a_failure_not_a_miss` | `assert <RetrievalStatus.NO_HIT: 'no_hit'> is <RetrievalStatus.PROVIDER_FAILURE: 'provider_failure'>` |
| M2 | the verdict vocabulary check disabled | `test_a_sample_with_a_verdict_outside_the_vocabulary_is_refused` | the refusal no longer fired, so the exception the test awaited never arrived |
| M3 | an empty sample measured as `MEASURED 0/0` | `test_the_empty_sample_in_the_tree_is_read_and_says_not_measured` | `assert not measured.measured` → `assert not True` |
| M4 | supported and unsupported swapped in the numerator | `test_a_judged_sample_measures_its_denominator_and_names_it` | `assert (1, 3) == (2, 3)` |
| M5 | the unsupported citations averaged away instead of named in the row's context | `test_a_handed_sample_measures_the_row_and_names_the_failures` | `assert "s-2" in context` — the row said `none` |

One command, as run (the script lives outside the repository):

```
python -I E:\labcairn-local\tmp\mutations\mutate_and_witness.py m1-silent-empty-answer "tests/test_evidence_retrieval.py::test_a_query_the_index_cannot_serve_is_a_failure_not_a_miss"
```

## 6. The witnesses, and where they are registered

The nine new tests live in `tests/test_evaluation_harness.py` — the
harness's own witness file — and are registered in
[`LC-P1-13-evaluation.md`](LC-P1-13-evaluation.md) §9's witness table, which
`test_the_evaluation_record_names_every_witness_in_this_file` re-reads from
the tree. No new test file was created, so the shard list is unchanged; the
file's own cost grew, which is the shard-cost witness's business and is
re-measured by the runner at the next run, per the repository's rule.

**What this document does not claim.** No retrieval quality. The number
this machinery produces is a measurement of whatever sample a person has
put behind it, and until that person has read the reports, the report's row
says NOT MEASURED — which is the claim this piece delivers.

---

## 4. The metric, measured — 2026-11-05

The sample the machinery was waiting for now exists. It was built from five
candidate reports over the public fixtures (45 citations: 26 at text-line
addresses, 19 at CSV cells), each row judged against the material at its
address.

| | |
|---|---|
| Sample | 45 rows — **36 `supported`, 9 `unsupported`**; the five-field table is `E:\labcairn-local\citation-sample\citation-support-sample.json`, outside this repository |
| Judgement | the coordinator read each citation against its address and wrote a recommendation; the owner accepted all 45 on 2026-11-05 |
| Run | `python -m tests.evaluation --citation-sample <the table> --out E:\labcairn-local\citation-sample\eval-run`, exit 0 |
| Metric | **`evidence-locator-validity: 36/45` (80.0%)** |
| Report | `E:\labcairn-local\citation-sample\eval-run\evaluation-report.md` (and `.json`), outside the repository |

**What the number is, and what it is not.** It is the share of judged
citations whose address supports the claim attached to it, over a sample of
45 synthetic-fixture citations. It is **not** a human-checked sample: the
judgement was the coordinator's reading, accepted by the owner, and this
record states that mechanism rather than calling it a person's. Under the
owner's decision of 2026-11-05 an independent agent session may stand in
for a human reader; this sample was accepted from the coordinator's
recommendations, so it is recorded as such.

**What the run did not move.** The frozen P1 baseline was taken before this
machinery existed and carries no locator-validity key, so the comparison
still prints no pair for it — the first baseline taken after this sample is
the one a later retrieval change will be compared against.

---

## 5. The frozen baseline over the filled sample — 2026-11-05

The first baseline taken **after** the filled sample exists is
[`LC-P2-26-baseline.json`](LC-P2-26-baseline.json). It was measured at
`c5e1f40cc204a225e5f2a7c8aec711d00363b116`, on a clean worktree, Windows 11
(Python 3.12.13), with `python -m tests.evaluation --citation-sample
<the 45-row table> --out E:\labcairn-local\citation-sample\baseline-run2`.

| | |
|---|---|
| Duration | **2082.2 s** |
| Exit | **2** — `real_model_smoke` was selected and could not run (no provider credential); the five offline classes all ran with **zero failures** (unit 1878, integration 1714, negative 388, e2e 143, repository 798) |
| `evidence-locator-validity` | **36/45** |
| Other metrics | numeric extraction 84/84, unsupported-claim detection 1/1, recovery 4/4, latency/usage 2080407/4934 |
| Comparison | `assess` reports **comparable** on all six conditions against the harness's own run basis |

**Two failed starts, recorded rather than hidden.** The first baseline run
stopped after 987.8 s with four classes `ran=False` and one integration setup
error; the two affected tests passed when re-run alone. Its output was not
frozen. The script also initially wrote the public fixtures' hashes into the
comparison basis, where the harness uses the eleven `CORPUS_FIXTURES` and
their `.expected.json` answer keys — a mismatch that would make every later
comparison fail `matched_task` and `matched_task_versions`. Both were
corrected before this document froze; no harness run was repeated for the
basis fix, because the report and the tree it measured are unchanged.

**The sample now has two independent readings.** The coordinator's 36/9
judgement and an independent reader's 36/9 judgement agree **45/45**; the
agreement record is `E:\labcairn-local\citation-sample\INDEPENDENT-AGREEMENT.md`.
Neither is a human being's reading, and this record does not call the sample
human-checked.
