# ADR-0018: A role is a contract, not a model — and the three roles of the guidance loop

**Status:** Proposed
**Work order:** LC-P2-01, LC-P2-12 (proposed; not yet dispatched).
**Date:** 2026-10-30

## Context and concrete problem

Phase 2's product goal is a system that gives a researcher guidance on a
manuscript it has never seen, grounded in real revision histories, and
honest about what it does not know. The adjustment of 2026-10-30 (P2-AMD-01)
settled the route: **no self-trained model is a precondition**; the route is
**configurable cloud models, three roles with distinct responsibilities, the
advisor's real revision trajectories, and human feedback**.

Three facts in the tree shape what that means here.

**First: the outbound machinery already exists, and it is strict.** `MODEL_REQUEST`
is the **only** `CapabilityId` with `Effect.NETWORK`
(`security/capabilities.py:370-375`), it carries `ModelRequestArgs` and
`root_kinds={source, output}`, and the provider layer refuses a request
whose capabilities have not been **probed**
(`providers/adapter.py:452-461`: *"no capability probe has run for this
provider"* → unverified → blocked). There is a budget with a preflight
(`providers/budget.py:369`), a transcript, a usage capture, a redaction pass,
a credential store, a cancellation path, and an `ExchangeRecord` that
carries what went out and what came back.

**Second: the scientific discipline is already a machine, and it is
already strict.** `EvidenceCreator.MODEL_PROPOSAL` exists and is never
exercised; `VerificationStatus` is a **six-state** machine whose negative
states exist so that "a paraphrase is not a quote" and "neither side wins by
recency" can be *displayed*; and the record's own constructor refuses
`user_attested` for a non-`USER` creator, because *"an attestation is
something a person did; a rule or a model proposal reaching this state
would misreport who stands behind the claim."*

**Third: the chain that carries the evidence does not exist yet.**
LC-P2-09's design (`ADR-0017`) names the four objects — a comment, an edit,
a response, an assessment — and **LC-P2-08's contracts have no writer**, so
a version edge cannot be stored at all.

## The concrete problem this creates

A "multi-agent system" is the easiest thing in this domain to build and the
hardest to make honest. Three prompts in a loop produce three paragraphs,
and the paragraphs can be wrong in ways nothing notices. The hazards are
specific:

- **A role that is only a prompt is not enforced.** A system prompt saying
  *"you may not modify the manuscript"* is a request, and a model that
  misreads it, or an adapter that drops it, loses it silently. **The
  boundary has to be in code.**
- **A role that reaches the database or the network directly bypasses
  every gate the repository has.** The operation approval, the
  material-purpose grant, the budget, the probe, the transcript — all of
  them are properties of *one* path, and a path around them is a path
  around them.
- **"Another agent agrees" is not a fact.** Two models from two suppliers
  agreeing is a *corroboration*, and a corroboration is evidence about a
  model's behaviour, not about the manuscript.
- **A role that never says "I do not know" is a role that will guess.**
  The absence of an abstention is not a small gap: it is the mechanism by
  which an unsupported claim enters a report.

## Alternatives

### A. Three different models, one per role

**Rejected.** It buys a distinction the product does not need, at a cost
the evaluation cannot afford, and it confounds the comparison LC-P2-14 has
to make: with three different models, a difference between the `B-only` and
the `B+C` arms measures **the models**, not **the roles**. The adjustment
says so directly — the same base model may play several roles, and the
difference is responsibility, data, permissions, output contract and
hand-off.

### B. One model, three system prompts

**Rejected, and this is the shape most such systems take.** It makes the
role a **string**, and a string is not a boundary. It cannot express *"this
role may not write to the manuscript"* — only *"please do not"*. It cannot
express a budget, an abstain condition, a hand-off rule, or a schema the
output must satisfy, because none of those is prose. And it cannot be
**tested**: a prompt's compliance is not a fact about the tree.

### C. A role is a versioned contract, enforced by the code

**Chosen.** The contract says what the role is for, what it may read, what
it may do, what its output must look like, what it must refuse, and when it
must stop. **The prompt is one field of that contract** — `prompt_template_version`
— and it is the *least* load-bearing field in it.

## Decision

### D1 — A role is a versioned `AgentRoleSpec`, and the spec is data

A role is a row, and the row is versioned so that a change to what a role
may do is a change with a name and a date. Its fields:

| | |
|---|---|
| `role_id`, `role_version` | **which role, and which version of it** |
| `objective` | one sentence: what this role is for |
| `input_schema`, `output_schema` | **what goes in and what comes out**, as typed models |
| `allowed_capabilities` | the `CapabilityId`s it may exercise — `MODEL_REQUEST` and nothing else for the three roles |
| `forbidden_actions` | **named**: modify a manuscript, write an artefact without consent, execute code, approve an outbound transfer, raise a verified state |
| `allowed_data_purposes` | the `ConsentRefusal`-shaped purposes it may read under |
| `review_required` | whether another role must see the output before it counts |
| `provider_routing_policy` | which provider, which fallback, which ordering |
| `cost_budget`, `token_budget` | the ceilings for one invocation and for the run |
| `timeout_policy`, `retry_policy`, `fallback_policy` | what happens when it is slow, when it fails, and when the fallback is worse |
| `abstain_conditions` | **when this role must refuse to answer** |
| `escalation_conditions` | **when this role must hand over to a person** |
| `prompt_template_version` | which prompt text, and **nothing more** |
| `model_config_ref` | which model configuration — **a reference, not a model id** |

**And the model is configuration.** No model id, no endpoint, no price and
no capability claim is written into the tree. `model_config_ref` points at
a configuration the operator supplies, and the **capability probe** is what
says whether a provider may serve a role at all.

### D2 — The contract is enforced by the application, runtime and security layers, not by the prompt

**A role holds no database connection, no arbitrary file-write permission and
no direct network access.** Every outbound call goes through the one
provider boundary, and therefore through: the capability probe, the
**material-purpose grant check**, the **operation approval**, the budget's
preflight, the credential store, the redaction pass and the transcript.

**The order is the order, and it is already implemented.** LC-P2-06's
`transmit_request` runs the transmit gate **before** the approval is
consumed, so a request refused for want of a grant leaves the approval
**unspent** — asking is not spending. ADR-0015's two gates are therefore
not a new requirement for this phase; they are **the requirement, wired**.

**And the forbidden actions are refusals in the layer's vocabulary**, not
sentences in a prompt. A role that tried to write back to the manuscript
would meet a capability it does not hold, and the refusal would carry a
machine-readable reason.

### D3 — The three roles, their responsibilities and their outputs

**A. Revision-Trajectory Agent.** Reads the authorised project, its
versions, the OOXML revision and comment events, the version graph, the
original anchors and the student's revised passages. **Proposes** the
alignment between the advisor's comments and the edits actually made, and
marks the issue type and the state of each. Its output is a **typed
candidate**: the comment's own location, the advisor's original words, the
before and after fragments, the evidence references, the state
(`resolved | partial | unresolved | unknown`), the grounds and the
uncertainty. **It may not claim the advisor said something that is not in
the file**, and it may not order two versions by their file names.

**B. Scientific-Guidance Agent.** Reads the section being written, the
domain background, the authorised historical cases, the confirmed rules and
the checkable experimental or data sources. **Proposes** a diagnosis about
research questions, argument, experimental design, data support and the
limits of a conclusion, and **why the change is worth making**. Its output
is a `GuidanceCard`:

```
target_locator              where in the manuscript this is about
issue_type                  what kind of problem this is
severity                    how much it matters
reason                      why it matters
evidence_refs               the evidence it rests on
historical_case_refs        the prior cases it drew on
counterexamples_or_limits  the cases where this does not hold
suggested_next_action       what to do next
uncertainty                what it is not sure about
```

**And an abstention is a first-class output** — a structured `ABSTAIN`
naming what was missing, not an empty result. It may not invent an
experiment, a reference, a DOI or an advisor's opinion; **scientific facts
and stylistic advice are recorded separately**; and it may not write back to
the manuscript.

**C. Independent-Critique Agent.** Reads the original material and its
sources, **B's candidate cards**, and the counter-examples and evidence it
retrieves **for itself** — not only B's reasoning. It checks the logic,
whether the experiments support the conclusions, the contrary evidence, the
overreach and whether the advice is actionable, and it names what is
missing and what a person must handle. Its output is a `ReviewVerdict`:
per card `supported | needs_revision | unsupported | cannot_assess`, the
counter-evidence's anchors, the repair advice and **the reason for the
hand-off to a person**.

**And the roles are run on demand.** A single comment's extraction may be
A alone. A research suggestion triggers B. **C** runs when the risk is high,
the evidence is thin, the models disagree, or a person asks. **No
request runs all three by default, and there is no swarm.**

### D4 — A model proposes a judgement and never a fact

**This is where the adjustment and ADR-0017 meet, and it is the rule that
keeps the two documents from contradicting each other.**

| | What it is | Who may create it | Grade |
|---|---|---|---|
| `feedback_events` | **a fact about a file** — a comment that is there | **only the reader** | `observed` |
| `edit_actions` | **a fact about the manuscript's history** — a change that is there | **only the reader and the version graph** | `observed` |
| `response_links` | **a judgement** — "this change answered that comment" | a rule, a person, **or a model** | `observed` / `human_verified` / **`inferred`** |

**So role A's "candidates" are judgements, not facts.** A model's candidate
carries **no `comment_locator`**, because it read no comment of its own; it
*points at* one. **A model may not cause the system to claim the advisor
said something** — and the mechanism is structural rather than a promise:
the row that holds a locator is the row the reader wrote.

### D5 — The route is a configuration, and the probe is what says a provider may serve

**One primary provider per role, plus one measured fallback.** The choice
is made by configuration and by what the **capability probe** recorded —
tool calling, structured output, context limits, observable usage, error
behaviour, and when it was measured. **Nothing is ranked by a published
parameter count.**

**And a provider that cannot produce structured output is a provider that
cannot serve a role with a schema.** The probe records that, and the
provider is blocked from that role rather than being asked to try. When a
structured output fails, the path may **refuse or retry within a bounded
budget** — but **an illegal JSON is never silently turned into verified
evidence**, and a parse failure is a refusal with a reason.

### D6 — Two independent gates, and the material one comes first

**The operation approval** says *this operation may run once, now*. **The
material-purpose grant** says *this material may go to this place, for this
purpose*. They are different permissions and **the absence of the second
refuses the request whatever the first says.**

**The order is fixed and already implemented:** the material check runs
**first**, and only a permitted request spends the approval. `train_reuse`
and `external_transmit` are **not** interchangeable, and a request for one
is never a request for the other.

**And the refusal is offline and provable.** With no grant, the request is
refused **before any socket is opened**, the approval stays unspent, and the
record says **that no request was sent** — not merely that one was refused.
An outbound record carries the material and fragment ids, a minimal
fragment summary, the target provider and model, the consent credential, the
time, the purpose, the result, the cost and the audit event. **A plaintext
API key is never written anywhere.**

### D7 — The budget is a ceiling, and a failure is closed

**An unknown price, an unobservable consumption or a budget that is spent
all refuse.** The existing `RunBudget` and its preflight already say so,
and this ADR adds the rule the phase needs: **a retry across a restart
must not pay twice and must not repeat a side effect.** The event log
therefore distinguishes **prepared, requested, responded, unknown** and
**reconciled by a person** — and an **unknown** is unknown, not a success
and not a failure.

### D8 — Abstaining and escalating are results

**`abstain_conditions` and `escalation_conditions` are fields of the
contract, not behaviours hoped for.** A role that must abstain does so and
**records what was missing**; a role that must escalate hands over, and the
hand-off says why. **Neither is an empty result and neither is a crash**,
and the difference is the difference between "the system does not know" and
"the system is broken".

### D9 — Agreement between models is corroboration, and corroboration is not verification

**Role C's verdict is evidence about role B's output, and it enters the
ledger at the grade its own evidence supports.** Two suppliers agreeing
does not promote anything: `model_proposal` never becomes `user_attested`
or `verified_by_rule` by being agreed with, and the rule that enforces it
is already in the record's constructor (`evidence/record.py:363-371`).

**And a conclusion about scientific truth still needs the original material
or a person's review.** A verdict about a card is not a verdict about the
science.

## Upstream evidence (reference only)

- **P2-AMD-01** (the adjustment of 2026-10-30) — the route, the three
  roles, the two gates, the memory as retrieval, and the delivery order
- **ADR-0016** — the proposal-and-promotion rules, the six states, the
  abstention, and the prohibition on a model writing to the manuscript
- **ADR-0015** and **LC-P2-06** — the two gates and their order
- **ADR-0017** — the chain the roles read and write
- **`docs/plans/P2-AMD-01-impact-matrix.md`** — which work order each
  piece of this lands in

## Risks, tradeoffs and reversibility

**The risk that matters: a role that is only enforced by the model.** Every
field of the contract that is enforced by the prompt rather than by the
code is a field that can be lost. **D2 is the whole answer**, and it is
also the most expensive part of the work: it means the roles go through the
**same** consent, capability, budget and transcript machinery as everything
else, with no private path.

**The second risk: a corroboration that reads as a verification.** Two
suppliers agreeing is a strong signal about the model and a weak one about
the manuscript. **D9 keeps the two apart in the ledger's own vocabulary**,
so the report cannot blur them.

**The third: cost.** Three roles on a configurable provider is a bill. The
budget is a ceiling rather than an average, the roles run **on demand**,
and LC-P2-14 records cost and latency **per arm** — so a configuration
that costs more than it gains is visible rather than assumed.

**Reversibility.** The `AgentRoleSpec` is data. Removing a role removes a
row and a capability; the chain, the ledger, the provider boundary and the
budget are unaffected. **The one thing that is not reversible is a decision
that has been made and recorded** — which is why the hand-off and the
abstention are rows and not logs.

## Contracts and acceptance tests

| # | Contract | Witness |
|---|---|---|
| C1 | A role's contract is versioned, and the version is on every output it produces | to be written at LC-P2-12 |
| C2 | A role may exercise only the capabilities its contract lists, and a call outside them is refused by the layer | to be written at LC-P2-12 |
| C3 | A role holds no database connection, no arbitrary file-write permission and no direct network path | to be written at LC-P2-12 |
| C4 | The material-purpose check runs **before** the approval is consumed, and a refused request leaves the approval unspent | to be written at LC-P2-01 |
| C5 | With no grant, **no socket is opened**, and the record says that no request was sent | to be written at LC-P2-01 |
| C6 | A provider that has not been probed is blocked from a role that needs a schema, and a parse failure is a refusal with a reason | to be written at LC-P2-01 |
| C7 | An unknown price, an unobservable consumption or an exhausted budget refuses, and a retry across a restart does not pay twice | to be written at LC-P2-01 |
| C8 | A model's candidate carries no `comment_locator`, and a row that claims the advisor's words without having read them is refused | to be written at LC-P2-09 |
| C9 | An abstention is a structured record naming what was missing, and it is not an empty result and not a crash | to be written at LC-P2-12 |
| C10 | A `GuidanceCard` carries an anchor, the evidence, the counter-examples and the uncertainty, and a card with an empty `evidence_refs` is refused | to be written at LC-P2-12 |
| C11 | Two providers agreeing does not promote a proposal, and the record's constructor still refuses it | to be written at LC-P2-12 |
| C12 | A hand-over to a person records the reason, and an unanswered question stays unanswered | to be written at LC-P2-12 |
| C13 | A role runs alone when the contract says it may, and the roles that do run are the ones the request needed | to be written at LC-P2-12 |
| C14 | No model id, endpoint, price or capability claim is written into the tree | to be written at LC-P2-12 |

**Every one of these needs a witness, and the witness must fail for the
property.** A test that fails because of an unrelated encoding or lint
matter is not a witness of the property; when a test goes red, ask what
made it red before believing that it caught something.

## Re-evaluation trigger

This ADR is re-opened if **any** of these becomes true:

1. A provider's structured output is refused inside the adapter before the
   request is sent, as the 2026-10-28 probe found for two forms. **Then
   the schema has to be enforced on the way out as well as on the way in**,
   and the route has to say what "structured output" means.
2. The multi-user question opens (ADR-0015 D6). **Then a role's
   `allowed_data_purposes` is not enough** — the role needs an identity,
   and the audit trail needs a subject.
3. The cost of the `B+C` arm is measured to exceed the `B-only` arm's gain
   in LC-P2-14. **Then the arrangement is a product decision and not a
   default**, and this ADR's "on demand" rule becomes "B only".
4. A supplier's model changes under the same configuration name. **Then the
   probe record's timestamp is the only thing that says what was measured**,
   and a role's behaviour may have changed without any code changing.
5. The pilot asks for a role this ADR does not name. **Then the contract is
   what is extended, not the model.**
