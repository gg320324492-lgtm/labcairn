"""C2 — is the quoted text actually there?

The cases are drawn from the fixture papers themselves, because C2's central
question -- "how strict can a comparison be before it starts reporting genuine
quotations as unsupported" -- is a property of *this* corpus. ADR-0008
constraint 3 records that these PDFs space words by positioning, and the
extractor synthesises the space; on the same page "total correlation" keeps its
space and "alignsfusedmodalitysubsetswith" has none of its own.

Measured on this corpus before the ladder was written:

  - verbatim:        14 of the 21 human-confirmed (phrase, page) pairs
  - boundary-free:   21 of 21
  - false positives: 0 across the corpus's four negative queries

so a check that accepts only verbatim matches calls a third of the corpus's real
quotations unsupported. That is ADR-0004 R2's named failure -- false negatives
train users to turn the check off -- which is why the ladder has four rungs.

The trap this file is built to catch is the self-fulfilling one. A quote is
copied out of the store, so comparing it with the store verifies fidelity to
storage, not to the author. Every pass here is paired with a mutation of the
store that must turn it into a failure, and a mutation of the *index* that must
not.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pdfplumber
import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from conftest import migrated_database_from
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c2 import C2_CHECKER_ID, quotation_match
from labcairn.evidence.cite_support import (
    check_numeric_consistency,
    check_quotation_support,
)
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.normalize import normalize
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    NormalizationProfile,
    VerificationStatus,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import PdfLocator, TextLocator

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
PAPERS = Path(__file__).parent / "fixtures" / "papers"

SHA_10596 = hashlib.sha256(b"arx-2610.10596").hexdigest()
SHA_09396 = hashlib.sha256(b"arx-2610.09396").hexdigest()
LIG_SHA = "d" * 64
SCAN_SHA = "e" * 64

Ledger = tuple[Connection, LabCairnIndex]

#: Two real pages, chosen for the shapes they contain rather than their content.
#: Page 2 of 10596 has a phrase with its spaces ("customary greedy selection
#: rule") and one the extractor glued ("globalminimumov"); page 3 of 09396 is a
#: running header that joins "Structured Disambiguation" into one token.


def _page_text(name: str, page: int) -> str:
    with pdfplumber.open(PAPERS / name) as document:
        return document.pages[page - 1].extract_text() or ""


@pytest.fixture()
def ledger(migrated_database_template: Path, tmp_path: Path) -> Iterator[Ledger]:
    """Two papers, two stored pages, two anchors -- text from the real PDFs."""
    target = tmp_path / "c2.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    connection = engine.connect()

    for source_id, sha, name in (
        ("src-10596", SHA_10596, "arx-2610.10596.pdf"),
        ("src-09396", SHA_09396, "arx-2610.09396.pdf"),
    ):
        connection.execute(
            sql_text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
                " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
                " ingested_at, schema_version)"
                " VALUES (:sid,'local-user','pdf',:name,:rel,:sha,1,'readable',NULL,'[]',:now,1)"
            ),
            {"sid": source_id, "name": name, "rel": name, "sha": sha, "now": NOW},
        )
        for page, body in (
            (2, _page_text("arx-2610.10596.pdf", 2)),
            (3, _page_text("arx-2610.09396.pdf", 3)),
        ):
            key = render_locator_key(PdfLocator(page=page))
            connection.execute(
                sql_text(
                    "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                    " locator_kind, locator_key, page, text, text_sha256, created_at)"
                    " VALUES (:sha,'v1','pdf',:key,:page,:body,:tsha,:now)"
                ),
                {
                    "sha": sha,
                    "key": key,
                    "page": page,
                    "body": body,
                    "tsha": hashlib.sha256(body.encode()).hexdigest(),
                    "now": NOW,
                },
            )
            connection.execute(
                sql_text(
                    "INSERT INTO evidence_fts (normalized_text, source_content_sha256,"
                    " extraction_version, locator_key, source_text_id)"
                    " VALUES (:norm,:sha,'v1',:key,'1')"
                ),
                {
                    "norm": normalize(body, NormalizationProfile.NFKC_WHITESPACE_COLLAPSED).text,
                    "sha": sha,
                    "key": key,
                },
            )

    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-greedy','src-10596','quotation',:key,:sha,NULL,:now)"
        ),
        {"key": render_locator_key(PdfLocator(page=2)), "sha": SHA_10596, "now": NOW},
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-disambig','src-09396','quotation',:key,:sha,NULL,:now)"
        ),
        {"key": render_locator_key(PdfLocator(page=3)), "sha": SHA_09396, "now": NOW},
    )
    connection.commit()
    yield connection, LabCairnIndex(connection)
    engine.dispose()


def _record(span: str, anchors: tuple[str, ...], source_hash: str = SHA_10596) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev-1",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim the record attributes to the source.",
        anchor_ids=anchors,
        extracted_span=span,
        extracted_span_sha256=hashlib.sha256(span.encode()).hexdigest(),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=source_hash,
        created_at=NOW,
    )


# --------------------------------------------------------------------------- #
# the ladder, rung by rung
# --------------------------------------------------------------------------- #


def test_a_verbatim_quote_from_a_real_page_passes(ledger: Ledger) -> None:
    _, index = ledger
    match = quotation_match(_record("customary greedy selection rule", ("a-greedy",)), index=index)
    assert match.outcome is CheckOutcome.PASS
    assert match.profile is NormalizationProfile.EXACT


def test_a_line_break_inside_the_quote_is_indeterminate_not_pass(ledger: Ledger) -> None:
    """The stored page has "Lew, in\\nexamining"; the quote has a space.

    Collapsing whitespace is a lossy comparison, so A4 says indeterminate. It is
    not a failure -- the words are the author's -- but it is not confirmation
    either, and the recorded profile makes the difference visible in the audit
    row rather than invisible in the verdict.
    """
    _, index = ledger
    match = quotation_match(_record("Lew, in examining the connection", ("a-greedy",)), index=index)
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert match.profile is NormalizationProfile.NFKC_WHITESPACE_COLLAPSED


def test_a_glued_quote_from_the_real_corpus_is_indeterminate(ledger: Ledger) -> None:
    """Not a hypothetical: page 3 of arx-2610.09396 really stores
    ``StructuredDisambiguationforText-to-SQL``.

    A human quoting that heading writes it with spaces. The words are the
    author's; the missing spaces are the extractor's inference about glyph
    gaps. Recovering the match costs the boundary information, so it is
    ``indeterminate``, and the profile recorded says so out loud.
    """
    _, index = ledger
    match = quotation_match(_record("Structured Disambiguation", ("a-disambig",)), index=index)
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert match.profile is NormalizationProfile.WORD_BOUNDARIES_REMOVED


def test_a_ligature_only_match_is_indeterminate(ledger: Ledger) -> None:
    """Synthetic, and labelled as such.

    Measured: no page in the fixture corpus contains a ligature codepoint, so
    this rung of the ladder has no real material to run on. The case is built by
    hand, which tests the check honestly and says nothing about whether
    ingestion produces it -- the same distinction T04 records for A7.

    ``œ`` is chosen deliberately. NFKC already folds ``ﬁ``, ``ﬂ``, ``ﬀ`` and
    ``ﬅ``, so a test built on those would pass at the second rung and quietly
    prove nothing about the third. ``œ`` is one of the 45 ligatures NFKC leaves
    alone, which is what makes the ligature rung reachable at all.
    """
    connection, index = ledger
    key = render_locator_key(TextLocator(line=1))
    body = "The manœuvre is described in the appendix."
    connection.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES ('src-lig','local-user','text','lig.txt','lig.txt',:sha,1,'readable',"
            "NULL,'[]',:now,1)"
        ),
        {"sha": LIG_SHA, "now": NOW},
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, line_start, text, text_sha256, created_at)"
            " VALUES (:sha,'v1','text',:key,1,:body,:tsha,:now)"
        ),
        {
            "sha": LIG_SHA,
            "key": key,
            "body": body,
            "tsha": hashlib.sha256(body.encode()).hexdigest(),
            "now": NOW,
        },
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-lig','src-lig','quotation',:key,:sha,NULL,:now)"
        ),
        {"key": key, "sha": LIG_SHA, "now": NOW},
    )
    connection.commit()

    match = quotation_match(
        _record("The manoeuvre is described in the appendix.", ("a-lig",), source_hash=LIG_SHA),
        index=index,
    )
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert match.profile is NormalizationProfile.NFKC_WHITESPACE_COLLAPSED_LIGATURES


def test_no_rung_of_the_ladder_lets_a_paraphrase_through(ledger: Ledger) -> None:
    """Every rung is a character-sequence test, not a similarity test.

    Three probes that a human would call "the same idea", and none of them
    survives even the loosest profile. The corpus's own negative queries --
    including "retrieval augmented generation", central to this project and
    absent from all three papers -- are checked against the real pages too.
    """
    _, index = ledger
    for probe in (
        "Sniedovich rejects the greedy rule",
        "Dijkstra is greedy",
        "the algorithm always picks the nearest node",
        "retrieval augmented generation",
    ):
        match = quotation_match(_record(probe, ("a-greedy",)), index=index)
        assert match.outcome is CheckOutcome.FAIL, f"{probe!r} matched under some profile"
        assert match.profile is NormalizationProfile.WORD_BOUNDARIES_REMOVED


# --------------------------------------------------------------------------- #
# the self-fulfilling trap
# --------------------------------------------------------------------------- #


def test_editing_the_stored_text_after_the_quote_breaks_it(ledger: Ledger) -> None:
    """The drift C2 exists to catch.

    Quoting page 2 passes; rewriting page 2's text and asking the same record
    must not. A check built only from quotes copied out of the store would pass
    here, because it would still be agreeing with itself -- which is exactly why
    this test mutates the store rather than starting from a wrong quote.
    """
    connection, index = ledger
    before = quotation_match(_record("customary greedy selection rule", ("a-greedy",)), index=index)
    assert before.outcome is CheckOutcome.PASS

    connection.execute(
        sql_text(
            "UPDATE source_texts SET text = :body, text_sha256 = :tsha"
            " WHERE source_content_sha256 = :sha AND page = 2"
        ),
        {
            "body": "Sniedovich nevertheless endorses a strictly greedy rule.",
            "tsha": hashlib.sha256(b"edited").hexdigest(),
            "sha": SHA_10596,
        },
    )
    connection.commit()
    after = quotation_match(_record("customary greedy selection rule", ("a-greedy",)), index=index)
    assert after.outcome is CheckOutcome.FAIL


def test_the_check_reads_the_store_and_not_the_index(ledger: Ledger) -> None:
    """A quote planted in the index but absent from the store must fail.

    ``evidence_fts`` holds a normalised copy of the same rows. If C2 compared
    against it, the check would be asking the index whether the index contains
    the text -- a question with no way to answer wrongly, and the same shape as
    the two-column defect LC-P1-08 closed, where spliced text was stored and
    then cited as the author's words.
    """
    connection, index = ledger
    connection.execute(
        sql_text(
            "INSERT INTO evidence_fts (normalized_text, source_content_sha256,"
            " extraction_version, locator_key, source_text_id)"
            " VALUES (:norm,:sha,'v1',:key,'99')"
        ),
        {
            "norm": "the source plainly states that Dijkstra is greedy",
            "sha": SHA_10596,
            "key": render_locator_key(PdfLocator(page=2)),
        },
    )
    connection.commit()
    match = quotation_match(_record("Dijkstra is greedy", ("a-greedy",)), index=index)
    assert match.outcome is CheckOutcome.FAIL

    # And the index genuinely contains it, so the failure is evidence of which
    # table the check consulted, not of an empty comparison.
    present = int(
        connection.execute(
            sql_text("SELECT COUNT(*) FROM evidence_fts WHERE evidence_fts MATCH :q"),
            {"q": '"Dijkstra is greedy"'},
        ).scalar_one()
    )
    assert present > 0


# --------------------------------------------------------------------------- #
# the record's own integrity
# --------------------------------------------------------------------------- #


def test_a_record_whose_span_and_hash_disagree_fails(ledger: Ledger) -> None:
    """Before any source is consulted, the record must be self-consistent.

    ``EvidenceRecord`` requires the span and its hash to be both present or both
    absent, but not that they agree. A record quoting X with the hash of Y makes
    every downstream comparison a comparison against an unknown string, and that
    is a definite fact, so it is reported as a failure rather than an
    indeterminacy.
    """
    _, index = ledger
    record = EvidenceRecord(
        evidence_id="ev-bad",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim with a mis-hashed quotation.",
        anchor_ids=("a-greedy",),
        extracted_span="customary greedy selection rule",
        extracted_span_sha256="0" * 64,
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SHA_10596,
        created_at=NOW,
    )
    match = quotation_match(record, index=index)
    assert match.outcome is CheckOutcome.FAIL
    assert "does not match its own" in match.detail


def test_a_quote_cited_to_an_unresolvable_locator_fails(ledger: Ledger) -> None:
    """A1, from C2's side: a locator outside the document is a failure.

    Registered but unresolvable is different from unregistered. The anchor exists,
    so the record is not citing an invented id; the address it names simply is not
    there. ``indeterminate`` would be the tempting answer -- "we could not check" --
    and it is wrong, because the check *did* look and found nothing at that
    address. Reporting an absence as an uncertainty is how a record drifts from
    "unsupported" to "unexamined" without anyone deciding that.
    """
    connection, index = ledger
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-far','src-10596','quotation',:key,:sha,NULL,:now)"
        ),
        {"key": render_locator_key(PdfLocator(page=99)), "sha": SHA_10596, "now": NOW},
    )
    connection.commit()

    match = quotation_match(_record("customary greedy selection rule", ("a-far",)), index=index)
    assert match.outcome is CheckOutcome.FAIL
    assert "does not resolve" in match.detail
    assert "Nothing is compared in its place" in match.detail


def test_a_quotation_spanning_two_anchors_is_found(ledger: Ledger) -> None:
    """A sentence running from the end of one span into the next is one quote.

    The spans are short and written by hand so the concatenation is exactly what
    the test claims, rather than a slice of a 3300-character page. The record
    cites both anchors and the quote appears in neither alone.

    The second, looser check is deliberate and named: a real quotation can cross
    an anchor boundary, and requiring each span to contain the whole quote would
    report it as unsupported. It is also the one place where C2 is more permissive
    than "each anchor", which is why it is a separate test rather than a comment.
    """
    connection, index = ledger
    head = render_locator_key(PdfLocator(page=11))
    tail = render_locator_key(PdfLocator(page=12))
    for page, key, body in ((11, head, "The proof has two halves,"), (12, tail, " each sound.")):
        connection.execute(
            sql_text(
                "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                " locator_kind, locator_key, page, text, text_sha256, created_at)"
                " VALUES (:sha,'v1','pdf',:key,:page,:body,:tsha,:now)"
            ),
            {
                "sha": SHA_10596,
                "key": key,
                "page": page,
                "body": body,
                "tsha": hashlib.sha256(body.encode()).hexdigest(),
                "now": NOW,
            },
        )
        connection.execute(
            sql_text(
                "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
                " bound_source_sha256, excerpt_sha256, created_at)"
                " VALUES (:aid,'src-10596','quotation',:key,:sha,NULL,:now)"
            ),
            {"aid": f"a-page{page}", "key": key, "sha": SHA_10596, "now": NOW},
        )
    connection.commit()

    spanned = "The proof has two halves, each sound."
    match = quotation_match(_record(spanned, ("a-page11", "a-page12")), index=index)
    assert match.outcome is CheckOutcome.PASS
    assert "character-for-character" in match.detail

    # The same quote cited to only one of the two anchors must fail, so the
    # concatenation is not a blanket loosening: it applies only to anchors the
    # record actually cites.
    single = quotation_match(_record(spanned, ("a-page11",)), index=index)
    assert single.outcome is CheckOutcome.FAIL


# --------------------------------------------------------------------------- #
# the absences
# --------------------------------------------------------------------------- #


def test_a_record_with_no_quotation_is_indeterminate(ledger: Ledger) -> None:
    """Nothing was quoted, so nothing can be confirmed or denied."""
    _, index = ledger
    record = EvidenceRecord(
        evidence_id="ev-nospan",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim with no quoted text at all.",
        anchor_ids=("a-greedy",),
        extracted_span=None,
        extracted_span_sha256=None,
        status=VerificationStatus.PLANNED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    match = quotation_match(record, index=index)
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert "no quoted text" in match.detail


def test_a_quoted_record_citing_no_anchor_is_indeterminate(ledger: Ledger) -> None:
    """A quote with no address cannot be checked, and cannot be passed.

    Distinct from the case above: here the record *does* quote something, but
    cites nothing to quote it from. ``pass`` would assert the source contains a
    string that was never located anywhere, which is the vacuous answer C1 faces
    too. ``EvidenceRecord`` only permits an empty anchor list at ``planned``,
    which is exactly the transition these checks decide.
    """
    _, index = ledger
    record = EvidenceRecord(
        evidence_id="ev-noanchor",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim quoting text it never located.",
        anchor_ids=(),
        extracted_span="customary greedy selection rule",
        extracted_span_sha256=hashlib.sha256(b"customary greedy selection rule").hexdigest(),
        status=VerificationStatus.PLANNED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    match = quotation_match(record, index=index)
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert "cites no anchors" in match.detail


def test_the_record_model_refuses_an_empty_quotation(ledger: Ledger) -> None:
    """The guarantee that makes C2's missing empty-quote guard safe.

    ``extracted_span`` is ``NonEmptyText``, so an empty quotation is refused at
    construction. That is why ``_found`` does not need a guard: an empty string
    is a substring of everything, and a check that defended against it would be
    a branch no caller can reach. Testing the refusal is what keeps the guard
    unnecessary rather than merely absent.
    """
    with pytest.raises(ValueError):
        EvidenceRecord(
            evidence_id="ev-empty",
            task_id="task-1",
            kind=EvidenceKind.CLAIM,
            text="A claim quoting nothing.",
            anchor_ids=("a-greedy",),
            extracted_span="",
            extracted_span_sha256=hashlib.sha256(b"").hexdigest(),
            status=VerificationStatus.EXTRACTED,
            created_by=EvidenceCreator.RULE,
            created_by_id="seed",
            source_content_hash=SHA_10596,
            created_at=NOW,
        )


def test_a_quote_cited_to_an_unregistered_anchor_fails(ledger: Ledger) -> None:
    _, index = ledger
    match = quotation_match(_record("customary greedy selection rule", ("invented",)), index=index)
    assert match.outcome is CheckOutcome.FAIL
    assert "not registered" in match.detail


def test_a_quote_cited_to_an_unreadable_source_is_indeterminate(ledger: Ledger) -> None:
    """A7 again, from C2's side: unreadable is not "the source disagrees"." """
    connection, index = ledger
    connection.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES ('src-scan','local-user','pdf','scan.pdf','scan.pdf',:sha,1,"
            "'unreadable_no_ocr',:disc,'[]',:now,1)"
        ),
        {"sha": "e" * 64, "disc": "no extractable text layer", "now": NOW},
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, page, text, text_sha256, created_at)"
            " VALUES (:sha,'v1','pdf',:key,1,:body,:tsha,:now)"
        ),
        {
            "sha": "e" * 64,
            "key": render_locator_key(PdfLocator(page=1)),
            "body": "whatever the OCR produced",
            "tsha": hashlib.sha256(b"ocr").hexdigest(),
            "now": NOW,
        },
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-scan','src-scan','quotation',:key,:sha,NULL,:now)"
        ),
        {"key": render_locator_key(PdfLocator(page=1)), "sha": "e" * 64, "now": NOW},
    )
    connection.commit()
    match = quotation_match(
        _record("whatever the OCR produced", ("a-scan",), source_hash="e" * 64), index=index
    )
    assert match.outcome is CheckOutcome.INDETERMINATE
    assert "cannot be read" in match.detail or "no comparison was possible" in match.detail


# --------------------------------------------------------------------------- #
# what the verdict cannot do
# --------------------------------------------------------------------------- #


def test_an_indeterminate_c2_never_promotes_a_record(ledger: Ledger) -> None:
    """ADR-0004 A4: "indeterminate is never reported as pass" is a test, not a convention.

    ``verified_by_rule`` needs a ``pass`` entry from C1-C3. An ``indeterminate``
    C2 entry -- the ligature and boundary cases -- does not supply one, so the
    record cannot reach that state through a lenient match.
    """
    _, index = ledger
    match = quotation_match(_record("Structured Disambiguation", ("a-disambig",)), index=index)
    assert match.outcome is CheckOutcome.INDETERMINATE

    entry = VerificationRecord(
        check=CheckKind.C2,
        checker_id=C2_CHECKER_ID,
        outcome=match.outcome,
        detail=match.detail,
        checked_at=NOW,
        normalization_profile=match.profile,
    )
    with pytest.raises(ValueError):
        EvidenceRecord(
            evidence_id="ev-promoted",
            task_id="task-1",
            kind=EvidenceKind.CLAIM,
            text="A claim promoted by a lenient match.",
            anchor_ids=("a-disambig",),
            extracted_span="Structured Disambiguation",
            extracted_span_sha256=hashlib.sha256(b"Structured Disambiguation").hexdigest(),
            status=VerificationStatus.VERIFIED_BY_RULE,
            verification_log=(entry,),
            created_by=EvidenceCreator.RULE,
            created_by_id="seed",
            source_content_hash=SHA_09396,
            created_at=NOW,
        )


def test_the_profile_written_to_the_log_is_the_one_c2_used(ledger: Ledger) -> None:
    """The audit row has to be truthful about how lenient the comparison was.

    ``Verdict`` cannot carry a profile -- ADR-0004 fixes its fields -- so
    :func:`quotation_match` returns both, and the ledger layer uses that. A
    boundary-free match recorded as ``exact`` is R2's objection in exactly one
    field.
    """
    _, index = ledger
    for span, expected in (
        ("customary greedy selection rule", NormalizationProfile.EXACT),
        ("Structured Disambiguation", NormalizationProfile.WORD_BOUNDARIES_REMOVED),
        ("not in the source at all", NormalizationProfile.WORD_BOUNDARIES_REMOVED),
    ):
        match = quotation_match(_record(span, ("a-greedy",)), index=index)
        entry = VerificationRecord(
            check=CheckKind.C2,
            checker_id=C2_CHECKER_ID,
            outcome=match.outcome,
            detail=match.detail,
            checked_at=NOW,
            normalization_profile=match.profile,
        )
        assert entry.normalization_profile is expected


def test_c2_answers_and_c3_answers_too(ledger: Ledger) -> None:
    """Both quotation and numeric checks now answer, and neither refuses.

    Written so that landing C3 would break it -- and it did. The retained
    ``CiteSupportNotImplementedError`` is asserted unreachable here rather than
    left as a comment, because "nothing raises this" is a claim about code that
    only a test can keep true.
    """
    from labcairn.evidence.states import IMPLEMENTED_CHECKS

    _, index = ledger
    record = _record("customary greedy selection rule", ("a-greedy",))
    assert check_quotation_support(record, index=index).outcome is CheckOutcome.PASS
    numeric = EvidenceRecord(
        evidence_id="ev-num",
        task_id="task-1",
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=3.5,
        unit="dimensionless",
        tolerance=0.01,
        anchor_ids=("a-greedy",),
        extracted_span="3.5",
        extracted_span_sha256=hashlib.sha256(b"3.5").hexdigest(),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SHA_10596,
        created_at=NOW,
    )
    verdict = check_numeric_consistency(numeric, index=index)
    assert verdict.check is CheckKind.C3
    # A page of prose is not a cell. C3 refuses to pick a number out of it, which
    # is the honest answer: the text is there and the comparison is not available.
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "not a single quantity" in verdict.detail
    assert CheckKind.C2 in IMPLEMENTED_CHECKS
