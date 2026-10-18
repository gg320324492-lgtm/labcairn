"""The retrieval ground truth validates itself before anything is built on it.

A ground-truth set is an input to T03, and an input that is quietly wrong makes
every later test wrong in the same direction while looking green. So the checks
here do not need a retriever: they confirm that each expected phrase really does
appear on the pages this file claims, by reading the fixture PDFs.

That is the line. Reading the paper to confirm a human annotation is what makes
the annotation ground truth; running a retriever and recording what it returned
would make it a snapshot of the thing it is supposed to test. Nothing in this
file imports ``labcairn.evidence``'s retrieval, and the test below asserts that
the phrases are found in ``source_texts``' *inputs* -- the PDFs -- rather than
in anything the index produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pdfplumber
import pytest

PAPERS = Path(__file__).parent / "fixtures" / "papers"
GROUND_TRUTH = Path(__file__).parent / "fixtures" / "retrieval" / "ground_truth.json"


def _load() -> dict[str, Any]:
    # ``json.loads`` is typed ``Any``. Widening it explicitly is the honest
    # annotation here: the structure is validated by the tests below rather than
    # by a cast, and a cast would claim a guarantee nothing checks.
    parsed: dict[str, Any] = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return parsed


def _entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = _load()["queries"]
    return entries


def _pages_of(source: str) -> dict[int, str]:
    """Every page's extracted text, whitespace removed.

    Whitespace-insensitive because ADR-0008 measured space glyphs at
    0.03%-1.08% across this corpus: the papers space words by positioning, so
    body text arrives as 'Dijkstra'salgorithmis'. Comparing with spaces would
    describe text no query could match, and the failure would look like a
    retriever bug rather than a property of the material.
    """
    with pdfplumber.open(PAPERS / source) as document:
        return {
            n: (page.extract_text() or "").replace(" ", "")
            for n, page in enumerate(document.pages, 1)
        }


@pytest.fixture(scope="module")
def pages() -> dict[str, dict[int, str]]:
    return {path.name: _pages_of(path.name) for path in sorted(PAPERS.glob("*.pdf"))}


def test_the_set_is_not_empty_and_covers_every_fixture(pages: dict[str, Any]) -> None:
    """A ground truth that skips a fixture would let that paper go unretrievable
    without anything failing."""
    declared = set(_load()["papers"])
    assert declared == set(pages), sorted(declared.symmetric_difference(pages))
    touched = {e["expect"][0]["source"] for e in _entries() if e["expect"]}
    assert touched == declared, f"no positive query for {sorted(declared - touched)}"


def test_every_expectation_phrase_really_is_on_the_pages_claimed(
    pages: dict[str, dict[int, str]],
) -> None:
    """The whole point of this file, checked against the papers."""
    for entry in _entries():
        if not entry["expect"]:
            continue
        expected = entry["expect"][0]
        text = pages[expected["source"]]
        found = [
            number
            for number, page in text.items()
            if entry["expect_text_contains"].replace(" ", "") in page
        ]
        claimed = expected["pages"]
        assert sorted(found) == sorted(claimed), (
            f"{entry['id']}: '{entry['expect_text_contains']}' is on pages {found}, "
            f"the file claims {claimed}"
        )


def test_the_expectation_pages_are_in_range(pages: dict[str, dict[int, str]]) -> None:
    for entry in _entries():
        for expected in entry["expect"]:
            total = len(pages[expected["source"]])
            for number in expected["pages"]:
                assert 1 <= number <= total, f"{entry['id']}: page {number} of {total}"


def test_a_positive_query_holds_nothing_that_could_also_be_a_negative(
    pages: dict[str, dict[int, str]],
) -> None:
    """No positive phrase may appear anywhere in the corpus.

    A phrase that occurs in two papers cannot discriminate between them, so a
    retriever returning the wrong one would still satisfy it -- and the set would
    claim a discrimination it does not have.
    """
    for entry in _entries():
        if not entry["expect"]:
            continue
        phrase = entry["expect_text_contains"].replace(" ", "")
        elsewhere = [
            f"{source} p{number}"
            for source, text in pages.items()
            for number, page in text.items()
            if phrase in page and source != entry["expect"][0]["source"]
        ]
        assert elsewhere == [], f"{entry['id']}: also occurs at {elsewhere}"


def test_a_negative_query_holds_nothing_at_all(pages: dict[str, dict[int, str]]) -> None:
    """The other half. A negative that occurs somewhere is not a negative.

    This is the check that keeps ADR-0004 A6 and A12 honest: a term central to
    the project ('retrieval augmented generation') is genuinely absent, so a
    retriever returning its nearest passage is demonstrably wrong rather than
    merely unmatched by luck.
    """
    for entry in _entries():
        if entry["expect"]:
            continue
        hits = [
            f"{source} p{number}"
            for source, text in pages.items()
            for number, page in text.items()
            if "".join(entry["query"].split()).lower() in page.lower()
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
