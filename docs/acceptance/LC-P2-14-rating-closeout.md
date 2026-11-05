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
