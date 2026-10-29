"""The refusal vocabularies, closed against each other.

**What is under test.** LC-P2-06 T05: the layer's reason vocabulary, and
the two vocabularies under it — the consent machinery's and the intake
guards' — that the layer has to be able to name.

**Why a table and not a default.** A refusal that reaches a surface with a
reason nobody has a name for is a refusal a surface cannot render, and a
default would hide that: the layer would invent a label for somebody else's
refusal at the moment somebody needed to read it. **So the seam looks the
reason up**, and a reason with no row is a crash in the table rather than a
quiet substitution. `labcairn.application.analysis` settles the same
question for the run path, and this is that table's second instance.

**And the closure is the property, in both directions.** Every reason the
consent machinery and the intake guards can raise has a name in the layer,
**and** every name the layer holds for them is reached by one of those
reasons. The second direction is the one that catches drift: a member added
to the layer's vocabulary with no reason mapping to it is a name no refusal
can ever carry, and it is exactly the shape the intake's missing
`NO_GRANT` had taken.

**What breaks it:** a new reason in either vocabulary with no row here — the
refusal reaches a surface as an unmapped reason — or a row here that names
a reason the layer does not have, which would raise a member that does not
exist.
"""

from __future__ import annotations

import pytest

from labcairn.application.refusal import (
    CONSENT_REFUSALS,
    INTAKE_REFUSALS,
    ApplicationRefusal,
    consent_refusal_name,
    intake_refusal_name,
)
from labcairn.material.intake import IntakeRefusal
from labcairn.security.permissions import ConsentRefusal

pytestmark = pytest.mark.unit


def test_every_consent_refusal_has_a_layer_name() -> None:
    """The consent machinery's vocabulary and the layer's are closed.

    **Three checks, and the third is the one that catches drift.** The
    first says no reason is left unnamed; the second says the table has no
    row the vocabulary does not have; and the third says the layer's own
    consent names are **exactly** the ones this table reaches, so a name
    added to the layer with nothing mapping to it is caught here rather
    than by a reader looking for the refusal it was meant for.
    """
    unmapped = {reason for reason in ConsentRefusal if reason not in CONSENT_REFUSALS}
    assert not unmapped, (
        f"the consent machinery can refuse with {unmapped}, which the layer cannot name"
    )
    assert len(CONSENT_REFUSALS) == len(set(ConsentRefusal))
    invented = {
        layer_reason
        for layer_reason in CONSENT_REFUSALS.values()
        if layer_reason not in set(ApplicationRefusal)
    }
    assert not invented, f"the mapping names reasons the layer does not have: {invented}"

    named = {reason for reason in ApplicationRefusal if reason.name.startswith("CONSENT_")}
    assert named == set(CONSENT_REFUSALS.values()), (
        "the layer's consent names and the reasons that reach them differ: "
        f"{sorted(reason.value for reason in named ^ set(CONSENT_REFUSALS.values()))}"
    )


def test_every_intake_refusal_has_a_layer_name() -> None:
    """The intake guards' vocabulary and the layer's are closed.

    **And this one is the closure that caught a hole.** The guards refuse
    before they open, and the first thing they refuse with is *no grant* —
    which had no name in the layer at all, so a refusal that is the most
    important one to render was the one a surface could not name.
    """
    unmapped = {reason for reason in IntakeRefusal if reason not in INTAKE_REFUSALS}
    assert not unmapped, (
        f"the intake guards can refuse with {unmapped}, which the layer cannot name"
    )
    assert len(INTAKE_REFUSALS) == len(set(IntakeRefusal))
    invented = {
        layer_reason
        for layer_reason in INTAKE_REFUSALS.values()
        if layer_reason not in set(ApplicationRefusal)
    }
    assert not invented, f"the mapping names reasons the layer does not have: {invented}"

    named = {reason for reason in ApplicationRefusal if reason.name.startswith("INTAKE_")}
    assert named == set(INTAKE_REFUSALS.values()), (
        "the layer's intake names and the reasons that reach them differ: "
        f"{sorted(reason.value for reason in named ^ set(INTAKE_REFUSALS.values()))}"
    )


def test_the_names_line_up_with_the_reasons_they_name() -> None:
    """A reason and its name say the same thing.

    **A pair is right when the name is the reason's own word.** The
    consent machinery's `NO_GRANT` is the layer's `CONSENT_NO_GRANT`, and
    the intake's `NO_GRANT` is the layer's `INTAKE_NO_GRANT` — **two
    different refusals that happen to share a word**, and the layer
    distinguishes them because the module they came from is part of the
    name.
    """
    for consent_reason, name in CONSENT_REFUSALS.items():
        assert name.value == f"consent_{consent_reason.value}", (
            f"{consent_reason} is named {name.value!r} by the layer"
        )
    for intake_reason, name in INTAKE_REFUSALS.items():
        assert name.value == f"intake_{intake_reason.value}", (
            f"{intake_reason} is named {name.value!r} by the layer"
        )


def test_the_lookup_is_a_lookup_and_not_a_default() -> None:
    """The seam asks the table; it does not fall back.

    **A reason with no row must arrive as a failure.** A default would
    render every unmapped refusal as something true and unhelpful, and the
    reader would never learn that the table had a hole in it.
    """
    assert consent_refusal_name(ConsentRefusal.NO_GRANT) is ApplicationRefusal.CONSENT_NO_GRANT
    assert intake_refusal_name(IntakeRefusal.NO_GRANT) is ApplicationRefusal.INTAKE_NO_GRANT

    # And the two "no grant" refusals are **not** the same name: one is the
    # consent machinery's and one is the intake's, and a surface that drew
    # them alike would not tell a person which gate refused.
    assert (
        len(
            {
                ApplicationRefusal.CONSENT_NO_GRANT.value,
                ApplicationRefusal.INTAKE_NO_GRANT.value,
            }
        )
        == 2
    )
