"""LC-P1-10's analysis layer: vetted operators over tabular source material.

This package is where a number that was **computed** lives, as distinct from a
number that was **read**. The distinction is the whole point of the work
order, and it is a difference of provenance rather than of magnitude:

* a number read out of a cell is a statement about that cell, and the ledger
  checks it (C3 re-reads the cell and compares);
* a number computed from many cells is a statement about a **derivation**, and
  what makes it checkable is not a check but a **manifest** -- the inputs, the
  selection, the operator and its version, the parameters, and the output.

Nothing in this package executes code that was written at run time. The
operators are registered statically, with closed argument models, and a chart
is drawn from a declarative recipe. That is not a style preference: it is
what makes ``analysis.run`` a capability that can be granted at all.
"""

from __future__ import annotations

__all__: list[str] = []
