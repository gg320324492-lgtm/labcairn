"""The registered rule catalog.

ADR-0004 Contract 2 makes a `checker_id` a precondition of one transition:
``extracted → verified_by_rule`` needs *"a ``VerificationRecord`` with ``check``
in {C1, C2, C3}, ``outcome == pass``, from a ``checker_id`` present in the
registered rule catalog"*. The catalog is the set of ids a machine-written
verification may come from, and it is what separates a rule's pass from a
person's word.

**Code, not a table.** A registry table would let a rule be added at runtime,
and Phase 1 has nobody to add one: the checks are the rules, they live in
``labcairn.evidence.checks``, and a rule id that is not the id of a shipped
check has no implementation behind it. So the catalog is built *from* the check
modules rather than spelled out here, and that is the point of doing it that
way: one id has one spelling. A frozenset written out in this file would be a
second spelling of a closed set, which is exactly what ADR-0009's canonical
``locator_key`` was written to stop.

The cost is that a rule cannot be registered at runtime, and the benefit is that
a ``verified_by_rule`` record can only ever carry the id of a check that
actually exists.

**A user attestation is not in the catalog, and must not be.** ``checker_id`` is
free text on a :class:`~labcairn.evidence.record.VerificationRecord` because
``extracted → user_attested`` is logged by a *person*, whose id is not a rule id.
:func:`is_registered_rule` is therefore asked only about entries that claim to
be a rule's verdict, and the two endpoints of the state machine stay
distinguishable: a machine pass names a rule, an attestation names a human.
"""

from __future__ import annotations

from typing import Final

from labcairn.evidence.checks.c1 import C1_CHECKER_ID
from labcairn.evidence.checks.c2 import C2_CHECKER_ID
from labcairn.evidence.checks.c3 import C3_CHECKER_ID

__all__ = ["RULE_CHECKER_IDS", "is_registered_rule"]

#: The ids a machine-written verification may come from.
#:
#: C4's id is deliberately absent. C4's only verdict is ``not_checked`` --
#: ADR-0004 I2 makes it the permanent terminal for interpretation -- so it can
#: never carry a pass, and a catalog containing it would suggest it could.
RULE_CHECKER_IDS: Final[frozenset[str]] = frozenset({C1_CHECKER_ID, C2_CHECKER_ID, C3_CHECKER_ID})


def is_registered_rule(checker_id: str) -> bool:
    """Is *checker_id* the id of a rule this build actually implements?"""
    return checker_id in RULE_CHECKER_IDS
