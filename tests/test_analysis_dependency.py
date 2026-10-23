"""The dependency LC-P1-10's charts are drawn with, and the guarantees it owes.

LC-P1-10 T00 is the work order that decides **which library** the figures are
drawn with, and this file is where that decision is made checkable rather
than asserted. It is deliberately **not** the renderer's test — that is T07's,
and it will test LabCairn's own rcParams file and its own recipe. This file
tests the *library*: that it is here, that it is the version the project says
it is, that it draws a figure with no display attached, and that the two
controls T07 will rely on actually produce byte-identical output.

Two controls, two different failures
------------------------------------
The determinism claim rests on two matplotlib settings, and they are **not
interchangeable**, which is the thing worth knowing:

* **The creation date** is written into the SVG metadata, and two renders a
  second apart get different ones. Suppressing it (``metadata={"Date": None}``)
  is what makes two renders *in one process* identical.
* **``svg.hashsalt``** is the salt matplotlib uses to generate the element ids
  in an SVG. Left unset, matplotlib picks a **fresh random salt per process**,
  so two renders in *different* processes get different ids and different
  bytes even with the date suppressed.

So fixing the salt alone is not enough, and suppressing the date alone is not
enough either. Each test below fails if its own control is removed, and the
cross-process one is the only test that can observe the salt at all — within
a single process the default salt is constant, so a test that only rendered
twice in one process would pass with the salt removed.

This is also the file that catches the failure this work order exists to
prevent: a headless-rendering problem on the Windows runner, found in T00
where the dependency is decided rather than in T07 where the renderer is
built.

What this file does **not** claim
---------------------------------
It does not claim cross-machine byte-identity. Two renders on two different
machines depend on the font files each machine has, which is a different
question and is answered in ADR-0012 rather than here.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

#: The version floor and ceiling the project declares, as they appear in
#: ``pyproject.toml``. Parsed from there rather than restated, so the
#: declaration and the lock cannot drift apart without this failing.
_REQUIREMENT = re.compile(r"^matplotlib>=(\d+)\.(\d+),<(\d+)$")

#: matplotlib's own version, as a comparable tuple.
_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?")

#: The SVG control that makes matplotlib's generated element ids stable
#: across processes. The value is arbitrary and fixed: the property under
#: test is that a *fixed* salt produces stable ids, not that this particular
#: string is a good one.
HASHSALT = "labcairn"

#: The PNG magic number. A PNG that does not start with it is not a PNG, and
#: "the file was written" is not the same claim as "the file is an image".
_PNG_MAGIC = bytes.fromhex("89504e470d0a1a0a")

#: A renderer that runs in a *separate interpreter*, so that the salt's
#: cross-process effect is observable. The program is kept here rather than
#: in a helper file so that the two renders cannot drift apart: it is the
#: same text the in-process render is specified by, with the salt token
#: substituted in.
_RENDER_PROGRAM = """
import hashlib, io, os, sys
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
matplotlib.rcdefaults()
matplotlib.rcParams["svg.hashsalt"] = "__HASHSALT__"
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(2, 1.5), dpi=100)
ax.plot([0, 1, 2], [0, 1, 4])
buf = io.BytesIO()
fig.savefig(buf, format="svg", metadata={"Date": None})
sys.stdout.write(hashlib.sha256(buf.getvalue()).hexdigest())
"""


def _matplotlib() -> ModuleType:
    """matplotlib, imported with the Agg backend selected.

    The backend is chosen **before** the import, because matplotlib reads it
    at import time. ``matplotlib.use`` is called as well, because the backend
    of a session in which something else already imported pyplot is not
    something this file may assume.
    """
    os.environ.setdefault("MPLBACKEND", "Agg")
    import matplotlib

    matplotlib.use("Agg")
    return matplotlib


def _pyplot() -> ModuleType:
    """``matplotlib.pyplot``, imported after the backend is settled."""
    import matplotlib.pyplot as plt

    return plt


def _render_svg(*, controls: bool) -> bytes:
    """One SVG rendering, with or without the two determinism controls.

    ``controls=False`` is the matplotlib default, and it is the case that
    matters: it is what a renderer that forgets a setting produces.
    """
    matplotlib = _matplotlib()
    plt = _pyplot()
    matplotlib.rcdefaults()
    if controls:
        matplotlib.rcParams["svg.hashsalt"] = HASHSALT

    fig, ax = plt.subplots(figsize=(2, 1.5), dpi=100)
    ax.plot([0, 1, 2], [0, 1, 4])
    buffer = io.BytesIO()
    if controls:
        fig.savefig(buffer, format="svg", metadata={"Date": None})
    else:
        fig.savefig(buffer, format="svg")
    plt.close(fig)
    return buffer.getvalue()


def _render_in_another_process() -> str:
    """The sha256 of the same render, made by a separate interpreter."""
    program = _RENDER_PROGRAM.replace("__HASHSALT__", HASHSALT)
    done = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        # Both halves of the pipe are stated, and they agree: the child is
        # told to write UTF-8 and the parent decodes UTF-8. Leaving either
        # to the machine's locale is how a non-ASCII path turns into a
        # swallowed decode error and a capture that comes back as None --
        # and then ``done.stderr.strip()`` is an AttributeError that says
        # nothing about the cause.
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert done.returncode == 0, (
        f"the out-of-process render failed with exit {done.returncode}: "
        f"{done.stderr.strip()[-500:]}"
    )
    return done.stdout.strip()


def _declared_range(repo_root: Path) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The version floor and ceiling ``pyproject.toml`` declares.

    Read from the file rather than restated, so there is one spelling of the
    range in the repository. A declaration that drifts from the lock is
    exactly the failure worth catching.
    """
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = data["project"]["dependencies"]
    matches = [r for r in requirements if r.lower().startswith("matplotlib")]
    assert len(matches) == 1, (
        f"expected exactly one matplotlib requirement in pyproject.toml, found {matches!r}"
    )
    parsed = _REQUIREMENT.match(matches[0])
    assert parsed is not None, (
        f"matplotlib is declared as {matches[0]!r}, which this test cannot read. "
        f"It expects the form 'matplotlib>=X.Y,<Z'. If the declaration changed shape, "
        f"this test must be updated with it -- not loosened."
    )
    floor = (int(parsed.group(1)), int(parsed.group(2)))
    ceiling = (int(parsed.group(3)),)
    return floor, ceiling


@pytest.mark.unit
def test_the_installed_matplotlib_is_inside_the_range_the_project_declares(
    repo_root: Path,
) -> None:
    """The declared range and the locked version agree.

    The lockfile is what CI installs, and the declaration is what the
    project's own documentation claims. If they disagree, one of the two is
    a claim nobody checked.
    """
    matplotlib = _matplotlib()
    floor, ceiling = _declared_range(repo_root)

    version = matplotlib.__version__
    parsed = _VERSION.match(version)
    assert parsed is not None, (
        f"matplotlib reports version {version!r}, which is not a plain X.Y[.Z] "
        f"release. This test compares version tuples, and a version it cannot "
        f"read is a version it must not silently accept."
    )
    parts = tuple(int(p) for p in parsed.groups() if p is not None)
    assert parts >= floor, (
        f"matplotlib {version} is below the declared floor {floor[0]}.{floor[1]}. "
        f"The declaration and the lock have drifted apart."
    )
    assert parts[0] < ceiling[0], (
        f"matplotlib {version} is in major version {parts[0]}, but the project "
        f"declares <{ceiling[0]}. A major bump is the kind of change ADR-0012 "
        f"asks to be looked at rather than absorbed."
    )


@pytest.mark.unit
def test_a_figure_renders_headless_with_no_display() -> None:
    """A figure can be drawn with no display attached, on both CI platforms.

    This is the check that has to exist in T00 rather than in T07: a
    headless-rendering failure on the Windows runner is a *dependency*
    problem, and finding it here is what the work order's ordering is for.
    """
    matplotlib = _matplotlib()
    plt = _pyplot()
    matplotlib.rcdefaults()

    assert matplotlib.get_backend().lower() == "agg", (
        f"the backend is {matplotlib.get_backend()!r}, not 'agg'. Something "
        f"imported pyplot before the backend was settled, and this file may "
        f"not assume a display is absent."
    )

    fig, ax = plt.subplots(figsize=(2, 1.5), dpi=100)
    ax.plot([0, 1, 2], [0, 1, 4])

    svg_buffer = io.BytesIO()
    fig.savefig(svg_buffer, format="svg")
    png_buffer = io.BytesIO()
    fig.savefig(png_buffer, format="png")
    plt.close(fig)

    svg = svg_buffer.getvalue()
    png = png_buffer.getvalue()
    assert svg.startswith(b"<?xml"), f"the SVG does not start with an XML prolog: {svg[:40]!r}"
    assert b"<svg" in svg, "the SVG contains no <svg> element"
    assert png.startswith(_PNG_MAGIC), (
        f"the PNG does not start with the PNG magic number: {png[:8].hex()}"
    )


@pytest.mark.unit
def test_two_renders_in_one_process_are_byte_identical() -> None:
    """Suppressing the creation date is what makes one process's renders match.

    The finding this pins down: matplotlib writes a creation date into the
    SVG metadata, so two renders a second apart differ. A renderer that
    rendered the same data twice and compared the bytes would see a
    difference and conclude the figure was not reproducible -- or, worse,
    would not compare them at all and believe it was.

    The date is not asserted to be *present* in the uncontrolled output --
    that is a fact about matplotlib and is recorded in ADR-0012, where a
    change in matplotlib's behaviour belongs. What is asserted here is the
    property LabCairn needs: **with the controls, two renders are
    byte-identical.**
    """
    controlled_a = _render_svg(controls=True)
    controlled_b = _render_svg(controls=True)

    assert controlled_a, "the controlled render produced no bytes at all"
    assert controlled_a == controlled_b, (
        "two renders with the date suppressed differ. The controls ADR-0012 "
        "prescribes are not sufficient, and every determinism claim LC-P1-10 "
        "makes rests on them."
    )


@pytest.mark.unit
def test_a_render_in_another_process_has_the_same_bytes() -> None:
    """Fixing the hash salt is what makes two *processes* agree.

    Left unset, matplotlib generates a fresh random salt per process, so the
    element ids in an SVG differ between interpreters and the bytes differ
    even with the date suppressed. This is the only test in the file that
    can observe the salt: within one process the default salt is constant,
    so a test that rendered twice in one process would pass with the salt
    removed.
    """
    here = hashlib.sha256(_render_svg(controls=True)).hexdigest()
    there = _render_in_another_process()

    assert here == there, (
        f"the in-process render hashes to {here} and the out-of-process render "
        f"to {there}. The salt is not doing its job, so a figure's hash would "
        f"depend on which interpreter drew it."
    )


@pytest.mark.unit
def test_the_bundled_fonts_ship_with_their_licences() -> None:
    """matplotlib redistributes fonts, and their licences travel with them.

    This is the obligation ADR-0008 recorded for paper-qa and ADR-0012
    records here: a licence line that is accurate for the root of a
    distribution can be misleading about a directory inside it. matplotlib
    bundles forty TrueType fonts under two further licences, and those
    licences are inside the wheel.

    The assertion is deliberately about the *shape* of the obligation -- fonts
    present, and licence files present beside them -- rather than about
    particular filenames, so that a matplotlib that renames a licence file
    does not fail here while a matplotlib that drops the licences does.
    """
    _matplotlib()
    import matplotlib as mpl

    data_dir = Path(mpl.__file__).parent / "mpl-data" / "fonts" / "ttf"
    assert data_dir.is_dir(), (
        f"matplotlib ships no bundled TrueType fonts at {data_dir}. If that is "
        f"deliberate, ADR-0012's font-licence obligation has to be withdrawn "
        f"and the withdrawal has to be a decision, not a consequence."
    )

    fonts = sorted(data_dir.glob("*.ttf"))
    assert fonts, f"matplotlib bundles no .ttf fonts under {data_dir}"

    licences = sorted(
        p for p in data_dir.iterdir() if p.is_file() and p.name.upper().startswith("LICEN")
    )
    assert licences, (
        f"matplotlib bundles {len(fonts)} font(s) and no licence file beside "
        f"them. Redistribution without the notices is not permitted by either "
        f"of the two font licences, so this is an obligation, not a formality."
    )

    # And the distribution's own licence must be present too, in whichever of
    # the two layouts modern wheels use.
    site_packages = Path(mpl.__file__).parent.parent
    dist_infos = sorted(site_packages.glob("matplotlib-*.dist-info"))
    assert dist_infos, (
        f"matplotlib is installed under {site_packages} with no dist-info "
        f"directory, so its own licence file cannot be found."
    )
    own = [
        p
        for p in dist_infos[0].rglob("*")
        if p.is_file() and p.name.upper().startswith(("LICEN", "COPYING", "NOTICE"))
    ]
    assert own, (
        f"matplotlib's own licence file is not present under {dist_infos[0]}. "
        f"The licence was verified from that file, so its absence would leave "
        f"the verification unverifiable."
    )
