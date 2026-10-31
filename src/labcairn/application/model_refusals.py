"""The model-call path's own reasons for saying no.

**The enumeration lives apart from the raiser** for the reason the chain's
and the guidance memory's do: :mod:`labcairn.application.refusal` imports
this module to name the refusals it renders, and a module the application
layer imports cannot import the application layer back. The function that
*raises* them is :mod:`labcairn.application.model_request`.
"""

from __future__ import annotations

from enum import StrEnum


class ModelRefusal(StrEnum):
    """Why the model-call path said no.

    **Each one names what was wrong**, because a refusal that says only
    "no" is a refusal nobody can act on. They are the path's own reasons,
    and :data:`labcairn.application.refusal.MODEL_REFUSALS` gives each one
    the name a surface renders. The two schema refusals are distinguished
    because their remedies differ: never probed is remedied by probing,
    which is cheap and changes the decision for free; probed-and-failed
    is remedied by a different provider or a different output shape.
    """

    #: No capability probe has run for the provider a schema request was
    #: addressed to. **The request is refused rather than sent on the
    #: chance the schema comes back** — ADR-0002 treats an unprobed
    #: capability exactly like an unsupported one, and so does this path.
    SCHEMA_UNPROBED = "schema_unprobed"
    #: The probe ran and licensed no structured output — neither the
    #: protocol's own channel nor the prompt-described fallback. **A
    #: provider that cannot produce a schema's output is blocked from
    #: that request**, rather than being asked to try.
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    #: The call came back with nothing in the schema's shape. **An empty
    #: result is not a result** — a refusal here, not an answer to hand
    #: on.
    ANSWER_EMPTY = "answer_empty"
    #: The answer is not decodable into the schema it was asked for. The
    #: refusal's message names what was expected, and **illegal output is
    #: never silently turned into evidence** — ADR-0016 keeps a model's
    #: say-so out of the record until it is verifiable.
    ANSWER_UNDECODABLE = "answer_undecodable"
