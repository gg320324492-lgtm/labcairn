"""The retrieval ground truth validates itself before anything is built on it.

A ground-truth set is an input to T03, and an input that is quietly wrong makes
every later test wrong in the same direction while looking green. So the checks
here do not need a retriever: they confirm that each expected phrase really does
appear on the pages this file claims, by reading the fixture PDFs.

That is the line. Reading the paper to confirm a human annotation is what makes
the annotation ground truth; running a retriever and recording what it returned
would make it a snapshot of the thing it is supposed to test. Nothing in this
file imports ``labcairn.evidence.index``, and the test below asserts that the
computed column is recomputed here from the specification rather than read back
from the index.

**Two columns, two different kinds of knowledge.** ``phrase_on_pages`` is
observed -- a person confirmed the phrase is there. ``expect`` is computed --
every page where the query's terms occur, which is what a trigram index answers.
Both are checked here, by different means, and the file records where they
diverge rather than reconciling it away.
"""

from __future__ import annotations

import json
import pathlib
import unicodedata
from typing import Any

import pdfplumber
import pytest

PAPERS = pathlib.Path(__file__).parent / "fixtures" / "papers"
GROUND_TRUTH = pathlib.Path(__file__).parent / "fixtures" / "retrieval" / "ground_truth.json"


def _load() -> dict[str, Any]:
    # ``json.loads`` is typed ``Any``. Widening it explicitly is the honest
    # annotation: the structure is validated by the tests below rather than by a
    # cast, and a cast would claim a guarantee nothing checks.
    parsed: dict[str, Any] = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return parsed


def _entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = _load()["queries"]
    return entries


def _collapsed_pages(source: str) -> dict[int, str]:
    """Every page's text as the index holds it: NFKC, whitespace collapsed.

    This is T02's profile, recomputed here rather than imported, because the
    point of this file is to check the annotations against something other than
    the code under test.
    """
    with pdfplumber.open(PAPERS / source) as document:
        return {
            number: " ".join(unicodedata.normalize("NFKC", page.extract_text() or "").split())
            for number, page in enumerate(document.pages, 1)
        }


def _stripped_pages(source: str) -> dict[int, str]:
    """Every page's text with all whitespace removed.

    The observed column uses this because ADR-0008 measured space glyphs at
    0.03%-1.08% across this corpus: the papers space words by positioning, so
    body text arrives as 'Dijkstra'salgorithmis' and a phrase read with spaces
    would not be found.
    """
    return {number: text.replace(" ", "") for number, text in _collapsed_pages(source).items()}


@pytest.fixture(scope="module")
def collapsed() -> dict[str, dict[int, str]]:
    return {path.name: _collapsed_pages(path.name) for path in sorted(PAPERS.glob("*.pdf"))}


@pytest.fixture(scope="module")
def stripped() -> dict[str, dict[int, str]]:
    return {path.name: _stripped_pages(path.name) for path in sorted(PAPERS.glob("*.pdf"))}


def test_the_set_is_not_empty_and_covers_every_fixture(
    collapsed: dict[str, dict[int, str]],
) -> None:
    """A ground truth that skips a fixture would let that paper go unretrievable
    without anything failing."""
    declared = set(_load()["papers"])
    assert declared == set(collapsed), sorted(declared.symmetric_difference(collapsed))
    touched = {e["expect"][0]["source"] for e in _entries() if e["expect"]}
    assert touched == declared, f"no positive query for {sorted(declared - touched)}"


def test_the_observed_pages_really_do_contain_the_phrase(
    stripped: dict[str, dict[int, str]],
) -> None:
    """``phrase_on_pages`` -- the human judgement, checked against the papers.

    Every page named must contain the phrase, and no page outside the list may.
    This is the column a computation could never stand in for.
    """
    for entry in _entries():
        if not entry["expect"]:
            continue
        source = entry["expect"][0]["source"]
        phrase = entry["expect_text_contains"].replace(" ", "")
        found = sorted(number for number, page in stripped[source].items() if phrase in page)
        assert found == sorted(entry["phrase_on_pages"]), (
            f"{entry['id']}: '{entry['expect_text_contains']}' is on pages {found}, "
            f"the file claims {entry['phrase_on_pages']}"
        )


def test_the_computed_pages_are_what_the_stated_semantics_gives(
    collapsed: dict[str, dict[int, str]],
) -> None:
    """``expect`` -- recomputed here from the specification, not read back.

    "Every page where all of the query's terms occur, case-insensitively, in the
    whitespace-collapsed text" is a complete description of what the index
    answers. Recomputing it independently is what stops this file from becoming
    a snapshot of the implementation: if the index's semantics and this
    description ever drift, the two disagree and this fails.
    """
    for entry in _entries():
        if not entry["expect"]:
            continue
        expected = entry["expect"][0]
        terms = [term for term in entry["query"].split() if term]
        computed = sorted(
            number
            for number, page in collapsed[expected["source"]].items()
            if all(term.lower() in page.lower() for term in terms)
        )
        assert computed == sorted(expected["pages"]), (
            f"{entry['id']}: the stated semantics gives {computed}, "
            f"the file claims {expected['pages']}"
        )


def test_where_the_index_misses_a_phrase_it_is_named_not_reconciled(
    stripped: dict[str, dict[int, str]],
) -> None:
    """The divergence between the two columns, asserted to be *declared*.

    A retrieval index that cannot find every page a person can is a measured
    false-negative rate, and the honest record of one names the pages. An entry
    whose index answer is narrower than the observed answer without saying so
    would be a ground truth quietly lying about what it checks.
    """
    for entry in _entries():
        if not entry["expect"]:
            continue
        expected = set(entry["expect"][0]["pages"])
        observed = set(entry["phrase_on_pages"])
        missing = observed - expected
        if not missing:
            assert "index_misses_phrase_pages" not in entry, (
                f"{entry['id']} declares index misses it does not have"
            )
            continue
        assert entry.get("index_misses_phrase_pages") == sorted(missing), (
            f"{entry['id']}: the index misses {sorted(missing)} and the file "
            f"declares {entry.get('index_misses_phrase_pages')}"
        )


def test_a_wider_index_answer_is_allowed_and_needs_no_excuse() -> None:
    """Where the index returns more than the phrase pages, that is correct.

    The query's words really are on those pages, so a lexical index is entitled
    to return them; requiring it to find only phrase pages would be requiring a
    phrase matcher, which is C2's job and not retrieval's.
    """
    wider = 0
    for entry in _entries():
        if not entry["expect"]:
            continue
        if set(entry["expect"][0]["pages"]) > set(entry["phrase_on_pages"]):
            wider += 1
    assert wider >= 1, "no query exercises the wider case, so nothing pins that it is allowed"


def test_the_expectation_pages_are_in_range(
    collapsed: dict[str, dict[int, str]],
) -> None:
    for entry in _entries():
        for expected in entry["expect"]:
            total = len(collapsed[expected["source"]])
            for number in expected["pages"] + entry["phrase_on_pages"]:
                assert 1 <= number <= total, f"{entry['id']}: page {number} of {total}"


def test_a_negative_query_holds_nothing_at_all(
    collapsed: dict[str, dict[int, str]],
) -> None:
    """The other half. A negative that occurs somewhere is not a negative.

    This is the check that keeps ADR-0004 A6 and A12 honest: a term central to
    the project ('retrieval augmented generation') is genuinely absent, so a
    retriever returning its nearest passage is demonstrably wrong rather than
    merely unmatched by luck.
    """
    for entry in _entries():
        if entry["expect"]:
            continue
        needle = "".join(entry["query"].split()).lower()
        hits = [
            f"{source} p{number}"
            for source, text in collapsed.items()
            for number, page in text.items()
            if needle in page.replace(" ", "").lower()
        ]
        assert hits == [], f"{entry['id']} is meant to find nothing but appears at {hits}"


def test_ids_are_unique_and_queries_are_not_blank() -> None:
    entries = _entries()
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids)), "a duplicate id makes a failure unattributable"
    for entry in entries:
        assert entry["query"].strip(), entry["id"]
        assert entry["why"].strip(), f"{entry['id']} has no recorded reason"


def test_the_empty_query_is_recorded_rather_than_forgotten() -> None:
    """FTS5 rejects an empty MATCH string, so this case cannot live in the
    entries above. It is in ``frozen`` so the retrieval API has to answer it,
    and this test fails if someone deletes the note to tidy the file."""
    frozen = _load()["frozen"]
    assert frozen["empty_string_query"]["expect"] == []
    assert frozen["empty_string_query"]["why"].strip()


def test_the_two_kinds_of_answer_are_both_documented() -> None:
    """A reader must be able to tell which column is judgement and which is
    computation, without reading the diff that introduced it."""
    text = GROUND_TRUTH.read_text(encoding="utf-8")
    assert "phrase_on_pages" in text
    assert "TWO KINDS OF ANSWER" in text
    for entry in _entries():
        if entry["expect"]:
            assert "phrase_on_pages" in entry, f"{entry['id']} has no observed column"


def test_the_scope_limitation_is_still_written_down() -> None:
    """Three single-column papers cannot speak for a corpus that has none.

    The set's usefulness is bounded by its corpus, and a reader deciding whether
    a retrieval result is trustworthy needs that bound stated in the file rather
    than remembered.
    """
    declared = _load()["papers"]
    assert len(declared) == 3
    text = GROUND_TRUTH.read_text(encoding="utf-8")
    assert "no two-column material" in text
