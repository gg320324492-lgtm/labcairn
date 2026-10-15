"""Capability detection that issues a request, replacing the name-lookup.

The bug this replaces
--------------------
ADR-0002 §A1, from reading pydantic-ai at ``9ac853bb``::

    ModelProfile  profiles/__init__.py:55   TypedDict of *static booleans*
    supports_tools                           :63
    'supports_tools': True                   :360   <- per-family default
    profiles/google.py:260                   supports_tools=not is_image_model
    models/__init__.py:490                   class Model:  no supported_tools()
    repo-wide grep 'supported_tools'         1 hit, ui/_web/api.py:174

So there is no probe anywhere upstream. A `ModelProfile` is looked up **by model
name**, and an OpenAI-compatible endpoint serving ``gpt-4-turbo-mimic`` matches
nothing, falls through to the OpenAI family default, and is reported as
tool-capable without a single request having been made. OpenHands is the mirror
image — a single ``native_tool_calling: bool`` (``llm/llm.py:547``) that is
declared, not asked.

What this module does instead
-----------------------------
:class:`ProviderCapabilities` is built from :class:`~labcairn.providers.probe.ProbeRecord`,
and a probe record only exists if requests were sent. The three properties that
make the difference testable:

1. :meth:`ProviderCapabilities.require` raises for anything **absent** from
   ``supports``. There is no "probably", no default-True, no family fallback.
2. :meth:`ProviderCapabilities.require_all` reports the *first* missing
   capability and its recorded reason, so a caller halts a stage with a
   user-visible explanation rather than a bare ``KeyError``.
3. :class:`CapabilityOutcome` keeps ``UNVERIFIED`` and ``UNSUPPORTED``
   distinguishable in a report while giving them **identical** enforcement. That
   is ADR-0002 §4 mirroring OpenHands' ``SecurityRisk.UNKNOWN`` being
   un-orderable by construction (``risk.py:7-8``, ``:88-90``) — the uncertainty
   is preserved for the human and denied for the machine.

The negative space is enforced by a type: ``unsupported_reason`` is built only by
the two constructors, both of which fill it for **every** capability absent from
``supports``. There is no public way to build one with a silent gap, so a
capability cannot be quietly unsupported *and* unexplained.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from labcairn.providers.errors import UnsupportedCapabilityError


class Capability(StrEnum):
    """What a model endpoint can be asked to do, each verified by a real request.

    Wire values are frozen: a probe record persists them and a report renders
    them, so renaming one is a data migration, not a refactor.
    """

    #: Emit a well-formed tool call whose arguments validate against the schema.
    TOOL_CALLS = "tool_calls"
    #: Honour a JSON schema supplied through the protocol's own structured-output
    #: channel, returning data with no prose around it.
    STRUCTURED_OUTPUT_NATIVE = "structured_output_native"
    #: Honour a schema described in the prompt instead. **Always probed**, because
    #: this is the only fallback for a model without native support — and ADR-0002
    #: §A4 is precisely why that fallback must never extend to tool calls.
    STRUCTURED_OUTPUT_PROMPTED = "structured_output_prompted"
    #: Return a ``usage`` block at all. Without it, a token ceiling is unenforceable.
    USAGE_REPORTING = "usage_reporting"


#: Every capability, in probe order. ``USAGE_REPORTING`` is derived from the
#: others rather than probed on its own (ADR-0002's table: *"included in the
#: above"*), so it is deliberately last.
ALL_CAPABILITIES: Final[tuple[Capability, ...]] = (
    Capability.TOOL_CALLS,
    Capability.STRUCTURED_OUTPUT_NATIVE,
    Capability.STRUCTURED_OUTPUT_PROMPTED,
    Capability.USAGE_REPORTING,
)


class CapabilityOutcome(StrEnum):
    """The four answers, from ADR-0002 §4.

    Note what is missing: there is no ``MAYBE`` and no ``ASSUMED_SUPPORTED``.
    An endpoint that was never asked is ``UNVERIFIED``, and ``UNVERIFIED`` is
    treated exactly like ``UNSUPPORTED`` by :meth:`ProviderCapabilities.require`.
    """

    #: A real request was sent and it did the thing.
    OK = "ok"
    #: A real request was sent and it did not do the thing.
    UNSUPPORTED = "unsupported"
    #: No probe, or the probe itself failed. Same enforcement as ``UNSUPPORTED``.
    UNVERIFIED = "unverified"
    #: Policy said no, so no probe was run and no request was made.
    REFUSED = "refused"

    @property
    def usable(self) -> bool:
        """The only question a caller should be asking before starting a stage."""
        return self is CapabilityOutcome.OK

    @property
    def enforcement_class(self) -> str:
        """``"usable"`` or ``"blocked"`` — how the value is treated, not how it arose.

        Collapses ``OK`` against everything else. Kept as a property rather than
        an equality test at each call site because ``outcome in {UNSUPPORTED,
        UNVERIFIED}`` is the exact expression that eventually grows a third
        branch the day somebody adds an outcome.
        """
        return "usable" if self.usable else "blocked"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """What was actually observed from ``(endpoint, model, protocol)``.

    Frozen and closed. Build one with :meth:`from_outcomes` or
    :meth:`unverified`; both fill ``unsupported_reason`` for every capability
    missing from ``supports``, so the "required for every capability NOT in
    supports" requirement ADR-0002 states cannot be forgotten.
    """

    #: The endpoint fingerprint the result was measured against. Not the endpoint
    #: string itself — see :func:`~labcairn.providers.probe.endpoint_fingerprint`.
    endpoint_fingerprint: str
    model: str
    protocol: str
    outcomes: Mapping[Capability, CapabilityOutcome]
    #: LabCairn-authored one-liners explaining each absence. Never upstream text.
    unsupported_reason: Mapping[Capability, str]

    @classmethod
    def from_outcomes(
        cls,
        *,
        endpoint_fingerprint: str,
        model: str,
        protocol: str,
        outcomes: Mapping[Capability, CapabilityOutcome],
        unsupported_reason: Mapping[Capability, str],
    ) -> ProviderCapabilities:
        """Build from a probe, filling in any missing reason.

        An absent reason is a *LabCairn* bug (the probe forgot to say why), so it
        is filled with a fixed string rather than dropped — a report that says
        "unsupported: unprobed" is honest, and a report that says "unsupported:
        " is a dangling sentence.
        """
        complete: dict[Capability, str] = {}
        for capability in ALL_CAPABILITIES:
            outcome = outcomes.get(capability, CapabilityOutcome.UNVERIFIED)
            if outcome.usable:
                continue
            complete[capability] = unsupported_reason.get(capability, _default_reason(outcome))
        return cls(
            endpoint_fingerprint=endpoint_fingerprint,
            model=model,
            protocol=protocol,
            outcomes=dict(outcomes),
            unsupported_reason=complete,
        )

    @classmethod
    def unverified(
        cls,
        *,
        endpoint_fingerprint: str,
        model: str,
        protocol: str,
        reason: str = "no probe record for this endpoint, model and protocol",
    ) -> ProviderCapabilities:
        """No probe has ever run here. Everything blocked, loudly.

        This is the state a model is in between configuration and its first
        probe, and it is the state ADR-0002 requires to be **not usable** —
        ``test_capability_unverified_behaves_as_unsupported`` is this
        constructor.
        """
        outcomes = dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.UNVERIFIED)
        return cls.from_outcomes(
            endpoint_fingerprint=endpoint_fingerprint,
            model=model,
            protocol=protocol,
            outcomes=outcomes,
            unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, reason),
        )

    def outcome_for(self, capability: Capability) -> CapabilityOutcome:
        return self.outcomes.get(capability, CapabilityOutcome.UNVERIFIED)

    @property
    def supports(self) -> frozenset[Capability]:
        return frozenset(c for c in ALL_CAPABILITIES if self.outcome_for(c).usable)

    @property
    def missing(self) -> tuple[Capability, ...]:
        """Every capability that is blocked, in declaration order."""
        return tuple(c for c in ALL_CAPABILITIES if not self.outcome_for(c).usable)

    def require(self, capability: Capability) -> None:
        """Raise :class:`UnsupportedCapabilityError` unless ``capability`` was observed.

        The single gate. Note that it consults ``outcomes``, never a profile and
        never a default — a capability absent from the mapping is ``UNVERIFIED``
        and therefore raises.
        """
        outcome = self.outcome_for(capability)
        if outcome.usable:
            return
        raise UnsupportedCapabilityError(
            capability.value,
            self.unsupported_reason.get(capability, _default_reason(outcome)),
        )

    def require_all(self, capabilities: Iterable[Capability]) -> None:
        """Require several, reporting the first that is missing.

        Ordered by :data:`ALL_CAPABILITIES` rather than by the caller's argument
        order, so "the reason the user is shown" is the same reason on every
        machine running the same version.
        """
        wanted = frozenset(capabilities)
        for capability in ALL_CAPABILITIES:
            if capability in wanted:
                self.require(capability)

    def to_wire(self) -> Mapping[str, object]:
        """Render for a persisted probe record. Contains no secret and no endpoint URL."""
        return {
            "endpoint_fingerprint": self.endpoint_fingerprint,
            "model": self.model,
            "protocol": self.protocol,
            "outcomes": {c.value: o.value for c, o in sorted(self.outcomes.items())},
            "unsupported_reason": {c.value: r for c, r in sorted(self.unsupported_reason.items())},
        }


def _default_reason(outcome: CapabilityOutcome) -> str:
    if outcome is CapabilityOutcome.REFUSED:
        return "policy refused to probe this capability"
    if outcome is CapabilityOutcome.UNSUPPORTED:
        return "probe reported the capability absent, without a recorded reason"
    return "no probe record for this endpoint, model and protocol"
