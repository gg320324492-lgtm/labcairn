"""The fields each judgement part takes, and the ones a part does not.

**What this is for.** A judgement is the caller's own answer to one role, and
the role takes a fixed set of fields. That set was written down twice -- once
as the layer's dataclasses, once as the API's wire models, and a third time
implicitly in the CLI's own reader, which read the fields one by one and
dropped whatever it did not recognise. **Two spellings of one vocabulary is
how the two faces drifted:** the API's models forbid a field the role does
not take, and the CLI's reader accepted the same field and dropped it without
a word.

So the vocabulary has **one owner**, and it is the layer's dataclass. The
:func:`unknown_fields` helper below asks it what a part takes and reports
what a payload carries that the part does not, and every surface that reads
a judgement asks the same question.

**Why the dataclass owns it and not the wire model.** The judgement's fields
are a fact about the *role*: the layer's dataclass says so in as many words
("**The fields are the ones the role takes, and the role checks them**"), and
the role is what consumes the dataclass. The API's model is a spelling of
that dataclass for the wire, and a wire spelling that listed its own fields
would be a second place for the same answer to drift -- which is the mistake
this module exists to end. The layering agrees: the application layer is what
both the API and the CLI are built on, so a vocabulary owned by the wire layer
would make the CLI depend on the wire layer for a fact about a role.

**What it does not decide.** Which fields are *required* is a question the
wire model answers with a 422 and the CLI answers by letting the role refuse
an empty value. That difference is the roles' own business and it is not
settled here; this module only knows what a part *takes*.

**The nested claim is not here.** A guidance judgement carries claims, and a
claim carries its own fields, and the CLI's reader reads those one by one as
well. A claim with a field the role does not take is therefore dropped by the
CLI in exactly the way a part is -- and that hole is real, but it is a
separate claim about a separate shape, and widening this module to cover it
would make the module's answer true of a thing it does not describe.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from typing import Final

from labcairn.application.roles_run import (
    CritiqueJudgement,
    GuidanceJudgement,
    TrajectoryJudgement,
)

#: The three parts a judgement is made of, named as the API's body names them.
TRAJECTORY: Final[str] = "trajectory"
GUIDANCE: Final[str] = "guidance"
CRITIQUE: Final[str] = "critique"

#: The fields each part takes, read off the layer's dataclasses.
#:
#: **Read off, never written out.** The tuples are built from
#: :func:`dataclasses.fields`, so the list that decides what is refused is
#: the same list the role's own dataclass carries -- there is no second
#: spelling here to fall behind.
JUDGEMENT_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    TRAJECTORY: tuple(field.name for field in fields(TrajectoryJudgement)),
    GUIDANCE: tuple(field.name for field in fields(GuidanceJudgement)),
    CRITIQUE: tuple(field.name for field in fields(CritiqueJudgement)),
}


def fields_taken(part: str) -> tuple[str, ...]:
    """The fields the part takes, in the order the dataclass declares them."""
    return JUDGEMENT_FIELDS.get(part, ())


def unknown_fields(part: str, payload: Mapping[str, object]) -> tuple[str, ...]:
    """The names in ``payload`` that the part does not take.

    **The order is the payload's own**, so a caller is told about the fields
    in the order it wrote them.

    **A part this module does not know has no vocabulary**, so it has no
    unknown fields either: an unrecognised part name is a different
    question -- whether the part exists at all -- and answering it here would
    make this helper refuse a payload for a reason that has nothing to do
    with the fields in it.
    """
    taken = JUDGEMENT_FIELDS.get(part)
    if taken is None:
        return ()
    return tuple(name for name in payload if name not in taken)


__all__ = [
    "CRITIQUE",
    "GUIDANCE",
    "JUDGEMENT_FIELDS",
    "TRAJECTORY",
    "fields_taken",
    "unknown_fields",
]
