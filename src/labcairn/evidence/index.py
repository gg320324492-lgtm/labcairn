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

**Where the anchor itself comes from.** ``SourceAnchor`` is a Pydantic model,
so something has to persist one before C1 can be handed it -- and until
revision 0007 nothing did. ``load_anchor`` reads the ``source_anchors``
registry that migration created, and ``locator_from_key`` rebuilds the
locator from its canonical ``locator_key``. That round trip is the newest
thing here and the easiest to break in a way nothing catches: a mis-rebuilt
locator is still a *valid* locator, so it resolves, and the error surfaces as
C1 having quietly read the wrong page rather than as an exception. It is why
the registry stores one representation of the address and the reconstruction
refuses rather than repairs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.evidence.cite_support import LocatedContent, LocationResolution
from labcairn.material.addressing import LocatorKeyError, render_locator_key, split_locator_key
from labcairn.sources.locators import (
    CsvLocator,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
)
from labcairn.sources.source import AnchorKind, SourceAnchor

__all__ = [
    "Hit",
    "LabCairnIndex",
    "build_match_expression",
    "load_anchor",
    "locate_anchor",
    "locator_from_key",
    "read_content_hash",
    "search",
]

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


def locator_from_key(locator_key: str) -> SourceLocator:
    """Rebuild the locator that :func:`render_locator_key` rendered.

    The inverse direction, and the one place a bug would be invisible: a wrong
    reconstruction does not raise, it returns a *different valid* address, and
    every check downstream then resolves happily against the wrong page.

    ``split_locator_key`` returns a ``dict[str, str]`` -- the length-prefixed
    components, including the leading ``k`` that names the union member. So
    every field arrives as text and the integers have to be parsed here, which
    is the whole reason this function exists and the reason it is a decision
    rather than a lookup.

    Refuse rather than repair. A key whose components do not fit its kind is a
    corrupt row, and :class:`~labcairn.material.addressing.LocatorKeyError`
    is what says so -- the same error ``render_locator_key`` raises for a
    locator whose typed fields contradict its kind, so the two directions fail
    identically rather than only the awkward one.

    **Strict about *extra* components, not just missing ones.** A key that
    carries ``r=`` on a ``pdf`` reconstructs perfectly if the reader ignores
    the field, and the result is a page anchor pointing at the right page --
    which is the failure this function exists to make impossible, arriving
    disguised as success. So each kind declares the fields it may carry and an
    unexpected one is refused. It costs six lines and turns "the key is one I
    recognise" into a decidable property rather than a habit.

    **The length prefix needs no check of its own, and that took a mutation to
    establish.** ``split_locator_key`` reads the prefix's *declared* length and
    takes exactly that many characters, so ``k=9:pdf|p=1:4`` yields
    ``{"k": "pdf|p=1:4"}`` -- the prefix swallows the rest of the key, the
    value comes out as something that is not a kind, and the check above
    refuses it. A separate ``startswith(f"k={len(kind)}:")`` was written
    anyway, on the reasoning that a wrong prefix is a corrupt key; mutation
    checking showed it could not fire on any input the kind check does not
    already catch, so it was deleted rather than left as a branch no test could
    reach. The prefix is still enforced -- by the parser, where it belongs.
    """
    fields = split_locator_key(locator_key)
    kind = fields.get("k")
    if kind not in _REQUIRED_COMPONENTS:
        raise LocatorKeyError(
            f"locator_key {locator_key!r} names kind {kind!r}, which is not one of "
            f"{sorted(_REQUIRED_COMPONENTS)}. A kind LabCairn cannot rebuild is a "
            f"corrupt row; naming a member of the union by guesswork would produce "
            f"a valid address that points nowhere the author wrote."
        )
    _check_components(locator_key, kind, fields)

    if kind == "pdf":
        page = _integer(fields, "p")
        span = fields.get("c")
        if span is None:
            return PdfLocator(page=page)
        return PdfLocator(page=page, char_start=_span_start(span), char_end=_span_end(span))
    if kind == "text":
        return TextLocator(
            line=_integer(fields, "l"),
            line_end=_integer(fields, "le") if "le" in fields else None,
            section=fields.get("s"),
        )
    if kind == "csv":
        return CsvLocator(row=_integer(fields, "r"), column=fields["c"])
    return XlsxLocator(sheet_name=fields["sh"], cell_ref=fields["c"])


#: The components each kind must carry, and the ones it may. Generated from the
#: same grammar ``render_locator_key`` writes -- a fourth spelling of that
#: grammar would be exactly the fork ADR-0009's ``locator_key`` exists to stop.
_REQUIRED_COMPONENTS: Final[dict[str, frozenset[str]]] = {
    "pdf": frozenset({"k", "p"}),
    "text": frozenset({"k", "l"}),
    "csv": frozenset({"k", "r", "c"}),
    "xlsx": frozenset({"k", "sh", "c"}),
}

_OPTIONAL_COMPONENTS: Final[dict[str, frozenset[str]]] = {
    "pdf": frozenset({"c"}),
    "text": frozenset({"le", "s"}),
    "csv": frozenset(),
    "xlsx": frozenset(),
}


def _check_components(locator_key: str, kind: str, fields: dict[str, str]) -> None:
    """Refuse a key whose components do not match its kind's grammar."""
    allowed = _REQUIRED_COMPONENTS[kind] | _OPTIONAL_COMPONENTS[kind]
    missing = _REQUIRED_COMPONENTS[kind] - fields.keys()
    unexpected = fields.keys() - allowed
    if missing or unexpected:
        raise LocatorKeyError(
            f"locator_key {locator_key!r} is not a well-formed {kind!r} key. "
            f"Missing: {sorted(missing) or 'none'}. "
            f"Unexpected: {sorted(unexpected) or 'none'}. "
            f"A {kind!r} locator may carry {sorted(allowed)}."
        )


def _integer(fields: dict[str, str], name: str) -> int:
    """One component read as an integer, or refused.

    ``ValueError`` is wrapped rather than allowed out because every caller of
    this function is a reconstruction step in C1's path, and the caller's
    contract is a :class:`LocatorKeyError` meaning "this key does not describe
    a locator" -- a type it already handles from ``split_locator_key``.
    """
    raw = fields[name]
    try:
        return int(raw)
    except ValueError:
        raise LocatorKeyError(
            f"component {name!r} holds {raw!r}, which is not an integer. Every "
            f"page, line and row in a key is written in decimal; a key that says "
            f"otherwise was not produced by render_locator_key."
        ) from None


def _span_start(span: str) -> int:
    return _span_part(span, 0, "char_start")


def _span_end(span: str) -> int:
    return _span_part(span, 1, "char_end")


def _span_part(span: str, index: int, field: str) -> int:
    """One end of a PDF's ``c=start-end`` component.

    Split on the single ``-`` rather than parsed with ``partition``, because the
    separator appears exactly once in a well-formed span and a span that carries
    it twice is not a span. ``partition`` would happily return ``"99"`` for the
    right end of ``"10-99-4"`` and hand back a valid locator for a nonsense
    address.
    """
    parts = span.split("-")
    if len(parts) != 2:
        raise LocatorKeyError(
            f"a PDF character span is written 'start-end', and {span!r} has "
            f"{len(parts) - 1} separators. {field} cannot be read from it."
        )
    raw = parts[index]
    try:
        return int(raw)
    except ValueError:
        raise LocatorKeyError(
            f"a PDF character span holds {raw!r} where {field} should be an integer."
        ) from None


def load_anchor(connection: Connection, anchor_id: str) -> SourceAnchor | None:
    """The anchor with this id, or ``None`` if the ledger has never heard of it.

    **This is the seam ADR-0004's C1 requirement was missing.** The contract
    says C1 must "fail if an anchor id is unknown"; a record carries
    ``anchor_ids`` as bare strings and ``SourceIndex.locate`` takes a whole
    :class:`SourceAnchor`. Without this function there is no path between the
    two, so the requirement had nothing implementing it.

    ``None`` means **no such id**, which is ADR-0004 A12's fabricated source.
    It is deliberately *not* also the answer for a row that exists but cannot
    be read: a corrupt ``locator_key`` raises :class:`LocatorKeyError` instead,
    because "the ledger has never heard of this" and "the ledger has a broken
    row" are different findings and a report that cannot tell them apart will
    eventually call one the other. A caller turning either into a verdict is
    doing that at the *check*, not here.

    The key grammar this parses, one per union member::

        k=3:pdf|p=1:4
        k=3:pdf|p=1:2|c=5:10-99
        k=4:text|l=1:7
        k=4:text|l=1:7|le=1:9|s=7:Methods
        k=3:csv|r=2:12|c=4:mean
        k=4:xlsx|sh=2:S1|c=2:B2

    Note that ``c`` is three different things depending on the kind: a PDF's
    character span (``start-end``), a CSV's column header, and an XLSX's cell
    reference. Reading it without dispatching on ``k`` first is how one becomes
    another silently.
    """
    row = connection.execute(
        sql_text(
            "SELECT anchor_id, source_id, kind, locator_key, bound_source_sha256,"
            "       excerpt_sha256, created_at"
            "  FROM source_anchors WHERE anchor_id = :anchor_id"
        ),
        {"anchor_id": anchor_id},
    ).fetchone()
    if row is None:
        return None

    anchor_id_, source_id, kind, locator_key, bound_sha, excerpt_sha, created_at = cast(
        "tuple[str, str, str, str, str, str | None, datetime]", tuple(row)
    )
    return SourceAnchor(
        anchor_id=anchor_id_,
        source_id=source_id,
        kind=AnchorKind(kind),
        locator=locator_from_key(locator_key),
        bound_source_sha256=bound_sha,
        excerpt_sha256=excerpt_sha,
        created_at=created_at,
    )


class LabCairnIndex:
    """The concrete :class:`~labcairn.evidence.cite_support.SourceIndex`.

    Three members and one connection. It exists because the Protocol had no
    implementation: a ``Protocol`` nothing satisfies is a description, and
    anything handed one could get a duck-typed stand-in that answers from
    nothing. This class is the one place a C1-C3 call can be routed, and it
    routes to the store.

    Stateless with respect to the store -- it holds no cache and makes no
    decision. A caller that wants a snapshot asks inside a transaction, because
    the alternative is an index that answers about a store that has since moved.
    """

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def load_anchor(self, anchor_id: str) -> SourceAnchor | None:
        """See :func:`load_anchor`."""
        return load_anchor(self._connection, anchor_id)

    def locate(self, anchor: SourceAnchor) -> LocatedContent | None:
        """See :func:`locate_anchor`. Never ``None``: see its docstring."""
        return locate_anchor(self._connection, anchor)

    def content_hash(self, source_id: str) -> str | None:
        """See :func:`read_content_hash`."""
        return read_content_hash(self._connection, source_id)


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
