"""Per-run ceilings, and the rule that an unenforceable ceiling halts the run.

The failure this is written against
-----------------------------------
ADR-0002 §A1, quoting pydantic-ai ``usage.py:604-612``::

    def _warn_if_cost_unavailable(self, usage):
        warnings.warn(...)  # and returns


    def check_cost(self, usage):
        if usage.cost is not None:  # <- only compares when measurable
            ...

and OpenHands ``local_conversation.py:735-737``::

    if spent < self.max_budget_per_run:  # spent came from
        ...  # accumulated_cost: float = 0.0

Both reach "the ceiling is not being enforced" from opposite directions: one
warns and continues, the other treats the unmeasured spend as free. Either way
**a ceiling the operator set does nothing, permanently, with at most one
warning.** ADR-0002 §Risks calls that "the LC-P1-03 failure".

So the rule here has exactly one sentence:

    **A ceiling that is set and cannot be evaluated raises
    :class:`~labcairn.providers.errors.BudgetEnforcementUnavailableError`.**

There is no ``warn_and_continue`` overload, no ``strict=False``, and no
"degrade to a warning" constructor argument. The most tempting softening —
*only fail closed when the operator explicitly asked for the ceiling* — is
already how it works, because every ceiling is explicit: the difference from
upstream is that upstream's token ceilings were not fail-closed even when
explicit, because ``UsageBase.input_tokens: int = 0``
(``test_usage_limits.py:1166``, *"zero is not coerced to None"*).

Precedence between verdicts
---------------------------
:meth:`BudgetGuard.evaluate` returns one of three verdicts and there is an
order, because "we are over" and "we cannot tell" are not equally informative:

``EXCEEDED``
    A ceiling was compared and the measured value is past it. Decisive, so it
    wins even when another ceiling is unevaluable — the run is over either way.
``UNDECIDABLE``
    Every ceiling that could be evaluated was satisfied, and at least one could
    not be. Fail closed.
``ALLOW``
    Every ceiling was evaluated and satisfied.

Pre-flight, not post-hoc
------------------------
:meth:`BudgetGuard.require` is called **before** a request is built as well as
after it completes. ADR-0002 §OpenHands observation 13 and pydantic-ai's
``check_before_request`` (``usage.py:568``) agree: a ceiling checked only
afterwards bounds nothing, because the overshoot has already been paid for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from labcairn.core.providers.usage import Known, Unknown, UsageValue, require_known
from labcairn.providers.capabilities import (
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.errors import BudgetEnforcementUnavailableError, BudgetExceededError
from labcairn.providers.ledger import (
    LedgerSnapshot,
    usage_reporting_is_usable,
    usd_to_micros,
)


class BudgetDecision(StrEnum):
    """What the guard concluded. Three values, and the third is the important one."""

    ALLOW = "allow"
    EXCEEDED = "exceeded"
    #: At least one ceiling is set and the quantity it bounds is not measurable.
    UNDECIDABLE = "undecidable"


@dataclass(frozen=True, slots=True)
class RunBudget:
    """Per-run ceilings. Every field optional; ``None`` means unbounded.

    A deviation from ADR-0002 §"RunBudget", reported: the ADR's sketch declares
    all six ceilings as required fields with no defaults, but its own comment on
    ``max_total_tokens`` says ``None = unbounded``. Those cannot both hold. All
    optional is taken, because it is the reading that composes: a caller who
    wants only a wall-clock ceiling should not have to invent values for five
    other ceilings, and inventing them is how a limit gets set to a number nobody
    chose.

    Ceilings are **effort limits**, not correctness limits: exceeding one stops
    the run cleanly (ADR-0002 §OpenHands obs 13 — at most one step of overshoot).
    Nothing here decides whether an outcome is *right*.
    """

    #: Attempts, not successes. A tool that fails in a retry loop still costs.
    max_tool_calls: int | None = None
    #: LabCairn-issued calls only. ``provider_attempts`` is recorded but not
    #: bounded — see :mod:`labcairn.providers.ledger` on why the two differ.
    max_model_requests: int | None = None
    #: ``Known(n)`` for a real ceiling. ``Unknown`` as a *ceiling* is refused by
    #: :meth:`__post_init__`: a ceiling nobody can measure is not a ceiling.
    max_total_tokens: UsageValue | None = None
    max_cost_usd: Decimal | None = None
    max_wall_clock_s: float | None = None
    max_tool_call_seconds: float | None = None
    #: ADR-0002's "probe ≠ production" mitigation, enforced at request-build
    #: time rather than trusted to the probe: passing a probe with a trivial
    #: schema does not mean a 20-parameter schema will work.
    max_tool_arg_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        for name in ("max_tool_calls", "max_model_requests", "max_tool_arg_bytes"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative int or None, got {value!r}")
        for name in ("max_wall_clock_s", "max_tool_call_seconds"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative or None, got {value!r}")
        if isinstance(self.max_total_tokens, Unknown):
            raise ValueError(
                "max_total_tokens must be a measured ceiling (Known) or None; an Unknown "
                "ceiling is not a ceiling, and accepting one would make every run "
                "undecidable by construction"
            )
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError(
                f"max_cost_usd must be non-negative or None, got {self.max_cost_usd!r}"
            )

    @classmethod
    def unbounded(cls) -> RunBudget:
        """No ceilings at all.

        Explicit and named so "this run is unbounded" is a decision visible in a
        diff, rather than six ``None``s that look like an unfinished constructor
        call.
        """
        return cls()

    @property
    def is_unbounded(self) -> bool:
        return all(
            getattr(self, name) is None
            for name in (
                "max_tool_calls",
                "max_model_requests",
                "max_total_tokens",
                "max_cost_usd",
                "max_wall_clock_s",
                "max_tool_call_seconds",
            )
        )

    def to_wire(self) -> dict[str, object]:
        return {
            "max_tool_calls": self.max_tool_calls,
            "max_model_requests": self.max_model_requests,
            "max_total_tokens": self.max_total_tokens.to_wire() if self.max_total_tokens else None,
            "max_cost_usd": str(self.max_cost_usd) if self.max_cost_usd is not None else None,
            "max_wall_clock_s": self.max_wall_clock_s,
            "max_tool_call_seconds": self.max_tool_call_seconds,
            "max_tool_arg_bytes": self.max_tool_arg_bytes,
        }


#: A ceiling that was violated (with the measured value that violated it), or a
#: ceiling that could not be checked at all. ``observed`` is ``None`` in the
#: second case — never ``0``, because a finding about an unmeasurable quantity
#: that carries a zero is precisely the shape of the bug this module exists to
#: prevent.
@dataclass(frozen=True, slots=True)
class _Finding:
    ceiling: str
    observed: float | None
    reason: str


class BudgetGuard:
    """Evaluates :class:`RunBudget` against a :class:`LedgerSnapshot`. No I/O.

    Held per run, constructed once with the capabilities from the run's probe so
    that ``USAGE_REPORTING`` can be consulted. The capability can also be set
    later (``set_capabilities``) for a run whose probe completes after the guard
    was built; either way the default when it is unknown is "not usable", which
    fails a token ceiling closed.
    """

    __slots__ = ("_budget", "_capabilities")

    def __init__(
        self,
        budget: RunBudget,
        *,
        capabilities: ProviderCapabilities | None = None,
    ) -> None:
        self._budget = budget
        self._capabilities = capabilities

    @property
    def budget(self) -> RunBudget:
        return self._budget

    def set_capabilities(self, capabilities: ProviderCapabilities | None) -> None:
        self._capabilities = capabilities

    def evaluate(self, ledger: LedgerSnapshot) -> BudgetDecision:
        """The pure verdict. Never raises, never touches I/O."""
        exceeded = self._exceeded_by(ledger)
        if exceeded is not None:
            return BudgetDecision.EXCEEDED
        if self._undecidable_in(ledger) is not None:
            return BudgetDecision.UNDECIDABLE
        return BudgetDecision.ALLOW

    def require(self, ledger: LedgerSnapshot, *, pending_requests: int = 0) -> None:
        """Raise unless every set ceiling was both evaluable and satisfied.

        Three outcomes, in the order they are checked:

        * :class:`~labcairn.providers.errors.BudgetExceededError` — a measured value
          is past a ceiling. Terminal, non-retryable, ``user_action="settings"``,
          mirroring OpenHands' ``MaxBudgetExhausted -> QUOTA`` (``error_classification.py:71-72``).
        * :class:`~labcairn.providers.errors.BudgetEnforcementUnavailableError` — a
          ceiling is set and its quantity is not measurable. Also terminal, and
          also ``"settings"``: the operator can fix it by removing the ceiling or
          by choosing a priced endpoint.
        * ``None`` — proceed.

        The capability gate runs here too, not only in the adapter, and that is
        deliberate. A fresh ledger has measured nothing, so
        :meth:`evaluate` alone would report ``ALLOW`` for a run that can never
        enforce its token ceiling against an endpoint that does not report usage
        — and the first request would already have been paid for. ADR-0002 is
        explicit: *"the run halts with ``BudgetEnforcementUnavailable`` before
        issuing the request."* Putting the check inside ``require`` means every
        pre-flight gets it, including
        :func:`preflight_check`, rather than only the paths that remembered to.

        :meth:`evaluate` deliberately does **not** include it: that method answers
        "is this run over?", and mixing in "was it ever boundable?" would make one
        function answer two questions with one three-valued return.
        """
        exceeded = self._exceeded_by(ledger, pending_requests=pending_requests)
        if exceeded is not None and exceeded.observed is not None:
            raise BudgetExceededError(exceeded.ceiling, observed=exceeded.observed)
        self.require_capability_for_ceilings(
            self._capabilities if self._capabilities is not None else ledger.capabilities
        )
        undecidable = self._undecidable_in(ledger)
        if undecidable is not None:
            raise BudgetEnforcementUnavailableError(undecidable.ceiling, reason=undecidable.reason)

    def _exceeded_by(self, ledger: LedgerSnapshot, *, pending_requests: int = 0) -> _Finding | None:
        budget = self._budget

        # `pending_requests` is how many calls the caller is about to issue. A
        # pre-flight passes 1, so `max_model_requests=1` means *at most one
        # request* rather than *one is allowed and the second is caught
        # afterwards*. The post-flight check passes 0 and reports only what has
        # already happened.
        projected = ledger.labcairn_requests + pending_requests
        if budget.max_model_requests is not None and projected > budget.max_model_requests:
            return _Finding(
                "max_model_requests",
                projected,
                "more LabCairn-issued requests than the ceiling allows",
            )

        if budget.max_tool_calls is not None and ledger.tool_call_attempts > budget.max_tool_calls:
            return _Finding(
                "max_tool_calls",
                ledger.tool_call_attempts,
                "more tool-call attempts than the ceiling allows",
            )

        if budget.max_wall_clock_s is not None and ledger.elapsed_s > budget.max_wall_clock_s:
            return _Finding(
                "max_wall_clock_s", round(ledger.elapsed_s, 6), "wall clock past the ceiling"
            )

        if budget.max_total_tokens is not None:
            total = ledger.total_tokens
            if isinstance(total, Known):
                ceiling = require_known(budget.max_total_tokens)
                if total.value > ceiling:
                    return _Finding(
                        "max_total_tokens", total.value, "measured total tokens past the ceiling"
                    )

        if budget.max_cost_usd is not None:
            spend = ledger.cost_micros
            if isinstance(spend, Known) and spend.value > usd_to_micros(budget.max_cost_usd):
                return _Finding("max_cost_usd", spend.value, "measured spend past the ceiling")

        return None

    def _undecidable_in(self, ledger: LedgerSnapshot) -> _Finding | None:
        """The first set ceiling whose quantity is not measurable, or ``None``.

        Each arm is written as "the ceiling is set" AND "the value is Unknown" —
        never "the value is falsy" and never "the value is missing from a
        mapping", because both of those read a measured zero as an absence.
        """
        budget = self._budget
        capabilities = self._capabilities if self._capabilities is not None else ledger.capabilities

        if budget.max_total_tokens is not None and isinstance(ledger.total_tokens, Unknown):
            reason = ledger.total_tokens.reason.value
            if not usage_reporting_is_usable(capabilities):
                reason = f"usage reporting unverified; {reason}"
            return _Finding("max_total_tokens", None, reason)

        if budget.max_cost_usd is not None and isinstance(ledger.cost_micros, Unknown):
            return _Finding("max_cost_usd", None, ledger.cost_micros.reason.value)

        return None

    def require_capability_for_ceilings(self, capabilities: ProviderCapabilities | None) -> None:
        """Refuse to start a run whose ceilings it cannot enforce.

        Called from :meth:`require`, before the first request. This is ADR-0002's
        ``test_usage_reporting_capability_unverified_blocks_token_ceiling`` —
        *"the run halts with ``BudgetEnforcementUnavailableError`` before issuing
        the request"*.

        ``capabilities=None`` means no probe has ever run here, which is
        ``UNVERIFIED`` — not a licence to proceed. A caller that has genuinely not
        probed, holding a token ceiling, has not established that the ceiling can
        be checked; that is the fail-closed answer and it matches what the
        adapter's own capability gate already does for the other capabilities.

        Only ``max_total_tokens`` is gated, and only because a cost ceiling can be
        checked without the endpoint's help (a LabCairn price table supplies the
        rate) while a token count cannot — no provider reports a price, and no
        amount of local arithmetic invents one.
        """
        if self._budget.max_total_tokens is None:
            return
        outcome = (
            CapabilityOutcome.UNVERIFIED
            if capabilities is None
            else capabilities.outcome_for(Capability.USAGE_REPORTING)
        )
        if outcome.usable:
            return
        raise BudgetEnforcementUnavailableError(
            "max_total_tokens",
            reason=(
                "a token ceiling is configured but this endpoint has not demonstrated "
                f"it reports usage ({outcome.value})"
            ),
        )


def preflight_check(budget: RunBudget, ledger: LedgerSnapshot) -> None:
    """Raise unless every set ceiling is both evaluable and satisfied.

    Takes the budget rather than a guard because a one-shot pre-flight has no
    reason to hold capabilities separately — :meth:`BudgetGuard.require` reads
    them off the snapshot, and a snapshot that has none means "unverified",
    which is the fail-closed answer.
    """
    BudgetGuard(budget, capabilities=ledger.capabilities).require(ledger)
