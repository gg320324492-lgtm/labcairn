"""Path canonicalisation: the wall an escaped path hits.

Everything here exists to answer one question about a path a caller handed us:
*which real file does this name, after the filesystem has had its say?* The
answer has to be the real one, because the declared spelling and the real file
diverge in ways that are invisible to a string comparison.

Why this module is so long, and why it re-checks after resolving
-------------------------------------------------------------------
``docs/adr/ADR-0003`` §C4 fixes the rule — *both the declared path and its
symlink/junction-resolved target are matched* — and every oddity below is a
concrete instance of "the declared spelling is not the file". Measured on this
machine (Windows 11, CPython 3.12), not assumed:

* **A junction is not a symlink.** ``Path.is_symlink()`` returns ``False`` for a
  directory junction, so an ``is_symlink``-based guard walks straight past one.
  ``Path.resolve()`` *does* follow it. Only resolve-then-check works.
* **Trailing dots and spaces alias.** ``secret.txt.`` and ``secret.txt`` are
  the same file, so a deny rule written against the clean spelling can be
  evaded by appending a dot. ``resolve()`` strips the alias for an *existing*
  target, but a *new* file keeps it — and Win32 creates the clean name.
* **``file.txt:stream`` is not a new file.** ``open()`` writes an NTFS alternate
  data stream: the write succeeds, the main stream is unchanged, and a caller
  inspecting the source file sees nothing happened.
* **8.3 short names are expanded by ``resolve()``**, but only via the OS, so
  the guarantee is a platform property rather than one of this module's. It is
  tested here against a real short name (``C:\\PROGRA~1``) rather than claimed.
* **``\\\\?\\`` survives ``resolve()``**, so two spellings of one file produce
  two different strings. Device paths (``\\\\.\\``) reach hardware.
* **Fullwidth separators normalise to ``/``** under NFKC, so a path can look
  unlike a separator and compare equal to one.

The design consequence is the same everywhere: **reject the ambiguous spelling
before it can be compared, then resolve, then check containment again.** A
single check is not enough — ``is_relative_to`` on the unresolved spelling
passes for a junction escape, which is precisely the bypass §C4 forbids.

Failing closed
--------------
:func:`canonicalize` either returns a :class:`CanonicalPath` or **raises**
:class:`PathRefusedError`. It does not return an "inconclusive" result, because a
caller that forgets to check a returned sentinel is a silent bypass; a raised
exception cannot be stepped over without a traceback.

Per §C4, *a path that cannot be canonicalised is a deny, not an ask.* A
symlink loop, an unresolvable drive, a permission error on a parent — all raise
:class:`PathRefusedError` with :data:`PathRejection.CANONICALISATION_FAILED`.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Final

from pydantic import StringConstraints

#: Mirrors ``Operation.resource_key``'s ``max_length`` in
#: :mod:`labcairn.runtime.operation`. The key this module produces is fed
#: straight into that field, so the bound is a contract, not a preference.
MAX_RESOURCE_KEY_LEN: Final = 2000

#: A workspace-relative, POSIX-separated canonical resource key.
#:
#: Pattern-constrained rather than a bare ``str`` so that free prose is *not
#: assignable*: ADR-0003 §C6.1 requires that no value reaching a permission
#: decision can carry document or excerpt text, and a type that accepts any
#: string cannot make that promise. The pattern admits only printable
#: ASCII-ish path characters, so a paragraph of injected instructions does not
#: type-check into a resource key.
ResourceKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_RESOURCE_KEY_LEN,
        pattern=r"^[^\\:*?\x00-\x1f]+$",
    ),
]


class RootKind(StrEnum):
    """What a bound root is *for*.

    The distinction is a security boundary, not a label: ``SOURCE`` roots are
    supplied by the user and are never written to, ``OUTPUT`` roots are created
    by LabCairn for one task and are the only place a write may land.
    """

    #: Supplied source material. Read-only by construction, not by convention.
    SOURCE = "source"
    #: The dedicated output area for one task.
    OUTPUT = "output"


class PathRejection(StrEnum):
    """Why a path was refused. Enumerated so callers and tests can branch.

    Every value here is a **deny**. There is no "refused but askable" outcome:
    §C4 puts uncanonicalisable paths in deny, and nothing in this module
    produces an ``ask``.
    """

    #: The path was empty or all whitespace.
    EMPTY = "empty"
    #: An embedded NUL. ``pathlib`` raises on these, but the refusal has to be
    #: ours so the caller sees a :class:`PathRefusal` rather than a bare ValueError.
    NUL_BYTE = "nul_byte"
    #: A Unicode control (Cc) or format (Cf) character. These are the invisible
    #: characters a right-to-left override or a zero-width joiner uses to make
    #: one filename *render* as another.
    INVISIBLE_CHARACTER = "invisible_character"
    #: A segment ending in a dot or a space, which Win32 silently strips.
    TRAILING_DOT_OR_SPACE = "trailing_dot_or_space"
    #: A ``:`` inside a segment: the NTFS alternate-data-stream syntax.
    ALTERNATE_DATA_STREAM = "alternate_data_stream"
    #: A character that normalises to ``/`` or ``\`` under NFKC (fullwidth forms).
    SEPARATOR_SMUGGLING = "separator_smuggling"
    #: A ``\\?\`` extended-length prefix.
    EXTENDED_LENGTH_PREFIX = "extended_length_prefix"
    #: A ``\\.\`` device-namespace path, which addresses hardware not files.
    DEVICE_NAMESPACE = "device_namespace"
    #: A UNC ``\\server\share`` root.
    REMOTE_ROOT = "remote_root"
    #: A percent-escape that decodes to a structural character.
    ENCODED_TRAVERSAL = "encoded_traversal"
    #: A relative path with no root to resolve it against. §C5 makes absolute
    #: paths mandatory at the boundary precisely so this cannot happen quietly.
    RELATIVE_WITHOUT_ROOT = "relative_without_root"
    #: The path resolved, but to somewhere no bound root contains.
    OUTSIDE_EVERY_ROOT = "outside_every_root"
    #: The path resolved into a *different* root than the one it was declared
    #: under. Cross-root movement is refused even when both roots are allowed,
    #: because the destination root's rules were never consulted by the caller.
    CROSS_ROOT = "cross_root"
    #: ``resolve()`` failed: symlink loop, unavailable volume, unreadable parent.
    CANONICALISATION_FAILED = "canonicalisation_failed"
    #: The path was resolvable but is not a usable target (empty after
    #: normalisation, or a segment that vanished).
    DEGENERATE = "degenerate"


class PathRefusedError(ValueError):
    """A path that cannot be admitted, and why.

    A :class:`ValueError` because every caller treats it as a bad argument, but
    carrying :attr:`rejection` so policy evaluation and the event log can record
    a machine-readable reason rather than a prose message.
    """

    def __init__(self, rejection: PathRejection, detail: str) -> None:
        super().__init__(f"{rejection.value}: {detail}")
        self.rejection = rejection
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AllowedRoot:
    """One root the workspace explicitly bound.

    :attr:`path` must already be resolved with ``strict=True``: a root that
    cannot be canonicalised is not a root, because every containment decision
    below is made relative to it. :func:`bind_root` is the only supported way to
    make one.
    """

    root_id: str
    path: Path
    kind: RootKind


@dataclass(frozen=True, slots=True)
class CanonicalPath:
    """A path that survived canonicalisation, in both of its spellings.

    Both spellings are kept because §C5 matches on *both* the declared path and
    the symlink/junction-resolved target, and a policy that can only see one of
    them is blind to the other. ``declared_key`` is what the caller asked for;
    ``resolved_key`` is what the filesystem will actually open.
    """

    #: As-declared, made absolute against the root it was declared under and
    #: collapsed lexically. **Not** symlink-resolved: this is the caller's
    #: spelling, and matching it is how a rule aimed at ``sources/`` catches a
    #: symlink that claims to be somewhere else.
    declared_key: ResourceKey
    #: Fully resolved, symlinks and junctions followed, relative to the root it
    #: landed in.
    resolved_key: ResourceKey
    #: Absolute real path. Safe to open **after** re-checking containment,
    #: because between the check and the open the tree could have changed.
    real_path: Path
    #: Absolute path implied by the declared spelling, without following links.
    declared_path: Path
    #: The root the resolved path landed in.
    root_id: str
    root_kind: RootKind


# ---------------------------------------------------------------------------
# Spelling rejection
# ---------------------------------------------------------------------------

_PERCENT_ESCAPE: Final = re.compile(r"%([0-9A-Fa-f]{2})")
#: Decoding one of these turns an ordinary-looking name into a structural one.
_STRUCTURAL_BYTES: Final = frozenset(b"/\\.%:|")


def _check_no_nul(value: str) -> None:
    if "\x00" in value:
        raise PathRefusedError(PathRejection.NUL_BYTE, "path contains a NUL byte")


def _check_invisible(value: str) -> None:
    """Reject Cc and Cf characters.

    Neither class has a legitimate use in a path LabCairn reads or generates,
    and both are the delivery mechanism for homograph tricks: a right-to-left
    override makes ``evil\u202eexe`` display as ``exe\u202ebile``. Rejecting the
    whole class rather than a hand-picked list is deliberate — a new invisible
    codepoint added by Unicode must not become a new bypass.
    """
    for index, char in enumerate(value):
        if unicodedata.category(char) in {"Cc", "Cf"} and char not in ("\t",):
            raise PathRefusedError(
                PathRejection.INVISIBLE_CHARACTER,
                f"path contains U+{ord(char):04X} at position {index}, a Unicode "
                f"control or format character (category {unicodedata.category(char)})",
            )


def _check_segments(value: str, *, separators: str) -> None:
    """Per-segment checks: trailing dot/space, ADS colon, NFKC smuggling.

    The caller passes only the path *after* its drive or UNC root. That matters:
    ``C:\\Windows`` has a segment containing ``:``, and without the split every
    absolute Windows path would be refused as alternate-data-stream syntax —
    which would break the legitimate absolute paths ADR-0003 §C5 *requires* at
    the boundary, not just the hostile ones.
    """
    for raw_segment in re.split(f"[{re.escape(separators)}]", value):
        if not raw_segment:
            continue
        # NFKC first: FULLWIDTH SOLIDUS (U+FF0F) and FULLWIDTH REVERSE SOLIDUS
        # (U+FF3C) are not separators to the OS but *are* separators to anything
        # that normalises, so a name containing one can compare equal to a name
        # containing a real separator.
        segment = unicodedata.normalize("NFKC", raw_segment)
        if "/" in segment or "\\" in segment:
            raise PathRefusedError(
                PathRejection.SEPARATOR_SMUGGLING,
                f"segment {raw_segment!r} normalises to {segment!r}, which contains a "
                f"path separator. Only ASCII separators are accepted so that one "
                f"spelling of a path has exactly one meaning.",
            )
        if segment in (".", ".."):
            # Dot segments are legitimate *spelling*: `root/sub/../sub/ok.txt`
            # is a real, contained path, and resolve() collapses them against
            # the filesystem rather than lexically. Whether `..` escapes the
            # root is decided by the containment check, not here — which is why
            # they must not be caught by the trailing-dot rule below.
            continue
        if segment != segment.rstrip(". "):
            raise PathRefusedError(
                PathRejection.TRAILING_DOT_OR_SPACE,
                f"segment {raw_segment!r} ends in a dot or space. Win32 strips both, "
                f"so 'secret.txt.' and 'secret.txt' are the same file and a rule "
                f"written against one spelling would miss the other.",
            )
        # The drive colon was removed by the caller, so any colon still present
        # is alternate-data-stream syntax.
        if ":" in segment:
            raise PathRefusedError(
                PathRejection.ALTERNATE_DATA_STREAM,
                f"segment {raw_segment!r} contains ':'. On NTFS that is alternate "
                f"data stream syntax: open() would write a hidden stream on the "
                f"target file and leave the visible content untouched.",
            )


def _check_prefixes(value: str) -> None:
    """Reject ``\\\\?\\``, ``\\\\.\\`` and UNC roots.

    All three are Windows *namespace* prefixes rather than ordinary path
    syntax. ``\\\\?\\`` survives ``resolve()`` verbatim, so a path spelled with it
    and one spelled without it are different strings naming the same file — and
    the digest in ADR-0003 §C4 is computed over that string. ``\\\\.\\`` addresses
    devices. UNC addresses another machine, which a local-first workbench has no
    business reading silently.
    """
    lowered = value.lower()
    if lowered.startswith(("\\\\?\\", "\\\\??\\")):
        raise PathRefusedError(
            PathRejection.EXTENDED_LENGTH_PREFIX,
            "path uses the \\\\?\\ extended-length prefix. It survives resolve() and "
            "changes the canonical spelling of the same file, which would make two "
            "spellings of one resource produce two different digests.",
        )
    if lowered.startswith("\\\\.\\"):
        raise PathRefusedError(
            PathRejection.DEVICE_NAMESPACE,
            "path uses the \\\\.\\ device namespace, which addresses devices rather than files.",
        )
    if lowered.startswith("\\\\") or value.startswith("//"):
        raise PathRefusedError(
            PathRejection.REMOTE_ROOT,
            "path is a UNC/remote root. Phase 1 is local-first: a workspace never "
            "reads another machine's filesystem.",
        )


def _check_percent_encoding(value: str) -> None:
    """Refuse percent-escapes that decode to something structural.

    LabCairn never percent-decodes a path, so ``%2e%2e%2f`` is a perfectly good
    *filename* here. It is refused anyway: the value that gets stored in an
    event, logged, rendered into a report or handed to a future URL-shaped
    consumer is the literal string, and any one of those consumers decoding it
    turns a filename into a traversal. Refusing the spelling at the boundary is
    the only place the decision can be made once.
    """
    for match in _PERCENT_ESCAPE.finditer(value):
        decoded = bytes([int(match.group(1), 16)])
        if decoded[0] in _STRUCTURAL_BYTES:
            raise PathRefusedError(
                PathRejection.ENCODED_TRAVERSAL,
                f"path contains the escape {match.group(0)!r}, which decodes to "
                f"{decoded!r}. Percent-escaped separators and dots are refused at "
                f"the boundary even though this process never decodes them, because "
                f"a downstream consumer might.",
            )


def _reject_hostile_spelling(value: str) -> str:
    """Every spelling check, in order, returning the NFC-normalised path.

    NFC rather than NFKC is the normalisation applied to the *result*: NFKC is
    used above purely as a **detector** (does this name secretly contain a
    separator?), because it folds away distinctions — ``①`` and ``1`` — that a
    real file name may legitimately use. The stored key is NFC so the same file
    yields the same string on a machine that stores NFC and one that stores NFD.
    """
    if not value or not value.strip():
        raise PathRefusedError(PathRejection.EMPTY, "path is empty or whitespace only")
    _check_no_nul(value)
    _check_invisible(value)
    _check_prefixes(value)
    _check_percent_encoding(value)
    # Strip the drive or UNC root before per-segment checks, so the colon in
    # `C:` is not mistaken for alternate-data-stream syntax. `_check_prefixes`
    # has already refused UNC and namespace paths, so what remains is either a
    # drive spec or nothing.
    drive, remainder = os.path.splitdrive(value)
    del drive
    _check_segments(remainder, separators="/\\")
    return unicodedata.normalize("NFC", value)


def check_spelling(value: str) -> str:
    """The spelling guard, asked on its own.

    **The guard answers about the spelling; the filesystem answers about the
    file.** A caller that has a name it cannot speak must ask this first,
    because the filesystem's answer to such a name is not an answer at all:
    ``Path.resolve()`` on a name carrying a NUL byte raises a bare
    ``ValueError``, and a bare ``ValueError`` is a crash where the caller
    promised a refusal. :class:`PathRefusedError` is the same refusal the
    rest of this module raises, and it says which spelling it was.

    :param value: the name as the caller wrote it.
    :returns: the NFC-normalised spelling of *value*.
    :raises PathRefusedError: *value* is a spelling this build cannot speak —
        a NUL byte in it, an invisible character, a segment that ends in a
        dot, an alternate-data-stream colon, a percent-escape that decodes to
        a structural character, a namespace or UNC prefix.
    """
    return _reject_hostile_spelling(value)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def bind_root(root_id: str, path: Path, kind: RootKind) -> AllowedRoot:
    """Resolve a root once, strictly, and refuse it if that is not possible.

    ``strict=True`` is the point. A root that does not exist yet cannot contain
    anything, and a root that resolves through a broken link is not the place
    the operator selected — admitting it would make every later containment
    decision relative to something that does not exist.
    """
    if not root_id:
        raise PathRefusedError(PathRejection.EMPTY, "root_id is empty")
    try:
        real = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PathRefusedError(
            PathRejection.CANONICALISATION_FAILED,
            f"root {root_id!r} at {path} could not be resolved strictly: {exc}",
        ) from exc
    if not real.is_dir():
        raise PathRefusedError(
            PathRejection.DEGENERATE,
            f"root {root_id!r} at {path} resolved to {real}, which is not a directory",
        )
    return AllowedRoot(root_id=root_id, path=real, kind=kind)


def _resolve_or_refuse(candidate: Path) -> Path:
    """``Path.resolve()`` with every documented failure turned into a refusal.

    ``RuntimeError`` matters as much as ``OSError`` here: a symlink loop raises
    ``RuntimeError`` from ``pathlib.check_eloop``, verified on this machine. A
    handler that caught only ``OSError`` would let it escape as a crash — still
    a refusal in effect, but an uncontrolled one that bypasses the event log.
    """
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PathRefusedError(
            PathRejection.CANONICALISATION_FAILED,
            f"{candidate} could not be canonicalised: {exc}. ADR-0003 C4: a path "
            f"that cannot be canonicalised is a deny, not an ask.",
        ) from exc
    if not str(resolved):
        raise PathRefusedError(PathRejection.DEGENERATE, f"{candidate} resolved to nothing")
    return resolved


def _is_within(candidate: Path, root: Path) -> bool:
    """Containment by component, case-folded on Windows.

    ``Path.is_relative_to`` is used rather than a string prefix test, because a
    string test makes ``E:/root-evil`` count as inside ``E:/root``. On Windows
    ``PurePath`` already compares case-insensitively; the explicit
    ``os.path.normcase`` keeps that property from depending on the flavour
    object remaining the one that implements it.
    """
    try:
        inside = candidate.is_relative_to(root)
    except ValueError:  # different drives on Windows
        return False
    if inside:
        return True
    if os.name == "nt":
        return os.path.normcase(str(candidate)).startswith(
            os.path.normcase(str(root)) + os.sep
        ) and candidate.is_relative_to(root)
    return False


def _root_for(candidate: Path, roots: tuple[AllowedRoot, ...]) -> AllowedRoot | None:
    """The most specific root containing *candidate*, or ``None``.

    "Most specific" is longest-path-wins, so a workspace root and a source root
    nested inside it attribute the path to the source root — whose read-only
    rule is the one that should decide what happens to it.
    """
    matches = [root for root in roots if _is_within(candidate, root.path)]
    if not matches:
        return None
    return max(matches, key=lambda root: len(root.path.parts))


def _tail_below(candidate: Path, root: AllowedRoot, resolved: Path | None, exc: ValueError) -> Path:
    """The tail of *candidate* below *root*, or the refusal it already was.

    **This is the whole of the widening, and it is why it is safe.** The
    tail is only taken when the **resolved** path is under the root — that
    is the proof that the candidate is under it, and it is the proof the
    caller already has, because it found the resolved root by exactly that
    test. Without that proof, or without a resolved path at all, the
    refusal is the refusal it was before.

    **The depth is the difference in parts, and a short name is one part.**
    That is what makes the tail the same in both spellings: the directory
    that has two names has one part either way, so the parts below it line
    up.
    """
    if resolved is None:
        raise PathRefusedError(
            PathRejection.OUTSIDE_EVERY_ROOT,
            f"{candidate} is not under root {root.root_id!r} ({root.path})",
        ) from exc
    try:
        resolved.relative_to(root.path)
    except ValueError:
        raise PathRefusedError(
            PathRejection.OUTSIDE_EVERY_ROOT,
            f"{candidate} is not under root {root.root_id!r} ({root.path})",
        ) from exc
    depth = len(candidate.parts) - len(root.path.parts)
    if depth <= 0:
        raise PathRefusedError(
            PathRejection.OUTSIDE_EVERY_ROOT,
            f"{candidate} is not under root {root.root_id!r} ({root.path})",
        ) from exc
    return Path(*candidate.parts[-depth:])


def _key_for(candidate: Path, root: AllowedRoot, *, resolved: Path | None = None) -> ResourceKey:
    """Workspace-relative POSIX key for *candidate* under *root*.

    **The two may be two spellings of one directory.** On Windows an 8.3
    short name and the long one name the same directory, and ``resolve()``
    expands the short one only where it reaches an existing path — so a
    **new** file under a short-spelled directory keeps the short spelling,
    while the root, which exists, comes back long-spelled.
    ``relative_to`` then compares two spellings of one directory and fails,
    and a file that is plainly under the root is refused as being outside
    every root.

    **The proof that the candidate is under the root is not the
    ``relative_to`` that failed.** It is that the **resolved** path is under
    the root, and the caller has already established that by finding the
    resolved root. The key names the **tail below the root**, and the tail
    is the same in both spellings — one part for one part, because a short
    name is still one part.

    So this widens nothing that is not already proved to be inside: without
    a resolved path to check, or with a resolved path that is not under the
    root, the refusal is exactly the refusal it was.
    """
    try:
        relative = candidate.relative_to(root.path)
    except ValueError as exc:
        relative = _tail_below(candidate, root, resolved, exc)
    key = PurePosixPath(*relative.parts).as_posix()
    if not key or key == ".":
        raise PathRefusedError(
            PathRejection.DEGENERATE,
            f"{candidate} reduces to the root itself; a resource key must name a "
            f"resource, not the container it sits in",
        )
    if len(key) > MAX_RESOURCE_KEY_LEN:
        raise PathRefusedError(
            PathRejection.DEGENERATE,
            f"resource key is {len(key)} characters, over the {MAX_RESOURCE_KEY_LEN} "
            f"that Operation.resource_key accepts",
        )
    return key


def canonicalize(
    declared: str | Path,
    roots: tuple[AllowedRoot, ...],
    *,
    base: AllowedRoot | None = None,
) -> CanonicalPath:
    """Turn a caller-supplied path into a :class:`CanonicalPath`, or refuse it.

    :param declared: the caller's spelling. Never trusted, never passed through.
    :param roots: every root the workspace bound. Must be non-empty.
    :param base: the root a *relative* path is resolved against. ADR-0003 §C5
        makes absolute paths mandatory at the tool boundary; this parameter
        exists for internal callers that already hold a root, and a relative
        path with no ``base`` is refused rather than silently resolved against
        the process working directory — which is the documented relative-path
        bypass deepagents has (ADR-0003 A5).

    The sequence is fixed and each step is load-bearing:

    1. reject the spelling (§* Spelling rejection*),
    2. make it absolute against ``base`` if it is relative,
    3. resolve, following symlinks and junctions,
    4. **re-check containment on the resolved path**,
    5. attribute the declared spelling to the root it was declared under and
       the resolved path to the root it landed in, and refuse if they differ.
    """
    if not roots:
        raise PathRefusedError(
            PathRejection.OUTSIDE_EVERY_ROOT,
            "no roots are bound; a workspace with no root admits nothing",
        )

    raw = str(declared)
    normalised = _reject_hostile_spelling(raw)

    as_path = Path(normalised)
    if as_path.is_absolute():
        candidate = as_path
    else:
        if base is None:
            raise PathRefusedError(
                PathRejection.RELATIVE_WITHOUT_ROOT,
                f"{raw!r} is relative and no base root was given. Relative paths are "
                f"refused at the boundary rather than resolved against the process "
                f"working directory.",
            )
        candidate = base.path / as_path

    # The as-declared absolute location, collapsed lexically WITHOUT following
    # links. Computed before resolution so it describes what the caller wrote.
    declared_absolute = Path(os.path.normpath(str(candidate)))

    declared_root = _root_for(declared_absolute, roots)
    resolved = _resolve_or_refuse(candidate)

    # Step 4. This is the check that a single pre-resolution test would miss:
    # a junction or symlink inside an allowed root can still land outside it,
    # and only the resolved path shows that.
    resolved_root = _root_for(resolved, roots)
    if resolved_root is None:
        raise PathRefusedError(
            PathRejection.OUTSIDE_EVERY_ROOT,
            f"{raw!r} resolves to {resolved}, which is under none of the bound roots "
            f"({', '.join(f'{r.root_id}={r.path}' for r in roots)})",
        )

    if declared_root is not None and declared_root.root_id != resolved_root.root_id:
        raise PathRefusedError(
            PathRejection.CROSS_ROOT,
            f"{raw!r} is declared under root {declared_root.root_id!r} but resolves "
            f"into root {resolved_root.root_id!r}. Cross-root movement is refused "
            f"even when both roots are permitted: the destination root's rules were "
            f"never the ones the caller evaluated against.",
        )

    # Declared spelling is keyed against the root it was declared under when that
    # is known; otherwise it is keyed against the root it resolved into, which is
    # the only root it could belong to.
    key_root = declared_root if declared_root is not None else resolved_root

    return CanonicalPath(
        declared_key=_key_for(declared_absolute, key_root, resolved=resolved),
        resolved_key=_key_for(resolved, resolved_root),
        real_path=resolved,
        declared_path=declared_absolute,
        root_id=resolved_root.root_id,
        root_kind=resolved_root.kind,
    )
