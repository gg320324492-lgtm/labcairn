"""The session token: minted at start-up, written to a file, sent in a header.

``docs/ARCHITECTURE.md``'s privacy invariants end with *"localhost API requires
origin restrictions and a local authenticated session/token even if launched on
loopback"*, and §1.4.4 of the task breakdown records the owner's decision:
*"The service binds ``127.0.0.1``, refuses any request whose ``Origin`` is not
its own, and requires a bearer token minted at start-up, written to a workspace
file the CLI prints."*

Why the token is in a header and not a query string
---------------------------------------------------

A URL is pasted. A header is not. A token in a query string ends up in the
browser's history, in the ``Referer`` header of every request the page makes
afterwards, in a proxy's log and in a shell's scrollback. The token is
therefore read from the ``Authorization`` header and from nowhere else — and
:func:`read_bearer` is the only place that reads it, so there is exactly one
reading of it to audit.

Why the token is written to a file at all
----------------------------------------

Because the CLI has to be able to tell the user where it is without the
service having to hand the secret to whoever asks. The file is the service's
own, under the workspace the user selected, and it is written with the
narrowest permissions the platform allows.

The file is the *service's* file and not a task artefact
--------------------------------------------------------

It sits under ``<workspace>/.labcairn/`` rather than in the task's output
area. The output area holds artefacts, and an artefact is something the report
manifest names and the report may cite; a session secret is not a finding and
must never be counted as one. The workspace root is not writable by any
capability — *"no output capability addresses the workspace root directly"* —
so nothing else can put a file there, and the secret cannot be mistaken for
one of a task's products.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

#: How many bytes of entropy the token carries, before base64url encoding.
TOKEN_ENTROPY_BYTES = 32

#: The directory under the selected workspace that holds the service's own files.
SESSION_DIR_NAME = ".labcairn"

#: The file under that directory that holds the session token.
SESSION_FILE_NAME = "session-token"


@dataclass(frozen=True, slots=True)
class SessionToken:
    """A minted token, and the file it was written to.

    Frozen because a token that could be changed after it was written would
    leave a file that does not hold the token the service is using — and a
    file that lies about the session is worse than no file.
    """

    value: str
    path: Path

    def verify(self, candidate: str) -> bool:
        """Whether *candidate* is this token.

        The comparison is constant-time and over bytes, so it neither leaks the
        token's length through its running time nor raises on a candidate
        carrying non-ASCII characters, which a header may.
        """
        return secrets.compare_digest(self.value.encode("utf-8"), candidate.encode("utf-8"))


def mint_token() -> str:
    """A fresh session token.

    Base64url of :mod:`secrets`' bytes, so the token is safe to put in a
    header, a file and a terminal without escaping.
    """
    return secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)


def write_token_file(path: Path, token: str) -> Path:
    """Write *token* to *path*, and return the path.

    The file is created with the narrowest permissions the platform allows,
    and the parent directory with the narrowest a directory can carry. On a
    platform that does not have POSIX permissions this is a no-op rather than
    an error: the file is still created, and the platform's own access control
    is what governs it there.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    _restrict(path, 0o600)
    _restrict(path.parent, 0o700)
    return path


def read_bearer(header: str | None) -> str | None:
    """The token in an ``Authorization`` header, or ``None``.

    ``None`` for a header that is absent, that carries another scheme, or that
    carries an empty value — the three ways a request can fail to present a
    token at all, and they are the same answer for the guard.
    """
    if header is None:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.strip().lower() != "bearer":
        return None
    presented = value.strip()
    return presented or None


def _restrict(path: Path, mode: int) -> None:
    """Narrow *path*'s permissions to *mode*, where the platform has permissions.

    **A directory and a file need different modes, and a directory given a
    file's mode stops working.** On POSIX a directory is traversed with the
    **execute** bit, and a directory with no execute bit cannot be entered —
    not even by its owner. A session directory given the file's ``0o600`` was
    therefore writable exactly once: the first token could be written into it,
    and the second raised ``PermissionError``, because the directory could no
    longer be entered. Windows does not see it, because there ``chmod`` only
    toggles the read-only attribute and every directory stays traversable —
    so the bug showed up on one platform and not the other.

    The narrowest mode a directory can carry and still be usable is ``0o700``:
    the owner may enter it, and nobody else may.
    """
    try:
        path.chmod(mode)
    except OSError:
        # Windows, and any filesystem without POSIX modes. The file exists and
        # the platform governs who may read it; pretending otherwise by
        # failing would refuse to start a service that would have worked.
        return


__all__ = [
    "SESSION_DIR_NAME",
    "SESSION_FILE_NAME",
    "TOKEN_ENTROPY_BYTES",
    "SessionToken",
    "mint_token",
    "read_bearer",
    "write_token_file",
]
