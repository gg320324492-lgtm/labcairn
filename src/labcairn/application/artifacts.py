"""What a task has produced: listing it, and reading one.

An artefact is recorded as an :class:`~labcairn.reports.receipt.ArtifactReceipt`
— the frozen contract — and this layer reads the receipts back rather than the
rows, so a receipt the store cannot load is a receipt nobody may claim to have
produced.

Reading an artefact reads its bytes
-----------------------------------

Listing an artefact's record is one thing and reading the artefact is another,
and the layer does both, because a surface that could read the file itself
would be a surface that could read it *without the policy's verdict*. The
bound on how much is read is the capability's own ``max_bytes`` — the closed
argument model carries it, so the limit is declared in the same place as the
capability rather than in a caller's head.

The bytes are returned beside the receipt rather than in place of it, because
the receipt is the part that says what the artefact *is*: its hash, its
lineage, whether it has gone stale. A caller that has only the bytes cannot
say whether they are current.
"""

from __future__ import annotations

from typing import cast

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.repository import list_artifacts as store_list_artifacts
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.security.capabilities import CapabilityId, FsReadArgs


class ArtifactView(Result):
    """One artefact of a task, as the layer reports it."""

    receipt: ArtifactReceipt
    resource_key: str


class ArtifactContent(Result):
    """An artefact's record and its bytes.

    ``content`` is the bytes as they are on disk. They are not the receipt's
    hash and they are not a rendering of the receipt: a caller that wants to
    know whether the file still matches the receipt compares the two, and a
    layer that returned the hash instead of the bytes would make that
    comparison impossible.
    """

    receipt: ArtifactReceipt
    resource_key: str
    content: bytes


def list_artifacts(context: ApplicationContext) -> tuple[ArtifactView, ...]:
    """The artefacts this task has produced, oldest revision first.

    :raises ApplicationRefusedError: the policy denied listing the task's area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_LIST,
        arguments={"path": area.declared_key, "pattern": "*"},
        resource=area,
    )
    with store_refusals():
        receipts = store_list_artifacts(context.store.session, context.task_id)
    return tuple(
        ArtifactView(receipt=receipt, resource_key=receipt.relative_path) for receipt in receipts
    )


def read_artifact(
    context: ApplicationContext,
    artifact_id: str,
    *,
    max_bytes: int | None = None,
) -> ArtifactContent:
    """One artefact: its receipt and its bytes.

    ``max_bytes`` is the capability's own bound on how much one read may take,
    and it is the capability's argument model that bounds it — the closed
    model refuses a value the registry does not accept. Leaving it unset uses
    the registry's default.

    :raises ApplicationRefusedError: the store holds no artefact with that id,
        the policy denied reading it, the file is not there, or it is larger
        than the capability's own bound.
    """
    with store_refusals():
        receipts = store_list_artifacts(context.store.session, context.task_id)
    receipt = next((item for item in receipts if item.receipt_id == str(artifact_id)), None)
    if receipt is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARTIFACT_NOT_FOUND,
            f"the store holds no artefact with the id {artifact_id!r} for this task.",
        )

    resource = context.resource_for(receipt.relative_path)
    authorisation = consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"max_bytes": max_bytes} if max_bytes is not None else {},
        resource=resource,
    )
    limit = cast(FsReadArgs, authorisation.arguments).max_bytes

    path = resource.real_path
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARTIFACT_NOT_FOUND,
            f"the artefact {receipt.receipt_id!r} is recorded at "
            f"{receipt.relative_path!r}, and its bytes could not be read: {error}. "
            "A receipt whose file is gone describes an artefact that cannot be "
            "produced.",
        ) from error
    if size > limit:
        raise ApplicationRefusedError(
            ApplicationRefusal.LIMITS_EXCEEDED,
            f"the artefact {receipt.receipt_id!r} is {size} bytes, over the {limit} "
            "one read may take. The bound is the capability's own, and it is checked "
            "before a byte is read.",
        )
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARTIFACT_NOT_FOUND,
            f"the artefact {receipt.receipt_id!r} is recorded at "
            f"{receipt.relative_path!r}, and its bytes could not be read: {error}.",
        ) from error
    return ArtifactContent(receipt=receipt, resource_key=resource.resolved_key, content=content)


__all__ = ["ArtifactContent", "ArtifactView", "list_artifacts", "read_artifact"]
