"""Alembic environment.

Wired to :mod:`labcairn.db.models` for autogenerate, and to ``sqlalchemy.url``
from ``migrations/alembic.ini`` for the actual run. Nothing here reads an
environment variable: the URL is a local file path, and a store whose location
came from the ambient environment is a store whose authority depends on how it
was launched.

``render_as_batch`` is on because SQLite cannot ``ALTER`` most things in place.
A later revision that adds a column to a populated database needs the
copy-and-drop dance Alembic performs for batch mode; without it the migration
would be written and would fail against real data.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from labcairn.db.models import Base

#: Autogenerate compares the database against this metadata.
target_metadata = Base.metadata


def _url() -> str:
    return context.config.get_main_option("sqlalchemy.url") or "sqlite:///./labcairn.db"


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    configuration = context.config.get_section(context.config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
