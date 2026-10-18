"""The index: FTS5 retrieval, and the address resolution C1 is handed.

Two things live here, and they are different jobs that happen to share a table.

**Retrieval** answers a question: given a query, which excerpts mention it. It
owns the *query safety* below, and it returns :class:`Hit` objects carrying the
**original** text.

**Address resolution** implements :class:`~labcairn.evidence.cite_support.SourceIndex`
— ``locate`` and ``content_hash`` — which answer a different question: given an
anchor, what is at that address. Neither member can be handed a query string,
so without this module the Protocol would be the whole of retrieval and the
ground-truth set would have nothing to test.

A hit carries the original text, never the indexed text
-------------------------------------------------------------
T02's normalisation is an index-side copy; ``source_texts`` is the only
authority. So a hit re-reads the row named by its ``(sha, extraction_version,
locator_key)`` and hands back what the adapter produced. Handing C2 the
normalised text would have C2 comparing the index against itself — a comparison
that cannot fail, and the same shape as the two-column defect LC-P1-08 closed,
where spliced text was stored and then cited as the author's words.

A query string is not an FTS5 expression
----------------------------------------
Measured against the ground-truth set, a naive ``MATCH :query`` **crashes** on
two of its own queries: ``10.9999/j.labcairn.2026.00001`` is a syntax error near
the ``.``, and ``total-correlation`` is read as a column filter and fails with
*no such column*. ``NOT``, an unbalanced parenthesis, a lone quote and the empty
string all raise as well.

That is ADR-0004 A9 arriving as a crash rather than as a false negative, and it
is why every whitespace-separated term is quoted and joined with ``AND``: an
unrecognised ``-``, ``.``, ``*`` or ``"`` then matches literally. A query with no
terms issues no ``MATCH`` at all, which is A6's empty retrieval — an absence,
not an error and not a match-everything.

The table is on a **trigram** tokenizer, and that is not a performance choice
----------------------------------------
It is because the default ``unicode61`` tokenizer matches whole tokens, and on
this repository's own papers most words are not tokens. ADR-0008's third
constraint records that these PDFs space words by positioning — space glyphs are
0.03%-1.08% of characters — so extracted body text arrives with words run
together. Page 4 of ``arx-2610.12393`` stores::

    red and unique factors(q ,q ),anirreduciblesynergisticgapI(Y;q |q ,q )>0

``irreducible`` is not a token there; it is a fragment of the single token
``anirreduciblesynergisticgapI``, glued to an article on one side and a math
symbol on the other, with **no separator of any kind between them**. Measured,
``unicode61`` returns **zero** hits for ``irreducible``, ``synergistic`` and
``irreduciblesynergisticgap`` on a page that contains all three.

Changing separator characters cannot recover it, because the boundary
information is not in the text — there is nothing to split on. Only a
tokenizer built on substrings answers the question, and ``trigram`` is that.
See revision 0006, which rebuilds the table because an FTS5 tokenizer is part
of the table definition rather than a column.

Two shapes this does not have
-----------------------------
**An anchor does not pin an extraction version.** ``SourceAnchor`` carries
``bound_source_sha256`` but no ``extraction_version``, while
``source_texts`` is keyed by all three. After a library upgrade two versions of
the same page coexist — which is ADR-0009 working as intended, keeping the old
extraction so "an anchor written under the old version still resolves and the
divergence becomes detectable". This module resolves to the most recently
extracted row and says which version it used, so a caller comparing the two can
detect the divergence. The policy is stated here rather than left implicit
because the contracts do not answer it.

**There is no anchors table.** ``SourceAnchor`` is a Pydantic model and nothing
persists one yet, so ``locate`` cannot return ``None`` for an unknown anchor id
the way its Protocol member documents: it is handed a whole anchor, so there is
nothing to look up and no way to be unknown. The ``None`` branch belongs to a
future anchor registry. Recorded rather than faked, because a ``locate`` that
returned ``None`` for an anchor it simply had never heard of would make a
fabricated source indistinguishable from a real one — ADR-0004 A12.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.evidence.cite_support import LocatedContent, LocationResolution
from labcairn.material.addressing import render_locator_key
from labcairn.sources.source import SourceAnchor

__all__ = ["Hit", "build_match_expression", "locate_anchor", "read_content_hash", "search"]

#: SQLite's own default cap, restated so a caller raising it is doing so
#: visibly rather than by discovering SQLite's number in a traceback.
DEFAULT_LIMIT: Final[int] = 20

#: Trigram indexes overlapping three-character sequences, so a shorter term
#: has nothing to match. See :func:`build_match_expression` for why the query is
#: refused rather than answered more broadly.
_MIN_TRIGRAM: Final[int] = 3


@dataclass(frozen=True)
class Hit:
    """One excerpt a query matched.

    ``text`` is the **original** stored text, re-read from ``source_texts``.
    The index row holds a normalised copy, and that copy is for matching only.

    ``source_ids`` names the sources that currently hold these bytes, and it may
    be empty. Two cases make that honest rather than a bug:

    * the file changed after extraction, so the text still exists and no current
      source carries its hash any more — this is ADR-0004 A2's drift, and a
      caller citing it must notice;
    * the same bytes at two paths share one content-addressed extraction, so one
      hit legitimately belongs to two sources.

    ``extraction_version`` is reported so a caller can tell which extraction it
    is looking at rather than assuming the newest.
    """

    source_content_sha256: str
    extraction_version: str
    locator_key: str
    locator_kind: str
    text: str
    source_ids: tuple[str, ...]

    @property
    def is_drifted(self) -> bool:
        """This excerpt is from a version of the file that no longer exists.

        ADR-0004 A2: the source's bytes changed after this text was extracted.
        The text is still in ``source_texts`` -- ADR-0009 requires that, so an
        anchor written against the old bytes still resolves -- and the index
        carries it, because a passage that genuinely was written should not
        become unfindable and surface as A6's "the material does not say that".

        What must not happen is that it looks current. A hit carrying this text
        has a real page, a real locator and text C2 can verify against the
        store, so without this property every downstream check passes and the
        citation reads as though the file still said it.

        Named rather than inferred from an empty ``source_ids``: the emptiness
        is the *mechanism*, and a caller reading ``if not hit.source_ids`` has
        to know to look here at all.
        """
        return self.source_ids == ()


def build_match_expression(query: str) -> str | None:
    """An FTS5 expression for *query*, or ``None`` when it has no terms.

    Every term is quoted, which is what makes arbitrary user text safe: inside
    double quotes FTS5 reads ``-``, ``.``, ``*`` and ``"`` as literal characters
    rather than as column filters, prefix operators and phrase delimiters. A
    bare ``"`` is doubled, because that is how it is escaped inside a quoted
    string.

    Terms are joined with ``AND``, not a phrase: a query's words may appear in
    any order on the page, and requiring the exact adjacency of a phrase would
    report a real passage as absent. ``None`` means "no terms", which the caller
    turns into an empty result rather than into a ``MATCH`` -- an empty string is
    a syntax error to FTS5 and is ADR-0004 A6's honest answer.

    **A term shorter than three characters cannot be served by a trigram
    table**, whatever this function does with it. Trigram indexes overlapping
    three-character sequences, so ``"is"`` and ``"a"`` have nothing to match and
    SQLite returns no rows for them -- silently, without raising. A query the
    user typed is full of short words, so this is not a corner case.

    The decision here is to **refuse the query rather than narrow or widen it**.
    Both of the alternatives answer a question nobody asked:

    * dropping the short term makes the query *broader* -- "the is not greedy"
      becomes "the greedy" and returns excerpts the user did not ask for;
    * keeping it and letting SQLite answer makes the whole query return nothing,
      which is the same thing but with the ambiguity removed.

    Widening is the dangerous one. A broader result still *looks* like a hit: it
    carries a real excerpt, a real page and a real locator, so it survives every
    downstream check and arrives at a citation. And this retrieval exists to
    feed C2, which confirms a quotation verbatim -- so a wrong-but-plausible
    passage is not merely noise, it is something the ledger would then verify
    against the wrong page. Returning nothing is an absence, and ADR-0004 A6
    makes an absence an answer with its own semantics rather than a failure to
    answer.
    """
    tokens = [token for token in query.split() if token]

    if any(len(token) < _MIN_TRIGRAM for token in tokens):
        return None

    terms = ['"' + token.replace('"', '""') + '"' for token in tokens if token]
    if not terms:
        return None
    return " AND ".join(terms)


def search(connection: Connection, query: str, *, limit: int = DEFAULT_LIMIT) -> tuple[Hit, ...]:
    """Excerpts matching *query*, each carrying the original stored text.

    Returns an empty tuple for a query with no terms and for a query nothing
    matches. Distinguishing an empty *result* from an empty *query* is the
    retrieval API's caller-level concern and lands in T10; both are absences
    here, and neither is an error.
    """
    expression = build_match_expression(query)
    if expression is None:
        return ()

    rows = connection.execute(
        sql_text(
            "SELECT f.source_content_sha256, f.extraction_version, f.locator_key, "
            "       t.locator_kind, t.text, s.source_id "
            "  FROM evidence_fts AS f "
            "  JOIN source_texts AS t "
            "    ON t.source_content_sha256 = f.source_content_sha256 "
            "   AND t.extraction_version = f.extraction_version "
            "   AND t.locator_key = f.locator_key "
            "  LEFT JOIN sources AS s ON s.content_sha256 = f.source_content_sha256 "
            " WHERE evidence_fts MATCH :expression "
            " ORDER BY rank "
            " LIMIT :limit"
        ),
        {"expression": expression, "limit": limit},
    ).fetchall()

    hits: dict[tuple[str, str, str], Hit] = {}
    for record in rows:
        sha, version, locator_key, locator_kind, body, source_id = cast(
            "tuple[str, str, str, str, str, str | None]", tuple(record)
        )
        key = (sha, version, locator_key)
        found = hits.get(key)
        if found is None:
            hits[key] = Hit(
                source_content_sha256=sha,
                extraction_version=version,
                locator_key=locator_key,
                locator_kind=locator_kind,
                text=body,
                source_ids=(),
            )
        if source_id is not None and source_id not in hits[key].source_ids:
            hits[key] = _with_source(hits[key], source_id)
    return tuple(hits.values())


def _with_source(hit: Hit, source_id: str) -> Hit:
    return Hit(
        source_content_sha256=hit.source_content_sha256,
        extraction_version=hit.extraction_version,
        locator_key=hit.locator_key,
        locator_kind=hit.locator_kind,
        text=hit.text,
        source_ids=(*hit.source_ids, source_id),
    )


def locate_anchor(connection: Connection, anchor: SourceAnchor) -> LocatedContent:
    """What is at *anchor*'s address.

    Three outcomes, and ADR-0004 A1 and A7 need them distinguishable:
    ``RESOLVED`` when the address holds text, ``UNRESOLVABLE`` when the anchor
    is known but the address does not exist — page 99 of a 3-page PDF -- and
    ``UNADDRESSABLE`` when the material is present in a form LabCairn cannot
    address, which after LC-P1-08 means a source whose ``readability`` is
    anything but ``readable``: a scan, or a container that would not open.

    The third is only implementable because LC-P1-08 fixed ``readability``. A
    scanned PDF used to be recorded ``READABLE``, whose meaning is "may be
    indexed and cited", so there was nothing honest for this to return.
    """
    locator_key = render_locator_key(anchor.locator)

    row = connection.execute(
        sql_text(
            "SELECT t.text, s.readability "
            "  FROM source_texts AS t "
            "  LEFT JOIN sources AS s ON s.source_id = :source_id "
            " WHERE t.source_content_sha256 = :sha AND t.locator_key = :locator_key "
            " ORDER BY t.created_at DESC, t.id DESC "
            " LIMIT 1"
        ),
        {
            "sha": anchor.bound_source_sha256,
            "locator_key": locator_key,
            "source_id": anchor.source_id,
        },
    ).fetchone()

    if row is None:
        return LocatedContent(
            anchor_id=anchor.anchor_id,
            resolution=LocationResolution.UNRESOLVABLE,
            observed_content_sha256=read_content_hash(connection, anchor.source_id),
        )

    body, readability = cast("tuple[str | None, str | None]", (row[0], row[1]))
    if readability is not None and readability != "readable":
        return LocatedContent(
            anchor_id=anchor.anchor_id,
            resolution=LocationResolution.UNADDRESSABLE,
            observed_content_sha256=read_content_hash(connection, anchor.source_id),
        )

    stored = body or ""
    return LocatedContent(
        anchor_id=anchor.anchor_id,
        resolution=LocationResolution.RESOLVED,
        text=stored,
        numeric_value=_as_number(stored),
        observed_content_sha256=read_content_hash(connection, anchor.source_id),
    )


def read_content_hash(connection: Connection, source_id: str) -> str | None:
    """The source's **current** content hash, or ``None`` if it is unknown.

    C1 compares this against the anchor's ``bound_source_sha256``; a mismatch
    is ADR-0004 A2's drift. ``None`` is a real answer and not a zero: the ledger
    has never heard of that source id, which is A12's fabricated source rather
    than a real source whose bytes moved.
    """
    return connection.execute(
        sql_text("SELECT content_sha256 FROM sources WHERE source_id = :source_id"),
        {"source_id": source_id},
    ).scalar()


def _as_number(text: str) -> float | None:
    """The stored text read as a number, or ``None`` when it is not one.

    C3 compares a *quantity*, and the cell is stored as the string the file
    held. A cell written ``3.50`` and a record claiming ``3.5`` agree; string
    equality would call that a conflict. Text that is not numeric yields
    ``None`` so C3 answers ``indeterminate`` rather than coercing a sentence.
    """
    candidate = text.strip()
    if not candidate:
        return None
    try:
        value = float(candidate)
    except ValueError:
        return None
    return value if math.isfinite(value) else None
