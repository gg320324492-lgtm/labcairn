"""Types that exist so imported text can never be confused with an instruction.

ADR-0003 §C6 is the anti-injection contract, and it is deliberately
**structural, not textual**. §C6.1 states the goal: *no parameter carries
document text, excerpt text, or retrieval output* — the decision must be
unreachable from imported content *by construction*. A rule that says "do not
parse policy out of documents" is a rule a future contributor breaks by accident
and nothing catches it. A rule that says "the decision function's parameters
have these types" is checked by the type checker on every change.

So imported material is wrapped, at the moment it is ingested, in
:class:`UntrustedText`. It is not a ``str`` — it does not subclass ``str``, does
not compare equal to one, and cannot be passed where a :class:`~labcairn.security.
paths.ResourceKey` is expected. Converting it back requires an explicit,
visible ``.value`` access at the one place that genuinely wants characters.

The counterpart is §C6.3: *there is no policy-in-document parser, by
construction rather than by convention.* Nothing in this package takes a
:class:`UntrustedText` and returns a rule, a capability, an effect or a path.
The only consumer of the untrusted payload anywhere in the product is a provider
adapter, which sends it and gets a reply — it never governs anything.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final, get_args

from pydantic import AfterValidator, Field, StringConstraints

#: Upper bound on a single ingested chunk. Not a security control in itself —
#: the real limit is on what may be *sent*, which is the approval digest's job —
#: but an unbounded text field is how a 400 MB PDF excerpt becomes an approval
#: digest nobody can reason about.
MAX_UNTRUSTED_CHARS: Final = 2_000_000


class UntrustedOrigin(StrEnum):
    """Where an :class:`UntrustedText` came from.

    Recorded so an event can say *which* imported material was involved in a
    decision, without the decision ever reading it. A provenance label is not a
    permission input.
    """

    SOURCE_DOCUMENT = "source_document"
    RETRIEVAL_HIT = "retrieval_hit"
    EXTRACTED_CELL = "extracted_cell"
    MODEL_OUTPUT = "model_output"
    USER_NOTE = "user_note"


@dataclass(frozen=True, slots=True)
class UntrustedText:
    """Imported material, wrapped so it cannot masquerade as anything else.

    Deliberately **not** a ``str`` subclass. A subclass would compare equal to
    the plain string, hash like it, and be accepted by every parameter annotated
    ``str`` — which would make the wrapper decorative. As a distinct frozen
    dataclass, passing document text to something expecting an ordinary string
    is a type error, not a silent success.
    """

    value: str
    origin: UntrustedOrigin
    #: Stable locator into the source material (page, cell, row). A *reference*
    #: to the material, never a copy of it, and never parsed for meaning.
    locator: str | None = None

    def __post_init__(self) -> None:
        if len(self.value) > MAX_UNTRUSTED_CHARS:
            msg = (
                f"untrusted text of {len(self.value)} characters exceeds the "
                f"{MAX_UNTRUSTED_CHARS} limit"
            )
            raise ValueError(msg)

    def __str__(self) -> str:
        """Render for a log line. Never parse the result.

        Injected control characters are escaped rather than stripped: stripping
        would be silent correction of the payload, and the escape is visible to
        whoever reads the log, which is the point.
        """
        escaped = "".join(
            f"\\x{ord(c):02x}" if unicodedata.category(c) in {"Cc", "Cf"} else c for c in self.value
        )
        return f"<{self.origin.value}:{len(self.value)} chars>" + (
            f" {escaped[:200]}" if escaped else ""
        )


def _limit_untrusted(value: str) -> str:
    if len(value) > MAX_UNTRUSTED_CHARS:
        msg = f"untrusted text exceeds {MAX_UNTRUSTED_CHARS} characters"
        raise ValueError(msg)
    return value


#: A field that carries imported text. The annotation is what an argument model
#: uses when the value legitimately *is* document content — a retrieval query
#: built from source text, an excerpt bound for a provider. Using it marks the
#: field as carrying untrusted material in its own type.
UntrustedField = Annotated[
    str, AfterValidator(_limit_untrusted), Field(max_length=MAX_UNTRUSTED_CHARS)
]


def carries_untrusted_text(field_or_annotation: object) -> bool:
    """Whether a field or annotation is marked as carrying imported text.

    Exists because the marker is not findable by reading the annotation's string
    form. Pydantic moves ``Annotated[...]`` metadata into ``FieldInfo.metadata``,
    and a tuple element like ``tuple[UntrustedField, ...]`` keeps the marker
    nested several levels down — so ``"Untrusted" in str(annotation)`` misses
    exactly the cases it is meant to catch, silently.

    Walks the structure instead, comparing **function identity** against
    :func:`_limit_untrusted`, and accepts either a Pydantic ``FieldInfo`` or a
    raw annotation so a caller does not have to know which it has.

    Used by the anti-injection tests, and available to any audit that needs to
    answer "which inputs of this capability are imported material?" without
    depending on how Pydantic happens to store the annotation.
    """
    if field_or_annotation is None:
        return False
    if field_or_annotation is _limit_untrusted:
        return True
    # An AfterValidator (or any constraint object) wraps the function as .func.
    if getattr(field_or_annotation, "func", None) is _limit_untrusted:
        return True
    metadata = getattr(field_or_annotation, "__metadata__", None)
    if metadata is not None and carries_untrusted_text(metadata):
        return True
    # A Pydantic FieldInfo: check both places the marker can end up.
    field_metadata = getattr(field_or_annotation, "metadata", None)
    if field_metadata and carries_untrusted_text(field_metadata):
        return True
    field_annotation = getattr(field_or_annotation, "annotation", None)
    if field_annotation is not None and carries_untrusted_text(field_annotation):
        return True
    # A plain list of constraints (what ``FieldInfo.metadata`` holds). get_args()
    # unpacks typing constructs but not list *values*, so this has to be walked
    # explicitly or the metadata case is silently missed.
    if isinstance(field_or_annotation, list | tuple | set | frozenset):
        return any(carries_untrusted_text(item) for item in field_or_annotation)
    return any(carries_untrusted_text(arg) for arg in get_args(field_or_annotation))


#: A stable, non-semantic identifier. Pattern-constrained so that a paragraph of
#: injected prose cannot be stored where an id belongs.
StableId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
