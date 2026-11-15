"""The extraction version must track its code in a frozen build too.

D-07-01 (``docs/acceptance/LC-P3-07-drill-run-2026-11-14.md`` §5): on the
PyInstaller-packaged build, every ``.txt`` material was refused with
``material_incomplete`` because ``_module_source`` read each adapter's
``__file__`` bytes from disk, and a frozen module's ``__file__`` names a
path under ``_internal`` that does not exist.

The fix reads the bytes from the bundle's data directory (``sys._MEIPASS``)
when ``sys.frozen`` says the process is frozen, falling back to the
on-disk ``__file__`` otherwise. These witnesses pin the three properties
that make that fix honest rather than a silent degradation:

- an unfrozen run reads the disk exactly as before;
- a frozen run reads the bundled bytes, including when the on-disk path
  is gone -- the exact D-07-01 shape;
- a frozen run with **no** bundled bytes refuses with
  :class:`ExtractionVersionError` -- a version derived from nothing is the
  failure this module exists to prevent, so the freeze that forgets to
  ship the sources fails loudly instead of minting a version that stops
  changing when the behaviour does.
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from labcairn.material import text as text_module
from labcairn.material import version as version_module
from labcairn.material.ingest import ingest_bytes
from labcairn.material.version import (
    ExtractionVersionError,
    _module_source,
    derive_extraction_version,
)
from labcairn.sources.source import SourceKind

pytestmark = pytest.mark.negative


def _freeze(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Pretend this process is a PyInstaller bundle unpacked at *root*."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(root), raising=False)


def _bundle_source(root: Path, module: ModuleType, contents: bytes) -> Path:
    """Lay one module's source into the bundle's data tree."""
    name = module.__name__
    bundled = root / name.replace(".", "/")
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_bytes(contents)
    return bundled


def test_unfrozen_source_still_reads_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The venv path is untouched: disk bytes in, disk bytes out."""
    disk = Path(text_module.__file__ or "")
    assert disk.is_file(), "the editable install's text.py must exist on disk"
    assert _module_source(text_module) == disk.read_bytes()


def test_unfrozen_version_ignores_a_meipass_attribute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_MEIPASS`` alone means nothing; only ``sys.frozen`` turns it on.

    A stray attribute left by another tool must not redirect the reader:
    the development tree stays the source of truth while not frozen.
    """
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert _module_source(text_module) == Path(text_module.__file__ or "").read_bytes()


def test_frozen_reads_bundled_bytes_when_disk_path_is_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-07-01's shape: ``__file__`` dangles, the bundle carries the bytes.

    The recorded defect was exactly this: a frozen ``__file__`` pointing at
    an ``_internal`` path that does not exist. With the bundle carrying the
    module source, the version is derivable again.
    """
    dangling = tmp_path / "_internal" / "labcairn" / "material" / "text.py"
    assert not dangling.exists()
    bundled = _bundle_source(tmp_path, text_module, b"FROZEN-SENTINEL-1")

    _freeze(monkeypatch, tmp_path)
    monkeypatch.setattr(text_module, "__file__", str(dangling))

    assert _module_source(text_module) == b"FROZEN-SENTINEL-1"
    assert bundled.is_file()


def test_frozen_prefers_the_bundled_bytes_over_the_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A frozen build is its bundle: the packaged source, not the checkout's.

    If both exist they should agree in a real freeze, but the reader's
    contract under ``sys.frozen`` is that the bundle wins -- the disk copy
    is whatever the build machine happened to have.
    """
    _bundle_source(tmp_path, text_module, b"BUNDLED-VERSION")
    _freeze(monkeypatch, tmp_path)
    assert b"BUNDLED-VERSION" in _module_source(text_module)


def test_frozen_without_bundled_bytes_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A freeze that ships no sources fails loudly, never mints a version.

    The honest outcome is the error itself: a digest derived from nothing
    would stop changing when the extraction behaviour does, which is the
    lying key ADR-0009 forbids. This is the witness for the other half of
    the fix -- adding ``--add-data`` to the freeze is what keeps this test's
    shape green in the packaged build.
    """
    dangling = tmp_path / "_internal" / "labcairn" / "material" / "text.py"
    _freeze(monkeypatch, tmp_path)
    monkeypatch.setattr(text_module, "__file__", str(dangling))

    with pytest.raises(ExtractionVersionError) as excinfo:
        _module_source(text_module)
    message = str(excinfo.value)
    assert "cannot read the source" in message
    assert str(dangling) in message, "the failure names every path it tried"


def test_frozen_without_a_meipass_attribute_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``frozen`` without ``_MEIPASS`` is a broken bundle, not a crash.

    A ``sys._MEIPASS`` that is absent must degrade to the same honest
    refusal as any other unreadable source -- an ``AttributeError`` from
    inside the reader would be a different, unintended failure mode.
    """
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    dangling = tmp_path / "nowhere" / "text.py"
    monkeypatch.setattr(text_module, "__file__", str(dangling))

    with pytest.raises(ExtractionVersionError):
        _module_source(text_module)


def test_frozen_version_tracks_the_bundled_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation check: changing the bundled source changes the version.

    Reading the bytes is only half the property. The digest must actually
    move when the bundled code moves and stay put when it does not --
    otherwise a frozen build could carry a version unrelated to the code
    it runs.
    """
    _bundle_source(tmp_path, text_module, b"def decode_text(data):\n    return data\n")
    _freeze(monkeypatch, tmp_path)
    modules = (text_module,)
    libraries: dict[str, str] = {}

    first = derive_extraction_version(modules, libraries)
    again = derive_extraction_version(modules, libraries)
    assert first == again, "the same bundled bytes must give the same version"

    _bundle_source(tmp_path, text_module, b"def decode_text(data):\n    return data.upper()\n")
    changed = derive_extraction_version(modules, libraries)
    assert changed != first, "a one-byte change to the bundled source must move the version"


def test_unfrozen_version_is_stable_across_the_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix changes no unfrozen version: derive here == derive with the
    reader forced down the frozen path's candidate list shape.

    Concretely: without ``sys.frozen``, a ``_MEIPASS`` attribute and even a
    bundled copy must not leak into the digest. The version recorded by
    every pre-fix row stays valid.
    """
    modules = (text_module,)
    libraries: dict[str, str] = {}
    before = derive_extraction_version(modules, libraries)

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    _bundle_source(tmp_path, text_module, b"decoy bytes that must not be hashed")
    after = derive_extraction_version(modules, libraries)
    assert before == after


def test_frozen_txt_ingest_produces_a_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end, the recorded defect: a frozen build must ingest ``.txt``.

    On the drilled build, ``task create`` refused every ``.txt`` with
    ``material_incomplete`` because the version derivation raised before an
    adapter could run. With the bundle carrying this package's sources, the
    same derivation succeeds and the ingest produces addressed text.
    """
    material_root = Path(version_module.__file__ or "").resolve().parent
    shutil.copytree(
        material_root,
        tmp_path / "labcairn" / "material",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    _freeze(monkeypatch, tmp_path)

    material = ingest_bytes(
        b"observation\tone\nobservation\ttwo\n",
        relative_path="notes/session-log.txt",
        display_name="session-log.txt",
        ingested_at=datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC),
    )
    assert material.problems == (), f"the freeze must not refuse a .txt: {material.problems}"
    assert material.extraction_version != "no-adapter"
    assert len(material.extraction_version) == 32
    assert all(character in "0123456789abcdef" for character in material.extraction_version), (
        "the version is a hex digest, not a placeholder"
    )
    assert len(material.texts) == 2
    assert material.texts[0].text == "observation\tone"


def test_txt_ingest_version_matches_the_unfrozen_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A frozen run and an unfrozen run of the same code mint the same
    version for the same bytes.

    The bundle carries the checkout's sources, so identical code must give
    identical digests either way -- a version that depended on *how* the
    process was started, rather than on the code and its libraries, would
    break the address comparisons ADR-0009 keys on.
    """
    data = b"obs\tone\n"
    unfrozen = ingest_bytes(
        data,
        relative_path="notes/a.txt",
        display_name="a.txt",
        ingested_at=datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC),
    )

    material_root = Path(version_module.__file__ or "").resolve().parent
    shutil.copytree(
        material_root,
        tmp_path / "labcairn" / "material",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    _freeze(monkeypatch, tmp_path)
    frozen = ingest_bytes(
        data,
        relative_path="notes/a.txt",
        display_name="a.txt",
        ingested_at=datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC),
    )

    assert frozen.extraction_version == unfrozen.extraction_version


def test_every_registered_adapter_derives_under_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix covers the registry, not just the text adapter.

    The freeze ships ``labcairn/material`` as one tree, so every adapter's
    modules are bundle-readable. Driving all of them through the frozen
    path is what stops a second D-07-01 appearing for, say, ``.docx``.
    """
    from labcairn.material.units import adapter_for

    material_root = Path(version_module.__file__ or "").resolve().parent
    shutil.copytree(
        material_root,
        tmp_path / "labcairn" / "material",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    _freeze(monkeypatch, tmp_path)

    for kind in (SourceKind.TEXT, SourceKind.MARKDOWN, SourceKind.CSV):
        adapter = adapter_for(kind)
        derived = derive_extraction_version(adapter.source_modules(), adapter.libraries())
        assert len(derived) == 32, kind
        assert all(character in "0123456789abcdef" for character in derived), (
            f"{kind} derived a non-digest version under freeze"
        )
