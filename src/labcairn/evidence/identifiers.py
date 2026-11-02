"""Scholarly identifiers: recorded as data, resolved as a state, never a check.

The half of LC-P1-09's acceptance clause that was never built: **no record
could carry an identifier, nothing resolved one, and ingestion recorded
none**. A report cited locators only -- which is ADR-0004's contract, not a
shortcut -- but a claim whose support names a DOI had nowhere to put that DOI,
and a reader was never told whether anyone had resolved it.

Three closed vocabularies
-------------------------

:class:`IdentifierScheme`
    What kind of identifier it is. Two members -- a DOI and an arXiv id --
    because those are the two the work order names, and a third would be a
    guess at what a future resolver wants. Closed for the reason every
    enumeration here is closed: a coercion rule turns a typo in a persisted
    row into a value that reads as valid and is not.

:class:`IdentifierProvenance`
    Who supplied it: the ingestion machinery, a named person, or a model. The
    third member is the one the work order is about: **a model may propose an
    identifier, and proposing is not checking** -- the same rule
    :class:`~labcairn.evidence.states.EvidenceCreator.MODEL_PROPOSAL` already
    applies to a proposed record. Nothing downstream may read a model-supplied
    identifier as evidence that the citation was checked.

:class:`ResolutionState`
    Whether anyone resolved it, and resolution is **a state, not a failure**:

    * ``unresolved`` -- nobody has. The state a freshly recorded identifier
      holds, and a first-class answer, not an error to be swallowed.
    * ``not_attempted`` -- somebody asked for a resolution and the build
      recorded that it did not look. Resolving a scholarly identifier means
      contacting an external service, and this build cannot consent an
      outbound lookup: the closed capability registry
      (:class:`~labcairn.security.capabilities.CapabilityId`) defines exactly
      one network-effect capability, ``model.request``, which is consent to
      send a prompt to a provider and consent to nothing else, and the bridge
      ADR-0006 describes between the two capability vocabularies is unbuilt.
      So an outbound lookup is recorded as **not attempted** rather than
      silently sent or silently dropped.
    * ``resolved`` -- a named resolver answered, with the detail of what it
      found. Reached only by :func:`confirm_resolution`; a resolution already
      made is not unwritten, because it is a statement about the world that
      other readers may have acted on.

The two axes are deliberately separate
--------------------------------------
An identifier's **resolution** and a record's **verification** are different
questions, and this module keeps them in different vocabularies on purpose:
``ResolutionState`` has no "verified" member and :data:`VERIFICATION_STATES`
has no "resolved" member. Nothing that happens to an identifier -- not even a
person confirming one -- writes to a record's ``verification_log`` or moves a
record's status, so no sequence of identifier events can mark a citation as
checked. That is structural, not conventional: the functions below have no
parameter that names a record, and the ones that change a state take and
return identifiers only.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.sources.primitives import NonEmptyText

__all__ = [
    "IdentifierError",
    "IdentifierNotFoundError",
    "IdentifierProvenance",
    "IdentifierScheme",
    "ResolutionState",
    "ScholarlyIdentifier",
    "confirm_resolution",
    "load_identifier",
    "load_task_identifiers",
    "put_identifier",
    "request_resolution",
]


class IdentifierError(RuntimeError):
    """A refusal about an identifier, with the rule named in the message."""


class IdentifierNotFoundError(IdentifierError):
    """No identifier with that id."""


class IdentifierScheme(StrEnum):
    """What kind of scholarly identifier it is. Closed; see the module docstring."""

    #: A Digital Object Identifier, recorded as printed (``10.xxxx/suffix``).
    DOI = "doi"
    #: An arXiv identifier, recorded without its scheme prefix (``YYMM.NNNNN``).
    ARXIV = "arxiv"


class IdentifierProvenance(StrEnum):
    """Who supplied the identifier. Closed; see the module docstring."""

    #: The ingestion machinery found it in the material's own metadata.
    INGESTION = "ingestion"
    #: A named person supplied it. The name is ``supplied_by_id``.
    PERSON = "person"
    #: A model proposed it. **Proposing is not checking** -- see the module
    #: docstring. The run that proposed it is ``supplied_by_id``.
    MODEL = "model"


class ResolutionState(StrEnum):
    """Whether anyone has resolved the identifier. Closed; see the module docstring."""

    #: Nobody has resolved it. A first-class answer, not an error.
    UNRESOLVED = "unresolved"
    #: A resolution was requested and recorded as not attempted, because this
    #: build cannot consent an outbound lookup.
    NOT_ATTEMPTED = "not_attempted"
    #: A named resolver answered, and the row says what it found.
    RESOLVED = "resolved"


class ScholarlyIdentifier(BaseModel):
    """One identifier, as data, with its provenance and its resolution state.

    The resolution fields obey the same discipline as a record's ``unit``:
    declared, never inferred. A state that says something happened carries the
    evidence of it -- ``not_attempted`` says *why* no lookup was made, and
    ``resolved`` names who answered, what they found and when -- and
    ``unresolved`` carries none of them, because nothing has happened yet. A
    state whose fields disagree with it is refused at construction, in every
    path, including a hand-written SQL row (the schema repeats the rule).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_id: NonEmptyText
    #: Identifiers are held per task, as evidence records are: a local-first
    #: store has no global shelf, and a claim cites what its task holds.
    task_id: NonEmptyText
    scheme: IdentifierScheme
    #: The identifier as supplied, not normalised beyond the scheme's own
    #: spelling. A resolver that quietly canonicalised ``10.1234/A`` to
    #: lowercase would be resolving a different identifier than the one the
    #: source printed.
    value: NonEmptyText
    supplied_by: IdentifierProvenance
    #: The person's id, the ingestion run's id or the model run's id -- never
    #: empty, so an identifier always names where it came from.
    supplied_by_id: NonEmptyText
    resolution_state: ResolutionState
    resolution_detail: NonEmptyText | None = None
    resolved_by: NonEmptyText | None = None
    resolved_at: AwareDatetime | None = None
    created_at: AwareDatetime

    def is_resolved(self) -> bool:
        """Whether a resolver has answered. The one question the report asks."""
        return self.resolution_state is ResolutionState.RESOLVED

    @property
    def resolved_at_sqlite(self) -> str | None:
        """``resolved_at`` in the shape the column stores."""
        return None if self.resolved_at is None else self.resolved_at.isoformat()

    @property
    def created_at_sqlite(self) -> str:
        """``created_at`` in the shape the column stores."""
        return self.created_at.isoformat()

    @model_validator(mode="after")
    def _state_carries_what_it_names(self) -> Self:
        """A state says what happened; the fields are the evidence it happened.

        ``unresolved`` carries none of the three fields, because nothing has
        happened yet; ``not_attempted`` says *why* no lookup was made and by
        nobody, so ``resolved_by`` and ``resolved_at`` stay empty; ``resolved``
        names who answered, what they found and when. A state whose fields
        disagree with it is not a state, so it is refused here rather than
        stored for a reader to trip over.
        """
        if self.resolution_state is ResolutionState.UNRESOLVED:
            if (
                self.resolution_detail is not None
                or self.resolved_by is not None
                or self.resolved_at is not None
            ):
                raise ValueError(
                    "an unresolved identifier carries no resolution detail, resolver"
                    " or resolution time: nothing has happened to it yet. Detail"
                    " written before a state that explains it is a record nobody can"
                    " read back truthfully"
                )
            return self
        if self.resolution_state is ResolutionState.NOT_ATTEMPTED:
            if self.resolution_detail is None:
                raise ValueError(
                    "a not_attempted identifier must say why no lookup was made."
                    " A recorded refusal with no reason recorded is the one thing"
                    " worse than no refusal at all"
                )
            if self.resolved_by is not None or self.resolved_at is not None:
                raise ValueError(
                    "a not_attempted identifier carries no resolver and no resolution"
                    " time: it says a lookup did not happen, and a row that names a"
                    " resolver says it did"
                )
            return self
        if self.resolution_detail is None or self.resolved_by is None or self.resolved_at is None:
            raise ValueError(
                "a resolved identifier names who resolved it, what they found and"
                " when: a resolution without its detail is a 'verified' nobody can"
                " audit, which is the shape of the defect LC-P1-09's review found"
            )
        return self


def put_identifier(connection: Connection, identifier: ScholarlyIdentifier) -> None:
    """Persist an identifier, whole, or not at all.

    The ``(task_id, scheme, value)`` triple is unique, so the same identifier
    is recorded once per task: a second row for the same identifier would make
    "is this resolved?" answerable two ways. The constraint is what makes the
    answer true under two concurrent writers; the pre-check only turns the
    refusal into a message that names the row already there.
    """
    existing = connection.execute(
        sql_text(
            "SELECT identifier_id FROM identifier_records"
            " WHERE task_id = :tid AND scheme = :scheme AND value = :value"
        ),
        {"tid": identifier.task_id, "scheme": identifier.scheme.value, "value": identifier.value},
    ).scalar()
    if existing is not None:
        raise IdentifierError(
            f"task {identifier.task_id!r} already holds the {identifier.scheme.value}"
            f" identifier {identifier.value!r} as {existing!r}. One identifier, one"
            " row: a second row for it would make 'is it resolved' answerable"
            " two ways"
        )
    connection.execute(
        sql_text(
            "INSERT INTO identifier_records (identifier_id, task_id, scheme, value,"
            " supplied_by, supplied_by_id, resolution_state, resolution_detail,"
            " resolved_by, resolved_at, created_at)"
            " VALUES (:iid,:tid,:scheme,:value,:by,:byid,:state,:detail,:rby,:rat,:now)"
        ),
        {
            "iid": identifier.identifier_id,
            "tid": identifier.task_id,
            "scheme": identifier.scheme.value,
            "value": identifier.value,
            "by": identifier.supplied_by.value,
            "byid": identifier.supplied_by_id,
            "state": identifier.resolution_state.value,
            "detail": identifier.resolution_detail,
            "rby": identifier.resolved_by,
            "rat": identifier.resolved_at_sqlite,
            "now": identifier.created_at_sqlite,
        },
    )


def load_identifier(connection: Connection, identifier_id: str) -> ScholarlyIdentifier | None:
    """Read an identifier back, or ``None`` if there is no such id."""
    row = connection.execute(
        sql_text(
            "SELECT identifier_id, task_id, scheme, value, supplied_by, supplied_by_id,"
            " resolution_state, resolution_detail, resolved_by, resolved_at, created_at"
            "  FROM identifier_records WHERE identifier_id = :iid"
        ),
        {"iid": identifier_id},
    ).fetchone()
    if row is None:
        return None
    return ScholarlyIdentifier.model_validate(
        {
            "identifier_id": row[0],
            "task_id": row[1],
            "scheme": row[2],
            "value": row[3],
            "supplied_by": row[4],
            "supplied_by_id": row[5],
            "resolution_state": row[6],
            "resolution_detail": row[7],
            "resolved_by": row[8],
            "resolved_at": row[9],
            "created_at": row[10],
        }
    )


def load_task_identifiers(connection: Connection, task_id: str) -> tuple[ScholarlyIdentifier, ...]:
    """Every identifier a task holds, in a stable order.

    Ordered by creation time and then by id, the way
    :func:`labcairn.evidence.store.load_task_records` orders records: the order
    is for a stable rendering, not a ranking.
    """
    ids: list[str] = list(
        connection.execute(
            sql_text(
                "SELECT identifier_id FROM identifier_records WHERE task_id = :tid"
                " ORDER BY created_at, identifier_id"
            ),
            {"tid": task_id},
        ).scalars()
    )
    identifiers: list[ScholarlyIdentifier] = []
    for identifier_id in ids:
        identifier = load_identifier(connection, str(identifier_id))
        if identifier is not None:  # pragma: no cover - the row was read a moment ago
            identifiers.append(identifier)
    return tuple(identifiers)


def request_resolution(
    connection: Connection,
    identifier_id: str,
    *,
    detail: str,
    requested_at: datetime,
) -> ScholarlyIdentifier:
    """Record that a resolution was requested and **not attempted**.

    This is the honest answer to "resolve this", and the only one this build
    can give: resolving a scholarly identifier means contacting an external
    service, this build cannot consent an outbound lookup (the closed
    capability registry defines no identifier-lookup capability, and
    ``model.request`` is consent to prompt a provider, not to query Crossref),
    and a request that cannot be consented is recorded rather than silently
    sent or silently dropped. *detail* says why the caller asked, and the
    function appends the boundary's own reason to it, so the row a reader sees
    names the rule and not merely the caller's wish. *requested_at* dates the
    request; it is passed in rather than read, so that "when was this asked"
    is a fact and not a re-derivation.

    The caller asks for an outbound lookup; nothing here performs one. The
    function has no parameter that could hold a response, and no code path
    that leaves this module's own tables.
    """
    identifier = load_identifier(connection, identifier_id)
    if identifier is None:
        raise IdentifierNotFoundError(f"no identifier with id {identifier_id!r}")
    if identifier.resolution_state is ResolutionState.RESOLVED:
        raise IdentifierError(
            f"the identifier {identifier_id!r} is already resolved by"
            f" {identifier.resolved_by!r}. A resolution is not unwritten to make"
            " room for another request"
        )
    boundary_reason = (
        "outbound identifier lookup not attempted: resolving a scholarly"
        " identifier means contacting an external service, and this build cannot"
        " consent an outbound lookup (the closed capability registry defines no"
        " identifier-lookup capability; ADR-0006's bridge is unbuilt). The"
        " request is recorded, not sent"
    )
    full_detail = f"{detail} -- {boundary_reason}"
    updated = connection.execute(
        sql_text(
            "UPDATE identifier_records SET resolution_state = :state,"
            " resolution_detail = :detail, resolved_by = NULL, resolved_at = NULL"
            " WHERE identifier_id = :iid AND resolution_state != 'resolved'"
        ),
        {"state": ResolutionState.NOT_ATTEMPTED.value, "detail": full_detail, "iid": identifier_id},
    )
    if updated.rowcount != 1:  # pragma: no cover - guarded by the read above
        raise IdentifierError(f"the identifier {identifier_id!r} could not be updated")
    result = load_identifier(connection, identifier_id)
    if result is None:  # pragma: no cover - the row was read a moment ago
        raise IdentifierNotFoundError(f"no identifier with id {identifier_id!r}")
    return result


def confirm_resolution(
    connection: Connection,
    identifier_id: str,
    *,
    resolved_by: str,
    detail: str,
    resolved_at: datetime,
) -> ScholarlyIdentifier:
    """Record that a named resolver answered, with what it found.

    The resolver is a person who checked the identifier by hand (or a future
    consented lookup, which would arrive through the consent layer with its
    own provenance); what the resolver found is *detail*. The move is one-way:
    a resolution is a statement about the world that other readers may have
    acted on, and unwriting it would leave them acting on nothing.

    **This function touches identifiers and nothing else.** It takes no record
    id, writes no ``verification_log`` entry and moves no record's status:
    resolving an identifier is not a citation check, and a model-supplied
    identifier confirmed by a person is still not one. That is structural --
    there is no parameter here a record id could hide in -- and witnessed by
    the tests that assert a record's log is byte-identical across a resolution.
    """
    identifier = load_identifier(connection, identifier_id)
    if identifier is None:
        raise IdentifierNotFoundError(f"no identifier with id {identifier_id!r}")
    if identifier.resolution_state is ResolutionState.RESOLVED:
        raise IdentifierError(
            f"the identifier {identifier_id!r} is already resolved by"
            f" {identifier.resolved_by!r}. A resolution is a statement about the"
            " world and is not unwritten; a correction is a new confirmation"
            " with its own detail"
        )
    updated = connection.execute(
        sql_text(
            "UPDATE identifier_records SET resolution_state = 'resolved',"
            " resolution_detail = :detail, resolved_by = :rby, resolved_at = :rat"
            " WHERE identifier_id = :iid AND resolution_state != 'resolved'"
        ),
        {
            "detail": detail,
            "rby": resolved_by,
            "rat": resolved_at.isoformat(),
            "iid": identifier_id,
        },
    )
    if updated.rowcount != 1:  # pragma: no cover - guarded by the read above
        raise IdentifierError(f"the identifier {identifier_id!r} could not be updated")
    result = load_identifier(connection, identifier_id)
    if result is None:  # pragma: no cover - the row was read a moment ago
        raise IdentifierNotFoundError(f"no identifier with id {identifier_id!r}")
    return result
