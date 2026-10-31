"""The shapes this service speaks: the refusal body, the request bodies, and
the one panel it composes out of the layer's own objects.

The *response* models are not here, and that is the point. They are the
application layer's own models — ``TaskState``, ``TaskPlan``, ``SourceView``,
``ArtifactView`` and the rest — because §1.4.2's decision is that the CLI and
the API serve the same bytes: *"one serialization, two surfaces"*. A model
defined in this package for the API's convenience would be a second spelling
of what the CLI prints, and the CLI's ``--json`` and this API's body would
drift apart the first time one of them changed.

So the only models here are the ones the API owns outright:

* :class:`RefusalBody` — how a refusal is rendered. It carries exactly the
  two fields the layer's :meth:`~labcairn.application.refusal.ApplicationRefusedError.to_payload`
  produces, so the two refusals — the layer's and a guard's — are the same
  shape on the wire and a script branches on one field either way;
* the request bodies, which are the API's own because the CLI has no request
  bodies to share;
* :class:`SessionInfo` and :class:`Health`, which describe **the service**
  — the token it minted and the address it listens on — and there is no
  layer operation that produces either;
* :class:`Trajectory` and :class:`CommentResponses`, which **compose** the
  layer's own objects into the one panel a workbench draws.

The composed shapes are not a second model
------------------------------------------

:class:`Trajectory` is a bundle, and **every member of it is the layer's own
object**: the comments are ``application.chain``'s, the edits are its, and
the states of the judgements are its. The bundle adds no field of its own
except the one that ties a state to the comment it is about — and that tie
is a *fact the layer's own read does not spell out*, so the API states it
once, in one place, rather than every reader guessing it.

**A composed shape that re-spelled a member would be the defect this module
exists to prevent.** So a member is carried as the layer carries it, and
the composition is the only thing this package adds.

The refusal body is not a copy of the layer's payload
------------------------------------------------------

It is a *model* of a payload the layer already defines, and the test asserts
the two agree: the body of a refusal response equals the layer's
``to_payload()`` exactly. The layer remains the authority on what a refusal
says; this model is only the schema the OpenAPI document can describe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from labcairn.application import ChainComment, ChainEdit
from labcairn.application.models import Result
from labcairn.core.ids import ApprovalId, RunId
from labcairn.evidence.states import EvidenceKind
from labcairn.security.capabilities import CapabilityId


class RefusalBody(Result):
    """A refusal, as the two fields every refusal has.

    ``reason`` is the machine-readable half — the thing a script branches on —
    and ``message`` is the human half, which names what was wrong. The pair
    is the layer's own, so the API's error body and the CLI's error body are
    the same bytes.
    """

    reason: str
    message: str


class ApprovalBody(Result):
    """A request for consent, as the API accepts it.

    The shape is the application layer's :class:`~labcairn.application.approvals.ApprovalRequest`
    flattened for the wire: what it covers (``capability``, ``arguments``,
    ``root_id``, ``resource_key``, ``depends_on``) and when it lapses
    (``expires_at``), plus where the operation lives (``run_id``,
    ``stage_name``).
    """

    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    depends_on: tuple[str, ...] = ()
    expires_at: datetime
    run_id: RunId | None = None
    stage_name: str = "approval"


class ApprovalUseBody(Result):
    """What an approval is spent on, as the API accepts it.

    The same fields as :class:`ApprovalBody` without the expiry: an approval
    was issued for one moment and is spent on one request, and the moment it
    was issued for is the ledger's business rather than the caller's.
    """

    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    depends_on: tuple[str, ...] = ()


class StageBody(Result):
    """A stage run, as the API accepts it.

    The application layer's :class:`~labcairn.application.stages.StageRequest`
    without the work: the *effect* a stage performs belongs to the package
    that owns that effect, and a web request cannot supply one.
    """

    stage_name: str
    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    run_id: RunId | None = None
    approval_id: ApprovalId | None = None
    depends_on: tuple[str, ...] = ()


class AnalysisBody(Result):
    """One figure run, as the API accepts it.

    The six fields are the layer's own request, and all of them are required
    except the operator's parameters: the material's root and key, the
    registered operator, the chart recipe, and **the approval that covers exactly
    this set**. The approval is not inferred and not created here — the service
    has `POST /approvals` for asking and `/approvals/{id}/grant` for answering,
    and a run that could mint its own consent would not be a consented run.
    """

    root_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    recipe: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    approval_id: ApprovalId


class ReportBody(Result):
    """A report render, as the API accepts it.

    The application layer's :class:`~labcairn.application.reports.ReportRequest`,
    field for field, and both are required: **the service takes no default for
    either.** Which key the report lives under and which template it is drawn
    from are the caller's claims, and a default here would be the service making
    them — the same reasoning that keeps a stage's effect out of a web request.
    """

    path: str = Field(min_length=1)
    template_id: str = Field(min_length=1)


class ClaimBody(Result):
    """A claim to record, as the API accepts it.

    The application layer's :class:`~labcairn.application.evidence.ClaimRequest`,
    field for field. ``kind`` is the ledger's own vocabulary rather than a
    string this package translates, so an unknown kind is refused by the model
    that defines the kinds; which fields a kind requires is the record model's
    rule, and the service states it nowhere a second time.
    """

    source_id: str = Field(min_length=1)
    locator_key: str = Field(min_length=1)
    kind: EvidenceKind = EvidenceKind.CLAIM
    text: str | None = None
    span: str | None = None
    value: float | None = None
    unit: str | None = None
    tolerance: float | None = None


class SessionInfo(Result):
    """The session the caller is in, and the token that proves it.

    **This is the one response that carries the token.** The plan's §1.4.4
    records the owner's decision that *"the UI obtains the token through a
    same-origin request"*, and this is that request. The guard that lets it
    through is the origin check, so a page on another site cannot read it: a
    cross-origin read is blocked by the browser, and a cross-origin *request*
    is refused here with ``origin_refused``.

    Everywhere else the token stays out of the response, out of the events and
    out of the log, and the tests assert it.
    """

    token: str
    #: Where the token was written, so the CLI can tell the user where it is.
    path: str


class Health(Result):
    """What the service says about itself, without saying anything secret.

    Deliberately dull: the address it listens on, the origins it answers to
    and the task it is about. It is the one response a person may read aloud,
    so it carries no token and no credential of any kind.
    """

    status: str
    host: str
    port: int
    origins: tuple[str, ...]
    task_id: str


class CommentResponses(Result):
    """The judgements on one comment, and the states they hold.

    **The states belong to the comment they are about.** The layer's read
    answers with the states themselves, so a caller that wanted to know
    which comment a state belonged to would have to ask again — and asking
    again is how a reader ends up with two answers to one question.
    """

    feedback_id: str
    states: tuple[str, ...]


class Trajectory(Result):
    """The advisor's comments, the edits that answer them, and the responses.

    **Every member is the application layer's own object.** The comments are
    :class:`~labcairn.application.chain.ChainComment`, the edits are
    :class:`~labcairn.application.chain.ChainEdit`, and the states are the
    layer's own — so a workbench that draws this panel draws the chain, and
    not a second spelling of it.
    """

    comments: tuple[ChainComment, ...]
    edits: tuple[ChainEdit, ...]
    responses: tuple[CommentResponses, ...]


__all__ = [
    "AnalysisBody",
    "ApprovalBody",
    "ApprovalUseBody",
    "ClaimBody",
    "CommentResponses",
    "Health",
    "RefusalBody",
    "ReportBody",
    "SessionInfo",
    "StageBody",
    "Trajectory",
]
