"""The diagnostics package: an allowlist of facts, minted or refused.

LC-P3-07 deliverable 2 (work orders §12 §5.4: *"the diagnostics packaging
surface and its de-identification witness: local, de-identified diagnostics:
what is collected, what is proven absent"*, and §5.6 deliverable 2: *"with a
witness asserting what is collected and what is proven absent from the
package"*).

**An allowlist, not a dump.** A field is in the package because the allowlist
below names it and says why; a field not on the list is not collected, not
"collected then filtered". This is the move :class:`~labcairn.providers.errors.ProviderFailure`
made at one failed call applied to the whole product surface — a field that
*could* hold arbitrary text is a field a future caller will fill from
``str(exc)``.

**What is proven absent.** The package carries no source material, no excerpt,
no rendered prompt, no credential value, no provider's raw error text, no
absolute path into a source root, and no long verbatim or Han run of the
task's material. The absence is asserted by construction: the only constructor
is :func:`collect_diagnostics`, and it verifies before it mints — the same
type-level trick :class:`~labcairn.providers.deidentify.DeidentifiedCase`
uses, so a package that skipped verification has no representation.

The verification reuses :mod:`labcairn.providers.deidentify`'s checking half
(the caller replaces, this module verifies — and here there is nothing to
replace, because the collector never reads material text at all). The shape
checks run in the same order as ``redact_case``: run-length, named secrets,
final scrub.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Final

from labcairn.core.ids import TaskId
from labcairn.providers.deidentify import (
    GRAM_WINDOW,
    HAN_RUN_CEILING,
    DeidentificationRefusedError,
    DeidentificationPipeline,
)

if TYPE_CHECKING:
    from labcairn.application.context import ApplicationContext
    from labcairn.db.repository import TaskStore
    from labcairn.providers.bounded_run import RunRecord
    from labcairn.providers.errors import ProviderFailure
    from labcairn.runtime.event import Event
    from labcairn.runtime.operation import Operation
    from labcairn.reports.receipt import ArtifactReceipt

__all__ = [
    "DIAGNOSTICS_FORMAT_VERSION",
    "DiagnosticsPackage",
    "DiagnosticsRefusedError",
    "EventFact",
    "FileFact",
    "OperationFact",
    "RefusalFact",
    "collect_diagnostics",
]


#: The package format's own version. A reader refuses a format it does not
#: know rather than guessing at unknown fields — the same closed-vocabulary
#: rule the event envelope applies.
DIAGNOSTICS_FORMAT_VERSION: Final[int] = 1


class DiagnosticsRefusedError(Exception):
    """The package was not produced. The refusal names the check that failed.

    Distinct from "collected then filtered": a field whose text fails
    verification refuses the *whole* package, because a caller that ships the
    fields that passed is a caller that has learned to ship around the refusal
    — :meth:`DeidentificationPipeline.redact_case`'s own reasoning, at package
    scale.
    """


# --------------------------------------------------------------------------- #
# the allowlist, as data
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EventFact:
    """One ledger event, as the package may hold it.

    A transition's names and a UTC moment. No payload, no free text: the
    ordering question a supporter asks is answered by ``seq`` and the event's
    name, and nothing else about an event is diagnosable without carrying
    content.
    """

    seq: int
    type: str
    occurred_at: str  #: ISO-8601 UTC
    from_state: str | None = None
    to_state: str | None = None


@dataclass(frozen=True, slots=True)
class OperationFact:
    """One operation, as the package may hold it.

    State, capability and address — the recovery questions
    :func:`labcairn.application.recovery.describe_abandoned` answers — plus
    the digests, never the arguments themselves.
    """

    operation_id: str
    state: str
    capability: str
    resource_key: str
    args_digest: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FileFact:
    """One output-area file, as the package may hold it.

    ``relative_path`` is relative to the task output area (row 9 of the
    design's allowlist): an absolute path names a person's directory, and a
    path outside the output area is not a file fact at all.
    """

    relative_path: str
    content_sha256: str
    size_bytes: int
    kind: str
    revision: int


@dataclass(frozen=True, slots=True)
class RefusalFact:
    """One refusal or typed provider failure, as the package may hold it.

    The provider half embeds :meth:`ProviderFailure.to_wire`'s exact output —
    kind, retryable, user_action, detail_digest, message — and nothing added.
    The application-refusal half names the refusal and its message; the
    message is LabCairn-authored by construction
    (:class:`~labcairn.application.refusal.ApplicationRefusedError` is raised
    from fixed strings in ``src/``, never from a third-party ``str(exc)``).
    """

    source: str  #: ``"application_refusal"`` or ``"provider_failure"``
    kind: str
    message: str
    retryable: bool | None = None
    user_action: str | None = None
    detail_digest: str | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticsPackage:
    """What a supporter gets, and everything that is proven absent.

    Frozen and closed: the fields below are the allowlist. A caller that wants
    a sixth field edits this class, the collector and the witness together —
    the same edit-and-review cost :class:`~labcairn.providers.bounded_run.RunRecord`'s
    frozen counts impose, deliberately.

    Everything here is digests, counts, names and UTC moments. The absence of
    the material is a property of the field list, verified by
    :func:`collect_diagnostics` before any instance exists.
    """

    format_version: int
    created_at: str  #: ISO-8601 UTC
    #: Build identity (allowlist row 1).
    product_version: str
    schema_revision: str | None
    platform_name: str
    #: Task identity (row 2): the id only, never the task's title or goal.
    task_id: str
    #: Operation states (row 3).
    operations: tuple[OperationFact, ...] = ()
    #: Provider failures (row 4), as ``to_wire`` rendered them.
    failures: tuple[RefusalFact, ...] = ()
    #: Application refusals (row 8), name plus the LabCairn-authored remedy.
    refusals: tuple[RefusalFact, ...] = ()
    #: Bounded-run counts (row 5).
    run_counts: MappingCounts = field(default_factory=dict)
    #: Capability probe verdicts (row 6).
    capability_verdicts: tuple[tuple[str, str], ...] = ()
    #: Credential fingerprints (row 7) — never values.
    credential_fingerprints: tuple[str, ...] = ()
    #: File facts inside the task output area (row 9).
    files: tuple[FileFact, ...] = ()
    #: Time facts (row 10): the events already recorded, as names and moments.
    events: tuple[EventFact, ...] = ()


#: The counts-only view of a run record, keyed by name. A plain alias keeps the
#: package's own type honest without importing the run module at runtime.
MappingCounts = dict[str, int]


# --------------------------------------------------------------------------- #
# the verification, shared with the de-identification pipeline
# --------------------------------------------------------------------------- #


def _verify_no_material_grams(
    package_label: str, forbidden_grams: set[str], texts: tuple[tuple[str, str], ...]
) -> None:
    """Refuse any rendering that still carries a run of the material.

    The same run-length check ``redact_case`` runs, applied to every text
    field the package carries. ``texts`` is a sequence of ``(where, text)``
    pairs so the refusal names the field rather than the content.
    """
    from labcairn.providers.deidentify import _word_grams

    for where, text in texts:
        surviving = forbidden_grams & _word_grams(text)
        if surviving:
            raise DiagnosticsRefusedError(
                f"{package_label}: {where} still carries a {GRAM_WINDOW}-word run of "
                f"the material ({len(surviving)} such run(s)); the package is not "
                "de-identified"
            )
        han = _long_han_runs(text)
        if han:
            raise DiagnosticsRefusedError(
                f"{package_label}: {where} still carries a Han run of "
                f"{HAN_RUN_CEILING}+ characters ({len(han)} such run(s)); the "
                "package is not de-identified"
            )


def _long_han_runs(text: str) -> list[str]:
    """Han runs of ``HAN_RUN_CEILING`` characters or more."""
    runs: list[str] = []
    current: list[str] = []
    for character in text:
        if "一" <= character <= "鿿":
            current.append(character)
        else:
            if len(current) >= HAN_RUN_CEILING:
                runs.append("".join(current))
            current = []
    if len(current) >= HAN_RUN_CEILING:
        runs.append("".join(current))
    return runs


def _verify_no_named_secret(
    package_label: str, secrets: tuple[str, ...], texts: tuple[tuple[str, str], ...]
) -> None:
    """Refuse any rendering that still carries a secret the caller named."""
    for where, text in texts:
        for secret in secrets:
            if secret and len(secret) >= 8 and secret in text:
                raise DiagnosticsRefusedError(
                    f"{package_label}: {where} still carries a registered secret; "
                    "the package is not de-identified"
                )


# --------------------------------------------------------------------------- #
# the collector
# --------------------------------------------------------------------------- #


def collect_diagnostics(
    context: ApplicationContext,
    *,
    material_texts: tuple[str, ...] = (),
    secrets: tuple[str, ...] = (),
    store: TaskStore | None = None,
    run_record: RunRecord | None = None,
    failures: tuple[ProviderFailure, ...] = (),
    refusals: tuple[tuple[str, str], ...] = (),
    capability_verdicts: tuple[tuple[str, str], ...] = (),
    credential_fingerprints: tuple[str, ...] = (),
    now: datetime | None = None,
) -> DiagnosticsPackage:
    """Collect the package, and refuse rather than mint an unsafe one.

    ``material_texts`` are the renderings of the task's material the caller
    knows (the excerpts' source text, the material itself). The package's own
    fields never carry them, but the verification needs them to prove their
    absence from the fields that exist — a package verified against no
    material would be a package whose absence claims were untested.

    ``refusals`` are ``(kind, message)`` pairs the caller recorded; their
    messages are LabCairn-authored refusal prose. ``failures`` are provider
    failures; the package embeds ``to_wire()``'s output unchanged.

    The one constructor. A package that skipped this function has no
    representation — the dataclass is buildable in principle (Python has no
    private constructors), but every witness in
    ``tests/test_diagnostics_package.py`` asserts the *collected* shape, and a
    hand-built instance is a different object from a verified one.
    """
    from labcairn.db.repository import events_after, list_artifacts, list_operations

    moment = now if now is not None else datetime.now(timezone.utc)
    label = f"diagnostics for task {context.task_id}"

    # -- collect ------------------------------------------------------------- #
    active_store = store if store is not None else context.store
    with_store = active_store.session

    operations = tuple(
        OperationFact(
            operation_id=str(operation.operation_id),
            state=operation.state.value,
            capability=operation.capability,
            resource_key=operation.resource_key,
            args_digest=operation.args_digest,
            depends_on=tuple(operation.depends_on),
        )
        for operation in list_operations(with_store, context.task_id)
    )

    events = tuple(
        EventFact(
            seq=event.seq,
            type=event.type.value,
            occurred_at=event.occurred_at.astimezone(timezone.utc).isoformat(),
            from_state=(
                event.transition.from_state if event.transition is not None else None
            ),
            to_state=(event.transition.to_state if event.transition is not None else None),
        )
        for event in events_after(with_store, context.task_id)
    )

    artifacts: tuple[ArtifactReceipt, ...] = list_artifacts(with_store, context.task_id)
    files = tuple(
        FileFact(
            relative_path=artifact.relative_path,
            content_sha256=artifact.content_sha256,
            size_bytes=artifact.size_bytes,
            kind=artifact.kind.value,
            revision=artifact.revision,
        )
        for artifact in artifacts
    )

    failure_facts = tuple(
        RefusalFact(
            source="provider_failure",
            kind=failure.kind.value,
            message=failure.message,
            retryable=failure.retryable,
            user_action=failure.user_action,
            detail_digest=failure.detail_digest,
        )
        for failure in failures
    )
    refusal_facts = tuple(
        RefusalFact(source="application_refusal", kind=kind, message=message)
        for kind, message in refusals
    )

    counts: MappingCounts = (
        dict(run_record.to_counts()) if run_record is not None else {}
    )

    # -- verify before minting ---------------------------------------------- #
    from labcairn.providers.deidentify import _word_grams

    forbidden = _word_grams(" ".join(material_texts)) if material_texts else set()
    rendered: tuple[tuple[str, str], ...] = (
        *[(f"refusal {index}", fact.message) for index, fact in enumerate(refusal_facts)],
        *[(f"failure {index}", fact.message) for index, fact in enumerate(failure_facts)],
    )
    _verify_no_material_grams(label, forbidden, rendered)
    _verify_no_named_secret(label, secrets, rendered)

    # The final scrub runs too — but it *reports* rather than rewrites, because
    # the design says a package is refused at mint time, not blanked out. A
    # credential-shaped run in a LabCairn-authored message is a bug in the
    # message, and the witness watches for it.
    pipeline = DeidentificationPipeline()
    for secret in secrets:
        pipeline.redactor.register(secret)
    for where, text in rendered:
        if pipeline.redactor.contains_secret(text):
            raise DiagnosticsRefusedError(
                f"{label}: {where} still carries credential-shaped text after the "
                "final scrub; the package is not de-identified"
            )

    return DiagnosticsPackage(
        format_version=DIAGNOSTICS_FORMAT_VERSION,
        created_at=moment.astimezone(timezone.utc).isoformat(),
        product_version=_product_version(),
        schema_revision=_schema_revision(with_store),
        platform_name=platform.platform(),
        task_id=str(context.task_id),
        operations=operations,
        failures=failure_facts,
        refusals=refusal_facts,
        run_counts=counts,
        capability_verdicts=tuple(capability_verdicts),
        credential_fingerprints=tuple(credential_fingerprints),
        files=files,
        events=events,
    )


def _product_version() -> str:
    from labcairn import __version__

    return __version__


def _schema_revision(session: Any) -> str | None:
    """The alembic revision the store is stamped at, read from its own session.

    Read from the session the collector already holds, so the diagnostic and
    the task read the same database state rather than racing a second engine
    against a live writer.
    """
    from sqlalchemy import text

    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception:  # pragma: no cover - a diagnostic reports, it does not raise
        return None
    return str(row[0]) if row is not None else None


def to_json_dict(package: DiagnosticsPackage) -> dict[str, Any]:
    """The JSON-ready form. Field names are the allowlist's names."""
    return {
        "format_version": package.format_version,
        "created_at": package.created_at,
        "product_version": package.product_version,
        "schema_revision": package.schema_revision,
        "platform": package.platform_name,
        "task_id": package.task_id,
        "operations": [
            {
                "operation_id": op.operation_id,
                "state": op.state,
                "capability": op.capability,
                "resource_key": op.resource_key,
                "args_digest": op.args_digest,
                "depends_on": list(op.depends_on),
            }
            for op in package.operations
        ],
        "failures": [_refusal_json(fact) for fact in package.failures],
        "refusals": [_refusal_json(fact) for fact in package.refusals],
        "run_counts": dict(package.run_counts),
        "capability_verdicts": [
            {"capability": name, "verdict": verdict}
            for name, verdict in package.capability_verdicts
        ],
        "credential_fingerprints": list(package.credential_fingerprints),
        "files": [
            {
                "relative_path": fact.relative_path,
                "content_sha256": fact.content_sha256,
                "size_bytes": fact.size_bytes,
                "kind": fact.kind,
                "revision": fact.revision,
            }
            for fact in package.files
        ],
        "events": [
            {
                "seq": fact.seq,
                "type": fact.type,
                "occurred_at": fact.occurred_at,
                "from_state": fact.from_state,
                "to_state": fact.to_state,
            }
            for fact in package.events
        ],
    }


def _refusal_json(fact: RefusalFact) -> dict[str, Any]:
    return {
        "source": fact.source,
        "kind": fact.kind,
        "message": fact.message,
        "retryable": fact.retryable,
        "user_action": fact.user_action,
        "detail_digest": fact.detail_digest,
    }
