"""Building the three real providers: OpenAI, Anthropic, and an OpenAI-compatible endpoint.

Why this module is thin
-----------------------
ADR-0002 §A3 rejects hand-rolling the transport for Phase 1 — *"re-implements,
with no upstream test corpus behind it: streaming tool-call assembly, incremental
JSON-schema repair, retry-after handling, and token accounting across three
protocol dialects."* Pydantic AI already has all of that, tested. So the adapters
are a configuration of it, not a reimplementation, and this file is mostly
wiring:

* **OpenAI** — ``OpenAIChatModel`` over ``OpenAIProvider`` at the default base URL.
* **Anthropic** — ``AnthropicModel`` over ``AnthropicProvider``.
* **OpenAI-compatible** — the *same* ``OpenAIChatModel`` over an
  ``OpenAIProvider(base_url=...)`` the operator supplied. There is no third code
  path, and that is the point: the configuration ADR-0002 is most worried about
  is not a special case in LabCairn's code, it is a different URL.

Two things are attached to every provider that a bare pydantic-ai model does not have.

**The usage sniffer.** :class:`~labcairn.providers.usage_capture.HttpxUsageSniffer`
wraps the HTTP transport so the raw ``usage`` block survives. Without it every
token count is ``Unknown`` and every token ceiling refuses to run — which is the
correct default, but means a real provider is unusable until this is wired.
:func:`build_http_client` is where it goes in.

**The outbound policy.** Every outbound request built here goes to a host the
operator configured, and may carry retrieved material. What may be sent is
declared by :data:`~labcairn.providers.adapter.PHASE_1_OUTBOUND_POLICY`; this
module adds nothing to it, which is why there is no prompt-assembly code here to
review. A future work order that adds retrieval to a prompt has to change that
policy explicitly.

Dependencies, stated plainly
----------------------------
``pydantic-ai`` is declared in ``pyproject.toml``. ``httpx`` and the ``openai`` /
``anthropic`` SDKs are **not** — they arrive transitively through pydantic-ai,
whose public ``OpenAIProvider.__init__`` takes an ``httpx.AsyncClient`` and whose
``OpenAIChatModel`` takes an ``AsyncOpenAI``. That is a legitimate import for
this work but an undeclared one, and ``pyproject.toml`` is not this work order's
to edit. Flagged for the dependency owner: these should become explicit.

Smoke testing
-------------
No function here opens a socket by itself beyond what the model object does, and
**nothing in this repository may call :func:`build_model` with a real credential
during CI**. :func:`smoke_test` exists for an operator with authorisation to
spend money; it is not run by any test in ``tests/``, and the real-provider smoke
required by the work order's acceptance line has **not been executed** — see the
handoff report.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from labcairn.providers.credentials import (
    Credential,
    Protocol,
    ProviderSettings,
    load_credential,
)
from labcairn.providers.usage_capture import HttpxUsageSniffer

#: Header name per protocol. Kept here so a future protocol is one row rather
#: than a conditional in three places.
_AUTH_HEADER_NAMES: Mapping[Protocol, str] = {
    Protocol.OPENAI: "Authorization",
    Protocol.OPENAI_COMPATIBLE: "Authorization",
    Protocol.ANTHROPIC: "x-api-key",
}


def auth_header_name(protocol: Protocol) -> str:
    return _AUTH_HEADER_NAMES[protocol]


def make_sniffer() -> HttpxUsageSniffer:
    """A sniffer over a real httpx transport.

    Created once and then **shared**: the same object becomes the client's
    transport and the probe's ``usage_capture``. Two independent captures would
    let the run report a ``Known`` token count the probe could not confirm, which
    is precisely the disagreement this layer exists to prevent.
    """
    import httpx

    return HttpxUsageSniffer(httpx.AsyncHTTPTransport())


def build_http_client(
    settings: ProviderSettings,
    *,
    sniffer: HttpxUsageSniffer | None = None,
) -> Any:
    """An ``httpx.AsyncClient``, optionally routed through a usage sniffer.

    Omitting ``sniffer`` gives a plain client, and a plain client means every
    token count is ``Unknown`` and every token ceiling refuses to run. The failure
    mode is safe, so the wiring is left to the caller — but
    :func:`smoke_test` and any production wiring must pass one.
    """
    import httpx

    transport: Any = sniffer if sniffer is not None else httpx.AsyncHTTPTransport()
    return httpx.AsyncClient(transport=transport, timeout=settings.timeout_s)


def build_model(
    settings: ProviderSettings,
    *,
    credential: Credential | None = None,
    environ: Mapping[str, str] | None = None,
    http_client: Any = None,
) -> Any:
    """Construct the pydantic-ai model for ``settings``.

    ``credential`` may be passed explicitly (so a caller that already holds one
    does not read the environment twice) or is resolved from the settings. Either
    way the secret reaches the provider SDK through exactly one expression, and
    that expression is here — which is what
    ``test_reveal_call_sites_are_exhaustive`` checks.

    ``http_client`` is where the usage sniffer goes. Both provider factories take
    one, and passing a client whose transport is an
    :class:`~labcairn.providers.usage_capture.HttpxUsageSniffer` is the only way
    a real provider's token counts survive to LabCairn: pydantic-ai's own
    ``ModelResponse.usage`` cannot represent "not reported"
    (``test_usage_limits.py:1166``; see :mod:`labcairn.providers.usage_capture`).
    Without it every run is ``Unknown`` and every token ceiling refuses to start.
    """
    secret = credential if credential is not None else load_credential(settings, environ=environ)
    key = secret.reveal()

    if settings.protocol is Protocol.ANTHROPIC:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            settings.model,
            provider=AnthropicProvider(
                api_key=key,
                base_url=settings.effective_base_url,
                http_client=http_client,
            ),
        )

    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    if settings.protocol is Protocol.OPENAI_COMPATIBLE:
        return OpenAIChatModel(
            settings.model,
            provider=OpenAIProvider(
                base_url=settings.base_url, api_key=key, http_client=http_client
            ),
        )
    return OpenAIChatModel(
        settings.model,
        provider=OpenAIProvider(api_key=key, http_client=http_client),
    )


def smoke_test(
    settings: ProviderSettings,
    *,
    environ: Mapping[str, str] | None = None,
    credential: Credential | None = None,
) -> Mapping[str, object]:
    """One live capability probe against a real endpoint. **Costs money.**

    Not called by any test in this repository, and not to be called without the
    project owner's authorisation and a credential they supplied for the purpose.
    It exists so the work order's *"real smoke on at least one provider"* has a
    defined, repeatable procedure rather than a shell history.

    The result is deliberately a plain mapping rather than a
    :class:`~labcairn.providers.probe.ProbeRecord`: a smoke result gets pasted
    into an issue, and the record's ``to_wire`` form is what to paste.

    The client is wired through :func:`build_http_client`, so ``USAGE_REPORTING``
    is a real observation of this endpoint's response bodies rather than an
    artefact of how the smoke was assembled. That matters: a smoke that could
    only ever report ``usage_reporting: unsupported`` would tell the project
    owner nothing about their endpoint.

    What the result will **not** contain is a cost figure. Phase 1 has no price
    table, so the honest output is ``usage_reporting: ok`` and no money — and a
    ``max_cost_usd`` ceiling would fail closed against it.
    """
    from datetime import UTC, datetime

    from labcairn.providers.capabilities import ALL_CAPABILITIES
    from labcairn.providers.probe import PydanticAiProbe, endpoint_fingerprint

    sniffer = make_sniffer()
    model = build_model(
        settings,
        credential=credential,
        environ=environ,
        http_client=build_http_client(settings, sniffer=sniffer),
    )
    probe = PydanticAiProbe(model=model, usage_capture=sniffer, clock=lambda: datetime.now(tz=UTC))
    record = probe.probe(
        capabilities=frozenset(ALL_CAPABILITIES),
        endpoint_fingerprint=endpoint_fingerprint(
            base_url=settings.sanitised_base_url(),
            model=settings.model,
            protocol=settings.protocol_label,
        ),
        protocol=settings.protocol_label,
    )
    return record.to_wire()
