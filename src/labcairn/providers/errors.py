"""Failure classification for the provider layer — the closed vocabulary, never raw text.

The shape is ADR-0002 §"LabCairn's own contracts" item 5, scoped to the slice
this work order owns. ``labcairn/runtime/operations.py`` is the intended home for
the persisted form and is owned by LC-P1-02/LC-P1-04, so this module defines the
*provider-layer* failures and nothing else: no ``OperationFailure``, no
``operation_id``, no state transitions. What it does provide is the part the
provider layer is actually responsible for — deciding, from a third-party
exception, which of a small fixed set of things went wrong, **and discarding the
third party's own words in the process**.

Why discarding matters here specifically
----------------------------------------
ADR-0002 records the upstream bug this is written against, and it is a privacy
bug before it is a classification bug::

    # openhands-sdk/tests/sdk/event/test_error_classification.py:44
    assert detail not in event.classification.model_dump_json()
    # ...parametrised over 14 triples including
    #   ("OpenAIError", "Incorrect API key provided", "auth")

A provider's 4xx body is attacker-adjacent text. It routinely echoes the
credential that was rejected (*"Incorrect API key provided: sk-ant-..."*), and an
OpenAI-compatible endpoint under the user's control may echo arbitrary text back.
Anything built from ``str(exc)`` is therefore assumed to be hostile until
scrubbed, and :func:`classify_exception` never puts it in the record at all — it
computes a digest of the *scrubbed* text and keeps only that.

The three properties this module guarantees, each with a test:

1. :attr:`ProviderFailure.detail_digest` is present and is a function of the
   scrubbed text, so it is stable for the same failure and reveals nothing.
2. :attr:`ProviderFailure.message` is written *here*, by LabCairn, from a fixed
   per-kind template. No third-party substring reaches it.
3. ``retryable`` is decided per kind, not per exception text — the mapping from
   HTTP status to kind is in :data:`_STATUS_KINDS` and nothing else is consulted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from labcairn.providers.redaction import Redactor

#: What the operator should do about it. Mirrors ADR-0002's ``UserAction``.
type UserAction = str

#: No action required; the caller may proceed.
ACTION_NONE: UserAction = "none"
#: The same call may be attempted again unchanged.
ACTION_RETRY: UserAction = "retry"
#: A ceiling, a credential or an endpoint setting has to change first.
ACTION_SETTINGS: UserAction = "settings"
#: A human decision is outstanding.
ACTION_AWAIT_APPROVAL: UserAction = "await_approval"


class FailureKind(StrEnum):
    """The provider layer's slice of ADR-0002's ``FailureKind``.

    Same wire vocabulary as the ADR so a persisted reason from this module and a
    persisted reason from ``labcairn.runtime`` do not need translating later.
    Members LC-P1-03 cannot produce are deliberately absent rather than stubbed:
    ``MODEL_ARGUMENT_INVALID`` / ``MODEL_OUTPUT_MALFORMED`` belong to the tool
    loop, ``POLICY_DENIED`` to LC-P1-04's policy layer, and ``OUT_OF_SCOPE`` to
    the stage allowlist. An enum member nothing can raise is a member that will
    eventually be raised by accident.
    """

    # --- decided before the request goes out ---
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    BUDGET_EXHAUSTED = "budget_exhausted"
    BUDGET_ENFORCEMENT_UNAVAILABLE = "budget_enforcement_unavailable"
    OUTBOUND_REFUSED = "outbound_refused"
    #: The caller cancelled; terminal, and nothing about it is the operator's fault.
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    # --- provider / transport ---
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_QUOTA = "provider_quota"
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    PROVIDER_TRANSIENT = "provider_transient"
    #: The reply arrived but was not a reply we could read.
    PROVIDER_MALFORMED_RESPONSE = "provider_malformed_response"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class _Classification:
    retryable: bool
    user_action: UserAction
    message: str


_CLASSIFICATION: Mapping[FailureKind, _Classification] = {
    FailureKind.CAPABILITY_UNAVAILABLE: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="The configured model did not confirm a capability this step requires.",
    ),
    FailureKind.BUDGET_EXHAUSTED: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="A per-run ceiling was reached; the run stopped before the next step.",
    ),
    FailureKind.BUDGET_ENFORCEMENT_UNAVAILABLE: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message=(
            "A per-run ceiling is set but the quantity it bounds could not be measured, "
            "so the ceiling cannot be enforced. LabCairn stopped rather than assume the "
            "ceiling was met."
        ),
    ),
    FailureKind.OUTBOUND_REFUSED: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="The request carried material the outbound disclosure policy does not permit.",
    ),
    FailureKind.CANCELLED: _Classification(
        retryable=False,
        user_action=ACTION_NONE,
        message="The run was cancelled.",
    ),
    FailureKind.TIMEOUT: _Classification(
        retryable=True,
        user_action=ACTION_RETRY,
        message="The provider did not answer within the configured timeout.",
    ),
    FailureKind.PROVIDER_AUTH: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="The provider rejected the credential.",
    ),
    FailureKind.PROVIDER_QUOTA: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="The provider reported the account or key as out of quota.",
    ),
    FailureKind.PROVIDER_RATE_LIMIT: _Classification(
        retryable=True,
        user_action=ACTION_RETRY,
        message="The provider asked this client to slow down.",
    ),
    FailureKind.PROVIDER_TRANSIENT: _Classification(
        retryable=True,
        user_action=ACTION_RETRY,
        message="The provider reported a transient failure.",
    ),
    FailureKind.PROVIDER_MALFORMED_RESPONSE: _Classification(
        retryable=False,
        user_action=ACTION_SETTINGS,
        message="The provider's reply was not in a shape LabCairn can read.",
    ),
    FailureKind.INTERNAL: _Classification(
        retryable=False,
        user_action=ACTION_NONE,
        message="LabCairn failed for a reason it did not anticipate.",
    ),
}

#: HTTP status -> kind. The only thing consulted to classify a transport error;
#: the response body never participates in the decision, which is precisely why
#: the body (which may echo the key) can be discarded instead of parsed.
_STATUS_KINDS: Mapping[int, FailureKind] = {
    400: FailureKind.PROVIDER_MALFORMED_RESPONSE,
    401: FailureKind.PROVIDER_AUTH,
    402: FailureKind.PROVIDER_QUOTA,
    403: FailureKind.PROVIDER_AUTH,
    404: FailureKind.PROVIDER_MALFORMED_RESPONSE,
    408: FailureKind.TIMEOUT,
    413: FailureKind.PROVIDER_MALFORMED_RESPONSE,
    422: FailureKind.PROVIDER_MALFORMED_RESPONSE,
    429: FailureKind.PROVIDER_RATE_LIMIT,
    500: FailureKind.PROVIDER_TRANSIENT,
    502: FailureKind.PROVIDER_TRANSIENT,
    503: FailureKind.PROVIDER_TRANSIENT,
    504: FailureKind.PROVIDER_TRANSIENT,
    529: FailureKind.PROVIDER_TRANSIENT,
}


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """What LabCairn persists or shows about a failed provider interaction.

    Four fields, all of them LabCairn-authored. There is no ``detail`` field and
    there will not be one: a field that can hold a provider's error text is a
    field a future caller will fill from ``str(exc)``, and the whole point of
    this module is that they cannot.
    """

    kind: FailureKind
    retryable: bool
    user_action: UserAction
    #: SHA-256 over the *scrubbed* upstream text. Stable for the same failure,
    #: empty when there was no upstream text at all, and not reversible into one.
    detail_digest: str

    @classmethod
    def of(cls, kind: FailureKind, *, detail_digest: str = "") -> ProviderFailure:
        facts = _CLASSIFICATION[kind]
        return cls(
            kind=kind,
            retryable=facts.retryable,
            user_action=facts.user_action,
            detail_digest=detail_digest,
        )

    @property
    def message(self) -> str:
        """The human sentence. A template from :data:`_CLASSIFICATION`; never upstream text."""
        return _CLASSIFICATION[self.kind].message

    def to_wire(self) -> Mapping[str, object]:
        return {
            "kind": self.kind.value,
            "retryable": self.retryable,
            "user_action": self.user_action,
            "detail_digest": self.detail_digest,
            "message": self.message,
        }


class ProviderError(Exception):
    """Base for everything this layer raises. Carries the persistable failure.

    ``hint`` is an optional operator-facing sentence *LabCairn* writes, for the
    cases where the classification alone does not say what to do — "call this
    from an async context" rather than "internal error". It is not the
    exception's own message; nothing from a third party reaches it.
    """

    def __init__(self, failure: ProviderFailure, *, hint: str = "") -> None:
        super().__init__(failure.message if not hint else f"{failure.message} ({hint})")
        self.failure = failure
        self.hint = hint

    @property
    def kind(self) -> FailureKind:
        return self.failure.kind


class UnsupportedCapabilityError(ProviderError):
    """A capability the step needs was not confirmed. Decided *before* the request.

    Never followed by a downgrade to prose-parsed tool calls — ADR-0002 §A4
    refuses ``NonNativeToolCallingMixin.post_response_prompt_mock``
    (``non_native_fc.py:68``) precisely because it makes free text the carrier of
    a side effect's identity.
    """

    def __init__(self, capability: str, reason: str) -> None:
        super().__init__(ProviderFailure.of(FailureKind.CAPABILITY_UNAVAILABLE))
        self.capability = capability
        #: LabCairn-authored: either one of our fixed evidence strings or the
        #: exception's *class name*. Never the exception's message.
        self.reason = reason


class BudgetExceededError(ProviderError):
    """A known quantity passed a ceiling. Terminal and non-retryable.

    Matches OpenHands' ``MaxBudgetExhausted -> QUOTA, retryable=False``
    (``error_classification.py:71-72``) and diverges from pydantic-ai, whose
    single ``UsageLimitExceeded`` carries no classification at all.
    """

    def __init__(self, ceiling: str, *, observed: float) -> None:
        super().__init__(ProviderFailure.of(FailureKind.BUDGET_EXHAUSTED))
        self.ceiling = ceiling
        self.observed = observed


class BudgetEnforcementUnavailableError(ProviderError):
    """A ceiling is set but the quantity it bounds is not measurable. **Fail closed.**

    This is the ADR-0002 line, and the reason it exists::

        # pydantic-ai, usage.py:604-612 — check_cost warns and returns
        # openhands, local_conversation.py:735-737 — spent < max_budget_per_run
        #     where an unmeasured spent is 0.0, so the budget never trips

    Raising is the whole behaviour. There is deliberately no
    ``BudgetEnforcementUnavailableError.warn_and_proceed`` variant, because that is
    the two upstream bugs wearing a LabCairn name.
    """

    def __init__(self, ceiling: str, *, reason: str) -> None:
        super().__init__(ProviderFailure.of(FailureKind.BUDGET_ENFORCEMENT_UNAVAILABLE))
        self.ceiling = ceiling
        self.reason = reason


class ProviderCancelledError(ProviderError):
    def __init__(self, reason: str) -> None:
        super().__init__(ProviderFailure.of(FailureKind.CANCELLED))
        self.reason = reason


class ProviderTimeoutError(ProviderError):
    def __init__(self, seconds: float) -> None:
        super().__init__(ProviderFailure.of(FailureKind.TIMEOUT))
        self.seconds = seconds


class OutboundRefusedError(ProviderError):
    def __init__(self, reason: str) -> None:
        super().__init__(ProviderFailure.of(FailureKind.OUTBOUND_REFUSED))
        self.reason = reason


class ProviderMalformedResponseError(ProviderError):
    def __init__(self, *, detail_digest: str = "") -> None:
        super().__init__(
            ProviderFailure.of(FailureKind.PROVIDER_MALFORMED_RESPONSE, detail_digest=detail_digest)
        )


#: The lowest and highest HTTP status this table claims. Declared so a test can
#: assert the table grew no catch-all entry (``test_status_table_has_no_catch_all``).
_STATUS_TABLE_SPAN = (400, 599)


def classify_exception(exc: BaseException, *, redactor: Redactor) -> ProviderFailure:
    """Turn a third-party exception into a :class:`ProviderFailure`.

    The upstream message is read exactly once, to compute a digest of the
    *scrubbed* form, and is then dropped. Nothing downstream can reach it: the
    return type has no field that holds arbitrary text.
    """
    detail_digest = redactor.digest(_safe_text(exc))
    status = _status_of(exc)
    kind = _STATUS_KINDS.get(status, FailureKind.PROVIDER_TRANSIENT) if status else _name_kind(exc)
    return ProviderFailure.of(kind, detail_digest=detail_digest)


_NAME_KINDS: Mapping[str, FailureKind] = {
    "Timeout": FailureKind.TIMEOUT,
    "CancelledError": FailureKind.CANCELLED,
    "UserError": FailureKind.CAPABILITY_UNAVAILABLE,
}


def _name_kind(exc: BaseException) -> FailureKind:
    return _NAME_KINDS.get(type(exc).__name__, FailureKind.PROVIDER_TRANSIENT)


def _status_of(exc: BaseException) -> int | None:
    """Pull an HTTP status off a third-party exception without importing that library.

    duck-typed on purpose: ``httpx.HTTPStatusError``,
    ``pydantic_ai.exceptions.ModelHTTPError`` and a raw
    ``openai.APIStatusError`` all expose the number somewhere, and none of them
    is a subclass of a common base we could name without taking the dependency.
    Returns ``None`` when there is no status, which routes the exception through
    :func:`_name_kind` instead.
    """
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) and not isinstance(status, bool) else None


def _safe_text(exc: BaseException) -> str:
    """The most descriptive text an exception offers, without unbounded nesting.

    ``httpx.HTTPStatusError.__str__`` already embeds the response body, so this
    is where an echoed credential arrives. It is scrubbed by the caller's
    redactor immediately afterwards; nothing else in the process sees it.
    """
    parts = [str(exc)]
    cause = exc.__cause__
    depth = 0
    while cause is not None and depth < 3:
        parts.append(str(cause))
        cause = cause.__cause__
        depth += 1
    return " | ".join(parts)
