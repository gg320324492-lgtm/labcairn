# LC-P1-13 — the public fixture corpus, and what is measured about it

**Work order:** LC-P1-13 (evaluation, fault injection and competitor baseline)
· **Status:** the fixture corpus is delivered and witnessed. The evaluation
harness that *measures* against it is T01's, and this document does not
claim anything about the product's behaviour.
· **Corpus version:** `2026-10-25.1`
· **Files:** `tests/fixtures/public/` · **Witness:** `tests/test_public_fixtures.py`

---

## 1. What the protocol asked for, and what this is

`docs/EVALUATION.md` fixes the requirement verbatim:

> Use permissively licensed or synthetic, clearly labeled materials. Minimum
> 3 tasks across distinct research genres (e.g. physical sciences,
> biomedical-style tabular measurements without real patient data,
> computational experiments), each with source PDFs/text, tabular data,
> grounded questions, and expected artifact checks. Fixtures must have actual
> source locators, hashes and answer keys; do not use generated outputs as
> their own oracle.

LC-P1-13's own build clause asks for *"at least 3 publicly shareable fixture
scenarios with actual answer/source locators and a negative/no-evidence
scenario"*.

**This document delivers the four scenarios and the witness that says they
are sound.** It does not deliver a score, and nothing here should be read as
one: the metrics the protocol names are measured by the harness (T01), and
three of the seven need inputs this subtask does not produce (a task corpus
the harness drives, a human-checked sample, and a corpus of source-change
runs).

## 2. The material, and its licence status

**Every byte of fixture material is synthetic.** Nothing third-party is
reproduced, so no third-party licence, attribution obligation or
redistribution restriction travels with the corpus.

That was a decision, not a convenience. The repository's copyright position
is unsettled — `LICENSE.PENDING.md` says in its first line that it *"is not
a license"* and that *"no license has been granted"* — so the corpus could
not have been released under a permissive licence of its own even if its
material had been permissively licensed. Reproducing third-party material
would have added a second, separate question (whose notice travels with the
distribution) to a question that is already open and is the owner's to
close.

| | |
|---|---|
| **Material origin** | synthetic, authored for this corpus |
| **Third-party material** | none — no attribution or notice obligation |
| **Licence of the material** | the repository's own pending status; `LICENSE.PENDING.md` grants nothing yet |
| **How it is labelled** | every material file carries `SYNTHETIC MATERIAL` near its top; the CSVs carry it in a `material_origin` column on every row |
| **Where the statement lives** | `MANIFEST.json`'s `notice` and `material_origin` fields, plus a test that reads both |

**The labelling is witnessed, not promised.** `test_every_material_file_says_it_is_synthetic`
opens every file in the corpus and fails if the marker is missing, and
`test_every_fixture_declares_its_material_origin_and_licence` fails if the
manifest stops saying the corpus is synthetic or stops saying the repository
grants nothing. A CSV of plausible-looking measurements is exactly the thing
a reader might mistake for a real result, so the marker is in the material
itself rather than only in a file beside it.

**The corpus is closed.** `test_the_manifest_names_every_material_file_and_no_other`
fails if a file appears in the corpus that the manifest does not name, or if
the manifest names a file that is not there. An unrecorded file is material
no answer key exists for, so a measurement over the corpus would be
measuring something the manifest does not describe.

## 3. The four scenarios

Each fixture is a directory: the material, plus its share of the corpus
manifest.

### 3.1 `physical_tension` — physical sciences

**Material.** `notebook.md` (a synthetic lab notebook: specimen, method,
units) and `measurements.csv` (five rows — three pulls of specimen `B-2`,
two of `B-1`).

**Questions and answer keys.**

| Question | Answer | Derivation | Locator |
|---|---|---|---|
| `tension.mean_peak_stress_b2` | `412.0 MPa` | mean of the `peak_stress (MPa)` cells of the three `B-2` rows (412.6, 418.3, 405.1) | `k=3:csv\|r=1:2\|c=17:peak_stress (MPa)` |
| `tension.crosshead_speed` | `0.5 mm/min` | the crosshead speed stated in the notebook's Method section | `k=4:text\|l=2:15\|s=6:Method` |

**The near-miss.** The artifact checks forbid `388.4` — specimen `B-1`'s peak
stress. A report that averaged the wrong specimen's rows produces a number,
and this is the number it produces.

### 3.2 `biomedical_panel` — biomedical-style tabular measurements, no real patient data

**Material.** `panel_notes.md` and `panel_readings.csv` (six synthetic
panels, two technical replicates each).

**No real patient data, and the corpus says so in three places.** The notes
state that *"Nothing here comes from a human being, an animal, a clinical
encounter, or a real laboratory"*, every subject code is `SYN-Pnn`, and every
CSV row carries the `material_origin` marker. The concentrations are
properties of a synthetic reference material, not of a subject.

**Questions and answer keys.**

| Question | Answer | Derivation | Locator |
|---|---|---|---|
| `panel.mean_concentration_p03` | `7.68 ng/mL` | mean of the `concentration (ng/mL)` cells of the two `SYN-P03` rows (7.62, 7.74) | `k=3:csv\|r=1:6\|c=21:concentration (ng/mL)` |
| `panel.detection_wavelength` | `450.0 nm` | the `detection_wavelength (nm)` column, which every row carries | `k=3:csv\|r=1:6\|c=25:detection_wavelength (nm)` |

**The near-miss.** `12.4` — `SYN-P01`'s concentration — is forbidden, so a
report that averaged the wrong panel's replicates is caught.

### 3.3 `computational_solver` — computational experiments

**Material.** `solver_log.md` and `solver_runs.csv` (five synthetic runs).

**Questions and answer keys.**

| Question | Answer | Derivation | Locator |
|---|---|---|---|
| `solver.mean_final_residual` | `0.000374` (dimensionless) | mean of the `final_residual (dimensionless)` cells over all five rows | `k=3:csv\|r=1:2\|c=30:final_residual (dimensionless)` |
| `solver.stopping_tolerance` | `1.0e-8` (dimensionless) | the stopping tolerance stated in the log's Configuration section | `k=4:text\|l=2:12\|s=13:Configuration` |

**Why this fixture is the aggregate one.** The other two ask for a mean over
a *named subset* of rows; this one asks for a mean over the whole table, and
its answer is `3.74e-4` — a number that appears nowhere in the material. A
report that reports one run's residual instead of the mean is wrong, and
`0.00051` (run `SYN-R3`'s, the largest of the five) is forbidden.

### 3.4 `no_evidence` — the negative scenario

**Material.** `protocol_excerpt.md` and `sample_log.csv` (three synthetic
samples).

**Question.** *"What was the pH of the wash buffer used on the synthetic
samples?"*

**Answer key.** `kind: "not_stated"`, `value: null`. The honest answer is
that the material does not say.

**Why this is the scenario that makes the corpus able to measure anything.**
`EVALUATION.md` lists *"unsupported-claim detection and appropriate
abstention"* among the metrics, and abstention only shows up where the
answer is not. A corpus of answerable fixtures cannot measure it at all.

**Two properties make this fixture real rather than decorative.**

1. **It is negative about one quantity, not about the document.** The
   material reports four quantities — the wash count (3), the buffer
   concentration (50 mM), the elution volume (250 µL) and the incubation
   temperature (37 °C) — and the test asserts each is present and
   resolvable. A material that said nothing would be satisfied by a system
   that abstains from everything, and would measure nothing.
2. **It names the quantity it does not report.** The excerpt says outright
   that it does not report the pH, the elution efficiency, the sample mass
   or the storage duration. That is what a real excerpt looks like, and it
   is why the check is for a *reported pH value* — a number and the word
   "pH" together — rather than for the word. A detector that forbade the
   word would fail on a fixture being straightforward about its own limits;
   a detector that looked only for the word would pass on a material that
   answers the question.

The artifact checks therefore require an **abstention**, forbid `50` (the
buffer concentration, which is not a pH) and `37` (the incubation
temperature, which is not a pH), and — importantly — require the report to
**cite what the material does report**, so an abstention is a statement about
this one quantity rather than a refusal to engage.

## 4. The locators are real, and the hashes bind the material

**Every locator resolves; none is compared as a string.** Each cited address
goes through three separate steps:

1. **Parsed** into a typed `SourceLocator` by the addressing module's own
   reader. A key that does not describe a real address is rejected, not
   string-matched.
2. **Canonically rendered** back to the key the manifest records, so the two
   spellings of one address cannot drift apart.
3. **Resolved** through `locate_anchor` against the material as ingested by
   the product's own ingest path. A locator naming a line or cell that is
   not there comes back `UNRESOLVABLE` — and that is a failure here.

**The hashes bind the answers to the bytes.** `MANIFEST.json` records each
material's SHA-256 and length;
`test_every_material_file_is_byte_identical_to_its_recorded_hash` fails if
either differs. A fixture edited without its answers being re-derived is a
fixture whose answers are answers about a file that no longer exists, and
without this check nothing would say so.

## 5. The answer key is not the product's own output

This is the requirement that decides the whole design: *"do not use
generated outputs as their own oracle"*. A fixture whose expected answer was
produced by running the product and recording what came out would test
nothing — the product would be graded against its own output, and a product
returning the wrong number would be graded correct.

So the two directions are kept apart:

- **The answer key was written by reading the material.** The values in
  `MANIFEST.json` were derived from the fixture files by hand.
- **The witness re-derives them from the material, through the product's own
  machinery** — and never by trusting the number written beside the data:
  - a **tabular** answer is recomputed by running the product's own
    `labcairn.analysis.mean` operator over a `Selection` of the material's
    cells, with the rows read out of the ingested material rather than out
    of the manifest;
  - a **prose** answer is recomputed by resolving the cited line and reading
    the quantity out of the resolved text with the product's own quantity
    reader.

A manifest that says `412.0` where the material says something else fails
here. A manifest that names the wrong rows fails here, because the rows come
from the material.

## 6. The mutation table

Every mutation below was applied to the committed corpus, the suite was
run, and the corpus was restored afterwards. **Each one went red.**

| # | Mutation | What went red | Why that is the right red |
|---|---|---|---|
| 1 | `tension.mean_peak_stress_b2`'s answer changed `412.0` → `999.0` | `test_the_tabular_answers_are_re_derived_by_the_products_own_operator`, `test_every_number_present_check_matches_its_question_s_answer`, `test_a_corrupted_answer_key_is_caught` | the answer no longer matches the material, the artifact check and the answer key disagree, and the self-check on the check fires |
| 2 | a citation pointed at row 99, which does not exist | `test_every_cited_locator_resolves_to_the_text_the_manifest_expects[physical_tension]`, `test_the_prose_answers_are_re_derived_from_the_resolved_text` | the address does not resolve; the second failure is the locator parse raising `LocatorKeyError` on the malformed key |
| 3 | a material's recorded SHA-256 replaced with zeroes | `test_every_material_file_is_byte_identical_to_its_recorded_hash[physical_tension]` | the material is not the bytes the answer key was derived from |
| 4 | a pH value written into the negative fixture's prose (`a pH of 7.2`) | `test_the_negative_fixture_really_does_not_answer_the_question` | the negative fixture now answers the question, so it no longer measures abstention |
| 5 | a material file's line endings changed to CRLF | `test_every_material_file_is_byte_identical_to_its_recorded_hash[physical_tension]`, `test_no_material_file_carries_a_carriage_return[physical_tension]` | the material's bytes are no longer the bytes the answer key was derived from, and the change is invisible to every other assertion — the file reads the same |

**Mutation 5 came from the delivery, not from the design.** The manifest was
first written with CRLF line endings, and Git's `text=auto eol=lf` rule would
have normalised it to LF on commit — silently changing the file's bytes, and
with them the hashes the answer keys depend on. The corpus would have passed
on the author's machine and failed on the runner, for a reason no assertion
about content could see. `test_no_material_file_carries_a_carriage_return`
now says so out loud, and the material is stored with LF endings.

**Mutation 4 found a real defect, and that is why it is in the table.** The
first version of the negative check searched the material's *cells* for a pH
and never looked at its prose, so mutation 4 passed — the corpus would have
kept a "negative" fixture whose material stated the pH in a sentence. The
check now reads every ingested unit of the material, prose included, and
matches a number together with the word "pH" in either order, allowing the
short connective ("pH **of** 7.2") that prose actually uses.

**Two of the mutations are now permanent tests**, so the corpus cannot
quietly lose them: `test_a_corrupted_answer_key_is_caught` and
`test_the_negative_check_notices_a_ph_value_appearing_in_the_material`
apply their corruption to a *copy* and never touch the committed corpus.

## 7. What is witnessed, and what is not

**Witnessed by `tests/test_public_fixtures.py`** (41 tests):

| Property | Test |
|---|---|
| three answerable fixtures across distinct genres, plus a negative one | `test_the_corpus_holds_the_fixtures_the_protocol_asks_for` |
| the corpus is synthetic, says so, and grants nothing | `test_every_fixture_declares_its_material_origin_and_licence` |
| every material file labels itself synthetic | `test_every_material_file_says_it_is_synthetic` |
| every material is byte-identical to its recorded hash and length | `test_every_material_file_is_byte_identical_to_its_recorded_hash` |
| the manifest names every material file and no other | `test_the_manifest_names_every_material_file_and_no_other` |
| no material file carries a carriage return, so its bytes are the same everywhere | `test_no_material_file_carries_a_carriage_return` |
| every cited locator parses, renders canonically, and resolves | `test_every_cited_locator_resolves_to_the_text_the_manifest_expects` |
| a locator naming an absent address does **not** resolve | `test_a_locator_naming_something_absent_does_not_resolve` |
| every tabular answer is re-derived by the product's own operator | `test_the_tabular_answers_are_re_derived_by_the_products_own_operator` |
| every prose answer is re-derived from the resolved text | `test_the_prose_answers_are_re_derived_from_the_resolved_text` |
| the negative fixture states no pH value | `test_the_negative_fixture_really_does_not_answer_the_question` |
| the negative fixture names the quantity it does not report | `test_the_negative_fixture_states_no_ph_value_while_naming_the_quantity` |
| the negative fixture is not hollow — four real quantities, all resolvable | `test_the_negative_fixture_is_not_hollow` |
| the negative fixture's checks require an abstention | `test_the_negative_fixture_says_the_answer_is_an_abstention` |
| every check agrees with its question's answer | `test_every_number_present_check_matches_its_question_s_answer` |
| every forbidden value is one the material really holds | `test_every_no_fabricated_value_check_names_a_value_the_material_holds` |
| a corrupted answer key is caught | `test_a_corrupted_answer_key_is_caught` |
| a corrupted locator is caught | `test_a_corrupted_locator_is_caught` |
| the negative check can itself fail | `test_the_negative_check_notices_a_ph_value_appearing_in_the_material` |
| the manifest parses and declares its shape | `test_the_manifest_is_valid_json_and_declares_what_the_corpus_is` |
| the answer kinds are a closed set | `test_every_question_names_a_kind_the_corpus_understands` |
| every question has at least one artifact check | `test_every_question_has_at_least_one_artifact_check` |

**Not witnessed here, and deliberately so:**

- **The product's answers.** Nothing in this subtask runs the product end to
  end or scores a report. That is the harness's job (T01), and the corpus is
  an *input* to it, not a result from it.
- **The four protocol metrics that need inputs this subtask does not
  produce** — the harness's own note lists the same four.
- **Whether the product abstains correctly on `no_evidence`.** The corpus
  makes that measurable; measuring it is the harness's job.

## 8. The suite, and one thing that is not this subtask's fault

**Measured, in a clean checkout of the merged branch**, with its own
virtualenv whose editable install points at that checkout rather than at the
developer's — so the numbers are the ones a CI runner would see, not the
ones a developer's tree happens to produce.

- `tests/test_public_fixtures.py`: **41 passed**.
- `ruff check`, `ruff format --check` and `mypy --strict` on the new file:
  **clean**.
- Every committed material blob's SHA-256 matches the manifest, and no
  committed blob carries a carriage return — checked against the blobs
  themselves, not the working tree, because the two can differ.
- The whole suite: every test passes except the three shard-coverage tests,
  which are red for the reason §10 gives.

**A measurement that was wrong, and what it taught.** An earlier run of the
whole suite reported two failures in `tests/test_readme_accuracy.py` —
`uv sync` failing while the README's own command was being run. The cause
was not the repository: a *second* suite run was in flight, and on Windows
the concurrent `uv sync` could not replace the console script the first run
had it using (*"failed to remove file ... labcairn.exe: 拒绝访问"*). With the
concurrent run stopped, `uv sync` succeeds and the README tests pass in
full. The failure was an artefact of running two suites at once on one
machine, and it is recorded here because **a number reported from a run
that was interfered with is not a measurement**, and because the same
interference can make a suite that passes look like one that fails.

## 9. Limits
1. **The answer keys are derived by hand, and the witness re-derives them
   from the material.** Both use the product's own reading of the material,
   so a *systematic* misreading shared by the key's author and the product
   would not be caught by this corpus. It would be caught by the corpus in
   `tests/fixtures/papers/`, whose answer keys are read off real papers.
2. **The prose answers are read by a deliberately narrow rule** — the first
   number in the cited line, checked by the product's quantity reader. A
   line holding two numbers would make the answer ambiguous; the corpus's
   lines do not, and the manifest's derivations say which number is meant.
3. **The negative fixture is negative about one quantity.** It is not a test
   of abstention in general, and it does not cover a material that is
   silent about the whole subject.
4. **The corpus has no PDF.** `docs/EVALUATION.md` says *"source PDFs/text"*,
   and this corpus supplies text and tabular data. The PDF locator kind is
   covered by the papers corpus in `tests/fixtures/papers/`, whose material
   is third-party and therefore cannot be moved here without carrying its
   licence obligations into the public alpha.
5. **The cost of this test file is not yet recorded.** The CI shard file
   records what each file costs on the runner, and this file is new, so it
   has no cost until the merge's remeasurement pass gives it one. See §10.
6. **The corpus is a starting point, not a closed set.** The manifest's
   `schema` field names a version (`labcairn.public-fixtures/1`) so that a
   later corpus can say which one a result was measured on — which
   `EVALUATION.md` requires: *"Results are benchmarks only when measured on
   immutable fixture/version labels."*

## 10. What the merge needs

**The shard list.** `tests/test_public_fixtures.py` is a new test file, and
`tests/test_ci_shard_coverage.py` fails if a test file is in no shard — a
file in no shard is a test CI never runs.

**This subtask did not edit `.github/ci-shards.json`**, for two reasons.
It is a hand-edited file that four windows are adding test files to at once,
so one merge-time pass is the only way it stays coherent. And the shard
file's costs are a **measurement**, and the project now watches that
mechanically: the file records the commit its costs were measured at, and
`test_the_costs_belong_to_the_tree_they_were_measured_on` fails when
anything under `src/` or `tests/` has changed since. Any new test file
makes the costs stale by that rule, so the fix is the repository's
`.github/remeasure_shards.py <run-id>`, which reads the per-file seconds
out of a CI run's `--durations=0` output and rewrites the table.

**So the merge sequence is: merge → CI runs → the coordinator runs
`remeasure_shards.py` with that run id → the shard file and its
`measured_at` are rewritten → the shard tests go green.** This subtask
adds one more file for that remeasurement to cover, and nothing else. The
costs must come from a runner: a development machine gives a different
*order*, not merely a different total, so a locally measured cost would be
the wrong number rather than an approximate one.

**The corpus is a versioned input.** Any change to a material file changes
its hash, and the witness fails until the manifest's hash and answers are
re-derived. That is the intended behaviour, and it is why the corpus carries
a version label.
