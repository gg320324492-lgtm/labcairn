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
import sys
from collections.abc import Mapping
from pathlib import Path
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

#: The directory PyInstaller unpacks bundled data files into at run time.
#: Present only in a frozen build that was frozen with data files; the
#: attribute is spelled ``_MEIPASS2`` on some old loaders and ``_MEIPASS``
#: on every loader this project targets, so only the current spelling is
#: read and anything else falls through to the on-disk path.
_MEIPASS_ATTRIBUTE = "_MEIPASS"


class ExtractionVersionError(RuntimeError):
    """The adapter's source could not be read, so the version cannot track it."""


def _frozen_data_root() -> Path | None:
    """Where the freeze unpacked bundled files, when it did.

    ``sys.frozen`` is set only in a PyInstaller (or similar) bundle, and
    ``sys._MEIPASS`` is created only when the bundle carries data files.
    Checked with ``getattr`` rather than attribute access so a mocked
    ``sys.frozen`` without a ``_MEIPASS`` raises the honest error instead of
    an ``AttributeError`` from inside the reader.
    """
    if not getattr(sys, "frozen", False):
        return None
    root = getattr(sys, _MEIPASS_ATTRIBUTE, None)
    return Path(root) if root else None


def _module_source(module: ModuleType) -> bytes:
    """One module's own bytes.

    Read from disk rather than from ``inspect.getsource`` because a frozen
    or zipped install has no source object to introspect, and a version that
    silently stops tracking the code is the failure this module exists to
    prevent. Refusing to produce one is the honest outcome.

    In a frozen build the pure-Python product modules live inside the
    executable and their ``__file__`` names a path under ``_internal`` that
    does not exist, so the bytes are read from the bundle's data directory
    (``sys._MEIPASS``) instead -- which only works when the freeze carried
    the module sources as data files. The dependency is deliberate and
    announced: a freeze that does not ship them fails here, at the same
    point the unfrozen reader would, rather than deriving a version from
    nothing. D-07-01.
    """
    frozen_root = _frozen_data_root()
    candidates: list[Path] = []
    if frozen_root is not None:
        candidates.append(frozen_root / module.__name__.replace(".", "/"))
    path = getattr(module, "__file__", None)
    if path:
        candidates.append(Path(path))

    if not candidates:
        raise ExtractionVersionError(
            f"{module.__name__} has no source file, so its extraction version cannot be "
            f"derived from its code. Returning something else would produce a version "
            f"that stops changing when the behaviour does."
        )
    for candidate in candidates:
        try:
            return candidate.read_bytes()
        except OSError:
            continue
    details = "; ".join(str(candidate) for candidate in candidates)
    raise ExtractionVersionError(
        f"cannot read the source of {module.__name__} to derive an extraction "
        f"version; tried: {details}. A version derived from anything else stops "
        f"changing when the behaviour does."
    )


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
