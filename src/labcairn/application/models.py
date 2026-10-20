"""The base every result model uses.

The layer returns **data**, never formatted text: a CLI's ``--json`` output and
an API's response body are the same model, rendered the same way. That is
``docs/ARCHITECTURE.md``'s rule that formatting must never be load-bearing for
a machine-readable command, and it is why these are pydantic models rather
than dataclasses: a model has one JSON spelling, and the API's schema export
(T07) has a single source to export from.

Frozen, because a result is a statement about a moment. A caller that could
mutate one in place would be holding a claim about the task's state that the
store never made.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Result(BaseModel):
    """The base for every result the application layer returns.

    ``extra="forbid"`` for the same reason the persisted contracts have it: a
    result carrying a field this build does not know is a newer writer or a
    typo, and both deserve to be loud rather than dropped on the way to a
    surface.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


__all__ = ["Result"]
