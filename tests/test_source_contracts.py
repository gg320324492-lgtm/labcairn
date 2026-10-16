"""LC-P1-02 — the source/anchor contracts, and the malformed payloads they refuse.

Covers ``src/labcairn/sources/``: :class:`~labcairn.sources.source.Source`,
:class:`~labcairn.sources.source.SourceAnchor`, and the discriminated locator
union in :mod:`labcairn.sources.locators`.

Four properties are under test, in this order of importance:

1. **Precision.** A locator says exactly where it points — page and character
   span, line and section, row and column, sheet and cell, or inputs plus
   operator plus parameters. A prose label cannot do this, which is why
   ``SourceAnchor`` has no label field and :func:`describe_locator` is the only
   rendering path.
2. **Round-trip fidelity.** The same object serialises to the same bytes every
   time, including after a parse, because the ledger is compared, not eyeballed.
3. **Refusal.** Malformed JSON, unknown enum values, cross-type field mixing,
   missing required fields and both older *and* newer schema versions are
   rejected. Silently correcting any of them is how a ledger starts lying.
4. **Closedness.** The locator union has five members and the enum sets are
   closed; an unlisted value reaches no model and raises.

Every test name that quotes a contract quotes it from
``docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md`` or
``docs/ARCHITECTURE.md``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from labcairn.sources import (
    SOURCE_SCHEMA_VERSION,
    AnchorKind,
    ComputationLocator,
    CsvLocator,
    LocatorKind,
    NonEmptyText,
    PdfLocator,
    Source,
    SourceAnchor,
    SourceIdentifier,
    SourceIdentifierKind,
    SourceKind,
    SourceReadability,
    TextLocator,
    XlsxLocator,
    describe_locator,
)
from labcairn.sources.locators import LOCATOR_MODELS

pytestmark = pytest.mark.unit

# A canonical lowercase sha256. Used wherever a test needs "some content hash"
# and is not testing the hash rules themselves.
HASH_A = "a" * 64
HASH_B = "b" * 64


def assert_round_trips[ModelT: BaseModel](model: type[ModelT], instance: ModelT) -> str:
    """Serialise, parse, serialise again — the three renderings must be identical bytes.

    Also asserts the second dump of the *same live object* matches, so a
    non-deterministic field (an unordered set, a default-dict that re-inserts) is
    caught here rather than in a downstream byte comparison.
    """
    first = instance.model_dump_json()
    assert instance.model_dump_json() == first, "serialisation is not stable across calls"
    second = model.model_validate_json(first).model_dump_json()
    third = model.model_validate_json(second).model_dump_json()
    assert first == second, "a round-trip through JSON changed the bytes"
    assert second == third, "the round-trip has not reached a fixed point"
    assert model.model_validate_json(first) == instance, "the round-trip changed the object"
    return first


def rejects(model: type[BaseModel], payload: dict[str, Any]) -> str:
    """Assert ``payload`` is refused, and return the dict-path message to assert *why*.

    Both entry points are checked because LC-P1-02's acceptance is about
    *payloads*, and a payload arrives as JSON. A validator that only fires on
    ``model_validate`` is a write path that still lets bad rows in.

    The two messages are deliberately not compared for equality: Pydantic picks a
    different error code for the same rejection depending on whether the value
    arrived as a dict or as parsed JSON (``dict_type`` vs
    ``model_attributes_type``, ``extra_forbidden`` vs ``missing``). The contract
    under test is *refusal*, not the wording, and a wording change upstream is
    not a reason to change this file.
    """
    with pytest.raises(ValidationError) as from_dict:
        model.model_validate(payload)
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload))
    return str(from_dict.value)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _source_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_id": "src-paper-1",
        "kind": "pdf",
        "display_name": "A paper about things",
        "relative_path": "refs/paper.pdf",
        "content_sha256": HASH_A,
        "size_bytes": 412_993,
        "ingested_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _anchor_payload(locator: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "anchor_id": "anc-1",
        "source_id": "src-paper-1",
        "kind": "quotation",
        "locator": locator,
        "bound_source_sha256": HASH_A,
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Positive: round trips and precision
# ---------------------------------------------------------------------------


def test_source_round_trips_byte_identically() -> None:
    """A source is stored, reloaded and compared — so the bytes must be stable."""
    source = Source.model_validate(_source_payload())
    assert_round_trips(Source, source)


def test_source_anchor_round_trips_byte_identically() -> None:
    anchor = SourceAnchor.model_validate(
        _anchor_payload({"locator_kind": "pdf", "page": 12, "char_start": 0, "char_end": 512})
    )
    assert_round_trips(SourceAnchor, anchor)


@pytest.mark.parametrize(
    ("locator_payload", "expected"),
    [
        (
            {"locator_kind": "pdf", "page": 12, "char_start": 0, "char_end": 512},
            "pdf: page 12, chars 0-512",
        ),
        ({"locator_kind": "pdf", "page": 1}, "pdf: page 1"),
        (
            {"locator_kind": "text", "line": 40, "line_end": 44, "section": "Results"},
            'text: line 40-44, section "Results"',
        ),
        ({"locator_kind": "text", "line": 7}, "text: line 7"),
        (
            {"locator_kind": "csv", "row": 118, "column": "yield_pct"},
            "csv: row 118, column 'yield_pct'",
        ),
        ({"locator_kind": "xlsx", "sheet_name": "Run 3", "cell_ref": "B12"}, "xlsx: Run 3!B12"),
        (
            {
                "locator_kind": "computation",
                "operator_id": "labcairn.analysis.mean",
                "operator_version": "1.2.0",
                "parameters": {"axis": 0},
                "input_hashes": [HASH_A, HASH_B],
            },
            "computation: labcairn.analysis.mean@1.2.0 over 2 inputs",
        ),
        (
            {
                "locator_kind": "computation",
                "operator_id": "labcairn.analysis.mean",
                "operator_version": "1.2.0",
                "input_hashes": [HASH_A],
            },
            "computation: labcairn.analysis.mean@1.2.0 over 1 input",
        ),
    ],
    ids=[
        "pdf-with-span",
        "pdf-whole-page",
        "text-line-range",
        "text-single-line",
        "csv-row-column",
        "xlsx-sheet-cell",
        "computation-two-inputs",
        "computation-one-input",
    ],
)
def test_every_locator_kind_locates_and_round_trips(
    locator_payload: dict[str, Any], expected: str
) -> None:
    """All five kinds address their material exactly, and render from structure.

    The rendering is asserted because it is computed from the structured fields.
    There is no stored label that could disagree with them — the failure mode
    ADR-0004 identifies in PaperQA2, where ``"paper.pdf pages 1-3"`` is the only
    locator there is.
    """
    anchor = SourceAnchor.model_validate(_anchor_payload(locator_payload))

    assert anchor.locator.locator_kind.value == locator_payload["locator_kind"]
    assert describe_locator(anchor.locator) == expected
    assert_round_trips(SourceAnchor, anchor)


def test_computation_locator_records_inputs_operator_and_parameters() -> None:
    """LC-P1-10's reproducibility anchor: which bytes, which operator, which settings."""
    anchor = SourceAnchor.model_validate(
        _anchor_payload(
            {
                "locator_kind": "computation",
                "operator_id": "labcairn.analysis.grouped_aggregate",
                "operator_version": "0.4.1",
                "parameters": {"by": "treatment", "agg": "mean", "na": "skip"},
                "input_hashes": [HASH_A, HASH_B],
            }
        )
    )
    assert isinstance(anchor.locator, ComputationLocator)
    assert anchor.locator.operator_id == "labcairn.analysis.grouped_aggregate"
    assert anchor.locator.operator_version == "0.4.1"
    assert anchor.locator.parameters == {"by": "treatment", "agg": "mean", "na": "skip"}
    assert anchor.locator.input_hashes == (HASH_A, HASH_B)


def test_locator_kinds_are_closed_at_five_members() -> None:
    """ADR-0004 I2's spirit applied to locators: no "and then some other format"."""
    assert {member.value for member in LocatorKind} == {"pdf", "text", "csv", "xlsx", "computation"}
    assert len(LOCATOR_MODELS) == 5
    # Every member of the union is reachable from LOCATOR_MODELS, so the
    # "exhaustive tests" comment on it cannot rot.
    assert {model.__name__ for model in LOCATOR_MODELS} == {
        "PdfLocator",
        "TextLocator",
        "CsvLocator",
        "XlsxLocator",
        "ComputationLocator",
    }


def test_source_with_identifiers_round_trips() -> None:
    source = Source.model_validate(
        _source_payload(
            identifiers=[
                {"kind": "doi", "value": "10.1038/s41586-021-03819-2"},
                {"kind": "arxiv", "value": "2103.00020"},
            ]
        )
    )
    assert source.identifiers[0] == SourceIdentifier(
        kind=SourceIdentifierKind.DOI, value="10.1038/s41586-021-03819-2"
    )
    assert_round_trips(Source, source)


def test_unreadable_source_requires_and_keeps_its_disclosure() -> None:
    """ADR-0004 A7: 'OCR not available' is part of the record."""
    source = Source.model_validate(
        _source_payload(
            kind="pdf",
            readability="unreadable_no_ocr",
            readability_disclosure="Scanned PDF: no text layer. OCR is not available in Phase 1.",
        )
    )
    assert source.readability is SourceReadability.UNREADABLE_NO_OCR
    assert source.readability_disclosure is not None
    assert_round_trips(Source, source)


def test_anchor_binds_the_source_hash_it_was_made_against() -> None:
    """ADR-0004 I4/A2: the anchor records what the source hashed to *then*.

    This is what makes drift detectable. A field that re-read the source at check
    time would always match, and would make A2 untestable.
    """
    anchor = SourceAnchor.model_validate(
        _anchor_payload({"locator_kind": "pdf", "page": 3}, bound_source_sha256=HASH_B)
    )
    drifted = Source.model_validate(_source_payload(content_sha256=HASH_A))

    assert anchor.bound_source_sha256 != drifted.content_sha256
    assert "bound" not in json.loads(anchor.model_dump_json()).get("locator", {})


# ---------------------------------------------------------------------------
# Negative: malformed and hostile payloads
# ---------------------------------------------------------------------------


def test_malformed_json_is_rejected_not_repaired() -> None:
    for broken in ('{"schema_version": 1, "source_id": ', "not json at all", "", "[]"):
        with pytest.raises(ValidationError):
            Source.model_validate_json(broken)


def test_missing_required_field_is_rejected() -> None:
    """A record missing an identity field is not a record with a default identity."""
    for field in (
        "source_id",
        "kind",
        "display_name",
        "relative_path",
        "content_sha256",
        "ingested_at",
    ):
        payload = _source_payload()
        del payload[field]
        assert field in rejects(Source, payload)

    anchor_payload = _anchor_payload({"locator_kind": "pdf", "page": 3})
    del anchor_payload["bound_source_sha256"]
    assert "bound_source_sha256" in rejects(SourceAnchor, anchor_payload)


def test_unknown_enum_values_are_rejected_not_coerced() -> None:
    """An unlisted enum member reaches no model and raises — ADR-0003 §C1's rule."""
    for unknown in ("docx", "PDF", "verified", "pdf "):
        message = rejects(Source, _source_payload(kind=unknown))
        assert unknown.strip() in message

    message = rejects(SourceAnchor, _anchor_payload({"locator_kind": "docx", "page": 3}))
    assert "docx" in message

    message = rejects(
        SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": 3}, kind="quote")
    )
    assert "quote" in message


def test_cross_type_locator_fields_are_rejected() -> None:
    """A page number on a CSV locator is a mistake, not an ignored extra field.

    ``extra="forbid"`` plus the discriminator means the union cannot accept a
    mixed payload and quietly drop the part it does not understand.
    """
    cases = [
        {"locator_kind": "csv", "page": 3, "column": "yield_pct"},
        {"locator_kind": "csv", "row": 3, "column": "yield_pct", "cell_ref": "B12"},
        {"locator_kind": "xlsx", "sheet_name": "S", "cell_ref": "B12", "page": 3},
        {"locator_kind": "pdf", "page": 3, "row": 12},
        {"locator_kind": "text", "line": 4, "sheet_name": "S"},
    ]
    for mixed in cases:
        rejects(SourceAnchor, _anchor_payload(mixed))


def test_wrong_schema_version_is_rejected_in_both_directions() -> None:
    """Neither an older nor a newer payload is guessed at.

    Guessing is the failure: reading a v0 record through a v1 model drops the
    fields this build has never heard of and writes them back out as if they had
    never existed.
    """
    for version in (0, 2, 99):
        message = rejects(Source, _source_payload(schema_version=version))
        assert "unsupported Source schema_version" in message
        assert str(version) in message

        message = rejects(
            SourceAnchor,
            _anchor_payload({"locator_kind": "pdf", "page": 3}, schema_version=version),
        )
        assert "unsupported SourceAnchor schema_version" in message


def test_unknown_extra_field_is_rejected() -> None:
    """``extra="forbid"``: a field this build does not know about is a version skew, not a note."""
    rejects(Source, _source_payload(page_count=12))
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3}, label="paper.pdf pages 1-3"),
    )


def test_naive_datetime_is_rejected() -> None:
    """Timestamps are UTC and aware; a naive one is not the same instant as anything."""
    rejects(Source, _source_payload(ingested_at="2026-01-01T00:00:00"))
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3}, created_at="2026-01-01T00:00:00"),
    )


@pytest.mark.parametrize(
    "bad_hash",
    ["A" * 64, "a" * 63, "a" * 65, "z" * 64, "", "sha256:" + "a" * 64],
    ids=["uppercase", "too-short", "too-long", "not-hex", "empty", "prefixed"],
)
def test_content_hash_must_be_canonical_lowercase_hex(bad_hash: str) -> None:
    """Uppercase is rejected, not downcased.

    Two spellings of one hash make ``matches(source_hash)`` a question with two
    possible answers, which is the bug ADR-0004's A2 is written against.
    """
    rejects(Source, _source_payload(content_sha256=bad_hash))
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3}, bound_source_sha256=bad_hash),
    )


@pytest.mark.parametrize("page", [0, -1, -12])
def test_page_numbers_are_one_based(page: int) -> None:
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": page}))


def test_pdf_character_span_must_be_both_ends_and_ordered() -> None:
    """A half-open span with one endpoint cannot be located; both or neither."""
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": 3, "char_start": 10}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": 3, "char_end": 10}))
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3, "char_start": 20, "char_end": 20}),
    )
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3, "char_start": 30, "char_end": 20}),
    )
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "pdf", "page": 3, "char_start": -1, "char_end": 20}),
    )


def test_text_line_range_must_not_run_backwards() -> None:
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "text", "line": 40, "line_end": 10}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "text", "line": 0}))


@pytest.mark.parametrize(
    "cell_ref",
    ["b12", "B", "12", "B0", "B12X", "$B$12", "AAAA1", "", "B12 "],
    ids=[
        "lowercase",
        "no-row",
        "no-column",
        "row-zero",
        "trailing-junk",
        "absolute-markers",
        "too-wide",
        "empty",
        "trailing-space",
    ],
)
def test_xlsx_cell_ref_is_canonical_a1(cell_ref: str) -> None:
    """``b12`` and ``B12`` name one cell; storing both makes ``seen_cells()`` lie."""
    rejects(
        SourceAnchor,
        _anchor_payload({"locator_kind": "xlsx", "sheet_name": "S", "cell_ref": cell_ref}),
    )


def test_csv_locator_requires_row_and_column() -> None:
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "csv", "row": 3}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "csv", "column": "yield_pct"}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "csv", "row": 0, "column": "y"}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "csv", "row": 1, "column": "   "}))


def test_computation_locator_requires_sorted_unique_inputs() -> None:
    """Two spellings of one run is one too many ways for the comparison to disagree."""
    base = {
        "locator_kind": "computation",
        "operator_id": "labcairn.analysis.mean",
        "operator_version": "1.0.0",
    }
    rejects(SourceAnchor, _anchor_payload({**base, "input_hashes": []}))
    rejects(SourceAnchor, _anchor_payload({**base, "input_hashes": [HASH_A, HASH_A]}))
    message = rejects(SourceAnchor, _anchor_payload({**base, "input_hashes": [HASH_B, HASH_A]}))
    assert "sorted order" in message
    # The sorted form is accepted, which is the point of the rule.
    SourceAnchor.model_validate(_anchor_payload({**base, "input_hashes": [HASH_A, HASH_B]}))


def test_computation_locator_requires_operator_identity() -> None:
    base = {"locator_kind": "computation", "input_hashes": [HASH_A]}
    rejects(SourceAnchor, _anchor_payload(base))
    rejects(SourceAnchor, _anchor_payload({**base, "operator_id": "labcairn.analysis.mean"}))
    rejects(SourceAnchor, _anchor_payload({**base, "operator_id": "mean", "operator_version": ""}))


def test_workspace_relative_paths_are_rejected_not_normalised() -> None:
    """ADR-0003 §C4 canonicalisation, enforced.

    An absolute path or a ``..`` segment is a fact about the proposal, and
    quietly rewriting it into a relative one is how a read escapes the workspace.
    """
    for bad in (
        "/etc/passwd",
        "C:/Users/pc/refs/paper.pdf",
        "refs\\paper.pdf",
        "../outside/paper.pdf",
        "refs/../../outside/paper.pdf",
        "./paper.pdf",
        "refs//paper.pdf",
        " paper.pdf",
        "",
    ):
        rejects(Source, _source_payload(relative_path=bad))

    # The canonical form is accepted.
    Source.model_validate(_source_payload(relative_path="refs/sub/paper.pdf"))


def test_readability_and_disclosure_are_a_pair() -> None:
    """An unreadable source without a disclosure, or a readable one with a disclosure."""
    message = rejects(Source, _source_payload(readability="unreadable_no_ocr"))
    assert "readability_disclosure" in message

    message = rejects(Source, _source_payload(readability_disclosure="OCR not available"))
    assert "readability_disclosure" in message


def test_unknown_readability_is_rejected() -> None:
    rejects(
        Source,
        _source_payload(readability="unreadable", readability_disclosure="scanned, no OCR"),
    )


def test_duplicate_source_identifiers_are_rejected() -> None:
    rejects(
        Source,
        _source_payload(
            identifiers=[
                {"kind": "doi", "value": "10.1000/xyz"},
                {"kind": "doi", "value": "10.1000/xyz"},
            ]
        ),
    )


@pytest.mark.parametrize(
    "bad_doi",
    ["10.1000", "10./xyz", "https://doi.org/10.1000/xyz", "not a doi", "10.1000/"],
)
def test_identifier_shape_is_checked_but_existence_is_not_claimed(bad_doi: str) -> None:
    """Shape only. LC-P1-09's fabricated-DOI case needs C1, not a regex."""
    message = rejects(Source, _source_payload(identifiers=[{"kind": "doi", "value": bad_doi}]))
    assert "does not establish that the work exists" in message

    # The converse, stated as a test: a well-formed DOI passes shape validation,
    # which is NOT a claim that the work exists. If this assertion ever needs a
    # network call, something has grown an existence check nobody asked for.
    Source.model_validate(_source_payload(identifiers=[{"kind": "doi", "value": "10.1000/xyz"}]))


def test_local_identifier_kind_is_unconstrained() -> None:
    """A local handle makes no external claim, so there is no external shape to check."""
    source = Source.model_validate(
        _source_payload(identifiers=[{"kind": "local", "value": "workspace://whatever/this is"}])
    )
    assert source.identifiers[0].kind is SourceIdentifierKind.LOCAL


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n  "])
def test_blank_strings_are_rejected_not_stripped(blank: str) -> None:
    """A validator that stripped would be silently correcting the input."""
    rejects(Source, _source_payload(display_name=blank))
    rejects(Source, _source_payload(source_id=blank))


def test_frozen_models_cannot_be_edited_in_place() -> None:
    """A locator that can be mutated would change what a logged check was run against."""
    source = Source.model_validate(_source_payload())
    with pytest.raises(ValidationError):
        source.display_name = "Something else"

    anchor = SourceAnchor.model_validate(_anchor_payload({"locator_kind": "pdf", "page": 3}))
    with pytest.raises(ValidationError):
        anchor.locator = CsvLocator(row=1, column="x")


def test_locator_is_resolved_from_the_payload_not_a_string() -> None:
    """A locator may not arrive as prose.

    This is the structural half of ADR-0004's rejection of PaperQA2: there is no
    field a caller could put ``"paper.pdf pages 1-3"`` into.
    """
    rejects(SourceAnchor, _anchor_payload("paper.pdf pages 1-3"))  # type: ignore[arg-type]
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": "3"}))
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": True}))


@pytest.mark.parametrize(
    ("bad_page", "note"),
    [
        ("3", "a quoted number"),
        (3.0, "a float where an int belongs"),
        (True, "a bool where an int belongs"),
        (None, "an explicit null"),
    ],
)
def test_numeric_locator_fields_are_not_silently_coerced(bad_page: Any, note: str) -> None:
    """Pydantic validates in lax mode by default, and lax mode reads ``"3"`` as 3.

    That is silent correction, and LC-P1-02's acceptance says malformed payloads
    are rejected. Every numeric field in these contracts therefore sets
    ``strict=True``; this test is the regression guard that it stays set.
    """
    assert isinstance(note, str)
    rejects(SourceAnchor, _anchor_payload({"locator_kind": "pdf", "page": bad_page}))


def test_size_bytes_is_not_silently_coerced() -> None:
    rejects(Source, _source_payload(size_bytes="412993"))
    rejects(Source, _source_payload(size_bytes=-1))
    Source.model_validate(_source_payload(size_bytes=0))


def test_csv_and_text_and_xlsx_models_are_exported_and_constructible() -> None:
    """The concrete locator classes are public, so callers can build one without a dict."""
    assert CsvLocator(row=1, column="x").locator_kind is LocatorKind.CSV
    assert TextLocator(line=1).locator_kind is LocatorKind.TEXT
    assert XlsxLocator(sheet_name="S", cell_ref="A1").locator_kind is LocatorKind.XLSX
    assert PdfLocator(page=1).locator_kind is LocatorKind.PDF
    assert (
        ComputationLocator(
            operator_id="op", operator_version="1", input_hashes=(HASH_A,)
        ).locator_kind
        is LocatorKind.COMPUTATION
    )


def test_non_empty_text_alias_is_exported_for_callers_composing_anchors() -> None:
    """``NonEmptyText`` is public because ids in all three packages share it."""
    assert NonEmptyText is not None


def test_anchor_kinds_are_closed() -> None:
    assert {member.value for member in AnchorKind} == {
        "quotation",
        "numeric",
        "structural",
        "absence_scan",
    }


def test_source_kinds_are_closed() -> None:
    assert {member.value for member in SourceKind} == {
        "pdf",
        "markdown",
        "text",
        "csv",
        "xlsx",
        "other",
    }


def test_datetime_is_preserved_exactly_across_the_round_trip() -> None:
    """Sub-second precision must survive; a ledger compared by hash needs it to."""
    stamp = datetime.fromisoformat("2026-03-04T05:06:07.891011+00:00")
    source = Source.model_validate(_source_payload(ingested_at=stamp))
    restored = Source.model_validate_json(source.model_dump_json())
    assert restored.ingested_at == source.ingested_at
    assert restored.ingested_at.tzinfo is not None
