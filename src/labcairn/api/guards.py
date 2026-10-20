"""The origin check and the session check: the two guards that ride on every
request, whatever it asks for.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.6 says why the origin check is
the one that matters: *"Every request whose ``Origin`` is not the service's own
is refused, whatever it asks for. This is the real defence: a page in the
user's browser on another site cannot drive a local service, and the browser
sends the ``Origin`` whether the page means to or not."*

The last clause is the load-bearing one. A guard that trusted the request's
*intentions* — a header a page sets when it means to, a parameter it is
invited to send — is a guard against a cooperating page. The ``Origin``
header is set by the browser, for the page's own reasons, and a page on
another site cannot change it. So the check is on the origin, and it is on
**every** request rather than only on the ones that change something.

A request with no ``Origin`` at all
-----------------------------------

A browser does not send ``Origin`` on a same-origin ``GET``, and does not send
it for a cross-origin subresource load either (``<img>``, ``<script>``), so
"no origin" is not the same fact as "a foreign origin". Refusing every
origin-less request would refuse the web app's own reads.

What it does not do is open a hole, because the two ways to *change* something
are covered elsewhere: a cross-origin form post carries an ``Origin`` (every
browser that can run this service sends one), and a mutation without one
still has to present the session token, which is not guessable. The origin
check is what stops a page on another site; the session check is what stops
everything else.

The session check
-----------------

The token is required on every request that **changes** something, and on no
request that only reads. That is the owner's decision in §1.4.4 and it is what
lets the web app draw the task before it has a token to draw it with.

The two checks are independent, and each of them is worth having on its own:
a foreign origin is refused *even with a valid token*, because a token is not
a pass to a page on another site; and the right origin without a token is
refused *for a mutation*, because a page on the right origin is a page this
service is willing to talk to, not a page it will act for.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from labcairn.api.session import SessionToken, read_bearer

#: The HTTP methods that do not change anything.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class GuardRefusal(StrEnum):
    """Why a guard refused a request.

    The same two-part shape the application layer's refusals have, for the
    same reason: a caller branches on the reason, and the message says which
    one it was.
    """

    #: The request's ``Origin`` is not one of the service's own.
    ORIGIN_REFUSED = "origin_refused"
    #: The request changes something and did not present the session token.
    SESSION_REQUIRED = "session_required"


#: The status each guard refusal is answered with.
#:
#: A foreign origin is *forbidden* — the request was understood and the
#: service declines to serve it. A missing session is *unauthorised* — the
#: request was understood and the service declines to carry it out without
#: the credential. The two are different situations with different remedies,
#: so they are different statuses; the reason in the body says which one it
#: was either way.
GUARD_STATUS_CODES: dict[GuardRefusal, int] = {
    GuardRefusal.ORIGIN_REFUSED: 403,
    GuardRefusal.SESSION_REQUIRED: 401,
}


class GuardRefusedError(RuntimeError):
    """A guard refused the request, and says why."""

    def __init__(self, reason: GuardRefusal, detail: str) -> None:
        super().__init__(f"request refused ({reason.value}): {detail}")
        self.reason = reason
        self.detail = detail

    def to_payload(self) -> dict[str, str]:
        """The refusal as data, in the layer's own two-field shape."""
        return {"reason": self.reason.value, "message": str(self)}


@dataclass(frozen=True, slots=True)
class OriginPolicy:
    """The origins this service answers to.

    The set is the service's own origin plus any the caller has explicitly
    added — the development web server is a different origin from the API, and
    a service that could not be told about it would be a service the
    development web app could not talk to. The set is empty of extras by
    default, and adding one is a decision somebody makes on purpose.
    """

    allowed: frozenset[str]

    @classmethod
    def for_service(cls, own: str, extra: Iterable[str] = ()) -> OriginPolicy:
        """The policy for a service answering to *own*, plus *extra*."""
        return cls(frozenset({own, *extra}))

    def permits(self, origin: str | None) -> bool:
        """Whether a request carrying *origin* may be served.

        ``None`` means the request carried no ``Origin`` header, and is
        permitted — see the module docstring for why that is not a hole.
        """
        if origin is None:
            return True
        return origin in self.allowed


@dataclass(frozen=True, slots=True)
class SessionGuard:
    """The token, and the check that a mutation presented it."""

    token: SessionToken

    def permits(self, method: str, presented: str | None) -> bool:
        """Whether a request of *method* may proceed on *presented*.

        A read is permitted without a token; a mutation is not. The token is
        compared in constant time, and a request that presents no token at all
        is refused without the comparison being made.
        """
        if method.upper() in SAFE_METHODS:
            return True
        if presented is None:
            return False
        return self.token.verify(presented)

    @staticmethod
    def read(request_headers: Mapping[str, str]) -> str | None:
        """The token a request presents, or ``None``.

        The only reading of the ``Authorization`` header in the service, so
        there is one place to look when asking where a token could come from.
        """
        return read_bearer(request_headers.get("authorization"))


__all__ = [
    "SAFE_METHODS",
    "GuardRefusal",
    "GuardRefusedError",
    "OriginPolicy",
    "SessionGuard",
]
