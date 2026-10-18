"""Text normalisation for C2, and the measurement that says how far it went.

ADR-0004 fixes the *vocabulary* of three profiles so "how lenient was this
comparison?" has an answer that is comparable across runs. This module is the
transform behind that vocabulary, and it carries one thing the enum deliberately
does not: whether a given call actually changed anything a reader would call a
difference in the **letters**.

That distinction is the whole of ADR-0004 A4. Collapsing the whitespace an
extractor introduced is not an uncertainty -- it is the difference between the
same text read twice. Folding a ligature changes letter *identity*, which is
precisely the "scanned-and-OCR'd or badly-encoded material" case the third
profile exists for and the case A4 says must answer ``indeterminate`` rather
than ``pass``. :attr:`Normalized.alters_letters` is how C2 tells those apart,
and it is per call rather than per profile: a lossy profile that happened to
leave this particular string alone changed nothing, and reporting it as lossy
would make ``indeterminate`` the answer to every comparison and teach users to
ignore it.

**Normalisation never mutates stored text.** What comes back is an index-side
copy; ``source_texts`` keeps the bytes the adapter produced. That is not a
convention but a precondition: C2's job is to say "the stored text is X and the
quote is Y", and a stored text quietly rewritten to agree with Y cannot answer
that.

**Two measurements, because the profile names are not self-describing.**

NFKC already folds the Latin ligatures -- ``ﬁ`` (U+FB01) becomes ``fi`` --
along with NBSP and ``①``. So the third profile is *not* redundant with the
second only in part, and implementing it as "apply NFKC again" would have
quietly produced a profile that differs from its documentation by nothing at
all. Scanning every codepoint whose Unicode name contains ``LIGATURE`` and
asking which ones NFKC leaves alone found 45, and 45 is not the size of the
table below.

Of those 45, only 6 are folded: Latin ``Œ``/``œ`` and six Cyrillic. The 23
Arabic are mostly **honorific phrases encoded as single characters** -- U+FD40 is
``ARABIC LIGATURE RAHIMAHU ALLAAH``, an entire phrase, not a ligature of two
letters -- and transliterating those is a claim about a text tradition this
project has no standing to make. The 3 Hebrew are Yiddish typography, and the
remainder are ornaments and special scripts. Folding an ornament -- U+1F670
``SCRIPT LIGATURE ET ORNAMENT`` carries the letters ``ET`` in its name and is
not the word ET -- is not normalisation, it is inventing text that was not
there.

One character that looked like a member is not. U+04D6 and U+04D7 are named
``CYRILLIC LETTER IE WITH BREVE``, and an earlier draft of this table included
them on the strength of the name. They are not ligatures: their canonical
decomposition is one letter plus a combining breve, so an "expansion" of them
to two letters invents a letter that was never there. They are out, and the
reason is recorded here because the name is the evidence that made them look
like members.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Final

from labcairn.evidence.states import NormalizationProfile

__all__ = ["LIGATURES", "Normalized", "normalize"]

#: The ligatures NFKC leaves alone, and that this project folds anyway.
#:
#: Measured by scanning every codepoint whose Unicode name contains
#: ``LIGATURE`` and asking which ones NFKC does not decompose -- 45 of them.
#: This table is the Latin and Cyrillic subset; the module docstring says why
#: the rest are not in it.
LIGATURES: Final[dict[str, str]] = {
    # Latin. NFKC leaves Œ/œ alone because they are letters in their own right
    # rather than compatibility forms, and French and German scholarly text is
    # full of them.
    "Œ": "OE",
    "œ": "oe",
    # Cyrillic. A Russian-language corpus is a normal thing for a research
    # workspace to hold.
    #
    # Written as \u escapes on purpose. These characters are confusable with
    # Latin ones by design, which is why RUF001 exists -- and a rule that has
    # to be suppressed here is a rule that is no longer checking anything, so
    # the escapes keep both the lint and the review honest. An earlier draft
    # used the literal characters and had **all three rows wrong**: TSE was
    # read as C rather than U+0426, and EN GHE as U+0415 U+041D rather than
    # U+041D U+0413. Those are the mistakes RUF001 exists to catch, made in
    # the one place the rule was turned off.
    #
    # Every expansion is the letters named in the character's own Unicode
    # name. The tests re-derive them from that name rather than reading them
    # from here, so an eye-written table fails instead of shipping.
    "\u04a4": "\u041d\u0413",
    "\u04a5": "\u043d\u0433",
    "\u04b4": "\u0422\u0426",
    "\u04b5": "\u0442\u0446",
    "\u04d4": "\u0410\u0415",
    "\u04d5": "\u0430\u0435",
}


@dataclass(frozen=True)
class Normalized:
    """One normalisation, and whether it changed the letters.

    ``text`` is the copy to index or compare with. ``profile`` is what was
    declared, and is what a C2 log entry must record: ADR-0004 R2's objection is
    to a comparison whose aggressiveness is invisible, because a false negative
    teaches users to turn the check off.

    ``alters_letters`` is the A4 signal. ``True`` means the comparison can only
    have succeeded by matching text that is not character-for-character the
    stored text, which ADR-0004 A4 answers ``indeterminate`` rather than
    ``pass``.
    """

    text: str
    profile: NormalizationProfile
    alters_letters: bool


def normalize(text: str, profile: NormalizationProfile) -> Normalized:
    """Apply *profile* to *text* and report what it cost.

    ``EXACT`` means byte-for-byte after **extraction** normalisation -- the
    adapter's own, already applied by the time text reaches here. It does not
    mean "the raw bytes of the file": LC-P1-08's PDF adapter already trims what
    a page boundary introduces, and re-deriving that here would be a second,
    divergent implementation of a decision that was already made.
    """
    if profile is NormalizationProfile.EXACT:
        return Normalized(text=text, profile=profile, alters_letters=False)

    collapsed = _collapse(text)
    if profile is NormalizationProfile.NFKC_WHITESPACE_COLLAPSED:
        folded = collapsed
    else:
        folded = "".join(LIGATURES.get(character, character) for character in collapsed)

    return Normalized(
        text=folded,
        profile=profile,
        # Compared against the *input*, not against the intermediate: NFKC can
        # change a non-whitespace character on its own (① becomes 1), and a
        # comparison against the intermediate would report that as free.
        alters_letters=_letters(folded) != _letters(text),
    )


def _collapse(text: str) -> str:
    """NFKC, runs of whitespace to one space, ends trimmed."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _letters(text: str) -> str:
    """The text with every whitespace character removed.

    ``str.split()`` splits on Unicode whitespace, which includes NBSP and the
    ideographic space. That is what makes this the right comparison: NFKC turns
    NBSP into an ordinary space, and that is a layout change, so it must not
    count as a change of letters.
    """
    return "".join(text.split())
