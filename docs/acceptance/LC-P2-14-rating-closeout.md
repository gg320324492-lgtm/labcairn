# LC-P2-14 — The human rating close-out's machinery — acceptance

**Work order:** LC-P2-14 (the blind evaluation and ablation), rating
close-out preparation · **Protocol:**
[`../plans/LC-P2-14-ablation-protocol.md`](../plans/LC-P2-14-ablation-protocol.md) ·
**Mechanical preparation:**
[`LC-P2-14-preparation.md`](LC-P2-14-preparation.md) ·
**Status of this record:** **the rating machinery and the operator kit are
prepared; no human rating has been collected and no evaluation claim is made.**

**What this is.** The human half of the scaled blind run's close-out: two
anonymous rating sheets, a withheld unblinding map, a consistency check that
names disagreements, a third reader's packet, and the paired sign tests for
the two contrasts the work order names plus the protocol's arrangement pair.
The repository carries the witnessed machinery and this record only. The
run's answers, the raters' sheets and the unblinding map are outside the tree.

**What this is not.** This record reports no winner. It reports no human
rating, no agreement claim about real raters, and no significance claim about
the run. A not-significant result is a first-class outcome, and the machinery
is built to render it rather than round it up.

---

## 1. The products, and where each one lives

| # | The product | In the tree | Outside the tree |
|---|---|---|---|
| 1 | **Sheet assembly.** The run's completed call rows and answer bodies are read once; the answer bodies are copied into two blind sheets whose item ids are salted digests and whose orders come from two different seeds. No arm, case, issue key, annotator id, source id or other answer route is written into a sheet. A case key or source id quoted in an answer body is redacted before a rater sees it | `tests/evaluation/blind_rating_closeout.py` | `E:\labcairn-local\blind-rating-kit\lc_p2_14_rating_kit.py` |
| 2 | **The leak vocabulary.** The consistency check reads a flat list of anonymous ids and forbidden strings, not the unblinding map; no anonymous id is paired with an arm or case there | `blind_rating_closeout.make_leak_vocabulary` | `leak-vocabulary.json` |
| 3 | **The withheld map.** Item id to arm, case and source id, for unblinding only | `blind_rating_closeout.read_unblinding` | `withheld/unblinding.json`, `withheld/assembly.json` |
| 4 | **The consistency check and third reader.** Two completed sheets are compared item by item and dimension by dimension; the report carries the agreement denominator; every disagreement becomes a blind arbitration packet | `consistency_check`, `compare_ratings`, `build_arbitration_packet`, `load_arbitrations` | `disagreements.json`, `arbitration-packet.json`, `arbiter.json` |
| 5 | **The protocol's denominators.** The five dimensions do not all have the same denominator. The owner's human denominator mask is required; hallucination and mis-citation must cover every case, and no dimension is silently widened to every case | `read_denominators`, `_dimension_row`, `_contrast_report` | `denominators.template.json`, `denominators.json` |
| 6 | **The three contrasts.** `D vs C`, `E vs D` and the protocol's arrangement pair `B+C vs B-only` are paired by case and judged by the protocol's exact two-tailed sign test; the not-significant verdict is rendered with its numbers and reason | `_contrast_report`, `summarise_verdicts`, `CloseoutReport.render` | `closeout-report.txt`, `closeout-summary.json` |

The arrangement pair's 24 volumes enter the same close-out as the five arms'
60: the assembly casts their arm key from the call rows' roles (`guidance` alone
is `B-only`; `guidance` with `independent_critique` is `B+critique`), so each
of the 12 cases carries exactly one volume per arrangement arm, and the third
contrast pairs by case through the same code path as the other two. The
protocol names the comparison in its §1 ("the role arrangement to be measured
separately from the evidence") and its §5 ("More agents is not a gain ... If
`B+C` does not beat `B-only`, or does not beat it enough to pay for itself,
that is the finding") — so the arrangement's not-significant verdict is a
first-class finding, rendered the same way as the other two. The protocol does
not spell the third contrast's arithmetic out; what this close-out assumes,
and reports as an assumption, is that it is *like-for-like* with the two the
work order names — same five dimensions, same per-dimension denominator mask,
same exact sign test, same two-raters-plus-arbiter settlement for its volumes.
The protocol's arbitration rule (§3) and denominator rule (§4) are written per
case and per dimension, not per contrast, so the arrangement pair's volumes
take the same settlement and the same mask as the five arms'.

## 2. The operator's human steps

1. **Confirm the run and choose raters.** The owner confirms that the scaled
   run is complete. The owner chooses two raters who did not take part in the
   system's development and did not annotate any case in the current test
   set, and a third reader who is neither rater. The machinery can check that
   the arbiter's reader id is distinct from the two rater ids; whether the
   people behind those ids satisfy the protocol's eligibility rule is the
   owner's judgement.
2. **Assemble.** Run the kit's `assemble` command against the scaled run
   directory and a fresh output directory. The scaled run directory is
   read-only to the kit. The kit writes two anonymous sheets, a withheld
   map, a leak vocabulary, a denominator template and an empty arbiter file.
3. **Rate blind.** Give each rater one sheet and no other rater's sheet, no
   unblinding map, no case keys and no answer-route metadata. Each rater
   replaces every `unknown` placeholder on every item with `yes`, `no` or
   `unknown`, then sets that sheet's `rated` field to `true`.
   `unknown` is a considered label, not a missing value; the `rated`
   confirmation is what distinguishes it from an untouched placeholder.
4. **Check consistency.** Run the kit's `check` command. It re-checks both
   completed sheets for answer routes, reports the agreement count over its
   denominator, writes the disagreement list and writes a blind arbitration
   packet that carries the answer body and the two labels in sorted order —
   no rater id, arm, case or source id.
5. **Arbitrate.** Give the arbitration packet to the third reader. The third
   reader writes one protocol label for every disagreement into the arbiter
   file. The machinery refuses a missing arbitration, an extra arbitration,
   a label outside the protocol's vocabulary, and an arbiter whose reader id
   is one of the two raters.
6. **Fill denominators.** Copy the denominator template to
   `denominators.json` and fill each dimension's protocol denominator with
   the cases on which it is measurable. `hallucination_mis_citation` must
   cover every case. The machinery refuses a missing dimension, an unknown
   case, a repeated case, or a hallucination denominator that is not every
   case.
7. **Close.** Run the kit's `close` command with the denominator file. The
   machinery unblinds, settles every label, refuses any rating that is still
   unresolved, pairs all three contrasts by case, and writes the rendered
   report. A row that is not significant is rendered as `NOT SIGNIFICANT`
   with its wins, losses, ties, difference and p-value (or the reason no
   p-value was computed).

## 3. What the machinery refuses

* a blind sheet that carries an arm key, case key, issue key, annotator id,
  source id, or any other field outside the anonymous schema;
* a withheld value in a sheet's structural fields, or a source id or case key
  in an answer body;
* two sheets that cover different volumes, duplicate an item, present the
  same volume order, or do not carry byte-identical answer bodies;
* a sheet that is not confirmed as rated, or that lacks one of the five
  rating columns or uses a label outside the protocol's vocabulary;
* a disagreement without a third-reader decision, an arbitration about a
  rating that was not disputed, a duplicate arbitration, or an arbiter who is
  one of the two raters;
* a missing, malformed or out-of-run denominator, or a hallucination and
  mis-citation denominator that does not cover every case;
* a case one arm of a contrast covers and the other does not, or an arm with
  two settled labels for one case — the denominator is the paired cases, and
  a case counted on one side only would move it without saying so;
* a rating that remains unresolved after arbitration.

## 4. Witnesses

The witnesses live in the existing preparation witness file; no new test file
was created, so no shard, manifest or gate-class registration was needed:

* `TestHumanRatingCloseout::test_the_leak_vocabulary_carries_no_routes_to_the_answer`
  — the consistency check's input carries no id-to-placement map;
* `::test_the_84_volumes_are_anonymous_and_carry_no_route_to_the_answer` — 84
  invented volumes produce two sheets with no withheld value in their
  structural fields;
* `::test_a_mapping_value_in_the_blind_sheet_is_refused` — an arm or answer
  route smuggled into a sheet field is refused, not stripped;
* `::test_a_withheld_value_in_an_answer_body_is_refused` and
  `::test_a_case_key_in_an_answer_body_is_refused` — a route quoted into an
  answer body is refused;
* `::test_answer_routes_in_answer_bodies_are_redacted_before_rating` — route
  tokens read from the run are redacted before a rater sees an answer;
* `::test_a_withheld_value_in_a_structural_field_is_refused` — a withheld
  value hidden under a legal field name or dimension key is refused;
* `::test_the_two_raters_receive_different_orders` — one seed is not two
  independent readings;
* `::test_the_two_sheets_carry_the_same_answer_bodies` — the two readings are
  of the same texts, not of one rater's edited copy;
* `::test_an_unrated_sheet_is_refused_instead_of_defaulting_to_a_score` — the
  assembly's `unknown` placeholders are not silently scored;
* `::test_a_missing_arbitration_is_refused_not_counted_as_agreement` — a
  disagreement without a third reader never becomes a settled label, and the
  arbiter is not one of the two raters;
* `::test_the_arbitration_packet_carries_no_route_to_the_answer` — the third
  reader's packet carries two labels and the answer, never a placement;
* `::test_a_not_significant_result_is_reported_as_not_significant` — all ties
  are rendered as not significant, with their numbers;
* `::test_a_significant_verdict_is_not_rounded_into_a_not_significant_one` —
  the verdict words follow the exact sign test in both directions;
* `::test_the_denominators_are_refused_rather_than_defaulted` and
  `::test_each_dimension_uses_its_own_denominator` — the protocol's
  per-dimension denominators are required and are not silently widened;
* `::test_the_end_to_end_closeout_pairs_twelve_cases_on_each_contrast` — the
  whole close-out runs over 84 invented volumes, 420 settled labels and all
  three contrasts;
* `::test_the_arrangement_contrast_is_measured_not_hardwired` — the
  arrangement pair's verdict comes from its ratings, not from a rule: twelve
  `B+critique` volumes rated `yes` by both raters go significant on the four
  `yes`-beneficial dimensions while the untouched five-arm contrasts stay all
  ties, and the hallucination dimension ties on the same `yes` ratings
  because its beneficial label is `no`;
* `::test_the_arrangement_contrast_refuses_an_unpaired_case` — a case one
  arrangement arm covers and the other does not (cast by moving a volume's
  arm in the withheld map, which the blind sheets cannot see) is refused as
  an unpaired denominator.

## 5. Mutations, and what each one turned red

Each mutation was applied to exactly one anchor in
`tests/evaluation/blind_rating_closeout.py`, the named witness was run, and
the module was restored byte-for-byte (the restoration's SHA-256 was checked).
The mutation driver and its full JSON output live outside the tree at
`E:\labcairn-local\blind-rating-kit\mutate_rating_closeout.py` and
`E:\labcairn-local\blind-rating-kit\mutation-results\`.

| # | The property | The mutation | The red light |
|---|---|---|---|
| M1 | mapping leakage into a rating sheet is red | the item allow-list was widened to accept `arm` | `RatingRefusedError: rater-a has an item outside the anonymous schema` / `FAILED ...::test_a_mapping_value_in_the_blind_sheet_is_refused` |
| M2 | an identical volume order is red | the sheets' order-equality refusal was disabled | `Failed: DID NOT RAISE <class '...RatingRefusedError'>` / `FAILED ...::test_the_two_raters_receive_different_orders` |
| M3 | a missing rating silently scored is red | the `rated` confirmation refusal was disabled | `Failed: DID NOT RAISE <class '...RatingRefusedError'>` / `FAILED ...::test_an_unrated_sheet_is_refused_instead_of_defaulting_to_a_score` |
| M4 | a not-significant verdict written as significant is red | `verdict_word(False)` was made to return `SIGNIFICANT` | `AssertionError: assert 'NOT SIGNIFICANT' in 'D vs C on problem_identification: SIGNIFICANT; wins=0, losses=0, ties=12, p=n/a'` |
| M5 | an unfilled arbitration treated as agreement is red | `compare_ratings` was made to count a disagreement as agreement | `AssertionError: Regex pattern did not match. Regex: 'no third-reader arbitration' Input: '1 rating(s) remain unresolved after arbitration'` |
| M6 | the third contrast silently dropped is red | the `B+C vs B-only` row was deleted from `CONTRASTS` | `AssertionError: assert ('D vs C', 'E vs D') == ('D vs C', 'E...+C vs B-only')` / `FAILED ...::test_the_end_to_end_closeout_pairs_twelve_cases_on_each_contrast` |
| M7 | the arrangement contrast's direction flipped is red | the `CONTRASTS` row's treatment and control were swapped | `AssertionError: assert PairedCounts(wins=0, losses=12, ties=0) == PairedCounts(wins=12, losses=0, ties=0)` / `FAILED ...::test_the_arrangement_contrast_is_measured_not_hardwired` |

The seventh is the load-bearing one for the arrangement pair: a contrast
whose direction is wrong can still come out "significant", so the witness
holds the counts, not only the verdict word. After all seven the module was
restored to SHA-256 `a7fcf97df935a93bc323ab3fbed1b2d838c51bd24b143679f2aec34371d503c7`.

## 6. The end-to-end rehearsal

The kit was run end-to-end on **84 invented English answer volumes** — five
five-arm arms and the two arrangement variants, over 12 synthetic cases — and
on **invented ratings**, not on real answers. The rehearsal assembled two
anonymous sheets, marked them rated, planted one disagreement, ran the
consistency check, filled a legal all-cases denominator mask, arbitrated the
one disagreement as a third reader, and closed. The report's ten verdict rows
were all rendered `NOT SIGNIFICANT`, including the row whose one loss gave
`p=1.0000`; no row was rounded into a win. A second rehearsal of the
extension ran the same way with no planted disagreement and the `B+critique`
volumes rated `yes`: all three contrasts rendered — fifteen verdict rows, the
arrangement pair significant on the four `yes`-beneficial dimensions and
tied on hallucination — confirming the third contrast reaches the rendered
report through the kit's own file path. The real scaled run's answers were
assembled into two sheets, but no real sheet has been rated and no real
verdict exists.

## 7. Differences from the work order, and what remains

* **Two blind reads and independence.** The work order's shorthand says
  "two blind reads agreeing"; the protocol says two independent readings and
  an arbiter for every disagreement, with the agreement rate reported over
  its denominator. The machinery follows the protocol: it checks that two
  independent sheets cover the same volumes in different orders, reports
  agreement with its denominator, and sends disagreements to the third
  reader rather than requiring agreement for independence.
* **Per-dimension denominators.** The protocol gives the five dimensions
  different denominators. The work order did not name them, so the kit makes
  the denominator mask an explicit human input rather than guessing one. The
  machine checks its shape; the owner fills it from the material.
* **The third contrast.** The protocol also names `B+C vs B-only`, and this
  close-out now computes it: the 24 arrangement volumes carry the arm keys
  `B-only` and `B+critique`, cast by the assembly from the call rows' roles
  (measured on the scaled run's `measurements.json`: the 24 rows' `arm`
  letter is `B` for both variants, and `roles` is the only field that
  separates them — `["guidance"]` on calls 61–72, `["guidance",
  "independent_critique"]` on calls 73–84). The protocol does not spell the
  third contrast's arithmetic out; this close-out runs it like-for-like with
  the two the work order names, and §1 of this record says what that means
  and what stays the owner's to settle.
* **Rater eligibility.** That a rater took no part in development and
  annotated no current-test-set case is the owner's human judgement at rater
  selection. The machinery can only check that the arbiter's reader id is
  distinct from the two rater ids.


## 8. The second paper's 91 volumes

### 8.1 The two gaps, measured

The second paper's authorized run produced 91 answers: 86 in the scaled run
(60 five-arm calls over twelve cases, plus the 26 arrangement-pair calls over
thirteen cases) and 5 calibration calls. Two things kept that corpus out of
the rating table the close-out reads.

**Gap 1 — the role pair was not in the table.** The blind packet the
assembly produced covered 65 five-arm volumes. The 26 arrangement-pair
volumes (`arrangement_pair_unseen2`: thirteen cases times two variants) were
answered and were covered by the run's 91-entry unblinding, but no rating
table held them, so the protocol's third comparison had nothing to compare.

**Gap 2 — the ids had the wrong shape.** The close-out's identifier
grammar accepts `volume-<hex>` only; the run's own item ids are
`item-<hex>`. A withheld map keyed by the run's ids is refused
(`the unblinding map carries a non-anonymous item id`), and the assembly
itself refuses a sheet whose item ids are not anonymous
(`rater-a carries a non-anonymous item id`). The two papers therefore
spoke two different id languages, and the second paper's ids were the
language the close-out could not read.

### 8.2 The decision: re-mint, do not widen the grammar

Two repairs were available: widen the close-out to accept `item-` ids as
well, or mint the second paper's volumes into the `volume-` shape at
assembly time. **The repair chosen is re-minting.** The reason is measured,
not preferred:

* The run's `item-` id is an unsalted digest of `(run_scope, arm, case,
  roles)`. Rebuilding it from those four public fields reproduces
  **91 of 91** of the run's ids. An id that a rater can invert is not an
  anonymous id: it is a route back to the arm, carried on the face of the
  sheet. The `volume-` id is salted per assembly, so the same four fields
  do not produce it.
* Widening `_IDENTIFIER` to accept two prefixes would put both id
  languages in the same reader, and the reader could no longer tell from
  the id alone which language a sheet speaks. Re-minting leaves the
  grammar with one shape, so the first paper's sheets are unaffected **by
  construction** rather than by a test that has to keep passing.

The two properties the decision had to keep are therefore kept by
construction, not by inspection: one answer is never designated by two
anonymous ids (each volume is minted from the row's own name for its
answer, and the assembly refuses two volumes that mint to one id), and the
two run scopes' ids do not collide (91 run ids and 91 minted ids were
measured to share **0**).

### 8.3 What changed in the tree

`tests/evaluation/blind_rating_closeout.py` — `build_volumes` now reads both
row dialects, and nothing else changed:

* **The answer's name.** One run names each answer by the file it wrote;
  the other names it by the item id it minted. A row that names its answer
  two ways, or names it not at all, is refused.
* **The group.** A row that records no group still belongs to one: its run
  scope names it (`five_arm_unseen2` → `five_arm`,
  `arrangement_pair_unseen2` → `arrangement_pair`). A row whose scope
  contradicts its group is refused, and a scope that names no protocol
  group is refused rather than guessed at.
* **One answer, one volume.** An answer claimed by two run scopes is
  refused: the two scopes would be rating the same answer under two arms.
  The separate "two answer volumes carry the same source id" check was
  removed, because the claim map now holds that property and the old check
  could no longer fire.

`_IDENTIFIER`, `assemble_rating_sheets`, the anonymity checks, the pairing,
the sign test and the rendering are untouched.

### 8.4 The witnesses

Eight witnesses were added to the existing preparation witness file (no new
test file, so no shard, manifest or gate-class registration was needed).
The file's count went from 99 to 107.

* `TestTheSecondPapersAssembly::test_the_ninety_one_volumes_assemble_into_two_anonymous_sheets`
  — 91 volumes (A–E 13 each, `B-only` 13, `B+critique` 13), 91 distinct
  anonymous ids, no run id among them, two different rater orders, and the
  anonymity check passes;
* `::test_the_runs_own_item_id_is_not_an_anonymous_id` — the gap itself: a
  withheld map keyed by a run's `item-` id is refused;
* `::test_the_group_is_read_from_the_run_scope_when_the_row_records_none` —
  the calibration rows, which record no group, join the same assembly;
* `::test_a_row_whose_scope_contradicts_its_group_is_refused`;
* `::test_a_run_scope_that_names_no_group_is_refused`;
* `::test_one_answer_cannot_be_claimed_by_two_run_scopes`;
* `::test_the_first_paper_is_unaffected_by_the_second_papers_shape` — the
  first paper's 84 volumes still read exactly as before (12 per arm,
  `volume-` ids, two different orders);
* `::test_the_third_contrast_is_computable_once_the_arrangement_volumes_are_in_the_table`
  — with all 91 volumes rated, the close-out returns three contrasts and the
  arrangement pair is one of them.

### 8.5 The mutations

Seven mutations were applied to exactly one anchor each, the named witness
was run, and both files were restored byte-for-byte afterwards (the
restoration's SHA-256 was checked). The driver and its output live outside
the tree at `E:\labcairn-local\tmp\pc-1\mutate.py` and
`E:\labcairn-local\tmp\pc-1\mutations.txt`.

| # | The property | The mutation | The red light |
|---|---|---|---|
| M1 | both row dialects are read | the answer name was taken from the answer file alone | `RatingRefusedError: call 1 names no answer file and no item id` |
| M2 | the group is read from the scope | the scope was not consulted | `RatingRefusedError: call 1 carries no group and no run scope naming one` |
| M3 | a contradicting scope is refused | the contradiction check was disabled | `Failed: DID NOT RAISE <class '...RatingRefusedError'>` |
| M4 | an unknown scope is not guessed at | an unnamed scope fell back to the first group | `Failed: DID NOT RAISE <class '...RatingRefusedError'>` |
| M5 | one answer is not claimed by two scopes | the cross-scope check was disabled | `RatingRefusedError: call 66 repeats answer item-...` (the refusal changed, so the witness is red) |
| M6 | the volumes are re-minted, not carried over | the minted id was the run's own id | `RatingRefusedError: rater-a carries a non-anonymous item id` |
| M7 | the third contrast is computed | the arrangement pair was dropped from the contrast list | `AssertionError: assert ['D vs C', 'E vs D'] == ['D vs C', 'E...+C vs B-only']` |

### 8.6 The end-to-end rehearsal

Outside the tree, in `E:\labcairn-local\blind6-arms\`, the rating kit gained
an `assemble-unseen2` mode and a rehearsal script
(`rehearse_unseen2.py`) ran the whole chain over the **real** 91 answers of
the authorized run: assemble 91 volumes → both raters mark every label
`yes` (a simulation, not a judgement) → denominators over the 13 cases →
`close_out`. Measured output:

* the withheld map holds 91 items, all `volume-`, all distinct; the 91 run
  item ids and the 91 minted ids share **0** members;
* arms: `A`–`E` 13 each, `B-only` 13, `B+critique` 13 — the 26
  arrangement-pair volumes are in the table; 13 cases, 7 volumes each;
* the two raters received different volume orders, and no sheet repeats an
  item;
* `close_out` returned **15 verdicts** over **3 contrasts** (`D vs C`,
  `E vs D`, `B+C vs B-only`), each verdict 13 paired cases, 0 wins, 0
  losses, 13 ties, and every verdict rendered **NOT SIGNIFICANT**.

NOT SIGNIFICANT is the verdict the protocol calls a finding, not a failure
of the run, and the rehearsal produced it from simulated ratings. The real
sheets are still to be rated by two people and settled by a third; nothing
in this rehearsal is that.

The whole suite was run over the repository, with the temp directory outside
the checkout: 4902 passed, 1 failed, 14 skipped. The single failure is
`tests/test_fault_injection_e2e.py::test_a_task_continues_from_what_was_recorded_after_a_crash`,
which raises `sqlite3.OperationalError: disk I/O error` on
`PRAGMA journal_mode=WAL` — the flaky the database module's own comment
records as failing roughly two runs in five on that line. That file passes
on its own, and this change touches nothing in the database layer. The
shard-cost witness came out green: this change edits two existing files and
adds no new test file, so no measured per-file cost moved.


## 9. The close-out ran — with model readers, not human ones

**Status.** Both unseen papers' sheets were filled, checked, arbitrated and
closed on 2026-11-05. The close-out's numbers exist. **They are not a human
blind rating.** Both raters and both arbiters were independent model-reader
sessions with no project context, and the owner chose that arrangement on
2026-11-05. The protocol's condition — two independent **human** readers —
therefore remains unmet, and no capability claim is made from these numbers.

**What ran.** Each rater was a fresh session with no project memory; the
sheets carry no arm, and the readers did not open the unblinding maps. The
second reader's counts and the arbiters' decisions are recorded in the
rating logs and `arbiter.json` under each kit's `sheets/` directory
(operator-side, outside this repository).

| Paper | Labels | Agreement | Disagreements | Settled | Excluded |
|---|---|---|---|---|---|
| 1 (84 volumes) | 420 | **343/420 (81.7%)** | 77 | 420 | 0 |
| 2 (91 volumes) | 455 | **441/455 (96.9%)** | 14 | 455 | 0 |

Paper 1's third reader settled 77 disputes (75 yes, 2 unknown, 0 no);
paper 2's settled 14 (14 yes, 0 unknown, 0 no).

**Denominators.** The owner chose the **all-case wide mask** on 2026-11-05:
every dimension over every case — 12 cases for paper 1, 13 for paper 2 —
including hallucination and mis-citation. The protocol gives the five
dimensions different denominators; this record states the owner's choice
rather than treating the wide mask as the protocol's own.

**Close-out.** Paper 1: **all 15 verdicts NOT SIGNIFICANT** — the only
non-tied contrast is D vs C on `advisor_comprehension` (5 wins, 0 losses, 7
ties, p = 0.0625); E vs D on the same dimension is 0 wins, 2 losses, 10
ties, p = 0.5. Paper 2: **all 15 verdicts NOT SIGNIFICANT** — D vs C on
`problem_identification` 3 wins, 0 losses, 10 ties, p = 0.25; D vs C on
`advisor_comprehension` 2 wins, p = 0.5; E vs D on
`problem_identification` 1 win, p = 1.0; E vs D on
`advisor_comprehension` 2 wins, 1 loss, p = 1.0.

**What this is, and what it is not.** The machinery ran end to end on both
papers and produced data the close-out can read, with its denominators and
its failure instances named. It is **not** evidence of a capability gain,
**not** inter-human rater reliability, and **not** a substitute for the
human rating the protocol asks for. A human rating remains the owner's
step; when it exists, it replaces these sheets rather than adding to them.
