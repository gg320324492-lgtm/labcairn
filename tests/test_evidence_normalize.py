"""Text normalisation: the transform, and the measurement of what it cost.

The tests here are written against **measured facts about Unicode**, not against
the implementation, because the implementation could be reimplemented to agree
with itself and still be wrong about ligatures. Two of these assertions fail if
someone implements the third profile as "apply NFKC again" -- which is the
obvious thing to write from its name, and which would be a profile that differs
from its documentation by nothing.

``alters_letters`` is ADR-0004 A4's signal, so it gets the most attention: the
whole failure mode of a comparison is being *too sure*, and a signal that
reports every normalisation as lossy would make ``indeterminate`` the answer to
every comparison and teach users to read past it.
"""

from __future__ import annotations

import unicodedata

import pytest

from labcairn.evidence.normalize import LIGATURES, normalize
from labcairn.evidence.states import NormalizationProfile as Profile

pytestmark = pytest.mark.unit

#: Spelled by codepoint rather than pasted. A NO-BREAK SPACE inside a string
#: literal is invisible to a reader and trips RUF001, and these cases are about
#: exactly that character.
NBSP = chr(0x00A0)

EXACT = Profile.EXACT
COLLAPSED = Profile.NFKC_WHITESPACE_COLLAPSED
LIGATURES_PROFILE = Profile.NFKC_WHITESPACE_COLLAPSED_LIGATURES


# --------------------------------------------------------------------------- #
# EXACT
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        "plain prose",
        "  leading and trailing  ",
        "double  spaces\nand\ta tab",
        "",
        "\ufb01t œuvre \u04b4\u0437\u044b",
    ],
)
def test_exact_returns_the_text_untouched(text: str) -> None:
    """``EXACT`` is byte-for-byte after **extraction** normalisation.

    Not "the raw bytes of the file": LC-P1-08's PDF adapter already trims what a
    page boundary introduces, and re-deriving that here would be a second,
    divergent implementation of a decision already made.
    """
    result = normalize(text, EXACT)
    assert result.text == text
    assert result.alters_letters is False


# --------------------------------------------------------------------------- #
# the measured facts about NFKC
# --------------------------------------------------------------------------- #


def test_nfkc_already_folds_the_latin_ligatures() -> None:
    """The reason the third profile is not redundant.

    Written down because it is the fact most likely to be assumed away: the
    obvious implementation of ``..._LIGATURES`` is "NFKC, and ligatures", and
    the ligature half is already in NFKC. A profile that adds nothing is a
    profile that lies on its log entry.
    """
    assert unicodedata.normalize("NFKC", "\ufb01") == "fi"
    result = normalize("\ufb01t", COLLAPSED)
    assert result.text == "fit"
    assert result.alters_letters is True, "folding a ligature changes letter identity"


def test_nfkc_already_folds_nonbreaking_space() -> None:
    assert unicodedata.normalize("NFKC", " ") == " "


def test_nfkc_can_change_a_character_that_is_not_whitespace() -> None:
    """So ``alters_letters`` must compare against the *input*.

    Compared against the intermediate instead, this would read as free: the
    intermediate already had ``1`` in it. A circled digit folding to ``1`` is
    exactly the "letter identity may not be preserved" case ADR-0004 A4 names.
    """
    result = normalize("\u2460", COLLAPSED)
    assert result.text == "1"
    assert result.alters_letters is True


# --------------------------------------------------------------------------- #
# whitespace
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("double  spaces", "double spaces"),
        ("tabs\tand\nnewlines", "tabs and newlines"),
        ("   padded   ", "padded"),
        (f"a{NBSP}b", "a b"),
        ("mixed \t \n spacing", "mixed spacing"),
    ],
)
def test_whitespace_is_collapsed_and_the_ends_are_trimmed(raw: str, expected: str) -> None:
    assert normalize(raw, COLLAPSED).text == expected


@pytest.mark.parametrize(
    "raw", ["double  spaces", "  padded  ", f"a{NBSP}b", "tabs\tand\nnewlines"]
)
def test_collapsing_whitespace_does_not_alter_letters(raw: str) -> None:
    """Layout is not uncertainty.

    This is the distinction the whole module turns on. Extraction introduces
    spacing differences that no reader would call a difference; a C2 comparison
    that reported those as ``indeterminate`` would be reporting almost every
    real match as undecidable.
    """
    assert normalize(raw, COLLAPSED).alters_letters is False


def test_nonbreaking_space_is_a_layout_change_not_a_letter_change() -> None:
    """NFKC turns NBSP into an ordinary space, and ``str.split()`` treats both
    as whitespace -- which is what makes the letter comparison come out even."""
    result = normalize(f"a{NBSP}b", COLLAPSED)
    assert result.text == "a b"
    assert result.alters_letters is False


# --------------------------------------------------------------------------- #
# the ligature table
# --------------------------------------------------------------------------- #


def test_the_table_holds_only_characters_nfkc_does_not_already_fold() -> None:
    """Every entry must be doing work.

    A character NFKC already decomposes belongs in no table: adding it would
    make the profile's name describe work it does not do, on a log entry whose
    whole purpose is to say what the comparison did.
    """
    redundant = [
        f"U+{ord(char):04X}" for char in LIGATURES if unicodedata.normalize("NFKC", char) != char
    ]
    assert redundant == [], "these are already folded by NFKC"


def _letter_named(script: str, case: str, component: str) -> str:
    """The one character Unicode calls ``<SCRIPT> <CASE> LETTER <component>``."""
    wanted = f"{script} {case} LETTER {component}"
    for code in range(0x41, 0x530):
        if unicodedata.name(chr(code), "") == wanted:
            return chr(code)
    raise AssertionError(f"no character is named {wanted!r}")


def test_every_cyrillic_expansion_is_the_letters_its_unicode_name_gives() -> None:
    """The table, derived from Unicode rather than read off it.

    The table maps characters that *look* like Latin, so an eye-written
    expansion is invisible in review and silently corrupts a quotation. This
    test takes each Cyrillic character's own Unicode name apart and looks up the
    letters the remaining words name; nothing about the answer is written by
    hand.

    It is what caught the previous version, whose **three Cyrillic rows were all
    wrong**: ``TSE`` had been read as C rather than \u0426, and ``EN GHE`` as \u0415\u041d
    rather than \u041d\u0413. Both are exactly the mistake RUF001 exists to catch, made in
    the one place the rule has to be suppressed -- which is why suppressing the
    rule is not a licence to stop checking.
    """
    checked = 0
    for character, expansion in LIGATURES.items():
        name = unicodedata.name(character)
        if not name.startswith("CYRILLIC"):
            continue
        case = "CAPITAL" if "CAPITAL" in name else "SMALL"
        components = name.split("LIGATURE", 1)[1].split()
        derived = "".join(_letter_named("CYRILLIC", case, part) for part in components)
        assert derived == expansion, (
            f"U+{ord(character):04X} {name}: Unicode names {components} = {derived!r}, "
            f"the table says {expansion!r}"
        )
        checked += 1
    assert checked == 6, f"expected 6 Cyrillic rows, checked {checked}"


def test_the_latin_row_is_the_name_minus_the_word_ligature() -> None:
    """Œ has no ``LATIN LETTER OE`` to decompose into, so the derivation is
    its own Unicode name with the word ``LIGATURE`` removed."""
    for code, expansion in ((0x0152, "OE"), (0x0153, "oe")):
        character = chr(code)
        tail = unicodedata.name(character).replace(" LIGATURE", "").split()[-1]
        assert tail.lower() == expansion.lower(), unicodedata.name(character)
        assert LIGATURES[character] == expansion


def test_the_table_is_the_size_it_claims() -> None:
    assert len(LIGATURES) == 8


def test_a_letter_with_a_diacritic_is_not_a_ligature() -> None:
    """U+04D6 looked like a member and is not.

    It is named ``CYRILLIC CAPITAL LETTER IE WITH BREVE``, which reads like a
    ligature of two letters, and an earlier draft of the table expanded it to
    two on the strength of the name. Its canonical decomposition is one letter
    plus a combining breve -- it is a single precomposed letter, and expanding
    it invents a letter that was never in the text.

    A table that folded it would return a fabricated quotation from a real one,
    which is the whole failure this module exists to avoid.
    """
    letter = chr(0x04D6)
    assert unicodedata.name(letter) == "CYRILLIC CAPITAL LETTER IE WITH BREVE"
    decomposition = unicodedata.decomposition(letter)
    assert decomposition, "it has a canonical decomposition, so it is a letter not a ligature"
    assert letter not in LIGATURES
    assert normalize(letter, LIGATURES_PROFILE).text == letter


def test_an_ornamental_ligature_is_not_folded() -> None:
    """Folding a decoration into letters is inventing text.

    U+1F670 ``SCRIPT LIGATURE ET ORNAMENT`` carries the letters ``ET`` in its
    name and is not the word ET. A profile that expanded every character whose
    name mentions a ligature would turn a flourish in a title into text, and the
    result would be quoted back as something the author wrote.

    Named by codepoint rather than pasted, because the neighbouring block at
    U+1D6F0 is ``MATHEMATICAL ITALIC CAPITAL OMICRON`` -- an earlier version of
    this test pasted that one and passed for a reason that had nothing to do
    with ligatures.
    """
    ornament = chr(0x1F670)
    assert unicodedata.name(ornament) == "SCRIPT LIGATURE ET ORNAMENT"
    assert normalize(ornament, LIGATURES_PROFILE).text == ornament


def test_a_honorific_encoded_as_one_character_is_not_folded() -> None:
    """Out of scope by decision, and the decision is recorded.

    23 of the 45 ligatures NFKC leaves alone are Arabic, and they are not letter
    ligatures at all: U+FD40 is ``ARABIC LIGATURE RAHIMAHU ALLAAH``, an entire
    phrase in a single codepoint. Expanding one is transliterating a religious
    convention, which is not this project's call to make, and a wrong expansion
    is a fabricated quotation.

    U+FDF2 would have been the intuitive example here and is the wrong one: it is
    a *canonical* form, so NFKC already decomposes it and the table is never
    consulted. A test written against it would pass for the wrong reason.
    """
    ligature = chr(0xFD40)
    assert unicodedata.name(ligature) == "ARABIC LIGATURE RAHIMAHU ALLAAH"
    assert normalize(ligature, LIGATURES_PROFILE).text == ligature


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("œuvre", "oeuvre"),
        ("Œuvre", "OEuvre"),
        ("\u04a4\u0437\u044b", "\u041d\u0413\u0437\u044b"),
        ("\u04d4", "\u0410\u0415"),
    ],
)
def test_the_ligature_profile_folds_what_its_table_holds(raw: str, expected: str) -> None:
    result = normalize(raw, LIGATURES_PROFILE)
    assert result.text == expected
    assert result.alters_letters is True


def test_the_third_profile_differs_from_the_second_only_on_its_table() -> None:
    """Otherwise it is the second profile wearing a different name."""
    samples = ["plain prose", "\ufb01t", "œuvre", "\u04b4\u0437\u044b", "  spaced  ", "\u2460"]
    for raw in samples:
        second = normalize(raw, COLLAPSED).text
        third = normalize(raw, LIGATURES_PROFILE).text
        if raw in ("œuvre", "\u04b4\u0437\u044b"):
            assert third != second, raw
        else:
            assert third == second, raw


# --------------------------------------------------------------------------- #
# alters_letters is per call, not per profile
# --------------------------------------------------------------------------- #


def test_a_lossy_profile_that_changed_nothing_reports_no_change() -> None:
    """The reason the signal is per call.

    Reporting by profile would make ``indeterminate`` the answer to every
    comparison made under a lossy profile -- and ``indeterminate`` is a verdict a
    reader has to act on. A string the third profile leaves alone was compared
    exactly as strictly as one under ``EXACT``.
    """
    result = normalize("nothing here needs folding", LIGATURES_PROFILE)
    assert result.text == "nothing here needs folding"
    assert result.alters_letters is False


def test_the_same_text_can_go_both_ways_under_one_profile() -> None:
    """One profile, two honest answers."""
    clean = normalize("plain", LIGATURES_PROFILE)
    folded = normalize("œuvre", LIGATURES_PROFILE)
    assert clean.alters_letters is False
    assert folded.alters_letters is True


def test_alteration_is_reported_even_when_the_result_is_identical() -> None:
    """A character can fold to itself and still be a change of identity.

    Not reachable through this table -- every entry has a distinct expansion --
    but the comparison is structural, so it holds if the table ever gains one.
    """
    assert normalize("", LIGATURES_PROFILE).alters_letters is False
    assert normalize("   ", LIGATURES_PROFILE).alters_letters is False


# --------------------------------------------------------------------------- #
# normalisation is a copy
# --------------------------------------------------------------------------- #


def test_normalising_never_mutates_its_input() -> None:
    """A precondition, not a nicety.

    C2's job is to say "the stored text is X and the quote is Y". A stored text
    quietly rewritten to agree with Y cannot answer that, and Python strings
    being immutable is the only reason this holds.
    """
    original = "  spaced   text  "
    kept = original
    normalize(original, LIGATURES_PROFILE)
    assert original is kept
    assert original == "  spaced   text  "


def test_the_result_is_immutable() -> None:
    """A verdict's inputs must not be editable after it is recorded."""
    result = normalize("x", EXACT)
    with pytest.raises(Exception):  # noqa: B017 - dataclass raises FrozenInstanceError
        result.text = "y"  # type: ignore[misc]
