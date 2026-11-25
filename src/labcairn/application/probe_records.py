"""The capability probe's record, kept in the store.

What this module is for
-----------------------
ADR-0002 §Contracts promised two things about probe results:

    "Probe results are cached per ``(endpoint, model, protocol)`` in SQLite
    with a timestamp and are invalidated by a protocol or endpoint change."

    "Provide ``doctor --probe`` so users opt in, and a ``probed: false``
    override that yields ``UNVERIFIED``."

The first half was a :class:`~labcairn.providers.probe.ProbeCache` protocol
with one implementation -- :class:`~labcairn.providers.probe.InMemoryProbeCache`
-- and **no product code read it**. A probe result was therefore something a
document could record and the product could not: a real capability probe run
against the signed authorisation's endpoint on 2026-11-25 wrote its reading
into ``docs/acceptance/LC-P4-PILOT-capability-probe-2026-11-25.md`` and
nowhere else, so ``doctor`` on that same workspace still reported every
capability as unverified and the capability gate had nothing to read.

:class:`SqliteProbeCache` is the persistent half of that promise. It is a
:class:`~labcairn.providers.probe.ProbeCache` with the **same key shape** as
the in-memory one -- ``(endpoint_fingerprint, model, protocol)`` -- so the
two are interchangeable and the substitution is real rather than nominal.

Where it lives and why
----------------------
In the application layer, not in ``labcairn.providers`` and not in
``labcairn.db``. The provider layer is a leaf: it imports ``labcairn.core``
and nothing else, and a cache that reached into the store would make it
depend on storage it has no business knowing about. The database layer knows
about rows and about the runtime's own contracts, and importing the provider
layer's vocabulary into it would make the store depend on the provider layer
in turn. The application layer already depends on **both**, and it already
holds the pattern this is an instance of -- a store-backed implementation of
a port the inner layer defines (``StoredApprovalLedger`` implements
``labcairn.security.approval``'s ledger against this same store). So this
is that pattern once more, and it adds **no new edge between layers**.

What the record holds
---------------------
The record is secret-free by construction, and this module does not change
that. The endpoint is a fingerprint rather than a URL, so no host and no
``?api_key=`` is written; the evidence strings are LabCairn-authored
one-liners -- an exception's *class name*, or a fixed phrase -- and never an
exception message, which may echo a credential; the timestamps are UTC.

**The key is what invalidates the record.** ADR-0002 says a record is
"invalidated by a protocol or endpoint change", and the unique constraint on
``(endpoint_fingerprint, model, protocol)`` is how that is true: a probe of
a different protocol, a different model or a different endpoint is a
*different row*, and the lookup for the old key simply does not find it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.db.models import ProbeRecordRow
from labcairn.providers.capabilities import Capability, CapabilityOutcome
from labcairn.providers.probe import ProbeRecord


class SqliteProbeCache:
    """The store-backed :class:`~labcairn.providers.probe.ProbeCache`.

    **A session, not an engine.** The cache reads and writes inside the
    caller's transaction, so a record written by ``doctor --probe`` commits
    with the command that wrote it and rolls back with it if the command
    fails. That is the same discipline every other store-backed thing in
    this repository follows, and it is why this class takes a
    :class:`~sqlalchemy.orm.Session` rather than opening its own.

    **Writing is an upsert, not an append.** One row per key: a second
    probe of the same ``(endpoint, model, protocol)`` replaces the first
    one's reading, because the newest reading is the one that was measured
    last. The row's ``observed_at`` says when, so the replacement is a
    fact about time and not a silent overwrite.
    """

    __slots__ = ("_session",)

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, endpoint_fingerprint: str, model: str, protocol: str) -> ProbeRecord | None:
        """The record for this key, or ``None`` when nothing was probed.

        ``None`` is the honest answer for a key nobody has probed, and it is
        what makes a capability that was never probed stay ``unverified``.
        """
        row = self._session.execute(
            select(ProbeRecordRow).where(
                ProbeRecordRow.endpoint_fingerprint == endpoint_fingerprint,
                ProbeRecordRow.model == model,
                ProbeRecordRow.protocol == protocol,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return _record_from_row(row)

    def put(self, record: ProbeRecord) -> None:
        """Write *record* under its own key, replacing any earlier reading."""
        row = self._session.execute(
            select(ProbeRecordRow).where(
                ProbeRecordRow.endpoint_fingerprint == record.endpoint_fingerprint,
                ProbeRecordRow.model == record.model,
                ProbeRecordRow.protocol == record.protocol,
            )
        ).scalar_one_or_none()
        if row is None:
            row = ProbeRecordRow()
            self._session.add(row)
        row.endpoint_fingerprint = record.endpoint_fingerprint
        row.model = record.model
        row.protocol = record.protocol
        row.outcomes = {
            capability.value: outcome.value for capability, outcome in record.outcomes.items()
        }
        row.evidence = {capability.value: text for capability, text in record.evidence.items()}
        row.probes_run = sorted(capability.value for capability in record.probes_run)
        row.observed_at = record.observed_at
        self._session.flush()


def _record_from_row(row: ProbeRecordRow) -> ProbeRecord:
    """Rebuild the record the row holds.

    **A value this build does not know is dropped, not guessed at.** A row
    written by a build with a capability this one has never heard of is read
    as a record that says nothing about that capability -- which leaves it
    ``unverified``, the fail-closed answer -- rather than as a record whose
    vocabulary has been silently extended.
    """
    return ProbeRecord(
        endpoint_fingerprint=row.endpoint_fingerprint,
        model=row.model,
        protocol=row.protocol,
        outcomes=_outcomes_from_json(row.outcomes),
        evidence=_evidence_from_json(row.evidence),
        probes_run=_probes_from_json(row.probes_run),
        observed_at=row.observed_at,
    )


def _outcomes_from_json(raw: Any) -> dict[Capability, CapabilityOutcome]:
    outcomes: dict[Capability, CapabilityOutcome] = {}
    for key, value in _mapping(raw).items():
        capability = _capability(key)
        outcome = _outcome(value)
        if capability is None or outcome is None:
            continue
        outcomes[capability] = outcome
    return outcomes


def _evidence_from_json(raw: Any) -> dict[Capability, str]:
    evidence: dict[Capability, str] = {}
    for key, value in _mapping(raw).items():
        capability = _capability(key)
        if capability is None or not isinstance(value, str):
            continue
        evidence[capability] = value
    return evidence


def _probes_from_json(raw: Any) -> frozenset[Capability]:
    if not isinstance(raw, list):
        return frozenset()
    found: set[Capability] = set()
    for item in raw:
        capability = _capability(item)
        if capability is not None:
            found.add(capability)
    return frozenset(found)


def _mapping(raw: Any) -> Mapping[Any, Any]:
    return raw if isinstance(raw, Mapping) else {}


def _capability(raw: Any) -> Capability | None:
    try:
        return Capability(str(raw))
    except ValueError:
        return None


def _outcome(raw: Any) -> CapabilityOutcome | None:
    try:
        return CapabilityOutcome(str(raw))
    except ValueError:
        return None
