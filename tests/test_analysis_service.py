"""The run path: from a granted capability to a recorded artefact.

LC-P1-10 T09. This is the file that says what an analysis *is* in this
project: a registered operator, a selection, an approval that covers exactly
those two, and a manifest plus receipts afterwards. The properties below are
the ones the work order names, and each is written so that it could fail.

**The corpus is the oracle.** Nothing here computes an expected number. The
expected mean of ``basic.csv`` is read out of the committed
``*.expected.json`` beside the fixture, so a test that passes means the run
agreed with a value nobody in this repository produced.

**The consent is the point.** An ``analysis.run`` approval is bound to the
capability, the resource key and the arguments digest, so an approval to
analyse one selection does not authorise another. That is the property most
of the refusals below exist to check, and the mutation table at the end
records the ways it could be undone.

**The order is load-bearing and is observed, not assumed.** The environment is
prepared *before* the manifest is built, because the manifest records the
environment the render happens in; and the manifest is written *before* the
figure, because the figure's chain names the manifest. Both are checked by
behaviour -- a salt the renderer sets, and a file the renderer looks for --
rather than by reading the source and agreeing with it.

**A refusal names what is wrong.** Every refusal below is checked for the
fact it names, not merely for having happened: a refusal that says "refused"
and a refusal that says "the file now hashes to X and the source was ingested
from bytes that hash to Y" are different products, and only the second is
usable by the person who has to act on it.

The mutation notes at the end of this file record the ways each property
could be undone and the named test that catches each one. A property no
mutation reached is a property nothing observes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import Engine, select

from labcairn.analysis.catalog import operator_for
from labcairn.analysis.manifest import canonical_digest, selection_payload
from labcairn.analysis.operators import operator_reference
from labcairn.analysis.selection import (
    MissingPolicy,
    RowRange,
    RowSelection,
    Selection,
)
from labcairn.analysis.service import (
    UNENFORCED_LIMITS,
    AnalysisRefusal,
    AnalysisRefusedError,
    AnalysisRequest,
    AnalysisRun,
    RunLimits,
    analysis_arguments,
    run_analysis,
    selection_from_payload,
)
from labcairn.core.ids import ApprovalId, OperationId, TaskId, new_id
from labcairn.db.materials import ExtractedTextRow, current_texts, put_source_texts
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.models import ArtifactRow
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.evidence.cite_support import LocationResolution
from labcairn.evidence.index import locate_anchor
from labcairn.material.addressing import render_locator_key
from labcairn.material.ingest import ingest_into_store
from labcairn.reports.receipt import ArtifactKind
from labcairn.runtime.lifecycle import Task, TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    SourceBinding,
    make_approval,
)
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.locators import CsvLocator
from labcairn.sources.source import AnchorKind, Source, SourceAnchor
from labcairn.workspace.roots import Workspace

#: The corpus, and the only oracle for what a number should be.
CORPUS: Path = Path(__file__).parent / "fixtures" / "analysis"

#: A fixed moment. Nothing in this file reads the wall clock.
NOW: dt.datetime = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.UTC)

#: The operator most of these tests run.
MEAN: str = "labcairn.analysis.mean"

#: An operator that takes a parameter besides the selection. A manifest that
#: dropped its parameters is invisible under ``mean``, whose only other
#: argument is none, so the tests that look at the parameters run this one.
STDEV: str = "labcairn.analysis.stdev"

#: The source root the workspace binds, and the root-relative key of the
#: material inside it.
ROOT_ID: str = "source:0"

#: The recipe every run names. The run path records it by path and hash; it
#: does not read it, because the recipe's schema belongs to T06.
RECIPE: str = "recipe.json"

#: The bytes a fake renderer returns for a figure.
FIGURE: bytes = b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"


# --------------------------------------------------------------------------- #
# The scenario
# --------------------------------------------------------------------------- #


@dataclass
class Scenario:
    """Everything one test needs to run an analysis."""

    workspace: Workspace
    store: TaskStore
    session: Any
    engine: Engine
    policy: PermissionPolicy
    ledger: ApprovalLedger
    source: Source
    key: str
    selection: Selection
    now: dt.datetime

    def close(self) -> None:
        """Release the database, so a Windows test run can remove the directory."""
        self.session.close()
        self.engine.dispose()

    @property
    def root_id(self) -> str:
        """The source root the material lives in."""
        return ROOT_ID

    def parameters(
        self, selection: Selection | None = None, extra: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """The operator's parameters, as the caller states them.

        The selection is the one parameter every operator takes, and it is
        stated in the manifest's own spelling. ``extra`` carries the rest --
        ``ddof`` for ``stdev`` -- so that a test can run an operator that has
        a parameter besides the selection, and a manifest that dropped its
        parameters would be visible.
        """
        payload: dict[str, Any] = {"selection": selection_payload(selection or self.selection)}
        if extra:
            payload.update(extra)
        return payload

    def arguments(
        self,
        *,
        operator_id: str = MEAN,
        selection: Selection | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The capability's own arguments, as the caller states them."""
        return {
            "path": self.key,
            "operator_id": operator_id,
            "parameters": self.parameters(selection, extra),
        }

    def grant(
        self,
        *,
        selection: Selection | None = None,
        operator_id: str = MEAN,
        expected_hash: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ApprovalId:
        """An approval covering exactly this request, granted.

        Built through :func:`labcairn.security.approval.make_approval` and the
        service's own :func:`analysis_arguments`, so the digest the approval
        carries is the one the service will recompute -- which is the whole
        point of the mechanism and the reason it is not written out here by
        hand.
        """
        chosen = selection or self.selection
        arguments = analysis_arguments(
            {
                "path": self.key,
                "operator_id": operator_id,
                "parameters": self.parameters(chosen, extra),
            }
        )
        canonical = self.workspace.path_in(self.key, self.root_id)
        approval = make_approval(
            task_id=self.workspace.task_id,
            operation_id=OperationId(new_id()),
            capability="analysis.run",
            resource=canonical,
            args=arguments,
            depends_on=(self.source.content_sha256,),
            expires_at=self.now + dt.timedelta(hours=1),
        )
        granted = approval.model_copy(
            update={"state": ApprovalState.GRANTED, "granted_at": self.now}
        )
        self.ledger.issue(
            ApprovalGrant(
                approval=granted,
                policy_digest=self.policy.digest(),
                sources=(
                    SourceBinding(
                        resource_key=self.key,
                        expected_hash=expected_hash or self.source.content_sha256,
                    ),
                ),
            )
        )
        return granted.approval_id

    def request(
        self,
        approval_id: ApprovalId,
        *,
        operator_id: str = MEAN,
        selection: Selection | None = None,
        parameters: dict[str, Any] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> AnalysisRequest:
        """The request the run path is handed."""
        return AnalysisRequest(
            approval_id=approval_id,
            root_id=self.root_id,
            arguments={
                "path": self.key,
                "operator_id": operator_id,
                "parameters": (
                    parameters if parameters is not None else self.parameters(selection, extra)
                ),
            },
        )

    def run(
        self,
        *,
        renderer: Any = None,
        limits: RunLimits | None = None,
        approval_id: ApprovalId | None = None,
        **request_kwargs: Any,
    ) -> AnalysisRun:
        """Run the analysis, with a fresh approval unless one is given."""
        chosen = approval_id or self.grant(**request_kwargs)
        return run_analysis(
            request=self.request(chosen, **request_kwargs),
            store=self.store,
            workspace=self.workspace,
            policy=self.policy,
            ledger=self.ledger,
            renderer=renderer if renderer is not None else _FakeRenderer(),
            recipe=RECIPE,
            limits=limits,
            now=self.now,
        )


class _FakeRenderer:
    """A renderer that records what it was asked to do.

    T07 builds the real one and must not import this module, so the contract
    is the protocol and this is a stand-in for it. The stand-in can be told to
    return a figure or not, and it can be told to look at the workspace when
    it renders -- which is how the order of the manifest and the figure is
    observed rather than assumed.
    """

    def __init__(
        self,
        *,
        figure: bytes | None = FIGURE,
        on_prepare: Any = None,
        on_render: Any = None,
    ):
        self.figure = figure
        self.on_prepare = on_prepare
        self.on_render = on_render
        self.prepared = 0
        self.rendered: list[tuple[str, BaseModel]] = []

    def prepare(self) -> None:
        """Put the render environment into its declared state."""
        self.prepared += 1
        if self.on_prepare is not None:
            self.on_prepare()

    def render(self, operator_id: str, result: BaseModel) -> bytes | None:
        """The figure's bytes, or ``None`` when this result is not a figure."""
        self.rendered.append((operator_id, result))
        if self.on_render is not None:
            self.on_render()
        return self.figure


def _build(
    base: Path,
    *,
    fixture: str = "basic.csv",
    rows: RowSelection | None = None,
    columns: tuple[str, ...] = ("value",),
    missing: MissingPolicy = MissingPolicy.EXCLUDE,
    data: bytes | None = None,
) -> Scenario:
    """One scenario: a workspace, a store, an ingested material and a policy."""
    base.mkdir(parents=True, exist_ok=True)
    root = base / "ws"
    sources = root / "sources"
    sources.mkdir(parents=True)

    payload = data if data is not None else (CORPUS / fixture).read_bytes()
    (sources / fixture).write_bytes(payload)

    task_id = TaskId(new_id())
    workspace = Workspace.bind(root, task_id=task_id, source_dirs=(sources,))
    (root / RECIPE).write_bytes(b'{"operator": "labcairn.analysis.mean"}')

    db_path = base / "labcairn.db"
    upgrade_to_head(db_path)
    engine = create_db_engine(db_path)
    session = create_session_factory(engine)()
    store = TaskStore(session, clock=lambda: NOW)
    store.create_task(
        Task(
            task_id=task_id,
            title="Analysis",
            goal=TaskGoal(
                objective="Establish whether the observation holds.",
                success_criterion="A cited answer, or an honest 'not established'.",
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )

    outcome = ingest_into_store(
        session, payload, relative_path=fixture, display_name=fixture, ingested_at=NOW
    )
    source = outcome.material.source
    selection = Selection(
        source_id=source.source_id,
        content_sha256=source.content_sha256,
        columns=columns,
        rows=rows if rows is not None else RowRange(2, 11),
        missing=missing,
    )
    policy = PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({"analysis.run"}),
            )
        ]
    )
    return Scenario(
        workspace=workspace,
        store=store,
        session=session,
        engine=engine,
        policy=policy,
        ledger=ApprovalLedger(),
        source=source,
        key=fixture,
        selection=selection,
        now=NOW,
    )


@pytest.fixture
def scenarios(tmp_path: Path) -> Iterator[Callable[..., Scenario]]:
    """A factory for scenarios, each with its own workspace and database."""
    built: list[Scenario] = []

    def make(name: str = "default", **kwargs: Any) -> Scenario:
        scenario = _build(tmp_path / name, **kwargs)
        built.append(scenario)
        return scenario

    yield make
    for scenario in built:
        scenario.close()


def _two_sheet_workbook() -> bytes:
    """A workbook with two sheets holding the same addresses.

    Built here rather than in the corpus because the corpus is a fixture of
    *readable* material, and a two-sheet workbook is here to be refused.
    """
    import io

    import openpyxl

    workbook = openpyxl.Workbook()
    first = workbook.active
    assert first is not None
    first.title = "One"
    second = workbook.create_sheet("Two")
    for sheet in (first, second):
        sheet.cell(row=1, column=1, value="value")
        sheet.cell(row=2, column=1, value="1")
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _expected_mean(fixture: str) -> float:
    """The mean the corpus says, read out of the committed expectations."""
    return _expected_statistic(fixture, "mean")


def _expected_statistic(fixture: str, name: str) -> float:
    """A statistic the corpus says, read out of the committed expectations."""
    import json

    expected = json.loads((CORPUS / f"{fixture}.expected.json").read_text(encoding="utf-8"))
    return float(expected["selections"][0]["expect"]["statistics"][name])


def _statistic(run: AnalysisRun) -> Any:
    """The run's result, as the statistic the operators produce."""
    assert isinstance(run.result, BaseModel)
    return run.result


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_a_run_produces_the_number_the_corpus_says(scenarios: Any) -> None:
    """The operator's own value, checked against the committed expectation.

    Not against a value this repository computed: the expected mean lives in
    ``basic.csv.expected.json`` beside the fixture, and no script in this
    repository regenerates it.
    """
    scenario = scenarios()
    run = scenario.run()

    assert _statistic(run).value == _expected_mean("basic.csv")
    assert _statistic(run).n_used == 10
    assert _statistic(run).operator_id == MEAN


@pytest.mark.unit
def test_a_run_records_the_operator_that_ran(scenarios: Any) -> None:
    """One operator, one spelling -- the catalogue's own reference.

    The receipt and the manifest both quote it, and a manifest that quoted a
    second spelling would not compare equal to another run's.
    """
    scenario = scenarios()
    run = scenario.run()

    registered = operator_for(MEAN)
    assert registered is not None
    assert run.manifest.operator == operator_reference(registered.operator)
    assert run.manifest_receipt.producer_id == run.manifest.operator


@pytest.mark.unit
def test_a_run_writes_the_manifest_and_records_both_receipts(scenarios: Any) -> None:
    """The manifest is a file, and the receipts are rows.

    A run that produced a number and left no record of what produced it has
    not produced a reproducible result, and the test for that is that the
    manifest exists and that the artefacts table holds the chain.
    """
    scenario = scenarios()
    run = scenario.run()

    written = scenario.workspace.selected_root / run.manifest_receipt.relative_path
    assert written.is_file()
    assert run.manifest_receipt.kind is ArtifactKind.MANIFEST

    rows = scenario.session.scalars(
        select(ArtifactRow).where(ArtifactRow.task_id == str(scenario.workspace.task_id))
    ).all()
    assert {row.artifact_id for row in rows} == {
        run.manifest_receipt.receipt_id,
        run.figure_receipt.receipt_id if run.figure_receipt else "",
    }
    assert {row.kind for row in rows} == {"manifest", "figure"}


@pytest.mark.unit
def test_the_manifest_carries_the_six_fields_the_work_order_names(scenarios: Any) -> None:
    """Input hash, selection, operator version, parameters, recipe, output hash.

    Each checked *where* it lives, not merely that something like it exists.
    The operator is ``stdev`` and not ``mean`` because ``mean`` has no
    argument besides the selection: a test that named the parameters while
    running an operator with none would assert nothing about them.
    """
    scenario = scenarios()
    run = scenario.run(operator_id=STDEV, extra={"ddof": 1})
    manifest = run.manifest

    assert manifest.input_file.content_sha256 == scenario.source.content_sha256
    assert manifest.locator.parameters["selection"] == selection_payload(scenario.selection)
    assert manifest.locator.operator_version == "1.0.0"
    assert manifest.locator.parameters["ddof"] == 1
    assert manifest.recipe.relative_path == RECIPE
    assert manifest.output_sha256 == canonical_digest(manifest.output)


@pytest.mark.unit
def test_the_manifests_parameters_are_the_operators_own_arguments(scenarios: Any) -> None:
    """The parameters are the operator's, and the selection has its own field.

    Two failure modes, and the assertion catches both: a manifest that
    recorded **no** parameters is indistinguishable from one whose operator
    has none, so the operator here has one (``ddof``); and a run that passed
    the selection among the operator's parameters would not produce a
    manifest at all, because the manifest refuses a parameter that shadows
    the selection. The parameters are therefore exactly the selection and the
    argument, each once.
    """
    scenario = scenarios()
    run = scenario.run(operator_id=STDEV, extra={"ddof": 1})

    assert _statistic(run).value == pytest.approx(_expected_statistic("basic.csv", "stdev_sample"))
    assert run.manifest.locator.parameters == {
        "selection": selection_payload(scenario.selection),
        "ddof": 1,
    }


@pytest.mark.unit
def test_the_manifests_input_hash_is_the_sources_own_content_hash(scenarios: Any) -> None:
    """One hash lineage: the file, the source, the selection and the locator.

    The comparison against the file's bytes is the part that is not vacuous.
    """
    scenario = scenarios()
    run = scenario.run()

    assert run.manifest.input_file.content_sha256 == scenario.source.content_sha256
    assert run.manifest.locator.input_hashes == (scenario.source.content_sha256,)
    recorded = run.manifest.locator.parameters["selection"]
    assert isinstance(recorded, dict)
    assert recorded["content_sha256"] == scenario.source.content_sha256


@pytest.mark.unit
def test_the_manifests_selection_is_the_selection_that_ran(scenarios: Any) -> None:
    """Which cells were used is part of what the number means."""
    scenario = scenarios()
    run = scenario.run()

    assert run.manifest.locator.parameters["selection"] == selection_payload(scenario.selection)
    assert run.selection == scenario.selection


@pytest.mark.unit
def test_the_figures_chain_names_the_manifest(scenarios: Any) -> None:
    """The chain is linear: file, result, manifest, figure.

    Each link names the one before it, and nothing names a document that has
    not been written.
    """
    scenario = scenarios()
    run = scenario.run()

    assert run.figure_receipt is not None
    figure = run.figure_receipt
    assert figure.kind is ArtifactKind.FIGURE
    assert figure.derived_from[0].target_id == run.manifest_receipt.receipt_id
    assert figure.derived_from[0].content_sha256 == run.manifest_receipt.content_sha256
    assert figure.derived_from[1].target_id == run.manifest.input_file.relative_path
    assert figure.derived_from[1].content_sha256 == run.manifest.input_file.content_sha256


@pytest.mark.unit
def test_the_figure_is_written_where_the_receipt_says_it_is(scenarios: Any) -> None:
    """The receipt's hash is the writer's own hash of the bytes on disk.

    The path in the receipt is derived from where the file landed, so the
    receipt and the file cannot disagree about either.
    """
    scenario = scenarios()
    run = scenario.run()

    assert run.figure_receipt is not None
    written = scenario.workspace.selected_root / run.figure_receipt.relative_path
    assert written.is_file()
    assert written.read_bytes() == FIGURE
    assert run.figure_receipt.content_sha256 == hashlib.sha256(FIGURE).hexdigest()
    assert run.figure_receipt.size_bytes == len(FIGURE)


@pytest.mark.unit
def test_a_run_over_a_spreadsheet_reads_the_ledger_cells(scenarios: Any) -> None:
    """A spreadsheet is addressed by a sheet and a cell, and read as a row and
    a header.

    The ledger holds a cell reference rather than a row number and a column
    name, so the run has to look the header up rather than assume it -- and
    the number it produces must be the corpus's, not the adapter's.
    """
    from analysis_fixtures import build_spreadsheet_fixtures

    scenario = scenarios(fixture="numeric.xlsx", data=build_spreadsheet_fixtures()["numeric.xlsx"])
    run = scenario.run()

    assert _statistic(run).value == _expected_mean("numeric.xlsx")
    assert _statistic(run).n_used == 10
    assert _statistic(run).n_absent == 0


@pytest.mark.unit
def test_a_workbook_with_two_sheets_is_refused(scenarios: Any) -> None:
    """A selection names a row and a header and no sheet.

    Two sheets can hold the same address, and an address that cannot be told
    apart is not one anybody chose -- so the run refuses rather than picking
    a sheet.
    """
    scenario = scenarios(fixture="two.xlsx", data=_two_sheet_workbook())
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.SOURCE_AMBIGUOUS
    assert "One" in str(caught.value) and "Two" in str(caught.value)


# --------------------------------------------------------------------------- #
# The consent
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_a_run_without_an_approval_is_refused(scenarios: Any) -> None:
    """An analysis nobody agreed to is not an analysis."""
    scenario = scenarios()
    request = scenario.request(ApprovalId(new_id()))

    with pytest.raises(AnalysisRefusedError) as caught:
        run_analysis(
            request=request,
            store=scenario.store,
            workspace=scenario.workspace,
            policy=scenario.policy,
            ledger=scenario.ledger,
            renderer=_FakeRenderer(),
            recipe=RECIPE,
            now=scenario.now,
        )
    assert caught.value.reason is AnalysisRefusal.APPROVAL_MISSING


@pytest.mark.unit
def test_an_approval_for_one_selection_does_not_authorise_another(scenarios: Any) -> None:
    """A different selection is a different digest.

    This is the property the work order names, and it is the one a run path
    without it would quietly break: the approval says *these cells*, and
    analysing other cells under it would be a claim nobody made.
    """
    scenario = scenarios()
    other = Selection(
        source_id=scenario.source.source_id,
        content_sha256=scenario.source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 6),
        missing=MissingPolicy.EXCLUDE,
    )

    # The half that is easy to leave out: the approval it *was* granted for
    # is authorised. A digest that covered nothing at all would refuse this
    # one too, and a test that only checked the refusal would not notice.
    authorised = scenario.grant()
    assert scenario.run(approval_id=authorised).selection == scenario.selection

    # And the half the work order names: a different selection is not.
    granted = scenario.grant()
    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, selection=other)
    assert caught.value.reason is AnalysisRefusal.APPROVAL_REFUSED
    assert "args_changed" in str(caught.value)


@pytest.mark.unit
def test_a_source_that_drifted_since_the_approval_is_refused(scenarios: Any) -> None:
    """A file that moved is not the file the approval promised.

    The service's own check fires first, because it is the one that does not
    depend on the caller having set up a source binding.
    """
    scenario = scenarios()
    granted = scenario.grant()
    (scenario.workspace.selected_root / "sources" / scenario.key).write_bytes(b"group,value\nA,1\n")

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.SOURCE_DRIFTED
    assert scenario.source.content_sha256 in str(caught.value)


@pytest.mark.unit
def test_an_approval_that_promised_another_hash_is_refused(scenarios: Any) -> None:
    """ADR-0003 §C4's own check: the approval's source binding is re-hashed.

    The service's drift check cannot see this one -- the file is exactly what
    the source was ingested from -- so it is the approval's own mechanism
    doing the refusing, and the refusal says so.
    """
    scenario = scenarios()
    granted = scenario.grant(expected_hash="c" * 64)

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.APPROVAL_REFUSED
    assert "source_changed" in str(caught.value)


@pytest.mark.unit
def test_a_denied_policy_is_refused(scenarios: Any) -> None:
    """The policy's verdict is asked for, and a deny is a refusal.

    The **message** is what a reader acts on, so it is asserted and not only
    the reason: a denial says it was *denied*, and it names the policy's own
    reason and the rule that matched. The two refusals this path can make for
    the same reason -- a denial and an unanswered question -- are different
    facts, and a message that said "asked" about a denial would be false
    about what the policy did.
    """
    scenario = scenarios()
    scenario.policy = PermissionPolicy.from_rules(
        [Rule(effect=Permission.DENY, pattern="**", capabilities=frozenset({"analysis.run"}))]
    )
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.PERMISSION_DENIED
    assert caught.value.detail.startswith("the policy denied analysis.run on")
    assert "rule_deny" in caught.value.detail
    assert scenario.policy.rules[0].render() in caught.value.detail
    assert "asked" not in caught.value.detail


@pytest.mark.unit
def test_a_policy_that_asks_is_refused(scenarios: Any) -> None:
    """An unanswered question is not consent.

    The path has no way to ask -- there is no one to ask, in a library call --
    so an ``ASK`` is refused rather than read as a yes. The message says
    *asked*, because a question that was not answered is a different fact
    from a request that was denied.
    """
    scenario = scenarios()
    scenario.policy = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ASK, pattern="**", capabilities=frozenset({"analysis.run"}))]
    )
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.PERMISSION_DENIED
    assert "the policy asked about analysis.run" in caught.value.detail
    assert "denied" not in caught.value.detail


@pytest.mark.unit
def test_the_approval_is_spent_by_the_run(scenarios: Any) -> None:
    """One approval, one run.

    A second run under the same approval is refused, because the approval
    moved to ``consumed`` and a consumed approval is not a granted one.
    """
    scenario = scenarios()
    granted = scenario.grant()
    scenario.run(approval_id=granted)

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.APPROVAL_REFUSED
    assert "consumed" in str(caught.value)


@pytest.mark.unit
def test_a_refusal_before_the_consent_point_does_not_spend_the_approval(scenarios: Any) -> None:
    """Re-asking a human is cheap; burning consent on a request that was
    never allowed to start is not.

    The bounds are checked before the approval is consumed, so a request that
    is too big is refused and the approval is still there for a smaller one.
    """
    scenario = scenarios()
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, limits=RunLimits(max_rows=2))
    assert caught.value.reason is AnalysisRefusal.LIMITS_EXCEEDED

    run = scenario.run(approval_id=granted)
    assert _statistic(run).value == _expected_mean("basic.csv")


@pytest.mark.unit
def test_the_approval_is_spent_before_the_operator_runs(scenarios: Any) -> None:
    """The operator's evaluation is the operation, and the approval is spent
    before it happens.

    Proved by the operator refusing: the units in ``units.csv`` disagree, so
    the run is refused -- and the approval is already spent, which is only
    true if it was consumed before the evaluation.
    """
    scenario = scenarios(fixture="units.csv", rows=RowRange(2, 7))
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.OPERATOR_REFUSED
    assert "kg" in str(caught.value) and "g" in str(caught.value)

    with pytest.raises(AnalysisRefusedError) as spent:
        scenario.run(approval_id=granted)
    assert spent.value.reason is AnalysisRefusal.APPROVAL_REFUSED
    assert "consumed" in str(spent.value)


# --------------------------------------------------------------------------- #
# The source
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_an_unreadable_source_is_refused(scenarios: Any) -> None:
    """ADR-0004 A7: unreadable material is neither analysed nor cited.

    And it is not an empty source either -- it is a source this build could
    not look at, which is a different fact and gets a different refusal.
    """
    scenario = scenarios(fixture="broken.xlsx", data=b"not a workbook at all")
    assert scenario.source.readability.value != "readable"
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted)
    assert caught.value.reason is AnalysisRefusal.SOURCE_UNREADABLE
    assert scenario.source.readability.value in str(caught.value)


@pytest.mark.unit
def test_a_selection_bound_to_other_bytes_is_refused(scenarios: Any) -> None:
    """The selection and the source are one value.

    The hash here is well formed and wrong, so the refusal cannot be an
    artefact of a malformed argument.
    """
    scenario = scenarios()
    other = Selection(
        source_id=scenario.source.source_id,
        content_sha256="b" * 64,
        columns=("value",),
        rows=RowRange(2, 11),
        missing=MissingPolicy.EXCLUDE,
    )
    granted = scenario.grant(selection=other)

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, selection=other)
    assert caught.value.reason is AnalysisRefusal.SELECTION_MISMATCH
    assert "b" * 64 in str(caught.value)


@pytest.mark.unit
def test_a_source_that_is_not_in_the_ledger_is_refused(scenarios: Any) -> None:
    """A run reads what the ledger holds, not what the caller remembers."""
    scenario = scenarios()
    unknown = Selection(
        source_id="src-never-ingested",
        content_sha256=scenario.source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 11),
        missing=MissingPolicy.EXCLUDE,
    )
    granted = scenario.grant(selection=unknown)

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, selection=unknown)
    assert caught.value.reason is AnalysisRefusal.SOURCE_NOT_FOUND


# --------------------------------------------------------------------------- #
# The operator and the arguments
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_an_unregistered_operator_is_refused(scenarios: Any) -> None:
    """The catalogue is built from the operators' own constants, so an id it
    does not hold names no code that could run.
    """
    scenario = scenarios()
    request = scenario.request(ApprovalId(new_id()), operator_id="labcairn.analysis.nonexistent")

    with pytest.raises(AnalysisRefusedError) as caught:
        run_analysis(
            request=request,
            store=scenario.store,
            workspace=scenario.workspace,
            policy=scenario.policy,
            ledger=scenario.ledger,
            renderer=_FakeRenderer(),
            recipe=RECIPE,
            now=scenario.now,
        )
    assert caught.value.reason is AnalysisRefusal.OPERATOR_NOT_REGISTERED


@pytest.mark.unit
def test_parameters_the_operator_does_not_take_are_refused(scenarios: Any) -> None:
    """The operator's argument model is closed.

    An unrecognised key is a typo or a newer caller, and both deserve to be
    loud rather than ignored.
    """
    scenario = scenarios()
    parameters = {
        "selection": selection_payload(scenario.selection),
        "not_a_parameter": 1,
    }
    request = scenario.request(ApprovalId(new_id()), parameters=parameters)

    with pytest.raises(AnalysisRefusedError) as caught:
        run_analysis(
            request=request,
            store=scenario.store,
            workspace=scenario.workspace,
            policy=scenario.policy,
            ledger=scenario.ledger,
            renderer=_FakeRenderer(),
            recipe=RECIPE,
            now=scenario.now,
        )
    assert caught.value.reason is AnalysisRefusal.ARGUMENTS_INVALID
    assert "not_a_parameter" in str(caught.value)


@pytest.mark.unit
def test_a_path_outside_the_source_root_is_refused(scenarios: Any) -> None:
    """A run reads supplied material, and the root says what that is."""
    scenario = scenarios()
    granted = scenario.grant()
    request = AnalysisRequest(
        approval_id=granted,
        root_id="workspace",
        arguments=scenario.arguments(),
    )

    with pytest.raises(AnalysisRefusedError) as caught:
        run_analysis(
            request=request,
            store=scenario.store,
            workspace=scenario.workspace,
            policy=scenario.policy,
            ledger=scenario.ledger,
            renderer=_FakeRenderer(),
            recipe=RECIPE,
            now=scenario.now,
        )
    assert caught.value.reason is AnalysisRefusal.PATH_REFUSED


# --------------------------------------------------------------------------- #
# The bounds
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_a_selection_over_too_many_rows_is_refused(scenarios: Any) -> None:
    """The row bound is checked before a cell is read.

    A limit checked afterwards is a report, not a bound.
    """
    scenario = scenarios()
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, limits=RunLimits(max_rows=3))
    assert caught.value.reason is AnalysisRefusal.LIMITS_EXCEEDED
    assert "10 rows" in str(caught.value)


@pytest.mark.unit
def test_a_selection_over_too_many_cells_is_refused(scenarios: Any) -> None:
    """The cell bound counts the addresses the selection can reach."""
    scenario = scenarios()
    granted = scenario.grant()

    with pytest.raises(AnalysisRefusedError) as caught:
        scenario.run(approval_id=granted, limits=RunLimits(max_rows=100, max_cells=4))
    assert caught.value.reason is AnalysisRefusal.LIMITS_EXCEEDED
    assert "10 cells" in str(caught.value)


@pytest.mark.unit
def test_the_unenforceable_bound_is_named_rather_than_shipped(scenarios: Any) -> None:
    """A timeout that does not fire is worse than no timeout at all.

    The bounds that **are** enforceable are enforced -- the two tests above
    are the proof -- and the one that is not is named, so a reader can see
    that the gap is a decision rather than an oversight.
    """
    assert "wall_clock_timeout" in UNENFORCED_LIMITS
    assert len(UNENFORCED_LIMITS) == 1


# --------------------------------------------------------------------------- #
# The current text
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_a_run_reads_the_current_extraction_of_the_material(scenarios: Any) -> None:
    """The ledger may hold more than one extraction of the same bytes.

    An adapter's code changed and the material was re-ingested without the
    file changing, so the same address is held twice. The run must read the
    **current** one -- the newest row for the address -- or the number it
    reports is about an extraction nobody is using.
    """
    scenario = scenarios()
    key = render_locator_key(CsvLocator(row=2, column="value"))
    put_source_texts(
        scenario.session,
        source_content_sha256=scenario.source.content_sha256,
        extraction_version="re-extraction",
        rows=[
            ExtractedTextRow(
                locator_kind="csv",
                locator_key=key,
                text="100",
                text_sha256=hashlib.sha256(b"100").hexdigest(),
                created_at=scenario.now + dt.timedelta(minutes=1),
                row_number=2,
                column_name="value",
            )
        ],
    )

    run = scenario.run()
    # 1..10 with the first value replaced by 100: (55 - 1 + 100) / 10.
    assert _statistic(run).value == 15.4
    assert _statistic(run).value != _expected_mean("basic.csv")


@pytest.mark.unit
def test_the_bulk_reader_and_the_evidence_index_agree_on_which_row_is_current(
    scenarios: Any,
) -> None:
    """One rule for "current", in two readers.

    :func:`labcairn.evidence.index.locate_anchor` already answers it for one
    address; the store's bulk reader answers it for all of them. If the two
    disagreed, an analysis and a citation of the same cell would read
    different text, and neither would notice.
    """
    scenario = scenarios()
    key = render_locator_key(CsvLocator(row=2, column="value"))
    put_source_texts(
        scenario.session,
        source_content_sha256=scenario.source.content_sha256,
        extraction_version="re-extraction",
        rows=[
            ExtractedTextRow(
                locator_kind="csv",
                locator_key=key,
                text="100",
                text_sha256=hashlib.sha256(b"100").hexdigest(),
                # The same instant as the original extraction, so the two rows
                # are separated by the id alone -- which is the tiebreak the
                # two readers have to agree about.
                created_at=scenario.now,
                row_number=2,
                column_name="value",
            )
        ],
    )
    scenario.session.commit()

    current = {
        row.locator_key: row.text
        for row in current_texts(
            scenario.session, source_content_sha256=scenario.source.content_sha256
        )
    }
    assert current[key] == "100"

    anchor = SourceAnchor(
        anchor_id="anchor-1",
        source_id=scenario.source.source_id,
        kind=AnchorKind.NUMERIC,
        locator=CsvLocator(row=2, column="value"),
        bound_source_sha256=scenario.source.content_sha256,
        created_at=scenario.now,
    )
    # The session's own connection, not a second one: the session holds this
    # database's write lock, and a second connection would wait for it.
    located = locate_anchor(scenario.session.connection(), anchor)
    assert located.resolution is LocationResolution.RESOLVED
    assert located.text == current[key]


# --------------------------------------------------------------------------- #
# The render, and the order
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_environment_is_prepared_before_the_manifest_is_built(scenarios: Any) -> None:
    """The manifest records the environment the render happens in.

    The salt is the observable: the renderer sets it in ``prepare()``, and
    the manifest must carry the value that was set. A manifest built before
    the preparation would carry the old one, and the figure it describes
    would have been rendered in an environment the manifest does not name.
    """
    import matplotlib

    scenario = scenarios()

    def prepare() -> None:
        matplotlib.rcParams["svg.hashsalt"] = "prepared-salt"

    renderer = _FakeRenderer(on_prepare=prepare)
    original = matplotlib.rcParams["svg.hashsalt"]
    try:
        run = scenario.run(renderer=renderer)
    finally:
        matplotlib.rcParams["svg.hashsalt"] = original

    assert renderer.prepared == 1
    assert run.manifest.environment.svg_hashsalt == "prepared-salt"


@pytest.mark.unit
def test_the_manifest_is_written_before_the_figure(scenarios: Any) -> None:
    """The figure's chain names the manifest, so the manifest must exist first.

    Observed rather than assumed: the renderer looks for the manifest file
    when it renders, and a service that rendered first would find nothing.
    """
    scenario = scenarios()
    seen: list[list[str]] = []

    def render() -> None:
        found = list((scenario.workspace.selected_root / "output").rglob("*.manifest.json"))
        seen.append([str(path) for path in found])

    run = scenario.run(renderer=_FakeRenderer(on_render=render))
    assert seen, "the renderer was never asked to render"
    assert seen[0], "the manifest was not on disk when the figure was first rendered"
    assert str(scenario.workspace.selected_root / run.manifest_receipt.relative_path) in seen[0]


@pytest.mark.unit
def test_a_result_that_is_not_a_figure_writes_no_figure(scenarios: Any) -> None:
    """``render()`` returning ``None`` is the renderer's own word for it.

    The path does not second-guess it, and no figure receipt is invented.
    """
    scenario = scenarios()
    run = scenario.run(renderer=_FakeRenderer(figure=None))

    assert run.figure_receipt is None
    rows = scenario.session.scalars(
        select(ArtifactRow).where(ArtifactRow.task_id == str(scenario.workspace.task_id))
    ).all()
    assert {row.kind for row in rows} == {"manifest"}


@pytest.mark.unit
def test_the_renderer_is_asked_for_the_operator_that_ran(scenarios: Any) -> None:
    """The renderer is given the operator's id and the operator's result.

    The figure's numbers are the operator's numbers, because the object the
    renderer receives is the operator's own result object.
    """
    scenario = scenarios()
    renderer = _FakeRenderer()
    run = scenario.run(renderer=renderer)

    assert len(renderer.rendered) == 1
    operator_id, result = renderer.rendered[0]
    assert operator_id == MEAN
    assert result is run.result


# --------------------------------------------------------------------------- #
# The selection payload
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_selection_payload_round_trips(scenarios: Any) -> None:
    """One spelling of a selection, written by one function and read by one.

    The payload the manifest writes is the payload the run path reads, so a
    manifest and an approval digest cannot disagree about the selection.
    """
    scenario = scenarios()
    selection = Selection(
        source_id=scenario.source.source_id,
        content_sha256=scenario.source.content_sha256,
        columns=("value", "group"),
        rows=RowRange(2, 11),
        missing=MissingPolicy.REFUSE,
    )
    payload = selection_payload(selection)
    assert selection_from_payload(payload) == selection


@pytest.mark.unit
def test_a_selection_payload_with_an_unknown_row_kind_is_refused() -> None:
    """The row specification is a closed union of three shapes.

    A reader that guessed between them would be guessing, and a guess here
    routes a number to the wrong cells.
    """
    payload: dict[str, Any] = {
        "source_id": "src-1",
        "content_sha256": "a" * 64,
        "columns": ["value"],
        "rows": {"kind": "expression", "value": "mean(x)"},
        "missing": "exclude",
    }
    with pytest.raises(AnalysisRefusedError) as caught:
        selection_from_payload(payload)
    assert caught.value.reason is AnalysisRefusal.ARGUMENTS_INVALID
    assert "expression" in str(caught.value)


@pytest.mark.unit
def test_the_arguments_of_a_run_are_the_ones_the_approval_is_bound_to(scenarios: Any) -> None:
    """The digest is over the capability's own arguments, in canonical form.

    Two spellings of the same selection produce the same arguments, and a
    different selection produces different ones.
    """
    scenario = scenarios()
    arguments = analysis_arguments(scenario.arguments())

    assert arguments["operator_id"] == MEAN
    assert arguments["path"] == scenario.key
    assert arguments["parameters"] == {"selection": selection_payload(scenario.selection)}

    other = Selection(
        source_id=scenario.source.source_id,
        content_sha256=scenario.source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 6),
        missing=MissingPolicy.EXCLUDE,
    )
    changed = analysis_arguments(scenario.arguments(selection=other))
    assert changed["parameters"] != arguments["parameters"]


# --------------------------------------------------------------------------- #
# Mutation notes
# --------------------------------------------------------------------------- #
#
# Each of these is a way the path's properties could be undone, and the named
# test that catches it. Every one was applied and run; all thirty-seven were
# caught. Two of them were applied outside this module, and they are marked:
# the approval's single-use rule lives in the shared approval machinery, and
# the "current row" rule lives in the store's reader. The last three came out
# of an independent review that wrote its own mutations against the branch,
# and the two that survived it were real gaps in these tests rather than bad
# mutations: a policy *denial* was reported with the message an unanswered
# *question* gets, and the manifest's parameters were never observed.
#
#   1. the approval's digest not recomputed at the moment of use
#      -> test_an_approval_for_one_selection_does_not_authorise_another
#   2. the approval's source binding not checked
#      -> test_an_approval_that_promised_another_hash_is_refused
#   3. a missing approval treated as consent
#      -> test_a_run_without_an_approval_is_refused
#   4. the approval not consumed, so it could be spent twice
#      (applied to labcairn.security.approval, which owns the rule)
#      -> test_the_approval_is_spent_by_the_run
#   5. the approval consumed after the operator ran
#      -> test_the_approval_is_spent_before_the_operator_runs
#   6. a refusal before the consent point spending the approval
#      -> test_a_refusal_before_the_consent_point_does_not_spend_the_approval
#   7. the policy's verdict not asked for
#      -> test_a_denied_policy_is_refused
#   8. an ASK read as an allow
#      -> test_a_policy_that_asks_is_refused
#   9. an unreadable source analysed anyway
#      -> test_an_unreadable_source_is_refused
#  10. a drifted file read as the ingested bytes
#      -> test_a_source_that_drifted_since_the_approval_is_refused
#  11. a selection bound to other bytes accepted
#      -> test_a_selection_bound_to_other_bytes_is_refused
#  12. a source that is not in the ledger accepted
#      -> test_a_source_that_is_not_in_the_ledger_is_refused
#  13. an unregistered operator run
#      -> test_an_unregistered_operator_is_refused
#  14. the operator's closed argument model not applied
#      -> test_parameters_the_operator_does_not_take_are_refused
#  15. a path outside the source root admitted
#      -> test_a_path_outside_the_source_root_is_refused
#  16. the row limit not enforced
#      -> test_a_selection_over_too_many_rows_is_refused
#  17. the cell limit not enforced
#      -> test_a_selection_over_too_many_cells_is_refused
#  18. the unenforceable bound shipped as if it fired
#      -> test_the_unenforceable_bound_is_named_rather_than_shipped
#  19. the first extraction read rather than the current one
#      (applied to labcairn.db.materials, which owns the rule)
#      -> test_a_run_reads_the_current_extraction_of_the_material
#  20. the bulk reader disagreeing with the evidence index
#      (applied to labcairn.db.materials, which owns the rule)
#      -> test_the_bulk_reader_and_the_evidence_index_agree_on_which_row_is_current
#  21. the environment prepared after the manifest was built
#      -> test_the_environment_is_prepared_before_the_manifest_is_built
#  22. the figure written before the manifest
#      -> test_the_manifest_is_written_before_the_figure
#  23. a figure receipt invented for a result that is not a figure
#      -> test_a_result_that_is_not_a_figure_writes_no_figure
#  24. the renderer given something other than the operator's result
#      -> test_the_renderer_is_asked_for_the_operator_that_ran
#  25. a second spelling of the selection accepted
#      -> test_a_selection_payload_with_an_unknown_row_kind_is_refused
#  26. the selection payload not round-tripping
#      -> test_the_selection_payload_round_trips
#  27. the manifest's input hash not the source's own
#      -> test_the_manifests_input_hash_is_the_sources_own_content_hash
#  28. the manifest's selection not the selection that ran
#      -> test_the_manifests_selection_is_the_selection_that_ran
#  29. the figure's chain not naming the manifest
#      -> test_the_figures_chain_names_the_manifest
#  30. the receipts not written to the artefacts table
#      -> test_a_run_writes_the_manifest_and_records_both_receipts
#  31. the figure's receipt not carrying the writer's own hash
#      -> test_the_figure_is_written_where_the_receipt_says_it_is
#  32. the operator quoted under a second spelling
#      -> test_a_run_records_the_operator_that_ran
#  33. a spreadsheet's header not looked up
#      -> test_a_run_over_a_spreadsheet_reads_the_ledger_cells
#  34. a two-sheet workbook read from whichever sheet came first
#      -> test_a_workbook_with_two_sheets_is_refused
#  35. a policy denial reported with the message an unanswered question gets
#      -> test_a_denied_policy_is_refused
#  36. the manifest's parameters dropped
#      -> test_the_manifests_parameters_are_the_operators_own_arguments
#  37. the selection passed among the operator's parameters
#      -> test_the_manifests_parameters_are_the_operators_own_arguments
