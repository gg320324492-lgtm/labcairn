"""The paper-version exit demonstration, for LC-P2-08.

**Run it:**

```bash
python examples/paper_version_demo.py
```

**What it shows.** A project with four versions, in the state the design
says an archive is allowed to hold and not allowed to hide:

1. **a project** with a pseudonym and a consent reference;
2. **four versions**, one of which has no established parent;
3. **a version graph** with a branch — two versions share one parent,
   because the teacher's process branches;
4. **a duplicate** — two files with the same name and different bytes, and
   the system reports them as two versions with an unresolved relationship
   rather than merging them;
5. **a missing round** — the sequence has a hole, and the hole is reported
   and **nothing is renumbered**;
6. **a proposal** the alignment made, with its evidence, and **no
   acceptor** — because a score may not settle an order;
7. **a person accepting it**, which is what settles it.

**Every claim is carried by a `check()` that raises.** The exit code is the
assertion that matters: a zero exit means every one of them still holds, and
a non-zero exit names the one that stopped. A demonstration that only
printed would be prose.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from labcairn.papers.alignment import propose_alignment
from labcairn.papers.duplicates import (
    VersionSummary,
    check_duplicates,
    check_missing_rounds,
)
from labcairn.papers.versions import (
    ConfirmationOutcome,
    EdgeSource,
    PaperProject,
    PaperVersion,
    VersionEdge,
    VersionStatus,
    confirm_edge,
)

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)

#: The four versions. The third is the duplicate (same name, different
#: bytes) and the fourth sits in a round that the sequence skips.
VERSIONS_TEXT: dict[str, str] = {
    "v1": """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on three benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.12 on the synthetic set.
""",
    "v2": """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on three benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.09 on the synthetic set.

Discussion
The improvement is consistent across every benchmark we ran.
""",
    "v3-duplicate": """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on three benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.09 on the synthetic set.

Discussion
The improvement is consistent across every benchmark we ran.
""",
    "v4": """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on four benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.07 on the synthetic set.
""",
}


def check(condition: bool, message: str) -> None:
    """Assert, by raising.

    **A demonstration that warns is a demonstration that fails quietly.**
    The exit code carries every claim, so each one has to stop the run when
    it stops holding.
    """
    if not condition:
        raise AssertionError(message)


def main() -> int:
    print("LC-P2-08 exit demonstration: the paper version graph")
    print("=" * 60)

    # -- 1. the project ---------------------------------------------------- #
    project = PaperProject(
        project_id="proj-1",
        workspace_id="ws-1",
        subject_pseudonym="student-a",
        consent_ref="grant-1",
    )
    print(f"\n1. The project: {project.project_id} (pseudonym {project.subject_pseudonym})")
    print(f"   consent reference: {project.consent_ref}")
    check(project.consent_ref == "grant-1", "the project carries its consent reference")

    # -- 2. the versions ---------------------------------------------------- #
    versions: list[PaperVersion] = []
    labels = {
        "v1": ("draft.docx", "a" * 64),
        "v2": ("v2.docx", "b" * 64),
        "v3-duplicate": ("v2.docx", "c" * 64),
        "v4": ("v4.docx", "d" * 64),
    }
    for version_id, (label, digest) in labels.items():
        versions.append(
            PaperVersion(
                version_id=version_id,
                project_id=project.project_id,
                source_content_sha256=digest,
                version_label_raw=label,
            )
        )
    print(f"\n2. The versions: {len(versions)} of them")
    for version in versions:
        print(
            f"   {version.version_id:<14} label={version.version_label_raw!r:<14} "
            f"status={version.status.value}"
        )

    # -- 3. the unresolved one --------------------------------------------- #
    unresolved = [v for v in versions if v.status is VersionStatus.UNRESOLVED]
    check(len(unresolved) == 4, "every version starts unresolved")
    print(f"\n3. Every version starts unresolved: {len(unresolved)} of {len(versions)}")
    print("   None of them has an established parent yet.")

    # -- 4. the duplicate ---------------------------------------------------- #
    summaries = [
        VersionSummary(
            version_id=version.version_id,
            content_sha256=version.source_content_sha256,
            version_label_raw=version.version_label_raw,
        )
        for version in versions
    ]
    duplicates = check_duplicates(summaries)
    print("\n4. The duplicates")
    for group in duplicates.same_label_different_bytes:
        print(f"   same name, different bytes: {group} -- two versions, unresolved")
    check(
        duplicates.same_label_different_bytes == (("v2", "v3-duplicate"),),
        "the same name with different bytes is reported as two versions",
    )
    check(
        not duplicates.same_bytes_different_labels,
        "nothing shares its bytes under a different name",
    )

    # -- 5. the missing round ------------------------------------------------ #
    rounds = check_missing_rounds(summaries)
    print("\n5. The rounds")
    print(f"   present: {rounds.present}   missing: {rounds.missing}")
    print(f"   unplaced: {rounds.unplaced}")
    print("   The hole is reported and nothing is renumbered.")
    check(rounds.has_gap, "the missing round is reported")
    check(rounds.present == (2, 4), "the rounds that exist are reported as they are")
    check(rounds.missing == (3,), "the missing round is named")
    # **The version whose label declares no round is unplaced, not in round
    # one.** A name that does not say where it goes does not put it
    # somewhere, and the difference between "unplaced" and "missing" is the
    # difference between "this one does not say" and "something was here
    # and is not now".
    check(
        rounds.unplaced == ("v1",),
        "the version whose label declares no round is unplaced, not in a round",
    )

    # -- 6. the proposal ------------------------------------------------------ #
    proposal = propose_alignment("v2", VERSIONS_TEXT["v2"], {"v1": VERSIONS_TEXT["v1"]})
    print("\n6. The alignment's proposal")
    print(f"   candidate: {proposal.candidates[0]!r}   confidence: {proposal.confidence:.3f}")
    for item in proposal.evidence:
        print(f"   evidence: {item.kind} -- {item.detail}")
    check(proposal.candidates[0] == "v1", "the proposal points at the parent")
    check(proposal.decided, "the evidence pointed one way")
    check(bool(proposal.evidence), "the proposal carries its evidence")

    # **The proposal is a proposal.** No acceptor, no decision.
    edge = VersionEdge(
        edge_id="edge-1",
        project_id=project.project_id,
        parent_version_id="v1",
        child_version_id="v2",
        source=EdgeSource.EVIDENCE,
        confidence=proposal.confidence,
        evidence_spans=tuple(item.kind for item in proposal.evidence),
    )
    check(edge.is_proposal, "the edge is a proposal")
    check(edge.accepted_by is None, "the proposal names no acceptor")
    print(f"   the edge names no acceptor: accepted_by={edge.accepted_by!r}")
    print("   A score may propose an order; it may not settle one.")

    # -- 7. the branch --------------------------------------------------------- #
    branch = VersionEdge(
        edge_id="edge-2",
        project_id=project.project_id,
        parent_version_id="v1",
        child_version_id="v3-duplicate",
        source=EdgeSource.EVIDENCE,
        confidence=0.4,
    )
    print("\n7. The branch")
    print(f"   v1 has two children: {edge.child_version_id!r} and {branch.child_version_id!r}")
    check(
        edge.parent_version_id == branch.parent_version_id,
        "two versions may share one parent",
    )

    # -- 8. the person ---------------------------------------------------------- #
    decision = confirm_edge(
        edge,
        ConfirmationOutcome.ACCEPTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        reason="the passages match; this is the same draft.",
    )
    print("\n8. A person accepts it")
    print(f"   decided by {decision.decided_by!r} at {decision.decided_at.isoformat()}")
    print(f"   reason: {decision.reason}")
    check(decision.edge is not None, "the acceptance produces an edge")
    assert decision.edge is not None
    check(decision.edge.is_accepted, "the edge is now settled")
    check(decision.edge.accepted_by == "Prof. Lin", "the edge names who settled it")
    check(
        decision.edge.source is EdgeSource.HUMAN,
        "a settled edge says a person decided it",
    )

    # -- 9. the rejection -------------------------------------------------------- #
    rejection = confirm_edge(
        branch,
        ConfirmationOutcome.REJECTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        reason="this is a copy, not a second draft.",
    )
    print("\n9. A person rejects the other one")
    print(f"   decided by {rejection.decided_by!r}")
    print(f"   reason: {rejection.reason}")
    check(rejection.edge is None, "a rejection produces no edge")
    check(rejection.corrects is not None, "a rejection keeps the proposal it refused")
    assert rejection.corrects is not None
    check(
        rejection.corrects.accepted_by is None,
        "the refused proposal is still a proposal",
    )
    print("   The refusal is recorded and the proposal is still readable.")

    print("\n" + "=" * 60)
    print("All checks held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
