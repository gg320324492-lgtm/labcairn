"""the anchor registry: the address half of a citation

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-18

LC-P1-09 T05a. Revision 0005 created ``evidence_anchors``, and the name is
doing two jobs it should not. That table is a *join* -- it records which
anchor ids one evidence record cites, and in what order. It stores the id and
nothing else, which is correct for a join and fatal for C1:

ADR-0004 Contract 3 says C1 must "fail if an anchor id is unknown". The
record carries ``anchor_ids: tuple[str, ...]``, and ``SourceIndex`` exposes
``locate(anchor: SourceAnchor)`` and ``content_hash(source_id: str)``. Neither
accepts an id, so there was no path from one to the other: C1 could not reach
``locate`` at all. The requirement was in the ADR from the start and had no
implementation behind it.

This revision creates the registry that closes it, and adds
``SourceIndex.load_anchor(anchor_id) -> SourceAnchor | None``. ADR-0004 does
not fix ``SourceIndex``'s members -- the Protocol exists only in
``src/labcairn/evidence/cite_support/__init__.py`` -- so this is the seam
ADR-0004's requirement was missing, not an amendment to it.

**One locator representation, on purpose.** ``source_texts`` stores both
``locator_key`` and the eight typed locator columns, and nothing in the schema
requires the two to agree. Storing both here would have been consistent with
that precedent and would have been a mistake: ``load_anchor`` would have to
choose which one to rebuild the :class:`SourceAnchor`` from, and choosing wrong
does not raise -- it returns a *different address*, which C1 then resolves
successfully against the wrong page. That is ADR-0004 A1's exact prohibition
("no nearest-page fallback") arriving by a route nobody was watching.

So the anchor's locator is stored **only** as ``locator_key``, the canonical
rendering ``material.addressing.render_locator_key`` already produces and
``split_locator_key`` already parses. One representation cannot disagree with
itself. The cost is that an anchor is not queryable by page number; Phase 1's
C1 goes id -> anchor -> (sha, locator_key) -> text and never asks "all page-5
anchors", so that cost is currently nothing.

**The kind comes out of the key, and that is the reason there is no
``locator_kind`` column.** A rendered key opens with its discriminator::

    k=3:pdf|p=1:4
    k=3:csv|r=2:12|c=4:mean

so a separate ``locator_kind`` column would be a second copy of a fact the key
already carries -- which is the exact disagreement the previous paragraph
exists to prevent, reintroduced one column over. ``split_locator_key`` returns
the leading ``k`` field like any other, so reconstruction dispatches on it and
there is nothing left to fall out of step. ``kind`` is still a column because
it is *not* a locator fact: :attr:`SourceAnchor.kind` records what the anchor
is for (quotation, numeric, structural, absence_scan) and never appears in the
key.

The vocabulary constraint is a GLOB on the key's prefix rather than a list of
allowed values in a column of its own, for the same reason -- and its prefix is
**generated from each kind's spelling length**, because that length is not
constant: ``pdf`` and ``csv`` render ``k=3:``, ``text`` and ``xlsx`` render
``k=4:``. Written out by hand it accepted the first two kinds and refused the
other two, which is what the first draft of this revision did.

**The wildcard ``?`` is not usable here, and finding that out was instructive.**
SQLAlchemy reads ``:csv`` as a bind parameter, so
``locator_key GLOB 'k=?:csv|*'`` compiled to the literal ``'k=?NULL|*'`` -- four
times over -- and the table accepted nothing at all. The schema parity test
passed straight through it, because this revision and the ORM were mangled
identically, and a test that compares two texts cannot catch both being wrong.
What caught it was inserting a row the schema must refuse. Revision 0004
records the same lesson about extraction problems; this is a new route to it.

**``computation`` is refused here**, following ``source_texts``'s precedent: a
derived number is addressed by the operator that produced it, so it has no
extracted text and belongs in no row that C1 could resolve. The honest
consequence is recorded rather than papered over -- an anchor that needs one
will have to be given a resolution path of its own before C1 can answer for it,
and until then C1 says it cannot address it rather than guessing.

Direct DDL, for the reason 0002 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently rewrite
what this revision meant to create. ``tests/test_evidence_schema.py``'s parity
test is what holds the two together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_anchors",
        # Not an autoincrement: an anchor id is minted by the caller so a record
        # can cite one that was made in an earlier run. A row-number id would
        # make citation depend on insertion order.
        sa.Column("anchor_id", sa.String(200), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        # SourceAnchor.kind -- what the anchor is for, not what it points at.
        sa.Column("kind", sa.String(32), nullable=False),
        # The anchor's address. The locator's own kind is the key's leading
        # `k=` component, not a column: see the module docstring.
        sa.Column("locator_key", sa.String(2000), nullable=False),
        # The source's hash *as it was when this anchor was made*. Compared
        # against the current hash by C1; never refreshed (ADR-0004 I4).
        sa.Column("bound_source_sha256", sa.String(64), nullable=False),
        sa.Column("excerpt_sha256", sa.String(64), nullable=True),
        # sa.String(), not sa.DateTime or sa.Text: the models use UtcDateTime,
        # a TypeDecorator whose impl is String because SQLite has no timestamp
        # type and SQLAlchemy's DateTime drops the offset. Revision 0005 spells
        # it the same way, and revision 0003 got it wrong once -- which is what
        # the schema parity test exists to catch.
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("anchor_id", name="pk_source_anchors"),
        # Closed vocabulary. Same standard as events.type and source_texts: a
        # kind that reconstructs no union member must not be storable, because
        # load_anchor would then have nothing to build.
        #
        # The prefix is generated from each kind's spelling length, since the
        # length prefix is not constant -- see the module docstring for the two
        # bugs that fact cost, one of which passed the parity test.
        sa.CheckConstraint(
            " OR ".join(
                f"locator_key GLOB 'k={len(kind)}:{kind}|*'"
                for kind in ("pdf", "text", "csv", "xlsx")
            ),
            name="source_anchors_locator_key_vocabulary",
        ),
        sa.CheckConstraint(
            "kind IN ('quotation', 'numeric', 'structural', 'absence_scan')",
            name="source_anchors_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "length(bound_source_sha256) = 64 AND bound_source_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_anchors_bound_sha256_shape",
        ),
        sa.CheckConstraint(
            "excerpt_sha256 IS NULL OR (length(excerpt_sha256) = 64 "
            "AND excerpt_sha256 NOT GLOB '*[^0-9a-f]*')",
            name="source_anchors_excerpt_sha256_shape",
        ),
        # '' as a locator_key would be a storable address that resolves to
        # nothing, which is the same defect 0005 found in source_texts.
        sa.CheckConstraint(
            "length(locator_key) > 0 AND length(anchor_id) > 0 AND length(source_id) > 0",
            name="source_anchors_ids_present",
        ),
    )
    # C1 looks up by id every time, so this is the table's only hot path.
    op.create_index("ix_source_anchors_source", "source_anchors", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_source_anchors_source", table_name="source_anchors")
    op.drop_table("source_anchors")
