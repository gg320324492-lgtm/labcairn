"""Negative tests for path admission: every escape vector must actually fire.

Each test here corresponds to a way a declared path and the file it opens can
diverge. Where a vector is subtle, the test does two things: it asserts the
refusal, **and** it asserts that the underlying hazard is real on this machine
(``samefile`` for the trailing-dot alias, a real ``open()`` for the alternate
data stream, ``resolve()`` for the 8.3 name). Without the second half, a test
that passes because Windows happens not to have the quirk would look identical
to one that passes because the guard works.

The junction tests are the reason this file exists. ``Path.is_symlink()`` returns
``False`` for a Windows directory junction — verified, not assumed — so an
``is_symlink``-based guard walks past one and the containment check on the
*resolved* path is the only thing that catches it.
"""

from __future__ import annotations

import os
import subprocess
import unicodedata
from pathlib import Path

import pytest

from labcairn.security.paths import (
    AllowedRoot,
    PathRefusedError,
    PathRejection,
    RootKind,
    bind_root,
    canonicalize,
)

IS_WINDOWS = os.name == "nt"
requires_windows = pytest.mark.skipif(not IS_WINDOWS, reason="Windows path semantics")


def make_junction(link: Path, target: Path) -> None:
    """Create a Windows directory junction, which is *not* a symlink.

    ``os.symlink`` would not do: it creates a real symbolic link, which
    ``Path.is_symlink()`` does report. A junction is the thing that slips past
    that check, so it is the thing these tests must use.
    """
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"mklink /J unavailable: {proc.stderr.decode('utf-8', 'replace')}")


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, tuple[AllowedRoot, ...]]:
    """One allowed root plus a sibling directory that is *outside* it."""
    base = tmp_path / "base"
    allowed = base / "allowed"
    (allowed / "sub").mkdir(parents=True)
    (allowed / "ok.txt").write_text("ok", encoding="utf-8")
    (allowed / "secret.txt").write_text("secret", encoding="utf-8")
    outside = base / "outside"
    outside.mkdir()
    (outside / "target.txt").write_text("target", encoding="utf-8")
    return allowed, (bind_root("allowed", allowed, RootKind.OUTPUT),)


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tail", "label"),
    [
        (["..", "outside", "target.txt"], "one level"),
        (["sub", "..", "..", "outside", "target.txt"], "two levels"),
        (["sub", "..", "..", "..", "..", "outside", "target.txt"], "four levels"),
    ],
)
def test_dotdot_traversal_escaping_the_root_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
    tail: list[str],
    label: str,
) -> None:
    """``../`` upward, at several depths, never reaches outside the root."""
    allowed, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed.joinpath(*tail), bound)
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT, label


def test_dotdot_that_stays_inside_is_admitted(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """The complement, so the test above is not passing on a blanket refusal.

    ``sub/../ok.txt`` names a real file inside the root. Refusing it would be
    correct-but-useless; admitting it is what makes refusing the escaping form
    meaningful.
    """
    allowed, bound = roots
    canonical = canonicalize(allowed / "sub" / ".." / "ok.txt", bound)
    assert canonical.resolved_key == "ok.txt"
    assert canonical.real_path == allowed / "ok.txt"


def test_relative_path_with_no_base_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """Absolute paths are mandatory at the boundary.

    Resolving a relative path against the process working directory is the
    documented bypass deepagents has (ADR-0003 §A5). The CWD during this test
    is the repository root, so a CWD-relative resolution would admit
    ``conftest.py`` — a real file outside every bound root.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize("conftest.py", bound)
    assert caught.value.rejection is PathRejection.RELATIVE_WITHOUT_ROOT


def test_relative_path_with_an_explicit_base_resolves_under_that_base(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    allowed, bound = roots
    canonical = canonicalize("ok.txt", bound, base=bound[0])
    assert canonical.real_path == allowed / "ok.txt"


def test_relative_base_cannot_be_used_to_climb_out(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """Having a base does not license escaping it."""
    _, bound = roots
    with pytest.raises(PathRefusedError):
        canonicalize("../outside/target.txt", bound, base=bound[0])


# ---------------------------------------------------------------------------
# Absolute paths
# ---------------------------------------------------------------------------


def test_absolute_path_inside_the_root_is_admitted(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """ADR-0003 §C5 makes absolute paths *mandatory* at the boundary."""
    allowed, bound = roots
    canonical = canonicalize(allowed / "ok.txt", bound)
    assert canonical.resolved_key == "ok.txt"


@pytest.mark.skipif(os.name == "nt", reason="the Windows drive form is meaningless on POSIX")
def test_windows_drive_path_is_refused_on_posix(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """A Windows drive path is not absolute on POSIX.

    ``C:/Windows/...`` is a *relative* name on Linux — it has no leading
    separator — so the refusal has to be whatever the right answer is there,
    which today is the alternate-data-stream rule firing on the drive colon.

    The safety property under test is **refused**, not *which rule refused*:
    a segment containing ``:`` is refused everywhere, and the drive form is
    refused as a path outside the roots on Windows. Asserting a single
    rejection reason across both platforms would be asserting a platform
    accident.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError):
        canonicalize("C:/Windows/System32/drivers/etc/hosts", bound)


def test_absolute_path_outside_every_root_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """An absolute path naming a real location outside every root.

    The path is platform-appropriate: a POSIX absolute path on POSIX, a drive
    path on Windows. Using one form on both was how this test passed locally on
    Windows and failed on Ubuntu — ``C:/...`` is relative there, so the drive
    colon tripped the ADS rule instead of the containment rule, and the test
    asserted a reason that was correct for the wrong platform.
    """
    _, bound = roots
    absolute = "C:/Windows/System32/drivers/etc/hosts" if os.name == "nt" else "/etc/passwd"
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(absolute, bound)
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT


def test_posix_absolute_path_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """``/etc/passwd``.

    On Windows a leading ``/`` is drive-relative, not absolute, so the refusal
    is ``relative_without_root`` — still a refusal, which is the property that
    matters. On POSIX it is absolute and refused as outside every root.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize("/etc/passwd", bound)
    assert caught.value.rejection in {
        PathRejection.RELATIVE_WITHOUT_ROOT,
        PathRejection.OUTSIDE_EVERY_ROOT,
    }


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "escaped",
    [
        "..%2f..%2foutside%2ftarget.txt",
        "..%2Fsecret.txt",
        "%2e%2e%2fok.txt",
        "ok.txt%3a-hidden",
        "%252e%252e%252f",  # double-encoded
    ],
)
def test_percent_encoded_traversal_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]], escaped: str
) -> None:
    """Percent-escapes that decode to a separator or dot are refused.

    This process never percent-decodes a path, so ``%2f`` is a legal filename
    here. The refusal is about the *string* — it is what gets logged, rendered
    into a report, or handed to a future URL-shaped consumer, any of which might
    decode it.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(escaped, bound)
    assert caught.value.rejection is PathRejection.ENCODED_TRAVERSAL


def test_percent_escape_that_is_not_structural_is_allowed(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """``%20`` decodes to a space, which is not structural.

    Guards against the encoded-traversal check over-firing into a blanket ban
    on ``%``, which would refuse legitimate file names.
    """
    allowed, bound = roots
    (allowed / "a%20b.txt").write_text("x", encoding="utf-8")
    canonical = canonicalize(allowed / "a%20b.txt", bound)
    assert canonical.resolved_key == "a%20b.txt"


def test_unicode_separator_smuggling_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """FULLWIDTH SOLIDUS normalises to ``/`` under NFKC.

    Not a separator to the OS, so it would be a perfectly ordinary filename —
    but anything that normalises the string before comparing it sees a
    separator. One spelling of a path has to have one meaning.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize("sub\uff0f..\uff0foutside\uff0ftarget.txt", bound)
    assert caught.value.rejection is PathRejection.SEPARATOR_SMUGGLING


def test_unicode_normalisation_does_not_change_the_stored_key(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """NFC/NFD spellings of one name produce one key.

    APFS stores NFD and most other filesystems store NFC, so the *same* file
    arrives spelled two ways depending on the machine. The resolved key must not
    vary, or the §C4 digest would differ for one file across two machines.
    """
    allowed, bound = roots
    composed = "caf\u00e9.txt"  # e-acute as one code point (NFC)
    decomposed = "caf\u00e9.txt"  # e + combining acute (NFD)
    assert unicodedata.normalize("NFC", decomposed) == composed

    (allowed / composed).write_text("x", encoding="utf-8")
    canonical = canonicalize(allowed / composed, bound)

    assert canonical.resolved_key == unicodedata.normalize("NFC", canonical.resolved_key)
    assert canonical.resolved_key == composed


@requires_windows
def test_invisible_unicode_characters_are_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """ZERO WIDTH SPACE and RIGHT-TO-LEFT OVERRIDE make one name *render* as another."""
    _, bound = roots
    for name in ("ok\u200b.txt", "ok\u202eexe.txt", "ok\u00ad.txt"):
        with pytest.raises(PathRefusedError) as caught:
            canonicalize(name, bound)
        assert caught.value.rejection is PathRejection.INVISIBLE_CHARACTER


@requires_windows
def test_nul_byte_is_refused(roots: tuple[Path, tuple[AllowedRoot, ...]]) -> None:
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize("ok.txt\x00.png", bound)
    assert caught.value.rejection is PathRejection.NUL_BYTE


# ---------------------------------------------------------------------------
# Windows spellings that alias
# ---------------------------------------------------------------------------


@requires_windows
def test_trailing_dot_alias_is_refused(roots: tuple[Path, tuple[AllowedRoot, ...]]) -> None:
    """``secret.txt.`` is the same file as ``secret.txt``.

    The first assertion proves the hazard is real on this filesystem — without
    it, the refusal could be passing for an unrelated reason.
    """
    allowed, bound = roots
    assert (allowed / "secret.txt.").samefile(allowed / "secret.txt"), (
        "the trailing-dot alias is the whole point of this test; if Windows does "
        "not alias it here, the fixture is not testing what it claims"
    )
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed / "secret.txt.", bound)
    assert caught.value.rejection is PathRejection.TRAILING_DOT_OR_SPACE


@requires_windows
def test_trailing_space_alias_is_refused(roots: tuple[Path, tuple[AllowedRoot, ...]]) -> None:
    allowed, bound = roots
    assert (allowed / "secret.txt ").samefile(allowed / "secret.txt")
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed / "secret.txt ", bound)
    assert caught.value.rejection is PathRejection.TRAILING_DOT_OR_SPACE


@requires_windows
def test_alternate_data_stream_syntax_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """``secret.txt:stream`` would write a hidden stream on the source file.

    The proof writes one, inside the fixture, and shows the main stream is
    unchanged — the failure mode is invisible to anything that reads the file.
    """
    allowed, bound = roots
    stream = Path(str(allowed / "secret.txt") + ":probe")
    try:
        with stream.open("w", encoding="utf-8") as handle:
            handle.write("smuggled")
        assert (allowed / "secret.txt").read_text(encoding="utf-8") == "secret"
    except OSError as exc:  # pragma: no cover - only on a filesystem without ADS
        pytest.skip(f"alternate data streams unavailable here: {exc}")

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(str(allowed / "secret.txt") + ":stream", bound)
    assert caught.value.rejection is PathRejection.ALTERNATE_DATA_STREAM


@requires_windows
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\\\\?\\E:\\temp\\x", PathRejection.EXTENDED_LENGTH_PREFIX),
        ("\\\\.\\PhysicalDrive0", PathRejection.DEVICE_NAMESPACE),
        ("\\\\server\\share\\x", PathRejection.REMOTE_ROOT),
    ],
)
def test_windows_namespace_prefixes_are_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]], raw: str, expected: PathRejection
) -> None:
    """``\\\\?\\``, ``\\\\.\\`` and UNC are namespace syntax, not path syntax.

    ``\\\\?\\`` is the subtle one: it **survives** ``Path.resolve()`` verbatim,
    so the same file spelled with and without it produces two different
    canonical strings — and ADR-0003 §C4 computes a digest over that string.
    """
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(raw, bound)
    assert caught.value.rejection is expected


@requires_windows
def test_extended_length_prefix_really_does_change_the_resolved_string(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """Proves the ``\\\\?\\`` hazard rather than asserting it from memory."""
    allowed, _ = roots
    plain = (allowed / "ok.txt").resolve()
    extended = Path("\\\\?\\" + str(allowed / "ok.txt")).resolve()
    assert str(plain) != str(extended), (
        "if resolve() normalised the prefix away, the refusal would be "
        "unnecessary; the test is asserting the opposite"
    )


@requires_windows
def test_8_3_short_name_is_expanded_by_resolve() -> None:
    """A real short name, checked against the platform rather than assumed.

    ``C:\\PROGRA~1`` is the genuine 8.3 alias for ``C:\\Program Files`` on this
    machine. Note the scope honestly: 8.3 generation is **disabled on the
    volume these tests use** (``dir /x`` shows no short-name column), so a
    short-name alias cannot be minted inside a fixture here. What *can* be
    tested is that the canonicaliser inherits the expansion the OS performs,
    which is the part LabCairn depends on.
    """
    short = Path("C:/PROGRA~1")
    if not short.exists():  # pragma: no cover - depends on the machine's C:
        pytest.skip("C:/PROGRA~1 does not exist on this machine")
    resolved = short.resolve()
    assert resolved == Path("C:/Program Files"), (
        f"expected resolve() to expand the 8.3 alias, got {resolved}"
    )
    assert "PROGRA~1" not in str(resolved)


@requires_windows
def test_a_new_file_under_a_short_spelled_root_is_not_refused(tmp_path: Path) -> None:
    r"""A new file under a short-spelled root is under the root.

    **This is the defect the earlier gates' own witness found.** G1's exit
    demonstration runs on a Windows CI runner, whose temp directory is
    spelled in the 8.3 short form (``C:\Users\RUNNER~1\...``) while the
    workspace root is spelled long (``C:\Users\runneradmin\...``). A
    **new** file under a short-spelled directory keeps the short spelling,
    because there is nothing for the OS to expand, while the root -- which
    exists -- comes back long-spelled. The two spellings name one directory
    and the comparison between them failed, so a file plainly under the root
    was refused as being outside every root.

    The proof that it is under the root is not the comparison that failed;
    it is that the **resolved** path is under it. The key names the tail
    below the root, and the tail is the same in both spellings.

    **The scope is honest.** 8.3 generation is **disabled on the volume
    these tests use**, so on a machine without it there is no short name to
    mint and the test skips -- which is exactly why the defect survived
    from G1 to G5. A Windows CI runner *does* have short names, and there
    this test runs.
    """
    short = _short_name(tmp_path)
    if short is None or str(short) == str(tmp_path):
        pytest.skip("this machine's volume has no 8.3 short names")

    root = Path(short) / "root"
    root.mkdir(parents=True, exist_ok=True)
    bound = bind_root("root", root, RootKind.OUTPUT)

    # A file that does not exist yet: the short spelling is all it has.
    new_file = Path(short) / "root" / "outputs" / "summary.md"
    (Path(short) / "root" / "outputs").mkdir(parents=True, exist_ok=True)

    canonical = canonicalize(new_file, (bound,))
    assert canonical.declared_key == "outputs/summary.md", (
        f"the key should name the tail below the root, got {canonical.declared_key!r}"
    )
    assert canonical.resolved_key == "outputs/summary.md", (
        f"the resolved key should name the same tail, got {canonical.resolved_key!r}"
    )


@requires_windows
def test_a_path_outside_a_short_spelled_root_is_still_refused(tmp_path: Path) -> None:
    r"""The widening is a widening, and not a hole.

    **The same comparison, the other way round.** A path that is *not* under
    the root must still be refused, and refused as being outside every root
    -- not quietly accepted because the two spellings happened to differ.

    This is the witness for the part of the fix that matters most: the
    fallback takes the tail only when the **resolved** path is under the
    root, and this is what says the fallback is not taken otherwise.
    """
    short = _short_name(tmp_path)
    if short is None or str(short) == str(tmp_path):
        pytest.skip("this machine's volume has no 8.3 short names")

    root = Path(short) / "root"
    root.mkdir(parents=True, exist_ok=True)
    bound = bind_root("root", root, RootKind.OUTPUT)

    outside = Path(short) / "elsewhere" / "secret.md"
    (Path(short) / "elsewhere").mkdir(parents=True, exist_ok=True)

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(outside, (bound,))
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT, (
        f"a path outside the root must be refused as outside every root, got "
        f"{caught.value.rejection}"
    )


def _short_name(path: Path) -> Path | None:
    """The 8.3 short spelling of *path*, or ``None`` if there is not one.

    **The OS is asked, not guessed.** A short name is one part either way
    and it exists only where the volume generates them, so a spelling
    invented here would be a spelling of nothing.
    """
    if not IS_WINDOWS:  # pragma: no cover - the caller skips it
        return None
    import ctypes

    # `ctypes.windll` exists on Windows and nowhere else, and **the type
    # checker knows that**. A `# type: ignore` would be right on one platform
    # and wrong on the other -- "unused" where the attribute is there, and
    # "missing" where it is not -- and the wrong one is a red build on the
    # other platform. So the attribute is read the way a platform that may
    # not have it has to be read.
    windll = getattr(ctypes, "windll", None)
    if windll is None:  # pragma: no cover - only on a POSIX build
        return None

    buffer = ctypes.create_unicode_buffer(4096)
    length = windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        return None
    return Path(buffer.value)


# ---------------------------------------------------------------------------
# Symlinks and junctions
# ---------------------------------------------------------------------------


@requires_windows
def test_a_junction_is_not_reported_as_a_symlink(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """The reason the guard is resolve-then-check rather than ``is_symlink``.

    If this assertion ever fails, the junction tests below are testing
    something different from what they claim.
    """
    allowed, _ = roots
    outside = allowed.parent / "outside"
    link = allowed / "escape"
    make_junction(link, outside)

    assert link.is_symlink() is False, (
        "Path.is_symlink() returning True for a junction would mean the "
        "is_symlink-based approach was viable and this file's premise is wrong"
    )
    assert link.is_dir() is True
    assert link.resolve() == outside.resolve(), (
        "resolve() must follow the junction; it is the only thing that does"
    )


@requires_windows
def test_junction_escaping_the_root_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """The headline case: a path whose *declared* spelling is inside the root.

    Every prefix of ``allowed/escape/target.txt`` passes a containment test on
    the unresolved spelling. Only following the junction reveals that it lands
    outside.
    """
    allowed, bound = roots
    outside = allowed.parent / "outside"
    make_junction(allowed / "escape", outside)

    declared = allowed / "escape" / "target.txt"
    assert declared.is_relative_to(allowed), "the declared spelling is inside"

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(declared, bound)
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT


@requires_windows
def test_symlink_escaping_the_root_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    allowed, bound = roots
    outside = allowed.parent / "outside" / "target.txt"
    (allowed / "sub" / "alias.txt").symlink_to(outside)
    assert (allowed / "sub" / "alias.txt").is_symlink()

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed / "sub" / "alias.txt", bound)
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT


@requires_windows
def test_symlinked_parent_directory_mid_path_is_refused(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """The link is in a *middle* segment, so only full resolution finds it."""
    allowed, bound = roots
    outside = allowed.parent / "outside"
    (allowed / "sub" / "hop").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed / "sub" / "hop" / "target.txt", bound)
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT


@requires_windows
def test_junction_pointing_back_inside_the_root_is_admitted(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """The complement: a junction that stays inside must not be refused.

    Without this, "refuse everything with a link in it" would pass every escape
    test above while making the feature useless. The target here is a real file
    reached *through* the junction, which is the case that has to keep working.
    """
    allowed, bound = roots
    (allowed / "sub" / "inner.txt").write_text("inner", encoding="utf-8")
    make_junction(allowed / "inside_hop", allowed / "sub")

    canonical = canonicalize(allowed / "inside_hop" / "inner.txt", bound)
    assert canonical.resolved_key == "sub/inner.txt"
    assert canonical.real_path == allowed / "sub" / "inner.txt"


@requires_windows
def test_both_spellings_are_reported_so_policy_can_match_each(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """A link inside the root gives two different, both-meaningful keys.

    ADR-0003 §C5 requires the declared path *and* the resolved target to be
    matched. The declared spelling is what a rule about the link's own name
    catches; the resolved key is what a rule about the real file catches.
    """
    allowed, bound = roots
    link = allowed / "alias.txt"
    link.symlink_to(allowed / "secret.txt")

    canonical = canonicalize(link, bound)
    assert canonical.declared_key == "alias.txt"
    assert canonical.resolved_key == "secret.txt"
    assert canonical.declared_key != canonical.resolved_key


@requires_windows
def test_symlink_loop_is_refused_rather_than_crashing(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """``pathlib`` raises ``RuntimeError`` here, not ``OSError``.

    A handler catching only ``OSError`` would let it escape as an unhandled
    crash — still a refusal in effect, but one that never reaches the event log.
    """
    allowed, bound = roots
    loop = allowed / "loop"
    try:
        loop.symlink_to(loop, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - depends on OS policy
        pytest.skip(f"self-symlink refused by the OS: {exc}")

    with pytest.raises(PathRefusedError) as caught:
        canonicalize(loop, bound)
    assert caught.value.rejection is PathRejection.CANONICALISATION_FAILED


# ---------------------------------------------------------------------------
# Case sensitivity
# ---------------------------------------------------------------------------


@requires_windows
def test_case_variant_of_a_path_inside_the_root_is_admitted(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """Windows is case-insensitive, so ``OK.TXT`` is ``ok.txt``.

    Refusing it would be fail-safe but useless; admitting it is correct, and it
    is what makes the *case-insensitive deny* below meaningful.
    """
    allowed, bound = roots
    canonical = canonicalize(allowed / "OK.TXT", bound)
    assert canonical.real_path.name == "ok.txt"
    assert canonical.resolved_key == "ok.txt"


@requires_windows
def test_case_variant_cannot_escape_a_case_insensitive_check(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """A deny rule must bite regardless of the casing used to reach the file.

    The rule is matched against the *resolved* key, and ``resolve()`` returns
    the filesystem's own casing, so a rule written in lower case still fires.
    """
    allowed, bound = roots
    canonical = canonicalize(allowed / "SECRET.TXT", bound)
    assert canonical.resolved_key == "secret.txt"


# ---------------------------------------------------------------------------
# Roots
# ---------------------------------------------------------------------------


def test_a_root_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """A root that had to be invented is not one the user selected."""
    with pytest.raises(PathRefusedError) as caught:
        bind_root("ghost", tmp_path / "not-created", RootKind.OUTPUT)
    assert caught.value.rejection is PathRejection.CANONICALISATION_FAILED


def test_a_file_is_not_a_root(tmp_path: Path) -> None:
    target = tmp_path / "a-file.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(PathRefusedError) as caught:
        bind_root("file", target, RootKind.OUTPUT)
    assert caught.value.rejection is PathRejection.DEGENERATE


def test_no_roots_admits_nothing(tmp_path: Path) -> None:
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(tmp_path / "anything", ())
    assert caught.value.rejection is PathRejection.OUTSIDE_EVERY_ROOT


def test_the_root_itself_is_not_a_resource(tmp_path: Path) -> None:
    """A key must name a resource, not the container it sits in."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    bound = (bind_root("allowed", allowed, RootKind.OUTPUT),)
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(allowed, bound)
    assert caught.value.rejection is PathRejection.DEGENERATE


def test_the_most_specific_root_wins(tmp_path: Path) -> None:
    """A nested root governs its own subtree, not the outer one."""
    outer = tmp_path / "ws"
    inner = outer / "sources"
    inner.mkdir(parents=True)
    (inner / "a.pdf").write_bytes(b"%PDF-")

    outer_root = bind_root("ws", outer, RootKind.OUTPUT)
    inner_root = bind_root("sources", inner, RootKind.SOURCE)
    roots = (outer_root, inner_root)

    canonical = canonicalize(inner / "a.pdf", roots)
    assert canonical.root_id == "sources"
    assert canonical.root_kind is RootKind.SOURCE


def test_moving_from_one_root_to_another_is_refused(tmp_path: Path) -> None:
    """Cross-root movement is refused even when both roots are permitted.

    A source root holding a junction to the output area: the destination is
    allowed, but the caller evaluated against the source root's rules, so the
    request is refused rather than silently reinterpreted.
    """
    outer = tmp_path / "ws"
    sources = outer / "sources"
    out = outer / "output"
    sources.mkdir(parents=True)
    out.mkdir(parents=True)
    (out / "planted.txt").write_text("planted", encoding="utf-8")

    roots = (
        bind_root("sources", sources, RootKind.SOURCE),
        bind_root("output", out, RootKind.OUTPUT),
    )

    (sources / "hop").symlink_to(out, target_is_directory=True)
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(sources / "hop" / "planted.txt", roots)
    assert caught.value.rejection is PathRejection.CROSS_ROOT


# ---------------------------------------------------------------------------
# Empty / malformed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "\t", "\n"])
def test_empty_paths_are_refused(roots: tuple[Path, tuple[AllowedRoot, ...]], raw: str) -> None:
    _, bound = roots
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(raw, bound)
    assert caught.value.rejection in {PathRejection.EMPTY, PathRejection.INVISIBLE_CHARACTER}


def test_every_rejection_is_a_denial_and_never_an_ask(
    roots: tuple[Path, tuple[AllowedRoot, ...]],
) -> None:
    """ADR-0003 §C4: *a path that cannot be canonicalised is a deny, not an ask*.

    Asserted structurally over the enum rather than by trusting each test above
    to have covered its member: every value of :class:`PathRejection` is a
    terminal outcome, and none of them maps to "ask".
    """
    for rejection in PathRejection:
        assert "ask" not in rejection.value
        assert "allow" not in rejection.value


def test_resource_key_rejects_a_path_longer_than_the_operation_field(tmp_path: Path) -> None:
    """The key is fed straight into ``Operation.resource_key`` (max 2000)."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    bound = (bind_root("allowed", allowed, RootKind.OUTPUT),)
    deep = allowed / "/".join("d" * 200 for _ in range(12))
    with pytest.raises(PathRefusedError) as caught:
        canonicalize(deep, bound)
    assert caught.value.rejection is PathRejection.DEGENERATE
