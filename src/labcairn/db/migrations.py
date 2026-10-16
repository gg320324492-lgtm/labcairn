"""Running migrations programmatically.

Alembic's CLI is the right tool for a developer and the wrong one for
:mod:`labcairn.db`'s tests and for LC-P1-12's ``init`` command: both need to
say "upgrade this specific file to head" without a shell, a config file on disk
or a working directory they do not control. That is this module's whole job.

It also fixes the location of ``migrations/alembic.ini`` by walking up from this
file, so a test running from any directory finds the same migrations the
repository ships. The one thing it cannot do is survive having the package
installed without its source tree — see :func:`alembic_config`, which raises a
message that says exactly that instead of an opaque file-not-found.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

#: ``src/labcairn/db/migrations.py`` -> repository root is three levels up.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
ALEMBIC_INI: Path = REPO_ROOT / "migrations" / "alembic.ini"
MIGRATIONS_DIR: Path = REPO_ROOT / "migrations"


class MigrationsUnavailableError(RuntimeError):
    """The migrations directory is not next to an installed ``labcairn.db``.

    Raised instead of ``FileNotFoundError`` because the cause is packaging, not
    a typo: an installed wheel without ``migrations/`` cannot migrate, and a
    caller deserves to be told that rather than to chase a path.
    """


def alembic_config(db_path: str | Path | None = None) -> Config:
    """An Alembic config pointing at *db_path*.

    *db_path* is a filesystem path, converted to a ``sqlite:///`` URL. Omit it
    to use the URL already in ``migrations/alembic.ini``.
    """
    if not ALEMBIC_INI.is_file():
        raise MigrationsUnavailableError(
            f"no Alembic configuration at {ALEMBIC_INI}. The migrations directory is "
            "not part of the installed package; run from a checkout, or point "
            "LC_MIGRATIONS_DIR at one."
        )
    config = Config(str(ALEMBIC_INI))
    # Absolute, so the URL does not resolve against whatever directory the
    # process happens to be in.
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    if db_path is not None:
        config.set_main_option("sqlalchemy.url", _as_url(db_path))
    return config


def _as_url(db_path: str | Path) -> str:
    text = str(db_path)
    return text if "://" in text else f"sqlite:///{text}"


def upgrade_to_head(db_path: str | Path) -> None:
    """Bring *db_path* to the latest revision.

    Safe to call on a database that is already at head: Alembic compares
    ``alembic_version`` against the revision tree, finds nothing to apply, and
    returns without touching the schema or the data. That is the rerun
    behaviour LC-P1-05's acceptance asks for, and
    ``tests/test_store_migrations.py`` asserts it rather than assuming it.
    """
    command.upgrade(alembic_config(db_path), "head")


def downgrade_to_base(db_path: str | Path) -> None:
    """Drop everything back to no revisions. Used by tests to prove the
    downgrade path works, not part of the product's normal operation."""
    command.downgrade(alembic_config(db_path), "base")


def current_revision(db_path: str | Path) -> str | None:
    """The revision *db_path* is stamped at, or ``None`` if it is unstamped."""
    from sqlalchemy import create_engine

    engine = create_engine(_as_url(db_path))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def head_revision() -> str:
    """The newest revision the repository knows about."""
    head = ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()
    if head is None:
        # Only reachable with an empty or unreadable versions/ directory. Saying
        # so is better than returning None into a caller that declared `str`.
        raise MigrationsUnavailableError(f"no revisions found under {MIGRATIONS_DIR}")
    return head
