"""The bind address: the first of the three guards, and the one that cannot be
argued with.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.6 puts three things in order,
and this is the first: *"The bind address. ``127.0.0.1`` only. Not
``0.0.0.0``."* The brief sharpens it: *"The service refuses to start on a
non-loopback address, rather than starting and warning — a warning is a thing
a user reads once and a refusal is a thing that cannot be missed."*

So this module has no "warn and carry on" path. :func:`ensure_loopback` either
returns the address or raises, and the caller that starts the server does not
start it.

Why the address and not the name
--------------------------------

``localhost`` is refused, and that is deliberate. A name is resolved through
the host's resolver, and the resolver is a thing outside this program: a hosts
file, an LDAP lookup or a container runtime can all answer ``localhost`` with
something that is not this machine's loopback interface. The guard's whole
claim is *"this socket is reachable from nowhere else"*, and a claim about a
name is not that claim. An address is.

The address is checked with :mod:`ipaddress` rather than by comparing against a
list, so the check is the platform's idea of loopback and not this file's
opinion of it. ``127.0.0.1`` and ``::1`` are loopback on every platform this
runs on; ``0.0.0.0`` is not, and neither is any address on a real network.
"""

from __future__ import annotations

import ipaddress

#: The address the service binds when the caller names none.
DEFAULT_BIND_HOST = "127.0.0.1"

#: The port the service binds when the caller names none.
DEFAULT_BIND_PORT = 8000


class BindRefusedError(RuntimeError):
    """The service was asked to listen somewhere it must not listen.

    Raised rather than logged, because a service that starts on ``0.0.0.0``
    and warns is a service that is already reachable from the network by the
    time the warning is read.
    """


def ensure_loopback(host: str) -> str:
    """Return *host* if it is a loopback address, and refuse it otherwise.

    :param host: the address the caller asked the service to bind.
    :returns: the same address, unchanged, once it is known to be loopback.
    :raises BindRefusedError: *host* is not a loopback address, or is not an
        address at all.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise BindRefusedError(
            f"the service will not bind {host!r}: it is not an address. Name the "
            "loopback address itself (127.0.0.1 or ::1) rather than a host name, "
            "because a name is resolved outside this program and a host file or a "
            "resolver can answer it with something this service did not choose."
        ) from error
    if not address.is_loopback:
        raise BindRefusedError(
            f"the service will not bind {host!r}: it is not a loopback address. A "
            "local research service that listens on a routable address is a "
            "service on the network, and the guards that follow assume it is not."
        )
    return host


def own_origin(host: str, port: int) -> str:
    """The origin the service answers to, given where it binds.

    An origin is scheme, host and port together, and the port is part of it:
    a page served from ``http://127.0.0.1:8000`` is not the same origin as one
    served from ``http://127.0.0.1:5173``, so the origin the service compares
    against carries the port it was told to bind.
    """
    return f"http://{host}:{port}"


__all__ = [
    "DEFAULT_BIND_HOST",
    "DEFAULT_BIND_PORT",
    "BindRefusedError",
    "ensure_loopback",
    "own_origin",
]
