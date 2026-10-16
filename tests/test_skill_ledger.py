"""The ledger: what makes an artifact *this run's*, and what catches a swap.

Two independent properties are tested here, and the distinction matters because
neither substitutes for the other:

* **provenance at write time** — an artifact is only recorded with a lineage
  matching the digests the orchestrator actually handed over;
* **integrity at read time** — a recorded artifact is re-hashed on every read, so
  replacing it *afterwards* is caught even though the write-time checks already
  ran and passed.

A third property falls out of the implementation and is asserted rather than
assumed: a recorded entry is **frozen**. Mutation of a stored object is refused
by the type, and the digest check covers the case where the whole entry is
replaced with a new one carrying the old digest — which is what an attacker (or a
buggy migration) with access to the ledger would actually do.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest
from test_skill_support import (
    DATA_SHA,
    PAPER_SHA,
    StageBlockedError,
    build_inventory,
    build_retrieved,
    make_anchor,
    make_objective,
    make_orchestrator,
)

from labcairn.core.schema import LabCairnModel
from labcairn.skills import (
    ArtifactKind,
    ArtifactLedger,
    ArtifactSubstitutedError,
    ArtifactTypeError,
    InventoryAnchor,
    InventoryMaterial,
    LineageError,
    Orchestrator,
    SourceInventory,
    StageContractError,
    StageName,
    artifact_digest,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
LINEAGE = ("a" * 64,)
OTHER_LINEAGE = ("b" * 64,)


def _ledger_with_objective() -> ArtifactLedger:
    ledger = ArtifactLedger()
    ledger.record(
        ArtifactKind.RESEARCH_OBJECTIVE,
        StageName.INTAKE,
        make_objective("t"),
        produced_by=StageName.INTAKE,
        now=NOW,
    )
    return ledger


def _substitute(ledger: ArtifactLedger, stage: StageName, artifact: LabCairnModel) -> None:
    """Replace a ledger entry, keeping its recorded digest.

    ``RecordedArtifact`` is frozen, so the entry has to be swapped wholesale.
    That is the realistic attack: the row's digest column still says what it
    always said, and only re-hashing the object catches it.
    """
    recorded = ledger.by_stage[stage]
    ledger.by_stage[stage] = dataclasses.replace(recorded, artifact=artifact)


class TestDigests:
    def test_a_digest_is_deterministic(self) -> None:
        assert artifact_digest(build_inventory(LINEAGE)) == artifact_digest(
            build_inventory(LINEAGE)
        )

    def test_a_digest_changes_when_the_content_changes(self) -> None:
        one = build_inventory(
            LINEAGE, materials=(("paper.pdf", PAPER_SHA, True), ("data.csv", DATA_SHA, True))
        )
        two = build_inventory(LINEAGE, materials=(("paper.pdf", PAPER_SHA, True),))
        assert artifact_digest(one) != artifact_digest(two)

    def test_a_digest_changes_when_only_the_lineage_changes(self) -> None:
        """Same content, different ancestors, different digest.

        A digest that ignored ``derived_from`` would let an unsupported claim
        borrow a supported claim's identity, which is the whole reason the
        lineage is inside the hashed payload.
        """
        assert artifact_digest(build_inventory(LINEAGE)) != artifact_digest(
            build_inventory(OTHER_LINEAGE)
        )

    def test_the_digest_is_lowercase_hex(self) -> None:
        digest = artifact_digest(build_inventory(LINEAGE))
        assert len(digest) == 64
        assert digest == digest.lower()
        assert all(char in "0123456789abcdef" for char in digest)


class TestRecording:
    def test_recording_computes_and_stores_the_digest(self) -> None:
        ledger = _ledger_with_objective()
        recorded = ledger.load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)
        assert recorded.digest == artifact_digest(recorded.artifact)
        assert recorded.produced_by is StageName.INTAKE

    def test_the_wrong_model_for_a_port_is_refused(self) -> None:
        with pytest.raises(ArtifactTypeError, match="declares SourceInventory"):
            ArtifactLedger().record(
                ArtifactKind.SOURCE_INVENTORY,
                StageName.INVENTORY,
                make_objective("t"),
                produced_by=StageName.INVENTORY,
                now=NOW,
            )

    def test_a_naive_timestamp_is_refused(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ArtifactLedger().record(
                ArtifactKind.RESEARCH_OBJECTIVE,
                StageName.INTAKE,
                make_objective("t"),
                produced_by=StageName.INTAKE,
                now=datetime(2026, 3, 1),  # noqa: DTZ001 - deliberately naive
            )

    def test_a_recorded_entry_is_frozen(self) -> None:
        """Mutation of the stored object is refused by the type itself."""
        ledger = _ledger_with_objective()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ledger.by_stage[StageName.INTAKE].digest = "f" * 64  # type: ignore[misc]

    def test_loading_an_absent_stage_is_a_key_error(self) -> None:
        with pytest.raises(KeyError, match="no artifact recorded"):
            ArtifactLedger().load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)

    def test_loading_with_the_wrong_kind_is_refused(self) -> None:
        with pytest.raises(ArtifactTypeError, match=r"holds 'research_objective'"):
            _ledger_with_objective().load(StageName.INTAKE, ArtifactKind.SOURCE_INVENTORY)

    def test_history_is_append_only_across_a_re_record(self) -> None:
        """A reader must still be able to ask what a stage produced the first time."""
        ledger = _ledger_with_objective()
        first = ledger.by_stage[StageName.INTAKE].digest
        ledger.record(
            ArtifactKind.RESEARCH_OBJECTIVE,
            StageName.INTAKE,
            make_objective("t", objective="A different objective for the same task."),
            produced_by=StageName.INTAKE,
            now=NOW,
        )
        assert len(ledger.history) == 2
        assert ledger.history[0].digest == first
        assert ledger.by_stage[StageName.INTAKE].digest != first


class TestSubstitutionDetection:
    """The read-time guard. Write-time checks cannot do this job."""

    def _two_stages(self) -> ArtifactLedger:
        ledger = _ledger_with_objective()
        ledger.record(
            ArtifactKind.SOURCE_INVENTORY,
            StageName.INVENTORY,
            build_inventory(LINEAGE),
            produced_by=StageName.INVENTORY,
            now=NOW,
        )
        return ledger

    def test_an_untouched_ledger_loads(self) -> None:
        recorded = self._two_stages().load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
        assert isinstance(recorded.artifact, SourceInventory)

    def test_swapping_the_stored_object_is_caught_on_read(self) -> None:
        """Well-formed, internally consistent, and not what was verified."""
        ledger = self._two_stages()
        _substitute(
            ledger,
            StageName.INVENTORY,
            build_inventory(
                LINEAGE,
                materials=(
                    ("paper.pdf", PAPER_SHA, True),
                    ("other.csv", DATA_SHA, True),
                    ("third.pdf", "e" * 64, True),
                ),
            ),
        )
        with pytest.raises(ArtifactSubstitutedError, match="was substituted after it was verified"):
            ledger.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)

    def test_verify_all_reports_every_substitution(self) -> None:
        ledger = self._two_stages()
        ledger.record(
            ArtifactKind.RETRIEVED_EXCERPTS,
            StageName.RETRIEVE,
            build_retrieved(LINEAGE),
            produced_by=StageName.RETRIEVE,
            now=NOW,
        )
        impostor = make_objective("t", objective="An objective dropped into the wrong slot.")
        _substitute(ledger, StageName.INVENTORY, impostor)
        _substitute(ledger, StageName.RETRIEVE, impostor)
        assert {m.stage for m in ledger.verify_all()} == {
            StageName.INVENTORY,
            StageName.RETRIEVE,
        }

    def test_verify_all_is_quiet_on_an_intact_ledger(self) -> None:
        assert self._two_stages().verify_all() == ()

    def test_digests_refuses_to_hand_over_a_mixed_lineage(self) -> None:
        """Either every ancestor verifies or the stage is not entered.

        A stage handed one verified and one swapped input has been handed inputs
        whose guards were partly void, and there is no safe way to continue.
        """
        ledger = self._two_stages()
        ledger.record(
            ArtifactKind.RETRIEVED_EXCERPTS,
            StageName.RETRIEVE,
            build_retrieved(LINEAGE),
            produced_by=StageName.RETRIEVE,
            now=NOW,
        )
        _substitute(ledger, StageName.RETRIEVE, build_retrieved(OTHER_LINEAGE))
        with pytest.raises(ArtifactSubstitutedError):
            ledger.digests((StageName.INVENTORY, StageName.RETRIEVE))


def _parked_at_inventory() -> tuple[Orchestrator, str]:
    """An orchestrator whose run stopped at ``inventory``, plus its task id.

    Public API only. ``inventory`` blocks itself, so ``intake`` is recorded and
    nothing else is — which is exactly the state an adoption applies to.
    """
    from labcairn.skills import StageContext

    def blocking_inventory(context: StageContext) -> LabCairnModel:
        raise StageBlockedError("the ingestion backend is not configured in this build")

    orchestrator = make_orchestrator({StageName.INVENTORY: blocking_inventory})
    outcome = orchestrator.run(make_objective(str(orchestrator.task_id)))
    assert outcome.stop.value == "blocked"
    assert outcome.stopped_at is StageName.INVENTORY
    assert outcome.completed_stages == (StageName.INTAKE,)
    return orchestrator, str(orchestrator.task_id)


def _intake_lineage(orchestrator: Orchestrator) -> tuple[str, ...]:
    recorded = orchestrator.ledger.load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)
    return (recorded.digest,)


class TestAdoptionSeam:
    """``adopt_artifact`` is the only way in from outside, so it is checked."""

    def test_a_correctly_lineaged_artifact_adopts(self) -> None:
        orchestrator, task_id = _parked_at_inventory()
        inventory = build_inventory(_intake_lineage(orchestrator), task_id=task_id)
        orchestrator.adopt_artifact(StageName.INVENTORY, inventory)
        recorded = orchestrator.ledger.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
        assert recorded.digest == artifact_digest(inventory)
        assert recorded.externally_asserted is True

    def test_a_forgery_with_the_wrong_lineage_is_refused(self) -> None:
        """Schema-valid, non-empty, internally consistent — and not this run's."""
        orchestrator, task_id = _parked_at_inventory()
        with pytest.raises(LineageError, match="declares lineage"):
            orchestrator.adopt_artifact(
                StageName.INVENTORY,
                build_inventory(OTHER_LINEAGE, task_id=task_id),
            )

    def test_the_wrong_model_is_refused_before_the_lineage_is_considered(self) -> None:
        orchestrator, task_id = _parked_at_inventory()
        with pytest.raises(ArtifactTypeError, match="declares SourceInventory"):
            orchestrator.adopt_artifact(
                StageName.INVENTORY,
                make_objective(task_id),
            )

    def test_a_forgery_whose_materials_are_not_the_declared_ones_is_refused(self) -> None:
        """Right lineage, wrong content: the half a digest check alone cannot catch.

        The artifact names the correct upstream digest, so lineage passes. It is
        caught because the inventory has to reproduce the materials ``intake``
        declared.
        """
        orchestrator, task_id = _parked_at_inventory()
        forged = build_inventory(
            _intake_lineage(orchestrator),
            task_id=task_id,
            materials=(("unrelated.pdf", "e" * 64, True),),
            anchors=(make_anchor("a-foreign", "e" * 64),),
        )
        with pytest.raises(StageContractError, match="does not reproduce the materials"):
            orchestrator.adopt_artifact(StageName.INVENTORY, forged)

    def test_a_placeholder_is_refused_on_the_adoption_path_too(self) -> None:
        """The seam applies the same guards. It is not a way around them.

        The shape a lazy stage produces: right ids, right hashes, nothing said.
        """
        orchestrator, task_id = _parked_at_inventory()
        shell = SourceInventory(
            task_id=task_id,
            materials=(
                InventoryMaterial(
                    display_name="paper.pdf",
                    content_sha256=PAPER_SHA,
                    size_bytes=1024,
                    readable=True,
                ),
                InventoryMaterial(
                    display_name="data.csv",
                    content_sha256=DATA_SHA,
                    size_bytes=1024,
                    readable=True,
                ),
            ),
            anchors=tuple(
                InventoryAnchor(
                    anchor_id=anchor_id,
                    material_sha256=material,
                    locator_description="TODO",
                )
                for anchor_id, material in (("a-1", PAPER_SHA), ("a-2", DATA_SHA))
            ),
            derived_from=_intake_lineage(orchestrator),
        )
        with pytest.raises(StageContractError, match="placeholder"):
            orchestrator.adopt_artifact(StageName.INVENTORY, shell)

    def test_a_self_blocked_handler_parks_the_stage_rather_than_failing_it(self) -> None:
        """The graceful-blocking rule, on the handler path.

        A stage that says "I need a person" and is retried until its budget runs
        out is a stage whose waiting has been reported as breakage.
        """
        orchestrator, _ = _parked_at_inventory()
        assert orchestrator.checkpoint_report()[-1].status.value == "blocked"
