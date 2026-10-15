"""Strict scalar primitives shared by every contract.

These live in ``core`` rather than beside their first user because the rule they
encode is project-wide, not specific to sources: **a malformed payload is
rejected, never silently corrected.**

Pydantic validates in *lax* mode by default, and in lax mode ``"3"`` is a
perfectly good integer, ``3.0`` is a perfectly good integer, and ``True`` is a
perfectly good ``1``. For most fields that is convenient. For ``seq`` — which
ADR-0003 calls "the only order" — it means a value that was never an integer
becomes one without a word, and an event log orders itself by a number the
caller did not write.

The comment above this group used to claim every numeric field opted into
``strict=True`` while the runtime layer's eight numeric fields did not. A stated
rule that the code does not follow is worse than no rule, so the types are here,
the runtime layer uses them, and a test asserts the whole tree obeys.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import Field

#: An integer that must arrive as an integer. ``"3"``, ``3.0`` and ``True`` are
#: all refused.
type StrictInt = Annotated[int, Field(strict=True)]

#: A strictly-parsed integer >= 1. Used for ``seq``, which is 1-based.
type StrictPosInt = Annotated[int, Field(strict=True, ge=1)]

#: A strictly-parsed integer >= 0.
type StrictNonNegInt = Annotated[int, Field(strict=True, ge=0)]

#: A strictly-parsed float. An ``int`` is still accepted: Pydantic widens int to
#: float even under ``strict=True``, and refusing ``0`` where ``0.0`` is meant
#: would be pedantry rather than safety.
type StrictFloat = Annotated[float, Field(strict=True)]

#: A strictly-parsed float >= 0.
type StrictNonNegFloat = Annotated[float, Field(strict=True, ge=0.0)]

#: A strictly-parsed float > 0.
type StrictPosFloat = Annotated[float, Field(strict=True, gt=0.0)]

#: The minimum a non-negative int must exceed. Zero is legal for ``after_seq``
#: and ``material_hashes`` lengths; it is not legal for ``seq`` or ``attempt``.
ZERO: Final = 0
