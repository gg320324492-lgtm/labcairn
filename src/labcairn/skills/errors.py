"""Every way a stage can be refused, as a distinct type.

Why these are exception classes and not a ``(ok, reason)`` pair
---------------------------------------------------------------
A guard that returns a value can be ignored by the caller that was supposed to
honour it, and the failure mode is silent: the stage proceeds, and the check
that would have stopped it is still sitting right there in the source. Raising
means the only way past a guard is to catch it, and a catch that does not
re-raise has to say so in its own ``except`` clause.

The split below is the one that matters operationally, and it mirrors
:class:`~labcairn.runtime.lifecycle.StageStatus`:

* :class:`StageContractError` — the stage **did** run and produced something
  this orchestrator will not accept. Retrying the same inputs will produce the
  same thing, so the orchestrator does not retry it: it fails the stage.
* :class:`StageBlockedError` — the stage **cannot** proceed until a human or an
  external system does something. Nothing failed; the run is parked.
* :class:`SkillBudgetError` — a declared limit was reached. Also not a failure
  of the work, and also not retryable by this orchestrator.

The base class exists so a caller that wants "the run stopped" can catch
``SkillError`` without having to enumerate the reasons, which is the same thing
:meth:`~labcairn.runtime.lifecycle.Stage` does with ``blocked_reason``.
"""

from __future__ import annotations


class SkillError(Exception):
    """Base for everything the skill layer refuses."""


class SkillDeclarationError(SkillError, ValueError):
    """The skill declaration itself is inconsistent.

    Raised at import/registration time rather than at run time: a stage that
    consumes an artifact no earlier stage produces, or two stages that produce
    the same artifact kind, is a defect in the declaration and is caught before
    any work starts.
    """


class StageContractError(SkillError):
    """A stage returned something the orchestrator will not accept.

    Covers all four acceptance rules for what may cross a stage boundary:
    wrong type, content that does not descend from what was handed in, output
    that is a placeholder, and output whose references do not close over its
    inputs. Each has its own subclass so a test — and a reader of an event log —
    can tell them apart.
    """


class ArtifactTypeError(StageContractError):
    """The artifact handed to a stage was not the declared type for that port."""


class LineageError(StageContractError):
    """An artifact's ``derived_from`` did not match what it was actually built on.

    This is the check that makes *"every stage consumes actual previous
    artifacts"* mean something. A stage that ignores its inputs, or an artifact
    injected from outside the ledger, names the wrong ancestors; both are caught
    here. A stage that produced a well-formed artifact from nothing in
    particular cannot pass, because "nothing in particular" is not the set the
    orchestrator handed over.
    """


class PlaceholderError(StageContractError):
    """The artifact is structurally valid but says nothing.

    Empty required collections, fields holding only placeholder text, and bodies
    too short to carry a claim are all rejected. See
    :mod:`labcairn.skills.quality` for the definition and why it is written the
    way it is.
    """


class DerivationClosureError(StageContractError):
    """The artifact references ids that do not exist upstream.

    A draft citing a claim id no evidence stage produced, or a delivered report
    whose ``draft_digest`` is not the draft this run built, is a report that is
    about something other than what was verified. The reference graph has to
    close over the inputs, or the content relationship between stages is
    decorative.
    """


class ArtifactSubstitutedError(SkillError):
    """A recorded artifact's bytes no longer hash to the digest recorded for it.

    Detected on read: the ledger recomputes the canonical digest and compares.
    This is the guard against an artifact being swapped *after* it was accepted,
    which no amount of checking at write time can catch.
    """


class ApprovalRequiredError(SkillError):
    """A stage requiring an approval was entered without one.

    Raised when something tries to enter the guarded stage directly rather than
    through :meth:`~labcairn.skills.execution.Orchestrator.run`. The orchestrator
    itself parks the stage as ``BLOCKED`` instead of raising, because parking is
    the graceful behaviour; raising is what happens to a caller that tries to
    route around it.
    """


class StaleApprovalError(ApprovalRequiredError):
    """An approval exists but does not cover what is about to be done.

    The proposal changed, an uncovered item became significant, or the approval
    expired. All three are the same refusal with different causes, and none of
    them is repaired by retrying.
    """


class SkillBudgetError(SkillError):
    """A declared budget limit was reached.

    Not a stage failure: the work did not fail, the run ran out of its declared
    allowance. Callers that want to raise the limit and continue should do so
    by declaring a new budget, not by catching this and retrying.
    """


__all__ = [
    "ApprovalRequiredError",
    "ArtifactSubstitutedError",
    "ArtifactTypeError",
    "DerivationClosureError",
    "LineageError",
    "PlaceholderError",
    "SkillBudgetError",
    "SkillDeclarationError",
    "SkillError",
    "StageContractError",
    "StaleApprovalError",
]
