"""The de-identification pipeline, watched — LC-P3-06 substitute-first half.

**What is under test.** Work orders §11 §4.8, left column, row 1 and row 3:
*the de-identification pipeline and its witnesses, on synthetic material*
and *the sample-class definition and the fingerprint record format*. Every
byte in this file is authored here; no advisor material, no real route, no
credential, no socket.

The order the work order names is structural: **redaction runs BEFORE the
outbound payload is built**. The pipeline is therefore the only path to the
shape an outbound request accepts (:class:`DeidentifiedCase`); the refusal
witnesses prove that a rendering with a surviving material run, a long Han
run, or a registered secret never becomes a case at all. The pipeline's
output carries no material text — that is asserted on the case itself, not
on a log line after the fact.

**What is deliberately not claimed.** This pipeline verifies a *rendering*;
it does not rewrite text, and it does not decide what a name is. That
decision is a person's (§4.8's real-material half), and the run record says
so. The witnesses here watch the mechanical half: what a leak looks like.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from labcairn.providers.adapter import prompt_digest
from labcairn.providers.deidentify import (
    GRAM_WINDOW,
    DeidentificationPipeline,
    DeidentificationRefusedError,
    DeidentifiedCase,
    SampleClass,
    SampleFingerprint,
    SampleRecordError,
)
from labcairn.providers.redaction import PLACEHOLDER

pytestmark = pytest.mark.unit

#: A fixed instant, so the fingerprint record is byte-stable.
MOMENT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)

#: Synthetic material. Long enough to hold several eight-word runs; the
#: sentence is invented here, not drawn from any manuscript.
MATERIAL = (
    "The green algae inhibition assay was repeated three times under identical "
    "lighting conditions and the results disagreed with the earlier published "
    "curve at every measured concentration point without exception or explanation."
)

#: A de-identified rendering, changed in every clause. The same work a person
#: would do before a real case is authorised.
CLEAN_RENDERING = (
    "Assay S-1 was run on three occasions; luminance held fixed. Its trace "
    "diverges from a prior reference trace across the dilution series. "
    "No mechanism is offered here."
)

#: A real eight-word run of the material, used as the counter-mutation's
#: payload: the witness must redden when the n-gram check is removed.
LEAKED_RUN = "the results disagreed with the earlier published curve"

SECRET = "sk-ant-synthetic-key-00000000"


def _pipeline() -> DeidentificationPipeline:
    return DeidentificationPipeline()


def _case(
    pipeline: DeidentificationPipeline,
    *,
    rendered: str = CLEAN_RENDERING,
    rendered_excerpts: Sequence[str] = ("Disagrees with a reference trace.",),
    secrets: Sequence[str] = (),
) -> DeidentifiedCase:
    """The one construction path to a case, shared so the order is one thing."""
    return pipeline.redact_case(
        case_id="synthetic-1",
        source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
        material_text=MATERIAL,
        excerpts=("the assay disagreed with the curve",),
        rendered_prompt=rendered,
        rendered_excerpts=rendered_excerpts,
        sample_class=SampleClass.PUBLIC_SYNTHETIC,
        secrets=secrets,
    )


# --- 1. the pipeline's output carries no material text --------------------


def test_a_clean_rendering_becomes_a_case_with_no_material_run() -> None:
    """The case retains a rendering, not the material it was drawn from."""
    pipeline = _pipeline()
    case = _case(pipeline)

    assert MATERIAL not in case.safe_prompt
    assert MATERIAL not in " ".join(case.excerpts)
    # No eight-word run of the material survives in any outbound field.
    words = MATERIAL.lower().split()
    grams = {" ".join(words[i : i + GRAM_WINDOW]) for i in range(len(words) - GRAM_WINDOW + 1)}
    for field in (case.safe_prompt, *case.excerpts):
        assert all(gram not in field.lower() for gram in grams)
    assert pipeline.cases_minted == 1


def test_each_excerpt_carries_its_own_digest_over_the_rendered_text() -> None:
    """Q3's per-excerpt digest binding, at the case level.

    The digest is the adapter's own domain-separated spelling of the
    *rendered* excerpt, so the approval binds what leaves and the exchange
    record computes the same number from what it saw: two paths, one value.
    """
    case = _case(_pipeline())

    assert len(case.excerpt_digests) == len(case.excerpts)
    for rendered, digest in zip(case.excerpts, case.excerpt_digests, strict=True):
        assert digest == prompt_digest(rendered)
        assert len(digest) == 64


def test_the_cjk_ceiling_holds_outbound_too() -> None:
    """A long Han run in a rendering is refused; a short one is not prose.

    The repository's own ceiling watches tracked files; this one watches
    outbound text. The synthetic run here is twelve identical characters —
    enough to be the shape of a quoted paragraph, not a name or a formula.
    """
    pipeline = _pipeline()
    # Twelve consecutive Han characters, built from code points so this test
    # file itself carries no Han run for the repository's CJK pin to measure.
    han_run = "".join(chr(0x6D4B + offset) for offset in range(12))
    assert len(han_run) == 12
    rendering = f"{CLEAN_RENDERING} {han_run}"

    with pytest.raises(DeidentificationRefusedError) as raised:
        _case(pipeline, rendered=rendering)

    assert "Han run" in str(raised.value)
    assert pipeline.cases_minted == 0


def test_the_final_scrub_catches_a_credential_shaped_copy() -> None:
    """The second net: a key the n-gram check cannot see.

    The rendering is otherwise clean; it copies one credential-shaped string.
    The redactor's shape pass removes it, and the case carries the placeholder
    instead of the secret — the pipeline's output has no secret either.
    """
    case = _case(_pipeline(), rendered=f"{CLEAN_RENDERING} {SECRET}")

    assert SECRET not in case.safe_prompt
    assert PLACEHOLDER in case.safe_prompt


def test_a_named_secret_copied_verbatim_is_refused() -> None:
    """A secret the caller knows by name is not a shape; it is a fact.

    Registering it makes the refusal exact rather than shape-dependent.
    """
    pipeline = _pipeline()
    named = "Operator-Alpha-Laboratory-Name"
    with pytest.raises(DeidentificationRefusedError) as raised:
        _case(
            pipeline,
            rendered=f"{CLEAN_RENDERING} {named}",
            secrets=(named,),
        )

    assert "registered secret" in str(raised.value)
    assert pipeline.cases_minted == 0


# --- 2. the refusals are mutation-checkable -------------------------------


def test_a_surviving_material_run_refuses_the_whole_case() -> None:
    """One eight-word run of the material in one excerpt is enough.

    The mutation that breaks this witness removes the n-gram check from
    ``_verify_rendering``; the case would then be minted with the material's
    own sentence in it, and this assertion reddens.
    """
    pipeline = _pipeline()
    # A full eight-word run copied from the material, not a paraphrase.
    assert any(
        " ".join(MATERIAL.lower().split()[i : i + GRAM_WINDOW]) == LEAKED_RUN
        for i in range(len(MATERIAL.split()) - GRAM_WINDOW + 1)
    )

    with pytest.raises(DeidentificationRefusedError) as raised:
        pipeline.redact_case(
            case_id="synthetic-leak",
            source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
            material_text=MATERIAL,
            excerpts=("one excerpt",),
            rendered_prompt=CLEAN_RENDERING,
            rendered_excerpts=(LEAKED_RUN,),
            sample_class=SampleClass.PUBLIC_SYNTHETIC,
        )

    assert f"{GRAM_WINDOW}-word run" in str(raised.value)
    assert pipeline.cases_minted == 0


def test_a_refusal_echoes_no_material() -> None:
    """A refusal that quotes the leak would be the leak's own log line."""
    pipeline = _pipeline()
    with pytest.raises(DeidentificationRefusedError) as raised:
        pipeline.redact_case(
            case_id="synthetic-leak",
            source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
            material_text=MATERIAL,
            excerpts=("one excerpt",),
            rendered_prompt=CLEAN_RENDERING,
            rendered_excerpts=(LEAKED_RUN,),
            sample_class=SampleClass.PUBLIC_SYNTHETIC,
        )

    assert LEAKED_RUN not in str(raised.value)
    assert MATERIAL not in str(raised.value)


def test_a_mismatched_excerpt_count_refuses_before_verification() -> None:
    """One rendering per excerpt. A shorter list is not a partial case."""
    pipeline = _pipeline()
    with pytest.raises(DeidentificationRefusedError, match="one rendering per excerpt"):
        pipeline.redact_case(
            case_id="synthetic-count",
            source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
            material_text=MATERIAL,
            excerpts=("one", "two"),
            rendered_prompt=CLEAN_RENDERING,
            rendered_excerpts=("only one",),
            sample_class=SampleClass.PUBLIC_SYNTHETIC,
        )
    assert pipeline.cases_minted == 0


# --- 3. the sample class and the fingerprint record ----------------------


def test_the_three_sample_classes_are_the_execution_plans_three() -> None:
    """The classes are named, not invented for this ticket."""
    assert {c.value for c in SampleClass} == {
        "public_synthetic",
        "deidentified_domain",
        "authorised_trial",
    }


def test_a_fingerprint_is_digest_size_class_and_moment_only() -> None:
    """The record format carries no prose from the file it fingerprints."""
    data = b"synthetic DOCX bytes; no advisor material"
    fp = SampleFingerprint.from_bytes(
        data,
        sample_class=SampleClass.PUBLIC_SYNTHETIC,
        recorded_at=MOMENT,
        note="synthetic fixture, not a sample",
    )

    assert fp.digest == hashlib.sha256(data).hexdigest()
    assert fp.byte_size == len(data)
    assert data.decode() not in repr(fp)
    # The fields are exactly the five the operator registry writes.
    assert set(fp.__slots__) == {
        "digest",
        "byte_size",
        "sample_class",
        "recorded_at",
        "note",
    }


def test_a_fingerprint_refuses_a_free_string_class_or_a_naive_moment() -> None:
    """A fingerprint that guessed its class or its moment is not a record."""
    data = b"more synthetic bytes"
    with pytest.raises(SampleRecordError, match="not a SampleClass"):
        SampleFingerprint(
            digest=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            sample_class="owner-paper",  # type: ignore[arg-type]
            recorded_at=MOMENT,
        )
    with pytest.raises(SampleRecordError, match="aware datetime"):
        SampleFingerprint(
            digest=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            sample_class=SampleClass.DEIDENTIFIED_DOMAIN,
            recorded_at=datetime(2026, 11, 10, 9, 0),  # noqa: DTZ001
        )


def test_a_fingerprint_refuses_a_digest_that_is_not_sha256_hex() -> None:
    """A short digest or one with uppercase is not the operator's record."""
    with pytest.raises(SampleRecordError, match="lowercase sha256"):
        SampleFingerprint(
            digest="abc123",
            byte_size=1,
            sample_class=SampleClass.AUTHORISED_TRIAL,
            recorded_at=MOMENT,
        )


def test_the_real_sample_class_is_named_but_not_promised() -> None:
    """The second class stays a named gap in the substitute-first half.

    ``DEIDENTIFIED_DOMAIN`` is in the vocabulary — the format must be able
    to record a real sample when the owner supplies one — but no case in
    this file is drawn from one. The rehearsal's cases all declare the
    synthetic class, and the run record reports that verbatim.
    """
    case = _case(_pipeline())
    assert case.sample_class is SampleClass.PUBLIC_SYNTHETIC
    assert case.material_word_count == len(MATERIAL.split())
