# ADR-0016: A model's proposal is a proposal — and a human's confirmation is the only promotion

**Status:** Proposed
**Work order:** LC-P2-01, LC-P2-12 (proposed; not yet dispatched)
**Date:** 2026-10-29

## Context and concrete problem

Phase 2's product goal is a system that gives a researcher guidance on a
manuscript it has never seen, grounded in real revision histories, and
honest about what it does not know.

That goal contains a hazard the design names in one line: **"成果不是一个
'像老师说话'的聊天机器人，而是一条可重放、可验证、可反驳的科研指导链"**
— the deliverable is a replayable, verifiable, *refutable* chain of guidance,
not a chatbot that sounds like the advisor.

Three facts from the tree shape what is possible.

**First: the vocabulary already exists and has never been used.**
`EvidenceCreator` (`evidence/states.py:96-112`) carries **three** creators:
`rule`, `user` and `model_proposal`. The enum's own docstring states the
rule this ADR turns on:

> *"Who or what produced the record's **current** state. ADR-0002's rule,
> restated by ADR-0004 Contract 1: a record claiming a final state must also
> name who or what established it. `EvidenceRecord` pairs this with
> `created_by_id` and **refuses `user_attested` unless the creator is
> `USER`**."*

And the third member's comment is the phase's thesis in one line:

> *"A model proposed it. **Proposing is not verifying** — a proposal reaches
> `planned` and no further without a log entry from C1-C3 or a user."*

The application's own comment says the same thing from the other side:

> *"`model_proposal` exists so a future proposal path is expressible; it is
> not [yet exercised]."* (`application/evidence.py:44`)

A grep for `MODEL_PROPOSAL` across `src/` returns exactly two hits: the
declaration and that comment. **Phase 1 carved the slot out and left it
empty.**

**Second: the outbound consent vocabulary exists and has never been emitted.**
`EventType.OUTBOUND_CONSENT_REQUESTED` (`runtime/event.py:76`) is declared
and grouped with the annotation events. The grep returns two hits, both in
`runtime/event.py`. Phase 1's own carried limitation says the same thing
from the other side: *"ADR-0006's outbound-consent bridge is not built — both
modules exist, nothing joins them"*.

**Third: the provider cannot be assumed to return structured output.** The
probe's measured answer (2026-10-28, against `MiniMax-M3.1-Flash` on the
`anthropic` protocol) is that `tool_calls` and `usage_reporting` **work**, and
that **both structured-output forms are declined inside `pydantic-ai` before a
request is sent**. A design that assumes "the model returns JSON" starts from
a refusal.

## The concrete problem this creates

The phase's exit gate is *"measured capability gain against a frozen P1
baseline, no scientific-claim inflation"*. The second half is the harder
one, and it is a **structural** requirement, not a style guide: a claim that
reaches a report must be traceable to something that was checked.

ADR-0004 already holds the rule in prose: *"a model's say-so is not
evidence"*. Phase 2 must hold it in code, and the code has three distinct
promotion paths to close:

| Path | The trap |
|---|---|
| **model → verified** | the model asserts a fact; nothing checks it; the report cites it |
| **model → advisor's rule** | the model distils a rule from cases; the rule is treated as confirmed |
| **model → accepted change** | the model rewrites the manuscript; the change is recorded as the advisor's |

The third is the one that is easiest to get wrong by accident, because the
project already has a *human* path for the same thing. Phase 1 records
claims and attestations through `EvidenceCreator.USER` — a person's
attestation, logged by that person's id. A model proposal that ends up
logged as a user attestation is a forged signature, and it would be
invisible: the schema would be satisfied, the report would cite a locator,
and nothing would say the sentence was invented.

## Alternatives

### A. Let the model write the report text, and let the checks catch what is wrong

**Rejected.** It inverts the design's order. The Phase 1 report path
assembles *what a task has*: *"a record that may be stated becomes a claim
and one that may not becomes a disclosure"* (`application/reports.py`). A
model-authored report has no such partition — the model decides what is
claim and what is prose.

### B. Validate the model's output against a schema, and treat schema-validity as correctness

**Rejected.** The design says it in one sentence: *"schema 合法不代表科学判断
正确"* — and the provider makes it moot anyway, since both structured-output
forms are declined before the request is sent. A design whose correctness
argument is "the JSON parsed" is not a correctness argument.

### C. Let the model produce a proposal, and have the model's own confidence decide whether it ships

**Rejected.** A model-confident claim and a model-unconfident claim are the
same kind of object: neither has been checked. Confidence is not evidence,
and using it as a gate would make the system's behaviour a function of the
provider's calibration on the day.

### D. A proposal is a distinct, first-class object that only a rule or a human can promote

**Chosen**, and it is the shape `model_proposal` was cut for.

## Decision

### D1 — A proposal is an evidence record whose creator is `model_proposal`, and it starts unpromoted

The proposal is stored like any other record, with `creator =
model_proposal`, and it **cannot be cited** while its verification status is
anything other than `verified_by_rule` or `user_attested`.

**The status machine already exists, and it is a six-state machine.**
`VerificationStatus` (`evidence/states.py:50-76`) is:

| State | Meaning |
|---|---|
| `PLANNED` | declared, not yet located — the only state that may carry no anchor |
| `EXTRACTED` | located and copied out; the span and its hash are on the record |
| `VERIFIED_BY_RULE` | a rule confirmed a **number or a structure** — never a scientific hypothesis |
| `USER_ATTESTED` | a named human said so, and the record says who |
| `CONFLICTED` | two readings disagree beyond tolerance — a state to surface, not a terminal failure |
| `UNSUPPORTED` | cannot be located, or does not support the record |

The enum's own docstring says why the three negative states exist: *"A design
with only `planned` and `verified` cannot express either"* — ADR-0004 A3 (a
paraphrase presented as a quote does not reach `verified_by_rule`) and A5
(neither wins by recency; the conflict is displayed).

**So the phase's central scientific discipline is already a state machine
with six states, and `model_proposal` is already one of the creators of a
record in it.** A proposal therefore has exactly two legitimate routes out of
`extracted`:

- **a rule** verifies it, or
- **a human** attests it — and a human attestation is logged by *that
  person's* id, never by the model's.

> **Corrected on 2026-10-31, and the correction is D1's second bullet
> that was never reachable.** The two routes above are the ones the *state
> machine* offers. The second of them cannot be taken on the proposal's own
> record: `user_attested` requires `created_by='user'`, and D2's own rule
> forbids rewriting a model's creator to make it fit — which is correct, and
> which leaves the person's route as **the person's own record, which
> supersedes the proposal**. The store says so in its own words
> (`evidence/store.py`, `supersede_record`): *"the only route to
> `user_attested` needs `created_by == 'user'` … a rule-written record …
> has nowhere to go — it cannot be verified, because no check passed, and it
> cannot be attested, because it is not a person's record. Superseding is the
> exit the schema provides: a person writes their own record, and the
> rule's is kept and marked."* D2's diagram is corrected below, and the
> confirmation door implements what it says.

**A model proposal cannot promote itself.** The `model_proposal` member's
comment says it: *"a proposal reaches `planned` and no further without a log
entry from C1-C3 or a user."*

**And `VERIFIED_BY_RULE` means what it says.** Its own comment: *"A rule
confirmed a **number or a structure**. It never confirms a scientific
hypothesis — `verified_by_rule` can mean numeric/structural verification; it
must not imply a scientific hypothesis is established."* Phase 2's guidance
cards are scientific hypotheses about a manuscript, so **a rule may verify
their structural facts (does this anchor resolve? is this quote verbatim?)
and never their scientific claims.**

### D2 — A model's output can never be recorded as a person's, and the check is already in the constructor

The creator of a record records *who made the assertion*. A model that made
it did not become a user by being promoted.

**This is not a rule Phase 2 has to establish — it is a rule the record
model already enforces.** `EvidenceRecord`'s validator
(`evidence/record.py:363-371`) refuses the record at construction:

```python
if self.status is VerificationStatus.USER_ATTESTED:
    if self.created_by is not EvidenceCreator.USER:
        raise ValueError(
            f"user_attested requires created_by="
            f"{EvidenceCreator.USER.value!r}, not {self.created_by.value!r}. An "
            f"attestation is something a person did; a rule or a model "
            f"proposal reaching this state would misreport who stands behind "
            f"the claim."
        )
```

**A model proposal therefore cannot become `user_attested`.** The refusal
is at construction, in every path, including a hand-written JSON file —
which is the same standard the record model's docstring sets for the
status-without-a-log-entry rule: *"not left to a database check constraint
that some future writer might forget — it raises at construction, in every
path."*

**What Phase 2's own path must preserve.** The check is on the *record*.
Phase 2's model request path must not be able to **write the creator field
itself** in a way that bypasses it — and the real risk is not the
constructor, it is a path that writes `created_by=USER` for something the
model said. That is the mutation this ADR's contract C2 exists to catch, and
it is a Phase 2 witness, not a Phase 1 one.

**The promotion paths, stated exactly:**

```
model_proposal ──(a rule verifies a STRUCTURAL fact)──> verified_by_rule
model_proposal ──(the anchor does not resolve)──────> unsupported
model_proposal ──(conflicting readings)─────────────> conflicted
```

**And the human's route, which is not a status on the proposal** (corrected
on 2026-10-31, because the arrow that was here was unreachable — see D1's
correction above):

```
a person's own record ──(at the same address)──> user_attested, attributed to that person
        └── supersedes ──> the proposal, which is kept and marked
```

`model_proposal` never becomes `user`, and never becomes `user_attested`.
**And a model proposal never becomes citable**, because the states a report
may cite are `verified_by_rule` and `user_attested` and it is neither. What
a report cites after a person has settled a proposal is **the person's own
record** — which is the point: the thing in front of a reader is a person's
word, and the model's answer is beside it in the ledger, kept, marked, and
attributable to the model that said it.

### D3 — Structured output is not assumed; the schema is enforced on the way in and the way out

The provider declines both structured-output forms, so:

- the **request** carries the required shape as an instruction and a
  validation schema, and the **response** is parsed and validated against a
  **repository-side** schema, not a client-side one;
- a response that does not parse is a **refusal with a reason**, not a
  partially-filled record;
- the design's §5 data contract is therefore **a schema in this repository**
  (`GuidanceCard`, `EditIntent`, `ResponseAlignment`, `Advice`), with the
  validation code here and the prompt there — not the other way round.

**A model-supplied value is never trusted into a field that another
calculation reads.** Every field the prompt asks for is validated against a
declared type, and a field the model cannot fill is `UNKNOWN`.

### D4 — The guidance card is a proposal, and its uncertainty is a field, not a caveat

`GuidanceCard` carries: the issue category, the anchor into the current
manuscript, *why* it may be a problem, the recommended next step, the
evidence and the counterexamples, the confidence **type**, what needs the
student's confirmation, and the effect on the manuscript's claims.

**"Confidence type" is not a score.** The design's requirement is that a
suggestion says what kind of uncertainty it has — *this is anchored in the
text*, *this is a pattern from three cases*, *this is a general expectation
with no case here* — because a number would invite the reader to compare
magnitudes that are not comparable, and would be a claim the system cannot
support.

**The card never cites the advisor's opinion as a rule.** A card may say
*"three archived cases show advisor X asked for a control group in this
situation"* — that is a citable observation about the archive. It may not
say *"advisor X would want this"*, which is an assertion about a person's
mind that no archive can support.

### D5 — The agent may abstain, and abstention is a first-class success

The acceptance clause is *"无足够材料可正确拒答"* — with insufficient
material, the correct answer is to refuse.

**Abstention is recorded as an outcome, not as an absence.** A run that
produces no card produces an **abstention record** naming what was missing.
This matters for LC-P2-14's metric `abstention_quality`: an abstention rate
that can only be measured by counting the cards that were *not* produced is
not measurable, because it cannot distinguish a correct refusal from a
failure to run.

### D6 — The model cannot write to the manuscript, and cannot cause an effect

The model may not modify the original file, may not create an artifact
without the existing `artifact.write` consent, and may not execute code.
Phase 1's boundaries already say this — the chart recipe is *"a JSON
document of exactly three parts ... with no script beside it and no way to
run one"*, and the phase boundary holds that *"Phase 2/3 features do not
excuse failure of Phase 1 boundaries"*.

**No model-generated code execution, in Phase 2 or after.** The design's
§0.3 lists it as a non-goal, and Phase 1's analysis layer is the model to
follow.

### D7 — The model sees only what the consent allows, and the request is recorded

Every model request is a **`model.request` operation**: an operation approval
(per §D3 of ADR-0015, the *second* of the two gates), an egress grant check,
a budget, and a transcript.

The transcript is stored, and the stored transcript is what the report's hash
chain covers — so a reader can tell exactly what was sent and what came
back. The design's LC-P2-01 acceptance says it: *"recorded (transcript and
usage land in the store and in the report's hash chain)"*.

**The request carries an excerpt set, not the document.** `ModelRequestArgs`
has `root_kinds=frozenset({"source", "output"})` and the capability's summary
is *"send an excerpt set to a remote model provider (transmits data)"*.

### D8 — A rule distilled from cases is a `candidate` until a human confirms it

LC-P2-11's rule lifecycle is `candidate → human_approved → contested /
retired`, and it is the design's own: *"经导师或授权人员审批才能上升为'导师
已确认原则'"*.

**A rule carries its source events, its scope and its counterexamples**, and
a rule whose source material is withdrawn is invalidated with it (ADR-0015
D4). **Two rules that conflict are shown side by side, and neither is
picked by being newer** — the design says so directly, and the evidence
ledger already refuses to express a winner: *"A conflict is handed over as
data with two interchangeable sides, so the structure itself cannot express a
winner."*

### D9 — A model suggestion does not become an advisor's rule by being retrieved often

Retrieval frequency is not confirmation. A rule that appears in many
retrievals is not thereby established; a rule with one well-evidenced case
and a stated scope may be better. **The evidence ledger's confidence
vocabulary is the only thing that ranks anything**, and the design's
LC-P2-14 metric set includes "过度模仿" (over-imitation) as a thing to
measure — the system's agreement with the advisor's wording is a **risk
metric**, not a quality metric.

## Upstream evidence (reference only)

| Project | SHA | What was observed | Licence |
|---|---|---|---|
| XtraGPT | `9f4be5c69878b16b5836a3769745bd190b585572` | instruction-conditioned revision with component-wise evaluation; weights asserted under MG0-2.0 with **no LICENSE file shipped**; trained on third-party paper revision pairs | **not established** |
| arXivEdits | `113913d68522c1c8428d8e191d5c9bed633da6ce` | BERT+CRF aligner requiring CUDA; T5 edit-intention classifiers; **no licence file**; corpus carries a mixture of eight per-paper licences | **none declared** |

The design-relevant reading is the one in
`docs/research/upstream-study/XtraGPT.md`: a model that already encodes
unlabelled revisions **cannot claim that its advice comes from the
advisor-experience library**, and cannot report which parts of its behaviour
are learned and which are inherited. That is a scientific-integrity reason to
keep Phase 2's guidance grounded in a **citable, attributable rule store**,
independent of the licensing question.

Full records: `docs/research/upstream-study/`.

## Risks, tradeoffs and reversibility

**Risk — the creator field is forgeable.** Nothing in the schema prevents a
future code path from writing `creator=user` for something a model said.
Mitigation: the creator is written in exactly one place, and a witness
asserts that promotion does not change it. This is the "**the witness must
fail for the property**" rule applied to the phase's most dangerous single
field.

**Risk — validation is confused with verification.** A schema-valid card can
still be scientifically wrong, and the pipeline will happily carry it.
Mitigation: D1's two promotion paths, and the design's insistence that the
final evaluation be human scientific judgement plus verifiable data — *"模型
分数不能替代人工科研正确性"*.

**Risk — the prompt becomes the contract.** When a provider declines
structured output, the temptation is to define the contract in the prompt
and treat the response as the record. Mitigation: D3 — the schema lives in
the repository, and the response is validated against it on arrival.

**Risk — a transcript is a copy of the material.** The stored transcript may
contain manuscript text, which is exactly what ADR-0015's grants govern.
Mitigation: the transcript is stored under the same access grants as the
material it contains, and it is not a place where material escapes the
consent model. **This is easy to get wrong** — a transcript is a *derived
copy* and the grant model has to cover it.

**Tradeoff — abstention costs usefulness.** A conservative system that
refuses often will score well on `abstention_quality` and badly on
"grounded_actionability". The two trade off, and LC-P2-14's ablation exists
to measure the trade rather than to pick a side in advance.

**Reversibility.** Nothing here changes a Phase 1 table's shape. The
`model_proposal` creator and the `OUTBOUND_CONSENT_REQUESTED` event type
already exist; Phase 2 makes them reachable. Removing Phase 2's code leaves
Phase 1 exactly as it is.

## Contracts and acceptance tests

| # | Contract | Witness |
|---|---|---|
| C1 | A record created by a model has `creator = model_proposal` and is **not citable** | to be written at LC-P2-01 |
| C2 | A model proposal **cannot** reach `user_attested` — the record model's constructor refuses it, and Phase 2's path cannot bypass the refusal by writing the creator field itself | constructor check: **already implemented** (`evidence/record.py:363`); Phase 2 path: to be written at LC-P2-01 |
| C3 | A model proposal with no rule and no human attestation is refused by the evidence gate, and the refusal names the missing promotion | to be written at LC-P2-01 |
| C4 | A model's response that does not parse against the repository-side schema is refused with a reason, and no partial record is written | to be written at LC-P2-01 |
| C5 | A field the model cannot fill is `UNKNOWN`, and no other field is affected | to be written at LC-P2-01 |
| C6 | A model request without an operation approval is refused and does not spend anything | to be written at LC-P2-01 |
| C7 | A model request whose material lacks an `external_transmit` grant is refused (ADR-0015 C2) | to be written at LC-P2-01 |
| C8 | The transcript and the usage land in the store and in the report's hash chain | to be written at LC-P2-01 |
| C9 | A run with insufficient material produces an abstention record naming what was missing, not an empty result | to be written at LC-P2-12 |
| C10 | A guidance card cannot be produced that cites a rule whose source material has been withdrawn | to be written at LC-P2-11/12 |
| C11 | Two conflicting rules are both returned, and neither is selected by recency | to be written at LC-P2-11 |
| C12 | The model cannot modify a manuscript file, create an artifact without consent, or execute code | to be written at LC-P2-12 |
| C13 | A rule may verify a guidance card's **structural** facts and may not verify its **scientific** claim — `verified_by_rule` does not imply a hypothesis is established | to be written at LC-P2-01/12 |

**C2 is the mutation that must not survive.** Removing the constructor's
creator check leaves every other test green — the record still refuses a
status without a log entry, and the report still cites only resolvable
anchors. That is precisely why the check needs its own witness, and why
LC-P2-01's review must mutate it.

**C13 is what keeps "no scientific-claim inflation" honest.** A rule that
checks *"does this quotation appear verbatim at this locator"* is C2's job
and is genuinely mechanical. A rule that checks *"is this scientific claim
correct"* is not a check at all, and the six-state machine says so in the
`verified_by_rule` member's own comment. Phase 2's guidance cards sit on
that line, and C13 is what stops them from crossing it.

## Re-evaluation trigger

1. The provider probe's answer changes — structured output becomes
   available, or a different provider is configured. D3's
   repository-side schema stays, but the request path may change, and C4's
   witness must be re-checked against the new path.
2. A model is fine-tuned on the permitted corpus (LC-P2-14's optional
   LC-P2-15). Then D9's "cannot claim the advice comes from the rule store"
   constraint changes shape, and the ablation protocol must be re-specified
   to separate learned behaviour from retrieved behaviour.
3. The evidence ledger's status machine changes. D1 and D2 are written
   against the current machine, and a new promotion path is a re-opening
   trigger for this ADR.
4. A human attestation becomes available through a surface that a model can
   trigger. That is the exact forgery path C2 guards, and it would make
   this ADR's D2 load-bearing in a new place.
