"""Recording a claim through the product, and what the ledger and checks see.

The gap this file closes was stated as a limitation in the acceptance
documents: **the product had no operation that wrote an evidence record or an
anchor**, so the only path that ended with a report was the outsider walk,
which wrote the claim's own address itself. These tests are about the
operation that does it, and each one is a property the product now rests on:

**The address must be in the ledger's text for the bytes the source holds
now.** An anchor bound to one version of a file and pointing at an address
another version answers is the drift ADR-0004 I4 exists to detect, so the
write happens against the text the ledger holds and resolves it first.

**The task must hold the material.** A report's builder refuses an anchor
whose source the report does not carry, so a claim on unbound material would
make every later report of the task refuse.

**Recording is not verifying.** The record is ``extracted`` and the check
that can confirm its quotation is run afterwards, by ``advance`` — and the
test runs it, so "the writer's output is usable by the check path" is a
measured fact rather than an intention.

**A report can be produced from a product-written claim.** This is the
end-to-end property §2.2 is about: the report is rendered by the layer, from
a record no test wrote itself.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    ClaimRequest,
    ReportRequest,
    SourceAddress,
    create_task,
    ingest_material,
    list_source_addresses,
    list_sources,
    record_claim,
    render_report,
)
from labcairn.core.ids import SourceId
from labcairn.db.materials import put_source
from labcairn.db.repository import load_task
from labcairn.evidence.index import LabCairnIndex, load_anchor
from labcairn.evidence.states import CheckKind, EvidenceKind, VerificationStatus
from labcairn.evidence.store import advance, load_task_records
from labcairn.material.addressing import split_locator_key
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.source import Source, SourceKind, SourceReadability

pytestmark = pytest.mark.integration

env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The table the numeric claim is read from.
_CSV_TEXT = "group,value\nA,1\nB,2\n"

#: The note the sentence claim is read from.
_NOTES_TEXT = "The yield across the five runs was 4.253 percent.\n"


def _allow_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _write_the_material(workspace_root: Path) -> None:
    (workspace_root / "materials" / "groups.csv").write_text(_CSV_TEXT, encoding="utf-8")
    (workspace_root / "materials" / "notes.md").write_text(_NOTES_TEXT, encoding="utf-8")


def _context(
    env: StoreEnv,
    workspace_root: Path,
    policy: PermissionPolicy | None = None,
) -> ApplicationContext:
    """A task that holds the workspace's material, under the policy wanted."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Recording claims",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )
    ingest_material(context, now=_MOMENT)
    return ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=policy if policy is not None else _allow_all(),
        ledger=context.ledger,
    )


def _source_id(context: ApplicationContext, suffix: str) -> str:
    """The id of the material whose path ends with *suffix*, as the task holds it."""
    held = {
        str(bound) for bound in load_task(context.store.session, context.task_id).bound_source_ids
    }
    for view in list_sources(context):
        if view.source.relative_path.endswith(suffix) and view.source.source_id in held:
            return view.source.source_id
    raise AssertionError(f"the task holds no material ending in {suffix!r}: {sorted(held)}")


def _an_address(
    context: ApplicationContext,
    source_id: str,
    *,
    predicate: Callable[[SourceAddress], bool],
) -> tuple[str, str]:
    """One address's ``(locator_key, text)`` matching *predicate*."""
    for address in list_source_addresses(context, source_id):
        if predicate(address):
            return address.locator_key, address.text
    raise AssertionError(f"no address of {source_id} matched")


def _assert_refused(
    call: Callable[[], object], reason: ApplicationRefusal
) -> ApplicationRefusedError:
    with pytest.raises(ApplicationRefusedError) as caught:
        call()
    assert caught.value.reason is reason
    return caught.value


# --------------------------------------------------------------------------- #
# listing the addresses
# --------------------------------------------------------------------------- #


def test_the_addresses_are_the_ledgers_text_for_the_material(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Every address the listing reports is one the ledger holds text at.

    The listing is not a second extraction: the keys parse, the kinds are the
    material's own, and the text is what ``source_texts`` holds for the
    source's current bytes.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    csv_id = _source_id(context, "groups.csv")

    addresses = list_source_addresses(context, csv_id)

    assert addresses, "the ingested table yielded no addresses"
    for address in addresses:
        fields = split_locator_key(address.locator_key)
        assert fields["k"] == "csv"
        assert address.locator_kind == "csv"
        assert address.text != ""

    # The shape of the ledger's own key, not a key the listing invented: the
    # row and column the claim below rests on are addressable.
    values = {
        split_locator_key(address.locator_key)["c"]: address
        for address in addresses
        if "c" in split_locator_key(address.locator_key)
    }
    assert "value" in values


def test_an_unknown_source_has_no_addresses(env: StoreEnv, workspace_root: Path) -> None:
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)

    _assert_refused(
        lambda: list_source_addresses(context, "src-0000000000000000"),
        ApplicationRefusal.SOURCE_NOT_FOUND,
    )


def test_a_denied_source_is_not_listed(env: StoreEnv, workspace_root: Path) -> None:
    """ADR-0003 C5's posture, on the single-source ask: a denial is a refusal."""
    _write_the_material(workspace_root)
    deny = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    context = _context(env, workspace_root)
    csv_id = _source_id(context, "groups.csv")
    denied = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=deny,
        ledger=context.ledger,
    )

    _assert_refused(
        lambda: list_source_addresses(denied, csv_id),
        ApplicationRefusal.PERMISSION_DENIED,
    )


# --------------------------------------------------------------------------- #
# recording a claim
# --------------------------------------------------------------------------- #


def test_a_claim_is_located_resolves_and_carries_the_sources_hash(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The record is in the ledger, its anchor is in the registry, and both bind."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    csv_id = _source_id(context, "groups.csv")
    locator_key, text = _an_address(
        context, csv_id, predicate=lambda address: address.text.strip() == "1"
    )

    recorded = record_claim(
        context,
        ClaimRequest(
            source_id=csv_id,
            locator_key=locator_key,
            kind=EvidenceKind.NUMERIC,
            value=1.0,
            unit="dimensionless",
        ),
        now=_MOMENT,
    )

    records = load_task_records(context.store.session.connection(), str(context.task_id))
    assert [record.evidence_id for record in records] == [recorded.record.evidence_id]
    record = records[0]
    assert record.status is VerificationStatus.EXTRACTED
    assert record.anchor_ids == (recorded.anchor_id,)
    assert record.source_content_hash is not None
    assert record.extracted_span == text

    anchor = load_anchor(context.store.session.connection(), recorded.anchor_id)
    assert anchor is not None
    assert anchor.source_id == csv_id
    assert anchor.bound_source_sha256 == record.source_content_hash
    located = LabCairnIndex(context.store.session.connection()).locate(anchor)
    assert located is not None
    assert located.resolution.value == "resolved"


def test_a_denied_source_cannot_have_a_claim_recorded(env: StoreEnv, workspace_root: Path) -> None:
    """The write half of the same posture the listing test checks.

    `record_claim` asks the policy (`source.inventory` consent) before it
    resolves or writes. The listing path has a denial witness
    (`test_a_denied_source_is_not_listed`) but the write path did not, so
    deleting `record_claim`'s consent ask left every claim test green — a
    DENY policy would still have written an anchor and an `extracted` record.
    This closes that: everything the request would otherwise accept is
    supplied, the only difference from the passing test is a deny-everything
    policy, and the expectation is a refusal that writes nothing.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    csv_id = _source_id(context, "groups.csv")
    locator_key, _text = _an_address(
        context, csv_id, predicate=lambda address: address.text.strip() == "1"
    )
    deny = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    denied = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=deny,
        ledger=context.ledger,
    )

    _assert_refused(
        lambda: record_claim(
            denied,
            ClaimRequest(
                source_id=csv_id,
                locator_key=locator_key,
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    connection = denied.store.session.connection()
    assert load_task_records(connection, str(denied.task_id)) == ()
    anchors: int = connection.execute(text("SELECT COUNT(*) FROM source_anchors")).scalar_one()
    assert anchors == 0, "a refused claim must not have left an anchor behind"


def test_the_check_path_can_verify_a_product_written_claim(
    env: StoreEnv, workspace_root: Path
) -> None:
    """C2 confirms the quotation, and the status moves through ``advance``.

    The record is written ``extracted``; the pass is a **separate act** with
    its own audit row. What this measures is that the writer's output is the
    input the check path is built to consume — a claim copied out of the
    ledger's own text matches it, and the upgrade is recorded.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "notes.md")
    locator_key, text = _an_address(
        context, source_id, predicate=lambda address: address.text.strip().startswith("The yield")
    )

    recorded = record_claim(
        context,
        ClaimRequest(source_id=source_id, locator_key=locator_key, text=text.strip()),
        now=_MOMENT,
    )
    connection = context.store.session.connection()
    verified = advance(
        connection,
        recorded.record.evidence_id,
        VerificationStatus.VERIFIED_BY_RULE,
        index=LabCairnIndex(connection),
        checks=(CheckKind.C2,),
        checked_at=_MOMENT,
    )
    context.store.session.commit()

    assert verified.status is VerificationStatus.VERIFIED_BY_RULE
    assert any(
        entry.check is CheckKind.C2 and entry.outcome.value == "pass"
        for entry in verified.verification_log
    )


def test_a_report_is_rendered_from_a_product_written_claim(
    env: StoreEnv, workspace_root: Path
) -> None:
    """§2.2's end-to-end property: the report's claim is the product's own.

    Nothing in this test writes an anchor or a record by hand. The claim is
    recorded through the layer, the report is rendered through the layer, and
    the sentence the material holds is in the report's Markdown.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "notes.md")
    locator_key, text = _an_address(
        context, source_id, predicate=lambda address: address.text.strip().startswith("The yield")
    )
    record_claim(
        context,
        ClaimRequest(source_id=source_id, locator_key=locator_key, text=text.strip()),
        now=_MOMENT,
    )

    rendered = render_report(
        context, ReportRequest(path="report", template_id="default"), now=_MOMENT
    )

    assert rendered.resource_key == "report"
    revision_dir = context.workspace.output_root.path / "report" / f"v{rendered.receipt.revision}"
    markdown = (revision_dir / "report.md").read_text(encoding="utf-8")
    # The Markdown writer escapes punctuation that could be read as syntax, so
    # the assertions are made against the text it draws rather than its bytes.
    plain = markdown.replace("\\", "")
    assert "The yield across the five runs was 4.253 percent." in plain
    assert "(extracted)" in plain, "the report does not state the ledger's status"


def test_the_task_must_hold_the_material(env: StoreEnv, workspace_root: Path) -> None:
    """A claim on material another task holds is refused, and nothing is written."""
    _write_the_material(workspace_root)
    holding = _context(env, workspace_root)
    source_id = _source_id(holding, "groups.csv")
    locator_key, _text = _an_address(
        holding, source_id, predicate=lambda address: address.text.strip() == "1"
    )

    # A second task in the same workspace, holding nothing.
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Holds nothing",
        goal=TaskGoal(objective="One.", success_criterion="Done."),
        source_dirs=(),
    )
    empty = ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )

    _assert_refused(
        lambda: record_claim(
            empty,
            ClaimRequest(
                source_id=source_id,
                locator_key=locator_key,
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.SOURCE_NOT_BOUND,
    )
    assert load_task_records(empty.store.session.connection(), str(empty.task_id)) == ()


def test_an_unreadable_source_cannot_be_cited(env: StoreEnv, workspace_root: Path) -> None:
    """ADR-0004 A7: unreadable material is neither analysed nor cited."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = "src-00000000000000aa"
    put_source(
        context.store.session,
        Source(
            source_id=source_id,
            kind=SourceKind.PDF,
            display_name="scan.pdf",
            relative_path="materials/scan.pdf",
            content_sha256="0" * 64,
            size_bytes=1,
            readability=SourceReadability.UNREADABLE_NO_OCR,
            readability_disclosure="no text layer; OCR is not available",
            ingested_at=_MOMENT,
        ),
    )
    context.store.bind_sources(context.task_id, (SourceId(source_id),), occurred_at=_MOMENT)
    context.store.session.commit()

    _assert_refused(
        lambda: record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key="k=3:csv|r=1:1|c=4:mean",
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.SOURCE_UNREADABLE,
    )


def test_an_address_nothing_answers_is_refused_and_writes_nothing(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An anchor at an address nothing answers is an anchor to nothing."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "groups.csv")

    _assert_refused(
        lambda: record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key="k=3:csv|r=3:999|c=5:value",
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.ADDRESS_NOT_FOUND,
    )
    connection = context.store.session.connection()
    assert load_task_records(connection, str(context.task_id)) == ()
    anchors: int = connection.execute(text("SELECT COUNT(*) FROM source_anchors")).scalar_one()
    assert anchors == 0


def test_a_malformed_address_is_an_argument_that_is_not_usable(
    env: StoreEnv, workspace_root: Path
) -> None:
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "groups.csv")

    _assert_refused(
        lambda: record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key="not a key",
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )


def test_a_result_is_not_a_claim_read_out_of_material(env: StoreEnv, workspace_root: Path) -> None:
    """``result`` is the analysis path's record, not this operation's."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "groups.csv")
    locator_key, _text = _an_address(
        context, source_id, predicate=lambda address: address.text.strip() == "1"
    )

    _assert_refused(
        lambda: record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key=locator_key,
                kind=EvidenceKind.RESULT,
                text="a result",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )


def test_the_same_span_twice_is_refused_by_name(env: StoreEnv, workspace_root: Path) -> None:
    """``uq_evidence_task_span`` is one record per span per task, said plainly."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "groups.csv")
    locator_key, _text = _an_address(
        context, source_id, predicate=lambda address: address.text.strip() == "1"
    )
    request = ClaimRequest(
        source_id=source_id,
        locator_key=locator_key,
        kind=EvidenceKind.NUMERIC,
        value=1.0,
        unit="dimensionless",
    )
    first = record_claim(context, request, now=_MOMENT)

    _assert_refused(
        lambda: record_claim(context, request, now=_MOMENT),
        ApplicationRefusal.CLAIM_ALREADY_RECORDED,
    )

    connection = context.store.session.connection()
    records = load_task_records(connection, str(context.task_id))
    assert [record.evidence_id for record in records] == [first.record.evidence_id]


def test_a_claim_with_a_missing_unit_is_an_argument_that_is_not_usable(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The record model's rule, not a second one stated by the writer."""
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    source_id = _source_id(context, "groups.csv")
    locator_key, _text = _an_address(
        context, source_id, predicate=lambda address: address.text.strip() == "1"
    )

    _assert_refused(
        lambda: record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key=locator_key,
                kind=EvidenceKind.NUMERIC,
                value=1.0,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )
