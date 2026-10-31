# LC-P2-01 — The model-call path — acceptance

**Work order:** LC-P2-01 (one product operation that asks a declared
model) · **Subtasks:** T00–T07 · **Task breakdown:**
[`../plans/LC-P2-01-task-breakdown.md`](../plans/LC-P2-01-task-breakdown.md)
· **Status of the work order:** the dependency decision, the bridge,
the operation and its record, the budget, the decoded-or-refused
output, the proposal entry, the closed refusal vocabulary, the
demonstration and this record are landed.

**What this is.** One operation, `request_model`, that turns "a model
may be asked" into an actual ask — under the consent layer's two gates
in their order, under a budget that fails closed, with the exchange
recorded in the provider layer's own wire form, the answer judged
against the schema it was asked for, and what a model says entering the
ledger as a `model_proposal` bound to a locator. The bridge is at the
caller: `providers/` still imports nothing of the permission layer, and
that is a deliberate outcome rather than a lucky one.

**What this is not.** Work order §5 says so in its own words: it does
not make the model good (LC-P2-14's question), it does not make a real
cloud call (the demonstration sends nothing, and a real smoke needs the
owner's authorisation), it does not make an unknown answer into an
answer, and it does not let a model's say-so into a report.

---

## 1. The decisions, and where each is held

| # | The decision | Held by | Witnessed by |
|---|---|---|---|
| D1 | **httpx is declared** at `>=0.27,<1`, the lockfile moves with it, and the tree carries no **route** to a supplier — no configuration file, no price, no capability claim, and no authorised supplier's model id or endpoint — so a fresh checkout cannot spend money by accident, and the operator's `providers.json` is the only route to a real supplier | `pyproject.toml`, `uv.lock`, ADR-0019 | `test_httpx_is_a_declared_dependency`, `test_no_model_id_endpoint_or_price_is_written_into_the_tree`, and the six witnesses in `tests/test_provider_credentials.py` that read the checkout |
| D2 | **The bridge is at the caller**: `request_model` hands the caller's `ApprovalUse` straight to `transmit_request` and inherits its order as the property it is — the material gate first, then the approval — and builds no gate of its own | `src/labcairn/application/model_request.py` | `test_providers_does_not_import_the_permission_layer`, the two T01 witnesses |
| D3 | **The budget's preflight runs before the gate**, because a refusal that cannot be measured should not cost the person their approval | the first lines of `request_model` | `test_a_cost_ceiling_fails_closed_when_the_price_is_unknown` |
| D4 | **A schema request the provider's probe does not license is refused at the same price — nothing**: before the gate, before the wire, and the two ways not to be licensed name themselves (never probed vs probed-and-failed, because their remedies differ) | `_require_schema_ability`, `ModelRefusal` | `test_an_unprobed_provider_is_blocked` |
| D5 | **What came back is judged, not accepted**: an empty result is not a result; an undecodable answer is a refusal naming what was expected; the refusal does not unstate the call — the exchange record stays — but illegal output is never silently turned into evidence | `_decode` | `test_an_empty_result_is_not_a_result`, `test_an_undecodable_answer_is_refused_with_the_expectation` |
| D6 | **The exchange is an annotation**: `model_exchanged` carries the provider layer's wire form — digests and counts, never text — the credential by its fingerprint, and lands in the same unit of work as the fact it records | `src/labcairn/runtime/model_exchange.py`, the four SQL CHECK word lists of revision 0001 | `test_the_transcript_and_usage_land_and_no_key_is_written`, the store's schema-parity suite |
| D7 | **A model's answer enters as a proposal**: creator `model_proposal`, status `planned`, and the locator is an argument of the write, not something parsed out of the answer afterwards. The constructor holds the line the proposal cannot cross, and nothing on this path writes the creator field around it | `record_model_proposal` in `src/labcairn/application/evidence.py` | `test_a_models_answer_enters_as_a_proposal_and_is_bound` |
| D8 | **The path's refusals are named in the layer's vocabulary**, closed against each other in both directions, and the path raises through `model_refused` so every reason arrives looked up rather than hand-written | `src/labcairn/application/model_refusals.py`, `MODEL_REFUSALS` | `test_the_model_path_refusals_are_in_the_layers_vocabulary`, `test_the_path_raises_through_the_vocabulary` |
| D9 | **An unanswered call is unknown and not a success**, and one approval pays for one call across a restart | the raise of the provider's own error; the consumption of the approval | `test_an_unanswered_request_is_unknown_and_not_a_success`, `test_a_retry_does_not_pay_twice` |

## 2. The acceptance clauses, and where each is carried

| # | The clause | The test |
|---|---|---|
| A1 | An unapproved request refuses, spends nothing, sends nothing | `test_an_unapproved_model_request_refuses_and_sends_nothing` |
| A2 | No material-purpose grant, refused **before** the approval is consumed | `test_the_material_gate_runs_before_the_approval_is_spent` |
| A3 | `providers/` does not import the permission layer; the bridge is at the caller | `test_providers_does_not_import_the_permission_layer` |
| A4 | `httpx` declared; the lockfile moves with it | `test_httpx_is_a_declared_dependency` |
| A5 | No model id, endpoint, price or capability claim written into the tree | `test_no_model_id_endpoint_or_price_is_written_into_the_tree` |
| A6 | A provider with no capability probe is blocked from a request that needs a schema | `test_an_unprobed_provider_is_blocked` |
| A7 | A ceiling that cannot be measured fails closed | `test_a_cost_ceiling_fails_closed_when_the_price_is_unknown` |
| A8 | A sent-and-unanswered request is **unknown**, reconciled by a person | `test_an_unanswered_request_is_unknown_and_not_a_success` |
| A9 | A retry does not pay twice | `test_a_retry_does_not_pay_twice` |
| A10 | An undecodable output is a refusal naming what was expected | `test_an_undecodable_answer_is_refused_with_the_expectation` |
| A11 | A model's answer is a `model_proposal`, bound to a locator, never `user_attested`/`verified_by_rule` | `test_a_models_answer_enters_as_a_proposal_and_is_bound` |
| A12 | The transcript and the usage land; **no plaintext key is written** | `test_the_transcript_and_usage_land_and_no_key_is_written` |
| A13 | The path's refusals are in the layer's vocabulary, closed both ways | `test_the_model_path_refusals_are_in_the_layers_vocabulary` |
| A14 | The demo is run by a test, and it sends nothing | `test_the_model_request_demo_runs`, `test_the_demonstrations_exit_code_still_means_something` |

## 3. The mutations, and what each one proved

Every mutation was applied to the working tree, run, and reverted; the
witness that reddened and the count are recorded beside it. A mutation
that reddens nothing is a property nobody is watching, and a mutation
that reddens the wrong thing is a claim about the wrong property.

| Where | The mutation | What reddened | What it proved |
|---|---|---|---|
| T00 | the `httpx` line removed from `pyproject.toml` | exactly A4's witness | the declaration is written, not assumed |
| T00 | `MiniMax-M3.1-Flash` written into a `src/` file | exactly A5's witness | the scan reads the tree, not the intentions |
| T01 | the caller's `send` reached before `transmit_request` | both T01 witnesses at once | they watch the same order from its two sides |
| T02 | `credential_fingerprint` sent a key-shaped string | exactly A12's witness | the record's shape is the proof, not the docstring |
| T03 | the preflight moved past the approval consumption | exactly A7's witness | the position *is* the property |
| T04 | the schema-ability check dropped | exactly A6's witness | the unprobed provider was never asked to try |
| T04 | the decode failure passed the answer through | exactly A10's witness | illegal output is refused, not handed on |
| T04 | the empty-result check dropped | exactly its witness | an empty result is not a result |
| T05 | the proposal's status graded to `EXTRACTED` | exactly A11's witness | a proposal reaches planned and no further |
| T05 | the locator binding dropped (`anchor_ids=()`) | exactly A11's witness | the record enters the ledger already pinned |
| T06 | an orphan `MODEL_*` member with no mapping row | exactly A13's witness | the closure holds in both directions |
| T07 | the demonstration's first `check` planted false from outside | the exit code, in `test_the_demonstrations_exit_code_still_means_something` | the demonstration's verdict still means something |

Two incidents are recorded because the discipline they teach is the
record's: the A4 restore script's anchor did not survive a CRLF file
and failed *silently*, discovered only because the A5 mutation round
ran with A4 already red — a restore that does not assert its own
success is not a restore; and the T04 restore script's second write
overwrote its first recovery with stale text, discovered because the
unprobed witness reddened with the wrong refusal. Restorations now
happen in one read-modify-write, and every mutation script asserts its
anchors before writing.

## 4. What was measured, and on what tree

- T00–T03 measured at commits `cdc1d71`, `bf5547c`, `2d70f62`,
  `f2221d7`; T04 at `d76aac0`; T05 at `1357f8c`; T06 at `63dfbf8`; T07
  on its own commit. The unit of evidence is the single worktree of
  `claude/p2-lc-p2-10-plans`; every run's `--basetemp` was outside the
  repository, and no two runs shared one.
- The suites run on this machine before this record was written:
  `tests/test_model_request_path.py` (15), the evidence suites
  (108), the refusal-vocabulary suites (36), and the demonstration's
  own two. Every one green; lint and `mypy` clean on every file the
  work order touched.
- **The shard costs were re-measured on 2026-10-31, and one witness is
  still red.** Fifteen test files this phase added had no runner-measured
  costs, so `test_ci_shard_coverage`'s coverage clauses were red on
  purpose until a runner's `--durations=0` output existed to apportion
  from. The costs are now written from the last green runner's log
  (`python .github/remeasure_shards.py 41110813867`), and the partition is
  rebuilt from the runner's numbers rather than guessed. What remains red
  is `test_the_costs_belong_to_the_tree_they_were_measured_on`:
  `tests/test_store_events.py` changed on this branch, and its cost
  exceeds the partition's slack, so the witness asks for a measurement of
  the current tree — which is a push, and a push is the owner's call.
  **The numbers must come from a runner**; a development machine answers
  differently, not only a different total but a different order.
- **The checked-in TypeScript contract was regenerated on 2026-10-31.** The
  `model_exchanged` event this work order added had not been carried into
  `web/src/api/generated.ts`, and `test_the_checked_in_typescript_is_what_
  the_python_models_produce` was red for exactly that one line. The file is
  generated from the OpenAPI document, which is generated from the models,
  so it was regenerated rather than edited: `uv run python -m
  labcairn.api.typescript web/src/api/generated.ts`. The witness that
  watches the drift was already in the suite; it had simply never run
  against this branch's tree.

## 5. What this work order does not carry

Work order §5's own list, unchanged: it does not make the model good;
it does not make a real cloud call; it does not make an unknown answer
into an answer; it does not let a model's say-so into a report. The
proposal's status is `planned`, and the checks that would grade it are
the evidence ledger's own, not this path's.

## 6. The weakest point an independent review found

An independent read-only review re-applied eleven mutations on this
work order's tree and found every claim here **holds**. Its weakest
point is the one this record should name: **the exchange record's
safety is held by this path's discipline and its callers' honesty, not
by the payload's type.**

`ModelExchangePayload.exchanges` is `list[dict[str, object]]` — free
shaped — and `request_model` forwards whatever `send()` returns
verbatim into the event log. Nothing on the write path re-validates
that each entry is the provider layer's `ExchangeRecord` wire form, and
`credential_fingerprint: str = Field(min_length=1)` accepts a
key-shaped string without complaint. The mutation that sent a key-shaped
string as the fingerprint rode exactly that hole; only the assertion on
the exact scripted value caught it.

**Why it is not yet a defect.** The only `send` implementations are the
repository's own, and they are right. But LC-P2-12's three roles all
funnel through this path, and a role that composed an `ModelInvocation`
by hand — or an adapter bug that put text into an exchange dict —
would have that text persisted with every test green.

**The remedy:** type the exchanges as the provider layer's record type,
or check each dict against it at the emit, so that "no text, no key"
moves from a docstring and a witness to the schema itself.
