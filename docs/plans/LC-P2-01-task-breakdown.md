# LC-P2-01 — The model-call path in the product — task breakdown

**Work order:** LC-P2-01 (the model-call path) · **Status:** drafted
2026-10-30, **not yet dispatched**. **Priority:** the adjustment of
2026-10-30 (P2-AMD-01) puts this **second**, after LC-P2-02 and before
the trajectory work.

## 0. How to read this document

**This is a contract, not a suggestion.** §4 names the acceptance clauses
and, for each, the test that carries it. **This work order spends money**,
and the owner's authorisation is a precondition of the demonstration in
§3.7 — not a footnote, and not something this work order can grant
itself.

**And it must not become a second consent path.** The digest is
recomputed at the moment of use over the capability's canonical arguments;
a ticket that mints its own approval has shipped an authorisation bypass.

## 1. Goals and boundaries

### 1.1 What LC-P2-01 must produce

**One product operation** that asks a **declared** model and records what
came back, under the repository's existing consent, budget, capability and
refusal machinery.

**And the route is configuration.** Which provider and which model is
**operator configuration**, read from the workspace's existing
`providers.json` — **no model id, no endpoint, no price and no capability
claim is written into the tree**, and every supplier is measured
separately by the capability probe.

### 1.2 Already done — removed from scope

- **`providers/`** — three real protocols, the capability probe, the
  budget, the credential store, the redaction pass, the usage capture, the
  cancellation path and the transcript. **They are used, not rewritten.**
- **`CapabilityId.MODEL_REQUEST`** — the **only** `CapabilityId` with
  `Effect.NETWORK`, already registered with `ModelRequestArgs` and
  `root_kinds={source, output}`. **No new capability id is needed for the
  three roles**; ADR-0018's `AgentRoleSpec.allowed_capabilities` names this
  one.
- **The two gates.** LC-P2-06's `transmit_request` already runs the
  material-purpose grant **before** the operation approval is consumed, so
  a refused request leaves the approval unspent. **What is missing is the
  wiring** — and this work order is where it is wired.
- **ADR-0016's promotion rules** — `model_proposal`, the six states, and
  the record constructor's refusal to promote a proposal.
- **The probe's measured answer** (2026-10-28, `MiniMax-M3.1-Flash`):
  `tool_calls` and `usage_reporting` work, and **both structured-output
  forms are declined inside `pydantic-ai` before a request is sent.**

### 1.3 Explicitly not in scope

- **The roles themselves.** LC-P2-12, with ADR-0018's `AgentRoleSpec`.
  This work order builds **the path**; the roles are its first callers.
- **Training, fine-tuning or a specialised model.** P2-AMD-01 removed it
  from the phase's preconditions; LC-P2-15 holds the optional research.
- **The material-purpose grant's own semantics.** LC-P2-06's table. This
  work order **consults** it.
- **A real cloud smoke.** It needs the owner's authorisation, a limit, and
  **synthetic content that may be sent**. The demonstration in §3.7 uses
  `FakeProvider` and **sends nothing**.
- **A second provider configuration format.** `providers.json` is the
  format `load_providers_config` reads.

## 2. The decisions that shape it

### 2.1 The bridge is at the caller, and the provider layer stays disjoint

**ADR-0006 §Risks** says the bridge is not built and names the test that
says so in code: `test_providers_does_not_import_the_permission_layer`
"pins the current boundary. **It is expected to fail when the LC-P1-05
bridge lands**, and that is deliberate."

**That test does not have to fail, and the reason is a decision.** ADR-0006
itself says the arrangement is reversible: *"If outbound consent later
proves to belong inside the provider adapter rather than at its caller,
only this ADR and the call site change."*

**The bridge goes at the caller.** LC-P2-06 already put the transmit gate
in `application/model_transmit.py`, and this work order calls it **there**.
So `providers/` keeps its disjointness from the permission layer, **the
witness stays green, and the boundary does not move.** A design that put
the gate inside the adapter would have made a long-standing witness red
for a change that buys nothing.

### 2.2 Two gates, and the material one is first

**The operation approval** says *this operation may run once, now*. **The
material-purpose grant** says *this material may go to this place, for this
purpose*. **They are different permissions**, and the absence of the second
refuses the request whatever the first says.

**And the order is already implemented and must not be inverted:** the
material check runs **first**, and only a permitted request spends the
approval. `train_reuse` and `external_transmit` are **not**
interchangeable.

### 2.3 A model id is configuration, and a capability claim is a measurement

**Nothing about a supplier is written into the tree.** The route comes from
the operator's configuration; whether a provider may serve a request is
decided by the **capability probe's record** — tool calling, structured
output, context limits, observable usage, error behaviour, and **when it
was measured**.

**And a provider that cannot produce a schema's output is blocked from
that request**, rather than being asked to try. **A parse failure is a
refusal with a reason**, and an illegal JSON is **never** silently turned
into verified evidence.

### 2.4 An unknown answer is unknown

**A request that was sent and did not come back is not a failure and not a
success.** The event log distinguishes **prepared, requested, responded,
unknown**, and an unknown is reconciled by a person. **A retry across a
restart must not pay twice and must not repeat a side effect** — which is
what LC-P2-02's durable approval buys.

### 2.5 What a model says is a proposal, and it is bound before it can be cited

**ADR-0016's rule, unchanged:** a model's say-so is a `model_proposal`, and
it cannot be cited while its verification status is anything other than
`verified_by_rule` or `user_attested`. **And the protocol's third blocker
stands:** any claim the model makes is **bound to a locator** before it can
reach a report. "No scientific-claim inflation" is half the phase's exit
gate, and this work order is where a model's output enters the system at
all.

## 3. The work

### T00 — The dependency, and the configuration

**Files:** `pyproject.toml`, `uv.lock`, `src/labcairn/providers/` (the
configuration reader), `docs/`.

**Declare `httpx`**, which today arrives transitively through `pydantic-ai`
and is in **no** `dependencies` list — the provider path runs on it, so it
must be a version this project chose, and the lockfile moves with it.

**And the model configuration is the operator's**, read from the existing
`providers.json`. **The repository's own configuration carries a fake
provider and nothing else**, so a fresh checkout cannot spend money by
accident.

### T01 — The bridge: the material gate, then the approval

**Files:** `src/labcairn/application/model_transmit.py`,
`src/labcairn/application/model_request.py` (new).

**The call site asks the transmit gate first and consumes the operation
approval only if the gate permits.** This is `transmit_request`'s order,
kept.

**And `providers/` does not import the permission layer.** ADR-0006's
witness stays green, and that is a **deliberate outcome** rather than a
lucky one — see §2.1.

### T02 — The operation, and what it records

**Files:** `src/labcairn/application/model_request.py`, the store methods
it needs.

**One operation**, under the consent layer, that asks a declared model and
records: the **transcript** (what was sent and what came back), the
**usage**, the **cost**, the **target provider and model**, and the
**consent credential** the request was made under.

**And the record is never a secret.** The credential is a reference, not a
value; **a plaintext API key is written nowhere**, and the redaction pass
runs over what goes out.

### T03 — The budget, and the unknown state

**Files:** `src/labcairn/providers/budget.py`, the application's use of it.

**A ceiling that cannot be measured fails closed**, and the existing
`test_cost_ceiling_fails_closed_when_price_unknown` already establishes
that for the layer. **A retry must not pay twice**, and the state machine
is **prepared → requested → responded | unknown → reconciled by a person**.

### T04 — The output, decoded or refused

**Files:** the request module, the schema handling.

**The output is validated against the schema it was asked for.** A refusal
to decode is a refusal with a reason, **and the reason names what was
expected**. **An empty result is not a result**: the path refuses.

### T05 — A model's output enters as a proposal

**Files:** `src/labcairn/application/evidence.py` (or the path that
records it), `src/labcairn/evidence/`.

**A model's answer is recorded as an evidence record whose creator is
`model_proposal`**, it is **bound to a locator** before it can be cited,
and **nothing in this path writes `user_attested` or `verified_by_rule`**.
The record constructor already refuses those; **this path must not bypass
it by writing the creator field itself** (ADR-0016's D2).

### T06 — The refusal vocabulary, and the first use of the role contract

**Files:** `src/labcairn/application/refusal.py`, the application layer.

**The refusals this path can make are in the layer's vocabulary**, with the
closed mapping the other two vocabularies already have, and a witness that
closes them against each other in both directions.

### T07 — The demonstration, and the acceptance record

**Files:** `examples/model_request_demo.py` (new),
`tests/test_model_request_demo.py` (new),
`docs/acceptance/LC-P2-01-acceptance.md` (new), `.github/ci-shards.json`.

**The demonstration uses `FakeProvider` and sends nothing.** It shows the
four outcomes the acceptance names: **consented, budgeted, recorded, and
refused** — and the refusal is the one that matters most, because it is the
one that has to happen **before** a socket exists.

**And the shard costs**, by the two-step process the Phase 2 evidence pack
records.

## 4. Acceptance, mapped to where it is carried

| # | The clause | The test |
|---|---|---|
| A1 | An unapproved model request refuses with a machine-readable reason, **spends nothing**, and **sends nothing** | `test_an_unapproved_model_request_refuses_and_sends_nothing` |
| A2 | With no material-purpose grant, the request is refused **before** the approval is consumed | `test_the_material_gate_runs_before_the_approval_is_spent` |
| A3 | The provider layer does not import the permission layer, and the bridge is at the caller | `test_providers_does_not_import_the_permission_layer` |
| A4 | `httpx` is a declared dependency, and the lockfile moves with it | `test_httpx_is_a_declared_dependency` |
| A5 | No model id, endpoint, price or capability claim is written into the tree | `test_no_model_id_endpoint_or_price_is_written_into_the_tree` |
| A6 | A provider with no capability probe is blocked from a request that needs a schema | `test_an_unprobed_provider_is_blocked` |
| A7 | A ceiling that cannot be measured fails closed | `test_a_cost_ceiling_fails_closed_when_the_price_is_unknown` |
| A8 | A request that was sent and did not answer is **unknown**, and it is reconciled by a person | `test_an_unanswered_request_is_unknown_and_not_a_success` |
| A9 | A retry across a restart does not pay twice and does not repeat a side effect | `test_a_retry_does_not_pay_twice` |
| A10 | An output that cannot be decoded is a refusal naming what was expected | `test_an_undecodable_answer_is_refused_with_the_expectation` |
| A11 | A model's answer is recorded as a `model_proposal`, bound to a locator, and never as `user_attested` or `verified_by_rule` | `test_a_models_answer_enters_as_a_proposal_and_is_bound` |
| A12 | The transcript and the usage land in the store and in the report's hash chain, and **no plaintext key is written** | `test_the_transcript_and_usage_land_and_no_key_is_written` |
| A13 | The refusals this path can make are in the layer's vocabulary, and the two vocabularies are closed against each other | `test_the_model_path_refusals_are_in_the_layers_vocabulary` |
| A14 | The demo is run by a test, and it sends nothing | `test_the_model_request_demo_runs` |

**Every one of these needs a witness, and the witness must fail for the
property.** When a test goes red, ask what made it red before believing
that it caught something. **And a mutation that was never applied is
reported by anyone who does not check as a survivor**, which looks exactly
like a success.

## 5. What this work order cannot deliver, and why

- **It does not make the model good.** It makes the call **consented,
  budgeted, recorded and refused when it cannot be decoded**. Whether the
  answer is any good is LC-P2-14's question.
- **It does not make a real cloud call.** The demonstration sends nothing.
  A real smoke needs the owner's authorisation, a limit, and synthetic
  content that may be sent.
- **It does not make an unknown answer into an answer.** It makes the
  unknown **visible** and reconcilable.
- **It does not let a model's say-so into a report.** It enters as a
  proposal, bound to a locator, and the record constructor refuses the
  promotion.
- **It does not move the provider layer's boundary.** The bridge is at the
  caller, and ADR-0006's disjointness witness stays green.

## 6. The file-ownership map

| Subtask | Files it owns (new unless stated) | Existing files it touches |
|---|---|---|
| T00 | — | `pyproject.toml`, `uv.lock`, `src/labcairn/providers/` |
| T01 | `src/labcairn/application/model_request.py` | `src/labcairn/application/model_transmit.py` |
| T02 | — | `src/labcairn/application/model_request.py`, `src/labcairn/db/repository.py` |
| T03 | — | `src/labcairn/providers/budget.py`, `src/labcairn/application/model_request.py` |
| T04 | — | `src/labcairn/application/model_request.py` |
| T05 | — | `src/labcairn/application/evidence.py`, `src/labcairn/evidence/` |
| T06 | — | `src/labcairn/application/refusal.py` |
| T07 | `examples/model_request_demo.py`, `tests/test_model_request_demo.py`, `docs/acceptance/LC-P2-01-acceptance.md` | `.github/ci-shards.json`, `tests/evaluation/manifest.py` |

**And the shared files.** `src/labcairn/db/repository.py` is shared with
every work order that stores something, and `src/labcairn/application/refusal.py`
with every work order that refuses something. **Neither may be dispatched
at the same time as another work order that touches them.**

## 7. What "done" means

1. **The demonstration sends nothing** and shows the four outcomes:
   consented, budgeted, recorded, refused.
2. The fourteen acceptance clauses above have a named test each, **and the
   tests are named as the table names them**.
3. **The zero-send negative case is witnessed**: an unapproved request
   with an unpublished fragment leaves the network call count at zero and
   the operation approval unspent.
4. The whole suite is green, and `ruff check`, `ruff format --check` and
   `mypy --strict` are clean.
5. The record at `docs/acceptance/LC-P2-01-acceptance.md` names the commit
   every number was measured at.
6. **The review points are recorded**, in
   [`docs/plans/PHASE_2-review-points.md`](PHASE_2-review-points.md).
7. **Every claim in §2 has been mutation-checked**: the property broken,
   the witness red, the tree restored.
