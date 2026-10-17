"""What every material adapter produces, and the rules they all obey.

ADR-0008 lists nine constraints on ingestion. Three of them are about the
*extracted text* rather than the schema, and all three are properties of
this package rather than of the store:

    a character range resolves to exactly the characters that were quoted
    the page text is the author's words, with spaces
    unreadable input is recorded, never fabricated

The shared types live here so those properties are stated once. An adapter
that does not fit this shape is not an adapter.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import ModuleType
from typing import Protocol, runtime_checkable

from labcairn.sources.locators import SourceLocator
from labcairn.sources.source import SourceKind, SourceReadability

__all__ = [
    "Adapter",
    "ExtractedUnit",
    "ExtractionProblem",
    "ExtractionResult",
    "UnknownAdapterError",
    "adapter_for",
    "register",
]


class UnknownAdapterError(LookupError):
    """No adapter claims this kind of material.

    Not a silent empty result: LC-P1-08's acceptance requires that unreadable
    and unhandled stay distinct from "nothing was found", and a material with
    no adapter is the second case, not the first.
    """


@dataclass(frozen=True)
class ExtractedUnit:
    """One addressable piece of a material and the text at that address.

    ``text`` is a plain ``str`` **inside the pipeline** and only becomes
    :class:`~labcairn.security.untrusted.UntrustedText` at the boundary that
    hands it to a consumer. Wrapping at extraction would mean every internal
    step took a wrapper it cannot use, and the wrapper's guarantee is
    consumer-side anyway: ADR-0003 C6 says imported text is "carried in
    fields explicitly typed as untrusted content", and the field that matters
    is the one a consumer reaches.
    """

    locator: SourceLocator
    text: str


@dataclass(frozen=True)
class ExtractionProblem:
    """Something about the material a reader must be told, and no guessing about.

    ``detail`` is what a user sees. ``location`` is where in the material it
    applies, or ``None`` for a whole-file problem. This is the record that
    keeps "we could not look" distinct from "there was nothing there" --
    ADR-0004 A7, which ``SourceReadability`` also encodes at the file level.
    """

    code: str
    detail: str
    location: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Everything an adapter found, plus everything it could not.

    Both halves are required. An adapter that can only report success is
    indistinguishable from one that silently dropped a page, and the
    difference between those two is the whole point of this type.
    """

    units: tuple[ExtractedUnit, ...] = ()
    problems: tuple[ExtractionProblem, ...] = ()
    #: Set when the material is readable in principle but carries no text
    #: layer -- a scanned PDF. ``SourceReadability.UNREADABLE_NO_OCR`` is the
    #: file-level expression of the same fact; this is the adapter-level one,
    #: and both are set rather than either.
    readability: SourceReadability = SourceReadability.READABLE

    def __iter__(self) -> Iterator[ExtractedUnit]:
        return iter(self.units)


@runtime_checkable
class Adapter(Protocol):
    """One material format, and nothing else.

    An adapter knows how to turn bytes into addressable text. It does not
    hash, does not persist, does not touch the workspace, and never writes:
    the read-only boundary is ``SourceMaterial``'s, and an adapter that
    reached past it would make LC-P1-04's promise depend on every future
    adapter being careful.
    """

    kind: SourceKind

    def extract(self, data: bytes) -> ExtractionResult:
        """Extract from raw bytes. Must not raise on malformed input."""
        ...

    def libraries(self) -> Mapping[str, str]:
        """Library versions that affect this adapter's output.

        Fed into the extraction version, so a dependency upgrade changes the
        key. Empty for an adapter with no dependencies beyond the standard
        library -- which is the honest answer for text and CSV.
        """
        ...

    def source(self) -> ModuleType:
        """The module whose source defines this adapter's behaviour.

        The extraction version hashes it, so that editing an adapter changes
        every key it produces without anyone remembering to bump anything.
        """
        ...


@dataclass(frozen=True)
class _Registry:
    _adapters: dict[SourceKind, Adapter] = field(default_factory=dict)


_REGISTRY = _Registry()


def register[AdapterT: Adapter | type[Adapter]](adapter: AdapterT) -> AdapterT:
    """Register an adapter, and return it unchanged.

    Usable as a bare decorator on a class, which is how every adapter is
    written::

        @register
        class PlainTextAdapter: ...

    The **class is returned, not the instance**, because an adapter is
    sometimes the base of another: ``MarkdownAdapter`` subclasses
    ``PlainTextAdapter``, and a decorator that rebound that name to an
    instance would leave ``class MarkdownAdapter(PlainTextAdapter)`` trying
    to inherit from an object.

    A class is instantiated once for the registry; an already-built instance
    is taken as it is. Instantiating is what makes the bare decorator work
    at all -- storing the class would hand callers a type, and
    ``adapter.extract(data)`` would fail for want of ``self``.
    """
    instance = adapter() if isinstance(adapter, type) else adapter
    existing = _REGISTRY._adapters.get(instance.kind)
    if existing is not None and type(existing) is not type(instance):
        raise ValueError(
            f"{instance.kind.value!r} already has an adapter "
            f"({type(existing).__module__}.{type(existing).__qualname__}); "
            f"two adapters for one kind means one of them is unreachable."
        )
    _REGISTRY._adapters[instance.kind] = instance
    return adapter


def adapter_for(kind: SourceKind) -> Adapter:
    """The adapter for ``kind``, or a refusal that names what is missing."""
    try:
        return _REGISTRY._adapters[kind]
    except KeyError:
        raise UnknownAdapterError(
            f"no adapter is registered for {kind.value!r}; the material is recorded "
            f"and hashed, and no text is extracted from it. That is different from a "
            f"material that was read and contained nothing."
        ) from None


def registered_kinds() -> tuple[SourceKind, ...]:
    """Every kind with an adapter, for the inventory report."""
    return tuple(sorted(_REGISTRY._adapters, key=lambda k: k.value))
