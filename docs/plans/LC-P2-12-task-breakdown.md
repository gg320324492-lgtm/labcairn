# LC-P2-12 — The three-role guidance loop — task breakdown

**Work order:** LC-P2-12 (the guided-revision agent) · **ADR:**
[`ADR-0018`](../adr/ADR-0018-agent-roles-and-routing.md) ·
[`ADR-0016`](../adr/ADR-0016-model-proposal-and-human-confirmation.md) ·
**Status:** drafted 2026-10-30, **not yet dispatched**. **Priority:** the
adjustment of 2026-10-30 (P2-AMD-01) makes this the phase's **fourth
step** — the three roles are the phase's route, and this work order
implements them.

## 0. How to read this document

**This is a contract, not a suggestion.** §4 names the acceptance clauses
and, for each, the test that carries it.

**And this work order spends money.** Every invocation is a paid call, and
§2.6 says what happens when the budget cannot be measured. **The owner's
authorisation of the suppliers and the budget is a precondition of any real
run** — the demonstration in §3.6 uses `FakeProvider` and sends nothing.

## 1. Goals and boundaries

### 1.1 What LC-P2-12 must produce

**The loop, as three roles with hard contracts and one path to the model:**

| Role | It produces |
|---|---|
| **A. Revision-Trajectory** | typed **candidates** that align the advisor's comments with the edits actually made, and mark the issue type and the state of each |
| **B. Scientific-Guidance** | a **`GuidanceCard`** — a diagnosis, an anchor, an explanation, a next step, the evidence and the counter-examples, the uncertainty, and what needs the student's confirmation |
| **C. Independent-Critique** | a **`ReviewVerdict`** — per card `supported \| needs_revision \| unsupported \| cannot_assess`, the counter-evidence's anchors, the repair advice, and the reason for the hand-off to a person |

**And the roles run on demand.** A single comment's extraction may be A
alone; a research suggestion triggers B; **C runs when the risk is high,
the evidence is thin, the models disagree, or a person asks.** No request
runs all three by default, and **there is no swarm**.

### 1.2 Already done — removed from scope

- **`CapabilityId.MODEL_REQUEST`** — the only network capability, already
  registered with its argument model and its root kinds.
- **The provider boundary, the budget, the probe, the credential store,
  the redaction pass and the transcript** — LC-P2-01's path. **This work
  order calls it; it does not change it.**
- **The two gates** — LC-P2-06's `transmit_request` and LC-P2-02's
  durable approval. **The roles go through them like everything else.**
- **ADR-0016's promotion rules** — a model's answer is a `model_proposal`,
  and the record's constructor refuses a promotion it did not earn.
- **The chain the roles read** — LC-P2-09's four tables and their events.

### 1.3 Explicitly not in scope

- **The model call itself.** LC-P2-01.
- **The trajectory's own tables.** LC-P2-09. This work order **reads**
  them and **writes judgements about them** — and ADR-0018's D4 says which
  object a model may create: a **judgement**, never a fact.
- **The rules the cards cite.** LC-P2-11.
- **The evaluation.** LC-P2-14, which measures whether the arrangement
  helped and **may report that it did not**.
- **A specialised model, a fine-tune, or a trained style.** P2-AMD-01
  removed these from the phase; LC-P2-15 holds the optional research.

## 2. The decisions that shape it

### 2.1 A role is a versioned contract, and the code enforces it

ADR-0018's D1 and D2 are the whole of it. **`AgentRoleSpec`** carries the
objective, the input and output schemas, the allowed capabilities, the
**forbidden actions**, the data purposes, the budgets, the routing, the
abstain conditions and the escalation conditions. **The prompt is one
field of it, and the least load-bearing one.**

**So a role holds no database connection, no arbitrary file-write
permission and no direct network path.** Every outbound call goes through
the one provider boundary, and therefore through the capability probe, the
**material-purpose grant**, the **operation approval**, the budget's
preflight, the credential store, the redaction pass and the transcript.

### 2.2 A role proposes a judgement and never a fact

ADR-0018's D4, and ADR-0017's D1: **a comment is a fact about a file and
only the reader may create one.** So what a model produces is a
**judgement**, and the judgement carries the grade its own evidence
supports — `observed`, `human_verified`, or **`inferred`** for a model's
candidate.

**And the mechanism is structural, not a promise.** A row carrying a
`comment_locator` is the row the reader wrote, and **a model's candidate
carries none** — it points at a comment rather than claiming to be one.

### 2.3 An abstention is a result

**A role that cannot answer says so, and says what was missing.** ADR-0016's
D5 makes the abstention first-class, and LC-P2-12's card carries it as
`uncertainty`. **An abstention is a structured record, not an empty result
and not a crash** — and the difference between "the system does not know"
and "the system is broken" is the difference between a product and an
outage.

### 2.4 A card cites a rule with its counter-examples

**A rule without its counter-examples is a slogan.** LC-P2-11's rules carry
a scope, an example, a counter-example, a version and a withdrawal state;
**a card that cites a rule cites the rule's counter-examples too**, because
a reader deciding whether to follow the advice needs to know where it does
not hold.

### 2.5 Two models agreeing is not a fact

ADR-0018's D9: role C's verdict is **evidence about role B's output**, and
it enters the ledger at the grade its own evidence supports. **A
corroboration is not a verification**, and the record's constructor already
refuses a promotion that was not earned.

### 2.6 An unmeasurable cost refuses, and a retry does not pay twice

**A budget whose price is unknown fails closed** — the layer's existing
semantics. **A request that was sent and did not answer is `unknown`, not
a success and not a failure**, and a retry across a restart **does not pay
twice**. ADR-0018's D7, and LC-P2-01's path.

### 2.7 A person decides, and the decision is audited

**A human may accept or reject a card, and the decision is recorded.**
**And role C may not approve an outbound transfer, release unauthorised
material, or execute code** — those are forbidden actions, enforced by the
capability the role does not hold.

## 3. The work

### T00 — The role contract, as data

**Files:** `src/labcairn/db/models.py` (`AgentRoleSpecRow`), a migration,
`src/labcairn/roles/spec.py` (new), `tests/test_agent_role_specs.py` (new).

**The spec is a row, and it is versioned.** The fields are ADR-0018's D1
list. **And the spec is enforced, not read:** a role's operation asks the
spec for its allowed capabilities and its forbidden actions, and **the
operation refuses a call the spec does not allow** — the refusal carries a
machine-readable reason.

**And a role's output schema is a typed model**, not a description of one.

### T01 — Role A: the trajectory candidates

**Files:** `src/labcairn/roles/trajectory.py` (new),
`tests/test_role_trajectory.py` (new).

**Reads** the authorised project, its versions, the OOXML events, the
version graph, the anchors and the revised passages. **Proposes** the
alignment between the advisor's comments and the edits, and marks the
issue type and the state of each — `resolved | partial | unresolved |
unknown`.

**And it may not claim the advisor said something that is not in the
file**, and it may not order two versions by their file names. **Both are
refusals, not warnings.**

### T02 — Role B: the guidance card

**Files:** `src/labcairn/roles/guidance.py` (new),
`tests/test_role_guidance.py` (new).

**The card**, with ADR-0018's D3 fields: `target_locator`, `issue_type`,
`severity`, `reason`, `evidence_refs`, `historical_case_refs`,
`counterexamples_or_limits`, `suggested_next_action`, `uncertainty`.

**And the prohibitions are refusals:** no invented experiment, no invented
reference, no invented advisor's opinion, **scientific facts and stylistic
advice recorded separately**, and **no write-back to the manuscript**. A
card whose `evidence_refs` is empty is refused.

### T03 — Role C: the independent critique

**Files:** `src/labcairn/roles/critique.py` (new),
`tests/test_role_critique.py` (new).

**Reads** the original material and its sources, B's cards, and **the
counter-examples and evidence it retrieves for itself** — not only B's
reasoning. **Checks** the logic, whether the experiments support the
conclusions, the contrary evidence, the overreach, and whether the advice
is actionable, and **names what is missing and what a person must
handle**.

**And the verdict enters the ledger at the grade its evidence supports** —
a review of a card is not a review of the science.

### T04 — The arrangement, on demand

**Files:** `src/labcairn/roles/orchestration.py` (new),
`tests/test_role_orchestration.py` (new).

**The rule for which roles run is data**, not a branch in the code: the
request's risk, the evidence's thinness, the models' disagreement and the
user's asking **decide**, and **the decision is recorded**.

**And the roles that run are the ones the request needed** — a witness
that a simple comment extraction did not run B and C, and that a
high-risk request did.

### T05 — The demonstration, and the acceptance record

**Files:** `examples/guidance_loop_demo.py` (new),
`tests/test_guidance_loop_demo.py` (new),
`docs/acceptance/LC-P2-12-acceptance.md` (new), `.github/ci-shards.json`.

**The demonstration uses `FakeProvider` and sends nothing.** It shows
**one grounded suggestion, one suggestion the critique rejects, and one
abstention for want of evidence** — and, throughout, **no write-back, no
unauthorised outbound and no paid call**.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | A role's contract is versioned, and the version is on every output it produces | `test_a_role_spec_is_versioned_and_the_version_is_on_the_output` |
| A2 | A role may exercise only the capabilities its contract lists, and a call outside them is refused with a machine-readable reason | `test_a_call_outside_the_role_spec_is_refused` |
| A3 | A role holds no database connection, no arbitrary file-write permission and no direct network path | `test_a_role_holds_no_direct_path_out` |
| A4 | Role A's candidate is a **judgement**: it carries no `comment_locator`, and it may not claim the advisor's words | `test_role_a_proposes_judgements_and_never_facts` |
| A5 | Role A may not order two versions by their file names, and may not treat a missing round as a present one | `test_role_a_does_not_order_versions_by_name_or_invent_a_round` |
| A6 | A card carries every field, and a card with an empty `evidence_refs` is refused | `test_a_card_carries_its_fields_and_one_without_evidence_is_refused` |
| A7 | A card cites a rule **with its counter-examples** | `test_a_card_cites_a_rule_with_its_counterexamples` |
| A8 | Insufficient material produces a structured abstention naming what was missing, and not an empty result | `test_insufficient_material_produces_a_named_abstention` |
| A9 | A card invents no experiment, no reference and no advisor's opinion | `test_a_card_invents_no_experiment_reference_or_opinion` |
| A10 | Scientific facts and stylistic advice are recorded separately | `test_facts_and_style_are_recorded_separately` |
| A11 | Role C reads the original material and its sources, and retrieves its **own** counter-evidence | `test_role_c_reads_the_sources_and_its_own_counterevidence` |
| A12 | A verdict enters the ledger at the grade its evidence supports, and two models agreeing does not promote anything | `test_a_verdict_does_not_promote_a_proposal` |
| A13 | The roles that run are the ones the request needed, and the decision is recorded | `test_the_roles_that_run_are_the_ones_the_request_needed` |
| A14 | An unmeasurable cost refuses, and a retry does not pay twice | `test_an_unmeasurable_cost_refuses_and_a_retry_does_not_pay_twice` |
| A15 | A human may accept or reject a card, and the decision is audited | `test_a_human_decision_on_a_card_is_audited` |
| A16 | No role may write back to the manuscript, release unauthorised material, or execute code | `test_no_role_may_write_back_release_or_execute` |
| A17 | The demo is run by a test, and it sends nothing | `test_the_guidance_loop_demo_runs` |

**Every one of these needs a witness, and the witness must fail for the
property.** When a test goes red, ask what made it red before believing
that it caught something. **And a mutation that was never applied is
reported by anyone who does not check as a survivor**, which looks exactly
like a success.

## 5. What this work order cannot deliver, and why

- **It does not make the guidance good.** It makes the loop
  **consented, budgeted, recorded, refusable and abstaining**. Whether the
  advice helps is LC-P2-14's question, and the answer may be no.
- **It does not make three agents better than one.** That is the
  `B-only` against `B+C` comparison, and **the result may be that the
  arrangement does not pay for itself.**
- **It does not let a proposal become a fact.** The rules are ADR-0016's
  and the record constructor's, and this path does not bypass them.
- **It does not decide what the advisor would have said.** The cards are
  **proposals**, and the trajectory's candidates are **inferences**; the
  only thing that is a fact is what is in the file.
- **It does not call a real model in its demonstration.** A real run needs
  the owner's authorisation, a limit, and synthetic content that may be
  sent.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | `src/labcairn/roles/spec.py`, `tests/test_agent_role_specs.py` | `src/labcairn/db/models.py`, `migrations/versions/` |
| T01 | `src/labcairn/roles/trajectory.py`, `tests/test_role_trajectory.py` | — |
| T02 | `src/labcairn/roles/guidance.py`, `tests/test_role_guidance.py` | — |
| T03 | `src/labcairn/roles/critique.py`, `tests/test_role_critique.py` | — |
| T04 | `src/labcairn/roles/orchestration.py`, `tests/test_role_orchestration.py` | — |
| T05 | `examples/guidance_loop_demo.py`, `tests/test_guidance_loop_demo.py`, `docs/acceptance/LC-P2-12-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**And the shared files.** `src/labcairn/db/models.py` is shared with every
work order that adds a table, and `src/labcairn/application/refusal.py`
with every work order that refuses something. **Neither may be dispatched
at the same time as another work order that touches them.**

## 7. What "done" means

1. **The role contract is data, and the code enforces it** — a call
   outside it is refused with a machine-readable reason.
2. The seventeen acceptance clauses above have a named test each, **and the
   tests are named as the table names them**.
3. **The demonstration sends nothing** and shows a grounded suggestion, a
   rejected suggestion and a named abstention.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-12-acceptance.md` names the commit
   every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md).
7. **Every claim in §2 has been mutation-checked**: the property broken,
   the witness red, the tree restored.
