"""Secrets and source excerpts must not reach a log line, an event, or an export.

What this module is for
-----------------------
The work order's acceptance line is *"no API keys/excerpts in logs"*. Two
different things can leak into a log, and they need different handling:

* **The credential.** LabCairn knows it — :func:`load_credential` reads it — so
  it can be registered once and removed from every string it ever passes
  through. This is exact: the full secret is matched literally.
* **Text we never held.** A provider's 4xx body, an httpx traceback, a
  pydantic-ai error string. These may *contain* the credential (providers echo it
  back: ``"Incorrect API key provided: sk-ant-..."``) and they may contain
  arbitrary bytes from a document. We cannot enumerate them, so we attack the
  *shapes* instead — see :data:`_SHAPES`.

And a third thing, which is the one that is easy to forget:

* **Source excerpts.** A retrieved passage that has been handed to a model for
  analysis, or that a provider echoes back in an error, is research material.
  The redactor has no way to recognise it — an excerpt is just text. What it can
  do is guarantee the excerpt is never *made available* to the log path in the
  first place, which is a discipline of the adapter rather than a property of
  this class. See :mod:`labcairn.providers.adapter` and
  ``PHASE_1_OUTBOUND_POLICY``. This module's honest scope is: **the credential
  and the credential's echoes**, not the document.

Why ``digest`` hashes the *scrubbed* text
-----------------------------------------
A digest of the raw text would be a hash of the secret. SHA-256 is not a
commitment scheme: ``sk-ant-...`` has low enough entropy that a candidate list
is feasible, so a digest over the raw secret is a secret with extra steps. A
digest over the *scrubbed* text cannot be inverted into the credential, stays
stable across occurrences of the same failure, and still tells a human "this is
the same failure as last Tuesday".

Redaction is best-effort by construction, and this is stated rather than hidden:
:attr:`Redactor.scrub` reduces risk, it does not prove absence. The guarantee it
does give is one that can be tested and is the one that actually matters here —
:func:`Redactor.contains_secret` over a registered secret, and the shape rules,
are both exact, and ``tests/test_provider_redaction.py`` asserts them.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from threading import RLock

#: What a removed secret is replaced with. Bracketed so it is visibly a
#: substitution rather than a short secret, and constant so a scrubbed string is
#: byte-stable across runs.
PLACEHOLDER: str = "<redacted>"

#: Domain separator. Prevents a digest computed here from colliding with a
#: digest of the same text computed for some unrelated purpose, and makes it
#: obvious in a hex dump that this module produced it.
_DIGEST_DOMAIN: bytes = b"labcairn.provider.redaction.v1\x00"

#: Shortest secret we will bother scrubbing. A 1-3 character "secret" is a
#: config value, not a credential, and blanket-replacing it would destroy log
#: text without protecting anything.
_MIN_SECRET_LENGTH: int = 8

#: Shapes that carry a credential regardless of who issued it. Deliberately
#: high-precision: a rule that matches ordinary prose would redact the
#: documentation that explains what went wrong.
_SHAPES: tuple[re.Pattern[str], ...] = (
    # Provider-issued keys, as used by Anthropic (sk-ant-…), OpenAI project keys
    # (sk-proj-…), and their relatives.
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"),
    # `Authorization: Bearer <token>` and bare `Bearer <token>`.
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-~+/]{8,}=*"),
    # `api_key=…`, `apikey: "…"` and friends in a JSON body or a query string.
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|secret|token)\s*[=:]\s*[\"']?[A-Za-z0-9._\-]{8,}[\"']?"
    ),
    # An Anthropic-style header value as it appears in a dumped header map.
    re.compile(r"(?i)[\"']?x-api-key[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9._\-]{8,}[\"']?"),
)


class Redactor:
    """Scrubs registered secrets and credential-shaped text out of strings.

    Thread-safe, because a provider adapter logs from whatever thread the HTTP
    client happens to use and a ``list.append`` guarded by nothing is a race
    that shows up as a leaked key once in a thousand runs.
    """

    __slots__ = ("_lock", "_secrets")

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._lock = RLock()
        self._secrets: list[str] = []
        for secret in secrets:
            self.register(secret)

    def register(self, secret: str) -> bool:
        """Add a secret. Returns whether it was worth registering.

        Empty and very short values are refused. The refusal is not paranoia: a
        one-character secret scrubbed globally turns every log line into
        ``<redacted>`` and costs more diagnosability than it returns safety.
        """
        if len(secret) < _MIN_SECRET_LENGTH:
            return False
        with self._lock:
            if secret not in self._secrets:
                self._secrets.append(secret)
        return True

    @property
    def registered_count(self) -> int:
        with self._lock:
            return len(self._secrets)

    def scrub(self, text: str) -> str:
        """Remove registered secrets and credential-shaped runs from ``text``.

        Longest-first, so a secret that contains another secret as a substring
        is removed whole rather than leaving a dangling tail behind.
        """
        if not text:
            return text
        result = text
        with self._lock:
            secrets = sorted(self._secrets, key=len, reverse=True)
        for secret in secrets:
            result = result.replace(secret, PLACEHOLDER)
        for shape in _SHAPES:
            result = shape.sub(PLACEHOLDER, result)
        return result

    def contains_secret(self, text: str) -> bool:
        """Whether ``text`` still holds something this redactor would remove.

        The assertion the log tests actually make. ``assert PLACEHOLDER in log``
        would pass on a log that leaked *other* material; this cannot.
        """
        return self.scrub(text) != text

    def digest(self, text: str) -> str:
        """SHA-256 over :meth:`scrub` of ``text``, domain-separated.

        The digest is computed from the scrubbed form, so the value that ends up
        in :attr:`~labcairn.providers.errors.ProviderFailure.detail_digest` is a
        commitment to "this failure, minus its credentials", not to the failure
        text itself.
        """
        return hashlib.sha256(_DIGEST_DOMAIN + self.scrub(text).encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        # The count, never the contents. A Redactor in a traceback, a reprlib
        # dump or a debugger transcript must not be a credential oracle.
        return f"Redactor(registered={self.registered_count})"


def scrub_exception_context(exc: BaseException, *, redactor: Redactor) -> str:
    """Render an exception for a log line, scrubbed.

    Separate from :func:`~labcairn.providers.errors.classify_exception` on
    purpose: that function *discards* the text, this one *logs* it. Operators do
    need to see why a provider failed, so the escape hatch is explicit and named
    rather than being the default every caller gets by reaching for ``str(exc)``.
    """
    return redactor.scrub(f"{type(exc).__name__}: {exc}")
