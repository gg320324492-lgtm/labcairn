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
    #: File-level readability, mirroring ``Source.readability``. **No adapter
    #: in this package sets it yet** -- the three standard-library adapters
    #: either extract or report why they cannot, and a material with no text
    #: layer is a PDF fact, which the PDF adapter will be the one to express.
    #:
    #: An earlier version of this comment claimed "both are set rather than
    #: either", which was a description of behaviour that did not exist. The
    #: field stays because the PDF adapter needs it; until one sets it, it is
    #: a declared seam and not a promise.
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

    **Two rules, learned the expensive way.** Four rounds of adversarial
    review found five fabrication paths in three adapters, and both rules
    below are what stopped them. They are written here so the PDF adapter
    inherits them rather than re-deriving them from another five findings.

    **One: ask whether the material determines the answer.**

    - *Determined* -- encodings, delimiters, line terminators. Exactly one
      reading is correct. If it cannot be recovered, refuse; if it can, take
      it and disclose that it was inferred. Every adapter in this package is
      in this class, and refusal was right every time.
    - *Underdetermined* -- PDF reading order, whitespace reconstruction.
      Two or more readings are equally consistent with the evidence, and
      ADR-0008 **measured** that no threshold separates them: word gaps and
      column gutters sit on one continuum with every integer in gutter
      territory populated. Refusal there refuses the dominant case --
      LaTeX- and Word-produced PDFs, which is what this product ingests.
      The obligation is a **disclosure the reader can check against the
      page**, not a refusal.

    The distinction is not "fallback versus refusal". Every fabrication
    found so far came from a *determined* question that was answered by a
    guess, and every fix came from answering it properly.

    **Two: find the signal in the bytes, and refuse when it fires.** Every
    one of the five had a candidate signal present that would have said so
    -- NULs, control characters, raggedness, per-candidate column counts.
    Not one was fixed by being more careful with the guess. The thing to
    design against is not "a heuristic fabricated" but **"a heuristic whose
    wrongness the reader cannot see"**, and that is why every disclosure
    here carries the evidence for its own conclusion.
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

    def source_modules(self) -> tuple[ModuleType, ...]:
        """Modules inside this package whose source can affect this adapter.

        **The adapter's own module first, then the ones it calls into.** The
        second part is not optional: `CsvAdapter` gets its decoding from
        `text.py`, so hashing only the adapter's own file left a real
        behaviour change -- edit `decode_text` and the CSV output changes
        while the version does not, which is exactly the key lying that
        ADR-0009 forbids.

        **Scope, stated narrowly because it is narrower than it sounds.** This
        covers `labcairn.material`, not the whole package: the locators in
        `labcairn.sources` and the validators in `sources.primitives` are
        outside the digest. A change to those alters which cells are accepted
        with the version fixed -- the round-one blank-header crash came from
        exactly that unhashed layer. Covering them properly means hashing the
        transitive import graph rather than a hand-listed set, which is a
        larger change than this protocol carries. Until then the guarantee
        is: *within this package*, behaviour changes move the version.

        Return `sys.modules[__name__]`, never ``__import__(__name__)``: with
        no ``fromlist`` the latter returns the *top-level package*, so three
        adapters in three modules all hashed ``labcairn/__init__.py`` and
        shared one version. That bug survived because every version test used
        a synthetic module in ``tmp_path`` and none called this on a real
        adapter.
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
    # Checked here rather than left to the first extract() call: an object
    # without `extract` registers fine and then fails deep inside an ingest,
    # which is the worst place to discover the adapter was never one.
    for required in ("extract", "libraries", "source_modules"):
        if not callable(getattr(instance, required, None)):
            raise TypeError(
                f"{type(instance).__name__} is not an Adapter: {required!r} is "
                f"missing or not callable."
            )

    existing = _REGISTRY._adapters.get(instance.kind)
    if existing is not None:
        same = type(existing) is type(instance)
        # A reload produces a *new* class object with the same qualified name.
        # That is the same adapter, not a rival one, and refusing it makes
        # importlib.reload -- and any pytest run using importlib import mode --
        # crash at import time for no reason.
        reloaded = (
            f"{type(existing).__module__}.{type(existing).__qualname__}"
            == f"{type(instance).__module__}.{type(instance).__qualname__}"
        )
        if not (same or reloaded):
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
