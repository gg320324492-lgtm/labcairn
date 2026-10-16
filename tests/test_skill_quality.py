"""The definition of "empty placeholder", and the checks that survive a fluent fake.

The important test in this file is
:func:`test_every_string_field_is_classified`. A placeholder rule only works if it
covers every free-text field, and the only way that stays true when someone adds
a field next year is a test that fails when it does not.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from test_skill_support import (
    DATA_SHA,
    FOREIGN_SHA,
    PAPER_SHA,
    build_draft,
    build_inventory,
    build_ledger,
    build_proposal,
    build_retrieved,
    build_validation,
    make_anchor,
)

from labcairn.core.schema import LabCairnModel
from labcairn.evidence.states import VerificationStatus
from labcairn.skills import (
    AnchorRef,
    DerivationClosureError,
    DraftSection,
    EvidenceClaim,
    EvidenceLedgerView,
    Materiality,
    PlaceholderError,
    ReportDraft,
    RetrievedExcerpts,
    SourceInventory,
    StageName,
    artifact_type,
)
from labcairn.skills.artifacts import (
    ArtifactKind,
    RetrievedExcerpt,
)
from labcairn.skills.quality import (
    BODY_FIELDS,
    CONTRACT_MODELS,
    FORMAT_FIELDS,
    IDENTIFIER_FIELDS,
    MIN_SUBSTANTIVE_CHARS,
    PLACEHOLDER_TOKENS,
    PRIMARY_CONTENT_FIELDS,
    PROSE_FIELDS,
    Upstream,
    UpstreamArtifact,
    is_placeholder_token,
    iter_text_fields,
    normalize_placeholder_text,
    require_closure,
    require_substance,
    string_field_names,
    substantive_length,
)

pytestmark = pytest.mark.unit

UPSTREAM = ("a" * 64,)
OTHER = ("b" * 64,)


class TestPlaceholderVocabulary:
    @pytest.mark.parametrize(
        "text",
        ["TODO", "todo", "  TODO  ", "TBD", "tbd.", "N/A", "n/a", "???", "...", "…"],
    )
    def test_the_obvious_markers_are_recognised(self, text: str) -> None:
        assert is_placeholder_token(text)

    @pytest.mark.parametrize("text", ["待定", "待定。", "占位", "暂无", "无"])
    def test_full_width_markers_are_recognised(self, text: str) -> None:
        """A report in this project may be written in either language."""
        assert is_placeholder_token(text)

    @pytest.mark.parametrize(
        "text",
        [
            "The yield fell to 61.4 percent at the highest catalyst loading tested.",
            "Methods",
            "paper.pdf",
            "a/b",
            "The method section describes the searched corpus in full detail.",
        ],
    )
    def test_real_text_is_not_a_marker(self, text: str) -> None:
        assert not is_placeholder_token(text)

    def test_normalisation_collapses_inner_whitespace_but_not_the_markers_edges(self) -> None:
        assert normalize_placeholder_text("to   be\ndetermined") == "to be determined"
        assert normalize_placeholder_text("N/A") == "n/a"

    def test_the_vocabulary_is_closed_and_small(self) -> None:
        """A small closed set is reviewable. A regex is not."""
        assert "todo" in PLACEHOLDER_TOKENS
        assert len(PLACEHOLDER_TOKENS) < 60


class TestSubstantiveLength:
    def test_counting_is_alphanumeric_and_language_agnostic(self) -> None:
        assert substantive_length("abc 123 !?") == 6
        assert substantive_length("待定") == 2

    def test_a_real_finding_clears_the_floor(self) -> None:
        body = "Yield fell to 61.4 percent at the highest catalyst loading tested."
        assert substantive_length(body) >= MIN_SUBSTANTIVE_CHARS


class TestFieldCoverage:
    """Every string field must be classified, or the rule has a hole in it."""

    def test_every_string_field_is_classified(self) -> None:
        classified = PROSE_FIELDS | BODY_FIELDS | IDENTIFIER_FIELDS | FORMAT_FIELDS
        unclassified = string_field_names(CONTRACT_MODELS) - classified
        assert unclassified == set(), (
            f"string field(s) {sorted(unclassified)} belong to none of PROSE_FIELDS, "
            f"BODY_FIELDS, IDENTIFIER_FIELDS or FORMAT_FIELDS. A field that is in "
            f"none of them is not covered by the placeholder rule, so a stage can "
            f"put its shell there."
        )

    def test_the_classification_sets_do_not_overlap(self) -> None:
        pairs = {
            "PROSE/BODY": PROSE_FIELDS & BODY_FIELDS,
            "PROSE/ID": PROSE_FIELDS & IDENTIFIER_FIELDS,
            "BODY/ID": BODY_FIELDS & IDENTIFIER_FIELDS,
            "BODY/FORMAT": BODY_FIELDS & FORMAT_FIELDS,
            "ID/FORMAT": IDENTIFIER_FIELDS & FORMAT_FIELDS,
            "PROSE/FORMAT": PROSE_FIELDS & FORMAT_FIELDS,
        }
        assert {name: overlap for name, overlap in pairs.items() if overlap} == {}

    def test_every_primary_content_field_is_required_non_empty_by_its_schema(self) -> None:
        """The list in ``quality`` and the constraint in the model must agree.

        ``quality`` names which invariant matters; the model says what happens
        when it is broken. If someone relaxes a ``Field(min_length=1)`` and forgets
        the orchestrator's re-check, this test is what notices.
        """
        for model in CONTRACT_MODELS:
            for name in PRIMARY_CONTENT_FIELDS & set(model.model_fields):
                field = model.model_fields[name]
                constraint = field.metadata[0] if field.metadata else None
                assert getattr(constraint, "min_length", None) == 1, (
                    f"{model.__name__}.{name} is listed in PRIMARY_CONTENT_FIELDS but "
                    f"the schema does not require it to be non-empty"
                )

    def test_the_walker_reaches_into_nested_models(self) -> None:
        draft = build_draft(UPSTREAM)
        paths = [path for path, _ in iter_text_fields(draft)]
        assert "sections[0].heading" in paths
        assert "sections[1].body" in paths


class TestSubstanceRejection:
    """A stage that produced a shell must be refused, by name."""

    def test_a_real_draft_is_accepted(self) -> None:
        require_substance(build_draft(UPSTREAM))

    def test_placeholder_text_in_a_body_is_refused(self) -> None:
        draft = build_draft(
            UPSTREAM,
            sections=(
                DraftSection(
                    section_id="s-1",
                    heading="Result",
                    body="TODO",
                    evidence_refs=("c-1",),
                ),
            ),
        )
        with pytest.raises(PlaceholderError, match=r"placeholder marker"):
            require_substance(draft)

    def test_a_body_too_short_to_carry_a_finding_is_refused(self) -> None:
        draft = build_draft(
            UPSTREAM,
            sections=(
                DraftSection(
                    section_id="s-1",
                    heading="Result",
                    body="nope",
                    evidence_refs=("c-1",),
                ),
            ),
        )
        with pytest.raises(PlaceholderError, match="alphanumeric character"):
            require_substance(draft)

    def test_a_short_heading_is_accepted(self) -> None:
        """``"Methods"`` is a real heading. The length floor is for bodies."""
        draft = build_draft(
            UPSTREAM,
            sections=(
                DraftSection(
                    section_id="s-1",
                    heading="Methods",
                    body="The corpus was searched locally with a lexical index over it.",
                    evidence_refs=("c-1",),
                ),
            ),
        )
        require_substance(draft)

    def test_every_violation_is_reported_at_once(self) -> None:
        """One attempt per empty section would burn the retry budget to find out."""
        draft = build_draft(
            UPSTREAM,
            sections=(
                DraftSection(section_id="s-1", heading="A", body="TODO", evidence_refs=("c-1",)),
                DraftSection(section_id="s-2", heading="B", body="TBD", evidence_refs=("c-2",)),
            ),
        )
        with pytest.raises(PlaceholderError) as caught:
            require_substance(draft)
        assert caught.value.args[0].count("is a placeholder marker") == 2

    def test_an_identifier_that_looks_short_is_not_flagged(self) -> None:
        ledger = build_ledger(UPSTREAM, claim_ids=("c", "d"))
        require_substance(ledger)

    def test_a_hash_is_not_flagged_for_being_sixty_four_characters(self) -> None:
        require_substance(build_inventory(UPSTREAM))

    def test_the_schema_refuses_an_empty_primary_collection(self) -> None:
        """The empty-collection rule is enforced by the model, before the gate runs."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SourceInventory(task_id="t", materials=(), anchors=(), derived_from=UPSTREAM)

    def test_a_stage_returning_an_empty_shell_cannot_even_build_it(self) -> None:
        """The specific shape a lazy stage produces: an object with nothing in it."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ReportDraft(task_id="t", sections=(), derived_from=UPSTREAM)


class TestClosure:
    """Reference closure — the property that survives a fluent fake."""

    def _upstream(self, kinds: Mapping[ArtifactKind, LabCairnModel]) -> Upstream:
        return Upstream(
            entries=tuple(
                UpstreamArtifact(kind=kind, digest="a" * 64, artifact=artifact)
                for kind, artifact in kinds.items()
            )
        )

    def test_a_correct_inventory_closes(self) -> None:
        from test_skill_support import make_objective

        objective = make_objective(
            "t", materials=(("paper.pdf", PAPER_SHA), ("data.csv", DATA_SHA))
        )
        inventory = build_inventory(
            UPSTREAM, materials=(("paper.pdf", PAPER_SHA, True), ("data.csv", DATA_SHA, True))
        )
        require_closure(
            StageName.INVENTORY,
            inventory,
            self._upstream({ArtifactKind.RESEARCH_OBJECTIVE: objective}),
        )

    def test_an_inventory_that_omits_a_declared_material_is_refused(self) -> None:
        from test_skill_support import make_objective

        objective = make_objective(
            "t", materials=(("paper.pdf", PAPER_SHA), ("data.csv", DATA_SHA))
        )
        inventory = build_inventory(
            UPSTREAM,
            materials=(("paper.pdf", PAPER_SHA, True), ("other.csv", FOREIGN_SHA, True)),
        )
        with pytest.raises(DerivationClosureError, match="inventoried but never bound"):
            require_closure(
                StageName.INVENTORY,
                inventory,
                self._upstream({ArtifactKind.RESEARCH_OBJECTIVE: objective}),
            )

    def test_an_inventory_that_drops_a_declared_material_is_refused(self) -> None:
        from test_skill_support import make_objective

        objective = make_objective(
            "t", materials=(("paper.pdf", PAPER_SHA), ("data.csv", DATA_SHA))
        )
        inventory = build_inventory(UPSTREAM, materials=(("paper.pdf", PAPER_SHA, True),))
        with pytest.raises(DerivationClosureError, match="not inventoried"):
            require_closure(
                StageName.INVENTORY,
                inventory,
                self._upstream({ArtifactKind.RESEARCH_OBJECTIVE: objective}),
            )

    def test_retrieval_from_an_unknown_anchor_is_refused(self) -> None:
        inventory = build_inventory(UPSTREAM)
        excerpts = RetrievedExcerpts(
            task_id="t",
            excerpts=(
                RetrievedExcerpt(
                    anchor_id="nowhere",
                    material_sha256=FOREIGN_SHA,
                    rank=1,
                    excerpt="A passage that came from somewhere the inventory never saw.",
                    retrieval_method="fts5 lexical over normalised excerpts",
                ),
            ),
            derived_from=UPSTREAM,
        )
        with pytest.raises(DerivationClosureError, match="inventory does not contain"):
            require_closure(
                StageName.RETRIEVE,
                excerpts,
                self._upstream({ArtifactKind.SOURCE_INVENTORY: inventory}),
            )

    def test_an_anchor_id_matching_but_a_different_hash_is_refused(self) -> None:
        """The sharp one: the id is right, the bytes behind it are not."""
        inventory = build_inventory(
            UPSTREAM,
            materials=(("paper.pdf", PAPER_SHA, True),),
            anchors=(make_anchor("a-1", PAPER_SHA),),
        )
        excerpts = RetrievedExcerpts(
            task_id="t",
            excerpts=(
                RetrievedExcerpt(
                    anchor_id="a-1",
                    material_sha256=FOREIGN_SHA,
                    rank=1,
                    excerpt="A passage whose anchor id matches but whose bytes differ.",
                    retrieval_method="fts5 lexical over normalised excerpts",
                ),
            ),
            derived_from=UPSTREAM,
        )
        with pytest.raises(DerivationClosureError, match="material hashes the inventory"):
            require_closure(
                StageName.RETRIEVE,
                excerpts,
                self._upstream({ArtifactKind.SOURCE_INVENTORY: inventory}),
            )

    def test_a_claim_citing_an_unretrieved_anchor_is_refused(self) -> None:
        excerpts = build_retrieved(UPSTREAM)
        ledger = EvidenceLedgerView(
            task_id="t",
            claims=(
                EvidenceClaim(
                    claim_id="c-1",
                    statement="A claim resting on an anchor retrieval never returned.",
                    anchor_refs=(AnchorRef(anchor_id="ghost", material_sha256=PAPER_SHA),),
                    status=VerificationStatus.EXTRACTED,
                ),
            ),
            derived_from=UPSTREAM,
        )
        with pytest.raises(DerivationClosureError, match="retrieval did"):
            require_closure(
                StageName.EVIDENCE,
                ledger,
                self._upstream({ArtifactKind.RETRIEVED_EXCERPTS: excerpts}),
            )

    def test_a_draft_citing_a_claim_the_ledger_never_produced_is_refused(self) -> None:
        """Fluent, well-cited, entirely fictitious prose. This is what it costs."""
        ledger = build_ledger(UPSTREAM, claim_ids=("c-1",))
        draft = build_draft(
            UPSTREAM,
            sections=(
                DraftSection(
                    section_id="s-1",
                    heading="Result",
                    body="A fluent paragraph asserting a finding nobody ever verified.",
                    evidence_refs=("c-never-produced",),
                ),
            ),
        )
        with pytest.raises(DerivationClosureError, match="no earlier stage produced"):
            require_closure(
                StageName.DRAFT, draft, self._upstream({ArtifactKind.EVIDENCE_LEDGER: ledger})
            )

    def test_a_validation_that_skipped_a_section_is_refused(self) -> None:
        draft = build_draft(UPSTREAM)
        report = build_validation(UPSTREAM, section_ids=("s-method",))
        with pytest.raises(DerivationClosureError, match="never looked at"):
            require_closure(
                StageName.VALIDATE,
                report,
                self._upstream({ArtifactKind.REPORT_DRAFT: draft}),
            )

    def test_a_significant_proposal_item_must_rest_on_a_claim(self) -> None:
        """A direction change the ledger cannot support is exactly what needs a human."""
        ledger = build_ledger(UPSTREAM)
        proposal = build_proposal(
            UPSTREAM,
            materiality=Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
            evidence_refs=(),
        )
        with pytest.raises(DerivationClosureError, match="cites no claim"):
            require_closure(
                StageName.PROPOSE,
                proposal,
                self._upstream({ArtifactKind.EVIDENCE_LEDGER: ledger}),
            )

    def test_a_stage_with_no_closure_rule_closes_vacuously(self) -> None:
        """``intake`` reads nothing; that is a stated fact, not an omission."""
        from test_skill_support import make_objective

        require_closure(StageName.INTAKE, make_objective("t"), Upstream())

    def test_a_closure_rule_missing_its_input_is_an_error_not_a_pass(self) -> None:
        with pytest.raises(DerivationClosureError, match="cannot see its upstream artifact"):
            require_closure(StageName.DRAFT, build_draft(UPSTREAM), Upstream())


def test_a_substantive_artifact_with_a_wrong_lineage_still_closes_only_against_the_right_one() -> (
    None
):
    """Lineage and closure are different checks, and both are needed.

    ``derived_from`` names the *digests*; closure checks the *content* against
    the objects those digests belong to. An artifact can satisfy one and not the
    other, which is why the orchestrator applies both.
    """
    draft = build_draft(UPSTREAM)
    assert tuple(draft.derived_from) == UPSTREAM

    # The ledger this draft actually cites: it closes.
    matching = build_ledger(UPSTREAM, claim_ids=("c-1", "c-2"))
    require_closure(
        StageName.DRAFT,
        draft,
        Upstream(
            entries=(
                UpstreamArtifact(
                    kind=ArtifactKind.EVIDENCE_LEDGER, digest="f" * 64, artifact=matching
                ),
            )
        ),
    )

    # A *different* ledger, under a digest the draft does not name. The digest
    # comparison is what notices the lineage is wrong; the content comparison is
    # what notices the citations are. Neither alone is enough, which is why the
    # orchestrator runs both.
    unrelated = build_ledger(UPSTREAM, claim_ids=("c-9",))
    with pytest.raises(DerivationClosureError, match="no earlier stage produced"):
        require_closure(
            StageName.DRAFT,
            draft,
            Upstream(
                entries=(
                    UpstreamArtifact(
                        kind=ArtifactKind.EVIDENCE_LEDGER, digest="f" * 64, artifact=unrelated
                    ),
                )
            ),
        )


def test_the_artifact_type_table_is_the_only_source_of_port_types() -> None:
    for kind, model in {
        ArtifactKind.RESEARCH_OBJECTIVE: "ResearchObjective",
        ArtifactKind.REPORT_DRAFT: "ReportDraft",
        ArtifactKind.VALIDATION_REPORT: "ValidationReport",
    }.items():
        assert artifact_type(kind).__name__ == model
