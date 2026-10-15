# ADR-0005: App-owned research semantics, framework-owned model interaction

**Status:** Proposed
**Work order:** LC-P1-02 (versioned contracts and module boundaries)
**Date:** 2026-10-15

## Context and concrete problem

`docs/ARCHITECTURE.md` commits to "Pydantic AI for model/tool interaction, not as
authoritative project/task data storage", and LC-P1-02 requires an ADR covering
that decision. The problem is concrete rather than philosophical: two of the
three ADRs written during LC-P1-00 reached conclusions that a framework-owned
task state would have made impossible to express.

1. ADR-0002 found that both Pydantic AI and OpenHands normalise an unmeasured
   cost to zero, and that OpenHands' budget check then never trips.
2. ADR-0003 found that recovery must *enter* an `UNCERTAIN` state rather than
   assume a side effect did not happen, and that a per-Task gapless `seq`
   cannot be a SQLite rowid.

Both are properties of **what the project knows**, not of how a model was
called. If the framework owned the record, neither could be represented without
fighting it.

The concrete question: where does the truth about a research task live?

## Alternatives

**A. Let the framework own task state.** Pydantic AI's message history, or a
graph/state object, becomes the record. Cheapest to build first, and the
default shape of most agent code in the wild.

*Rejected.* The research record must survive the model conversation. A crash
mid-run, a revision, or a resumed session three days later must still be able
to answer "what was true about this Task, what was actually written, and what
is still unverified" — and none of that is in a message list. It also makes the
framework the upgrade boundary for the project's most valuable asset.

**B. No framework: hand-rolled loop.** Write the model call, tool dispatch,
retry and schema handling directly.

*Rejected as premature, not as wrong.* ADR-0002 already assessed it: streaming
tool-call assembly, incremental JSON-schema repair, retry-after handling and
token accounting across three protocol dialects have no upstream test corpus
behind a hand-rolled version. ADR-0002 keeps it as the strongest Phase 2+
option and notes the contracts here are shaped so a hand-rolled adapter can be
dropped in behind `ModelProvider` without changing callers. That property is
the reason it is rejected now rather than dismissed.

**C. Split ownership — chosen.** The framework owns how a model is *called*; the
application owns what is *known*.

## Upstream evidence (reference only)

- Repository: `https://github.com/pydantic/pydantic-ai` @ `9ac853bb84ffed7ba0edccb026c5b4f3228c1de7`
- Inspected: `usage.py` (`UsageBase.cost: Decimal | None` at `:140`, alongside
  `input_tokens: int = 0` at `:392` and `output_tokens: int = 0` at `:407`);
  `models/__init__.py` (no `supported_tools()` anywhere);
  `profiles/__init__.py` (static `TypedDict` keyed by model name, default
  `'supports_tools': True` at `:360`)
- What was observed: an optional `cost` alongside integer token counters that
  default to zero, and capability flags resolved from the model *name* rather
  than probed. Neither can express "this run's cost is unknown".
- Repository: `https://github.com/OpenHands/software-agent-sdk` @ `8efff8d3cf1a5a3fcf7ce5e3b97c7f00684d9547`
- Inspected: `llm/utils/metrics.py` (`accumulated_cost: float = 0.0` at `:83`);
  `event/base.py`; `event/error_classification.py`; `tests/sdk/conversation/local/test_confirmation_mode.py`
- License obligations: MIT for both; nothing copied, only referenced.

## Decision

**LabCairn owns research semantics. Pydantic AI owns model interaction.**

Concretely, the boundary is:

| Owned by LabCairn | Owned by the framework |
|---|---|
| Task, Run, Stage, Operation, Approval, Checkpoint | Model transport and streaming |
| Event log, `seq`, `UNCERTAIN` | Tool-call schema validation |
| Evidence, SourceAnchor, ArtifactReceipt | Retry/usage accounting mechanics |
| Budget ceilings and `unknown` semantics | Message assembly |
| Canonical digests and approval binding | — |

Three consequences that are *not* optional consequences of the split:

1. **`unknown` is a value, not an absence.** `Known` and `Unknown` are distinct
   types and a folded `Unknown` is rejected by the type checker, by runtime
   coercion, and by a wire format whose wrong key raises. A framework that
   defaults a missing number to `0` cannot be corrected by the application
   afterwards, because by then the zero has been compared, summed and budgeted.
2. **The event log is not the conversation.** `seq` is allocated per Task by
   the application; the framework's message ordering is irrelevant to it. A
   resumed client reads `after_seq` from LabCairn, not from the model history.
3. **The application store is the only authority.** SQLite holds what is known;
   Pydantic AI holds what was said in a given turn. Neither can reconstruct the
   other, and only one of them survives a crash.

## Contracts and acceptance tests

`src/labcairn/core/{schema,ids,primitives}.py`, `src/labcairn/runtime/`,
`src/labcairn/sources/`, `src/labcairn/evidence/`, `src/labcairn/reports/`
with `tests/test_runtime_contracts.py`, `tests/test_id_aliases_are_nominal.py`,
`tests/test_source_contracts.py` and `tests/test_evidence_contracts.py`.

- `test_digest_refuses_arguments_that_would_make_it_lie` — an integer key
  would collide with its string form under `json.dumps`, and `NaN` would
  produce a digest no compliant reader could reproduce.
- `test_digest_is_reproducible_by_a_plain_json_reader` — an independent
  canonicalisation lands on the same digest, which is what "same on any
  platform" has to mean if it means anything.
- `test_run_scoped_events_require_a_run_id` (parameterised over a list typed
  out from ADR-0003's table, not sampled from the function under test) /
  `test_annotations_do_not_need_a_run` — event scope matches the five
  families.
- `test_seq_starts_at_one_and_is_per_task` — two Tasks both start at `seq == 1`.
  A rowid would give them different numbers.
- `test_events_do_not_expose_a_row_identity_field` — `id` cannot leak onto the
  model, where a consumer might sort by it and get the wrong order.
- `test_every_refusal_reason_is_reachable` — all seven approval refusals from
  ADR-0003 C4 are produced by real inputs.
- `test_unsupported_schema_versions_are_refused` — a payload from a newer
  writer is refused **at construction**, by the base model, not by a method
  nothing calls.
- `test_task_id_is_not_assignable_to_run_id` — the ID aliases are nominal.
  It shells out to mypy because the guarantee cannot be asserted from Python,
  and is paired with a control probe that must type-check cleanly, so a failure
  for the wrong reason does not read as a pass.

## Risks, tradeoffs and reversibility

**The split has a cost.** Every model call now crosses a boundary: the
application must translate the framework's types into its own and back. That is
real work with a real failure surface, and it is the price of being able to say
anything definite about a research claim afterwards.

**The boundary can erode.** The first time someone reaches into framework state
to avoid a translation, the split quietly ends. The tests above are the guard,
and this ADR is the reference to point at when that happens.

**Known limit, stated because it is easy to assume otherwise.** The ID types are
nominal to a type checker but transparent at runtime — `TaskId(x)` returns the
same UUID. That is what `NewType` is; enforcing them at runtime would mean
`isinstance` checks on every boundary. The tests assert the half that is
assertable and say so.

**Reversible.** `ModelProvider` is a Protocol with one method. A different
framework, or a hand-rolled adapter, replaces the import behind it. The
contracts deliberately do not name Pydantic AI in any of their fields or types.

**Wrong if measured otherwise.** If a framework later provides durable,
crash-safe, gapless-ordered application state that survives process death, this
ADR's central claim weakens considerably. That is worth re-testing at each gate
rather than treating as settled.

## Re-evaluation trigger

Revisit when any of these holds: LC-P1-03 finds the translation boundary
requires more code than the provider integration itself; a measured need for
durable agent state appears that the application store cannot serve; or
Pydantic AI ships a state model with per-run gapless ordering and an explicit
unknown-cost type.
