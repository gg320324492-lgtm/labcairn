"""Where a credential comes from, and why it cannot end up in a log.

Sources, in the order they are tried
------------------------------------
1. an environment variable **named by the settings** (``credential_env``) — the
   name is stored, never the value;
2. a file **named by the settings** (``credential_file``), with surrounding
   whitespace stripped because every text editor adds one and a trailing newline
   in an ``Authorization`` header is a 401 that looks like a wrong key;
3. otherwise :class:`MissingCredentialError`.

There is no third source. No keyring integration, no OAuth device flow, no
"paste it here" prompt: each of those is a decision about where a user's
long-lived secret lives on their machine, and it belongs to a work order that
will be able to see the threat model. Phase 1 ships the two that every operator
already uses, and refuses to invent a third.

Why ``Credential`` hides its value
----------------------------------
The class is frozen, hashed on its *fingerprint*, and redacted in ``repr``.
Three separate mechanisms, because each fails differently:

* ``__repr__`` / ``__str__`` hide the value, so an accidental ``f"{cred}"``, a
  traceback, a ``pydantic`` validation error dump or a debugger transcript
  cannot print it. This is the one that is actually load-bearing.
* ``__hash__`` / ``__eq__`` use :attr:`fingerprint`, so a ``Credential`` in a set
  or a dict key does not hash the secret into anything persisted.
* :meth:`reveal` is the *only* accessor, and it exists so the call that hands the
  secret to a provider SDK is visible to grep. There is no ``.value``, no
  indexing, no ``__getattr__``.

The fingerprint is salted with the same domain separator idea as
:mod:`labcairn.providers.redaction`, so it identifies "the same credential" for
diagnostics without being a hash an attacker could grind.

``httpx`` is a declared runtime dependency (LC-P2-01 T00; the decision
record is ``docs/adr/ADR-0019-model-call-dependencies.md``) -- it is the
HTTP client the real-protocol providers run on, and pydantic-ai's public
``OpenAIProvider.__init__`` takes an ``httpx.AsyncClient`` directly.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Domain separator for credential fingerprints, so a fingerprint from this module
#: is recognisable in a digest dump and cannot collide with a digest of the same
#: bytes computed for another purpose.
_FINGERPRINT_DOMAIN: bytes = b"labcairn.provider.credential.v1\x00"


class Protocol(StrEnum):
    """The wire dialect. Frozen values; they key the probe cache.

    ``OPENAI_COMPATIBLE`` is a *mode*, not a vendor: it is the OpenAI Chat
    Completions request shape sent to a ``base_url`` the operator chose. That is
    the configuration the work order asks for ("one OpenAI-compatible custom
    endpoint") and it is the one where ADR-0002's warning bites hardest, because
    nothing about the URL tells you which model is behind it.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"


#: Providers with a documented public endpoint. ``OPENAI_COMPATIBLE`` is absent
#: on purpose: its base URL is operator-supplied and there is no default.
DEFAULT_BASE_URLS: Mapping[Protocol, str] = {
    Protocol.OPENAI: "https://api.openai.com/v1",
    Protocol.ANTHROPIC: "https://api.anthropic.com/v1",
}


class MissingCredentialError(RuntimeError):
    """No credential could be found. Says where it looked, never what it found."""


class UnknownProviderError(RuntimeError):
    """The settings name a protocol that is not one of the three."""


@dataclass(frozen=True, slots=True)
class Credential:
    """A secret that is hard to print by accident."""

    #: The *name* of the variable or file it came from. Useful in errors.
    source: str
    _value: str
    _fingerprint: str

    @classmethod
    def of(cls, value: str, *, source: str) -> Credential:
        if not value.strip():
            raise MissingCredentialError(f"credential source {source!r} is empty")
        stripped = value.strip()
        return cls(
            source=source,
            _value=stripped,
            _fingerprint=hashlib.sha256(_FINGERPRINT_DOMAIN + stripped.encode("utf-8")).hexdigest(),
        )

    def reveal(self) -> str:
        """The secret, in plaintext.

        Named for what it does. There are exactly two callers in this package —
        the pydantic-ai provider factories — and
        ``tests/test_provider_credentials.py::test_reveal_call_sites_are_exhaustive``
        fails if that ever stops being true.
        """
        return self._value

    @property
    def fingerprint(self) -> str:
        """A stable, non-reversible identifier: which two configs share a key.

        Safe in a log and in a report. A provider API key is 40+ characters of
        base62, so this digest is not grindable — which is the whole reason it
        can be exposed where the value cannot.
        """
        return self._fingerprint

    def __repr__(self) -> str:
        return f"Credential(source={self.source!r}, value=<withheld>)"

    __str__ = __repr__

    def __hash__(self) -> int:
        return hash((Credential, self.fingerprint))

    def __eq__(self, other: object) -> bool:
        """Two credentials are equal when they are the *same key*.

        Not when they came from the same place: a key in an environment variable
        and the same key in a file are one credential configured twice, and the
        question a settings check actually asks — "are these two providers using
        the same secret?" — is about the key.
        """
        if not isinstance(other, Credential):
            return NotImplemented
        return self.fingerprint == other.fingerprint


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """One configured provider. A value; performs no I/O."""

    protocol: Protocol
    model: str
    #: Required for ``OPENAI_COMPATIBLE``; optional elsewhere (the default applies).
    base_url: str | None = None
    #: The environment variable to read. Stored as a *name*.
    credential_env: str | None = None
    #: A file to read. Path is operator-supplied and shown in errors.
    credential_file: Path | None = None
    #: Per-request timeout handed to the HTTP client.
    timeout_s: float = 60.0

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("provider settings need a model name")
        if self.timeout_s <= 0:
            raise ValueError(f"timeout_s must be positive, got {self.timeout_s!r}")
        if self.protocol is Protocol.OPENAI_COMPATIBLE and not self.base_url:
            raise ValueError(
                "an OpenAI-compatible endpoint must name a base_url; there is no default "
                "for a provider whose host the project does not know"
            )

    @property
    def effective_base_url(self) -> str | None:
        return self.base_url or DEFAULT_BASE_URLS.get(self.protocol)

    @property
    def protocol_label(self) -> str:
        """A stable label for the probe cache key. Never the base URL — see below."""
        return self.protocol.value

    def sanitised_base_url(self) -> str:
        """The base URL with anything credential-shaped removed.

        Used for the endpoint fingerprint and for logs. Strips userinfo
        (``https://user:key@host``) and the query string, because both are places
        a credential is routinely and quite reasonably put — ``?api_key=`` on a
        self-hosted gateway is not a user error, it is a common deployment.
        """
        url = self.effective_base_url or ""
        scheme, _, rest = url.partition("://")
        if rest:
            authority, slash, path = rest.partition("/")
            if "@" in authority:
                authority = authority.rsplit("@", 1)[1]
            url = f"{scheme}://{authority}{slash}{path}"
        return url.split("?", 1)[0].rstrip("/")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ProviderSettings:
        """Build from a parsed config file entry. Unknown keys are an error.

        Strict on purpose: a config key LabCairn does not understand is far more
        often a typo (``base_ur1``) than a forward-compatible extension, and a
        typo that silently leaves ``base_url`` unset against an OpenAI-compatible
        entry is a request going to the wrong place.
        """
        known = {
            "protocol",
            "model",
            "base_url",
            "credential_env",
            "credential_file",
            "timeout_s",
        }
        unknown = sorted(set(payload) - known)
        if unknown:
            raise ValueError(f"unknown provider settings key(s): {', '.join(unknown)}")
        raw_protocol = payload.get("protocol")
        try:
            protocol = Protocol(str(raw_protocol))
        except ValueError as exc:
            raise UnknownProviderError(
                f"protocol {raw_protocol!r} is not one of {', '.join(p.value for p in Protocol)}"
            ) from exc
        raw_file = payload.get("credential_file")
        return cls(
            protocol=protocol,
            model=str(payload.get("model", "")),
            base_url=_optional_str(payload.get("base_url")),
            credential_env=_optional_str(payload.get("credential_env")),
            credential_file=Path(str(raw_file)) if isinstance(raw_file, str) and raw_file else None,
            timeout_s=_as_float(payload.get("timeout_s"), 60.0),
        )


def load_credential(
    settings: ProviderSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> Credential:
    """Resolve a credential from the environment or a file.

    ``environ`` is a parameter rather than a call to :data:`os.environ` so a test
    can supply a fixture mapping — and, more importantly, so that no test can
    accidentally pick up a credential that happens to be set on the machine
    running it. The repository has a hard no-real-credentials rule and this is
    where it is enforced mechanically rather than by discipline.
    """
    env = os.environ if environ is None else environ

    if settings.credential_env:
        raw = env.get(settings.credential_env)
        if raw is not None and raw.strip():
            return Credential.of(raw, source=f"env:{settings.credential_env}")

    if settings.credential_file is not None:
        path = settings.credential_file
        if path.is_file():
            return Credential.of(path.read_text(encoding="utf-8"), source=f"file:{path}")
        raise MissingCredentialError(
            f"credential file {path} does not exist (settings asked for "
            f"{settings.credential_env or 'no environment variable'})"
        )

    raise MissingCredentialError(
        "no credential found: set the environment variable "
        f"{settings.credential_env or '(none configured)'} or point credential_file at a file"
    )


def load_providers_config(path: Path) -> Mapping[str, ProviderSettings]:
    """Read ``{"providers": {"<name>": {...}}}`` from JSON.

    JSON rather than TOML only because :mod:`tomllib` arrived in 3.11 and this is
    a 3.12 project; if the settings layer grows, TOML belongs here and this
    function is where it changes.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MissingCredentialError(f"providers config file {path} does not exist") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"providers config file {path} is not valid JSON: {exc.msg}") from exc
    if not isinstance(raw, Mapping) or not isinstance(raw.get("providers"), Mapping):
        raise ValueError(f'providers config file {path} must have a top-level "providers" object')
    entries = raw["providers"]
    return {str(name): ProviderSettings.from_mapping(entry) for name, entry in entries.items()}


def _as_float(value: object, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"timeout_s must be a number, got {value!r}")
    return float(value)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
