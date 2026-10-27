"""The evidence ledger's schema, exercised by writing the rows it forbids.

These tests insert rows **directly with SQL** and assert the database refuses
them. That is the point of them, and it is a different question from the one
``test_the_migrated_schema_matches_the_orm_models`` asks: that test proves the
constraint *text* in the migration equals the text in the ORM metadata, which
would both be satisfied by a constraint SQLite never enforces -- a misspelled
column name inside a CHECK body evaluates to NULL, and NULL satisfies a WHERE
clause. Every test here therefore writes a row that must not be storable and
asserts it is not storable.

The mirror risk is the other one. A test that constructs its expectations by
reading ``Base.metadata`` cannot fail when the metadata drifts, which is why
the illegal rows below are spelled out as literals rather than assembled from
the models.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError

from conftest import migrated_database_from
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine

pytestmark = pytest.mark.integration

NOW = "2026-10-18T00:00:00+00:00"
SHA = "a" * 64
OTHER_SHA = "b" * 64

#: A record that every CHECK accepts. Tests vary one field from this.
LEGAL_CLAIM: dict[str, Any] = {
    "evidence_id": "ev-legal",
    "schema_version": 1,
    "task_id": "task-1",
    "kind": "claim",
    "text": "Dijkstra's algorithm is not greedy.",
    "value": None,
    "unit": None,
    "tolerance": None,
    "anchor_key": '["anchor-1"]',
    "extracted_span": "Dijkstra's algorithm is not greedy.",
    "extracted_span_sha256": SHA,
    "source_content_hash": SHA,
    "status": "extracted",
    "created_by": "rule",
    "created_by_id": "rule-1",
    "created_at": NOW,
    "superseded_by": None,
}

#: The same shape for a numeric record. It deliberately carries **no**
#: ``extracted_span_sha256``: ``_insert_record`` derives one per id, and
#: inheriting the claim's would make these collide on the UNIQUE natural key for
#: a reason that has nothing to do with kind discipline.
LEGAL_NUMERIC: dict[str, Any] = {
    key: value
    for key, value in LEGAL_CLAIM.items()
    if key not in ("extracted_span_sha256", "evidence_id")
} | {
    "kind": "numeric",
    "text": None,
    "value": 3.5,
    "unit": "dimensionless",
    "tolerance": 0.01,
}

LEGAL_VERIFICATION: dict[str, Any] = {
    "evidence_id": "ev-legal",
    "seq": 1,
    "schema_version": 1,
    "check_kind": "c1",
    "checker_id": "c1-implementation",
    "outcome": "pass",
    "detail": "both anchors resolved and the source hash matches",
    "checked_at": NOW,
    "normalization_profile": None,
}


@pytest.fixture
def engine(migrated_database_template: Path, tmp_path: Path) -> Any:
    target = tmp_path / "evidence.db"
    migrated_database_from(migrated_database_template, target)
    made = create_db_engine(target)
    yield made
    made.dispose()


def _insert_record(engine: Any, evidence_id: str = "ev-legal", **overrides: Any) -> None:
    """Write one ``evidence_records`` row, defaulting the natural key per id.

    ``evidence_records`` is UNIQUE on ``(task_id, extracted_span_sha256)``, so
    two unrelated tests that both inherited ``LEGAL_CLAIM``'s hash collided for
    a reason that had nothing to do with what either was testing. The hash is
    derived from the row's own id unless the caller sets one, so each test stays
    independent; the one test that *is* about that constraint passes it.
    """
    row = {**LEGAL_CLAIM, **overrides}
    # "Explicit" means passed by the caller. ``LEGAL_CLAIM`` carries a hash of
    # its own, and merging it in first would make every derived default a
    # no-op -- which is how five tests came to collide on the natural key for a
    # reason that had nothing to do with what any of them was testing.
    explicit = "extracted_span_sha256" in overrides
    # The named parameter always wins. LEGAL_NUMERIC used to carry its own
    # evidence_id, and every numeric test then derived its hash from *that*
    # rather than the one it passed -- four tests colliding on the natural key
    # for a reason that had nothing to do with kind discipline.
    row["evidence_id"] = evidence_id
    if not explicit:
        row["extracted_span_sha256"] = hashlib.sha256(str(row["evidence_id"]).encode()).hexdigest()
    columns = ", ".join(row)
    marks = ", ".join(f":{name}" for name in row)
    with engine.begin() as connection:
        connection.execute(
            sql_text(f"INSERT INTO evidence_records ({columns}) VALUES ({marks})"), row
        )


def _insert_verification(engine: Any, **overrides: Any) -> None:
    row = {**LEGAL_VERIFICATION, **overrides}
    columns = ", ".join(row)
    marks = ", ".join(f":{name}" for name in row)
    with engine.begin() as connection:
        connection.execute(
            sql_text(f"INSERT INTO verification_records ({columns}) VALUES ({marks})"), row
        )


def _insert_anchor(engine: Any, **overrides: Any) -> None:
    row = {"evidence_id": "ev-legal", "position": 0, "anchor_id": "anchor-1", **overrides}
    columns = ", ".join(row)
    marks = ", ".join(f":{name}" for name in row)
    with engine.begin() as connection:
        connection.execute(
            sql_text(f"INSERT INTO evidence_anchors ({columns}) VALUES ({marks})"), row
        )


# --------------------------------------------------------------------------- #
# rows that must be storable
# --------------------------------------------------------------------------- #


def test_a_claim_record_and_a_numeric_record_are_both_storable(engine: Any) -> None:
    """The constraints above are not a filter that eats everything."""
    _insert_record(engine, evidence_id="ev-claim")
    _insert_record(engine, evidence_id="ev-num", **LEGAL_NUMERIC)
    with engine.connect() as connection:
        assert connection.execute(sql_text("SELECT COUNT(*) FROM evidence_records")).scalar() == 2


def test_a_c2_entry_with_a_profile_and_a_c4_entry_are_storable(engine: Any) -> None:
    _insert_record(engine)
    _insert_verification(engine)
    _insert_verification(
        engine,
        seq=2,
        check_kind="c2",
        outcome="indeterminate",
        normalization_profile="nfkc_whitespace_collapsed",
    )
    _insert_verification(engine, seq=3, check_kind="c4", outcome="not_checked")
    with engine.connect() as connection:
        assert (
            connection.execute(sql_text("SELECT COUNT(*) FROM verification_records")).scalar() == 3
        )


# --------------------------------------------------------------------------- #
# kind discipline
# --------------------------------------------------------------------------- #


def test_a_numeric_record_may_not_carry_text(engine: Any) -> None:
    """A sentence riding on a verified number is a second claim nothing checks."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, **{**LEGAL_NUMERIC, "text": "and it is fast"}, evidence_id="ev-a")


def test_a_numeric_record_must_carry_a_value(engine: Any) -> None:
    with pytest.raises(IntegrityError):
        _insert_record(engine, **{**LEGAL_NUMERIC, "value": None}, evidence_id="ev-b")


def test_a_numeric_record_must_declare_a_unit(engine: Any) -> None:
    """ADR-0004 Contract 1: declared, never inferred."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, **{**LEGAL_NUMERIC, "unit": None}, evidence_id="ev-c")


@pytest.mark.parametrize("field", ["value", "unit", "tolerance"])
def test_a_claim_record_may_not_carry_a_number_field(engine: Any, field: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_record(engine, evidence_id=f"ev-{field}", **{field: 1.0})


@pytest.mark.parametrize("kind", ["banana", "CLAIM", ""])
def test_an_unrecognised_kind_is_not_storable(engine: Any, kind: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_record(engine, kind=kind)


@pytest.mark.parametrize("status", ["verified", "done", ""])
def test_an_unrecognised_status_is_not_storable(engine: Any, status: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_record(engine, status=status)


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #


def test_quoted_text_without_its_hash_is_refused(engine: Any) -> None:
    """Hashless text cannot be checked for drift."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, extracted_span_sha256=None)


def test_a_planned_record_may_not_carry_a_hash_with_no_text(engine: Any) -> None:
    """``span_all_or_nothing`` on its own, with nothing else enforcing it.

    The test above is also refused by ``located_past_planned`` -- any record
    past ``planned`` needs the hash -- so it passes whether or not this
    constraint exists. Mutation-checking the constraints separately showed that
    removing ``span_all_or_nothing`` left the suite green apart from the
    migration-versus-metadata text comparison, which is a test of spelling.

    A ``planned`` record is the only shape where the pair rule is the *sole*
    guard: ``located_past_planned`` says nothing about it, so without this test
    a hash pointing at text nobody stored would be storable.
    """
    with pytest.raises(IntegrityError):
        _insert_record(
            engine,
            evidence_id="ev-planned-hash",
            status="planned",
            anchor_key="[]",
            extracted_span=None,
            extracted_span_sha256=SHA,
            source_content_hash=None,
        )


@pytest.mark.parametrize("field", ["evidence_id", "task_id", "created_by_id"])
def test_an_empty_identifier_is_refused(engine: Any, field: str) -> None:
    """A row that names nobody, no task or no verifier attests to nothing."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, **{field: ""})


@pytest.mark.parametrize("check", ["c5", "C1", ""])
def test_an_unrecognised_check_is_not_storable(engine: Any, check: str) -> None:
    """``check_kind`` is closed for the same reason ``kind`` is: an
    unrecognised check satisfies the C4 lock vacuously."""
    with pytest.raises(IntegrityError):
        _insert_verification(engine, check_kind=check)


@pytest.mark.parametrize("outcome", ["passed", "ok", ""])
def test_an_unrecognised_outcome_is_not_storable(engine: Any, outcome: str) -> None:
    """``indeterminate`` must never be spellable as something ``!= fail``."""
    with pytest.raises(IntegrityError):
        _insert_verification(engine, outcome=outcome)


def test_a_hash_without_the_text_it_hashes_is_refused(engine: Any) -> None:
    """A hash nobody can be shown is a hash of nothing."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, extracted_span=None)


@pytest.mark.parametrize("bad", ["abc", "z" * 64, "A" * 64])
def test_a_hash_of_the_wrong_shape_is_refused(engine: Any, bad: str) -> None:
    with pytest.raises(IntegrityError):
        _insert_record(engine, evidence_id=f"ev-{len(bad)}-{bad[0]}", extracted_span_sha256=bad)


def test_a_record_past_planned_must_carry_what_a_location_is_made_against(
    engine: Any,
) -> None:
    """The checkable half of ADR-0004 Contract 2, enforced by the database."""
    with pytest.raises(IntegrityError):
        _insert_record(
            engine,
            status="verified_by_rule",
            extracted_span=None,
            extracted_span_sha256=None,
            source_content_hash=None,
        )
    with pytest.raises(IntegrityError):
        _insert_record(engine, status="verified_by_rule", source_content_hash=None)
    with pytest.raises(IntegrityError):
        _insert_record(engine, status="verified_by_rule", anchor_key="[]")


def test_a_record_past_planned_is_storable_when_it_does_carry_them(engine: Any) -> None:
    _insert_record(engine, status="verified_by_rule")
    with engine.connect() as connection:
        assert connection.execute(sql_text("SELECT status FROM evidence_records")).scalar() == (
            "verified_by_rule"
        )


def test_a_planned_record_needs_nothing(engine: Any) -> None:
    """``planned`` is the one state that legitimately has no provenance yet."""
    _insert_record(
        engine,
        evidence_id="ev-planned",
        status="planned",
        anchor_key="[]",
        extracted_span=None,
        extracted_span_sha256=None,
        source_content_hash=None,
    )


def test_a_negative_tolerance_is_refused(engine: Any) -> None:
    """A comparison no number could satisfy is not a tolerance."""
    with pytest.raises(IntegrityError):
        _insert_record(engine, **{**LEGAL_NUMERIC, "tolerance": -1.0}, evidence_id="ev-tol")


def test_two_records_may_not_claim_the_same_span_in_one_task(engine: Any) -> None:
    """Two claims quoting the same passage of the same task are one claim.

    The key is ``(task_id, extracted_span_sha256)``, so the collision needs both
    halves -- the same task *and* the same span. Two records with the same span
    under different tasks, or the same task citing different passages, are both
    legitimate and are asserted below.
    """
    _insert_record(engine, evidence_id="ev-one", extracted_span_sha256=SHA)
    with pytest.raises(IntegrityError):
        _insert_record(engine, evidence_id="ev-two", extracted_span_sha256=SHA)


def test_the_same_span_in_a_different_task_is_not_a_collision(engine: Any) -> None:
    """The other half of "and", so the test above is not passing by accident."""
    _insert_record(engine, evidence_id="ev-one", extracted_span_sha256=SHA)
    _insert_record(engine, evidence_id="ev-three", task_id="task-2", extracted_span_sha256=SHA)


# --------------------------------------------------------------------------- #
# the verification log
# --------------------------------------------------------------------------- #


def test_a_c4_entry_may_not_record_a_pass(engine: Any) -> None:
    """ADR-0004 I2, enforced where a verdict becomes durable.

    The Pydantic model refuses this too, so the row cannot be built through the
    typed path either. What this proves is narrower and worth proving: a raw
    INSERT cannot slip it past, which is the whole reason the constraint is
    duplicated in the schema.
    """
    with pytest.raises(IntegrityError):
        _insert_verification(engine, check_kind="c4", outcome="pass")


def test_a_c2_entry_must_declare_its_normalization_profile(engine: Any) -> None:
    """An absent profile answers "how lenient was this" as *unknown*."""
    with pytest.raises(IntegrityError):
        _insert_verification(engine, check_kind="c2", outcome="pass", normalization_profile=None)


def test_a_check_that_compares_no_text_may_not_carry_a_profile(engine: Any) -> None:
    with pytest.raises(IntegrityError):
        _insert_verification(engine, check_kind="c1", normalization_profile="exact")


def test_an_unrecognised_profile_is_refused(engine: Any) -> None:
    with pytest.raises(IntegrityError):
        _insert_verification(engine, check_kind="c2", normalization_profile="whatever_seemed_right")


@pytest.mark.parametrize("seq", [0, -1])
def test_a_log_sequence_starts_at_one(engine: Any, seq: int) -> None:
    """A gap in an audit trail is a defect, so the order is dense from 1."""
    with pytest.raises(IntegrityError):
        _insert_verification(engine, seq=seq)


def test_two_entries_cannot_share_a_position_in_one_log(engine: Any) -> None:
    _insert_verification(engine)
    with pytest.raises(IntegrityError):
        _insert_verification(engine, checker_id="another", detail="a second C1 verdict")


# --------------------------------------------------------------------------- #
# anchors
# --------------------------------------------------------------------------- #


def test_one_anchor_may_not_appear_twice_for_a_record(engine: Any) -> None:
    """ADR-0004 rejects duplicate anchors on the record."""
    _insert_record(engine)
    _insert_anchor(engine, position=0, anchor_id="anchor-1")
    _insert_anchor(engine, position=1, anchor_id="anchor-2")
    with pytest.raises(IntegrityError):
        _insert_anchor(engine, position=2, anchor_id="anchor-1")


def test_two_anchors_may_not_share_a_position(engine: Any) -> None:
    _insert_anchor(engine)
    with pytest.raises(IntegrityError):
        _insert_anchor(engine, anchor_id="anchor-2")


def test_a_negative_anchor_position_is_refused(engine: Any) -> None:
    with pytest.raises(IntegrityError):
        _insert_anchor(engine, position=-1)


def test_an_empty_anchor_id_is_refused(engine: Any) -> None:
    """An anchor naming nothing is a fabricated source; C1 catches it as a
    verdict, and an empty id must not be storable in the first place."""
    with pytest.raises(IntegrityError):
        _insert_anchor(engine, anchor_id="")


def test_an_anchor_may_name_a_source_the_ledger_has_never_seen(engine: Any) -> None:
    """No foreign key, deliberately.

    A fabricated source is A12, and it must fail as a **verdict** a report can
    read and show. A foreign key here would make the row unstorable instead,
    which turns a checkable failure into a constraint error at write time and
    makes "the model invented a DOI" indistinguishable from "the database was
    unhappy". So the row stores, and C1's job is to fail it.
    """
    _insert_anchor(engine, anchor_id="doi:10.0000/does-not-exist")


# --------------------------------------------------------------------------- #
# the anchor registry (revision 0007)
# --------------------------------------------------------------------------- #
#
# A *different* helper from the one above. That one writes ``evidence_anchors``
# -- who cites what; this one writes ``source_anchors`` -- what an anchor is.
# The names are close enough to be worth separating explicitly rather than
# overloading.


LEGAL_SOURCE_ANCHOR: dict[str, Any] = {
    "anchor_id": "sa-legal",
    "source_id": "src-1",
    "kind": "quotation",
    "locator_key": "k=3:pdf|p=1:4",
    "bound_source_sha256": SHA,
    "excerpt_sha256": None,
    "created_at": NOW,
}


def _insert_source_anchor(engine: Any, **overrides: Any) -> None:
    row = {**LEGAL_SOURCE_ANCHOR, **overrides}
    columns = ", ".join(row)
    marks = ", ".join(f":{name}" for name in row)
    with engine.begin() as connection:
        connection.execute(
            sql_text(f"INSERT INTO source_anchors ({columns}) VALUES ({marks})"), row
        )


def test_a_registry_row_is_storable_and_holds_its_address(engine: Any) -> None:
    """The constraints below are not a filter that eats everything.

    Every kind the ledger can resolve, because the length prefix is not
    constant -- ``pdf`` and ``csv`` render ``k=3:`` while ``text`` and ``xlsx``
    render ``k=4:``. A hand-written ``k=3:`` accepted two kinds and refused the
    other two, which is why the guard is generated from the spelling length.
    """
    for index, key in enumerate(
        (
            "k=3:pdf|p=1:4",
            "k=3:pdf|p=1:2|c=5:10-99",
            "k=4:text|l=1:7",
            "k=4:text|l=1:7|le=1:9|s=7:Methods",
            "k=3:csv|r=2:12|c=4:mean",
            "k=4:xlsx|sh=2:S1|c=2:B2",
        )
    ):
        _insert_source_anchor(engine, anchor_id=f"sa-{index}", locator_key=key)
    with engine.connect() as connection:
        stored = connection.execute(
            sql_text("SELECT locator_key FROM source_anchors ORDER BY locator_key")
        ).scalars()
        assert list(stored) == [
            "k=3:csv|r=2:12|c=4:mean",
            "k=3:pdf|p=1:2|c=5:10-99",
            "k=3:pdf|p=1:4",
            "k=4:text|l=1:7",
            "k=4:text|l=1:7|le=1:9|s=7:Methods",
            "k=4:xlsx|sh=2:S1|c=2:B2",
        ]


@pytest.mark.parametrize(
    ("why", "overrides"),
    [
        ("kind is not a member of AnchorKind", {"kind": "quote"}),
        ("kind is uppercased", {"kind": "QUOTATION"}),
        ("kind is empty", {"kind": ""}),
        ("locator kind is not one LabCairn can resolve", {"locator_key": "k=3:docx|p=1:4"}),
        (
            "locator kind exists but has no extracted text",
            {"locator_key": "k=2:computation|p=1:4"},
        ),
        ("locator kind is uppercased", {"locator_key": "k=3:PDF|p=1:4"}),
        ("locator key carries no kind at all", {"locator_key": "p=1:4"}),
        ("locator key is empty", {"locator_key": ""}),
        ("bound hash is too short", {"bound_source_sha256": "abc"}),
        ("bound hash is not hex", {"bound_source_sha256": "z" * 64}),
        ("bound hash is not lowercase", {"bound_source_sha256": "A" * 64}),
        ("excerpt hash is not a hash", {"excerpt_sha256": "nope"}),
        ("anchor id is empty", {"anchor_id": ""}),
        ("source id is empty", {"source_id": ""}),
    ],
)
def test_a_registry_row_that_names_nothing_real_is_refused(
    engine: Any, why: str, overrides: dict[str, Any]
) -> None:
    """A storable address that resolves to nothing, or a hash that is not one.

    ``k=3:docx`` is the load-bearing case: the key parses, and a reader that
    did not check the kind would build a locator out of it. ``computation`` is
    a *real* :class:`LocatorKind` and is still refused, because a derived number
    is addressed by the operator that produced it and has no row to resolve
    against.
    """
    with pytest.raises(IntegrityError):
        _insert_source_anchor(engine, **overrides)


def test_two_rows_cannot_claim_the_same_anchor_id(engine: Any) -> None:
    """Identity is the id, so a second writer for one anchor is a duplicate.

    Not a silent overwrite: an anchor whose address changed under the same id
    would make every citation already pointing at it quietly mean something
    else, which is the drift ADR-0004 A2 detects by *failing*, not by
    accepting a newer row.
    """
    _insert_source_anchor(engine)
    with pytest.raises(IntegrityError):
        _insert_source_anchor(engine, locator_key="k=3:pdf|p=1:9")


def test_a_registry_row_may_bind_a_hash_no_source_currently_holds(engine: Any) -> None:
    """``bound_source_sha256`` is deliberately not a foreign key.

    It is the source's hash *as it was when the anchor was made*, so it names a
    version of a file that may no longer be on disk. Forcing it to match a
    current ``sources`` row would delete the evidence of the drift A2 exists to
    report -- the anchor would have to be rewritten to survive, and rewriting
    it is what A2 forbids.
    """
    _insert_source_anchor(engine, bound_source_sha256=OTHER_SHA)
    with engine.connect() as connection:
        assert (
            connection.execute(
                sql_text("SELECT COUNT(*) FROM sources WHERE content_sha256 = :sha"),
                {"sha": OTHER_SHA},
            ).scalar()
            == 0
        )


# --------------------------------------------------------------------------- #
# the index
# --------------------------------------------------------------------------- #


def test_the_fts_table_exists_as_a_virtual_table_and_is_usable(engine: Any) -> None:
    """An index that failed to be created would read as "nothing found".

    The migration is written to fail loudly if FTS5 is unavailable rather than
    to fall back to a plain table, because a database that upgraded cleanly but
    cannot retrieve returns an empty result on every query -- exactly what a
    genuine absence looks like.
    """
    with engine.connect() as connection:
        # ``PRAGMA table_list`` yields six columns per row; the kind is the
        # third. ``dict(rows)`` would raise on that, so name the pair.
        kinds = {row[1]: row[2] for row in connection.execute(sql_text("PRAGMA table_list"))}
    assert kinds.get("evidence_fts") == "virtual", sorted(kinds)

    with engine.begin() as connection:
        connection.execute(
            sql_text(
                "INSERT INTO evidence_fts "
                "(normalized_text, source_content_sha256, extraction_version, "
                "locator_key, source_text_id) VALUES (:t, :s, 'v1', 'p:1', '7')"
            ),
            {"t": "dijkstra is not greedy", "s": SHA},
        )
    with engine.connect() as connection:
        hits = connection.execute(
            sql_text("SELECT source_text_id FROM evidence_fts WHERE evidence_fts MATCH 'greedy'")
        ).fetchall()
    assert [row[0] for row in hits] == ["7"], "the index did not return the row it was given"


def test_the_index_carries_the_locator_a_hit_must_be_able_to_name(engine: Any) -> None:
    """A hit that cannot name its address is not a citation."""
    with engine.begin() as connection:
        connection.execute(
            sql_text(
                "INSERT INTO evidence_fts "
                "(normalized_text, source_content_sha256, extraction_version, "
                "locator_key, source_text_id) VALUES ('some body text', :s, 'v1', 'p:9', '3')"
            ),
            {"s": OTHER_SHA},
        )
    with engine.connect() as connection:
        row = connection.execute(
            sql_text(
                "SELECT locator_key, source_content_sha256 FROM evidence_fts "
                "WHERE evidence_fts MATCH 'body'"
            )
        ).one()
    assert row[0] == "p:9"
    assert row[1] == OTHER_SHA


def test_the_identity_columns_are_not_searchable(engine: Any) -> None:
    """A hash must not be findable by a text query, or a query for one hash
    could match the wrong excerpt."""
    with engine.begin() as connection:
        connection.execute(
            sql_text(
                "INSERT INTO evidence_fts "
                "(normalized_text, source_content_sha256, extraction_version, "
                "locator_key, source_text_id) VALUES ('body', :s, 'v1', 'p:1', '1')"
            ),
            {"s": SHA},
        )
    with engine.connect() as connection:
        hits = connection.execute(
            sql_text("SELECT COUNT(*) FROM evidence_fts WHERE evidence_fts MATCH :q"),
            {"q": SHA},
        ).scalar()
    assert hits == 0, "the content hash is searchable, so a query can match the wrong row"


# --------------------------------------------------------------------------- #
# downgrade
# --------------------------------------------------------------------------- #


def test_downgrading_removes_the_index_and_every_table_it_created(tmp_path: Path) -> None:
    """A virtual table that survives its downgrade leaves a database that claims
    a revision it no longer has."""
    from labcairn.db.migrations import downgrade_to_base

    target = tmp_path / "down.db"
    upgrade_to_head(target)
    downgrade_to_base(target)
    with sqlite3.connect(str(target)) as connection:
        names = {
            row[1]
            for row in connection.execute("PRAGMA table_list")
            if not row[1].startswith("sqlite_")
        }
    assert not any(name.startswith("evidence_") for name in names), sorted(names)
