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

**No USD figure is computed here and none belongs in this tree.** The repository
carries no unit price, and the money's source is the owner's billing console.
What the owner is approving is: **84 calls per unseen paper, roughly 130k tokens
per unseen paper, and a token ceiling at least that high** (`--budget-max-total-
tokens`), plus one approval record per call — the driver refuses a run whose
approvals are fewer than its requests, so 84 approvals, not one blanket.

Per annotator-hour rather than per token, the run also costs two independent
raters over 60 items × 5 dimensions, plus an arbiter for every disagreement.

## 8. What the real run still needs, in order

1. **The owner's budget decision** (§7), including the arrangement pair and the
   84 approvals.
2. **A literature source for arm B** — or B is declared as a control that
   repeats A, which the record must say before the run rather than after.
3. **The rule-face choice, §3.5**: run with 3 citable rules, relax the gate to
   the product's 9, or pick an unseen paper from a different laboratory.
4. **Two annotators who did not develop the system and did not annotate the
   current test set**, and an arbiter (§5 of the protocol) — the sheets are
   skeletons until real labels arrive.
5. **More unseen papers.** One paper gives twelve paired cases; the protocol's
   conclusion is about the system, not about one manuscript, and the split is
   checked per paper.

## 9. What was not changed in the tree

**No `src/` and no `tests/` change was needed.** The machinery took the real
material as it is: the seven-face case shape, the additive chain, the split
checker with its version caps, the blind loader and the paired sign test all ran
against real bytes and real store rows. Two things this assembly found are
**usage requirements the operator has to meet**, recorded above rather than
patched into the code: every paper in an arm's reach needs a declared cap (§3.4),
and the citable rule count is the product's serving answer, not the table's row
count (§3.5). A third finding is a **vacuous check** (§3.3) that the brief
expected to bite on numbers and that cannot, because the rules carry none.

Because no test file and no source file changed, the shard costs were not
re-measured and no new file was registered; `docs/` is not what the shard
witness watches. This record carries **no Chinese run at all**, so
`CJK_RUN_CEILINGS` needs no new entry and the material-quotage witness stays
green by the same measurement that reddens it if this file ever quotes the
paper.
