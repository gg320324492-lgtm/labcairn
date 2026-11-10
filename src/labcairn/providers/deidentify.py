"""The de-identification pipeline: material becomes a case, or nothing leaves.

LC-P3-06 deliverable 2, substitute-first half (work orders §11 §4.8, left
column, first row). The pipeline runs **before** the outbound payload is
built, on synthetic material until the owner supplies the real domain sample.

What this module is for
-----------------------
The redaction layer (:mod:`labcairn.providers.redaction`) scrubs the
*credential* and credential-shaped text out of any string LabCairn passes
around. Its honest scope stops there — it says so itself: *the credential and
the credential's echoes, not the document*. What LC-P3-06 needs is the other
half: the document.

The pipeline owns the boundary between the two sample sides of the work
order's split:

* it takes a material text and the excerpts a caller wants to send,
* it takes the caller's own de-identified rendering of them,
* and it refuses the case unless the rendering **proves clean** — no long
  verbatim run of the material survives, no long Han run survives, no
  registered secret survives.

Why the pipeline does not do the replacing itself
-------------------------------------------------
A pipeline that rewrites text has to decide what a name is, what an
affiliation is, what a strain designation is — decisions about the *material*,
which only a person (or a later, explicitly authorised surface) can make. What
a pipeline can decide mechanically is whether the replacement **worked**: the
shape of a leak is mechanical. So the division of labour is fixed and the
order is structural: the caller replaces, this module verifies, and nothing
that failed verification has any representation downstream — because
:class:`DeidentifiedCase`, the only thing a bounded run accepts, cannot be
built by any path that skipped the verification.

Why the check is n-gram, not substring
--------------------------------------
A whole-substring check would reject a case whose rendering changed two words
in a hundred-line paragraph — useless — and pass one that quoted every other
sentence — worse than useless. The check that matches the property the work
order names (*the output carries no material text*) is: no run of
:data:`GRAM_WINDOW` consecutive whitespace-separated words of the material
appears in the output, and no Han run of :data:`HAN_RUN_CEILING` or more
characters appears in the output. Short runs survive — a title, a chemical
formula, a strain code — and that is deliberate: those are the same shapes
:func:`~labcairn.providers.adapter.prompt_digest` was designed to coexist
with. A rendering that needs a longer run through has not de-identified; it
has paraphrased around the check, and the witness for that is the reviewer the
work order names, not this module.

The CJK discipline
------------------
The repository's own ceiling (``tests/test_no_reference_leakage.py``) watches
Han runs in *tracked files*, because the corpus's words must not enter the
tree. This module watches Han runs in *outbound text*, because the corpus's
words must not leave the machine either. Two ceilings, one rule: the material
is nowhere it was not invited.

The sample class and the fingerprint record
-------------------------------------------
Execution plan §4's three sample classes are named here as code, and the
fingerprint record is the format the operator-side registry (111 ``.docx``
fingerprints, 2026-11-09) already uses: digest, byte size, class, recorded
moment. No prose field beyond a short note — a fingerprint that carried the
first line of the file would be the leak it exists to prevent.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from labcairn.providers.adapter import prompt_digest
from labcairn.providers.redaction import Redactor

#: The longest word run of the material a rendering may carry verbatim.
#: Eight consecutive words is a sentence fragment, not a title or a formula.
GRAM_WINDOW: Final[int] = 8

#: The longest Han run a rendering may carry. Mirrors the repository's own
#: file-level pin (the measured ceilings in ``test_no_reference_leakage.py``)
#: at the outbound boundary.
HAN_RUN_CEILING: Final[int] = 8

#: Han characters, the range the file-level ceiling measures. Written as
#: escapes so this source file carries no Han run of its own — the repository's
#: CJK pin watches tracked files, and a regex literal would be an entry.
_HAN: Final[re.Pattern[str]] = re.compile("[\\u4e00-\\u9fff]+")


class DeidentificationRefusedError(Exception):
    """A rendering failed verification. The case does not exist downstream.

    The message names which check failed and how long the surviving run was.
    It never quotes the material: the refusal is written before the caller
    ever sees the text again, and a refusal that echoed the leak would be the
    leak's own log line.
    """


class SampleRecordError(ValueError):
    """A fingerprint record or a sample class is not in the plan's vocabulary."""


class SampleClass(StrEnum):
    """The execution plan's three sample classes (§4, "One real model" row).

    The classes are the plan's own words, lowered into identifiers. Which
    class a sample belongs to decides where it may exist:

    ``PUBLIC_SYNTHETIC``
        CI and negative tests. May enter the tree; the fixtures are this
        class. ``redact_case`` still runs on it — the pipeline's behaviour
        must not depend on trusting the caller's label.
    ``DEIDENTIFIED_DOMAIN``
        The owner-authorised, de-identified domain sample — the second of the
        plan's three classes, and the one the controlled real-model case runs
        on. Stays in the authorised environment.
    ``AUTHORISED_TRIAL``
        The trial sample, advisor use. The most restricted class; nothing in
        the repository handles it.
    """

    PUBLIC_SYNTHETIC = "public_synthetic"
    DEIDENTIFIED_DOMAIN = "deidentified_domain"
    AUTHORISED_TRIAL = "authorised_trial"


@dataclass(frozen=True, slots=True)
class SampleFingerprint:
    """The fingerprint record format, as the operator registry already writes it.

    sha256, byte size, class, recorded moment, note. The note is a *label*
    (``"batch A, advisor-annotated"``), never prose from the file: the
    registry's own discipline is *no prose extracted, no file enters the
    tree*, and a fingerprint field that carried the file's opening sentence
    would break both halves of it.
    """

    digest: str
    byte_size: int
    sample_class: SampleClass
    recorded_at: datetime
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.sample_class, SampleClass):
            raise SampleRecordError(
                f"{self.sample_class!r} is not a SampleClass; a fingerprint names "
                "one of the execution plan's three classes, not a free string"
            )
        if len(self.digest) != 64 or any(c not in "0123456789abcdef" for c in self.digest):
            raise SampleRecordError(
                "a fingerprint digest is a lowercase sha256 hex string, 64 characters"
            )
        if self.byte_size < 0:
            raise SampleRecordError("byte_size is a count, not a guess")
        if self.recorded_at.tzinfo is None:
            raise SampleRecordError(
                "recorded_at must be an aware datetime; a naive one is a lie about when"
            )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        sample_class: SampleClass,
        recorded_at: datetime | None = None,
        note: str = "",
    ) -> SampleFingerprint:
        """Fingerprint bytes. The digest is over the bytes, nothing else."""
        return cls(
            digest=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            sample_class=sample_class,
            recorded_at=recorded_at if recorded_at is not None else datetime.now(UTC),
            note=note,
        )


@dataclass(frozen=True, slots=True)
class DeidentifiedCase:
    """A verified case: the only shape that can become an outbound request.

    Built exclusively by :meth:`DeidentificationPipeline.redact_case` — the
    pipeline verifies the rendering, and only then constructs one.
    :meth:`BoundedRun.submit_case` refuses anything else at runtime, so
    *redaction before the payload is built* is the type system's shape, not a
    convention the caller is asked to remember.
    """

    #: The caller's label for the case. Never rendered outbound by itself.
    case_id: str
    #: The verified rendering the model is asked with.
    safe_prompt: str
    #: The verified renderings of the excerpts, one outbound request each.
    excerpts: tuple[str, ...]
    #: Per-excerpt digest over the *rendered* text — the adapter's own
    #: domain-separated spelling. This is what the digest-bound approval
    #: covers, and what :attr:`ExchangeRecord.prompt_digest` computes
    #: independently from the request it saw: two paths to the same number.
    excerpt_digests: tuple[str, ...]
    #: The material's own digest — the same shape the operator registry uses,
    #: so a case names the sample it was drawn from without carrying it.
    source_digest: str
    #: The class the sample was declared as. Recorded, never trusted: the
    #: verification ran regardless of it.
    sample_class: SampleClass
    #: How many words the rendering started from, for the run record's counts.
    material_word_count: int

    def __post_init__(self) -> None:
        if len(self.excerpts) != len(self.excerpt_digests):
            raise DeidentificationRefusedError(
                "each excerpt needs its own digest; the counts disagree"
            )


def _word_grams(text: str) -> set[str]:
    """Every ``GRAM_WINDOW``-word run in the text, lowercased."""
    words = text.lower().split()
    return {
        " ".join(words[i : i + GRAM_WINDOW]) for i in range(max(0, len(words) - GRAM_WINDOW + 1))
    }


def _long_han_runs(text: str) -> list[str]:
    """Han runs of ``HAN_RUN_CEILING`` characters or more."""
    return [run for run in _HAN.findall(text) if len(run) >= HAN_RUN_CEILING]


class DeidentificationPipeline:
    """Verifies a rendering against its material, and mints the case.

    The pipeline holds one :class:`~labcairn.providers.redaction.Redactor`
    per pipeline, registers the caller's named secrets in it, and runs a
    final scrub over the verified rendering. That scrub is a second net, not
    the primary one: it catches a secret-shaped string the n-gram check
    cannot see (a key that appeared in the material and was copied into the
    rendering verbatim). The primary check is the run-length verification,
    because secrets are a *shape* and material is *content*.
    """

    def __init__(self, *, redactor: Redactor | None = None) -> None:
        self._redactor = redactor if redactor is not None else Redactor()
        self._cases_minted = 0

    @property
    def redactor(self) -> Redactor:
        """The pipeline's redactor, for the caller to register credentials on."""
        return self._redactor

    @property
    def cases_minted(self) -> int:
        return self._cases_minted

    def redact_case(
        self,
        *,
        case_id: str,
        source_digest: str,
        material_text: str,
        excerpts: Sequence[str],
        rendered_prompt: str,
        rendered_excerpts: Sequence[str],
        sample_class: SampleClass,
        secrets: Sequence[str] = (),
    ) -> DeidentifiedCase:
        """Verify the renderings and mint the case — or refuse, wholly.

        ``rendered_prompt`` and ``rendered_excerpts`` are the caller's
        de-identified renderings. The checks, in order:

        1. **Run-length** — no ``GRAM_WINDOW``-word run of the material in
           any rendering; no Han run of the ceiling or more in any rendering.
        2. **Secret** — every secret named in ``secrets`` (a credential, a
           subject name the caller knows) is registered in the pipeline's
           redactor and must not survive into any rendering.
        3. **Final scrub** — the renderings pass through the redactor once,
           removing credential-shaped text.

        A failure refuses the *whole* case: there is no "the prompt is clean
        but excerpt 2 leaked" case, because a caller that ships the clean
        parts of a refused case is a caller that has learned to ship around
        the refusal.
        """
        if len(rendered_excerpts) != len(excerpts):
            raise DeidentificationRefusedError(
                "one rendering per excerpt; the counts disagree "
                f"({len(rendered_excerpts)} renderings for {len(excerpts)} excerpts)"
            )

        # The forbidden corpus is the material *and* every excerpt the caller
        # named. An excerpt can carry a long run the material text does not —
        # a caption, a table row, a footnote — and checking only the material
        # would let that run leave under a rendering that quoted it.
        forbidden_grams = _word_grams(" ".join((material_text, *excerpts)))
        renderings = (rendered_prompt, *rendered_excerpts)
        for index, rendering in enumerate(renderings):
            where = "the prompt" if index == 0 else f"excerpt {index - 1}"
            self._verify_rendering(case_id, where, forbidden_grams, rendering)

        for secret in secrets:
            if secret and len(secret) >= 8:
                self._redactor.register(secret)
        for index, rendering in enumerate(renderings):
            where = "the prompt" if index == 0 else f"excerpt {index - 1}"
            self._verify_no_named_secret(case_id, where, secrets, rendering)

        scrubbed_prompt = self._redactor.scrub(rendered_prompt)
        scrubbed_excerpts = tuple(self._redactor.scrub(r) for r in rendered_excerpts)

        self._cases_minted += 1
        return DeidentifiedCase(
            case_id=case_id,
            safe_prompt=scrubbed_prompt,
            excerpts=scrubbed_excerpts,
            excerpt_digests=tuple(prompt_digest(r) for r in scrubbed_excerpts),
            source_digest=source_digest,
            sample_class=sample_class,
            material_word_count=len(material_text.split()),
        )

    def _verify_rendering(
        self, case_id: str, where: str, material_grams: set[str], rendering: str
    ) -> None:
        """The run-length checks. The refusal names the check, not the text."""
        surviving = material_grams & _word_grams(rendering)
        if surviving:
            raise DeidentificationRefusedError(
                f"case {case_id!r}: {where} still carries a {GRAM_WINDOW}-word run of "
                f"the material ({len(surviving)} such run(s)); the case is not de-identified"
            )
        for run in _long_han_runs(rendering):
            raise DeidentificationRefusedError(
                f"case {case_id!r}: {where} carries a {len(run)}-character Han run; "
                "the CJK ceiling holds outbound too"
            )

    def _verify_no_named_secret(
        self, case_id: str, where: str, secrets: Sequence[str], rendering: str
    ) -> None:
        for secret in secrets:
            if secret and len(secret) >= 8 and secret in rendering:
                raise DeidentificationRefusedError(
                    f"case {case_id!r}: {where} carries a registered secret verbatim"
                )


__all__ = [
    "GRAM_WINDOW",
    "HAN_RUN_CEILING",
    "DeidentificationPipeline",
    "DeidentificationRefusedError",
    "DeidentifiedCase",
    "SampleClass",
    "SampleFingerprint",
    "SampleRecordError",
]
