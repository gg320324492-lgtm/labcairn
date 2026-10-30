# ADR-0019: The model-call path's dependency, and a checkout that cannot spend money by accident

**Status:** Proposed
**Work order:** LC-P2-01.
**Date:** 2026-10-31

## Context and concrete problem

LC-P2-01 wires the model-call path into the product: one operation under
the consent layer that asks a declared model and records what came back.
Two facts about the tree it runs in are the problem this ADR settles.

**First, `httpx` runs the path but is declared by nobody.** It arrives
transitively through `pydantic-ai` and appears in **no** `dependencies`
list — `pyproject.toml` does not name it, and
`src/labcairn/providers/credentials.py`'s module docstring has carried a
warning saying so since the provider layer landed. A library the
product's network path is built on must be a version **this project
chose**: a transitive arrival can move under us on an unrelated resolve,
and nothing in the tree would say the project had an opinion about it.

**Second, nothing stops a fresh checkout from being one typo away from a
paid call.** The operator's configuration (`providers.json`) names the
provider, the model and where the credential lives; the repository
itself ships no configuration. The guarantee the work order asks for is
precise: **the repository's own configuration carries a fake provider and
nothing else**, so out of the box the model path runs against
`FakeProvider` and sends nothing, and spending money requires an
operator's deliberate act — a configuration file, a credential, and a
consumed approval.

## Decision

**D1 — `httpx` is declared, at `>=0.27,<1`.** The locked version is
0.28.1, already inside the range, so the resolve does not move: the
declaration makes the project's opinion explicit rather than changing
what is installed. The licence is BSD-3-Clause; it is a runtime
dependency because `providers/adapter.py` and the real-protocol clients
import it directly, not because a transitive path happens to touch it.

**D2 — no model id, no endpoint, no price and no capability claim is
written into the tree.** The route is the operator's `providers.json`;
the capability claims live in the **probe's record** (measured, dated,
in the store), never in source. The two public endpoints in
`DEFAULT_BASE_URLS` are **protocol defaults** — library knowledge of
where OpenAI's and Anthropic's documented endpoints sit — and are not
this project's supplier choice. The models the capability probe has
measured are recorded in the work orders' measurement histories
(`docs/plans/`), which are records, not configuration.

**D3 — the default is the fake.** Where no operator configuration
exists, the model path resolves to `FakeProvider`. The refusal
vocabularies and the budget still run — the fake is a provider, not an
exemption — so a test or a demonstration exercises the same gates a real
call would, minus the wire.

## Consequences

- `pyproject.toml` declares `httpx>=0.27,<1`; `uv.lock` moves with it.
- The warning in `credentials.py`'s module docstring is retired with the
  debt it described.
- `tests/test_model_request_path.py` carries the two witnesses (A4, A5):
  the declaration and the lockfile, and the tree scan for written model
  configuration. The scan's vocabulary grows if and when the owner
  authorises a supplier — the list of forbidden strings is the list of
  suppliers, and a supplier that is not authorised has no entry.
- A real cloud smoke remains out of scope for LC-P2-01 (§1.3 of its task
  breakdown): it needs the owner's authorisation, a limit, and synthetic
  content that may be sent.
