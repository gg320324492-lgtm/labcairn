"""Engine construction: three pragmas and one ``BEGIN`` clause.

Getting ``BEGIN IMMEDIATE`` to actually reach SQLite needed two settings, and
one of the three below turned out on measurement not to be load-bearing. Both
facts are recorded here because the first version of this docstring asserted
the wrong one.

**1. ``BEGIN IMMEDIATE`` on SQLAlchemy's ``begin`` event.** SQLAlchemy's default
is a *deferred* ``BEGIN``, and a deferred transaction takes the write lock only
at its first write. That is exactly the read-then-write upgrade ADR-0003 C3
forbids: two connections both read, both try to write, and one fails with
``SQLITE_BUSY`` instead of waiting. ``IMMEDIATE`` takes the write lock up front,
so the loser waits at the lock rather than failing at the upgrade. This one is
load-bearing and is asserted directly by
``tests/test_store_concurrency.py::test_the_write_lock_is_taken_before_the_first_read``.

**2. ``isolation_level = None`` — defensive, and measurably *not* required.**
This was originally documented as the fix for ``cannot start a transaction
within a transaction``: Python's ``sqlite3`` runs in legacy mode by default and
opens a deferred transaction implicitly before the first DML. That reasoning is
**wrong**, and removing the setting was tried to check it — 50 tests still pass
without it. The reason is that pysqlite decides whether to inject a ``BEGIN``
from ``sqlite3_get_autocommit()``: once ``BEGIN IMMEDIATE`` has opened a
transaction, the driver sees one is already active and does not issue a second.
Verified against a raw connection, not inferred.

It is kept anyway, for the property the failed reasoning was reaching for: with
it unset, the DBAPI connection's own ``commit()``/``rollback()`` and implicit
transaction handling become a second authority over transaction boundaries, one
SQLAlchemy does not control. Setting it to ``None`` removes that second
authority outright. Cheap insurance, honestly labelled as such.

**3. ``PRAGMA foreign_keys = ON`` per connection.** SQLite ships with foreign
key enforcement **off**, and it is a per-connection pragma, not a database one.
Without this line every ``ForeignKey`` in :mod:`labcairn.db.models` is
documentation. The deferred constraints on ``events`` — the ones that let an
event be inserted before the state row it describes — are enforced at COMMIT
under this pragma. Asserted by
``tests/test_store_atomicity.py::test_a_dangling_reference_is_caught_at_commit``.

``WAL`` is set for concurrency: it lets readers proceed while a writer holds the
write lock, and it is what makes the multi-threaded ``seq`` allocation test
meaningful rather than a test of ``SQLITE_BUSY``. ``busy_timeout`` turns lock
contention into a wait rather than an immediate error, because ``BEGIN
IMMEDIATE`` failing fast is correct behaviour but makes a concurrent writer look
like a bug.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

#: How long a writer waits for the write lock before raising ``database is
#: locked``. Long enough that a burst of concurrent writers serialises cleanly;
#: short enough that a genuinely wedged writer is reported rather than hanging.
DEFAULT_BUSY_TIMEOUT_MS: Final[int] = 10_000


def create_db_engine(
    url: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    echo: bool = False,
) -> Engine:
    """An engine configured for ADR-0003 C3's transaction boundary.

    *url* may be a path or a ``sqlite:///`` URL. ``check_same_thread=False`` is
    required because a SQLite connection belongs to the thread that made it and
    the concurrency tests legitimately use one engine from several threads; SQLAlchemy's
    pool still hands each thread its own connection, so this does not make a
    connection shared *within* a thread.
    """
    resolved = str(url)
    if "://" not in resolved:
        resolved = f"sqlite:///{resolved}"

    engine = create_engine(
        resolved,
        echo=echo,
        future=True,
        connect_args={
            "check_same_thread": False,
            "timeout": busy_timeout_ms / 1000,
            # Step 1 above: stop the driver emitting its own BEGIN.
            "isolation_level": None,
        },
    )

    @event.listens_for(engine, "connect")
    def _configure_connection(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            # Off by default in SQLite. Without this every ForeignKey in the
            # models module is inert prose.
            cursor.execute("PRAGMA foreign_keys=ON")
            # Readers do not block the writer. Persistent in the database file.
            cursor.execute("PRAGMA journal_mode=WAL")
            # A write lock that is held is waited for, not reported immediately.
            cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(connection: Any) -> None:
        # Step 2 above. Deliberately raw: SQLAlchemy has no portable spelling
        # of "BEGIN IMMEDIATE", and the whole point of C3 is this exact clause.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """A session factory bound to *engine*.

    ``expire_on_commit=False`` so objects stay readable after COMMIT without a
    refresh; without it, reading an attribute after commit silently issues a
    SELECT on a session that may already be closed.
    """
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """A session that commits on clean exit and rolls back on any exception."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
