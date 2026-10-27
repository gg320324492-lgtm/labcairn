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
from pathlib import Path
from typing import Any

import pytest

from conftest import migrated_database_from
from labcairn.core.ids import TaskId, new_id
from labcairn.material import ingest_workspace
from labcairn.material.walk import WalkReport
from labcairn.security.policy import PermissionPolicy
from labcairn.workspace.readonly import SourceMaterial
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.unit

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
def session(migrated_database_template: Path, tmp_path: pathlib.Path) -> Any:
    from labcairn.db.session import create_db_engine, create_session_factory

    target = tmp_path / "walk.db"
    migrated_database_from(migrated_database_template, target)
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
        "sources/papers/a.pdf",
        "sources/notes.md",
        "sources/data.csv",
        "sources/archive.zip",
    }
    assert report.failures == ()


def test_a_format_with_no_adapter_is_inventoried_not_skipped(
    material: SourceMaterial, session: Any
) -> None:
    """A ``.zip`` is a fact about the workspace, not an omission."""
    report = ingest_workspace(session, material, ingested_at=NOW)
    assert "archive.zip" in report.skipped
    zipped = next(
        o for o in report.outcomes if o.material.source.relative_path == "sources/archive.zip"
    )
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
    assert "sources/public/ok.md" in {o.material.source.relative_path for o in report.outcomes}


def test_a_failing_file_does_not_stop_the_walk_and_leaves_the_rest_stored(
    tmp_path: pathlib.Path, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure path, asserted against the **store**, not a path subset.

    The earlier version used a ``.bin`` fixture -- ``SourceKind.OTHER``, which
    never fails -- and asserted ``{"a.md", "c.md"} <= paths``, a subset check
    that passes whatever else happens. So the whole try/except/rollback path
    had zero coverage, and two mutations survived: deleting the per-file
    ``commit`` and deleting the ``rollback``.

    Both are caught here. Without the commit, ``a.md`` is still pending when
    ``boom.md``'s rollback fires, so the report claims a file the store does
    not have -- and the walk's own promise, that a failure "does not roll
    back the files already ingested", is inverted.
    """
    from sqlalchemy import text as text_sql

    import labcairn.material.walk as walk_module

    root = tmp_path / "ws3"
    sources = root / "sources"
    sources.mkdir(parents=True)
    for name in ("a.md", "boom.md", "z.md"):
        (sources / name).write_text(name[0] + chr(10), encoding="utf-8", newline="")

    from labcairn.material.ingest import ingest_into_store

    # walk.py does ``from ...ingest import ingest_into_store``, so the name it
    # calls is bound in *its* namespace. Patch there, not on the source
    # module, or the patch never lands.
    real = ingest_into_store

    def flaky(session: Any, data: bytes, **kwargs: Any) -> Any:
        if "boom" in kwargs.get("relative_path", ""):
            raise RuntimeError("simulated adapter explosion")
        return real(session, data, **kwargs)

    monkeypatch.setattr(walk_module, "ingest_into_store", flaky)

    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    report = ingest_workspace(session, SourceMaterial(ws, _allowing_policy()), ingested_at=NOW)

    assert [key for key, _ in report.failures] == ["boom.md"]
    ingested = sorted(o.material.source.relative_path for o in report.outcomes)
    assert ingested == ["sources/a.md", "sources/z.md"]

    # The store is the claim. A report that disagrees with it is a lie the
    # caller cannot see.
    stored = sorted(
        r[0] for r in session.execute(text_sql("SELECT relative_path FROM sources")).fetchall()
    )
    assert stored == ["sources/a.md", "sources/z.md"], (
        "the report and the store disagree; one of them is wrong"
    )


def test_a_symlink_into_a_denied_directory_is_not_ingested(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """ADR-0011 contract 3: the walk does not ingest it, and no denied text
    reaches ``source_texts``.

    This test used to assert the *opposite*, deliberately, to pin a known gap:
    it said so in code as well as in the module docstring, so that closing the
    gap would break a test rather than pass quietly. The gap is closed, so the
    assertion is inverted.

    The walk is defended twice and needs only one to hold. The listing drops
    ``public/hop`` because the policy is evaluated on the canonical entry, and
    the read re-evaluates before opening because a listing entry is a name and
    a name can be a symlink. That the walk reports *no failure* here is the
    point: the entry is filtered, so it is never visited and never read.
    """
    root = tmp_path / "ws7"
    sources = root / "sources"
    (sources / "public").mkdir(parents=True)
    (sources / "private").mkdir(parents=True)
    (sources / "private" / "secret.md").write_text("# SECRET" + chr(10), encoding="utf-8")
    (sources / "public" / "ok.md").write_text("# fine" + chr(10), encoding="utf-8")

    link = sources / "public" / "hop"
    try:
        link.symlink_to(sources / "private", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this platform or filesystem")

    ws = Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))
    from labcairn.security.capabilities import CapabilityId
    from labcairn.security.policy import Permission, Rule

    policy = PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            ),
            Rule(
                effect=Permission.DENY,
                pattern="private/**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            ),
        ]
    )
    report = ingest_workspace(session, SourceMaterial(ws, policy), ingested_at=NOW)
    ingested = {o.material.source.relative_path for o in report.outcomes}

    assert "sources/public/hop/secret.md" not in ingested, (
        "the walk ingested a denied file through a symlink"
    )
    everything = "".join(unit.text for o in report.outcomes for unit in o.material.texts)
    assert "SECRET" not in everything, "denied material reached the store"
    assert "sources/public/ok.md" in ingested, "the permitted file stopped being ingested too"

    # The store is the claim, not the report.
    from sqlalchemy import text as text_sql

    stored = [
        r[0] for r in session.execute(text_sql("SELECT relative_path FROM sources")).fetchall()
    ]
    assert "sources/public/hop/secret.md" not in stored
    rows = [r[0] for r in session.execute(text_sql("SELECT text FROM source_texts")).fetchall()]
    assert not any("SECRET" in row for row in rows), "denied text was persisted"


def test_every_ingested_file_passed_through_the_policy_check(
    workspace: Workspace, material: SourceMaterial, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0011's second check, and the one the listing cannot stand in for.

    Every byte the walk stores went through ``read_permitted``, which
    evaluates the policy on the canonical entry *before* opening the file.

    Pinned because nothing else notices its absence. While the listing is
    correct the denied symlink is never visited, so reverting the walk to the
    unchecked ``read`` leaves every other test in the suite green and the
    second layer disappears with nothing failing -- while this module's
    docstring keeps claiming it is there. That is the same shape of defect
    ADR-0011 was written about: a boundary asserted in prose and not
    enforced in code.
    """
    checked: list[str] = []
    real = SourceMaterial.read_permitted

    def recording(self: SourceMaterial, key: str, **kwargs: Any) -> bytes:
        checked.append(key)
        return real(self, key, **kwargs)

    monkeypatch.setattr(SourceMaterial, "read_permitted", recording)
    report = ingest_workspace(session, material, ingested_at=NOW)

    assert report.outcomes, "the walk ingested nothing, so nothing was checked"
    assert report.failures == (), [m for _, m in report.failures]
    recorded = {o.material.source.relative_path for o in report.outcomes}
    assert all(path.startswith("sources/") for path in recorded), (
        f"the recorded path is not workspace-relative: {sorted(recorded)}"
    )
    assert sorted(checked) == sorted(path.removeprefix("sources/") for path in recorded), (
        "a file was ingested without passing the policy check first"
    )


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

    The superseded text is **kept**, not deleted: ADR-0009's item 2 says
    anchors bound to the old hash still resolve to the old text, and an
    anchor already pointing into the old bytes must still resolve to them.
    (ADR-0004's A2 is the neighbouring clause -- drift makes C1 return
    ``fail`` -- and it is about staleness, not about text surviving.)
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
        "resolves, per ADR-0009's item 2"
    )


def test_two_source_roots_holding_the_same_name_both_ingest(
    tmp_path: pathlib.Path, session: Any
) -> None:
    """Two roots, two ``notes.md``, and both of them in the ledger.

    ``sources.relative_path`` is workspace-relative and globally UNIQUE, so
    the two files can only live side by side if their paths differ -- and
    they do, because each root's own place in the workspace is part of the
    path. While the walk recorded the root-relative key instead, the two
    roots produced the same string, the second one lost at the store on the
    UNIQUE constraint, and the material under it was never recorded at all.

    The walk visits both roots and the store holds both rows, so the second
    root's material is inventoried rather than lost.
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

    assert report.failures == (), [message for _, message in report.failures]
    assert sorted(o.material.source.relative_path for o in report.outcomes) == [
        "sources/a/notes.md",
        "sources/b/notes.md",
    ]

    # The store is the claim, not the report.
    from sqlalchemy import text as text_sql

    stored = sorted(
        r[0] for r in session.execute(text_sql("SELECT relative_path FROM sources")).fetchall()
    )
    assert stored == ["sources/a/notes.md", "sources/b/notes.md"], (
        "the report and the store disagree; one of them is wrong"
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
