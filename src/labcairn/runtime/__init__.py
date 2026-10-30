"""Runtime contracts: Task, Run, Stage, Operation, Approval, Checkpoint, events.

**And the trajectory's payload schemas.** :mod:`labcairn.runtime.trajectory`
registers the four payload schemas of ADR-0017's feedback chain, and a
schema that is registered only where the writer was imported is a schema the
reader does not have — the defect ADR-0007's registry exists to prevent.
Importing a module of a package imports the package first, so pulling the
trajectory in here is what puts those schemas in front of every reader of
:mod:`labcairn.runtime.event`, and the reader validates every stored event
against them.
"""

from labcairn.runtime import trajectory as _trajectory  # noqa: F401 - registration

__all__ = ["trajectory"]
