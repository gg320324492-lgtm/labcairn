# ADR-0006: Provider capability and permission capability are different questions

**Status:** Proposed
**Work order:** LC-P1-03 (providers), LC-P1-04 (permissions) — cross-cutting
**Date:** 2026-10-16

## Context and concrete problem

G1 was built by three agents that never looked at each other's work. Independent
cross-review found that the two capability vocabularies LC-P1-03 and LC-P1-04
produced are **disjoint, with no bridge between them**:

```text
providers.Capability      tool_calls, structured_output_native,
                          structured_output_prompted, usage_reporting
security.CapabilityId     fs.read, fs.write, fs.delete, fs.list,
                          source.read, source.inventory, retrieval.query,
                          analysis.run, artifact.write, report.render,
                          model.request

intersection              EMPTY
```

An AST scan of the whole tree found zero imports of `labcairn.security` from
`labcairn.providers`, and zero uses of `CapabilityId` outside `security/`.

The concrete consequence: `CapabilityOutcome.OK(TOOL_CALLS)` — the model *will*
emit tool calls — and whether `CapabilityId.FS_WRITE` is permitted are related
to nothing in the code. A run could report that the model can call tools while
every filesystem capability is denied, and no code would notice.

Worse, and this is the part that is not merely untidy: **sending a request to a
provider is itself an outbound action**, and `CapabilityId.MODEL_REQUEST` exists
precisely to gate it. Nothing connects the two. The permission layer can deny
`model.request` and the provider will still send.

## Alternatives

**A. Unify into one vocabulary.** Let `providers` and `security` share a single
capability enum.

*Rejected.* They answer different questions. `tool_calls` is a fact about a
*model* discovered by probing it. `fs.write` is a *policy* decision about what
*this process* may do. Merging them would imply the permission layer knows
something about models and the provider layer knows something about policy,
and each would then be wrong somewhere.

**B. Leave as-is, document the gap, bridge it in LC-P1-05.**

*Partially rejected.* The gap is real but leaving it entirely to a later
work order means G1 closes with an ungated outbound path, in a gate whose whole
purpose is that outbound requires consent. The decision can be deferred; the
coupling that already exists cannot.

**C. Keep the vocabularies disjoint, state the one real coupling, and make it
executable — chosen.**

## Upstream evidence (reference only)

This is an internal design decision, not an upstream borrow. What it rests on is
ADR-0003's transaction boundary and ADR-0005's ownership split: the application
owns what is known, and an outbound transmission is something it knows about.

## Decision

**The two vocabularies stay disjoint, permanently. One coupling is real and is
made explicit: an outbound transmission is `CapabilityId.MODEL_REQUEST`.**

Three statements, all of which can be made false by a future edit and are
therefore asserted in `tests/test_capability_namespaces.py`:

1. **A provider capability is a fact; a permission capability is a grant.** They
   are never compared, never merged, and a test asserts the intersection stays
   empty. A merge would be a design regression, not a cleanup.

2. **Outbound consent is a permission decision.** Before a request leaves the
   process, `CapabilityId.MODEL_REQUEST` must be evaluated. The evaluation
   belongs to the permission layer; what the provider layer owes is that it
   cannot send without having been handed the result.

3. **A capability probe is not consent.** Probing a model sends requests. A
   probe therefore requires consent too — in the same way, and for the same
   reason, as any other outbound request.

### What is *not* coupled

| Concern | Owner | Why it is separate |
|---|---|---|
| "will this model emit tool calls" | `providers.Capability` | A property of the model, discovered by probing |
| "may this process call `fs.write`" | `security.CapabilityId` | A policy decision about this process |
| "may this process transmit anything" | `security.CapabilityId.MODEL_REQUEST` | A policy decision, and the one that gates the provider layer |
| "what did the run cost" | `providers` ledger | A measurement, and unknown is not zero |

A model that can call tools does not thereby authorise a write. A write that is
permitted does not thereby make the model able to call tools. Conflating either
pair would let one side's answer stand in for the other's.

## Contracts and acceptance tests

`tests/test_capability_namespaces.py`:

- `test_the_two_capability_namespaces_are_disjoint` — the intersection is
  empty. A merge fails here.
- `test_outbound_has_a_permission_capability` — `CapabilityId.MODEL_REQUEST`
  exists, so "gate the outbound path" is expressible rather than aspirational.
- `test_providers_does_not_import_the_permission_layer` — pins the current
  boundary. It is expected to fail **when the LC-P1-05 bridge lands**, and that
  is deliberate: the bridge should be a visible change, not a drift.

The last one is worth stating plainly: it asserts a *limitation*. That is
unusual, and it is the honest form here. An alternative was to delete the test,
which would leave the gap invisible and identical.

## Risks, tradeoffs and reversibility

**The bridge is not built.** `CapabilityId.MODEL_REQUEST` is decided and
enforceable, but nothing yet forces `provider.send()` to consult it. LC-P1-05,
which owns tool dispatch, is where that must happen. Until then a caller can
send without consent, and the test above says so in code rather than leaving
it to be rediscovered.

**A disjoint pair invites a third vocabulary.** Someone facing a third question
may add a bridge enum that both import. The disjointness test catches a merge;
it will not catch a well-meaning intermediate type. The ADR is the counter.

**Reversible.** If outbound consent later proves to belong inside the provider
adapter rather than at its caller, only this ADR and the LC-P1-05 call site
change. The two vocabularies and their disjointness are unaffected either way.

## Re-evaluation trigger

Revisit when LC-P1-05 lands tool dispatch — that is the first point at which a
model's tool capability and a permitted tool capability must be reconciled, and
the first real test of whether keeping them disjoint was right.
