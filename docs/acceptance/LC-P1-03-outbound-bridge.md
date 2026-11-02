# LC-P1-03/04 cross-cutting: the outbound consent bridge

**Date:** 2026-11-02
**Work order:** LC-P1-03 (providers) × LC-P1-04 (permissions) — the debt
recorded when Phase 1 closed
**ADR:** ADR-0006, §Decision statement 2
**Status:** implemented; local measurement only (no runner, no pull request)

## The debt

ADR-0006 named it in one sentence:

> *Sending a request to a provider is itself an outbound action, and
> `CapabilityId.MODEL_REQUEST` exists precisely to gate it. Nothing connects
> the two. The permission layer can deny `model.request` and the provider will
> still send.*

Both halves existed — `ApprovalLedger` could grant and spend a capability, and
`PydanticAiModelProvider.send` could send — and no code joined them. A caller
could construct the provider and call `send` with no permission decision in
existence at all.

## What was built

### The provider's side: a required port, not an import

`src/labcairn/providers/consent.py` defines `OutboundConsent`, a one-method
Protocol:

```python
def require(self, request: ModelRequest) -> None: ...
```

`PydanticAiModelProvider.__init__` now takes `consent: OutboundConsent` as a
**required keyword argument**, and `send` calls `self._consent.require(request)`
after the local pre-flights and immediately before `_send_ungated`. A refused
request raises the provider layer's existing `OutboundRefusedError`
(`FailureKind.OUTBOUND_REFUSED`), and the transport is never reached.

**Why the port and not an import.** ADR-0006's two constraints pull in
opposite directions and the port satisfies both: the evaluation belongs to the
permission layer, and the provider "cannot send without having been handed the
result". A Protocol in `providers/` lets the decision cross as a value while
`providers/` still imports nothing from `labcairn.security` — the vocabularies
stay disjoint, and `tests/test_capability_namespaces.py` keeps watching that
boundary.

**Why it is required rather than defaulted.** A defaulted port is a defaulted
permission: `consent=None` would restore exactly the defect. There is now no
construction path that omits the hand-off, and
`test_the_provider_cannot_be_built_without_a_consent_port` is the structural
witness.

**Why the consent check runs after the capability gate and the budget.** Those
pre-flights can refuse with no effect, and an approval is single-use; spending
it on a call the budget was about to refuse would cost a person a new approval
for nothing. The order is ADR-0015 D3's "asking is not spending", applied at
the provider boundary. Once `require` returns, the call is made and cannot be
repeated.

### The permission layer's side: one approval, spent through the one function

`src/labcairn/application/outbound.py` defines `OutboundApproval`, the
implementation of the port bound to one granted approval:

```python
@dataclass(frozen=True, slots=True)
class OutboundApproval:
    context: ApplicationContext
    approval_id: ApprovalId
    use: ApprovalUse
    at: datetime

    def require(self, request: ModelRequest) -> None: ...
```

`require` calls `consume_approval` — the one function that spends an approval,
and the one that already validates the capability's arguments, asks the policy,
recomputes the digest at the moment of use, and moves the row to `CONSUMED`.
The module translates `ApplicationRefusedError` into `OutboundRefusedError`;
it builds no second consent path and widens no approval.

**Single use is the ledger's, not the object's.** A second `require` re-reads
the row, sees `CONSUMED`, and refuses. Expiry is checked at the moment of use,
so an approval granted inside its window and spent after it closes is refused.
Neither of those facts is re-implemented here.

## The witnesses

`tests/test_outbound_consent_bridge.py` — every assertion about "the request
did not leave" is made on `FakeEndpoint.calls`, the recording upstream.

| Test | Property |
|---|---|
| `test_a_missing_approval_refuses_the_send_and_sends_nothing` | No approval row → `OutboundRefusedError`, zero upstream calls. |
| `test_a_pending_approval_is_not_consent` | A question asked and not answered authorises nothing. |
| `test_an_expired_approval_refuses_before_the_wire` | Expiry is measured at the decision moment, not the grant. |
| `test_a_policy_refusal_does_not_spend_the_approval` | A permission withdrawn after the grant refuses the send **unspent** (the product's closest state to revocation; see "Not done" below). |
| `test_a_budget_refusal_does_not_spend_the_approval` | The consent check is the last pre-flight, so a local refusal costs no approval. |
| `test_a_granted_request_is_sent_and_the_approval_moves_to_consumed` | The happy path: one call out, one row spent. |
| `test_the_same_approval_cannot_authorise_two_sends` | The second `send` is refused by the ledger; upstream count stays one. |
| `test_the_provider_cannot_be_built_without_a_consent_port` | There is no construction path that omits the hand-off. |

**Mutation-checked.** Each witness was run against a deliberately broken tree
and was observed red; the mutations and their results are recorded in the
session that produced this file. A witness that could not be made to fail was
not counted.

## Callers updated (a behaviour change, not a regression)

`PydanticAiModelProvider` is constructed in no production module today — the
application path calls a caller-supplied `send` callable — so no product call
site changed. Five test constructions did, because the port is required:

- `tests/test_provider_adapter.py`: the `_provider` helper and one direct
  construction now pass `PermissiveConsent()`, a new fake in
  `tests/provider_fakes.py` that records being asked. Those tests' subject is a
  different gate; the refusal path is witnessed in the new file.
- `tests/test_provider_redaction.py`: three constructions, same fake.

This is a **behaviour change**: a provider built without a consent port no
longer exists, and `send` without a live decision no longer sends. It is not a
regression, and the updated tests were not weakened — their assertions are
unchanged.

`tests/test_capability_namespaces.py`'s third test was **not** broken by the
bridge, because the bridge crosses as a value rather than as an import. Its
docstring was updated from "pins a known limitation" to "pins the shape of the
bridge that landed"; the assertion itself is unchanged.

## Registration

- `tests/test_outbound_consent_bridge.py` declares
  `pytestmark = pytest.mark.integration`.
- `.github/ci-shards.json`: filed under shard 3 on both platforms, beside
  `test_model_request_path.py`. **The cost is deliberately not guessed** — it
  must be measured on the runner, and `test_the_recorded_costs_cover_every_test_file`
  is expected red until then.
- `tests/evaluation/manifest.py`: `("integration", "approvals")`.

**Expected local reds, and why they are correct:**

1. `test_ci_shard_coverage.py::test_the_recorded_costs_cover_every_test_file`
   — the new file has no measured cost. Fix on the next runner run with
   `python .github/remeasure_shards.py <run-id>`; a local number is not a
   runner number (CLAUDE.md, "The CI runs in shards").
2. `test_ci_shard_coverage.py::test_the_costs_belong_to_the_tree_they_were_measured_on`
   will go red once this commit changes `src/` and `tests/`. That is the
   project's own rule — a value that can change is re-measured, not carried
   forward — and the same command fixes it.

## Not done

- **The probe path is still a second outbound path.** `PydanticAiProbe`
  issues requests through its own `ProbeModel`, not through
  `PydanticAiModelProvider.send`. ADR-0006 statement 3 says a probe therefore
  requires consent too, in the same way. This work order changed `send`; the
  probe needs its own port, and it is named here rather than silently left.
- **There is no `REVOKED` approval state in the product.** `ApprovalState` has
  `PENDING`, `GRANTED`, `DENIED`, `CONSUMED`, `EXPIRED`, and no public API
  moves a granted row to `DENIED`. The witnesses cover every refusal the
  machine can produce — missing, pending, expired, consumed — plus the policy
  withdrawal case, which is the closest observable analogue of revocation.
  Inventing a state to satisfy the word "revoked" would have been a second
  vocabulary.
- **No integration between `request_model` and the provider port was wired.**
  The application path spends its approval through `transmit_request` and then
  calls a caller-supplied `send` callable; wiring the provider into that path
  means handing it a port that represents the decision already made, and that
  is wiring work with its own order to preserve. The provider boundary is now
  closed regardless: a caller that bypasses the application path must still
  hand over a live decision.

## Measurement

Local, in the repository's virtualenv, with `TEMP`/`TMP`/`TMPDIR` and
`--basetemp` outside the checkout:

```text
tests/test_outbound_consent_bridge.py                                  8 passed
provider adapter + redaction + namespaces + model-request + approvals
  + evaluation harness (155 tests)                                  155 passed
ruff check                                                           passed
ruff format --check                                                  passed
```

The shard-cost red is expected and is recorded above. Nothing was pushed; no
pull request was opened.
