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

The layout guard carries its own **two-column control**, built here rather
than borrowed. An earlier version of this file grouped characters by
doctop across the full page width and counted line-start peaks; a reviewer
proved with a control that it could never fire for a normally-set
two-column page, because left and right column lines share baselines and
merge into a single group whose leftmost glyph is always in the left
column. The guard was therefore inert -- and the corpus's central claim
was being protected by a test that could not fail. ``test_the_layout_guard
_detects_two_columns`` exists so that cannot recur silently.
"""

from __future__ import annotations

import collections
import hashlib
import importlib
import itertools
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

# CC BY 4.0 section 3(a)(1)(A) asks for identification of the creator(s).
# An earlier manifest listed five of this paper's ten authors, which is an
# unmet condition rather than a formatting slip, so the names are asserted
# here rather than trusted to the prose.
AUTHORS = {
    "arx-2610.10596.pdf": ["Wang, Shengbao"],
    "arx-2610.12393.pdf": [
        "Dai, Qun",
        "Wen, Liangjian",
        "Duan, Jiang",
        "Dai, Yong",
        "Wang, Dongkai",
        "Wang, Maolin",
        "Wang, Mingjie",
        "Liu, Jianzhuang",
        "Yan, He",
        "Kang, Zhao",
    ],
    "arx-2610.09396.pdf": ["Hu, Yihao", "Feng, Yanlin", "Otani, Naoki", "Bhutani, Nikita"],
}

SPLIT_GAP = 10.0  # wider than this is not a word gap
CLUSTER_TOL = 5.0
MIN_SUPPORT_FRACTION = 0.18


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
        # **pdfplumber is a declared dependency** -- ADR-0008 chose it over
        # PyMuPDF -- so it is not a case this test may skip, it is a broken
        # environment. The message used to say it was "not a dependency until
        # LC-P1-08 adopts it", and LC-P1-08 adopted it a long time ago. **A
        # skip that names a condition which no longer holds is a skip that
        # hides a real failure.**
        pytest.skip(
            "pdfplumber is not installed, and it is a declared dependency: "
            "this is a broken environment, not a case this test may skip"
        )


# --------------------------------------------------------------------------
# Layout classification -- shared by the guard and its own control
# --------------------------------------------------------------------------


def _column_local_runs(page: Any) -> list[list[tuple[float, float]]]:
    """Glyph runs separated by more than a word gap, grouped by doctop.

    Splitting *before* measuring is the whole point: measuring across the
    full page merges the two columns of a two-column page, because they
    share baselines.
    """
    by_y: dict[float, list[dict[str, Any]]] = collections.defaultdict(list)
    for char in page.chars:
        by_y[round(char["doctop"], 1)].append(char)

    runs: list[list[tuple[float, float]]] = []
    for members in by_y.values():
        members.sort(key=lambda c: c["x0"])
        current: list[tuple[float, float]] = []
        edge = -1e9
        for char in members:
            if char["x0"] - edge <= SPLIT_GAP:
                current.append((char["x0"], char["x1"]))
                edge = max(edge, char["x1"])
            else:
                if current:
                    runs.append(current)
                current = [(char["x0"], char["x1"])]
                edge = char["x1"]
        if current:
            runs.append(current)
    return runs


def _column_count(runs: list[list[tuple[float, float]]]) -> int:
    """Column count from recurring left edges of column-local runs."""
    solid = [r for r in runs if len(r) >= 12]
    if len(solid) < 8:
        return 1
    starts: collections.Counter[float] = collections.Counter(
        int(r[0][0] // CLUSTER_TOL) * CLUSTER_TOL for r in solid
    )
    strong = sorted(x for x, n in starts.most_common(6) if n / len(solid) >= MIN_SUPPORT_FRACTION)
    if len(strong) < 2:
        return 1
    return 2 if any(b - a >= 80.0 for a, b in itertools.pairwise(strong)) else 1


def _dominant_columns(path: Path) -> int:
    pdfplumber = _pdfplumber()
    with pdfplumber.open(str(path)) as pdf:
        counts = [_column_count(_column_local_runs(page)) for page in pdf.pages[:10]]
    return max(set(counts), key=counts.count)


def _one_page_pdf(lines: list[tuple[float, float, str]]) -> bytes:
    """Minimal PDF with Helvetica, one Tj per (x, text). No external library."""
    content = b"".join(
        b"BT /F1 9 Tf "
        + str(int(x)).encode()
        + b" "
        + str(y).encode()
        + b" Td ("
        + text.encode()
        + b") Tj ET\n"
        for x, y, text in lines
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


# --------------------------------------------------------------------------
# Integrity -- no third-party dependency, runs today
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_is_byte_identical_to_the_manifest(name: str) -> None:
    """A swapped fixture must fail here, not silently pass a content test."""
    path = PAPERS / name
    assert path.is_file(), f"{name} is missing; the fixture set changed"
    digest, _, size = EXPECTED[name]
    data = path.read_bytes()
    assert len(data) == size, f"{name} is {len(data)} bytes, manifest says {size}"
    assert hashlib.sha256(data).hexdigest() == digest, (
        f"{name} has changed. If that is intended, the manifest digest, the "
        f"recorded measurements and any test asserting on this paper must be "
        f"updated together -- a fixture swap invalidates every claim made "
        f"about it."
    )


def test_no_unexpected_fixture_is_present() -> None:
    """An extra PDF would be unvetted material inside the repository."""
    found = {p.name for p in PAPERS.glob("*.pdf")}
    assert found == set(EXPECTED), f"unexpected fixtures: {sorted(found - set(EXPECTED))}"


def test_no_pdf_is_tracked_outside_the_fixture_directory() -> None:
    """Catches a generated PDF committed at the repository root.

    One was: a development script wrote its control to the working
    directory, `git add -A` swept it up, and Hatch's sdist target
    includes tracked files that are not excluded -- so it would have
    shipped in the distribution. Nothing referenced it, and the fixture
    guard did not see it, because that guard globs one directory.
    """
    import subprocess

    repo_root = PAPERS.parents[2]
    result = subprocess.run(
        ["git", "ls-files", "*.pdf"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        # Explicit, not the system code page: a decode error surfaces in
        # subprocess's reader thread, which returns None rather than raising
        # where the caller can see it. CI is UTF-8; a Windows checkout on
        # another code page is not.
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    tracked = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith("tests/fixtures/papers/")
    }
    assert not tracked, (
        f"PDFs are tracked outside the fixture directory: {sorted(tracked)}. "
        f"Third-party material needs a manifest entry; generated material "
        f"needs a temporary directory."
    )


def test_manifest_records_the_digest_of_every_fixture() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    for name, (digest, _, _) in EXPECTED.items():
        assert name in text, f"{name} is not named in the manifest"
        assert digest in text, f"{name}'s digest is not recorded in the manifest"


def test_manifest_discharges_cc_by_attribution() -> None:
    """Every creator named, not just a pointer at the source page.

    A partial list is worse than a bare link: it asserts the author set
    and gets it wrong. Five of ten authors were missing once.
    """
    text = MANIFEST.read_text(encoding="utf-8")
    assert "CC BY 4.0" in text, "the licence is not stated"
    assert "creativecommons.org/licenses/by/4.0" in text, "the licence URI is not given"
    for name in sorted(EXPECTED):
        assert name in text, f"{name} is not named in the manifest"
        missing = [author for author in AUTHORS[name] if author not in text]
        assert not missing, f"{name}: unattributed creators {missing}"


def test_manifest_states_that_two_column_coverage_is_missing() -> None:
    """The corpus's main limitation must stay visible, not be forgotten."""
    text = MANIFEST.read_text(encoding="utf-8").lower()
    assert "two-column" in text
    assert "unproven" in text or "untested" in text, (
        "the manifest must say plainly that two-column detection is untested; "
        "the corpus is single-column only and that fact is easy to forget"
    )


# --------------------------------------------------------------------------
# Content -- needs pdfplumber, i.e. LC-P1-08
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_page_count_matches_the_manifest(name: str) -> None:
    pdfplumber = _pdfplumber()
    _, pages, _ = EXPECTED[name]
    with pdfplumber.open(str(PAPERS / name)) as pdf:
        assert len(pdf.pages) == pages, f"{name} has {len(pdf.pages)} pages, expected {pages}"


def test_the_layout_guard_detects_two_columns(tmp_path: Path) -> None:
    """The guard must be able to fail, or it is not a guard.

    Two columns on shared baselines are exactly what defeated the earlier
    version of this file. If this test ever fails, the classifier below has
    regressed to something that cannot see the case it exists for.
    """
    _pdfplumber()  # skips with a stated reason when pdfplumber is absent

    body_a = "The quick brown fox jumps over the lazy dog again"
    body_b = "and again today the lazy dog jumps over the quick brown fox"
    baselines = (680.0, 668.0, 656.0, 644.0, 632.0, 620.0, 608.0)

    two_column: list[tuple[float, float, str]] = []
    for y in baselines:
        two_column.append((54.0, y, body_a))
        two_column.append((360.0, y, body_b))
    one_column: list[tuple[float, float, str]] = [
        (72.0, y, f"{body_a} {body_b}") for y in baselines
    ]

    two_path = tmp_path / "two.pdf"
    two_path.write_bytes(_one_page_pdf(two_column))
    one_path = tmp_path / "one.pdf"
    one_path.write_bytes(_one_page_pdf(one_column))

    assert _dominant_columns(two_path) == 2, (
        "the classifier no longer detects two columns on shared baselines; "
        "every single-column assertion below is then vacuous"
    )
    assert _dominant_columns(one_path) == 1


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_fixture_really_is_single_column(name: str) -> None:
    """A two-column fixture would invalidate the negative-case reasoning."""
    assert _dominant_columns(PAPERS / name) == 1, (
        f"{name} looks two-column. The manifest and the single-column reasoning need revisiting."
    )


def test_real_papers_contain_almost_no_space_glyphs() -> None:
    """ADR-0008 constraint 3, on real material rather than a fixture."""
    pdfplumber = _pdfplumber()

    for name in sorted(EXPECTED):
        with pdfplumber.open(str(PAPERS / name)) as pdf:
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
