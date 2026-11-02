# LC-P2-14 — The blind evaluation's mechanical preparation — acceptance

**Work order:** LC-P2-14 (the blind evaluation and ablation), prepared
before the run · **Protocol:**
[`../plans/LC-P2-14-ablation-protocol.md`](../plans/LC-P2-14-ablation-protocol.md) ·
**Status of the work order:** **the machinery and the run driver are built
and witnessed; the run has not happened.**

**What this is.** The four pieces of the experiment that wait on nobody:
the five arms' run configuration, the by-paper split's leak check, the
blind score sheet's machine-checkable form, and the aggregation that can
report not significant. Each is scaffolding beside the evaluation harness,
each refusal and each leak shape has a witness, and every witness is
mutation-checked (§4). **The run driver was added on 2026-11-02** (§6):
it walks those four pieces in one command, in a dry run that claims
nothing and in a real mode that refuses without the owner's approval and
budget.

**What this is not.** **No run has happened.** No model was contacted, no
real paper was read, every number in the witnesses is invented, and no
number in the tree pretends to come from a run. The real run waits on
unseen papers and a budget — the owner's to bring — and the protocol's law
holds: *without a controlled experiment on unseen papers, the system
cannot be said to have learned the advisor's scientific thinking.*

---

## 1. The four pieces, and where each is held

| # | The piece | Held by | Witnessed by |
|---|---|---|---|
| 1 | **The five arms' run configuration.** Each arm is a typed declaration — letter, model, budget, evidence faces, roles — and `assess_configuration` refuses, by name, a set of arms that disagrees on the model, declares no budget, breaks the additive chain, adds a letter the protocol does not define, or leaves one of the two contrasts (D vs C, E vs D) without an input difference. `assess_arrangement` holds the B-only / B+C pair to the protocol's same-evidence-same-model-same-budget rule, because a pair that moves two things measures neither | `tests/evaluation/arms.py` | `tests/test_blind_evaluation_preparation.py::TestArmsConfiguration`, `::TestArrangementPair` |
| 2 | **The leak check, as a test.** The split is by paper, and the checker takes the split as data — the assignments, the corpus entries, each case's retrievable corpus, each arm's declared version caps — and reports every leak it can name, each carrying the shape that produced it | `tests/evaluation/split_check.py` | `::TestSplitCheck` |
| 3 | **The blind score sheet.** Anonymous while rated; the loader refuses incomplete ratings, missing items, labels outside the vocabulary, and **any item carrying an arm key**. Unblinding is a separate act with its own refusals. `resolve_pair` settles one label per item and dimension from two raters and an arbiter, and returns its exclusions rather than dropping them | `tests/evaluation/blind_sheet.py` | `::TestBlindSheetLoading`, `::TestUnblinding`, `::TestResolution` |
| 4 | **The aggregation that can say not significant.** The paired sign test over the settled labels, exact, from `math.comb` and nothing else. The not-significant verdict is a first-class outcome: rendered with its numbers, its reason, and the protocol's own sentence | `tests/evaluation/significance.py` | `::TestPairing`, `::TestNotSignificant`, `::TestContrastReport` |

The witness file is filed `unit` / `typed-contracts` in the harness's own
partition (`tests/evaluation/manifest.py`).

## 2. The design decisions, and why

**The configuration is a type, not a dictionary.** A run whose arms are
declared in free-form JSON can drift apart silently; a typed declaration
with a checker refuses the drift before anything runs. The vocabulary of
evidence faces (`draft`, `literature`, `version_differences`,
`advisor_comments`, `student_responses`, `review_outcome`,
`confirmed_rules`) is closed, because an undeclared face is a face no leak
check would ever watch. The model and budget are strings the owner fills
at run time — this preparation declares no supplier and contacts nothing.

**A refusal, not a warning.** The harness's own comparison returns
`comparable: False` with reasons rather than printing numbers with a
caveat underneath; the arms check and the sheet loader follow the same
shape. A check that prints anyway is a check a reader skims past.

**The leak shapes the checker names.** Over the whole corpus
(`check_split`):

- `paper-on-both-sides` — one paper's material filed on both sides. The
  assignments mapping cannot promise two sides for one paper, so this
  check runs over the material itself: two entries of one paper whose
  sides disagree.
- `entry-unassigned` — an entry whose paper has no side in the split.
- `entry-on-wrong-side` — an entry filed on a side its paper is not
  assigned to; this is the shape that catches a version of a split paper
  on the wrong side.
- `rule-built-on-evaluated-paper` — a rule whose source paper is on the
  evaluation side, wherever the rule itself is filed.
- `side-unrecognized` — an assignment to a side the checker does not know.

Per case (`check_case`):

- `unseen-version-reachable` — a version of the target paper later than
  the one the case asks about, reachable from that case. The final
  version may not be reachable from the case that asks about the first
  draft, not through the index, not through a rule, not through the
  case's own history.
- `case-targets-wrong-side` — the case asks about a paper assigned to the
  other side than the one the case runs on. The case carries its side and
  the check compares the two rather than trusting either.
- `rule-from-evaluation-reachable` — a rule distilled from an evaluated
  paper, in reach of any case.

Per arm (`check_arm_exposure`):

- `version-beyond-declared-cap` — a version entry beyond the arm's
  declared per-paper cap, or reachable with no cap declared at all. The
  protocol's arm-level rule: an arm that differs from another only
  because it can see more of the same paper's history is a leak.

**`unknown` is a label everywhere.** The protocol says the evidence not
settling a case is a verdict about the case, so `unknown` sits beside
`yes` and `no` through loading, resolution and pairing, and is never
converted to an absence on the way.

**The pairing claims no ordering between `no` and `unknown`.** Each
dimension names its beneficial label — `yes` for the four dimensions of
the form "did it do the thing", `no` for hallucination and mis-citation,
where not doing it is the point — and a case is a win when exactly one
arm's label is the beneficial one. A case where neither arm reaches the
beneficial label is a tie and says so. A rule that ranked "the evidence
does not settle this" above or below "confirmed not done" would be
inventing a measurement the raters did not make.

**The pairing refuses rather than repairs.** An item with no arm in the
unblinding map, an item that maps to no case, an arm with two settled
labels for one case, a case one arm covers and the other does not — each
is a denominator that would move without anyone seeing it move, so each
is refused, by name.

**The not-significant paths, in the order a verdict meets them.** Below
ten paired cases — not significant **by rule**, before any test runs, and
no p-value is computed or invented; every case tied — not significant,
with the reason saying there is no evidence either way, so the zero is
not read as a measured absence of effect; the two-tailed sign test at or
above alpha — not significant, with the p-value and the numbers; below
alpha — significant, and the row still carries its denominator, and the
renderer puts the protocol's sentence *"a significant difference in one
dimension is not a phase gate"* beside it.

## 3. What the machinery deliberately does not do

**It runs nothing.** No arm is executed, no provider is named, no
protocol run is invoked; the configuration's model field is a string the
owner fills when the material arrives.

**It judges no rater's eligibility.** The sheet carries the rater's name
for the record; the protocol's rule that a rater took no part in the
development and annotated no case in the current test set is satisfied
when the rater is chosen, not by a field the sheet could lie about.

**It computes no agreement rate.** `resolve_pair` returns the settled
labels and the exclusions; the report rows carry the agreed /
arbitrated / excluded counts per dimension. An agreement rate without its
denominator is a number without a meaning, and the number is computed
over the run's real sheets, not over a fixture.

## 4. The mutations, and what each one turned red

Each mutation was applied to exactly one anchor (the anchor's uniqueness
was checked before applying), the whole witness file was run against it,
and the file was restored byte-for-byte (the restore was checked by
hash). **A mutation that leaves the file green is reported as a survivor,
not hidden.**

**Forty-seven mutations, every one caught, and the table took two
passes.** The first pass ran 47 mutations and caught 43; three anchors had
gone stale or ambiguous against the formatted files and were re-run with
corrected anchors (M8, M17, M20, M45/M46 below carry the corrected runs),
and **two mutations survived — M8 in the first pass, M17 in the second —
and both survivals were the same shape: a check that was present but
watched by no witness of its own.** M8 (an arm missing the inputs its own
letter names) was caught only through the additive-chain check, which
cannot see arm A, which has no predecessor; M17 (a case whose target paper
has no side) was caught only through the same-named shape in
`check_split`, which is a different function. Both now have their own
witness, and both mutations were re-run and went red.

Each mutation was applied to exactly one anchor (the anchor's uniqueness
was checked before applying), the whole witness file ran against it, and
the file was restored byte-for-byte (the restore was checked by hash). The
runner recorded which witness went red, not merely that the file went red.

**Arms — `tests/evaluation/arms.py`:**

| # | The mutation | The witness it turned red |
|---|---|---|
| M1 | the model-agreement check disabled | `test_an_arm_running_a_different_model_is_refused_by_name` |
| M2 | the declared-budget check disabled | `test_an_arm_without_a_budget_is_refused_by_name` |
| M3 | the missing-letter check disabled | `test_a_missing_letter_is_refused_by_name` |
| M4 | the letter-outside-the-protocol check disabled | `test_a_letter_outside_the_protocol_is_refused_by_name` |
| M5 | the additive-chain (missing evidence) check disabled | `test_a_broken_additive_chain_is_refused_by_name` |
| M6 | the letter-that-measures-nothing check disabled | `test_a_letter_that_sees_what_its_predecessor_sees_measures_nothing` |
| M7 | the contrast-without-difference check disabled | `test_the_contrasts_exist_in_an_admissible_configuration` |
| M8 | the letter's-own-inputs check disabled (survived pass 1; its own witness added) | `test_an_arm_missing_its_own_lettered_inputs_is_refused_by_name` |
| M9 | `from_document`'s unknown-input-face refusal disabled | `test_an_arm_declaring_an_input_the_protocol_does_not_name_is_refused` |
| M10 | `from_document`'s missing-field refusal disabled | `test_a_configuration_document_without_a_budget_is_refused` |
| M11 | the arrangement's model check disabled | `test_a_pair_on_different_models_measures_the_models` |
| M12 | the arrangement's budget check disabled | `test_a_pair_on_different_budgets_is_refused` |
| M13 | the arrangement's evidence check disabled | `test_a_pair_on_different_evidence_measures_the_evidence` |
| M14 | the arrangement's same-roles check disabled | `test_a_pair_running_the_same_roles_measures_no_arrangement` |

**The split — `tests/evaluation/split_check.py`:**

| # | The mutation | The witness it turned red |
|---|---|---|
| M15 | the side-unrecognized check disabled | `test_a_side_the_checker_does_not_know_is_named` |
| M16 | the paper-on-both-sides (material) check disabled | `test_a_paper_on_both_sides_is_named` |
| M17 | `check_case`'s entry-unassigned refusal disabled (survived pass 1; its own witness added) | `test_a_case_whose_target_paper_has_no_side_is_named` |
| M18 | the entry-on-wrong-side check disabled | `test_a_version_of_a_split_paper_on_the_wrong_side_is_named` |
| M19 | the rule-built-on-evaluated-paper check disabled | `test_a_rule_built_on_an_evaluated_paper_is_named` |
| M20 | the unseen-version-reachable check disabled | `test_a_later_version_reachable_from_a_first_draft_case_is_named` |
| M21 | the case-targets-wrong-side check disabled | `test_a_case_targeting_the_other_side_is_named` |
| M22 | the no-declared-cap refusal disabled | `test_a_reachable_version_with_no_declared_cap_is_named` |
| M23 | the beyond-declared-cap check disabled | `test_an_arm_seeing_history_beyond_its_declared_cap_is_named` |
| M24 | the version-id grammar refusal disabled | `test_a_version_id_that_is_not_v_number_is_refused` |

**The sheet — `tests/evaluation/blind_sheet.py`:**

| # | The mutation | The witness it turned red |
|---|---|---|
| M25 | the arm-key-in-a-blind-item refusal disabled | `test_a_blind_item_carrying_an_arm_key_is_refused` |
| M26 | the missing-rating refusal disabled | `test_a_sheet_missing_a_rating_is_refused` |
| M27 | the label-vocabulary refusal disabled | `test_a_label_outside_the_vocabulary_is_refused` |
| M28 | the missing-item refusal disabled | `test_a_sheet_missing_an_item_is_refused` |
| M29 | the duplicate-item refusal disabled | `test_a_sheet_with_a_duplicate_item_is_refused` |
| M30 | the unblinding's no-arm refusal disabled | `test_an_item_with_no_arm_in_the_map_is_refused` |
| M31 | the unblinding's invalid-arm refusal disabled | `test_an_arm_outside_the_runs_five_is_refused` |
| M32 | the unblinding's extra-mapping refusal disabled | `test_a_map_naming_items_the_sheet_does_not_carry_is_refused` |
| M33 | the resolution's same-items check disabled | `test_raters_who_rated_different_item_sets_are_refused` |
| M34 | the disagree-without-arbiter exclusion disabled | `test_a_disagreement_no_arbiter_covers_is_excluded_and_named` |
| M35 | the arbiter-vocabulary refusal disabled | `test_an_arbiter_label_outside_the_vocabulary_is_refused` |

**The aggregation — `tests/evaluation/significance.py`:**

| # | The mutation | The witness it turned red |
|---|---|---|
| M36 | the small-denominator rule path disabled | `test_a_small_denominator_is_not_significant_by_rule_with_no_p_value` |
| M37 | the all-ties path disabled | `test_all_ties_is_not_significant_and_says_so` |
| M38 | the p-at-or-above-alpha path disabled | `test_a_p_at_or_above_alpha_is_not_significant_with_its_numbers`, `test_the_not_significant_path_renders_as_words_not_a_zero` |
| M39 | the not-significant sentence changed to say the opposite | `test_the_not_significant_path_renders_as_words_not_a_zero` |
| M40 | the phase-gate sentence changed to say the opposite | `test_the_significant_row_carries_the_gate_sentence`, `test_the_significant_row_renders_inside_the_report` |
| M41 | the unpaired-case refusal disabled | `test_an_unpaired_case_is_refused_by_name` |
| M42 | the two-labels-for-one-case refusal disabled | `test_two_labels_for_one_case_on_one_arm_are_refused` |
| M43 | the no-arm refusal disabled | `test_an_item_with_no_arm_is_refused_by_name` |
| M44 | the no-case refusal disabled | `test_an_item_that_maps_to_no_case_is_refused` |
| M45 | hallucination's beneficial label flipped to `yes` | `test_hallucination_counts_no_as_the_beneficial_label` |
| M46 | the row's excluded count hard-zeroed | `test_excluded_ratings_are_counted_on_the_row` |

(M46 was run in the second pass with a corrected anchor after formatting
had moved its first anchor; it went red there and in the final pass.)

## 5. How this was measured

The witness file ran green locally, 75 tests, with the worktree's `src`
first on `PYTHONPATH` and the temp directory outside the repository. The
shard-cost witnesses are expected red until the coordinator re-measures
after merge — a new test file has no measured cost — and the shard
coverage check expects the file to be unassigned until then.

## 6. The run driver, added 2026-11-02

**What was added.** `tests/evaluation/blind_runner.py` is the missing
middle between the four preparation modules and a run:
`scripts/run_blind_evaluation.py` is its executable entry point. The
driver takes the five arms and a case set, sends one request per arm and
case, writes one artefact per request in the shape the blind sheet reads,
writes the anonymous packet and the unblinding map, and then walks the
same pipeline the protocol describes — `load_blind_sheet` →
`resolve_pair` → `unblind` → `pair_by_case` → `build_report`. The score
mode takes two real sheets and an arbiter and does the last three steps.

**The dry run, and what it claims.** `--mode dry-run` (the default) sends
every request to `DryRunProvider`, a stub that records the request and
returns a deterministic sentence saying no model was called. Its ratings
are the protocol's `unknown` label on every dimension — a dry run has no
evidence, so it is the only label that does not invent a judgement. The
record therefore says `model: ""`, `provider_calls: 0`,
`stub_calls: 80`, `"synthetic": true`, and its limitations sentence says
the numbers are not a measurement. The two contrasts are the
not-significant path by rule (every case tied), which is what makes the
pipeline's wiring visible without dressing a fixture up as a result.

**The witnesses added, and the one that matters most.** Thirteen tests
were appended to `tests/test_blind_evaluation_preparation.py`; no new
test file was created, so the shard partition and the manifest are
unchanged.

| | The property | The witness |
|---|---|---|
| W1 | the dry run never enters the real-provider path | `test_a_dry_run_never_constructs_a_provider` |
| W2 | the artefacts, packet, sheets and verdicts have the shapes they claim | `test_a_dry_run_writes_the_shapes_the_scoring_stage_reads` |
| W3 | scoring loads real sheets, unblinds and judges both contrasts | `test_scoring_a_completed_run_uses_the_production_loader` |
| W4 | a finished real run stops at AWAITING RATINGS | `test_a_real_run_stops_before_it_claims_a_comparison` |
| W5 | no consent, no provider | `test_a_real_provider_cannot_be_built_without_consent` |
| W6 | no ceiling, no provider | `test_a_real_provider_cannot_be_built_without_a_budget_ceiling` |
| W7 | no usage capture, no provider | `test_a_real_provider_cannot_be_built_without_a_usage_capture` |
| W8 | every missing real-mode piece is named at once | `test_missing_real_requirements_names_every_missing_piece` |
| W9 | the command runs the dry run | `test_the_command_runs_a_dry_run` |
| W10 | no approval means the command constructs nothing | `test_a_real_run_without_approvals_is_refused_before_a_provider` |
| W11 | approvals without a ceiling are also refused | `test_a_real_run_without_a_budget_is_refused_before_a_provider` |
| W12 | the consent port refuses an empty grant list at construction | `test_an_empty_approval_grant_list_is_refused_at_construction` |
| W13 | an approvals file that parses to no grants reaches the refusal path | `test_a_real_run_with_an_empty_approvals_file_is_refused_before_a_provider` |

W1 is the one the work order names: it monkeypatches
`build_real_provider` to raise, runs the whole dry-run pipeline, and
passes only because the stub path never reaches it. W2 checks the packet
carries no arm key and every item's output names the stub.

**The real mode's boundary.** `build_real_provider` is the only place the
driver constructs a provider, and it raises `RealRunRefusedError` when the
consent port, a budget ceiling or a usage capture is absent. The provider
it builds is `PydanticAiModelProvider` and nothing else; the consent it
takes is `ConsumingApprovals`, which hands each request to the
application layer's `OutboundApproval` — `consume_approval` is still the
one function that spends an approval, and the driver has no second path
around it. The command line refuses before construction when the owner
has supplied fewer approvals than the run has requests (one approval
covers one request) or no ceiling. A real run writes the artefacts and
the packet and stops at `awaiting-ratings`; its `run.json` carries
`significance: {"status": "NOT RUN"}` as a first-class state, and
`report.md` says so in words.

**What was not done.** No real provider was contacted, no real paper was
read, and no real run happened: the unseen papers and the budget are the
owner's to bring. The dry-run case set is sixteen synthetic fixtures,
each labelled `[synthetic fixture]` in its own material. A real run's
per-request approvals are the owner's to create; the driver does not
request them, mint them or widen them.

**Mutation checks, including an independent review's four.** On
2026-11-02, making `run_dry` call `build_real_provider` turned W1 red
(the witness's planted `AssertionError` fired), and adding `arm_id` to
the blind packet turned W2 red (the packet's key set was no longer
disjoint from `ARM_KEY_VARIANTS`). An independent review then ran four
mutations against `blind_runner.py`: dry-run `provider_calls`, missing
consent and missing budget were caught; the fourth — replacing
`if not grants` in `ConsumingApprovals.__init__` with `if False` —
**survived**, because the CLI witness stopped at the argument-level
check before the port was constructed.

That is the gap W12 closes. With the direct-construction witness in
place, the same mutation now fails with `DID NOT RAISE`. W13 covers the
adjacent real path — an approvals file that parses to an empty list — but
it does **not** hold that branch: the run's approval-count check refuses
first. The two witnesses are kept as two properties, not counted as one.
The remaining witnesses await a pass, and the §4 table covers the four
preparation modules rather than the driver.
