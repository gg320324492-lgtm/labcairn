"""Taking a source's row back: what the removal takes, and what it leaves.

The acceptance record ``docs/acceptance/LC-P4-PILOT-source-removal-2026-11-26.md``
measured this operation on the pilot workspace — ``labcairn sources remove
--source src-0738f31ecf1e750b --json``, and the counts read back from a copy of
the database taken immediately before the command — and **nothing in the tree
held it still**. A number that was measured once on one workspace is not a
property; a property needs a witness that fails when it is broken.

So this file builds the same shape in a workspace of its own, under a temporary
directory, from the product's own APIs, and holds the behaviour still. **It
reads nothing of the pilot**: the material under ``E:/labcairn-local`` is real
material and stays out of the repository, so every byte below is written by the
test into its own temporary workspace and every row below is written by the
product into its own temporary database.

**The shape is the one the record measured.** A source's identity is its
*location*, so a material that is moved and ingested again leaves two rows
behind: one naming the path the material came from, which is not on the disk
any more, and one naming the path the material sits at now. The removal takes
the first and leaves the second. A version of a manuscript that named the first
follows the bytes to the second, because a version with no file is not a
version.

**Two paths the record reported as untested are instantiated here.** §9.2 said
the claim *"the addresses stay"* was never exercised on a source that held
addresses — the pilot's removed row held no row in ``source_anchors`` and no
row in ``evidence_records`` — and §9.3 said that a source id in
``source_anchors`` has nothing keeping it honest, so what happens when a row
that held addresses is taken back was *"reported as untested rather than as
safe"*. Both are measured here: the addresses stay, the record that cites one
stays, and the addresses are left naming a source the ledger no longer holds.

**One number in the record does not generalise, and this file says so.** The
record read ``source_problems`` at 113 before and 113 after, and the two
refusals changed nothing. That is true of the row the record removed, because
that row carried **no** disclosure of its own — the command's own report said
``removed_problem_count: 0``. It is not a property of the removal: the
disclosures about *that file at that path* go with the row, and everyone else's
stay. Measured here on a row that carried two, the count goes 4 → 2 and the
command says ``removed_problem_count: 2``. The witness asserts the behaviour
that exists, and says which shape the record's number came from.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    create_task,
    ingest_material,
)
from labcairn.application.material_ingestion import remove_source
from labcairn.core.ids import TaskId
from labcairn.db.materials import current_texts, put_anchor
from labcairn.db.repository import (
    events_after,
    load_task,
    put_paper_project,
    put_paper_version,
)
from labcairn.evidence.index import load_anchor, locate_anchor
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import append_record
from labcairn.papers.versions import PaperProject, PaperVersion, StageCandidate, VersionStatus
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.locators import CsvLocator, SourceLocator
from labcairn.sources.source import AnchorKind, SourceAnchor

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The tables the acceptance record counted, in the order it counted them.
#: The list is the record's (§6): the same eight, so a reader can put a number
#: from the pilot next to a number from here.
_COUNTED_TABLES = (
    "sources",
    "source_texts",
    "source_anchors",
    "source_problems",
    "paper_versions",
    "evidence_records",
    "evidence_anchors",
    "events",
)

#: A material with two cells and a header. A CSV is used because it carries
#: disclosures of its own — the delimiter announcement and the header notice —
#: so the witness can measure what a removal does to the disclosures of the row
#: it takes, and not only to the disclosures of other rows.
_CSV_BODY = b"a,b\n1,2\n"

#: A material with no disclosure of its own: a plain text file is read without
#: an announcement, so its row carries none. This is the shape the pilot's
#: removed row had, and it is why the record's disclosure count did not move.
_TEXT_BODY = b"first line\nsecond line\n"


# --------------------------------------------------------------------------- #
# the workspace
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _inventory_only() -> PermissionPolicy:
    """A policy that allows the inventory of material, and nothing else.

    The removal goes through the permission boundary like every other
    operation, so the policy under which it runs is part of the behaviour and
    not a detail of the test.
    """
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


def _context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context for a task that exists, under the policy the operation needs."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Taking a row back",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_inventory_only(),
        ledger=ApprovalLedger(),
    )


@dataclass(frozen=True)
class _Material:
    """One material, ingested twice: the row that is stale and the row that is not.

    ``stale_id`` names the path the material came from — a path that is not on
    the disk any more, because the material was **moved**. ``survivor_id``
    names the path the material sits at now. Both rows carry the same digest:
    one material, two locations.
    """

    context: ApplicationContext
    stale_id: str
    survivor_id: str
    digest: str
    task_id: TaskId


def _one_material_ingested_twice(
    env: StoreEnv, workspace_root: Path, *, relative: str, body: bytes
) -> _Material:
    """Ingest a material, move it, and ingest it again — the record's shape.

    The material is **moved** rather than copied, because that is what the
    pilot did and what leaves the first row behind: a source is a location, so
    a material that moves becomes a second source and the row the old path
    left behind is a row nobody has taken back yet.
    """
    materials = workspace_root / "materials"
    (materials / relative).write_bytes(body)
    context = _context(env, workspace_root)

    first = ingest_material(context, now=_MOMENT)
    stale_id = first.source_ids[0]
    digest = first.files[0].source.content_sha256

    (materials / relative).unlink()
    (materials / "moved").mkdir()
    (materials / "moved" / relative).write_bytes(body)

    second = ingest_material(context, now=_MOMENT)
    return _Material(
        context=context,
        stale_id=stale_id,
        survivor_id=second.source_ids[0],
        digest=digest,
        task_id=context.task_id,
    )


# --------------------------------------------------------------------------- #
# the rows a test needs
# --------------------------------------------------------------------------- #


def _a_version_naming(
    env: StoreEnv,
    source_id: str,
    digest: str,
    *,
    version_id: str = "ver-1",
    project_id: str = "proj-1",
) -> str:
    """A paper project, and a version of a manuscript recorded against the material.

    The rows are written through the store's own writers. A version names a
    file, and the removal's whole answer is about what happens to a version
    whose file is taken back — so the version has to be a real row with a real
    foreign key, not a shape assembled in a test.
    """
    put_paper_project(
        env.session,
        PaperProject(
            project_id=project_id,
            workspace_id="ws-1",
            subject_pseudonym="subject",
        ),
        created_at=_MOMENT,
    )
    put_paper_version(
        env.session,
        PaperVersion(
            version_id=version_id,
            project_id=project_id,
            source_content_sha256=digest,
            version_label_raw="material.txt",
            stage_candidate=StageCandidate.UNKNOWN,
            status=VersionStatus.UNRESOLVED,
        ),
        source_id=source_id,
        created_at=_MOMENT,
    )
    env.session.commit()
    return version_id


def _an_anchor_into(
    env: StoreEnv, source_id: str, digest: str, *, anchor_id: str, locator: SourceLocator
) -> SourceAnchor:
    """An address into the material — a row in ``source_anchors``.

    This is the thing the record's §9.2 said was never exercised: the pilot's
    removed row held no address, so *"the addresses stay"* was measured for the
    extracted text and for the version and **not** for the addresses.
    """
    anchor = SourceAnchor(
        anchor_id=anchor_id,
        source_id=source_id,
        kind=AnchorKind.QUOTATION,
        locator=locator,
        bound_source_sha256=digest,
        created_at=_MOMENT,
    )
    put_anchor(env.session, anchor)
    env.session.commit()
    return anchor


def _a_record_citing(
    env: StoreEnv, task_id: TaskId, anchor_id: str, digest: str, *, evidence_id: str = "ev-1"
) -> str:
    """An evidence record that cites the address, with its verification log.

    The record is written through the ledger's own writer, so it is a whole
    record — row, anchors and log — rather than a row that claims a status its
    log does not support.
    """
    span = "The value in the second row."
    record = EvidenceRecord(
        evidence_id=evidence_id,
        task_id=str(task_id),
        kind=EvidenceKind.CLAIM,
        text=span,
        anchor_ids=(anchor_id,),
        extracted_span=span,
        extracted_span_sha256=hashlib.sha256(span.encode()).hexdigest(),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=digest,
        created_at=_MOMENT,
        verification_log=(
            VerificationRecord(
                check=CheckKind.C1,
                checker_id="c1",
                outcome=CheckOutcome.PASS,
                detail="the cited address resolves",
                checked_at=_MOMENT,
            ),
        ),
    )
    append_record(env.session.connection(), record)
    env.session.commit()
    return evidence_id


# --------------------------------------------------------------------------- #
# reading the ledger back
# --------------------------------------------------------------------------- #


def _counts(session: Session) -> dict[str, int]:
    """How many rows each of the record's tables holds."""
    return {
        table: int(session.execute(sql_text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
        for table in _COUNTED_TABLES
    }


def _rows(session: Session, table: str) -> list[dict[str, Any]]:
    """Every row of a table, as a dictionary."""
    result = session.execute(sql_text(f"SELECT * FROM {table}"))
    return [dict(row) for row in result.mappings().all()]


def _source_ids(session: Session) -> tuple[str, ...]:
    """The ids of the sources the ledger holds."""
    return tuple(row["source_id"] for row in _rows(session, "sources"))


def _held(env: StoreEnv, task_id: TaskId) -> tuple[str, ...]:
    """The ids the task's binding holds, read through the store's own reader."""
    task = load_task(env.session, task_id)
    return tuple(str(bound) for bound in task.bound_source_ids)


# --------------------------------------------------------------------------- #
# the witnesses
# --------------------------------------------------------------------------- #


def test_the_row_that_names_the_path_that_is_gone_goes_and_the_one_that_is_not_stays(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The stale row goes; the row that names where the material is now does not.

    **What would make this red.** A removal that deleted by the **digest**
    rather than by the id would take the surviving row as well, and the ledger
    would hold no source for a file that is still in the workspace — the
    material would be gone from the inventory while the bytes sit there. A
    source is a location, and the removal takes back one location.

    The path is asserted as well as the row, because the coordinate is what
    the grant's scope is matched against: the material the grant covers must
    keep the key the grant names.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    materials = workspace_root / "materials"
    assert not (materials / "one.csv").exists()
    assert (materials / "moved" / "one.csv").exists()
    assert _source_ids(env.session) == (material.stale_id, material.survivor_id)

    removed = remove_source(material.context, material.stale_id)

    assert removed.source_id == material.stale_id
    assert removed.relative_path == "materials/one.csv"
    assert removed.content_sha256 == material.digest
    assert _source_ids(env.session) == (material.survivor_id,)
    survivor = _rows(env.session, "sources")[0]
    assert survivor["relative_path"] == "materials/moved/one.csv"
    assert survivor["content_sha256"] == material.digest


def test_the_extracted_text_stays_when_the_row_that_held_it_goes(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The text outlives the row: it is keyed by the content hash.

    **What would make this red.** A removal that took the extracted text with
    it would delete the records that rest on those addresses — ADR-0009 is
    explicit that a file which is deleted does not take its text with it. The
    text is read back through the store's own reader afterwards, so a removal
    that emptied the table and left the count alone could not pass.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    before = current_texts(env.session, source_content_sha256=material.digest)
    assert before, "the material yielded no text to begin with"
    texts_before = _counts(env.session)["source_texts"]

    remove_source(material.context, material.stale_id)

    assert _counts(env.session)["source_texts"] == texts_before
    after = current_texts(env.session, source_content_sha256=material.digest)
    assert [row.locator_key for row in after] == [row.locator_key for row in before]
    assert [row.text for row in after] == [row.text for row in before]


def test_the_addresses_stay_when_the_row_that_held_them_goes(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The addresses stay — the path the record's §9.2 said was never exercised.

    **What would make this red.** A removal that took the addresses with the
    row would leave every record that cites one pointing at nothing, and the
    address would resolve to nothing: a claim whose address is gone is a
    claim nobody can check. The addresses are read back through the product's
    own reader, and the address is resolved to the text at it, so a removal
    that left the rows but broke them could not pass either.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    anchor = _an_anchor_into(
        env,
        material.stale_id,
        material.digest,
        anchor_id="anc-1",
        locator=CsvLocator(row=2, column="b"),
    )
    anchors_before = _counts(env.session)["source_anchors"]
    assert anchors_before == 1

    remove_source(material.context, material.stale_id)

    assert _counts(env.session)["source_anchors"] == anchors_before
    found = load_anchor(env.session.connection(), "anc-1")
    assert found is not None
    assert found.anchor_id == anchor.anchor_id
    assert found.kind is AnchorKind.QUOTATION
    assert found.bound_source_sha256 == material.digest
    located = locate_anchor(env.session.connection(), found)
    assert located.text == "2", "the address no longer resolves to what is at it"


def test_the_addresses_left_behind_name_a_source_the_ledger_no_longer_holds(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The dangling shape, measured: this is the record's §9.3.

    ``source_anchors.source_id`` is a plain column with an index and **no
    foreign key**, so a row that held addresses can be taken back and the
    address rows stay behind naming a source the ledger does not hold. The
    record reported that path as untested rather than as safe; here it is
    measured, and this witness holds the shape still.

    **What would make this red.** A removal that re-pointed the addresses at
    the surviving row, or deleted them, would change what an address *is* —
    an address is a fact about the bytes and the row it was made against, not
    a pointer the ledger is free to move. Either change would be a decision
    rather than an accident, and this witness is where such a decision shows
    up: the tree would go red and the record would be re-measured against it.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    _an_anchor_into(
        env,
        material.stale_id,
        material.digest,
        anchor_id="anc-1",
        locator=CsvLocator(row=2, column="b"),
    )

    remove_source(material.context, material.stale_id)

    anchor_rows = _rows(env.session, "source_anchors")
    assert len(anchor_rows) == 1
    assert anchor_rows[0]["source_id"] == material.stale_id
    assert material.stale_id not in _source_ids(env.session), (
        "the row the address names is supposed to be gone — if it is not, "
        "this witness is no longer measuring the shape it names"
    )


def test_a_record_that_cites_the_address_survives_the_row_being_taken_back(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The claim that cites the address is still there, and still cites it.

    **What would make this red.** A removal that reached into the evidence
    ledger — or a cascade that did it — would leave a claim whose address is
    gone, and the claim would still be in the ledger saying it was verified.
    The record's §9.2 named the evidence table as a table the claim was never
    instantiated on; here it is.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    _an_anchor_into(
        env,
        material.stale_id,
        material.digest,
        anchor_id="anc-1",
        locator=CsvLocator(row=2, column="b"),
    )
    _a_record_citing(env, material.task_id, "anc-1", material.digest)
    records_before = _counts(env.session)["evidence_records"]
    links_before = _counts(env.session)["evidence_anchors"]
    assert records_before == 1

    remove_source(material.context, material.stale_id)

    assert _counts(env.session)["evidence_records"] == records_before
    assert _counts(env.session)["evidence_anchors"] == links_before
    record = _rows(env.session, "evidence_records")[0]
    assert record["evidence_id"] == "ev-1"
    assert record["source_content_hash"] == material.digest
    link = _rows(env.session, "evidence_anchors")[0]
    assert link["anchor_id"] == "anc-1"
    assert load_anchor(env.session.connection(), "anc-1") is not None


def test_the_disclosures_of_the_removed_row_go_with_it_and_the_others_stay(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A disclosure is about *that file at that path*, so it goes with the path.

    **What would make this red.** Two ways, and both are wrong. A removal
    that took every disclosure in the ledger would delete what the other
    files have to say about themselves — a disclosure is a fact about a
    material, and deleting it because a *different* material was taken back
    is a silent loss. A removal that left the removed row's own disclosures
    behind would leave the ledger saying that a file it does not hold has
    problems, which is a fact about nothing.

    **The number the record read.** The record measured 113 disclosures before
    and 113 after, because the row it removed carried none of its own
    (``removed_problem_count: 0``). Here the removed row carries two, and the
    count moves by exactly two.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    problems_before = _counts(env.session)["source_problems"]
    own = _rows(env.session, "source_problems")
    own_before = [row for row in own if row["source_id"] == material.stale_id]
    others_before = [row for row in own if row["source_id"] == material.survivor_id]
    assert own_before, "the removed row carried no disclosure of its own"
    assert others_before, "the surviving row carried no disclosure of its own"

    removed = remove_source(material.context, material.stale_id)

    assert removed.removed_problem_count == len(own_before)
    assert _counts(env.session)["source_problems"] == problems_before - len(own_before)
    after = _rows(env.session, "source_problems")
    assert [row["source_id"] for row in after] == [row["source_id"] for row in others_before]
    assert [row["code"] for row in after] == [row["code"] for row in others_before]


def test_a_removed_row_that_carried_no_disclosure_leaves_the_count_untouched(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The record's own shape, held still: a row with no disclosure of its own.

    A plain text file is read without an announcement, so its row carries no
    disclosure — which is the shape the pilot's removed row had, and the
    reason the record read 113 before and 113 after. This witness says that
    shape is a *consequence* of what the row carried, not a rule that the
    count never moves: the row that had two took two with it, and the row that
    had none took none.

    **What would make this red.** A removal that deleted disclosures it does
    not own — the other material's disclosures — would move this count even
    though the removed row carried none. That is the failure the count would
    otherwise hide.
    """
    material = _one_material_ingested_twice(
        env, workspace_root, relative="one.txt", body=_TEXT_BODY
    )
    # Another material, which **does** carry disclosures of its own: a plain
    # text file is read without an announcement, and a CSV is read with two.
    # Without one, the ledger would hold no disclosure at all, and a removal
    # that took every disclosure in it would move nothing.
    materials = workspace_root / "materials"
    (materials / "other.csv").write_bytes(_CSV_BODY)
    other = ingest_material(material.context, now=_MOMENT)
    other_id = other.source_ids[0]
    problems_before = _counts(env.session)["source_problems"]
    others_before = [
        row for row in _rows(env.session, "source_problems") if row["source_id"] == other_id
    ]
    assert problems_before > 0, "no material in the ledger carried a disclosure of its own"

    removed = remove_source(material.context, material.stale_id)

    assert removed.removed_problem_count == 0
    assert _counts(env.session)["source_problems"] == problems_before
    after = [row for row in _rows(env.session, "source_problems") if row["source_id"] == other_id]
    assert [row["code"] for row in after] == [row["code"] for row in others_before]


def test_the_version_that_named_the_removed_row_points_at_the_surviving_one(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A version follows the bytes to the row that holds them.

    **What would make this red.** A removal that took the version's row with
    it would delete a version of a manuscript — the record of a draft, with
    its label and its place in the version graph. A removal that left the
    version naming a row the ledger does not hold would make it a version
    with no file, which the schema itself refuses to call a version. The
    version's own digest is not touched by the move, because the bytes are
    the same bytes.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    version_id = _a_version_naming(env, material.stale_id, material.digest)

    removed = remove_source(material.context, material.stale_id)

    assert removed.repointed_version_ids == (version_id,)
    assert removed.repointed_to_source_id == material.survivor_id
    version = _rows(env.session, "paper_versions")[0]
    assert version["version_id"] == version_id
    assert version["source_id"] == material.survivor_id
    assert version["source_content_sha256"] == material.digest


def test_no_version_is_lost_added_or_changed_its_digest(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The whole version table, before and after: the same rows, the same hashes.

    **What would make this red.** Three ways. A removal that dropped a version
    would delete a draft. A removal that added one would put a version in the
    ledger that nobody wrote. A removal that rewrote a digest would move a
    version's identity onto bytes it was not recorded from — and the schema
    says the hash is written down once, precisely so that the bytes cannot
    move underneath it. The version that named the *surviving* row keeps its
    own row: the removal re-points what it took, and touches nothing else.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    _a_version_naming(env, material.stale_id, material.digest, version_id="ver-moved")
    _a_version_naming(
        env,
        material.survivor_id,
        material.digest,
        version_id="ver-stayed",
        project_id="proj-2",
    )
    before = _rows(env.session, "paper_versions")
    assert len(before) == 2

    remove_source(material.context, material.stale_id)

    after = _rows(env.session, "paper_versions")
    assert len(after) == len(before), "a version was lost or added"
    assert [row["version_id"] for row in after] == [row["version_id"] for row in before]
    assert [row["source_content_sha256"] for row in after] == [
        row["source_content_sha256"] for row in before
    ], "a version's digest changed"
    stayed = next(row for row in after if row["version_id"] == "ver-stayed")
    assert stayed["source_id"] == material.survivor_id, (
        "the version that named the surviving row was re-pointed at something else"
    )


def test_a_second_removal_of_the_same_id_refuses_and_changes_nothing(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The second removal of an id that is not there is refused, and moves nothing.

    **What would make this red.** A removal that treated an id it does not
    hold as an empty job — deleting nothing but reporting success — would
    leave an operator believing the ledger was tidied when it was not. A
    removal that raised something other than a refusal would break the
    surface's own rule: one refusal type, one reason vocabulary.

    Every table is counted before and after, **including the events**, so a
    refusal that left a trace — a row, a binding, a log entry — fails here
    rather than passing on the strength of the exception alone.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    version_id = _a_version_naming(env, material.stale_id, material.digest)
    remove_source(material.context, material.stale_id)
    before = _counts(env.session)

    with pytest.raises(ApplicationRefusedError) as caught:
        remove_source(material.context, material.stale_id)

    assert caught.value.reason is ApplicationRefusal.SOURCE_NOT_FOUND
    assert material.stale_id in caught.value.detail
    assert _counts(env.session) == before
    assert _source_ids(env.session) == (material.survivor_id,)
    version = _rows(env.session, "paper_versions")[0]
    assert version["version_id"] == version_id
    assert version["source_id"] == material.survivor_id


def test_the_removal_is_refused_where_the_material_is_nowhere_else_and_nothing_moves(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A version with no file is not a version: the material stays in the ledger.

    This is the record's other refusal. The material's bytes are nowhere else
    in the ledger, so taking it back would take a version's row with it — and
    the schema says that would cascade.

    **What would make this red.** A removal that took the material anyway
    would delete a draft of a manuscript, and the version row would go with it
    by the foreign key's own hand — so the ledger would lose both, and the
    refusal that is supposed to protect it would be decoration. The count
    before and after covers every table, the events among them.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    # A material of its own: its bytes are nowhere else in the ledger.
    materials = workspace_root / "materials"
    (materials / "lonely.csv").write_bytes(b"c,d\n5,6\n")
    lonely = ingest_material(material.context, now=_MOMENT)
    lonely_id = lonely.source_ids[0]
    lonely_digest = lonely.files[0].source.content_sha256
    _a_version_naming(env, lonely_id, lonely_digest, version_id="ver-lonely", project_id="proj-3")
    before = _counts(env.session)

    with pytest.raises(ApplicationRefusedError) as caught:
        remove_source(material.context, lonely_id)

    assert caught.value.reason is ApplicationRefusal.PAPER_CONTRACT_REFUSED
    assert "ver-lonely" in caught.value.detail
    assert _counts(env.session) == before
    assert lonely_id in _source_ids(env.session)
    version = next(
        row for row in _rows(env.session, "paper_versions") if row["version_id"] == "ver-lonely"
    )
    assert version["source_id"] == lonely_id


def test_the_removal_is_recorded_in_the_log_as_the_task_s_own_revision(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The task lets the material go, and the log says that the task was revised.

    **What would make this red.** A removal that released the binding
    without writing the event would leave a change nobody could find in the
    log. A removal that released the binding *and left it* would leave a task
    claiming material the ledger does not hold, and the layer refuses that
    when it lists a task's sources — so the task would be broken by an
    operation that reported success.

    **What is not asserted.** The record observed that the removal of the row
    itself is **not** in the log: the event vocabulary has ``source_changed``,
    and ``remove_source`` writes no event of that kind. This witness does not
    freeze that, because an event that named the removal would be an
    improvement rather than a regression, and a witness that forbade it would
    forbid the better answer. It holds the shape that is here: one event, the
    task's own revision.
    """
    material = _one_material_ingested_twice(env, workspace_root, relative="one.csv", body=_CSV_BODY)
    events_before = events_after(env.session, material.task_id)

    remove_source(material.context, material.stale_id)

    events_after_removal = events_after(env.session, material.task_id)
    new = events_after_removal[len(events_before) :]
    assert len(new) == 1, "the removal wrote something other than one event"
    assert new[0].type is EventType.TASK_REVISED
    assert new[0].task_id == material.task_id
    assert material.stale_id not in _held(env, material.task_id)
    assert material.survivor_id in _held(env, material.task_id)
