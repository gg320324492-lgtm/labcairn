# LC-P2-14 — The first unseen paper assembled into the five arms — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation
and ablation) · **Machinery:**
[`LC-P2-14-preparation.md`](LC-P2-14-preparation.md) · **This record:** the first
real unseen material put through that machinery.

**Status.** The material is assembled and every wire has been walked end to
end in a dry run: **60 stub calls, zero provider calls, zero money spent.** The
real run has not happened and cannot until the owner approves a budget. **No
arm has been measured, and nothing here says anything about capability.**

**What this record does not carry.** The paper's title, its sentences, its
numbers, its section headings and the names of the people who wrote and revised
it are not in this file and not anywhere in the repository. The material is
referred to as **unseen paper 1**, and each file by the first sixteen hex
characters of its sha256. The assembly's own outputs — which *do* carry the
material's text, because that is what an arm's prompt is — live outside the
repository under `E:\labcairn-local\blind5-arms\`, and
`tests/test_no_reference_leakage.py` is what keeps them out of the tree.

---

## 1. The material, as the product's reader measured it

Ten `.docx` files, one paper's evolution. Read with
`labcairn.material.ooxml.read_document` — the same reader the chain uses, not a
parallel implementation, because a measurement taken with a second parser
measures the parser.

| Version | Files | sha256 prefix | Tracked revisions | Margin comments |
|---|---|---|---|---|
| **v1** | 2 | `95a7e977b1f420bb`, `87833307de6d99f9` | 526 | 0 |
| **v2** | 2 | `ec3a2da1bd995d49`, `20638e48e8b7fe09` | 0 | 0 |
| v3 | 1 | `a7a38132cf35d363` | 113 | 0 |
| v4 | 1 | `e90659cbc54ee727` | 0 | 0 |
| v5 | 1 | `01e8fe66554f3e5d` | 0 | 0 |
| v6 | 1 | `0d1a6eb555d6105f` | 23 | 0 |
| **v7** | 1 | `46e8962723178156` | 0 | 0 |
| v8 | 1 | `4bab71ff32b1123a` | 0 | 0 |

**The version numbers come from the accepted text, not from the file names.**
Two files are one version when their accepted and rejected views are both
equal: v1 is two spellings of the same draft (identical `document.xml`,
different `docProps` and two images, so the *bytes* differ while the draft does
not), and v2 is likewise two spellings. Eight distinct versions across ten
files. v8 is the English translation of v7 and is a version of the same paper
for the split, not a stage of the argument.

**Zero margin comments, measured, not assumed.** Every one of the ten files was
opened and its part list read: **no file carries `word/comments.xml`**, and the
reader's comment count is 0 for all ten. The advisor's hand in this material is
entirely in-document: **662 tracked revisions** across the distinct versions
(526 + 113 + 23). Two files whose names say "comments" carry revisions, not
comments — which is why the names are not evidence and the part list is.

**One caveat on the arithmetic.** The reader reports 1188 revision events over
the ten files, because v1 exists twice and its 526 revisions are counted per
file. 662 is the count over distinct versions. The record says which is which.

**A second hand.** Two of v3's 113 revisions carry an author who is not the
advisor — the student's own edits, in the material's spelling. Named authors are
not reproduced here.

## 2. The task, as the protocol defines it

**The protocol's own shape, not the frozen baseline's three tasks.** §4 of the
protocol measures five dimensions per case (problem identification, evidence
support, comprehension of the advisor's response, hallucination and mis-citation,
abstention) plus cost and latency. A case is a section of a draft and a question
about it. Nothing in the protocol routes this paper through the LC-P2-00
reference tasks, and the arm table is built from evidence faces, not from those
three task ids. So the cases ask each arm to review one section of the draft.

**Which version the arms read — and why the obvious answer is wrong.** v1 is the
first draft, but its **accepted** view already contains the advisor's 526
revisions, so an arm given the accepted view is an arm given the answer. The
arms read v1's **rejected** view, which is the student's own text before the
advisor's hand. This is not an interpretation of the protocol; it is what
`split_check` enforces — a case that asks about v1 must not reach v2…v8, and the
accepted view of v1 *is* later material for that paper.

Twelve cases, cut from v1's rejected view at 1200 characters with the longest
chunk split until the set reached the sign test's floor of ten paired cases
(`significance.MIN_PAIRS`). Twelve, not more: each additional case multiplies the
run's cost by five arms' worth of calls.

## 3. The by-paper leak check, measured

Three independent measures, all run over the real chain and the real files. The
raw output is outside the repository (`blind5-leak-check.out`,
`batch5-leak-verdict.out`, `blind5-arms/leak-check.json`,
`blind5-arms/split-shape.json`).

### 3.1 Chain material sitting verbatim inside the paper

Units of at least twenty characters, whitespace-normalised, tested for exact
containment in the union of every file's accepted and rejected view:

| Chain project | Units tested | Verbatim inside the paper | Share of the project |
|---|---|---|---|
| proj-pilot-1 | 10700 | **0** | 0.0000% |
| proj-pilot-2 | 927 | **0** | 0.0000% |
| proj-pilot-3 | 4818 | **0** | 0.0000% |
| proj-pilot-4 | 972 | **9** | 0.9259% |

Nine units from proj-pilot-4, 622 characters in total, longest 101. The long
ones are instrument sentences: the same make and model of particle-size analyser
and the same microscope appear in both manuscripts, in the same word order. That
is two drafts of neighbouring experiments from one laboratory, not one paper
inside another. **No chain version, comment or rule was produced by this paper**
— if any had been, its sentences would be inside the chain, and the reverse test
is next.

### 3.2 The paper's sentences sitting verbatim inside the chain

964 distinct sentences of at least twenty characters were taken from the paper
and searched in each project:

| Project | Paper sentences found verbatim | What they are |
|---|---|---|
| proj-pilot-1 | 1 | a figure-panel label |
| proj-pilot-2 | **0** | — |
| proj-pilot-3 | 2 | one cited reference title, one journal volume and page range |
| proj-pilot-4 | 3 | the instrument sentence, and two figure-panel labels |

Per file, 4 of 318–341 sentences are verbatim in the chain (1.23%–1.26%), and
every one is a shared bibliography entry, a figure label, or an instrument
model. **A distilled rule would have shown up here as a run of argument, and no
run of argument appears.**

### 3.3 The confirmed rules against the paper

- **No confirmed rule shares a run of twelve characters or more with the
  paper.** Twenty-four rules, each tested sentence-fragment by sentence-fragment
  against the whole material: zero overlaps.
- **The rule statements carry no digits at all.** 24 of 24 confirmed rules have
  zero numeric tokens in the statement. **So the "does a rule carry this paper's
  specific numbers" test, which the brief expected to be the most likely true
  positive, is vacuous on this data** — not clean because nothing matched, but
  incapable of matching. It was replaced by the fragment test above and by the
  source-provenance test in §3.5, and this is said plainly because a check that
  cannot fail must not be reported as a check that passed.
- **The shared vocabulary is the field's, and it is heavy — but unevenly.**
  Seven of the paper's own terms were counted over the whole chain (counts
  below; the terms are named in English because the repository carries no
  material words):

  | The term | In the paper | In the chain | Reading |
  |---|---|---|---|
  | the bubble abbreviation (MNB) | 2130 | 14330 | the field's own shorthand |
  | the organism | 591 | 9510 | the same test organism across the lab |
  | micro-nano bubble | 308 | 5874 | the same object of study |
  | nano bubble | 314 | 6338 | the same object of study |
  | chlorination disinfection | 559 | **25** | **this paper's angle, nearly absent from the chain** |
  | the reagent formula | 810 | **0** | absent from the chain |
  | the reagent name | 507 | **0** | absent from the chain |

  So the chain shares this paper's *objects* and its *organism* — because three
  of the four pilot projects are the same laboratory's work — and does **not**
  share the chlorination-disinfection angle or either reagent spelling. That is
  the shape of a same-domain neighbour rather than a duplicate, and it is the
  reason §3.1's instrument sentences are the only verbatim overlap.

### 3.4 The split, through the checker itself

`split_check` over the real assignments — the four pilot projects on the
development side, unseen paper 1 on the evaluation side — with 175 corpus
entries (65 versions, 80 comments, 24 rules, 6 assessments):

- **`check_split` is clean**: no paper on both sides, no unassigned entry.
- **`check_case` is clean for all twelve cases**: each asks about v1, each
  reaches the development side and v1 only.
- **The negative control bites**: hand the same case every version of its own
  paper and the checker reports
  `unseen-version-reachable: version v2 of paper unseen-paper-1 is reachable
  from a case that asks about v1`, once per reachable version. The clean result
  above is therefore a result, not an empty machine.
- **`check_arm_exposure` is clean for all five arms** with the caps declared:
  unseen paper 1 at v1, and each development paper at the latest version the
  chain holds. **This is a usage requirement, not a product defect**: the checker
  treats an unnamed paper as having no cap and reports every version of it as
  reaching beyond that missing cap. An assembly that declares only the evaluated
  paper gets five arms of false leaks. Whoever assembles the next paper declares
  a cap for every paper in reach.

## 3.5 The rule face — and the conflict this assembly has to report

**The brief said the D and E arms retrieve over "the chain's 24 confirmed
rules". The measured citable set is 3.** Three numbers, all from the data:

| Set | Count | Where it comes from |
|---|---|---|
| Confirmed rules in the store | 24 | `guidance_rules` where `state='confirmed'` |
| What the product serves this reader | **9** | `labcairn.guidance.retrieval.search_rules` over the real store, read-only |
| What the leak gate leaves standing | 18 | six withheld, see below |
| **The face the arms actually carry** | **3** | the intersection of the two |

**The 15-rule gap is the product's own expiry rule working.** `search_rules`
serves a confirmed rule only when its sources resolve, are reachable by the
reading permission, and carry a judgement that says the change answered. It is
"an expired thing is judged by its state, not by the clock", and the state is the
chain's. **24 is a row count; 9 is what a card may cite.** The protocol's arm E
says "the review outcome and the confirmed rules" — and the confirmed rules it
means are the ones that stand, not the ones in the table.

**The six the gate withheld.** A rule was withheld when the chain material its
own sources resolve to sits verbatim inside the unseen paper and the chain holds
that material in only one project. All six resolve to proj-pilot-4 — the
same-laboratory neighbour of §3.1 — and their overlapping source units are the
nine instrument sentences, longest 101 characters. These six are *inside* the
product's 9, which is why the intersection is 3: the product would serve them to
this reader, and the leak gate is what stops them.

**Why the gate withholds rather than keeps them.** A rule distilled from a
sibling experiment in the same laboratory, whose methods text this paper reuses
verbatim, is a rule this paper has already paid for. Serving it to arm E would
give arm E the shape of the answer while arm D got only the advisor's process,
and the difference the protocol wants to measure — does the *outcome* help beyond
the *process* — would then be partly an artifact of one laboratory writing the
same instrument sentence twice. Withholding is the conservative act, and it is
reported per rule with its widest overlap and its carrier count in
`blind5-arms/retrieval-report.json`.

**The choice the owner has to make, and this record does not make.** Three rules
in arm E's rule face is thin: E vs D may then measure nothing because there is
barely anything in the difference. The options are (a) run with 3, accept the
thinness and report it; (b) relax the gate to "withhold nothing, serve the
product's 9" and record the sibling overlap as a known confound; (c) choose an
unseen paper from a different laboratory, which removes the confound but is a
different paper. **This assembly ships (a) — the conservative setting — because
the machinery must not be tuned to make a contrast look meaningful.** The brief's
"24 rules" assumption is what is in conflict with the real material; the
protocol itself says only "the confirmed rules", and §3.5 shows which of those
are actually citable.

## 4. The five arms, assembled

Each case carries all seven protocol faces — `CaseSpec` refuses a case with a
missing face, because a silently shorter prompt is an undeclared difference
between arms. The unseen paper supplies `draft` **only**; the other six come from
the development side, because an arm that could see this paper's own later drafts
would be the leak §6 of the protocol names first.

| Arm | Faces | Measured prompt size (mean per case) |
|---|---|---|
| A | draft | 1644 chars |
| B | + literature | 1949 chars |
| C | + version differences | 3069 chars |
| D | + advisor comments, student responses | 4147 chars |
| E | + review outcome, confirmed rules | 4525 chars |

**The additive chain is visible in the bytes**, which is the property
`assess_configuration` watches: each arm is strictly longer than the one before
it, and E vs D and D vs C each carry an input difference.

**Two faces say what they do not have, in the text a model reads.** The
`literature` face states that this assembly reached no external corpus and spent
no money, so arm B is arm A plus a sentence — the owner's run has to name a
literature source or B measures nothing. The `student_responses` face carries
what `response_links` actually holds, and says so when a comment has no recorded
response instead of implying one. An empty face described as empty is a
limitation in the report; an empty face dressed as material is a fake.

**Per-case retrieval is recorded, not summarised.** For each of the twelve cases
the report names the rules and comments that case reaches, by the store's own
containment matching over the rule's statement, context and scope. Where a case
reaches no rule, the face says so.

## 5. The blind sheet skeleton

- `blind_packet.json` — 60 items, one per arm per case, each carrying `item_id`,
  `case_id`, the question and an empty `output` for the run to fill. **No arm
  key**, and the item ids are the driver's own `item_id_for` digests, so the
  packet gives a rater nothing to unblind with.
- `sheets/rater-a.skeleton.json`, `sheets/rater-b.skeleton.json` — the loader's
  own shape, every dimension at the protocol's `unknown` label. 60 items, 300
  ratings. **This is the skeleton, not a result**: `unknown` means *the evidence
  does not settle this*, and a dry run has no evidence.
- `unblinding.json` — the item-to-arm map, written apart from anything a rater
  reads, with the notice that it is the unblinding act.

Both the skeleton and the packet were pushed back through the real
`load_blind_sheet` (60 items accepted, 300 ratings read), and the negative
control was re-run against the same loader: **an item carrying an `arm` key is
still refused** — `item item-3b2d08944b47f986 carries the key 'arm', which names
an arm; a blind sheet is anonymous until unblinding`. So the skeleton's blindness
is measured, not asserted.

## 6. The dry run, walked end to end on the real assembly

`python scripts/run_blind_evaluation.py --mode dry-run --cases
blind5-arms/cases.json --out blind5-arms/dryrun`, exit code **0** read from the
command itself, not from a pipe.

| The run says | |
|---|---|
| status | `dry-run-complete` |
| model | empty |
| provider calls | **0** |
| stub calls | 60 |
| split clean | true |
| both contrasts, all five dimensions | wins 0, losses 0, **ties 12**, significant **false** |

Twelve paired cases clear the floor of ten, so the sign test computes rather than
short-circuiting — and the verdicts are still ties, because every rating is
`unknown`. The report's own limitation line is the one the machinery writes:
*the dry run used a stub that is not a model; every rating is the protocol's
unknown label; the numbers are not a measurement of any arm's capability.*

**Artifacts**: `dryrun/artifacts/` (60), `blind_packet.json`, `ratings/`,
`significance.json`, `significance.md`, `report.md`, `run.json`,
`unblinding.json`.

## 7. The real run's budget shape, measured from the assembly

Five arms × 12 cases = **60 calls**. The protocol's arrangement pair (B-only and
B+C, same evidence, same model, same budget) adds 2 × 12 = **24 calls**. One
unseen paper, run properly, is **84 calls**.

| | Input tokens (estimated) | Output tokens (at 700/call) |
|---|---|---|
| A | 9389 | 8400 |
| B | 10304 | 8400 |
| C | 18893 | 8400 |
| D | 23301 | 8400 |
| E | 25812 | 8400 |
| **Five arms** | **87699** | **42000** |

**Estimated total input + output for one paper: about 130000 tokens.** The
estimate is CJK characters counted as one token and other characters per four,
which is a statement about size, **not** a provider meter — the run's record
carries the metered count, as LC-P2-18's precedent requires.

**This estimate did not survive the calibration.** The owner approved a real
run on 2026-11-04 against that shape, with one condition: measure one case
first, and stop if the real cost differs materially. It did. The three arms
that answered a single case metered **5010 input and 47769 output tokens**
(A 1047/11791, C 1693/14717, E 2270/21261), against an estimated 7308 input
and 3500 output for a whole five-arm case — **4.88x** the estimate, driven
almost entirely by the model's long reasoning output, not by the prompts. The
input estimate was roughly right; the 700-token-per-call output allowance was
wrong by an order of magnitude. Extrapolated to 84 calls the measured size is
**about 1.48 million tokens**, not 130k, and the three successful calls took
397.5 seconds of wall clock. **Scaling was not started**, as the owner
instructed. The wrong estimate is kept above rather than silently replaced,
because a corrected number needs its wrong predecessor visible. The measured
numbers, the per-call ledger and the reasons are in the operator-side report
outside this repository, under `blind5-arms/live/CALIBRATION-REPORT.md`.

**The owner's two decisions.** The citable rule face is the **measured three**
(24 confirmed rows → 9 served by `search_rules` → 6 withheld by the leak gate
→ 3), not 24, and the gate was not relaxed; the three numbers and their
provenance are stated where the result is reported. The real run was
authorized; calibration spent money, no full run did.

**No USD figure is computed here and none belongs in this tree.** The repository
carries no unit price, and the money's source is the owner's billing console.
One approval record per call is still required — the driver refuses a run whose
approvals are fewer than its requests — and the approvals' cost is not zero
even when the outbound bridge refuses, because the consent port runs before
the wire.

Per annotator-hour rather than per token, the run also costs two independent
raters over 60 items × 5 dimensions, plus an arbiter for every disagreement.

## 8. The recalibration: repaired machine, one case, still no scaling

The owner's next decision was to repair the machine and measure one case again
before any 12-case spend. The three gaps are now fixed with mutation-checked
synthetic witnesses:

1. **The event-loop fault.** A shared keep-alive connection belonged to a loop
   the adapter had already closed; the next `send` refused in 0.02s with
   `Event loop is closed`. Both the plain client and the sniffer's own
   transport now disable pooled keep-alive connections. A loopback HTTP/1.1
   server reproduces the alternating fault, and six sequential sends through
   each product client shape survive six fresh loops.
2. **Approval consumption.** An approval is verified and reserved before a
   request, but spent only after the wire sniffer observes a measurable
   response. A local fault leaves the row `GRANTED`; a response that bypasses
   the wire is refused. Consecutive calls each need their own observation.
3. **Output policy.** The provider sends `max_tokens=12000` and
   `reasoning_effort=low`. A reply whose `finish_reason` says `length` raises
   `ProviderOutputTruncatedError` before any artefact, blind packet or rating
   can carry it. The cap was derived from the three complete calibration
   answers (the largest measured answer was 4797 tokens in a generic
   tokenizer); 12000 is a ceiling, not an instruction to fill it.

The protocol's arrangement pair now has a runnable path. Its two B variants
share an arm id, differ only in roles, and are assessed by the arrangement
check rather than the five-letter check. Their anonymous item ids include the
roles, their prompts differ in the critique instruction, and their one
contrast is `B+C vs B-only`. A pair that moves evidence, model or budget is
still refused; so is a third variant.

**The recalibration proper spent exactly five calls.** Every arm answered,
every answer was complete, and the consent ledger ended with five `CONSUMED`
rows. The metered rows are in the operator-side report and its
`measurements.json`, outside this repository.

| Arm | Input | Output | Total | Wall clock |
|---|---:|---:|---:|---:|
| A | 1047 | 3715 | 4762 | 53.53s |
| B | 1119 | 3712 | 4831 | 37.42s |
| C | 1693 | 4200 | 5893 | 32.78s |
| D | 2081 | 3821 | 5902 | 39.20s |
| E | 2270 | 3551 | 5821 | 50.30s |
| **Five arms, one case** | **8210** | **18999** | **27209** | **213.23s** |

Against the old calibration's **52779** tokens for three answering arms,
**27209** for all five is a **48.45% reduction** (25570 fewer tokens). It is
still **2.52x** the original 10808-token estimate for a whole five-arm case.
The new 12-case shape is **326508 tokens** for the 60 five-arm calls. Using
B's metered two-call cost as a proxy for the arrangement pair's two calls per
case adds **57972 tokens** for its 24 calls: **384480 tokens for 84 calls**,
plus a mean-shape cross-check of about **457111** tokens (5441.8 per call).
At the measured mean of 42.646s per call, 84 sequential calls are about
**59.7 minutes**, not the old three-hour extrapolation. These are shapes for
the owner's decision, not a budget that has been approved. **USD is not
computed here**; the owner's billing console is the money source.

**The 12-case scaling run was subsequently authorized and completed.** Its
measured shape is §9; the recalibration's 384480-token estimate and
457111-token mean-shape ceiling are the budgets the run was held to.

## 9. The authorized 12-case scaling run

The owner approved the scaled run against the recalibration's budget shape.
The run made **84 calls**: 60 five-arm calls and 24 arrangement-pair calls.
All **84** answered, no response was truncated, no approval was spent twice,
and the product's own ledger ended with 84 `CONSUMED` rows. The cumulative
metered total was **398555 tokens** (115337 input, 283218 output), **87.19%**
of the 457111-token hard ceiling; the gate was not triggered and 58556 tokens
of headroom remained. Wall clock was **3115.56s / 51.9 minutes**. **No USD
is computed here**; the owner's billing console is the money source.

| Run scope | Arm / roles | Calls | Input | Output | Total | Wall clock |
|---|---|---:|---:|---:|---:|---:|
| five arms | A, guidance | 12 | 10973 | 37780 | 48753 | 390.61s |
| five arms | B, guidance | 12 | 11693 | 39767 | 51460 | 469.56s |
| five arms | C, guidance | 12 | 18776 | 46309 | 65085 | 501.62s |
| five arms | D, guidance | 12 | 24158 | 39072 | 63230 | 418.19s |
| five arms | E, guidance | 12 | 26063 | 39348 | 65411 | 499.06s |
| arrangement pair | B-only, guidance | 12 | 11693 | 37531 | 49224 | 404.74s |
| arrangement pair | B+C, guidance + critique | 12 | 11981 | 43411 | 55392 | 431.78s |
| **Total** | | **84** | **115337** | **283218** | **398555** | **3115.56s** |

An earlier attempt stopped before its first provider call with
`BudgetEnforcementUnavailableError`: the product's token ceiling requires a
capability probe that the 84-call authorization did not include. It spent
zero tokens and zero approvals; its record is archived separately. The run
that completed used the operator-side cumulative meter as the hard stop and
the product's 84-request ceiling, so no unapproved probe was made.

The first material build exposed a **new** machine defect: the five-arm B
answer and the arrangement pair's B-only answer had the same arm id, case and
guidance role, so their old anonymous item digests collided and 12 artifact
files overwrote 12 others. No answer was lost — every paid-for answer had
already been written per call — and no new provider call was made. The run
scope is now part of the item digest, artifact provenance and unblinding
map. The materials were rebuilt from the paid-for answers into **84 distinct
anonymous items**, with a mutation-checked witness. The blind packet,
unblinding map and rating template live outside this repository under
`blind5-arms/live/scaled/`; no answer or material text is in the tree.

**The machine side is complete; the measurement is not.** D vs C and E vs D
each have 12 paired answer sets and five protocol dimensions, but the two
independent human raters and the arbiter have not supplied sheets. The
machine-side record says `NOT RUN`, with no wins, losses, ties, p-value or
significance verdict. `unknown` and `not significant` are first-class
results, and no unscored answer is promoted into a significance claim. The
same `NOT RUN` shape applies to B+C vs B-only. A second unseen paper and the
human ratings remain owner-side work.

## 10. What the real run still needs, in order

1. **Two annotators who did not develop the system and did not annotate the
   current test set**, and an arbiter for disagreements (§5 of the protocol).
   The blind packet is ready; no sheet has been filled and no significance
   has been computed.
2. **A literature source for arm B** — or B is declared as a control that
   repeats A, which the record must say before the run rather than after.
3. **More unseen papers.** One paper gives twelve paired cases; the protocol's
   conclusion is about the system, not about one manuscript, and the split is
   checked per paper.

## 11. What the calibration changed in the tree

**The assembly itself changed no `src/` and no `tests/` file.** The seven-face
case shape, the additive chain, the split checker with its version caps, the
blind loader and the paired sign test all ran against real bytes and real store
rows. Three things it found are **usage requirements the operator has to meet**,
recorded above rather than patched into the code: every paper in an arm's reach
needs a declared cap (§3.4), the citable rule count is the product's serving
answer rather than the table's row count (§3.5), and the distinctive-number
check is vacuous because the rules carry no digits (§3.3).

**The calibration did change two lines of the driver**, because real requests
could not otherwise leave the process. Both are minimum fixes, both have a
witness, and each witness was mutation-checked: restoring the old line made it
go red.

| Gap the real run hit | The fix | The witness |
|---|---|---|
| `--task` was a raw string inside `TaskId` (a `NewType` does not convert at runtime), so the approval ledger's UUID task id never matched and every grant failed `task_scope_mismatch` **before any request** | parse it as `TaskId(UUID(args.task))` before the workspace is opened; a malformed id is a refusal that reads no files | `test_the_real_run_parses_the_task_id_as_a_uuid`, `test_a_real_run_refuses_a_task_id_that_is_not_a_uuid` |
| the CLI exposed no request timeout, and a full case prompt made the endpoint's generation exceed the library's 60-second default (`ReadTimeout` classified as a transient provider failure) | `--timeout-s`, handed to `ProviderSettings.timeout_s`; the default stays 60 | `test_the_real_run_hands_its_timeout_to_the_provider_settings` |

80 blind-evaluation witnesses pass; both mutations were restored byte for byte
after they reddened. **That calibration created no new test file**, so no shard
or manifest registration was needed, and `docs/` and `scripts/` are not what
the shard-cost witness watches. The repairs in §8 did add
`tests/test_blind_evaluation_machinery.py` and register it in the evaluation
manifest; its costs have not been measured on a runner, so the CI shard-cost
witness is expected to refuse the hand-edited list until an authorized run
remeasures it. Costs come from a runner, not a development machine. This
record carries **no Chinese run at all**, so
`CJK_RUN_CEILINGS` needs no new entry and the material-quotage witness stays
green by the same measurement that reddens it if this file ever quotes the
paper. The owner's approval phrase stands verbatim on line 2 of the operator's
report outside this repository, never in the tree.

---

# LC-P2-14 — The second unseen paper assembled into the five arms — acceptance

**Work order:** [LC-P2-14](../plans/LC-P2-14-ablation-protocol.md) (the blind evaluation
and ablation) · **Machinery:**
[`LC-P2-14-preparation.md`](LC-P2-14-preparation.md) · **Precedent:** the first
unseen paper, §1–§11 above · **This record:** the second real unseen material put
through that machinery, on the owner's delivery of 2026-11-05.

**Status.** The material is assembled and every wire has been walked end to end
in a dry run: **65 stub calls, zero provider calls, zero money spent.** The real
run has not happened and cannot until the owner approves a budget. **No arm has
been measured, and nothing here says anything about capability.**

**What this record does not carry.** The paper's title, its sentences, its
numbers, its section headings and the names of the people who wrote, revised and
commented on it are not in this file and not anywhere in the repository. The
material is referred to as **unseen paper 2**, and each file by the first sixteen
hex characters of its sha256. The assembly's own outputs live outside the
repository under `E:\labcairn-local\blind6-arms\`, beside paper 1's
`blind5-arms\`; `tests/test_no_reference_leakage.py` is what keeps them out of
the tree.

## 12. The material, as the product's reader measured it

Eight `.docx` files, one paper's evolution — a **different-domain** manuscript
(carbon emissions and air pollution; the chain's four papers are water
treatment), which is the property the split wants in an unseen paper. Read with
`labcairn.material.ooxml.read_document` — the same reader the chain uses.

| Version | File (sha256 prefix) | Tracked revisions | Margin comments |
|---|---|---|---|
| **v1** | `e33f1ba60b45a1f0` | 0 | 0 |
| v2 | `0d5289424e2c2fd3` | 0 | 0 |
| v3 | `220965d897a2b5ca` | 0 | 0 |
| v4 | `58c9e06495bbf22a` | 0 | 0 |
| v5 | `5e78e60319d10bc7` | 0 | 0 |
| **v6** | `c230cb4113c23e19` | 0 | 0 |
| v7 | `3a72100e9422955f` (English) | 0 | 0 |
| v8 | `cdf135fad54a55dc` (English) | 0 | **8** |

**The version order is the recon report's stage order, transcribed, not a
file-name sort.** Every one of the eight accepted texts is distinct, so each
file is one version; the order — initial draft, five revisions, then two
English translations — comes from the batch-6 recon report, because this
batch's file names do not sort by stage (the initial draft's name sorts *after*
both English translations), and a guessed sort would have made the initial
draft v8 and pointed the case's reach the wrong way.

**Zero tracked revisions, measured, not assumed.** This paper's advisor hand is
not in-document: unlike paper 1's 662 tracked revisions, every file's accepted
and rejected views are one clean text (measured equal per file). **The eight
margin comments are the advisor's hand here**, all on v8, all resolved by the
reader, one author, who is not named here. The reader reports zero extraction
problems over all eight files.

## 13. The task, as the protocol defines it

**The same case shape as paper 1, one question of arithmetic more.** Thirteen
cases, cut from v1's clean draft at 1200 characters — the draft is 16550
characters of the student's own text, so the natural chunking gives thirteen
sections without any split-for-the-floor. Thirteen clears
`significance.MIN_PAIRS` with the same room the protocol wants, at the cost of
one case over paper 1's twelve (§15).

**Why the comments do not drive the cases.** The protocol's case is a section
of a draft and a question about it, and that shape is unchanged. This paper's
own comments sit on v8, the final English translation, while a case asks about
v1 in Chinese: they are later material for the paper (the split checker holds
them on the evaluation side, and the negative control below proves the check
sees them), and they are the **answer face** the raters read after unblinding —
not an input any arm may hold. Arm D's comment face comes from the chain's
development papers, as the protocol's arm table says.

## 14. The by-paper leak check, measured

Three independent measures, all run over the real chain and the real files. The
raw output is outside the repository (`blind6-arms/leak-check.json`,
`blind6-arms/split-shape.json`).

### 14.1 Chain material sitting verbatim inside the paper

Units of at least twenty characters, whitespace-normalised, tested for exact
containment in the union of every file's accepted and rejected views:
**0 verbatim units — paper 1 had 9.** Eight **shorter** chain units (8–22
characters) do sit verbatim inside the paper, every one carried by
`proj-pilot-3` alone; none reaches the 40-character single-carrier line the
serving gate withholds at. The longest *shared run* anywhere is 44 characters
(paper 1: 112), with no exact containment — the near-misses are the same
instrument and method sentences a same-lab corpus shares, listed for judgement
in the raw output.

### 14.2 Distinctive numbers

**0** — as in paper 1, vacuously: the confirmed rules carry no digits, so there
is no number to find (§3.3 above records this check as vacuous by
construction).

### 14.3 The serving gate, and the rule face it leaves standing

| Measure | Paper 1 | Paper 2 |
|---|---:|---:|
| Confirmed rules in the store | 24 | 24 |
| Withheld by the serving gate | **6** | **0** |
| Served with a note (widest overlap) | — | 2 (22 chars) |
| Served by the product's `search_rules` (read-only store) | 9 | 9 |
| **The citable rule face** | **3** | **9** |

**The cross-domain prediction held, and it is measured, not assumed.** No
rule's source material sits verbatim in this paper above the withholding line,
so the gate withholds nothing and the rule face is exactly what the product's
own surface serves — three times what paper 1's same-domain material left. The
two noted rules carry 22-character overlaps that stay under the 40-character
line; the raw output names them.

### 14.4 The split, checked as data

`check_split` over the assembled entries — 63 version, 88 comment (80 chain,
8 this paper's own, filed on the evaluation side), 24 rule, 6 assessment — is
**clean**. Per case: each case's assembled reach passes `check_case`, and the
negative control (the same case with the cap ignored) is **refused for every
later version v2–v8**, so the checker demonstrably sees this paper's later
material and its own comments. Per arm: `check_arm_exposure` over each arm's
declared caps reports **0 leaks** (paper 1: 0), with the negative control
reporting the 7 beyond-cap versions per arm-case pair, as designed.

## 15. The five arms, assembled

The cases are written as the driver's own case set (`blind6-arms/cases.json`,
case ids `b6-01`…`b6-13`, paper id `unseen-paper-2`). The unseen paper supplies
`draft` only; the other six faces come from the chain's development material,
as §2 says. Per-case reach is measured, not assumed: all thirteen cases reach
rules (3–6 each) and chain comments (4–6 each); no case reaches nothing.

## 16. The blind sheet, and the second paper's own item space

**The run scope is the second paper's own.** Paper 1's items live in
`five_arm`; paper 2's live in `five_arm_unseen2`, and the two anonymous id
spaces cannot collide — measured, **0 shared item ids** across the two papers'
skeletons. The skeleton's 65 items (5 arms × 13 cases) are minted by
`item_id_for` with the same arms a run builds — the roles are part of the
digest, and the five arms run one guidance role each, so the ids are minted
*with* the roles, not against an empty tuple that no run would ever produce.

Both the skeleton and the packet were pushed back through the real
`load_blind_sheet` (**65 items accepted, 325 ratings read**), and the negative
control was re-run against the same loader: **an item carrying an `arm` key is
still refused** — `item item-f04ea6b5149a833b carries the key 'arm', which
names an arm; a blind sheet is anonymous until unblinding`.

## 17. The dry run, walked end to end on the real assembly

`python scripts/run_blind_evaluation.py --mode dry-run --cases
blind6-arms/cases.json --out blind6-arms/dryrun --run-scope
five_arm_unseen2`, exit code **0** read from the command itself, not from a
pipe.

| The run says | |
|---|---|
| status | `dry-run-complete` |
| model | empty |
| provider calls | **0** |
| stub calls | 65 |
| split clean | true |
| both contrasts, all five dimensions | wins 0, losses 0, **ties 13**, significant **false** |

Thirteen paired cases clear the floor of ten, so the sign test computes rather
than short-circuiting — and the verdicts are still ties, because every rating
is `unknown`. The dry run's unblinding map and the assembly's skeleton mint
**the same 65 item ids**, so the sheet a rater will hold is the sheet this
assembly built.

## 18. The real run's budget shape, measured from the assembly

Five arms × 13 cases = **65 calls**. The protocol's arrangement pair adds
2 × 13 = **26 calls**. One unseen paper, run properly, is **91 calls**.

Two shapes, both carried from the recalibration and the scaling run (§8–§9),
anchored to those runs' commits' tree:

- **The recalibration's per-case shape**: 27209 tokens for a five-arm case
  extrapolates to 13 × 27209 = **353717 tokens** for the five-arm calls. The
  arrangement pair's per-call cost from the scaling run (104616 tokens over 24
  calls) extrapolates to **113335 tokens** for its 26 calls: **about 467000
  tokens** for the whole paper.
- **The scaling run's mean shape**: 398555 tokens over 84 measured calls is
  4744.7 per call, which over 91 calls is **about 432000 tokens** — the
  cross-check below the extrapolation.

At the scaling run's measured 37.09s per call, 91 sequential calls are about
**56 minutes**. These are shapes for the owner's decision, not a budget that
has been approved. **USD is not computed here**; the owner's billing console is
the money source.

## 19. What this assembly changed in the tree

**The run scope now rides through the driver.** `run_dry` takes and honours a
`run_scope`, and the driver's `--run-scope` reaches both the dry run and the
real run (the arrangement pair keeps its own scope, as before). The gap was
real: without it, a second paper's run would mint its anonymous items in the
first paper's namespace, and the two papers' ids could collide on the same
case shape. Two witnesses carry it — one at the machinery level, one at the
driver level — and **both were mutation-checked: dropping the pass-through
reddened both; dropping only the driver's reddened only the driver's
witness.** No new test file was created, so no shard or manifest registration
was needed. The shard-cost witness stays as §11 left it: expected to refuse
the hand-edited list until an authorized run remeasures it.

**82 blind-evaluation witnesses pass** (80 from §11, plus these two), with
`ruff check`, `ruff format --check` and `mypy --strict` clean on the changed
files. This record carries **no Chinese material at all**, so
`CJK_RUN_CEILINGS` needs no new entry and the material-quotage witness stays
green by the same measurement that reddens it if this file ever quotes the
paper.
