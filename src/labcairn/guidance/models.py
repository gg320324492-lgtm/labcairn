"""The guidance memory's own value types: a rule, and the cases against it.

**Why these live apart from the lifecycle.** :mod:`labcairn.guidance.rules` is
the lifecycle, and the lifecycle reads and writes through the application
layer — and the application layer answers with a :class:`GuidanceRule`. So the
layer and the lifecycle would import each other, and the import would run in a
circle. The value types therefore sit **below both**, in a module that
imports nothing from the application layer.

That is the arrangement the rest of the repository already uses for the same
reason: :mod:`labcairn.papers.versions` holds the version graph's contracts and
:mod:`labcairn.evidence.record` holds the evidence record's, and both are
imported by the layer's operations and by the domain's own checks.

**And the types are the memory's own, not the store's.** A rule is a rule
whichever row holds it: the row is where the memory keeps it, and a reader
wants the rule — with its sources and its cases — rather than a row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RuleCounterexample:
    """The case where a rule does not hold, as the memory serves it."""

    statement: str
    #: The chain material the counterexample came from, when it has one.
    issue_key: str | None
    recorded_by: str
    recorded_at: datetime


@dataclass(frozen=True)
class GuidanceRule:
    """A mentor's rule as the memory holds it, with its sources and its cases.

    **The counterexamples travel with the rule, not beside it.** The
    work order's acceptance says a counterexample stops the rule being
    served unconditionally, and the mechanism starts here: a caller that
    has a rule has its cases against it, because they came back in the
    same read.
    """

    rule_id: str
    version: int
    issue_type: str
    statement: str
    context: str
    scope: str
    example: str
    state: str
    proposed_by: str
    proposed_at: datetime
    confirmed_by: str | None
    confirmed_at: datetime | None
    resolution_reason: str | None
    #: The chain material the rule was learned from, by the chain's own
    #: key. **At least one: a rule without a source is not a rule.**
    sources: tuple[str, ...]
    #: The cases against the rule. **Possibly empty, never optional** —
    #: an empty tuple says the memory holds none, not that it did not look.
    counterexamples: tuple[RuleCounterexample, ...]


__all__ = ["GuidanceRule", "RuleCounterexample"]
