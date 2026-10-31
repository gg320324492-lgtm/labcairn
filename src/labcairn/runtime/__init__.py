"""Runtime contracts: Task, Run, Stage, Operation, Approval, Checkpoint, events.

**And the payload schemas.** :mod:`labcairn.runtime.trajectory` registers the
four payload schemas of ADR-0017's feedback chain, and
:mod:`labcairn.runtime.model_exchange` registers the model's exchange
payload. A schema that is registered only where the writer was imported is a
schema the reader does not have — the defect ADR-0007's registry exists to
prevent. Importing a module of a package imports the package first, so
pulling both in here is what puts those schemas in front of every reader of
:mod:`labcairn.runtime.event`, and the reader validates every stored event
against them.

**The model's schema was missing here until 2026-10-31.** The exchange
event was written by the model path, which imports its own module, so the
schema was registered in the writer's process and **absent in every process
that only reads** — the worst shape a defect can take: the writer's tests
are green and the stored event is unchecked when it comes back. The
witness is ``tests/test_event_payload_vocabulary.py``, and it asks about
this event type the way it asks about the recovery layer's.
"""

from __future__ import annotations

from labcairn.runtime import model_exchange as _model_exchange  # noqa: F401 - registration
from labcairn.runtime import trajectory as _trajectory  # noqa: F401 - registration

__all__ = ["model_exchange", "trajectory"]
