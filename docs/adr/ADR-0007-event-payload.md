# ADR-0007: Adding the `payload` field the event contract always specified

**Status:** Proposed
**Work order:** G2 integration (LC-P1-05 / 06 / 07)
**Date:** 2026-10-16

## Context and concrete problem

ADR-0003 C1 lists `payload` as a column of the event table:

> | `payload` | JSON, validated against the type's Pydantic model |

The frozen `Event` contract never had that field. Its columns are `event_id`,
`seq`, `task_id`, `run_id`, `stage_id`, `operation_id`, `type`, `transition`
and `occurred_at`, and its model config is `extra="forbid"`.

Two work orders have now had to work around the gap, both honestly and both at
a cost:

- **LC-P1-05** stores the whole Event document as JSON in a dedicated column,
  because there is nowhere for the type-specific part to go.
- **LC-P1-06** cannot persist `resolution='confirmed_by_probe'`. It writes the
  resolution as the `operation_reconciled` event's `to_state` using C2's own
  vocabulary, and the fact is **re-derivable** — `CONFIRMED` is reachable two
  ways and the event log tells them apart, because one path emits
  `operation_reconciled` and no receipt. Re-derivable is not the same as stored.

A workaround that has to be explained twice is telling us the contract is
missing something it says it has.

## Alternatives

**A. Leave it.** Both workarounds function. The re-derivation is sound and
tested.

*Rejected.* It is sound only as long as C2's vocabulary has exactly the two
paths to `CONFIRMED`. The next state that becomes reachable two ways makes the
inference ambiguous, and the failure is silent — a reader would derive the
wrong provenance and have no way to tell. The whole point of the event log is
that it answers these questions directly.

**B. A Pydantic model per event type, 25 of them.** The literal reading of
"validated against the type's Pydantic model".

*Rejected as the wrong first step, not as wrong.* Most event types carry nothing
today beyond what the columns already hold, so 25 models would be 25 empty
classes and a discriminator, with the validation coming from a union that adds
cost to every insert for no current benefit. It is also a much larger change to
a frozen contract than the gap requires.

**C. One optional `payload` mapping, JSON-typed, with the schema declared per
type in one table — chosen.**

## Decision

`Event` gains:

```python
payload: Mapping[str, object] = Field(default_factory=dict)
```

Plus a **schema registry**, `EVENT_PAYLOAD_SCHEMAS: Mapping[EventType, type[LabCairnModel]]`,
which is empty today and grows as event types acquire content. Validation runs
in `Event`'s model validator:

- an event whose type has a registered schema must satisfy it
- an event whose type has no schema must carry an **empty** payload

The second rule is the one that matters. Without it, `payload` becomes a
free-form bag that anything can be dropped into — which is exactly the
"attributed to no one" state that the `extra="forbid"` config exists to
prevent, reintroduced through the back door.

**Corrected 2026-10-28: where the registration lives is part of the rule.** A
schema registered as a side effect of importing the *writer* is absent in a
process that only reads — `events_after` imports the vocabulary and not the
recovery layer — so the event validates where it was written and fails where
it is read. Schemas for the vocabulary therefore live in
`labcairn.runtime.event`; `ReconciliationPayload` moved there from
`labcairn.recovery.reconciliation`, and
`tests/test_event_payload_vocabulary.py` reads a stored event in a fresh
interpreter that never loads the recovery layer.

### What this makes possible immediately

LC-P1-06's reconciliation can register
`EventType.OPERATION_RECONCILED` with a schema carrying `resolution` and
`verdict`, so `confirmed_by_probe` is **stored** rather than inferred. That is
the change the gap was blocking.

### What it deliberately does not do

No per-type models are written speculatively. A type gets a schema when some
work order has content for it, and adding one is a local change: a registry
entry and a model. The registry being the only place that knows which types
carry content means a reader can answer "does this event have a payload?" in
one place rather than by inspecting 25 models.

## Contracts and acceptance tests

- `test_an_event_with_no_registered_schema_must_carry_no_payload` — the
  anti-bag rule. Dropping an arbitrary key into an unregistered type's payload
  fails.
- `test_a_registered_type_validates_its_payload` — a missing required key, a
  wrong type, and an unknown key are each refused.
- `test_the_registry_matches_the_contract` — every registered key is a real
  `EventType`, so a typo fails at import rather than at insert.
- `test_payload_round_trips_through_json` — a populated payload survives
  `model_dump_json` → `model_validate_json` byte-identically.
- `test_an_unregistered_type_with_an_empty_payload_is_accepted` — the ordinary
  case still works, so the rule does not make every event carry ceremony.

## Risks, tradeoffs and reversibility

**This changes a frozen contract after two work orders were built against it.**
That is the cost, and it is why it is an ADR rather than a commit. The change is
additive: `payload` defaults to an empty mapping, so every existing event,
stored document and test remains valid, and the migration adds one nullable
column.

**The registry is a place for drift to hide.** A type with content but no
registered schema would let that content be dropped silently — the same class of
failure as the empty-payload rule prevents, one level up. The contract test
above narrows it; it cannot close it, because "this type should have a schema"
is not machine-checkable. Named as a standing risk.

**Reversible.** Removing the field and the registry restores the previous
contract; the stored column is simply ignored. Nothing depends on `payload`
being present except code written after this ADR.

## Re-evaluation trigger

Revisit if more than a handful of types acquire schemas — at that point the
"one mapping plus a registry" shape may want to become a real discriminated
union, and the tradeoff in alternative B changes.
