"""Model providers, budgets and capability detection — LC-P1-03.

What is here
------------
The provider layer ADR-0002 §A1 rejected stock pydantic-ai objects for: real
adapters, ceilings that actually bind, and capability detection that **asks the
endpoint** instead of looking up a model name.

============================  ====================================================
Module                        Responsibility
============================  ====================================================
:mod:`~labcairn.providers.adapter`          gated ``ModelProvider``; the order of
                                            the four pre-flight checks
:mod:`~labcairn.providers.probe`             the probes that issue real requests
:mod:`~labcairn.providers.capabilities`      the fail-closed capability set
:mod:`~labcairn.providers.budget`            ceilings, and fail-closed enforcement
:mod:`~labcairn.providers.ledger`            tri-state spend accumulation
:mod:`~labcairn.providers.usage_capture`     recovering the raw ``usage`` block
:mod:`~labcairn.providers.cancel`            cooperative cancel + deadline
:mod:`~labcairn.providers.credentials`       env/config credentials that cannot print
:mod:`~labcairn.providers.redaction`         secret scrubbing
:mod:`~labcairn.providers.errors`            the closed failure vocabulary
:mod:`~labcairn.providers.pydantic_models`   OpenAI / Anthropic / compatible wiring
============================  ====================================================

The three properties everything else is arranged around
------------------------------------------------------
1. **Capabilities are probed, not declared.** Nothing in this package reads
   ``model.profile``. ADR-0002 measured pydantic-ai at ``9ac853bb``: there is no
   ``supported_tools()`` anywhere, ``ModelProfile`` is a static ``TypedDict``
   resolved *by model name*, and an OpenAI-compatible endpoint serving
   ``gpt-4-turbo-mimic`` matches nothing, inherits the OpenAI family default of
   ``supports_tools: True``, and is reported tool-capable without a request having
   been made. See :mod:`~labcairn.providers.probe`.

2. **Unknown never becomes 0.** Every quantity is a
   :class:`~labcairn.core.providers.usage.UsageValue`. A ceiling whose quantity is
   unmeasurable raises :class:`~labcairn.providers.errors.BudgetEnforcementUnavailableError`
   rather than passing, because ADR-0002 measured both upstreams failing exactly
   that way — pydantic-ai warns and proceeds (``usage.py:604-612``), OpenHands
   compares an unknown ``accumulated_cost`` of ``0.0`` against its ceiling and
   never trips (``local_conversation.py:735-737``).

3. **Credentials and source excerpts never reach a log.** Third-party error text
   is classified locally and discarded; only a digest of the *scrubbed* text is
   kept, following OpenHands' ``ErrorClassification`` test
   (``test_error_classification.py:44``, which asserts ``detail not in
   model_dump_json()`` for fourteen triples including one that echoes a key).
   See :mod:`~labcairn.providers.errors` and
   :mod:`~labcairn.providers.redaction`.

What is deliberately not here
----------------------------
* **Persisting probe results to SQLite.** ADR-0002 specifies a table; SQLite
  tables are LC-P1-05's. :class:`~labcairn.providers.probe.ProbeCache` is a
  Protocol with an in-memory implementation and the same
  ``(endpoint_fingerprint, model, protocol)`` key, so LC-P1-05 adds persistence
  without touching a probe.
* **The price table.** No provider reports a price, so cost is
  ``Unknown(UNPRICED)`` until a LabCairn-owned table exists, and
  ``max_cost_usd`` fails closed in the meantime. ADR-0002 §Risks requires exactly
  this.
* **The persisted ``OperationFailure``.** ADR-0002 puts it in
  ``labcairn/runtime/operations.py``, owned by LC-P1-02/LC-P1-04. This package
  defines the provider-layer :class:`~labcairn.providers.errors.ProviderFailure`
  and stops there.
* **Any tool execution.** Analysis tools and the ``allow / ask / deny`` policy are
  LC-P1-04. Nothing here dispatches a tool call.
"""

from __future__ import annotations

from labcairn.providers.adapter import (
    PHASE_1_OUTBOUND_POLICY,
    ExchangeRecord,
    OutboundDisclosure,
    PydanticAiModelProvider,
    UpstreamModel,
    prompt_digest,
    translate_response,
)
from labcairn.providers.budget import BudgetDecision, BudgetGuard, RunBudget, preflight_check
from labcairn.providers.cancel import CancellationToken
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.credentials import (
    Credential,
    MissingCredentialError,
    Protocol,
    ProviderSettings,
    UnknownProviderError,
    load_credential,
    load_providers_config,
)
from labcairn.providers.errors import (
    BudgetEnforcementUnavailableError,
    BudgetExceededError,
    FailureKind,
    OutboundRefusedError,
    ProviderCancelledError,
    ProviderError,
    ProviderFailure,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
    UnsupportedCapabilityError,
    classify_exception,
)
from labcairn.providers.ledger import (
    COST_SCALE,
    LedgerSnapshot,
    RunLedger,
    micros_to_usd,
    usage_reporting_is_usable,
    usd_to_micros,
)
from labcairn.providers.probe import (
    CachedCapabilityProbe,
    CapabilityProbe,
    InMemoryProbeCache,
    ProbeCache,
    ProbeRecord,
    PydanticAiProbe,
    endpoint_fingerprint,
)
from labcairn.providers.redaction import Redactor
from labcairn.providers.usage_capture import (
    HttpxUsageSniffer,
    NullUsageCapture,
    RecordingUsageCapture,
    UsageCapture,
)

__all__ = [
    "ALL_CAPABILITIES",
    "COST_SCALE",
    "PHASE_1_OUTBOUND_POLICY",
    "BudgetDecision",
    "BudgetEnforcementUnavailableError",
    "BudgetExceededError",
    "BudgetGuard",
    "CachedCapabilityProbe",
    "CancellationToken",
    "Capability",
    "CapabilityOutcome",
    "CapabilityProbe",
    "Credential",
    "ExchangeRecord",
    "FailureKind",
    "HttpxUsageSniffer",
    "InMemoryProbeCache",
    "LedgerSnapshot",
    "MissingCredentialError",
    "NullUsageCapture",
    "OutboundDisclosure",
    "OutboundRefusedError",
    "ProbeCache",
    "ProbeRecord",
    "Protocol",
    "ProviderCancelledError",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderFailure",
    "ProviderMalformedResponseError",
    "ProviderSettings",
    "ProviderTimeoutError",
    "PydanticAiModelProvider",
    "PydanticAiProbe",
    "RecordingUsageCapture",
    "Redactor",
    "RunBudget",
    "RunLedger",
    "UnknownProviderError",
    "UnsupportedCapabilityError",
    "UpstreamModel",
    "UsageCapture",
    "classify_exception",
    "endpoint_fingerprint",
    "load_credential",
    "load_providers_config",
    "micros_to_usd",
    "preflight_check",
    "prompt_digest",
    "translate_response",
    "usage_reporting_is_usable",
    "usd_to_micros",
]
