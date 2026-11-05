"""The five arms' run configuration, and whether the configuration may run.

**What this module holds.** The protocol (``docs/plans/LC-P2-14-ablation-protocol.md``
§1) names five arms — A through E, each adding one more source of evidence
to the one before it — and two contrasts that matter: **D vs C** and
**E vs D**. The question those contrasts answer is not whether a model
helps and not whether retrieval helps, but whether the advisor's actual
process helps, and whether the outcome of it helps more.

**Why the configuration is a type and not a dictionary.** A run whose arms
are declared in free-form JSON can drift apart silently: one arm's budget
edited, another's input set narrowed, and nothing refuses the result until
a human reads it. So each arm is an :class:`ArmConfiguration`, and a whole
set of arms is assessed by :func:`assess_configuration` before anything
runs. **A configuration whose arms disagree on anything the protocol
requires them to share is refused, by name** — the refusal names the arm
and the requirement, the way the harness's comparison refuses a baseline
that is not like-for-like.

**What the protocol requires the arms to share.** One underlying model
("on the same underlying model and a comparable budget"), a declared
budget, and the additive chain: each arm sees everything the arm before it
sees, plus exactly the one more source the protocol names. An arm whose
inputs fall short of its predecessor's is not the protocol's arm C or D or
E — it is something else wearing the letter.

**The arrangement pair.** P2-AMD-01 adds one more comparison, as an
independent variable: the same B evidence under a single guidance role
(B-only) and under guidance plus an independent critique role (B+C). The
protocol is explicit that this comparison is a measurement of the
*arrangement* only when the evidence, the model and the budget are all
held fixed — "with a different supplier, a difference measures the models
and not the roles." :func:`assess_arrangement` refuses a pair that differs
in anything else, because a difference measured across two moving parts is
the attribution of a difference to nothing.

**What this module deliberately does not do.** It runs nothing, contacts
nothing, and declares no model by name — the model is whatever the owner
puts in the configuration at run time. The real run waits on unseen papers
and a budget; this module is the shape that waits with it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Final

#: The five arms the protocol names, in its order.
ARM_IDS: Final[tuple[str, ...]] = ("A", "B", "C", "D", "E")

#: The sources of evidence an arm may declare, in the protocol's words.
#:
#: The protocol's arms are cumulative: each letter adds one more source to
#: the one before it. The vocabulary here is closed — a face the protocol
#: does not name is not a face a configuration may declare, because an
#: undeclared face is a face no leak check would ever watch.
INPUT_FACES: Final[tuple[str, ...]] = (
    "draft",
    "literature",
    "version_differences",
    "advisor_comments",
    "student_responses",
    "review_outcome",
    "confirmed_rules",
)

#: What each arm sees, by the protocol's §1 table.
#:
#: A is the current draft and a general model; B adds ordinary literature
#: retrieval; C adds version differences; D adds the advisor's comments and
#: the student's responses; E adds the review outcome and the confirmed
#: rules.
EXPECTED_INPUTS: Final[dict[str, frozenset[str]]] = {
    "A": frozenset({"draft"}),
    "B": frozenset({"draft", "literature"}),
    "C": frozenset({"draft", "literature", "version_differences"}),
    "D": frozenset(
        {
            "draft",
            "literature",
            "version_differences",
            "advisor_comments",
            "student_responses",
        }
    ),
    "E": frozenset(
        {
            "draft",
            "literature",
            "version_differences",
            "advisor_comments",
            "student_responses",
            "review_outcome",
            "confirmed_rules",
        }
    ),
}

#: The roles the protocol names for the arrangement comparison.
ROLE_GUIDANCE: Final = "guidance"
ROLE_CRITIQUE: Final = "independent_critique"

#: The two contrasts the protocol says matter.
CONTRAST_PAIRS: Final[tuple[tuple[str, str], ...]] = (("D", "C"), ("E", "D"))


@dataclass(frozen=True, slots=True)
class ArmConfiguration:
    """One arm's declaration: its identity, its model, its budget, its inputs.

    Every field is a declaration the leak check and the comparability check
    hold the run to. An arm that sees more than it declares is not caught
    here — that is the split check's job — but an arm that *declares* less
    than the protocol's letter requires is refused here, before anything
    runs.
    """

    #: The arm's letter, one of :data:`ARM_IDS`.
    arm_id: str
    #: The underlying model: name, version and parameter set, as one string.
    #: The protocol holds the model fixed across the arms, so a difference
    #: measures the evidence and not the supplier.
    model: str
    #: The declared budget, as one string. Declared, not promised: an arm
    #: with no budget line cannot be checked for comparability at all.
    budget: str
    #: The evidence faces the arm sees, from :data:`INPUT_FACES`.
    inputs: frozenset[str]
    #: The roles the arm runs under. The five arms run one guidance role;
    #: the arrangement comparison adds the independent critique role.
    roles: tuple[str, ...] = (ROLE_GUIDANCE,)

    def to_document(self) -> dict[str, Any]:
        """The configuration as a JSON-ready document."""
        return {
            "arm_id": self.arm_id,
            "model": self.model,
            "budget": self.budget,
            "inputs": sorted(self.inputs),
            "roles": list(self.roles),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> ArmConfiguration:
        """Read one arm's configuration out of a JSON document.

        A missing field is a refusal, not a default: an arm whose budget is
        absent is not an arm with a budget the reader has not seen yet.
        """
        missing = [key for key in ("arm_id", "model", "budget", "inputs") if key not in document]
        if missing:
            msg = f"arm configuration is missing {', '.join(missing)}"
            raise ValueError(msg)
        inputs = frozenset(str(face) for face in document["inputs"])
        unknown = sorted(set(inputs) - set(INPUT_FACES))
        if unknown:
            msg = (
                f"arm {document['arm_id']!r} declares inputs the protocol "
                f"does not name: {', '.join(unknown)}"
            )
            raise ValueError(msg)
        roles = tuple(str(role) for role in document.get("roles", (ROLE_GUIDANCE,)))
        return cls(
            arm_id=str(document["arm_id"]),
            model=str(document["model"]),
            budget=str(document["budget"]),
            inputs=inputs,
            roles=roles,
        )


@dataclass(frozen=True, slots=True)
class ConfigurationOutcome:
    """Whether a configuration may run, and every reason it may not.

    The harness's comparison shape: the reasons carry the arm's name and
    the requirement it disagrees with, and a report that prints reasons
    instead of numbers is a report a reader cannot skim past.
    """

    #: Whether the configuration satisfies everything the protocol requires.
    admissible: bool
    #: One reason per requirement the configuration fails.
    violations: tuple[str, ...] = ()


def assess_configuration(arms: Sequence[ArmConfiguration]) -> ConfigurationOutcome:
    """Refuse a set of arms that disagree on what the protocol requires.

    The checks, in the order a reader meets them in the protocol:

    1. **The five letters, exactly.** The protocol's arms are A through E;
       a missing letter is an arm that will not be measured, an extra
       letter is an arm the protocol does not define, and either is
       refused.
    2. **One underlying model.** Every arm names the same model, because a
       difference across models measures the models.
    3. **A declared budget.** Every arm declares one; an undeclared budget
       is not a comparable one.
    4. **The additive chain holds.** Each arm's inputs are a strict
       superset of its predecessor's — strict, because an arm whose
       difference set from its predecessor is empty is a letter that
       measures nothing.
    5. **The two contrasts exist.** D vs C and E vs D each pair two arms
       whose input difference is exactly what the protocol says it is.
    """
    violations: list[str] = []
    by_id = {arm.arm_id: arm for arm in arms}
    for letter in ARM_IDS:
        if letter not in by_id:
            violations.append(f"the protocol's arm {letter} is missing from the configuration")
    for arm in arms:
        if arm.arm_id not in ARM_IDS:
            violations.append(f"arm {arm.arm_id!r} is not one of the protocol's five arms")
    if len(by_id) != len(arms):
        violations.append("two arms share one arm_id")

    models = {arm.model for arm in arms}
    if len(models) > 1:
        offenders = sorted(arm.arm_id for arm in arms if arm.model != arms[0].model)
        violations.append(
            "the protocol holds the underlying model fixed, but these arms "
            f"disagree with arm {arms[0].arm_id}: {', '.join(offenders)}"
        )
    elif arms and not arms[0].model:
        violations.append(f"arm {arms[0].arm_id} declares no underlying model")

    for arm in arms:
        if not arm.budget:
            violations.append(f"arm {arm.arm_id} declares no budget to compare")

    for predecessor, successor in pairwise(ARM_IDS):
        prev, succ = by_id.get(predecessor), by_id.get(successor)
        if prev is None or succ is None:
            continue
        missing = sorted(prev.inputs - succ.inputs)
        if missing:
            violations.append(
                f"arm {successor} is missing evidence arm {predecessor} declares: "
                f"{', '.join(missing)}"
            )
        elif prev.inputs == succ.inputs:
            violations.append(
                f"arm {successor} sees exactly what arm {predecessor} sees, "
                f"so the letter {successor} measures nothing"
            )

    for arm in arms:
        if arm.arm_id not in EXPECTED_INPUTS:
            continue
        expected = EXPECTED_INPUTS[arm.arm_id]
        absent = sorted(expected - arm.inputs)
        if absent:
            violations.append(
                f"arm {arm.arm_id} is missing the inputs the protocol's letter "
                f"names: {', '.join(absent)}"
            )
        extra = sorted(arm.inputs - expected)
        if extra:
            violations.append(
                f"arm {arm.arm_id} sees evidence the protocol's letter does not "
                f"name: {', '.join(extra)}"
            )

    for treatment, control in CONTRAST_PAIRS:
        treat, ctrl = by_id.get(treatment), by_id.get(control)
        if treat is None or ctrl is None:
            continue
        difference = sorted(treat.inputs - ctrl.inputs)
        if not difference:
            violations.append(
                f"the contrast {treatment} vs {control} has no input difference, "
                "so it measures nothing"
            )

    return ConfigurationOutcome(admissible=not violations, violations=tuple(violations))


def assess_arrangement_set(arms: Sequence[ArmConfiguration]) -> ConfigurationOutcome:
    """Assess exactly the protocol's B-only / B+C arrangement pair.

    The five-arm set is assessed by :func:`assess_configuration`, which
    requires five distinct letters. The arrangement pair is a separate
    comparison with two configurations of the *same* B evidence and the same
    arm id; it is admissible when every other field is held fixed and only
    the roles differ. Any other shape — including a third configuration or
    a pair over a letter other than B — is refused by name.
    """
    violations: list[str] = []
    if len(arms) != 2:
        violations.append(f"the arrangement pair needs exactly two B variants; got {len(arms)}")
    for arm in arms:
        if arm.arm_id != "B":
            violations.append(f"arm {arm.arm_id!r} is not the protocol's B evidence")
        if arm.inputs != EXPECTED_INPUTS["B"]:
            violations.append(
                f"arm {arm.arm_id!r} does not carry exactly the protocol's B evidence"
            )
    if len(arms) == 2:
        violations.extend(assess_arrangement(arms[0], arms[1]).violations)
    return ConfigurationOutcome(admissible=not violations, violations=tuple(violations))


def arrangement_variants(arm: ArmConfiguration) -> tuple[ArmConfiguration, ArmConfiguration]:
    """The arrangement pair over one arm's evidence: B-only and B+C.

    Both share the arm's evidence, model and budget; the only difference is
    whether the independent critique role reviewed the output. That is what
    makes the comparison a measurement of the arrangement.
    """
    alone = arm
    critiqued = ArmConfiguration(
        arm_id=arm.arm_id,
        model=arm.model,
        budget=arm.budget,
        inputs=arm.inputs,
        roles=(ROLE_GUIDANCE, ROLE_CRITIQUE),
    )
    return alone, critiqued


def assess_arrangement(
    alone: ArmConfiguration, critiqued: ArmConfiguration
) -> ConfigurationOutcome:
    """Refuse an arrangement pair that differs in anything but the roles.

    The protocol's rule for this comparison: same evidence, same underlying
    model, same budget. A pair that differs in any of those measures the
    difference it happened to introduce and calls it the arrangement.
    """
    violations: list[str] = []
    if alone.model != critiqued.model:
        violations.append(
            f"the arrangement pair disagrees on the underlying model "
            f"({alone.arm_id}: {alone.model!r}, {critiqued.arm_id}: {critiqued.model!r})"
        )
    if alone.budget != critiqued.budget:
        violations.append(
            f"the arrangement pair disagrees on the budget "
            f"({alone.arm_id}: {alone.budget!r}, {critiqued.arm_id}: {critiqued.budget!r})"
        )
    if alone.inputs != critiqued.inputs:
        violations.append(
            f"the arrangement pair disagrees on the evidence "
            f"({alone.arm_id} sees {', '.join(sorted(alone.inputs))}; "
            f"{critiqued.arm_id} sees {', '.join(sorted(critiqued.inputs))})"
        )
    if alone.roles == critiqued.roles:
        violations.append(
            "the arrangement pair runs the same roles, so it measures no arrangement at all"
        )
    if ROLE_CRITIQUE not in critiqued.roles:
        violations.append(f"arm {critiqued.arm_id} does not run the independent critique role")
    if ROLE_CRITIQUE in alone.roles:
        violations.append(f"arm {alone.arm_id} is not B-only: it already runs the critique role")
    return ConfigurationOutcome(admissible=not violations, violations=tuple(violations))
