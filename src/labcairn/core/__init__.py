"""Core contracts for the LabCairn research layer.

``core`` holds config, provider adapters and typed model/tool output, per
``docs/ARCHITECTURE.md`` "Proposed package layout". It is created here, in T02,
only so the packaging recursive root is real and the wheel can be proven to ship
subpackages (LC-P1-01 amendment C-7).

Nothing belongs in this package yet that is not owned by a work order:

* ``providers/`` — LC-P1-01 T08/T09 via amendment C-3, for the FakeProvider
  and the ``Known`` / ``Unknown`` / ``UsageValue`` / ``UnknownReason`` types in
  ``providers/usage.py``. Placed under ``core/`` because ARCHITECTURE.md
  defines ``core/`` as "config, provider adapters, typed model/tool output".
* capability probes, budget ceilings, cancel/timeout — LC-P1-03.
* ``runtime/``, ``db/``, ``api/``, ``cli/`` — LC-P1-02 onwards.

Those directories are deliberately **not** pre-created: an empty package is a
claim that something was designed there, and none of them has been.
"""

from __future__ import annotations
