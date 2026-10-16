"""The real-paper fixtures must be the papers the manifest says they are.

A fixture that is silently swapped makes a test pass against material
nobody chose. That is the failure mode this project treats as worst, so
integrity is asserted, not assumed.

Two layers, deliberately:

  * Integrity checks need nothing but the standard library, so they run
    on every platform and in CI today.
  * Content checks need pdfplumber, which is not a dependency until
    LC-P1-08 adopts it. They skip with a stated reason rather than
    disappearing, so a green run never implies they passed.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from pathlib import Path
from typing import Any

import pytest

PAPERS = Path(__file__).parent / "fixtures" / "papers"
MANIFEST = PAPERS / "MANIFEST.md"

# file -> (sha256, pages, bytes)
EXPECTED = {
    "arx-2610.10596.pdf": (
        "6da9f8057e8cc7bafcf76316d660276f40c2e4a87230fa418e28cde51143d700",
        9,
        267_479,
    ),
    "arx-2610.12393.pdf": (
        "2429674e16c9b9dc2bb584d71e307285853fca11e356847d7e84508538799b9d",
        32,
        720_429,
    ),
    "arx-2610.09396.pdf": (
        "292eae176b6ea072cb23b163f861954bab2fd7e1f973d8f8fcd2575aa1338520",
        29,
        1_685_086,
    ),
}


def _pdfplumber() -> Any:
    """Imported dynamically so a missing dependency is a skip, not a type error.

    A static ``import pdfplumber`` would need a ``# type: ignore`` that is
    used where pdfplumber is installed and *unused* where it is not -- and
    an unused ignore is itself an error, so the same line fails on one CI
    platform while passing on the other. Importing by name keeps both
    platforms honest without a platform-conditional ignore.
    """
    try:
        return importlib.import_module("pdfplumber")
    except ImportError:
        pytest.skip("pdfplumber is not a dependency until LC-P1-08 adopts it")


# --------------------------------------------------------------------------
# Integrity -- no third-party dependency, runs today
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_is_byte_identical_to_the_manifest(name: str) -> None:
    """A swapped fixture must fail here, not silently pass a content test."""
    path = PAPERS / name
    assert path.is_file(), f"{name} is missing; the fixture set changed"
    digest, pages, size = EXPECTED[name]
    data = path.read_bytes()
    assert len(data) == size, f"{name} is {len(data)} bytes, manifest says {size}"
    assert hashlib.sha256(data).hexdigest() == digest, (
        f"{name} has changed. If that is intended, the manifest digest, the "
        f"recorded measurements and any test asserting on this paper must be "
        f"updated together -- a fixture swap invalidates every claim made "
        f"about it."
    )
    assert pages > 0


def test_no_unexpected_fixture_is_present() -> None:
    """An extra PDF would be unvetted material inside the repository."""
    found = {p.name for p in PAPERS.glob("*.pdf")}
    assert found == set(EXPECTED), f"unexpected fixtures: {sorted(found - set(EXPECTED))}"


def test_manifest_records_the_digest_of_every_fixture() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    for name, (digest, _, _) in EXPECTED.items():
        assert name in text, f"{name} is not named in the manifest"
        assert digest in text, f"{name}'s digest is not recorded in the manifest"


def test_manifest_records_licence_and_attribution() -> None:
    """CC BY obliges attribution, so the manifest must carry it."""
    text = MANIFEST.read_text(encoding="utf-8")
    assert "CC BY 4.0" in text, "the licence is not stated"
    for name in EXPECTED:
        assert name.replace(".pdf", "") in text, f"{name} has no attribution entry"
    # Attribution needs a human-readable title and an author, not just a hash.
    assert len(re.findall(r"https://arxiv\.org/abs/", text)) >= len(EXPECTED)
    assert "Authors" in text


def test_manifest_states_that_two_column_coverage_is_missing() -> None:
    """The corpus's main limitation must stay visible, not be forgotten."""
    text = MANIFEST.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "two-column" in lowered
    assert "unproven" in lowered or "untested" in lowered, (
        "the manifest must say plainly that two-column detection is untested; "
        "the corpus is single-column only and that fact is easy to forget"
    )


# --------------------------------------------------------------------------
# Content -- needs pdfplumber, i.e. LC-P1-08
# --------------------------------------------------------------------------


def test_every_fixture_really_is_single_column() -> None:
    """A two-column fixture would invalidate the negative-case reasoning."""
    pdfplumber = _pdfplumber()
    import collections

    for name in sorted(EXPECTED):
        with pdfplumber.open(PAPERS / name) as pdf:
            starts: collections.Counter[int] = collections.Counter()
            lines = 0
            for page in pdf.pages[:10]:
                by_y: dict[float, list[dict[str, Any]]] = collections.defaultdict(list)
                for char in page.chars:
                    by_y[round(char["doctop"], 1)].append(char)
                for members in by_y.values():
                    if len(members) < 20:
                        continue
                    members.sort(key=lambda c: c["x0"])
                    starts[int(members[0]["x0"])] += 1
                    lines += 1
        assert lines >= 25, f"{name}: too few body lines to classify"
        strong = [(x, n) for x, n in starts.most_common(6) if n / lines >= 0.18]
        spread = len(strong) >= 2 and abs(strong[0][0] - strong[1][0]) >= 80
        assert not spread, (
            f"{name} looks two-column (line-start peaks {strong}). The manifest "
            f"and the single-column reasoning need revisiting."
        )


def test_real_papers_contain_almost_no_space_glyphs() -> None:
    """ADR-0008 constraint 3, on real material rather than a fixture."""
    pdfplumber = _pdfplumber()

    for name in sorted(EXPECTED):
        with pdfplumber.open(PAPERS / name) as pdf:
            spaces = 0
            total = 0
            for page in pdf.pages[:10]:
                total += len(page.chars)
                spaces += sum(1 for c in page.chars if c["text"] == " ")
        ratio = spaces / total
        assert ratio < 0.02, (
            f"{name} has {ratio:.2%} space glyphs, which is not the "
            f"positioning-spaced case this corpus documents"
        )
