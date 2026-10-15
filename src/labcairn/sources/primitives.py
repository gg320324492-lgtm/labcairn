"""Domain-free primitives shared by the three contract packages.

Nothing in this module knows what a source, an evidence record or an artifact
is. It exists so that :mod:`labcairn.sources`, :mod:`labcairn.evidence` and
:mod:`labcairn.reports` can agree, byte for byte, on what a content hash and a
non-empty string look like — without any of the three importing another.

The import direction is deliberate and one-way::

    sources ─┐
    evidence ─┼─> primitives      reports ─┘
             └────────────────────────────> primitives

`evidence` additionally imports `sources` proper, because
:class:`~labcairn.sources.source.SourceAnchor` is a parameter of the cite-support
contracts. That edge is real and unavoidable; an edge from `reports` into
`sources` would not be, which is why `reports` takes only :data:`ContentHash`
and :data:`NonEmptyText` from here.

Three primitives, each chosen to **reject** rather than to coerce:

* :data:`ContentHash` — lowercase hex sha256, exactly 64 characters. Uppercase is
  rejected rather than downcased, because a hash that changes spelling between
  two records of the same file is a hash-comparison bug waiting to happen.
* :data:`NonEmptyText` — length ≥ 1 **and** not entirely whitespace. The stored
  value is never rewritten: a validator that strips would be silently correcting
  malformed input, which is exactly what LC-P1-02 forbids.
* :func:`require_schema_version` — the version gate each package wraps in its own
  ``Annotated[int, AfterValidator(...)]``.

Why the version gate is a *function taking the expected value* rather than a
shared annotated type: each schema versions **independently**. An
:class:`~labcairn.sources.source.SourceAnchor` at version 3 and an
:class:`~labcairn.evidence.record.EvidenceRecord` at version 3 are not the same
event, and a single shared ``SchemaVersion`` alias would silently couple them.
Each package therefore keeps its own constant and its own one-line wrapper; only
the comparison logic is shared.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import AfterValidator, Field, StringConstraints

#: Lowercase hexadecimal sha256. Uppercase is rejected, not normalised.
_CONTENT_HASH_PATTERN: Final[str] = r"^[0-9a-f]{64}$"


def _reject_blank(value: str) -> str:
    """A string that is present but says nothing is not a value.

    Raised through ``AfterValidator`` rather than ``StringConstraints`` so the
    original string is preserved: a leading or trailing space is part of the
    recorded evidence text, and trimming it would change what was extracted.
    """
    if not value.strip():
        raise ValueError("value is whitespace only; an empty string is not a value here")
    return value


#: A non-empty string that is not entirely whitespace. Never rewritten.
NonEmptyText = Annotated[str, StringConstraints(min_length=1), AfterValidator(_reject_blank)]

#: A sha256 content hash in canonical lowercase-hex form.
ContentHash = Annotated[str, StringConstraints(pattern=_CONTENT_HASH_PATTERN)]


def require_schema_version(value: int, *, expected: int, schema: str) -> int:
    """Accept exactly one payload version, in both directions.

    ``schema_version`` is not a compatibility hint, it is a statement about
    which field set the payload actually has. Guessing at an unknown one would
    mean reading a v0 record through a v1 model — silently dropping the fields
    this build has never heard of and writing them back out as if they had never
    existed.

    Older payloads are rejected rather than migrated here. A migration is a
    deliberate, reviewed act belonging to whoever bumps the constant, not
    something a parse should improvise.

    :param value: the version found in the payload.
    :param expected: the version this build reads.
    :param schema: the schema's human name, used verbatim in the message.
    :raises ValueError: if ``value != expected``, for a newer *or* older payload.
    """
    if value != expected:
        raise ValueError(
            f"unsupported {schema} schema_version {value!r}: this build reads exactly "
            f"{expected}. A payload from another version is refused, not coerced — "
            f"migrate it explicitly (older) or open a build that reads it (newer)."
        )
    return value


# ---------------------------------------------------------------------------
# Workspace-relative paths
# ---------------------------------------------------------------------------

#: Characters that may never appear in a stored workspace-relative path.
#: Backslash first: a Windows separator surviving into a stored locator is how a
#: path recorded on one platform fails to resolve on another.
_FORBIDDEN_IN_PATH: Final[tuple[str, ...]] = ("\\",)


def _reject_dot_segments(segment: str, path: str) -> None:
    if segment in ("", ".", ".."):
        raise ValueError(
            f"workspace-relative path {path!r} contains the segment {segment!r}. "
            f"Paths are stored canonicalised, not normalised on read: a '..' here "
            f"would resolve outside the workspace root."
        )


def require_workspace_relative(value: str) -> str:
    """A path that is unambiguously inside the workspace root.

    Stored **workspace-relative, POSIX-separated, no drive letter**, matching the
    canonicalisation ADR-0003 §C4 fixes for approval digests. Rejected rather
    than rewritten, for the same reason as :func:`_reject_blank`: an absolute
    path or a ``..`` segment is a fact about the *proposal*, and quietly turning
    it into a relative one is how a read escapes the workspace
    (``docs/ARCHITECTURE.md`` "Privacy and security invariants").

    What this deliberately does **not** do is touch the filesystem. Whether the
    path exists, and what it currently hashes to, is LC-P1-08's question.
    """
    if value != value.strip():
        raise ValueError(f"path {value!r} has leading or trailing whitespace")
    for token in _FORBIDDEN_IN_PATH:
        if token in value:
            raise ValueError(
                f"path {value!r} contains {token!r}. Stored paths are POSIX-separated "
                f"and workspace-relative; a backslash is a separator of a different "
                f"platform and is refused rather than translated."
            )
    if value.startswith("/"):
        raise ValueError(
            f"path {value!r} is absolute. Source and artifact locations are stored "
            f"workspace-relative so a ledger stays portable between machines."
        )
    if len(value) >= 2 and value[1] == ":":
        raise ValueError(
            f"path {value!r} carries a drive letter. Stored locations are "
            f"workspace-relative so a ledger stays portable between machines."
        )
    for segment in value.split("/"):
        _reject_dot_segments(segment, value)
    return value


#: A canonical workspace-relative POSIX path. See :func:`require_workspace_relative`.
WorkspaceRelativePath = Annotated[str, AfterValidator(require_workspace_relative)]


# ---------------------------------------------------------------------------
# Numbers that must not be silently converted
# ---------------------------------------------------------------------------
#
# Pydantic validates in *lax* mode by default, and in lax mode ``"3"`` is a
# perfectly good integer. That is silent correction: a payload written by a
# caller who had a string where a number belongs is accepted, the string is
# replaced by an int, and nothing downstream can tell that the payload was ever
# malformed. LC-P1-02's acceptance is "malformed payloads rejected", so every
# numeric field in these contracts opts into ``strict=True``.
#
# ``int`` into a ``float`` field is still accepted under ``strict=True`` — Pydantic
# documents it as the one widening that is not a coercion — so ``"value": 3`` on a
# float is fine while ``"value": "3"`` is refused.


#: A 1-based count: page, line, row, ``size_bytes`` is not one of these.
StrictPosInt = Annotated[int, Field(strict=True, ge=1)]

#: A 0-based offset into something: character positions, line ends.
StrictNonNegInt = Annotated[int, Field(strict=True, ge=0)]

#: A float that must arrive as a number. Negative is allowed; a quoted number is not.
StrictFloat = Annotated[float, Field(strict=True)]

#: A non-negative float that must arrive as a number — a comparison tolerance.
#:
#: ``0.0`` is legal and means "must match exactly"; what is *not* legal is
#: arriving as ``0.0`` by default, because an undeclared tolerance is not an
#: exact-match requirement. That is a default-value decision on
#: :attr:`~labcairn.evidence.record.EvidenceRecord.tolerance`, not a range rule,
#: and both are asserted separately in the tests.
StrictNonNegFloat = Annotated[float, Field(strict=True, ge=0.0)]
