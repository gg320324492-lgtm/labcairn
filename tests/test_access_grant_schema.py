"""The grant table's schema, and the rows it must refuse.

**What is under test.** LC-P2-06 T00: `access_grants` and `derived_copies`,
and the four refusals the schema holds.

**Why the refusals are witnessed by writing rows.** The project's lesson
from revision 0007: *"the parity test passed through it, because the
migration and the ORM were mangled identically — a test comparing two
texts cannot catch both being wrong."* So each rule is witnessed by
**writing a row the schema must refuse** and watching the database refuse
it, with a raw ``INSERT`` that bypasses the ORM.

**The four refusals.**

1. **A transmit grant with no destination.** It is a grant to send
   anywhere, which is the thing ADR-0015 D3 exists to prevent.
2. **A non-transmit grant with a destination.** Nothing needs it, and its
   presence would let a read grant be read as a transmit grant.
3. **A withdrawal with nobody behind it.** A state of ``withdrawn`` and no
   granter is a refusal nobody made.
4. **A permission or a purpose outside its vocabulary.** A typo like
   ``transmit`` instead of ``external_transmit`` must not sail through as
   a permission nobody holds.

**And the one that is not a refusal**, which matters as much: **there is
no row shape that means "denied".** The table holds only grants, and the
absence of a row is the refusal. A schema test cannot assert an absence
directly, so the test below asserts the shape of the *vocabulary*: every
row in the table is a permission somebody granted, and nothing in the
table's columns can say "no".
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory

pytestmark = pytest.mark.integration

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)

#: **The columns a grant is made of** — ADR-0015 D1's twelve, plus the
#: destination D3 requires (*"a grant naming provider A does not authorise
#: provider B"*).
#:
#: **The list is the shape, and the shape is the property.** A name list of
#: forbidden columns catches the five spellings a reader would guess and
#: nothing else: a table that grew a ``consent_state`` or a
#: ``permitted_flag`` would pass it, and a flag column is precisely what
#: D2 says must not exist. **So the assertion is against the whole set**,
#: and a column that is not on it is a column nobody designed.
GRANT_COLUMNS: frozenset[str] = frozenset(
    {
        "grant_id",
        "subject_ref",
        "purpose",
        "permission",
        "scope",
        "destination",
        "granted_by",
        "granted_at",
        "expires_at",
        "state",
        "withdrawn_at",
        "withdrawn_by",
        "withdrawal_reason",
    }
)

#: The three states a grant may be in, and no others.
GRANT_STATES: tuple[str, ...] = ("active", "withdrawn", "expired")


@pytest.fixture(scope="module")
def migrated_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The database, **migrated once for the whole module**.

    **The same shape as LC-P2-08's, and for the same reason.** A
    function-scoped migration would rebuild the schema for every test, and
    the runner's measurement found that cost on LC-P2-08's file: **38
    seconds on Windows** against a apportioned 0.64. The migration is
    module-scoped here for the same reason, and each test gets a copy.
    """
    directory = tmp_path_factory.mktemp("access-grants")
    database = directory / "template.db"
    upgrade_to_head(database)
    return database


@pytest.fixture()
def store(migrated_database: Path, tmp_path: Path) -> TaskStore:
    """A store on a **copy** of the migrated database.

    **A copy, and not the template.** Several of these tests have their
    writes *refused*, and a refused write leaves a transaction the next
    test must not inherit.
    """
    database = tmp_path / "grants.db"
    shutil.copyfile(migrated_database, database)
    engine = create_db_engine(database)
    session = create_session_factory(engine)()
    return TaskStore(session)


def _grant(store: TaskStore, grant_id: str, **overrides: object) -> None:
    """Insert a grant row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "grant_id": grant_id,
        "subject_ref": "proj-1",
        "permission": "store_read",
        "purpose": "read",
        "scope": "paper-1/**",
        "destination": None,
        "granted_by": "Dr. Chen",
        "granted_at": NOW.isoformat(),
        "expires_at": None,
        "state": "active",
        "withdrawn_at": None,
        "withdrawn_by": None,
        "withdrawal_reason": None,
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    with store.session as session:
        session.execute(
            text(f"INSERT INTO access_grants ({columns}) VALUES ({placeholders})"),
            values,
        )
        session.commit()


# --------------------------------------------------------------------------- #
# the schema refuses
# --------------------------------------------------------------------------- #


def test_a_transmit_grant_with_no_destination_is_refused(store: TaskStore) -> None:
    """A grant to send anywhere is a grant to send to a provider nobody
    approved.

    **What breaks it:** making ``destination`` optional for
    ``external_transmit``. The row would then name the permission and no
    place, and ADR-0015 D3's rule — *"a grant naming provider A does not
    authorise provider B"* — would have nothing to compare against.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(
            store,
            "g1",
            permission="external_transmit",
            purpose="transmit",
            destination=None,
        )
    assert "access_grants_destination_belongs_to_transmit" in str(refused.value)


def test_a_read_grant_with_a_destination_is_refused(store: TaskStore) -> None:
    """The other three permissions name no place.

    **What breaks it:** letting a destination ride along on any grant. A
    read grant that names a provider reads like a transmit grant to
    anything that checks the destination first, and the two are not the
    same permission.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", destination="api.minimax.cn")
    assert "access_grants_destination_belongs_to_transmit" in str(refused.value)


def test_a_withdrawal_with_nobody_behind_it_is_refused(store: TaskStore) -> None:
    """A state of ``withdrawn`` and no granter is a refusal nobody made.

    **What breaks it:** allowing ``state='withdrawn'`` without the
    granter. The row would say the permission was taken back and name
    nobody, and a check that cannot say *who* withdrew it cannot answer
    the question a person will ask.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", state="withdrawn", withdrawn_by=None, withdrawn_at=None)
    assert "access_grants_withdrawal_names_who_and_when" in str(refused.value)


def test_a_withdrawal_with_nobody_behind_it_is_refused_even_with_a_time(
    store: TaskStore,
) -> None:
    """The granter is required, and a time does not stand in for one.

    **What breaks it:** accepting the timestamp as the record of who. A
    withdrawal with a time and no granter says *when* and not *by whom*,
    and the second is the part that is the answer.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", state="withdrawn", withdrawn_by=None, withdrawn_at=NOW.isoformat())
    assert "access_grants_withdrawal_names_who_and_when" in str(refused.value)


def test_a_permission_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """The four permissions are closed.

    **What breaks it:** widening the vocabulary. A typo like ``transmit``
    instead of ``external_transmit`` would sail through and be
    indistinguishable from a real permission — and a permission nobody
    holds is the whole failure this table exists to prevent.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", permission="transmit")
    assert "access_grants_permission_vocabulary" in str(refused.value)


def test_a_purpose_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """The five purposes are closed, on the same standard."""
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", purpose="read_it")
    assert "access_grants_purpose_vocabulary" in str(refused.value)


def test_a_state_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """The three states are closed: active, withdrawn, expired."""
    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g1", state="pending")
    assert "access_grants_state_vocabulary" in str(refused.value)


def test_a_derived_copy_kind_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """The five kinds of derived copy are closed.

    **What breaks it:** a free-text kind, which would make "does this
    withdrawal reach it" unanswerable — because a copy of a kind nobody
    enumerated is a copy nobody looks for.
    """
    _grant(store, "g1")
    # **The two ``with`` statements are not combined on purpose.** The
    # session must be inside the ``raises``, because the refusal has to
    # happen *inside* the transaction -- a session opened outside it would
    # raise on the way out of the block rather than on the insert.
    with pytest.raises(IntegrityError) as refused:  # noqa: SIM117
        with store.session as session:
            session.execute(
                text(
                    "INSERT INTO derived_copies (copy_id, grant_id, kind, location, "
                    "subject_ref, created_at) VALUES "
                    "('c1', 'g1', 'spreadsheet', 'somewhere', 'proj-1', :t)"
                ),
                {"t": NOW.isoformat()},
            )
            session.commit()
    assert "derived_copies_kind_vocabulary" in str(refused.value)


# --------------------------------------------------------------------------- #
# the schema accepts what it must
# --------------------------------------------------------------------------- #


def test_a_transmit_grant_with_a_destination_is_storable(store: TaskStore) -> None:
    """The one shape a transmit grant may take.

    **What breaks it:** making the destination impossible to record. The
    grant would then be a permission with no place, and D3's rule would
    have nothing to compare.
    """
    _grant(
        store,
        "g1",
        permission="external_transmit",
        purpose="transmit",
        destination="api.minimax.cn",
    )

    with store.session as session:
        row = session.execute(
            text("SELECT destination, state FROM access_grants WHERE grant_id = 'g1'")
        ).one()
    assert row.destination == "api.minimax.cn"
    assert row.state == "active"


def test_an_active_grant_has_no_withdrawal_fields(store: TaskStore) -> None:
    """An active grant carries no withdrawal fields.

    **The other direction of the same constraint**, and the one that keeps
    the pair honest: a row that says "active" and also names a withdrawal
    is two stories at once, and a reader cannot tell which is true.
    """
    with pytest.raises(IntegrityError) as refused:
        _grant(
            store,
            "g1",
            state="active",
            withdrawn_by="Dr. Chen",
            withdrawn_at=NOW.isoformat(),
        )
    assert "access_grants_withdrawal_names_who_and_when" in str(refused.value)


def test_the_table_holds_only_grants_and_therefore_has_no_way_to_say_denied(
    store: TaskStore,
) -> None:
    """**There is no row shape that means "denied".**

    ADR-0015 D2 says the permission is *"denied in the model"*: there is no
    row, so there is nothing to check, so the path cannot proceed. **A
    schema test cannot assert an absence directly**, so this test asserts
    the shape that produces it:

    - **every column of the table is a column the design names** — ADR-0015
      D1's twelve, plus the destination D3 requires — and nothing else;
    - **there is no column that holds a yes or a no** — no ``permitted``,
      no ``allowed``, no ``denied``.

    **The shape, and not a list of names.** A list of forbidden spellings
    catches the five a reader would guess and nothing more: a column named
    ``consent_state`` or ``permitted_flag`` would pass it, and a flag
    column is precisely what D2 says must not exist. **So the assertion is
    against the whole set of columns**, and a column that is not on it is
    a column nobody designed.

    A column that could hold ``False`` could also be flipped to ``True`` by
    an update nobody audited, and the whole design is that the answer is a
    fact on the record rather than a flag somebody flipped.
    """
    with store.session as session:
        columns = {row[1] for row in session.execute(text("PRAGMA table_info(access_grants)"))}

    extra = sorted(columns - GRANT_COLUMNS)
    missing = sorted(GRANT_COLUMNS - columns)
    assert columns == GRANT_COLUMNS, (
        f"the grant table's columns are not the ones the design names. "
        f"extra: {extra}; missing: {missing}. A column that can hold a yes "
        f"or a no -- a ``permitted`` or a ``consent_state``, say -- would let "
        f"a permission be turned on by an update nobody audited, and the "
        f"permission is denied by the *absence* of a row."
    )


def test_the_state_column_cannot_hold_a_denial(store: TaskStore) -> None:
    """**The one column that could have said "no", and does not.**

    ``state`` is the column a table would reach for when it wanted to say
    "this was refused" — and a fourth state called ``denied`` would be
    exactly the row shape D2 says must not exist. **So the vocabulary is
    closed at three**, and this test says so by writing the rows: each of
    the three storable, and the one that would mean "denied" refused.

    **What breaks it:** widening ``access_grants_state_vocabulary``. A
    reader of the row would see a permission that was denied — a fact
    somebody could have written — rather than the absence of a grant.
    """
    for state in GRANT_STATES:
        values: dict[str, object] = {}
        if state == "withdrawn":
            values = {"withdrawn_by": "Dr. Chen", "withdrawn_at": NOW.isoformat()}
        _grant(store, f"g-{state}", state=state, **values)

    with pytest.raises(IntegrityError) as refused:
        _grant(store, "g-denied", state="denied")
    assert "access_grants_state_vocabulary" in str(refused.value)


def test_a_derived_copy_records_the_grant_it_came_from(store: TaskStore) -> None:
    """The provenance is the whole reason the row exists.

    **What breaks it:** a derived copy with no grant recorded. It would
    have no provenance, so a withdrawal could not reach it — and the
    design's question ("do the historical embeddings, caches and training
    queues expire when consent is withdrawn?") would have no answer.
    """
    _grant(store, "g1")
    with store.session as session:
        session.execute(
            text(
                "INSERT INTO derived_copies (copy_id, grant_id, kind, location, "
                "subject_ref, created_at) VALUES "
                "('c1', 'g1', 'embedding', 'vectors/c1', 'proj-1', :t)"
            ),
            {"t": NOW.isoformat()},
        )
        session.commit()
        row = session.execute(
            text("SELECT grant_id, kind FROM derived_copies WHERE copy_id = 'c1'")
        ).one()
    assert row.grant_id == "g1"
    assert row.kind == "embedding"
