"""The material a task is bound to: listing it, and inspecting one.

A Task binds its material by **content hash**, not by path — the runtime's own
note is that "a path moves, a content hash does not, and binding by path is how
a Task silently ends up describing a different file than it started with". So
"the sources of a task" is the task's own binding, resolved against the
ledger, and the ordering is the binding's own order: the order the researcher
bound them in.

Denied sources are dropped, not refused
---------------------------------------

ADR-0003 §C5 requires bulk listings to *filter* denied entries out of results
rather than refusing the call, because refusing the whole listing discloses
that something is there **and** denies work the operator wanted allowed. A
source the policy denies is therefore absent from the list, and asking for it
by name is refused. The two are different answers on purpose: the list is a
listing, and the single source is a request for one thing.

The layer inventories the ledger; it does not read the material
-----------------------------------------------------------------

Both operations report what the **ledger** holds about a material — its kind,
its hash, its size, and the disclosure that says why it could not be read.
Reading the bytes is a different operation, and the capability registry
already bounds that one (``source.read``'s ``max_bytes``). Inventing a second
reading path here would give the material two ways in.
"""

from __future__ import annotations

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.repository import list_sources as store_list_sources
from labcairn.db.repository import load_source, load_task
from labcairn.security.capabilities import CapabilityId
from labcairn.sources.source import Source


class SourceView(Result):
    """One source of a task, as the layer reports it.

    ``resource_key`` is the key the source's material has **in its own root**,
    which is what a policy rule is matched against. The source's
    ``relative_path`` is workspace-relative and would not match a rule written
    against a source root.
    """

    source: Source
    resource_key: str


def list_sources(context: ApplicationContext) -> tuple[SourceView, ...]:
    """The sources this task is bound to, in the order it bound them.

    :raises ApplicationRefusedError: the task is bound to a source the ledger
        does not hold. That is a broken binding rather than a policy refusal,
        and it is loud on purpose: a silently shorter list would be a task that
        claims a material it cannot produce.
    """
    with store_refusals():
        task = load_task(context.store.session, context.task_id)
        ledger = store_list_sources(context.store.session)
    by_id = {source.source_id: source for source in ledger}

    views: list[SourceView] = []
    for bound in task.bound_source_ids:
        source = by_id.get(str(bound))
        if source is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.SOURCE_NOT_FOUND,
                f"the task is bound to the source {bound}, and the ledger holds no such "
                "row. A task that claims a material the ledger does not hold is a "
                "binding that cannot be honoured.",
            )
        resource = context.resource_for(source.relative_path)
        try:
            consent.evaluate(
                context,
                capability=CapabilityId.SOURCE_INVENTORY,
                arguments={},
                resource=resource,
            )
        except ApplicationRefusedError as error:
            if error.reason is ApplicationRefusal.PERMISSION_DENIED:
                continue
            raise
        views.append(SourceView(source=source, resource_key=resource.resolved_key))
    return tuple(views)


def inspect_source(context: ApplicationContext, source_id: str) -> SourceView:
    """One source, as the ledger holds it.

    :raises ApplicationRefusedError: the ledger holds no such source, or the
        policy denied reading it.
    """
    source = load_source(context.store.session, str(source_id))
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {source_id!r}.",
        )
    resource = context.resource_for(source.relative_path)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resource=resource,
    )
    return SourceView(source=source, resource_key=resource.resolved_key)


__all__ = ["SourceView", "inspect_source", "list_sources"]
