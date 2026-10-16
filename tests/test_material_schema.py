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


# --------------------------------------------------------------------------
# Everything review found the schema wrongly accepting
# --------------------------------------------------------------------------


def test_a_row_cannot_claim_every_locator_kind_at_once(db: Path) -> None:
    """A row claiming to be a text locator *and* a page *and* a CSV cell.

    The shape constraints originally pinned only the columns each kind
    *uses*, so this passed: it satisfies no constraint at all, because
    every constraint is an implication keyed on locator_kind and this row
    is 'text'. No conforming code can produce such a row -- TextLocator is
    extra="forbid" and has none of those fields -- and none can consume
    it. Each shape check now names every column.
    """
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="text",
            locator_key="text:line=1",
            page=7,
            line_start=1,
            line_end=2,
            section="Intro",
            row_number=3,
            column_name="yield_pct",
            sheet_name="Sheet1",
            cell_ref="B2",
        )


def test_a_csv_row_may_not_carry_a_cell_ref(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="csv",
            locator_key="csv:row=1,column=mean",
            page=None,
            row_number=1,
            column_name="mean",
            cell_ref="B2",
        )


def test_a_csv_row_may_not_carry_a_section(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="csv",
            locator_key="csv:row=1,column=mean",
            page=None,
            row_number=1,
            column_name="mean",
            section="Methods",
        )


def test_an_xlsx_row_may_not_carry_a_column_name(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="xlsx",
            locator_key="xlsx:Sheet1!B2",
            page=None,
            sheet_name="Sheet1",
            cell_ref="B2",
            column_name="mean",
        )


def test_only_a_text_row_may_carry_a_line_end(db: Path) -> None:
    """TextLocator.line_end is optional and legitimate; no other kind has one."""
    _insert_text(
        db, locator_kind="text", locator_key="text:1-2", page=None, line_start=1, line_end=2
    )
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="csv",
            locator_key="csv:row=1,column=mean",
            page=None,
            row_number=1,
            column_name="mean",
            line_end=10,
        )


@pytest.mark.parametrize("kind", ["banana", "PDF", "", "docx", "computation"])
def test_locator_kind_is_a_closed_vocabulary(db: Path, kind: str) -> None:
    """Every shape check is an implication keyed on locator_kind.

    An unrecognised kind therefore satisfies all of them vacuously with
    every typed column NULL. The same standard ``events.type`` is held to.
    """
    with pytest.raises(IntegrityError):
        _insert_text(db, locator_kind=kind, locator_key=f"k:{kind}", page=None)


@pytest.mark.parametrize("kind", ["banana", "DOCX", ""])
def test_source_kind_is_a_closed_vocabulary(db: Path, kind: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_source(db, kind=kind)


@pytest.mark.parametrize("readability", ["unreadable", "UNREADABLE_NO_OCR", "banana", ""])
def test_source_readability_is_a_closed_vocabulary(db: Path, readability: str) -> None:
    """The pairing check is keyed on one literal.

    Without the vocabulary, ``'unreadable'`` with no disclosure sails
    through and ADR-0004 A7 is not enforced by the database at all.
    """
    with pytest.raises(IntegrityError):
        _insert_source(db, readability=readability, readability_disclosure=None)


def test_an_unreadable_source_may_not_carry_an_empty_disclosure(db: Path) -> None:
    """Paired is not the same as meaningful."""
    with pytest.raises(IntegrityError):
        _insert_source(db, readability="unreadable_no_ocr", readability_disclosure="   ")


@pytest.mark.parametrize(
    "path",
    [
        "../../etc/passwd",
        "papers/../../etc/passwd",
        "papers/..",
        "..",
        "/absolute/path",
        "papers/./paper.pdf",
        "papers/sub/.",
        ".",
        r"C:\Users\x\paper.pdf",
        r"papers\paper.pdf",
        "",
    ],
)
def test_relative_path_must_stay_inside_the_workspace(db: Path, path: str) -> None:
    """Defence in depth behind require_workspace_relative, not a copy of it.

    The application validator is the contract. This refuses the shapes that
    make a stored path dangerous if a row is written by something that
    skipped it -- and a stored ``..`` is exactly what that validator exists
    to reject.
    """
    with pytest.raises(IntegrityError):
        _insert_source(db, relative_path=path)


def test_a_legitimate_nested_path_is_accepted(db: Path) -> None:
    _insert_source(db, relative_path="papers/2026/widget-trial.pdf")


@pytest.mark.parametrize("value", ["not-a-hash", "A" * 64, "a" * 63, ""])
def test_content_sha256_must_look_like_one(db: Path, value: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_source(db, content_sha256=value)


def test_an_empty_display_name_is_refused(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_source(db, display_name="   ")


def test_an_empty_locator_key_is_refused(db: Path) -> None:
    """Four spellings of one page can otherwise coexist and fork the key."""
    with pytest.raises(IntegrityError):
        _insert_text(db, locator_key="   ")


def test_an_empty_extraction_version_is_refused(db: Path) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(db, extraction_version="")


@pytest.mark.parametrize("value", ["not-a-hash", "z" * 64, "b" * 10])
def test_text_sha256_must_look_like_one(db: Path, value: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_text(db, text_sha256=value)


def test_a_text_row_too_long_for_its_only_consumer_is_refused(db: Path) -> None:
    """UntrustedText refuses above two million characters.

    A longer row could be written and then never read back through the
    only sanctioned path, which is a row that exists for no purpose.
    """
    _insert_text(db, text="x" * 1_000, text_sha256="b" * 64)
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_key="pdf:page=2",
            page=2,
            text="x" * 2_000_001,
            text_sha256="b" * 64,
        )


def test_row_number_below_one_is_refused(db: Path) -> None:
    """The positive-row constraint had no test at all."""
    with pytest.raises(IntegrityError):
        _insert_text(
            db,
            locator_kind="csv",
            locator_key="csv:row=0,column=mean",
            page=None,
            row_number=0,
            column_name="mean",
        )
