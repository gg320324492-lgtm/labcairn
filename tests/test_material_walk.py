"""The workspace walk: permissions, idempotence, and failure isolation.

A walk that reached around the permission boundary would inventory material
the user has not agreed to inventory, so the first tests here are about
*refusal*, not ingestion: a denied subtree must be invisible to the walk
exactly as it is to the user, and the material under it must produce no
``sources`` row.

Everything else follows the two properties ADR-0009 makes load-bearing: a
second walk over unchanged bytes writes nothing, and one unreadable file
does not stop the ones after it.
"""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any

import pytest

from labcairn.core.ids import TaskId, new_id
from labcairn.material import ingest_workspace
from labcairn.material.walk import WalkReport
from labcairn.security.policy import PermissionPolicy
from labcairn.workspace.readonly import SourceMaterial
from labcairn.workspace.roots import Workspace

NOW = dt.datetime(2026, 10, 17, tzinfo=dt.UTC)
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "papers"


@pytest.fixture
def workspace(tmp_path: pathlib.Path) -> Workspace:
    root = tmp_path / "ws"
    sources = root / "sources"
    (sources / "papers").mkdir(parents=True)
    (sources / "papers" / "a.pdf").write_bytes(b"%PDF-1.4 a")
    (sources / "notes.md").write_text("# Notes\n\nsome text\n", encoding="utf-8")
    (sources / "data.csv").write_text("trial,mean\nalpha,3.5\n", encoding="utf-8")
    (sources / "archive.zip").write_bytes(b"PK\x03\x04 not a format we read")
    return Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))


@pytest.fixture
def material(workspace: Workspace) -> SourceMaterial:
    """An *allowing* policy.

    ``PermissionPolicy()`` denies ``source.inventory`` outright, so a walk with
    it sees nothing -- which is the correct behaviour and is what the boundary
    test asserts. The tests that expect files to be found need the grant.
    """
    return SourceMaterial(workspace, _allowing_policy())


def _allowing_policy() -> PermissionPolicy:
    from labcairn.security.capabilities import CapabilityId
    from labcairn.security.policy import Permission, Rule

    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


@pytest.fixture
def session(tmp_path: pathlib.Path) -> Any:
    from labcairn.db.migrations import upgrade_to_head
    from labcairn.db.session import create_db_engine, create_session_factory

    target = tmp_path / "walk.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    made = create_session_factory(engine)()
    yield made
    made.close()
    engine.dispose()


def test_the_walk_finds_every_file_under_the_source_root(
    workspace: Workspace, material: SourceMaterial, session: Any
) -> None:
    report = ingest_workspace(session, material, ingested_at=NOW)
    keys = {o.material.source.relative_path for o in report.outcomes}
    assert keys == {
        "papers/a.pdf",
        "notes.md",
        "data.csv",
        "archive.zip",
    }
    assert report.failures == ()


def test_a_format_with_no_adapter_is_inventoried_not_skipped(
    material: SourceMaterial, session: Any
) -> None:
    """A ``.zip`` is a fact about the workspace, not an omission."""
    report = ingest_workspace(session, material, ingested_at=NOW)
    assert "archive.zip" in report.skipped
    zipped = next(o for o in report.outcomes if o.material.source.relative_path == "archive.zip")
    assert zipped.material.source.kind.value == "other"
    assert zipped.material.source.content_sha256  # hashed
    assert zipped.text_rows_written == 0  # nothing extracted


def test_a_second_walk_writes_nothing(material: SourceMaterial, session: Any) -> None:
    """ADR-0009's idempotence, now end to end over a real workspace."""
    first = ingest_workspace(session, material, ingested_at=NOW)
    assert first.texts_written > 0 or first.outcomes
    second = ingest_workspace(session, material, ingested_at=NOW + dt.timedelta(days=1))
    assert second.texts_written == 0
    assert second.problems_written == 0
    assert set(second.source_ids) == set(first.source_ids)


def test_the_default_policy_denies_source_listing_so_the_walk_sees_nothing(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """The boundary test.

    ``PermissionPolicy()`` with no grants denies ``source.inventory``
    entirely, and ``list_dir`` returns empty rather than raising. A walk that
    reached around the policy -- by scanning the filesystem directly -- would
    still see every file. This asserts it sees none.
    """
    root = tmp_path / "ws2"
    sources = root / "sources"
    (sources / "public").mkdir(parents=True)
    (sources / "public" / "ok.md").write_text("# fine" + chr(10), encoding="utf-8")
    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    report = ingest_workspace(session, SourceMaterial(ws, PermissionPolicy()), ingested_at=NOW)
    assert report.outcomes == ()
    assert report.failures == ()


def test_the_walk_reads_what_an_allowing_policy_permits(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """The complement: a policy that grants inventory sees the files."""
    root = tmp_path / "ws4"
    sources = root / "sources"
    (sources / "public").mkdir(parents=True)
    (sources / "public" / "ok.md").write_text(
        "# fine" + chr(10) + "body" + chr(10), encoding="utf-8"
    )
    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    report = ingest_workspace(session, SourceMaterial(ws, _allowing_policy()), ingested_at=NOW)
    assert "public/ok.md" in {o.material.source.relative_path for o in report.outcomes}


def test_one_unreadable_file_does_not_stop_the_walk(tmp_path: pathlib.Path, session: Any) -> None:
    root = tmp_path / "ws3"
    sources = root / "sources"
    sources.mkdir(parents=True)
    (sources / "a.md").write_text("# first\n", encoding="utf-8")
    (sources / "b.bin").write_bytes(bytes(range(256)))
    (sources / "c.md").write_text("# third\n", encoding="utf-8")
    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    report = ingest_workspace(session, SourceMaterial(ws, _allowing_policy()), ingested_at=NOW)
    paths = {o.material.source.relative_path for o in report.outcomes}
    assert {"a.md", "c.md"} <= paths


def test_max_files_bounds_the_walk(
    workspace: Workspace, material: SourceMaterial, session: Any
) -> None:
    report = ingest_workspace(session, material, ingested_at=NOW, max_files=2)
    assert len(report.outcomes) == 2


def test_the_report_exposes_its_counts(material: SourceMaterial, session: Any) -> None:
    report = ingest_workspace(session, material, ingested_at=NOW)
    assert isinstance(report, WalkReport)
    assert len(report.source_ids) == len(report.outcomes)
    assert report.texts_written >= 0


def test_a_text_locator_keeps_its_line_number(session: Any) -> None:
    """The row mapping bug that ``getattr`` hid.

    ``to_text_row`` read ``TextLocator.line`` as ``line_start`` -- a name
    the locator does not have -- so ``getattr(..., None)`` returned ``None``
    for every text line and the ``text_shape`` CHECK refused the insert. It
    stayed invisible until a ``.md`` file produced a text locator, and then
    it looked like a store failure rather than a mapping mistake. Every text
    locator is affected, Markdown or not.
    """
    from labcairn.db.materials import texts_for
    from labcairn.material.ingest import ingest_into_store

    outcome = ingest_into_store(
        session,
        ("line one" + chr(10) + "line two" + chr(10)).encode(),
        relative_path="notes.txt",
        display_name="notes.txt",
        ingested_at=NOW,
    )
    assert outcome.material.texts, "no units extracted"
    stored = texts_for(
        session,
        source_content_sha256=outcome.material.source.content_sha256,
        extraction_version=outcome.material.extraction_version,
    )
    assert [row.line_start for row in stored] == [1, 2], [row.line_start for row in stored]
    assert [row.text for row in stored] == ["line one", "line two"]


def test_an_edited_file_is_re_ingested_under_a_new_hash(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """A changed file must move the recorded hash, not freeze at version one.

    The content-derived default ``source_id`` plus ``UNIQUE(relative_path)``
    made every re-walk of an edited file a permanent IntegrityError, so the
    stored hash and text stayed at the first version forever. The fix keys
    the id to the *location*, so the edit takes the refresh branch.

    The superseded text is **kept**, not deleted: ADR-0004 A2 says drift
    invalidates downstream rather than silently re-reading, and an anchor
    already pointing into the old bytes must still resolve to them.
    """
    import hashlib

    root = tmp_path / "ws5"
    sources = root / "sources"
    sources.mkdir(parents=True)
    notes = sources / "notes.md"
    # newline="" so the bytes are exactly what is written. write_text would
    # otherwise translate chr(10) to chr(13)+chr(10) on Windows, and the
    # expected hash below would then be the hash of a file nobody wrote --
    # a test that fails on one platform and passes on another.
    notes.write_text("version one" + chr(10), encoding="utf-8", newline="")
    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    mat = SourceMaterial(ws, _allowing_policy())

    first = ingest_workspace(session, mat, ingested_at=NOW)
    assert first.failures == () and len(first.outcomes) == 1
    source_id = first.outcomes[0].material.source.source_id

    notes.write_text("version two, edited" + chr(10), encoding="utf-8", newline="")
    second = ingest_workspace(session, mat, ingested_at=NOW)
    assert second.failures == (), [m for _, m in second.failures]
    assert second.outcomes[0].material.source.source_id == source_id, (
        "the identity moved when the bytes changed"
    )

    from sqlalchemy import text as text_sql

    row = session.execute(
        text_sql("SELECT content_sha256 FROM sources WHERE source_id = :s"), {"s": source_id}
    ).fetchone()
    assert row is not None
    assert row[0] == hashlib.sha256(("version two, edited" + chr(10)).encode()).hexdigest(), (
        "the recorded hash did not follow the edit"
    )

    texts = [t[0] for t in session.execute(text_sql("SELECT text FROM source_texts")).fetchall()]
    assert "version two, edited" in texts
    assert "version one" in texts, (
        "the superseded text must survive: an anchor pointing into it still "
        "resolves, per ADR-0004 A2"
    )


def test_two_source_roots_holding_the_same_name_are_documented_as_a_schema_limit(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """Two roots, two ``notes.md``. Documented rather than silently half-done.

    ``sources.relative_path`` is workspace-relative and globally UNIQUE, so
    the second root's ``notes.md`` cannot be stored alongside the first's --
    the schema rejects it, not the walk. The walk correctly visits both; the
    second loses at the store. This test pins that behaviour so the day the
    UNIQUE becomes ``(root_id, relative_path)`` it will say so.
    """
    root = tmp_path / "ws6"
    src_a = root / "sources" / "a"
    src_b = root / "sources" / "b"
    src_a.mkdir(parents=True)
    src_b.mkdir(parents=True)
    (src_a / "notes.md").write_text("from root a" + chr(10), encoding="utf-8")
    (src_b / "notes.md").write_text("from root b" + chr(10), encoding="utf-8")
    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(src_a, src_b))
    report = ingest_workspace(session, SourceMaterial(ws, _allowing_policy()), ingested_at=NOW)
    # The walk visited both; one failed at the store on the UNIQUE path.
    visited = len(report.outcomes) + len(report.failures)
    assert visited == 2, f"the walk missed a root entirely: {visited}"
    assert len(report.outcomes) == 1, (
        "if both now ingest, sources.relative_path is no longer globally unique -- "
        "update this test and the schema together"
    )


def test_max_files_is_a_real_bound(
    workspace: Workspace, material: SourceMaterial, session: Any
) -> None:
    """``max_files=1`` used to return two files.

    The check sat only in the file branch, so a directory recursion walked
    past the limit.
    """
    report = ingest_workspace(session, material, ingested_at=NOW, max_files=1)
    assert len(report.outcomes) == 1, [o.material.source.relative_path for o in report.outcomes]
