"""Building the index from what ingestion stored, and saying what it left out.

ADR-0004 A7: *an unreadable source is excluded from the index and refused as a
citation.* That is only implementable because LC-P1-08 made ``readability`` mean
what ``source.py`` says it means -- until ``98b5ea5`` a scanned PDF was recorded
``READABLE``, whose meaning is "may be indexed and cited", so there was nothing
honest for a filter to select on.

Measured on the fixture corpus, the whole path costs **four seconds**:
``ingest_workspace`` over three papers (70 pages) 3.98s, the readable join
instant, writing 70 index rows 0.02s. Cheap enough that the tests use the real
papers rather than a reduced corpus.

**What this cannot test, stated rather than hidden.** Every one of the 70 rows
in the corpus belongs to a readable source, so A7's exclusion rule has **no
negative case in the real material**. It is covered by a synthetic unreadable
source in the tests, and that is a weaker claim than an end-to-end one: a rule
that has never seen the thing it excludes has not been shown to exclude it.
The same was true of the two-column material LC-P1-08 declined to fabricate --
the corpus has none, and no fixture can supply what the licences would not.

**The index is derived and is rebuilt, never patched.** ``source_texts`` is the
authority; ``evidence_fts`` holds a normalised copy of the same rows and can be
dropped and reconstructed. That is why this module has no incremental-update
path: a patch is where an index and its authority stop agreeing, and the
symptom -- a hit whose text no longer exists -- is indistinguishable from a
correct hit.

Whether a *source that has drifted* is indexed at all is a question this module
must answer rather than assume, and it is left open in
:func:`_indexable_rows`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.evidence.normalize import normalize
from labcairn.evidence.states import NormalizationProfile

__all__ = ["IndexBuild", "build_index", "index_state"]

#: What the builder indexes by default. The middle profile: NFKC and collapsed
#: whitespace, no ligature folding, because the corpus's own words are already
#: glued together by ADR-0008's third constraint and unfolding more of them
#: changes what a query matches without changing what the paper says.
DEFAULT_PROFILE: Final[NormalizationProfile] = NormalizationProfile.NFKC_WHITESPACE_COLLAPSED


@dataclass(frozen=True)
class IndexBuild:
    """What a build wrote, and what it declined to write.

    The exclusions are reported rather than applied quietly. ADR-0004 A9 exists
    because a failure and a negative result must not look alike; a builder that
    silently dropped half the corpus would leave a later empty search
    indistinguishable from "the material does not say that".
    """

    indexed: int
    excluded_unreadable: int
    removed_stale: int
    #: Rows the builder skipped for a reason it names in ``excluded_reasons``.
    excluded_reasons: dict[str, int]


def build_index(
    connection: Connection, *, profile: NormalizationProfile = DEFAULT_PROFILE
) -> IndexBuild:
    """Rebuild ``evidence_fts`` from ``source_texts``.

    Whole-table rather than incremental. The index is a copy of rows that
    already exist, so a rebuild cannot leave it disagreeing with its authority,
    and at four seconds for seventy pages the argument for avoiding one does not
    hold here.
    """
    rows = _indexable_rows(connection)
    stale = _stale_row_count(connection)

    connection.execute(sql_text("DELETE FROM evidence_fts"))

    written = 0
    for sha, version, key, body, source_text_id in rows:
        connection.execute(
            sql_text(
                "INSERT INTO evidence_fts (normalized_text, source_content_sha256,"
                " extraction_version, locator_key, source_text_id)"
                " VALUES (:body, :sha, :version, :key, :sid)"
            ),
            {
                "body": normalize(body, profile).text,
                "sha": sha,
                "version": version,
                "key": key,
                "sid": str(source_text_id),
            },
        )
        written += 1
    return IndexBuild(
        indexed=written,
        excluded_unreadable=_unreadable_count(connection),
        removed_stale=stale,
        excluded_reasons=_excluded_reasons(connection),
    )


def index_state(connection: Connection) -> dict[str, int | bool]:
    """What the index currently holds, and whether it agrees with the store.

    Derived rather than stored, so it cannot go stale in the way a recorded
    flag would. A count comparison is not a proof -- two different sets can have
    the same size -- so it is a first-order check that an empty search can
    consult before its result is reported as an absence.
    """
    indexed = int(connection.execute(sql_text("SELECT COUNT(*) FROM evidence_fts")).scalar_one())
    stored = int(connection.execute(sql_text("SELECT COUNT(*) FROM source_texts")).scalar_one())
    return {
        "indexed": indexed,
        "stored": stored,
        "complete": indexed == len(_indexable_rows(connection)),
    }


# --------------------------------------------------------------------------- #
# the open question
# --------------------------------------------------------------------------- #


def _indexable_rows(connection: Connection) -> list[tuple[str, str, str, str, int]]:
    """The rows the index is built from.

    **Everything except unreadable material.** ADR-0004 A7 excludes a source the
    project cannot read from the index and from citation, and that exclusion is
    unconditional: an unreadable page's text must be neither findable nor
    citable, so it is left out here rather than indexed with a caveat.

    **Drifted text is indexed, and marked as drifted.** ADR-0009's key
    discipline keeps the old rows after a file is edited and re-ingested, so a
    replaced file does not orphan the text existing anchors still resolve
    against. Those rows are exactly the ones whose ``source_content_sha256``
    matches no current ``sources`` row, and they are kept here.

    The reason is that the two errors are not symmetric, and ADR-0004 is
    explicit about which one it is:

    * dropping them makes a passage that genuinely was written **unfindable**,
      and that surfaces as A6 -- "the material does not say that" -- when the
      truth is A2, "the material said it and has since changed". An absence
      impersonating a drifted claim is the exact confusion A2 exists to stop;
    * indexing them unmarked would let a search return a passage from a version
      of the file that no longer exists, carrying a real page and a real
      locator, and C2 would verify it against text still in the store -- so it
      would **pass**.

    So the drift is made visible instead. A hit whose ``source_ids`` is empty is
    exactly this case, and :func:`~labcairn.evidence.index.Hit.is_drifted`
    names it rather than leaving a caller to infer it from an empty tuple.
    """
    rows = connection.execute(
        sql_text(
            "SELECT t.source_content_sha256, t.extraction_version, t.locator_key,"
            "       t.text, t.id"
            "  FROM source_texts AS t"
            "  LEFT JOIN sources AS s ON s.content_sha256 = t.source_content_sha256"
            " WHERE s.content_sha256 IS NULL"
            "    OR s.readability = 'readable'"
            " ORDER BY t.id"
        )
    ).fetchall()
    return [cast("tuple[str, str, str, str, int]", tuple(row)) for row in rows]


def _unreadable_count(connection: Connection) -> int:
    return int(
        connection.execute(
            sql_text(
                "SELECT COUNT(*) FROM source_texts AS t JOIN sources AS s"
                " ON s.content_sha256 = t.source_content_sha256"
                " WHERE s.readability <> 'readable'"
            )
        ).scalar_one()
    )


def _stale_row_count(connection: Connection) -> int:
    """Rows in the index whose identity is no longer in ``source_texts``."""
    return int(
        connection.execute(
            sql_text(
                "SELECT COUNT(*) FROM evidence_fts WHERE NOT EXISTS ("
                "  SELECT 1 FROM source_texts AS t"
                "   WHERE t.source_content_sha256 = evidence_fts.source_content_sha256"
                "     AND t.extraction_version = evidence_fts.extraction_version"
                "     AND t.locator_key = evidence_fts.locator_key)"
            )
        ).scalar_one()
    )


def _excluded_reasons(connection: Connection) -> dict[str, int]:
    """Why rows were left out, counted by reason.

    A builder that dropped rows silently would leave a later empty search
    indistinguishable from a genuine absence -- which is ADR-0004 A9's whole
    subject, arriving one layer earlier than expected.
    """
    unreadable = int(
        connection.execute(
            sql_text(
                "SELECT COUNT(*) FROM source_texts AS t JOIN sources AS s"
                " ON s.content_sha256 = t.source_content_sha256"
                " WHERE s.readability <> 'readable'"
            )
        ).scalar_one()
    )
    reasons: dict[str, int] = {}
    if unreadable:
        reasons["source_unreadable"] = unreadable
    return reasons
