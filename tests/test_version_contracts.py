"""The version and edge contracts, and the refusals only this layer can make.

**What is under test.** LC-P2-08 T01: the typed models for a project, a
version and an edge, and the rules the **schema cannot express**.

**Why there is a second layer at all.** The store's constraints hold the
properties a CHECK constraint can see — one row at a time. Three of the
design's rules are about **two rows together**, and no constraint reaches
them:

1. **An edge's parent and child must belong to the same project.** A
   CHECK constraint sees one row; this rule is about the two versions the
   edge names.
2. **A proposal may not name an acceptor.** A ``source='evidence'`` edge
   with ``accepted_by`` set is a proposal wearing a person's name — and the
   schema's constraint allows it, because the constraint asks *"does an
   acceptance name somebody?"*, not *"is this edge an acceptance at all?"*.
3. **A human decision may not be anonymous.** The schema asks the same
   question from the other side, and the two together are what separate a
   decision from a proposal.

**And the one that is a number.** A confidence is **a number, not a
decision**. The edge's ``is_accepted`` says whether a person settled it,
and the two are independent: an edge with a confidence of 1.0 and no
acceptor is a *proposal*, and the model refuses to present it as anything
else. That is the design's rule — *"禁止仅靠相似度静默确定版本顺序"* — in a
property a test can watch.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from labcairn.papers.versions import (
    EdgeSource,
    PaperProject,
    PaperVersion,
    StageCandidate,
    VersionEdge,
    VersionStatus,
    check_edge_within_project,
)

pytestmark = pytest.mark.unit


def _edge(**overrides: Any) -> dict[str, Any]:
    """A well-formed edge, so each test changes one thing."""
    values: dict[str, Any] = {
        "edge_id": "edge-1",
        "project_id": "proj-1",
        "parent_version_id": "v1",
        "child_version_id": "v2",
        "source": EdgeSource.EVIDENCE,
        "confidence": 0.8,
    }
    values.update(overrides)
    return values


def _version(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "version_id": "v1",
        "project_id": "proj-1",
        "source_content_sha256": "a" * 64,
        "version_label_raw": "draft.docx",
    }
    values.update(overrides)
    return values


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #


def test_a_version_cannot_be_its_own_parent() -> None:
    """The model refuses the self-edge, and says why in the message.

    **What breaks it:** dropping the check from the validator. The schema
    refuses it too, but the model refuses it **earlier and with a message
    that names the contradiction**, and a caller that never reaches the
    database should not have to.
    """
    with pytest.raises(ValidationError) as refused:
        VersionEdge(**_edge(parent_version_id="v1", child_version_id="v1"))
    assert "cannot be its own parent" in str(refused.value)


def test_an_edge_with_no_acceptor_is_refused() -> None:
    """``source='human'`` with no ``accepted_by`` is refused.

    **What breaks it:** allowing it. The edge would read "a person decided
    this" and name nobody — and the schema's constraint does **not**
    catch it, because the schema asks *"does an acceptance name
    somebody?"* rather than *"is this edge an acceptance?"*. **This is the
    refusal only the application layer can make.**
    """
    with pytest.raises(ValidationError) as refused:
        VersionEdge(**_edge(source=EdgeSource.HUMAN))
    assert "nobody behind it" in str(refused.value)


def test_a_proposal_wearing_a_persons_name_is_refused() -> None:
    """``source='evidence'`` with an ``accepted_by`` is refused.

    **What breaks it:** allowing it. A proposal wearing a person's name is
    a forgery by another route — and it is the one the schema's
    constraint cannot see, because a row with both fields set satisfies
    *"an acceptance names somebody"* perfectly.

    **The design's reason, in one line:** a similarity score may propose
    an order and may not decide one, so a proposal that claims a decision
    is a decision nobody made.
    """
    with pytest.raises(ValidationError) as refused:
        VersionEdge(
            **_edge(
                source=EdgeSource.EVIDENCE,
                accepted_by="Prof. Lin",
                accepted_at="2026-03-02T09:15:00Z",
            )
        )
    assert "wears a person's name" in str(refused.value)


def test_a_model_proposal_is_not_an_acceptance() -> None:
    """``source='model'`` is a proposal, and the same rule applies to it.

    **What breaks it:** treating ``model`` as a kind of decision because
    it sounds more authoritative than ``evidence``. **A model proposing a
    relationship is exactly as much a proposal as the system proposing
    one** — and it is *less* trustworthy, because nobody has looked.
    """
    with pytest.raises(ValidationError) as refused:
        VersionEdge(
            **_edge(
                source=EdgeSource.MODEL, accepted_by="Prof. Lin", accepted_at="2026-03-02T09:15:00Z"
            )
        )
    assert "wears a person's name" in str(refused.value)


def test_an_acceptor_and_a_timestamp_are_set_together() -> None:
    """An acceptance nobody can place in time is refused.

    **What breaks it:** allowing one without the other. An acceptor with
    no time is a decision whose moment is unknown, and the schema's
    constraint covers both endpoints for exactly this reason.

    **The source here is ``evidence``, not ``human``.** A human edge with
    no acceptor is refused by a *different* rule — a decision with nobody
    behind it — and that rule fires first. This test is about the
    timestamp pairing, so it uses the source that reaches it.
    """
    with pytest.raises(ValidationError) as refused:
        VersionEdge(
            **_edge(
                source=EdgeSource.EVIDENCE,
                accepted_by="Prof. Lin",
                accepted_at=None,
            )
        )
    assert "both set or both omitted" in str(refused.value)

    with pytest.raises(ValidationError) as refused:
        VersionEdge(
            **_edge(
                source=EdgeSource.EVIDENCE,
                accepted_by=None,
                accepted_at="2026-03-02T09:15:00Z",
            )
        )
    assert "both set or both omitted" in str(refused.value)


def test_a_confidence_outside_the_range_is_refused() -> None:
    """A confidence above 1.0 is refused by the model too.

    **What breaks it:** widening the range. A confidence of 1.5 sorts
    above every real score, so it would put the least trustworthy
    proposal at the top of any ranking built on it.
    """
    with pytest.raises(ValidationError):
        VersionEdge(**_edge(confidence=1.5))
    with pytest.raises(ValidationError):
        VersionEdge(**_edge(confidence=-0.1))


def test_an_unknown_stage_is_refused_rather_than_coerced() -> None:
    """The vocabulary is closed, and a near-miss is not a member.

    **What breaks it:** accepting any string. ``"advised"`` would sail
    through and be indistinguishable from ``advisor_reviewed``, and a
    stage that could hold anything carries no information.
    """
    with pytest.raises(ValidationError):
        PaperVersion(**_version(stage_candidate="advised"))


def test_an_unknown_source_is_refused_rather_than_coerced() -> None:
    """The source vocabulary is closed at three.

    **What breaks it:** a fourth member that means something else. The
    three are not interchangeable, and the fourth would blur exactly the
    distinction the vocabulary exists to keep.
    """
    with pytest.raises(ValidationError):
        VersionEdge(**_edge(source="heuristic"))


def test_an_unknown_field_is_refused() -> None:
    """A field the contract does not define is refused.

    **What breaks it:** ``extra="allow"``. A typo in a field name would
    be **silently dropped**, and a contract that drops what it does not
    understand is a contract that agrees with a caller about something
    neither of them wrote.
    """
    with pytest.raises(ValidationError):
        VersionEdge(**_edge(parent_verison_id="v1"))


def test_a_blank_project_id_is_refused() -> None:
    """A blank identifier is refused.

    **What breaks it:** a min-length check that allows whitespace. ``" "``
    is a length of one and it identifies nothing.
    """
    with pytest.raises(ValidationError):
        PaperProject(project_id="   ", workspace_id="ws-1", subject_pseudonym="a")


# --------------------------------------------------------------------------- #
# the properties that are not refusals
# --------------------------------------------------------------------------- #


def test_a_confident_proposal_is_still_unaccepted() -> None:
    """An edge with no acceptor is a valid edge, and it says so.

    **This is the counterpart of the refusal above, and it is the one that
    is easy to get wrong in the other direction.** A model that required an
    acceptor would be unable to hold the thing the system produces before
    a person has looked — and the whole design is that a person looks.

    **The two properties are independent.** ``confidence`` says how strong
    the evidence is; ``is_accepted`` says whether anybody decided. A
    confident proposal is still a proposal.
    """
    edge = VersionEdge(**_edge(source=EdgeSource.EVIDENCE, confidence=1.0))

    assert edge.is_proposal is True
    assert edge.is_accepted is False
    assert edge.confidence == pytest.approx(1.0)


def test_a_human_decision_is_accepted_as_accepted() -> None:
    """An edge a person accepted says so, and names them."""
    edge = VersionEdge(
        **_edge(
            source=EdgeSource.HUMAN,
            confidence=0.3,
            accepted_by="Prof. Lin",
            accepted_at="2026-03-02T09:15:00Z",
        )
    )

    assert edge.is_accepted is True
    assert edge.is_proposal is False
    # The confidence is still there, and it is still just a number: a
    # person accepted this on **low** evidence, and the model does not
    # argue with them about it.
    assert edge.confidence == pytest.approx(0.3)


def test_a_version_defaults_to_unresolved_and_unknown() -> None:
    """The defaults are the honest ones.

    **What breaks it:** defaulting a version to ``resolved`` or to a real
    stage. A system that archives what it is given cannot know a version's
    parent before it has seen the other versions, and it cannot read a
    stage off a file name — the design says plainly that a name like
    ``最终版2.docx`` is not a statement about which is newer.
    """
    version = PaperVersion(**_version())

    assert version.status is VersionStatus.UNRESOLVED
    assert version.stage_candidate is StageCandidate.UNKNOWN


def test_the_version_label_is_kept_verbatim_and_is_not_an_order() -> None:
    """The author's label is kept, and the model does not read it.

    **What breaks it:** parsing the label for an order. The label is
    whatever the author called the file; it is kept because a person
    reading the archive needs to see it, and it decides nothing.
    """
    version = PaperVersion(**_version(version_label_raw="最终版2.docx"))

    assert version.version_label_raw == "最终版2.docx"
    assert version.status is VersionStatus.UNRESOLVED


def test_an_edge_is_frozen() -> None:
    """An edge cannot be edited in place.

    **What breaks it:** a mutable model. The project's rule is that a
    human correction produces a **new version** rather than silently
    replacing what was there, and a mutable edge would let a correction
    change the evidence underneath the record of it.
    """
    edge = VersionEdge(**_edge())
    with pytest.raises(ValidationError):
        edge.confidence = 0.1


def test_a_version_with_no_established_parent_is_unresolved_and_listed() -> None:
    """A version whose parent is unknown is ``unresolved``, and it is listed.

    **What breaks it:** a version that only exists once its relationship is
    known. The relationship cannot be established until the version is
    recorded, so that rule would make the version unrecordable — and
    **the absence of an edge is not the absence of a version**.

    **And "listed" is the half that is easy to lose.** A version whose
    parent is unknown is still material in the project; hiding it because
    its relationship is unknown would make the archive look complete when
    it is not.
    """
    version = PaperVersion(**_version())

    assert version.status is VersionStatus.UNRESOLVED
    # It is a version, and it is storable: the model does not require a
    # parent, because a parent is a fact about an edge and this is a fact
    # about a version.
    assert version.version_id == "v1"
    assert version.project_id == "proj-1"


def test_an_edge_to_a_version_outside_the_project_is_refused() -> None:
    """An edge may not name a version belonging to another manuscript.

    **This is the check a CHECK constraint cannot make.** The schema sees
    one row; this is a fact about three — the edge's project and the
    projects of the two versions it names. A row can satisfy every column
    constraint and still say that a version of one manuscript came from a
    version of another.

    **And an edge that crosses projects is a claim about a lineage that
    does not exist.** The graph would show a paper that is its own
    ancestor, and every count over the graph would be wrong.
    """
    edge = VersionEdge(**_edge())
    other_project = PaperVersion(**_version(version_id="other-v1", project_id="proj-2"))
    inside = PaperVersion(**_version(version_id="v1"))

    # A version the caller does not hold is a refusal, not an assumption.
    with pytest.raises(ValueError) as refused:
        check_edge_within_project(edge, {"v2": inside})
    assert "not among the versions given" in str(refused.value)

    # And a version that belongs to another project is refused.
    with pytest.raises(ValueError) as refused:
        check_edge_within_project(edge, {"v1": inside, "v2": other_project})
    assert "across projects" in str(refused.value)

    # And the same edge, with both versions inside the project, is fine.
    check_edge_within_project(edge, {"v1": inside, "v2": inside})
