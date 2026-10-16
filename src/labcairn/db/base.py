"""Declarative base and the conventions every table in the store follows.

Two conventions exist so that a schema dump stays readable and so a table can
never grow a column the ADR has not sanctioned:

* **Every table has an integer ``id`` that is *not* a domain identity.** ``id``
  is table-wide row identity; ``task_id`` / ``run_id`` / ``event_id`` are the
  domain identities that cross module boundaries. Keeping them separate is what
  lets ``events.seq`` be a per-Task counter without inheriting rowid's
  table-wide uniqueness (ADR-0003 C1).
* **Constraints are generated from the frozen contracts, not retyped.** The
  ``events`` CHECK constraints below are built from
  :class:`~labcairn.runtime.event.EventType` at import time, so a new event
  type that is added to the frozen contract cannot be silently absent from the
  store, and the store cannot invent a type the contract does not know.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

#: Deterministic constraint names. Alembic needs named constraints to emit
#: ``ALTER`` statements for later revisions, and unnamed constraints cannot be
#: altered at all — they can only be dropped and recreated.
NAMING_CONVENTION: Final[dict[str, Any]] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for the task store."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def sql_string_list(values: Iterable[str]) -> str:
    """Render *values* as a SQL ``IN`` list of single-quoted literals.

    Used to build CHECK constraints from a frozen enum. The values are a closed
    set of the project's own identifiers (event type names), never user input,
    so the interpolation is safe — and it keeps the constraint text identical
    between the ORM metadata and the migration, which a behavioural test
    compares rather than a hand-maintained copy.
    """
    ordered = sorted(values)
    if not ordered:
        raise ValueError("an empty IN list would match nothing and reject every row")
    return "(" + ", ".join(f"'{v}'" for v in ordered) + ")"
