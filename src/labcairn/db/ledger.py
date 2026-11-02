"""The artifact ledger on disk: the same entries, in a table a new process reads.

:class:`~labcairn.skills.ledger.ArtifactLedger` answers two questions that must
survive the process that asked them: *what did this run produce*, and *is what
the slot holds now still what was verified*. In memory both answers died with
the interpreter. This module is the store that puts them in SQLite.

**The store does no verification, deliberately.** :meth:`append` serialises and
writes; :meth:`entries` reads and reconstructs. Type checking, lineage and the
digest comparison stay in :class:`~labcairn.skills.ledger.ArtifactLedger`, so a
read from this store faces exactly the guards a read from the in-memory store
faces. A store that quietly "fixed" a mismatched digest would be a second
authority over the property the ledger exists to hold.

**The bytes written are the bytes hashed.** ``payload`` is
``artifact.json_canonical()`` — the same serialisation
:func:`~labcairn.skills.ledger.artifact_digest` runs over. A reader parses the
payload back into the model and the ledger re-hashes the reconstructed model;
for the untampered row those bytes are identical, so the digest comparison is a
comparison of stored bytes, not of two serialisers' opinions.

**A row written under another algorithm is refused, not compared.**
``digest_algorithm`` is stored with every entry because a durable row outlives
the release that wrote it. Comparing an old algorithm's digest to today's would
produce a mismatch and call it tampering; the honest answer is that the check
cannot be performed.

**One database can hold several ledgers.** ``ledger_id`` scopes every read and
write. The default is for a caller with one ledger per database; the
orchestrator's one-ledger-per-run contract is honoured by passing the run id.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from labcairn.db.models import ArtifactLedgerEntryRow
from labcairn.db.session import session_scope
from labcairn.skills.artifacts import ArtifactKind, StageName, artifact_type
from labcairn.skills.errors import LedgerAlgorithmError
from labcairn.skills.ledger import (
    DIGEST_ALGORITHM,
    RecordedArtifact,
    artifact_lineage,
)

#: The ledger a caller gets when it does not name one. A database with one
#: ledger uses this; a database with several must name them.
DEFAULT_LEDGER_ID: Final[str] = "default"


class SqliteArtifactLedgerStore:
    """An :class:`~labcairn.skills.ledger.ArtifactLedgerStore` over SQLite.

    One instance bound to one ``ledger_id``. It opens a session per operation
    from *sessions* and owns that transaction: the ledger's writes are single
    rows, and holding a caller's session open across a run would make the
    ledger's durability depend on when somebody else commits.

    :param sessions: the session factory bound to the database.
    :param ledger_id: which ledger this store reads and writes. Two stores on
        the same factory with different ids do not see each other's entries.
    """

    def __init__(
        self, sessions: sessionmaker[Session], *, ledger_id: str = DEFAULT_LEDGER_ID
    ) -> None:
        if not ledger_id:
            raise ValueError("a ledger id must not be empty: it is the scope of every read")
        self._sessions = sessions
        self._ledger_id = ledger_id

    @property
    def ledger_id(self) -> str:
        """The ledger this store is bound to."""
        return self._ledger_id

    def append(self, entry: RecordedArtifact) -> None:
        """Write one entry. It becomes the latest for its stage."""
        row = ArtifactLedgerEntryRow(
            ledger_id=self._ledger_id,
            kind=entry.kind.value,
            stage=entry.stage.value,
            payload=entry.artifact.json_canonical(),
            digest=entry.digest,
            digest_algorithm=DIGEST_ALGORITHM,
            produced_by=None if entry.produced_by is None else entry.produced_by.value,
            recorded_at=entry.recorded_at,
        )
        with session_scope(self._sessions) as session:
            session.add(row)

    def entries(self) -> list[RecordedArtifact]:
        """Every entry for this ledger, oldest first."""
        with self._sessions() as session:
            rows = session.scalars(
                select(ArtifactLedgerEntryRow)
                .where(ArtifactLedgerEntryRow.ledger_id == self._ledger_id)
                .order_by(ArtifactLedgerEntryRow.entry_id)
            ).all()
        return [self._recorded(row) for row in rows]

    def current(self) -> dict[StageName, RecordedArtifact]:
        """The latest entry per stage, in first-production order.

        Rebuilt from :meth:`entries` on every call rather than cached. A cache
        here would answer from an object this process remembered — exactly the
        behaviour the durable ledger exists to remove — and a row changed after
        the cache was filled would not be seen by the read-time check.
        """
        current: dict[StageName, RecordedArtifact] = {}
        for entry in self.entries():
            current[entry.stage] = entry
        return current

    @staticmethod
    def _recorded(row: ArtifactLedgerEntryRow) -> RecordedArtifact:
        """Turn one row back into the entry it recorded.

        The artifact is rebuilt from ``payload`` — the bytes the digest is over
        — rather than from any column that repeats what the payload already
        says. ``derived_from`` is read from the rebuilt artifact for the same
        reason: the lineage inside the hashed bytes is the authoritative one,
        and a second copy would be a second answer.
        """
        if row.digest_algorithm != DIGEST_ALGORITHM:
            raise LedgerAlgorithmError(
                f"ledger entry {row.entry_id} was recorded under digest algorithm "
                f"{row.digest_algorithm!r}, but this build checks "
                f"{DIGEST_ALGORITHM!r}. A digest from another algorithm is not "
                f"evidence about these bytes; re-record the artifact or read it "
                f"with the build that wrote it."
            )
        kind = ArtifactKind(row.kind)
        artifact = artifact_type(kind).model_validate_json(row.payload)
        return RecordedArtifact(
            kind=kind,
            stage=StageName(row.stage),
            artifact=artifact,
            digest=row.digest,
            produced_by=None if row.produced_by is None else StageName(row.produced_by),
            derived_from=artifact_lineage(artifact),
            recorded_at=row.recorded_at,
        )


__all__ = ["DEFAULT_LEDGER_ID", "SqliteArtifactLedgerStore"]
