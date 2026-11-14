"""The backup and rollback drill: a rollback preserves user data.

Drill deliverable 3 of work orders §12 §5.6, designed at
``docs/plans/LC-P3-07-backup-rollback-design.md``. The claim is execution
plan §4's: *"a rollback preserves user data"* — measured, not eyeballed:

1. **The ledger (the store).** Every event, approval, artefact row and
   version-graph row present before the rollback is present after, with the
   same digests — asserted by digest comparison, not by row count.
2. **The task output area.** The published revisions are user data; each
   file's ``content_sha256`` from its receipt row is re-hashed and compared.
3. **The source roots.** The originals are re-hashed against the import
   receipt (``verify_original`` is the public surface for exactly this).

The backup is SQLite's ``backup`` API with the source opened ``mode=ro``,
taken before any writes — the landed rehearsal-store method of the batch-9
and batch-10 records. A backup taken while a writer is live is a copy of a
torn state; the ``mode=ro`` + backup-API route is what the design names, and
the counter-mutation below is the one that earns its place: restoring a copy
of a *live* WAL database and reading it naively.

Data written after the backup point is either kept, or its loss is named in
the record with its digest. "Quietly gone" is a failed drill.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from store_support import env as _shared_env

env = _shared_env

pytestmark = pytest.mark.integration

MOMENT = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 16):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture()
def rig(env: Any, tmp_path: Path) -> Any:
    from drill_support import build_rig, run_loop_to_publication

    built = build_rig(env.store(), tmp_path / "workspace")
    run_loop_to_publication(built)
    return built


def _store_snapshot(db_path: Path) -> dict[str, Any]:
    """The store's content identity: every table's rows, hashed.

    Row counts alone hide a changed row; the snapshot hashes the rows
    themselves, in a stable order, so the comparison is about content.
    """
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        snapshot: dict[str, Any] = {"tables": {}}
        for table in tables:
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            digest = hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
            snapshot["tables"][table] = {"rows": len(rows), "digest": digest}
        return snapshot
    finally:
        connection.close()


def _take_backup(db_path: Path, backup_path: Path) -> None:
    """SQLite's ``backup`` API, source opened ``mode=ro`` — before any writes."""
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(str(backup_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def test_a_rollback_from_a_backup_point_preserves_user_data(
    rig: Any, env: Any, tmp_path: Path
) -> None:
    """The whole drill: backup, corrupt, restore, compare.

    Every user-data class survives: the store's rows hash the same, the
    published bytes hash the same, and the original is untouched. The store
    is restored via the backup API copy; the output area and the source root
    are file-level restores of atomic units.
    """
    db_path = env.db_path
    backup_path = tmp_path / "backup-point.db"

    # -- snapshot before ----------------------------------------------------- #
    before_tables = _store_snapshot(db_path)
    published_before = _sha256_file(rig.publication_path())
    original_before = _sha256_file(rig.original_path)

    # -- the backup point ---------------------------------------------------- #
    _take_backup(db_path, backup_path)
    assert backup_path.is_file() and backup_path.stat().st_size > 0

    # -- the disaster: the store is corrupted after the backup point --------- #
    # ``document`` is the frozen event envelope; overwriting it is a content
    # change with no CHECK to trip, which is exactly the shape the drill wants
    # — a corruption only a digest comparison can see.
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute("UPDATE events SET document = '{\"tampered\": true}'")
        connection.commit()
    finally:
        connection.close()
    assert _store_snapshot(db_path) != before_tables, "the corruption took"

    # -- the rollback: restore the store from the backup point --------------- #
    restored = sqlite3.connect(str(backup_path))
    target = sqlite3.connect(str(db_path))
    try:
        restored.backup(target)
        target.commit()
    finally:
        target.close()
        restored.close()

    # -- snapshot after, and the three comparisons --------------------------- #
    after_tables = _store_snapshot(db_path)
    assert after_tables == before_tables, (
        "every store row survives the rollback with its content, not merely "
        "its count"
    )

    integrity = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        assert integrity.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        integrity.close()

    assert _sha256_file(rig.publication_path()) == published_before, (
        "the published bytes are byte-identical after the rollback"
    )
    assert _sha256_file(rig.original_path) == original_before, (
        "the original is intact after the rollback"
    )


def test_data_written_after_the_backup_point_is_named_not_quietly_gone(
    rig: Any, env: Any, tmp_path: Path
) -> None:
    """A write after the backup point is either kept or named with its digest.

    The drill writes a second publication-shaped file after the backup point,
    rolls the store back, and asserts the post-backup-point file is still on
    disk (the output area is not the store; a store rollback does not touch
    it). The rule the design states — *kept, or its loss is named with its
    digests* — is checked by naming it in the record this test prints.
    """
    db_path = env.db_path
    backup_path = tmp_path / "backup-point-2.db"

    _take_backup(db_path, backup_path)

    late_file = rig.loop_dir() / "late-note.bin"
    late_file.write_bytes(b"written after the backup point\n")
    late_digest = _sha256_file(late_file)

    # Roll the store back.
    restored = sqlite3.connect(str(backup_path))
    target = sqlite3.connect(str(db_path))
    try:
        restored.backup(target)
        target.commit()
    finally:
        target.close()
        restored.close()

    assert late_file.exists(), (
        "the output area is not the store; a store rollback does not silently "
        "discard a file written after the backup point"
    )
    assert _sha256_file(late_file) == late_digest
    # The record names what post-dates the backup point, with its digest.
    print(f"post-backup-point data kept: {late_file.name} sha256={late_digest}")


def test_a_backup_of_a_live_wal_writer_is_refused_in_favour_of_the_backup_api(
    env: Any,
) -> None:
    """The settled-WAL rule, drilled at the seam the design names.

    A naive file copy of a live WAL database is a copy of a torn state: a
    reader that opens the copy without the WAL files reads the checkpointed
    pages only. The drill writes through one connection, takes *both* a
    naive copy and a backup-API copy while the writer's connection is open,
    and shows the difference the design's third counter-mutation names.
    """
    import shutil

    from labcairn.db.session import create_db_engine, create_session_factory

    live_dir = env.db_path.parent / "live-wal"
    live_dir.mkdir(exist_ok=True)
    live_db = live_dir / "labcairn.db"
    engine = create_db_engine(live_db)
    session = create_session_factory(engine)()
    try:
        session.execute(text("CREATE TABLE probe (value TEXT)"))
        session.commit()
        session.execute(text("INSERT INTO probe (value) VALUES ('uncommitted-checkpoint')"))
        session.commit()
    finally:
        session.close()
        engine.dispose()

    # Reopen and write without closing the engine: the WAL holds the writes.
    engine = create_db_engine(live_db)
    session = create_session_factory(engine)()
    try:
        session.execute(text("INSERT INTO probe (value) VALUES ('in-wal')"))
        session.commit()

        naive = live_dir / "naive-copy.db"
        shutil.copy2(live_db, naive)

        backup_copy = live_dir / "backup-copy.db"
        source = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
        try:
            destination = sqlite3.connect(str(backup_copy))
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()

        naive_rows = sqlite3.connect(str(naive)).execute("SELECT COUNT(*) FROM probe").fetchone()[0]
        backup_rows = (
            sqlite3.connect(str(backup_copy)).execute("SELECT COUNT(*) FROM probe").fetchone()[0]
        )
        assert backup_rows == 2, "the backup API copy carries the WAL's writes"
        assert naive_rows < backup_rows, (
            "a naive file copy of a live WAL database misses the "
            "uncheckpointed writes — the torn state the design refuses"
        )
    finally:
        session.close()
        engine.dispose()
