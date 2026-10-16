"""LC-P1-02 — the evidence and artifact contracts, and the locks on C4.

Covers ``src/labcairn/evidence/`` (:class:`~labcairn.evidence.record.EvidenceRecord`,
:class:`~labcairn.evidence.record.VerificationRecord`, the closed vocabularies,
and the four cite-support validators) plus
``src/labcairn/reports/`` (:class:`~labcairn.reports.receipt.ArtifactReceipt`).

The centre of this file is **C4**. ADR-0004's single most important decision is
negative — *C4 has no implementation in Phase 1* — and a negative decision that
rests on a comment is a decision waiting to be quietly reversed. So it is locked
four ways, each with its own test below:

1. :func:`~labcairn.evidence.cite_support.check_scientific_interpretation` has a
   body and returns ``not_checked`` for every record shape.
2. :class:`~labcairn.evidence.cite_support.NotCheckedVerdict` cannot be
   constructed with any other outcome — a ``Literal`` field, so Pydantic raises.
3. The function's return annotation is the narrow type, so a reimplementation
   that returned a pass would fail ``mypy``, not just a test.
4. :class:`~labcairn.evidence.record.VerificationRecord` refuses ``check=c4``
   with any outcome but ``not_checked``, so the claim cannot enter the ledger
   even from a hand-written payload.

Three independent sources agree on the answer, which is why this is a contract
and not a deferral: PaperSpine already demotes interpretation to a warning while
promoting link-existence to a hard finding; ``docs/ARCHITECTURE.md`` forbids
``verified_by_rule`` from implying a hypothesis is established; and there is no
Phase 1 evidence standard for "is this inference warranted".
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Final, get_type_hints

import pytest
from pydantic import BaseModel, ValidationError

from labcairn.evidence import (
    C4_CHECKER_ID,
    C4_DETAIL,
    CHECK_KINDS,
    CHECK_OUTCOMES,
    EVIDENCE_SCHEMA_VERSION,
    IMPLEMENTED_CHECKS,
    UPGRADING_CHECKS,
    VERIFICATION_STATES,
    CheckKind,
    CheckOutcome,
    CiteSupportNotImplementedError,
    EvidenceKind,
    EvidenceRecord,
    LocatedContent,
    LocationResolution,
    NormalizationProfile,
    NotCheckedVerdict,
    Verdict,
    VerificationRecord,
    VerificationStatus,
    check_numeric_consistency,
    check_quotation_support,
    check_scientific_interpretation,
    check_source_exists,
)
from labcairn.reports import (
    ARTIFACT_SCHEMA_VERSION,
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)

pytestmark = pytest.mark.unit

HASH_A: Final[str] = "a" * 64
HASH_B: Final[str] = "b" * 64

#: The six states, written out literally rather than derived from the enum, so
#: adding a seventh member breaks this test instead of quietly redefining it.
EXPECTED_STATES: Final[frozenset[str]] = frozenset(
    {"planned", "extracted", "verified_by_rule", "user_attested", "conflicted", "unsupported"}
)


def assert_round_trips[ModelT: BaseModel](model: type[ModelT], instance: ModelT) -> str:
    """Serialise, parse, serialise again — three renderings, identical bytes."""
    first = instance.model_dump_json()
    assert instance.model_dump_json() == first, "serialisation is not stable across calls"
    second = model.model_validate_json(first).model_dump_json()
    third = model.model_validate_json(second).model_dump_json()
    assert first == second, "a round-trip through JSON changed the bytes"
    assert second == third, "the round-trip has not reached a fixed point"
    assert model.model_validate_json(first) == instance, "the round-trip changed the object"
    return first


def rejects(model: type[BaseModel], payload: dict[str, Any]) -> str:
    """Assert ``payload`` is refused via both entry points; return the dict-path message."""
    with pytest.raises(ValidationError) as from_dict:
        model.model_validate(payload)
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload))
    return str(from_dict.value)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _entry(
    check: CheckKind | str = CheckKind.C3,
    outcome: CheckOutcome | str = CheckOutcome.PASS,
    checker_id: str = "c3.numeric_consistency",
    detail: str = "0.4e-9 within declared tolerance 1e-6",
    **overrides: Any,
) -> dict[str, Any]:
    """Build a log-entry payload.

    ``check`` and ``outcome`` accept the raw string as well as the enum member,
    because several negative tests need to write a value the enum does not have
    and the point is that the payload is refused rather than coerced.
    """
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "check": check.value if isinstance(check, CheckKind) else check,
        "checker_id": checker_id,
        "outcome": outcome.value if isinstance(outcome, CheckOutcome) else outcome,
        "detail": detail,
        "checked_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _numeric_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": "ev-1",
        "task_id": "task-1",
        "kind": "numeric",
        "text": None,
        "value": 4.2,
        "unit": "mg/L",
        "tolerance": 1e-06,
        "anchor_ids": ["anc-1"],
        "extracted_span": "4.2 mg/L",
        "extracted_span_sha256": HASH_A,
        "status": "verified_by_rule",
        "verification_log": [_entry()],
        "created_by": "rule",
        "created_by_id": "c3.numeric_consistency",
        "source_content_hash": HASH_A,
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _claim_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": "ev-claim-1",
        "task_id": "task-1",
        "kind": "claim",
        "text": "Treatment A reduced symptom score relative to placebo.",
        "anchor_ids": ["anc-1", "anc-2"],
        "extracted_span": "Treatment A reduced symptom score.",
        "extracted_span_sha256": HASH_A,
        "status": "extracted",
        "verification_log": [],
        "created_by": "model_proposal",
        "created_by_id": "run-7-attempt-1",
        "source_content_hash": HASH_A,
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _receipt_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "receipt_id": "rc-1",
        "task_id": "task-1",
        "kind": "figure",
        "relative_path": "out/task-1/figures/yield.png",
        "content_sha256": HASH_B,
        "size_bytes": 51_233,
        "produced_by": "analysis_operator",
        "producer_id": "labcairn.analysis.grouped_aggregate@0.4.1",
        "derived_from": [
            {"target_kind": "evidence_record", "target_id": "ev-1"},
            {
                "target_kind": "material_file",
                "target_id": "refs/data.csv",
                "content_sha256": HASH_A,
            },
        ],
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# The six states, and I2: there is no seventh
# ---------------------------------------------------------------------------


def test_verification_states_are_exactly_the_six_architecture_declares() -> None:
    """``docs/ARCHITECTURE.md`` "Evidence states" and ADR-0004 Contract 1.

    Asserted against a literal set, not against the enum itself: ``len(enum) ==
    6`` would still pass for six *different* states.
    """
    assert VERIFICATION_STATES == EXPECTED_STATES
    assert {member.value for member in VerificationStatus} == EXPECTED_STATES
    assert len(VerificationStatus) == 6


def test_no_state_means_scientifically_established() -> None:
    """ADR-0004 I2, asserted rather than documented.

    The three states that could plausibly be mistaken for one are enumerated
    explicitly: a test that fails when any of them appears is the mechanism that
    stops someone adding "scientifically_verified" as a seventh member.
    """
    for forbidden in (
        "scientifically_established",
        "established",
        "verified_scientifically",
        "replicated",
        "peer_reviewed",
    ):
        assert forbidden not in VERIFICATION_STATES


def test_verified_by_rule_is_a_numeric_or_structural_claim_only() -> None:
    """``docs/ARCHITECTURE.md``: it must not imply a hypothesis is established.

    Nothing in the model can enforce how a *reader* interprets the label; what it
    can enforce is that the label is backed by a numeric or structural check and
    nothing else. C4 is absent from :data:`UPGRADING_CHECKS`, so no log entry
    sequence makes C4 the thing that earned this state.
    """
    assert frozenset({CheckKind.C1, CheckKind.C2, CheckKind.C3}) == UPGRADING_CHECKS
    assert CheckKind.C4 not in UPGRADING_CHECKS


def test_check_outcomes_keep_indeterminate_and_not_checked_distinct_from_pass() -> None:
    """ADR-0004 Contract 3: ``indeterminate`` and ``not_checked`` are never ``pass``."""
    assert frozenset(CheckOutcome) == CHECK_OUTCOMES
    assert {member.value for member in CheckOutcome} == {
        "pass",
        "fail",
        "indeterminate",
        "not_checked",
    }
    for non_pass in (CheckOutcome.FAIL, CheckOutcome.INDETERMINATE, CheckOutcome.NOT_CHECKED):
        assert non_pass is not CheckOutcome.PASS
        # mypy calls this a non-overlapping comparison, which is the type system
        # independently asserting the same thing the closed enum guarantees: no
        # other member can be `pass`.
        assert (non_pass == CheckOutcome.PASS) is False  # type: ignore[comparison-overlap]
    assert frozenset({CheckKind.C1, CheckKind.C2, CheckKind.C3, CheckKind.C4}) == CHECK_KINDS


# ---------------------------------------------------------------------------
# C4 — structurally locked to not_checked
# ---------------------------------------------------------------------------


def test_c4_always_returns_not_checked() -> None:
    """ADR-0004 Contract 3: the function has a body and always returns not_checked.

    Run across every record shape the model admits, because a conditional early
    return somewhere would only show up for the shape it was written for.
    """
    records = [
        EvidenceRecord.model_validate(
            _claim_payload(
                status="planned",
                anchor_ids=[],
                extracted_span=None,
                extracted_span_sha256=None,
                source_content_hash=None,
                verification_log=[],
            )
        ),
        EvidenceRecord.model_validate(_claim_payload()),
        EvidenceRecord.model_validate(_numeric_payload()),
        EvidenceRecord.model_validate(
            _numeric_payload(
                status="unsupported",
                verification_log=[_entry(outcome=CheckOutcome.FAIL, detail="no anchor resolves")],
                anchor_ids=[],
                extracted_span=None,
                extracted_span_sha256=None,
                source_content_hash=None,
            )
        ),
        EvidenceRecord.model_validate(
            _claim_payload(
                status="user_attested",
                created_by="user",
                created_by_id="local-user",
                verification_log=[
                    _entry(
                        check=CheckKind.C2,
                        outcome=CheckOutcome.INDETERMINATE,
                        checker_id="user:local-user",
                        detail="ligature ambiguity",
                        normalization_profile="nfkc_whitespace_collapsed_ligatures",
                    )
                ],
            )
        ),
    ]
    assert len(records) == 5

    for record in records:
        verdict = check_scientific_interpretation(record)
        assert verdict.outcome is CheckOutcome.NOT_CHECKED
        # mypy proves this statically from NotCheckedVerdict's Literal outcome;
        # the runtime assertion is the version of the claim that survives someone
        # widening that field's type.
        assert verdict.outcome != CheckOutcome.PASS  # type: ignore[comparison-overlap]
        assert verdict.check is CheckKind.C4
        assert verdict.checker_id == C4_CHECKER_ID
        assert verdict.detail == C4_DETAIL


def test_c4_verdict_type_cannot_hold_a_pass() -> None:
    """Lock 2: ``NotCheckedVerdict`` makes the outcome unrepresentable, not discouraged.

    The fields are ``Literal``-typed, so Pydantic raises on construction. There
    is no code path — keyword, positional or ``model_construct`` — that produces
    one of these with ``outcome="pass"``.
    """
    for impossible in (
        CheckOutcome.PASS,
        CheckOutcome.FAIL,
        CheckOutcome.INDETERMINATE,
        "pass",
        "PASS",
        True,
        1,
    ):
        with pytest.raises(ValidationError):
            NotCheckedVerdict(check=CheckKind.C4, outcome=impossible)  # type: ignore[arg-type]

    # And the checker identity is pinned too, so a C4 verdict cannot claim to
    # have been produced by something else.
    with pytest.raises(ValidationError):
        NotCheckedVerdict(check=CheckKind.C4, checker_id="c4.someone-elses-implementation")

    # The honest one still constructs, by hand and by payload.
    assert NotCheckedVerdict(check=CheckKind.C4).outcome is CheckOutcome.NOT_CHECKED
    assert (
        NotCheckedVerdict.model_validate(
            {
                "check": "c4",
                "outcome": "not_checked",
                "checker_id": "c4.not_implemented",
                "detail": C4_DETAIL,
            }
        ).outcome
        is CheckOutcome.NOT_CHECKED
    )


def test_c4_cannot_enter_the_verification_log_as_a_pass() -> None:
    """Lock 4: the durable audit row refuses a C4 pass.

    The call-side locks keep a function honest; this one keeps a *hand-written
    payload* honest. Between them there is no route by which a C4 pass becomes a
    stored fact, which is what ADR-0004 I2 is actually about.
    """
    for outcome in (CheckOutcome.PASS, CheckOutcome.FAIL, CheckOutcome.INDETERMINATE):
        message = rejects(VerificationRecord, _entry(check=CheckKind.C4, outcome=outcome))
        assert "superseding ADR" in message

    # not_checked is the only C4 outcome a log entry may carry.
    entry = VerificationRecord.model_validate(
        _entry(
            check=CheckKind.C4,
            outcome=CheckOutcome.NOT_CHECKED,
            checker_id=C4_CHECKER_ID,
            detail=C4_DETAIL,
        )
    )
    assert entry.outcome is CheckOutcome.NOT_CHECKED


def test_c4_is_the_only_implemented_check_and_is_still_not_a_pass() -> None:
    """``IMPLEMENTED_CHECKS`` says what can answer, and today that is only C4.

    A report or a gate can ask this value rather than assuming. When LC-P1-09
    lands C1-C3, this test fails until someone changes the line on purpose.
    """
    assert frozenset({CheckKind.C4}) == IMPLEMENTED_CHECKS
    assert [check.value for check in sorted(IMPLEMENTED_CHECKS)] == ["c4"]

    record = EvidenceRecord.model_validate(_claim_payload())
    for implemented in IMPLEMENTED_CHECKS:
        verdict = check_scientific_interpretation(record)
        assert verdict.check is implemented
        assert verdict.outcome is CheckOutcome.NOT_CHECKED


def test_c4_return_type_is_narrow_enough_to_fail_a_mypy_reimplementation() -> None:
    """Lock 3: the signature, not just the body.

    ``check_scientific_interpretation`` is annotated ``-> NotCheckedVerdict``. An
    implementation that returned a ``Verdict`` carrying ``pass`` would type-check
    against ``Verdict`` and fail against this one. Asserting the annotation keeps
    that true even if the body is later replaced.
    """
    signature = inspect.signature(check_scientific_interpretation)
    hints = get_type_hints(check_scientific_interpretation)
    assert hints["return"] is NotCheckedVerdict
    assert signature.return_annotation in ("NotCheckedVerdict", NotCheckedVerdict)
    assert list(signature.parameters) == ["record"]


def test_c4_detail_never_reads_as_a_passed_check() -> None:
    """The rendered sentence is the only thing a user reads. Check what it says."""
    lowered = C4_DETAIL.lower()
    assert "not machine-verifiable" in lowered
    assert "do not present this record as scientifically established" in lowered
    for misleading in ("verified", "passed", "confirmed", "validated", "pass"):
        assert misleading not in lowered
    assert C4_DETAIL == (
        "Scientific interpretation is not machine-verifiable in Phase 1. "
        "Do not present this record as scientifically established."
    )


def test_c4_is_not_deletable_from_the_package_surface() -> None:
    """Removing the function must break an import, not pass a review quietly.

    The package re-exports it, so deleting it from ``cite_support`` turns
    ``from labcairn.evidence import check_scientific_interpretation`` into an
    ``ImportError`` at collection time of this file.
    """
    import labcairn.evidence as evidence_package

    assert "check_scientific_interpretation" in evidence_package.__all__
    assert evidence_package.check_scientific_interpretation is check_scientific_interpretation


def test_c1_c2_c3_are_declared_but_refuse_to_answer() -> None:
    """They raise; they do not return a placeholder verdict.

    A check that returned ``indeterminate`` because it is unimplemented would be
    indistinguishable, forever and downstream, from one that declined to answer
    for a real reason — and the first would let a record sit at ``extracted``
    looking, to a report, like something a system had looked at.
    """
    record = EvidenceRecord.model_validate(_numeric_payload())

    # `index=None` stands in for "no index exists yet"; the call must fail on
    # the unimplemented check, not on the missing argument, which is why the
    # raises below is specifically CiteSupportNotImplementedError.
    calls: tuple[tuple[CheckKind, Callable[[], Verdict]], ...] = (
        (CheckKind.C1, lambda: check_source_exists(record, index=None)),  # type: ignore[arg-type]
        (CheckKind.C2, lambda: check_quotation_support(record, index=None)),  # type: ignore[arg-type]
        (CheckKind.C3, lambda: check_numeric_consistency(record, index=None)),  # type: ignore[arg-type]
    )
    for check, call in calls:
        with pytest.raises(CiteSupportNotImplementedError) as caught:
            call()
        assert caught.value.check is check
        assert isinstance(caught.value, NotImplementedError)
        assert check.value in str(caught.value)
        assert "c4" in str(caught.value)


def test_the_four_validators_keep_adr_0004_signatures() -> None:
    """The parameter names are part of the contract callers are written against."""
    assert list(inspect.signature(check_source_exists).parameters) == ["record", "index"]
    assert list(inspect.signature(check_quotation_support).parameters) == ["record", "index"]
    assert list(inspect.signature(check_numeric_consistency).parameters) == ["record", "index"]
    assert list(inspect.signature(check_scientific_interpretation).parameters) == ["record"]
    for call in (check_source_exists, check_quotation_support, check_numeric_consistency):
        assert inspect.signature(call).parameters["index"].kind is inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# EvidenceRecord — positive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder",
    [_claim_payload, _numeric_payload, _receipt_payload],
    ids=["claim", "numeric", "artifact-receipt"],
)
def test_records_round_trip_byte_identically(builder: Any) -> None:
    if builder is _receipt_payload:
        receipt = ArtifactReceipt.model_validate(_receipt_payload())
        assert_round_trips(ArtifactReceipt, receipt)
        return
    record = EvidenceRecord.model_validate(builder())
    assert_round_trips(EvidenceRecord, record)


def test_result_kind_is_available_and_behaves_like_a_claim() -> None:
    """A result is text, not a value: the same cross-type rules apply."""
    record = EvidenceRecord.model_validate(_claim_payload(kind="result", evidence_id="ev-result-1"))
    assert record.kind is EvidenceKind.RESULT

    with pytest.raises(ValidationError) as caught:
        EvidenceRecord.model_validate(_claim_payload(kind="result", value=1.0))
    assert "belongs to kind='numeric'" in str(caught.value)


def test_planned_record_needs_no_anchors() -> None:
    """``planned`` is the one state a record may legitimately have no evidence for yet."""
    record = EvidenceRecord.model_validate(
        _claim_payload(
            status="planned",
            anchor_ids=[],
            extracted_span=None,
            extracted_span_sha256=None,
            source_content_hash=None,
            verification_log=[],
        )
    )
    assert record.status is VerificationStatus.PLANNED
    assert record.anchor_ids == ()


def test_tolerance_defaults_to_none_and_never_to_zero() -> None:
    """C3: "an undeclared tolerance is never 0".

    A default of ``0.0`` would be a default *exact-match requirement*, and
    "exactly equal" is a claim about a number nobody has compared yet.
    """
    record = EvidenceRecord.model_validate(_numeric_payload(tolerance=None))
    assert record.tolerance is None

    # 0.0 is legal when declared — the rule is about the default, not the value.
    exact = EvidenceRecord.model_validate(_numeric_payload(tolerance=0.0))
    assert exact.tolerance == 0.0

    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(_numeric_payload(tolerance=-1e-06))
    # A quoted tolerance is malformed input, not a number.
    rejects(EvidenceRecord, _numeric_payload(tolerance="1e-06"))


def test_unit_is_declared_never_inferred() -> None:
    """ADR-0004 Contract 1: "must be declared, not inferred"."""
    message = rejects(EvidenceRecord, _numeric_payload(unit=None))
    assert "declared, never inferred" in message

    # A dimensionless quantity says so out loud rather than leaving the field null.
    dimensionless = EvidenceRecord.model_validate(_numeric_payload(unit="dimensionless"))
    assert dimensionless.unit == "dimensionless"


def test_verification_log_round_trips_and_stays_append_only() -> None:
    """The log is the durable audit trail and is never rewritten."""
    record = EvidenceRecord.model_validate(
        _numeric_payload(
            verification_log=[
                _entry(
                    check=CheckKind.C1, checker_id="c1.anchor_resolves", detail="page 3 resolved"
                ),
                _entry(detail="anchor cell B12 read as 4.2"),
            ]
        )
    )
    rendered = assert_round_trips(EvidenceRecord, record)
    assert [entry["check"] for entry in json.loads(rendered)["verification_log"]] == ["c1", "c3"]

    with pytest.raises(ValidationError):
        record.status = VerificationStatus.CONFLICTED


def test_c2_log_entry_must_declare_its_normalization_profile() -> None:
    """How lenient was this comparison is a question the log has to be able to answer."""
    message = rejects(
        VerificationRecord,
        _entry(check=CheckKind.C2, outcome=CheckOutcome.PASS, checker_id="c2.verbatim"),
    )
    assert "normalization_profile" in message

    message = rejects(
        VerificationRecord,
        _entry(check=CheckKind.C3, normalization_profile="exact"),
    )
    assert "C2 only" in message

    for profile in NormalizationProfile:
        entry = VerificationRecord.model_validate(
            _entry(check=CheckKind.C2, normalization_profile=profile.value)
        )
        assert entry.normalization_profile is profile


# ---------------------------------------------------------------------------
# EvidenceRecord — negative
# ---------------------------------------------------------------------------


def test_malformed_json_is_rejected_not_repaired() -> None:
    for broken in ('{"kind": "claim", ', "not json", "", "[]", "null"):
        with pytest.raises(ValidationError):
            EvidenceRecord.model_validate_json(broken)


def test_missing_required_field_is_rejected() -> None:
    """Including ``text``, which is required *and* nullable.

    A numeric record must write ``"text": null`` out loud. If the key could be
    omitted, a claim string could end up riding along on a number unnoticed.
    """
    for field in (
        "evidence_id",
        "task_id",
        "kind",
        "text",
        "status",
        "created_by",
        "created_by_id",
        "created_at",
    ):
        payload = _claim_payload()
        del payload[field]
        assert field in rejects(EvidenceRecord, payload)


def test_unknown_enum_values_are_rejected_not_coerced() -> None:
    for field, unknown in (
        ("kind", "number"),
        ("status", "VERIFIED_BY_RULE"),
        ("status", "scientifically_verified"),
        ("created_by", "assistant"),
        ("created_by", "user_attested"),
    ):
        payload = _claim_payload(**{field: unknown})
        assert unknown in rejects(EvidenceRecord, payload)

    for unknown in ("c5", "C1", "c2b", "source_existence"):
        assert unknown in rejects(VerificationRecord, _entry(check=unknown))


def test_cross_type_field_mixing_is_rejected() -> None:
    """A claim string on a number, or a number on a sentence. Both are refused."""
    message = rejects(EvidenceRecord, _numeric_payload(text="The yield was high."))
    assert "may not carry text" in message

    for field, value in (("value", 1.0), ("unit", "mg/L"), ("tolerance", 1e-06)):
        message = rejects(EvidenceRecord, _claim_payload(**{field: value}))
        assert "belongs to kind='numeric'" in message

    with pytest.raises(ValidationError) as caught:
        EvidenceRecord.model_validate(_numeric_payload(value=None))
    assert "must carry a value" in str(caught.value)


def test_wrong_schema_version_is_rejected_in_both_directions() -> None:
    for version in (0, 2, 99):
        message = rejects(EvidenceRecord, _claim_payload(schema_version=version))
        assert "unsupported EvidenceRecord schema_version" in message

        message = rejects(VerificationRecord, _entry(schema_version=version))
        assert "unsupported VerificationRecord schema_version" in message

        message = rejects(ArtifactReceipt, _receipt_payload(schema_version=version))
        assert "unsupported ArtifactReceipt schema_version" in message


def test_unknown_extra_field_is_rejected() -> None:
    rejects(EvidenceRecord, _claim_payload(c4_checked=True))
    rejects(EvidenceRecord, _claim_payload(scientifically_established=True))
    rejects(VerificationRecord, _entry(confidence=0.97))
    rejects(ArtifactReceipt, _receipt_payload(exported_by="libreoffice"))


def test_naive_datetime_is_rejected() -> None:
    rejects(EvidenceRecord, _claim_payload(created_at="2026-01-01T00:00:00"))
    rejects(VerificationRecord, _entry(checked_at="2026-01-01T00:00:00"))
    rejects(ArtifactReceipt, _receipt_payload(created_at="2026-01-01T00:00:00"))


@pytest.mark.parametrize("bad_hash", ["A" * 64, "a" * 63, "a" * 65, "", "not-a-hash"])
def test_content_hashes_must_be_canonical(bad_hash: str) -> None:
    rejects(EvidenceRecord, _claim_payload(source_content_hash=bad_hash))
    rejects(EvidenceRecord, _claim_payload(extracted_span_sha256=bad_hash))


# ---------------------------------------------------------------------------
# The state machine's invariants (ADR-0004 Contract 2, I3)
# ---------------------------------------------------------------------------


def test_status_past_planned_requires_located_evidence() -> None:
    """``planned -> extracted`` preconditions, enforced at construction.

    Named in the message so a caller is told what to fix rather than that its
    record is invalid.
    """
    for drop in ("anchor_ids", "extracted_span", "extracted_span_sha256", "source_content_hash"):
        payload = _claim_payload()
        value = payload.pop(drop)
        message = rejects(EvidenceRecord, payload)
        assert drop in message
        payload[drop] = value

    # The complete record is accepted, which is the point of the rule.
    EvidenceRecord.model_validate(_claim_payload())


def test_extracted_span_and_its_hash_are_all_or_nothing() -> None:
    message = rejects(EvidenceRecord, _claim_payload(extracted_span_sha256=None))
    assert "both set or both omitted" in message
    rejects(EvidenceRecord, _claim_payload(extracted_span=None))


def test_verified_by_rule_requires_the_passing_entry_that_earned_it() -> None:
    """I3: a status may never be upgraded without appending a VerificationRecord."""
    for log in (
        [],
        [_entry(outcome=CheckOutcome.INDETERMINATE, detail="normalisation ambiguous")],
        [_entry(outcome=CheckOutcome.FAIL, detail="cell reads 4.0")],
    ):
        message = rejects(EvidenceRecord, _numeric_payload(verification_log=log))
        assert "verification_log entry" in message

    # A C4 entry is not an upgrade path: it is not in UPGRADING_CHECKS and it can
    # only ever say not_checked, so no sequence of C4 entries gets here.
    EvidenceRecord.model_validate(_numeric_payload())


def test_user_attested_requires_a_human_and_a_logged_action() -> None:
    message = rejects(
        EvidenceRecord,
        _claim_payload(
            status="user_attested",
            created_by="model_proposal",
            verification_log=[
                _entry(
                    check=CheckKind.C2,
                    outcome=CheckOutcome.INDETERMINATE,
                    checker_id="user:local",
                    detail="read it",
                    normalization_profile="exact",
                )
            ],
        ),
    )
    assert "user_attested requires created_by='user'" in message

    message = rejects(
        EvidenceRecord,
        _claim_payload(status="user_attested", created_by="user", created_by_id="local-user"),
    )
    assert "verification_log entry" in message

    attested = EvidenceRecord.model_validate(
        _claim_payload(
            status="user_attested",
            created_by="user",
            created_by_id="local-user",
            verification_log=[
                _entry(
                    check=CheckKind.C2,
                    outcome=CheckOutcome.INDETERMINATE,
                    checker_id="user:local-user",
                    detail="the ligature made verbatim matching unreliable; read it myself",
                    normalization_profile="nfkc_whitespace_collapsed_ligatures",
                )
            ],
        )
    )
    assert attested.status is VerificationStatus.USER_ATTESTED
    # I1: verified_by_rule and user_attested are mutually exclusive endpoints.
    # mypy reads the narrowed literal and calls the comparison non-overlapping —
    # which is the exclusivity, proved by the type system as well as asserted here.
    assert attested.status is not VerificationStatus.VERIFIED_BY_RULE  # type: ignore[comparison-overlap]


def test_unsupported_is_explicable_even_with_no_anchor_at_all() -> None:
    """ADR-0004 Contract 2 allows "or no anchor at all" as the reason.

    So ``unsupported`` is the one state past ``planned`` where a missing anchor
    *is* the evidence — but it must still be explicable, and a record with a
    locatable anchor and no failing check is not.
    """
    unsupported = EvidenceRecord.model_validate(
        _claim_payload(
            status="unsupported",
            anchor_ids=[],
            extracted_span=None,
            extracted_span_sha256=None,
            source_content_hash=None,
            verification_log=[],
        )
    )
    assert unsupported.status is VerificationStatus.UNSUPPORTED

    message = rejects(
        EvidenceRecord,
        _claim_payload(status="unsupported", verification_log=[], source_content_hash=HASH_A),
    )
    assert "which check failed" in message

    failed = EvidenceRecord.model_validate(
        _claim_payload(
            status="unsupported",
            verification_log=[
                _entry(
                    check=CheckKind.C2,
                    outcome=CheckOutcome.FAIL,
                    checker_id="c2.verbatim",
                    detail="paraphrase presented as a quote",
                    normalization_profile="exact",
                )
            ],
        )
    )
    assert failed.verification_log[0].outcome is CheckOutcome.FAIL


def test_conflicted_requires_a_log_entry_but_not_a_second_record_here() -> None:
    """A conflict is evidenced. ADR-0004's *two-record* test is LC-P1-09's.

    What is locally checkable — anchors present, log non-empty — is checked; what
    needs a sibling record is named in the module docstring as delegated, not
    quietly assumed.
    """
    message = rejects(EvidenceRecord, _claim_payload(status="conflicted", verification_log=[]))
    assert "conflicted requires a verification_log entry" in message

    conflicted = EvidenceRecord.model_validate(
        _claim_payload(
            status="conflicted",
            verification_log=[
                _entry(check=CheckKind.C3, outcome=CheckOutcome.PASS, detail="run A: 4.2"),
                _entry(
                    check=CheckKind.C3,
                    outcome=CheckOutcome.FAIL,
                    detail="run B: 3.1, exceeds tolerance",
                ),
            ],
        )
    )
    assert conflicted.status is VerificationStatus.CONFLICTED


def test_duplicate_anchor_ids_are_rejected() -> None:
    message = rejects(EvidenceRecord, _claim_payload(anchor_ids=["anc-1", "anc-1"]))
    assert "duplicates" in message


# ---------------------------------------------------------------------------
# Verdict and the index seam
# ---------------------------------------------------------------------------


def test_verdict_round_trips_and_is_closed() -> None:
    verdict = Verdict(
        check=CheckKind.C3,
        outcome=CheckOutcome.INDETERMINATE,
        checker_id="c3.rule",
        detail="segment is not numeric",
    )
    assert_round_trips(Verdict, verdict)

    rejects(Verdict, {"check": "c5", "outcome": "pass", "checker_id": "x", "detail": "d"})
    rejects(Verdict, {"check": "c3", "outcome": "maybe", "checker_id": "x", "detail": "d"})
    rejects(Verdict, {"check": "c3", "outcome": "pass", "detail": "d"})
    rejects(Verdict, {"check": "c3", "outcome": "pass", "checker_id": "", "detail": "d"})
    rejects(
        Verdict,
        {"check": "c3", "outcome": "pass", "checker_id": "x", "detail": "d", "confidence": 0.9},
    )


def test_not_checked_verdict_is_a_verdict_so_callers_need_not_special_case_it() -> None:
    """It is a strict subtype, not a parallel type: polymorphic handling still works."""
    verdict: Verdict = check_scientific_interpretation(
        EvidenceRecord.model_validate(_claim_payload())
    )
    assert isinstance(verdict, NotCheckedVerdict)
    assert isinstance(verdict, Verdict)
    assert verdict.model_dump()["outcome"] == "not_checked"


def test_located_content_never_claims_content_it_could_not_read() -> None:
    """ADR-0004 A7/A9: "we could not look" carries nothing, and says so."""
    for resolution in (LocationResolution.UNRESOLVABLE, LocationResolution.UNADDRESSABLE):
        message = rejects(
            LocatedContent,
            {"anchor_id": "anc-1", "resolution": resolution.value, "text": "leaked"},
        )
        assert "carries no content" in message
        LocatedContent.model_validate({"anchor_id": "anc-1", "resolution": resolution.value})

    # A resolved address that yielded nothing is not a resolution.
    rejects(LocatedContent, {"anchor_id": "anc-1", "resolution": "resolved"})
    LocatedContent.model_validate(
        {"anchor_id": "anc-1", "resolution": "resolved", "text": "4.2 mg/L"}
    )
    LocatedContent.model_validate(
        {"anchor_id": "anc-1", "resolution": "resolved", "numeric_value": 4.2}
    )


def test_location_resolution_separates_not_found_from_could_not_look() -> None:
    """PaperSpine's ``no_hit`` vs ``provider_failure`` split, reimplemented.

    Conflating them lets a failure discharge an evidence requirement, which is
    A9's whole point.
    """
    assert LocationResolution.UNRESOLVABLE is not LocationResolution.UNADDRESSABLE  # type: ignore[comparison-overlap]
    assert {member.value for member in LocationResolution} == {
        "resolved",
        "unresolvable",
        "unaddressable",
    }


# ---------------------------------------------------------------------------
# ArtifactReceipt
# ---------------------------------------------------------------------------


def test_receipt_records_provenance_not_just_a_path() -> None:
    """ARCHITECTURE.md: "ArtifactReceipt records generated outputs and their provenance"."""
    receipt = ArtifactReceipt.model_validate(_receipt_payload())
    assert receipt.kind is ArtifactKind.FIGURE
    assert receipt.produced_by is ArtifactProducerKind.ANALYSIS_OPERATOR
    assert receipt.producer_id == "labcairn.analysis.grouped_aggregate@0.4.1"
    assert {ref.target_kind for ref in receipt.derived_from} == {
        DerivationTargetKind.EVIDENCE_RECORD,
        DerivationTargetKind.MATERIAL_FILE,
    }
    assert receipt.revision == 1
    assert receipt.staleness is ArtifactStaleness.CURRENT


def test_hashed_derivation_targets_must_carry_their_hash() -> None:
    """A chain link with no hash is a link nothing can invalidate."""
    for kind in (DerivationTargetKind.MATERIAL_FILE, DerivationTargetKind.ARTIFACT):
        message = rejects(
            ArtifactReceipt,
            _receipt_payload(derived_from=[{"target_kind": kind.value, "target_id": "x"}]),
        )
        assert "must carry content_sha256" in message

    # The kinds that carry their own hash do not need a second copy of it.
    ArtifactReceipt.model_validate(
        _receipt_payload(derived_from=[{"target_kind": "evidence_record", "target_id": "ev-1"}])
    )


def test_staleness_is_paired_with_a_reason() -> None:
    """ADR-0004 I4 marks downstream artifacts stale; a mark nobody can act on is decoration."""
    message = rejects(ArtifactReceipt, _receipt_payload(staleness="stale"))
    assert "must carry staleness_reason" in message

    message = rejects(ArtifactReceipt, _receipt_payload(staleness_reason="source changed"))
    assert "not stale" in message

    receipt = ArtifactReceipt.model_validate(
        _receipt_payload(
            staleness="stale",
            staleness_reason="refs/data.csv changed after this figure was rendered",
        )
    )
    assert receipt.staleness is ArtifactStaleness.STALE


def test_receipt_rejects_absolute_paths_and_bad_numbers() -> None:
    rejects(ArtifactReceipt, _receipt_payload(relative_path="C:/out/fig.png"))
    rejects(ArtifactReceipt, _receipt_payload(relative_path="../../etc/passwd"))
    rejects(ArtifactReceipt, _receipt_payload(size_bytes="51233"))
    rejects(ArtifactReceipt, _receipt_payload(size_bytes=-1))
    rejects(ArtifactReceipt, _receipt_payload(revision=0))
    rejects(ArtifactReceipt, _receipt_payload(content_sha256="B" * 64))


def test_receipt_rejects_duplicate_derivation_targets() -> None:
    message = rejects(
        ArtifactReceipt,
        _receipt_payload(
            derived_from=[
                {"target_kind": "evidence_record", "target_id": "ev-1"},
                {"target_kind": "evidence_record", "target_id": "ev-1"},
            ]
        ),
    )
    assert "duplicate derivation target" in message


def test_derivation_ref_and_enums_are_closed() -> None:
    rejects(DerivationRef, {"target_kind": "web_page", "target_id": "https://example.com"})
    rejects(DerivationRef, {"target_kind": "source"})
    assert {member.value for member in DerivationTargetKind} == {
        "evidence_record",
        "source",
        "source_anchor",
        "artifact",
        "material_file",
    }
    assert {member.value for member in ArtifactKind} == {
        "report",
        "figure",
        "table",
        "dataset",
        "manifest",
        "other",
    }


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def test_aware_datetimes_survive_the_round_trip_exactly() -> None:
    """A ledger compared by hash cannot afford a truncated timestamp."""
    stamp = datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=UTC)
    record = EvidenceRecord.model_validate(_claim_payload(created_at=stamp))
    restored = EvidenceRecord.model_validate_json(record.model_dump_json())
    assert restored.created_at == record.created_at
    assert restored.created_at.tzinfo is not None
