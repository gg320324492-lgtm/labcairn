"""The material tables' constraints must be able to fail.

A CHECK constraint nobody tests is decoration. This file exists so that
each one is demonstrated to reject a violating row, rather than assumed
to.

The interesting cases are the ones SQLite makes easy to get wrong:

  * NULLs compare as distinct inside a UNIQUE index, so a unique
    constraint spanning nullable columns would look present and enforce
    nothing. ``source_texts`` therefore keys on ``locator_key``; these
    tests prove the key actually constrains.
  * A CHECK that only tests the presence of one column does not stop a
    half-populated locator. Each kind's shape is asserted.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine, create_session_factory

SHA = "a" * 64
OTHER_SHA = "b" * 64
NOW = datetime(2026, 10, 17, tzinfo=UTC).isoformat()


@pytest.fixture
def db(tmp_path: Path) -> Path:
    target = tmp_path / "materials.db"
    upgrade_to_head(target)
    return target


def _factory(db: Path) -> tuple[Any, Any]:
    engine = create_db_engine(db)
    return engine, create_session_factory(engine)


def _insert_source(db: Path, **overrides: object) -> None:
    engine, factory = _factory(db)
    row = {
        "source_id": "src-1",
        "owner_id": "local-user",
        "kind": "pdf",
        "display_name": "paper.pdf",
        "relative_path": "papers/paper.pdf",
        "content_sha256": SHA,
        "size_bytes": 10,
        "readability": "readable",
        "readability_disclosure": None,
        "identifiers": "[]",
        "ingested_at": NOW,
        "schema_version": 1,
    }
    row.update(overrides)
    with factory() as session:
        session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name, "
                "relative_path, content_sha256, size_bytes, readability, "
                "readability_disclosure, identifiers, ingested_at, schema_version) "
                "VALUES (:source_id, :owner_id, :kind, :display_name, :relative_path, "
                ":content_sha256, :size_bytes, :readability, :readability_disclosure, "
                ":identifiers, :ingested_at, :schema_version)"
            ),
            row,
        )
        session.commit()
    engine.dispose()


def _insert_text(db: Path, **overrides: object) -> None:
    engine, factory = _factory(db)
    row = {
        "source_content_sha256": SHA,
        "extraction_version": "v1",
        "locator_kind": "pdf",
        "locator_key": "pdf:page=1",
        "page": 1,
        "line_start": None,
        "line_end": None,
        "section": None,
        "row_number": None,
        "column_name": None,
        "sheet_name": None,
        "cell_ref": None,
        "text": "Hello",
        "text_sha256": OTHER_SHA,
        "created_at": NOW,
    }
    row.update(overrides)
    with factory() as session:
        session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO source_texts (source_content_sha256, extraction_version, "
                "locator_kind, locator_key, page, line_start, line_end, section, "
                "row_number, column_name, sheet_name, cell_ref, text, text_sha256, "
                "created_at) VALUES (:source_content_sha256, :extraction_version, "
                ":locator_kind, :locator_key, :page, :line_start, :line_end, :section, "
                ":row_number, :column_name, :sheet_name, :cell_ref, :text, :text_sha256, "
                ":created_at)"
            ),
            row,
        )
        session.commit()
    engine.dispose()


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


def test_a_readable_source_is_stored(db: Path) -> None:
    _insert_source(db)
    with sqlite3.connect(str(db)) as connection:
        assert connection.execute("SELECT display_name FROM sources").fetchone()[0] == "paper.pdf"


def test_a_negative_size_is_refused(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_source(db, size_bytes=-1)


def test_an_unreadable_source_must_disclose_why(db: Path) -> None:
    """ADR-0004 A7: 'we could not look' is not 'there was nothing there'."""
    with pytest.raises(IntegrityError):
        _insert_source(db, readability="unreadable_no_ocr", readability_disclosure=None)


def test_a_disclosure_on_a_readable_source_is_refused(db: Path) -> None:
    """A disclosure about something that did not happen is a false claim."""
    with pytest.raises(IntegrityError):
        _insert_source(db, readability="readable", readability_disclosure="no OCR available")


def test_an_unreadable_source_with_a_disclosure_is_accepted(db: Path) -> None:
    _insert_source(
        db, readability="unreadable_no_ocr", readability_disclosure="scanned image, no text layer"
    )
    with sqlite3.connect(str(db)) as connection:
        row = connection.execute(
            "SELECT readability, readability_disclosure FROM sources"
        ).fetchone()
    assert row == ("unreadable_no_ocr", "scanned image, no text layer")


def test_two_sources_cannot_share_a_workspace_path(db: Path) -> None:
    _insert_source(db)
    with pytest.raises(IntegrityError):
        _insert_source(db, source_id="src-2", relative_path="papers/paper.pdf")


# --------------------------------------------------------------------------
# source_texts -- the key
# --------------------------------------------------------------------------


def test_the_address_key_actually_constrains(db: Path) -> None:
    """The reason locator_key exists.

    Without it this duplicate would be accepted, because SQLite compares
    NULLs as distinct in a UNIQUE index and every non-key locator column
    here is NULL.
    """
    _insert_text(db)
    with pytest.raises(IntegrityError):
        _insert_text(db)


def test_a_different_content_hash_is_a_different_address(db: Path) -> None:
    """A modified file cannot inherit the text extracted from the old bytes."""
    _insert_text(db)
    _insert_text(db, source_content_sha256="c" * 64)
    with sqlite3.connect(str(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_texts").fetchone()[0] == 2


def test_a_different_extraction_version_is_a_different_address(db: Path) -> None:
    """A new extraction sits beside the old one rather than replacing it."""
    _insert_text(db)
    _insert_text(db, extraction_version="v2")
    with sqlite3.connect(str(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_texts").fetchone()[0] == 2


def test_text_survives_the_source_row_going_away(db: Path) -> None:
    """An anchor written against the old bytes must still resolve.

    ``source_texts.source_content_sha256`` is deliberately not a foreign
    key, so deleting the inventory row cannot orphan text an existing
    anchor still points at.
    """
    _insert_text(db)
    with sqlite3.connect(str(db)) as connection:
        connection.execute("DELETE FROM sources")
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM source_texts").fetchone()[0] == 1


# --------------------------------------------------------------------------
# source_texts -- locator shape
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,overrides",
    [
        ("a pdf row with no page", {"page": None}),
        ("a pdf row carrying a line number", {"line_start": 3}),
        ("a pdf row carrying a sheet name", {"sheet_name": "Sheet1"}),
        ("a pdf row carrying a cell ref", {"cell_ref": "B2"}),
        ("a page number below one", {"page": 0}),
    ],
)
def test_a_pdf_row_may_carry_only_a_page(
    db: Path, label: str, overrides: dict[str, object]
) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(db, **overrides)
    _ = label


def test_a_text_row_must_have_a_line(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(db, locator_kind="text", locator_key="text:line=1", page=None, line_start=None)


def test_a_text_row_with_a_line_is_accepted(db: Path) -> None:
    _insert_text(db, locator_kind="text", locator_key="text:line=1", page=None, line_start=1)


def test_a_line_range_must_not_run_backwards(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="text",
            locator_key="text:lines=9-4",
            page=None,
            line_start=9,
            line_end=4,
        )


def test_a_csv_row_needs_both_a_row_and_a_column(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="csv",
            locator_key="csv:row=1",
            page=None,
            row_number=1,
            column_name=None,
        )


def test_a_csv_row_with_row_and_column_is_accepted(db: Path) -> None:
    _insert_text(
        db,
        locator_kind="csv",
        locator_key="csv:row=1,column=mean",
        page=None,
        row_number=1,
        column_name="mean",
    )


def test_a_xlsx_row_needs_both_a_sheet_and_a_cell(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db, locator_kind="xlsx", locator_key="xlsx:Sheet1", page=None, sheet_name="Sheet1"
        )


def test_an_xlsx_row_with_sheet_and_cell_is_accepted(db: Path) -> None:
    _insert_text(
        db,
        locator_kind="xlsx",
        locator_key="xlsx:Sheet1!B2",
        page=None,
        sheet_name="Sheet1",
        cell_ref="B2",
    )
