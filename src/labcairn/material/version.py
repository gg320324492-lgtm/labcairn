"""How the extraction version is derived, mechanically rather than by memory.

ADR-0009 keys extracted text on ``(source_content_sha256,
extraction_version, locator)`` and says of the version:

    If ``extraction_version`` is not bumped when behaviour actually changes,
    the key lies. It is *specified* to be derived from something mechanical
    rather than a constant somebody remembers to bump.

A constant is not mechanical, even a carefully maintained one: it encodes
the author's belief about when behaviour changed, and nothing checks that
belief. A library version is mechanical for the library but says nothing
about *our* code, which is where extraction behaviour actually lives — the
reading order, the whitespace reconstruction and the column segmentation are
all ours, not pdfplumber's.

So the version hashes **the adapter's own source**. Change a line of
extraction code and every key it produces changes with it, without anyone
remembering. That is the property ADR-0009 asked for, and it is checkable:
:func:`assert_version_tracks_source` re-derives and compares.

Two things are deliberately *not* in the hash:

- **Wall-clock time.** A time component would make every extraction unique
  and defeat the idempotence ADR-0009 requires. The same bytes through the
  same code must produce the same version.
- **The material itself.** The content hash is already a key component and
  is hashed there.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from types import ModuleType

__all__ = [
    "ExtractionVersionError",
    "assert_version_tracks_source",
    "derive_extraction_version",
    "library_versions",
]

#: Domain-separated so this digest can never be confused with a content hash
#: or anything else this project hashes.
_DOMAIN = b"labcairn/extraction-version/v1"


class ExtractionVersionError(RuntimeError):
    """The adapter's source could not be read, so the version cannot track it."""


def _module_source(module: ModuleType) -> bytes:
    """One module's own bytes.

    Read from disk rather than from ``inspect.getsource`` because a frozen
    or zipped install has no source object to introspect, and a version that
    silently stops tracking the code is the failure this module exists to
    prevent. Refusing to produce one is the honest outcome.
    """
    path = getattr(module, "__file__", None)
    if not path:
        raise ExtractionVersionError(
            f"{module.__name__} has no source file, so its extraction version cannot be "
            f"derived from its code. Returning something else would produce a version "
            f"that stops changing when the behaviour does."
        )
    from pathlib import Path

    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ExtractionVersionError(
            f"cannot read {path} to derive an extraction version: {exc}"
        ) from exc


def derive_extraction_version(modules: tuple[ModuleType, ...], libraries: Mapping[str, str]) -> str:
    """A short digest binding an extraction to the code and libraries that made it.

    ``modules`` is every module whose source can change this adapter's
    output, in a fixed order. Passing only the adapter's own module leaves a
    real hole -- an adapter that calls a shared helper lives or dies by that
    helper, and the version would not notice.

    ``libraries`` is passed in rather than imported here so this module has
    no optional dependencies: a caller that has no pdfplumber installed
    derives a text-only version without the import failing at module load.
    """
    digest = hashlib.sha256()
    digest.update(_DOMAIN)
    for module in modules:
        # The module's qualified name goes in as well as its bytes: two files
        # with identical content are the same behaviour, but reordering the
        # tuple must still change the digest.
        digest.update(b"\0module\0")
        digest.update(module.__name__.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_module_source(module))
    for name in sorted(libraries):
        digest.update(b"\0lib\0")
        digest.update(name.encode("utf-8"))
        digest.update(b"=")
        digest.update(libraries[name].encode("utf-8"))
    return digest.hexdigest()[:32]


def library_versions(*modules: ModuleType) -> dict[str, str]:
    """``{name: version}`` for each module, skipping any that is absent.

    ``importlib.metadata`` is avoided in favour of ``__version__`` because a
    vendored or editable install can have the package without the
    distribution, and a missing version should degrade to "absent" rather
    than raise in the middle of an ingest.
    """
    found: dict[str, str] = {}
    for module in modules:
        version = getattr(module, "__version__", None)
        if isinstance(version, str) and version:
            found[module.__name__.rsplit(".", 1)[-1]] = version
    return found


def assert_version_tracks_source(
    modules: tuple[ModuleType, ...],
    libraries: Mapping[str, str],
    recorded: str,
) -> None:
    """Fail when a recorded version no longer matches what the code would produce.

    The check belongs at *write* time rather than read time: recording a
    version the current code cannot produce is how an address silently starts
    describing extraction behaviour that no longer exists.
    """
    current = derive_extraction_version(modules, libraries)
    if current != recorded:
        raise ExtractionVersionError(
            f"recorded extraction_version {recorded!r} does not match what this build "
            f"derives ({current!r}). Either the adapter changed -- in which case the "
            f"text must be re-extracted under the new version -- or the recorded value "
            f"was written by different code."
        )
