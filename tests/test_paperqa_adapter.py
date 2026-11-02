"""The competitor adapter's honesty, watched.

**What this file watches.** ``tests/evaluation/paperqa_adapter.py`` is
LC-P2-18's translation layer — corpus files in, paper-qa answers out —
and the brief calls that layer *the comparison's main honesty risk*:
an adapter that paraphrases the question toward an answer, cleans up the
output before scoring, or retries what the product side does not get has
already decided the result. So the rule brief §5 clause 5 states — *no
task logic, and scoring depends on nothing but the answer keys and the
artifacts* — is carried here as refusals with witnesses, in the same
shape as the LC-P2-14 preparation file beside it.

**Nothing here imports paper-qa.** The adapter is dependency-injected:
a case is driven by any ``(question, document) -> answer`` callable, so
every witness runs offline in the repository's own environment, and a
CI machine that has never installed the competitor can still watch the
adapter's rules.

**Each witness is mutated against.** The mutation table is in
``docs/acceptance/LC-P2-18-preparation.md``: every witness below was
checked by breaking the property it names and watching it go red.
"""

from __future__ import annotations

from typing import Any

import pytest
from analysis_fixtures import CORPUS_DIR, SPREADSHEET_SOURCES, load_expected
from evaluation.corpus import CORPUS_FIXTURES
from evaluation.paperqa_adapter import (
    STAT_ORDER,
    build_artifact,
    question_for,
    render_fixture,
    run_case,
    score_artifact,
)

pytestmark = pytest.mark.unit


def _numeric_key() -> dict[str, Any]:
    """A key with both a selection and a grouped section, for the witnesses."""
    return load_expected("units.csv")


def test_the_xlsx_rendering_is_the_csv_it_was_built_from() -> None:
    """The open XLSX choice adds no formatting: the text *is* the source CSV.

    An XLSX is a binary blob and paper-qa is text-first, so the adapter
    renders it — and the brief requires that genuinely open choice to be
    the dumbest one that parses. The witness is byte equality with the
    CSV the spreadsheet was built from, which is what makes "no
    formatting of its own" a measurement rather than a promise.
    """
    for spreadsheet, source in SPREADSHEET_SOURCES.items():
        rendered = render_fixture(spreadsheet)
        source_text = (CORPUS_DIR / source).read_text(encoding="utf-8")
        assert rendered == source_text, (
            f"{spreadsheet} did not render as {source}; the adapter's "
            "rendering added formatting of its own"
        )


def test_every_corpus_fixture_renders_as_a_document() -> None:
    """All eleven fixtures, not just the two spreadsheets, reach the system.

    The corpus is the brief's §1 list — nine CSV and two XLSX — and a
    fixture the adapter cannot render is a case the competitor never
    gets to run.
    """
    assert len(CORPUS_FIXTURES) == 11
    for fixture in CORPUS_FIXTURES:
        rendered = render_fixture(fixture)
        assert rendered.strip(), f"{fixture} rendered empty"


def test_the_question_depends_on_the_keys_structure_and_not_its_values() -> None:
    """Change every expected value, and the question does not move a byte.

    This is the witness for "no question rewritten toward an answer": the
    template reads selection names, row addresses, column names and group
    keys, and never a statistic. Mutating the statistics by +1000 leaves
    the question identical; mutating a selection's name changes it. The
    second half is what proves the test can see a change at all.
    """
    key = _numeric_key()
    original = question_for(key)

    moved_values = {**key, "selections": [], "grouped": key.get("grouped")}
    moved_values["selections"] = [
        {
            **selection,
            "expect": {
                **selection["expect"],
                "statistics": {
                    name: (None if value is None else value + 1000.0)
                    for name, value in (selection["expect"].get("statistics") or {}).items()
                },
            },
        }
        for selection in key["selections"]
    ]
    assert question_for(moved_values) == original, (
        "the question changed when only the expected values changed, so it "
        "is reading the answer rather than the task"
    )

    renamed = {
        **key,
        "selections": [
            {**key["selections"][0], "name": "a different selection"},
            *key["selections"][1:],
        ],
    }
    assert question_for(renamed) != original, (
        "renaming a selection did not change the question, so this witness "
        "cannot see the structure at all"
    )


def test_the_question_names_every_selection_and_group_but_no_statistic_value() -> None:
    """What the question may say, and what it may not.

    It names each selection's own words and each group key — the task's
    address. It does not contain any expected statistic's value.
    """
    key = _numeric_key()
    question = question_for(key)
    for selection in key["selections"]:
        assert selection["name"] in question
    for group in key["grouped"]["groups"]:
        assert str(group["key"]) in question
    values = [
        float(selection["expect"]["statistics"][name])
        for selection in key["selections"]
        for name in STAT_ORDER
        if name in (selection["expect"].get("statistics") or {})
        and selection["expect"]["statistics"][name] is not None
    ]
    assert values, "units.csv carries no statistics, so this witness measures nothing"
    for value in values:
        assert str(value) not in question, f"the question contains the expected value {value!r}"


def test_refused_selections_are_asked_but_not_scored() -> None:
    """A refusal is a semantic judgement, and the adapter does not invent it.

    ``units.csv`` asks for a column the key refuses; the question lists
    it like any other (the competitor gets the same task), while the
    score counts only the statistics the key attaches to ``ok``
    selections and ``ok`` groups.
    """
    key = _numeric_key()
    refused = [
        selection for selection in key["selections"] if selection["expect"]["outcome"] == "refused"
    ]
    assert refused, (
        "units.csv no longer carries a refused selection, so this witness measures nothing"
    )
    assert refused[0]["name"] in question_for(key)

    expected_values = sum(
        sum(
            1
            for value in (selection["expect"].get("statistics") or {}).values()
            if value is not None
        )
        for selection in key["selections"]
        if selection["expect"]["outcome"] == "ok"
    ) + sum(
        sum(1 for value in (group.get("statistics") or {}).values() if value is not None)
        for group in key["grouped"]["groups"]
        if group.get("outcome") == "ok"
    )
    score = score_artifact(build_artifact("units.csv", "q", ""), key)
    assert score.expected == expected_values


def test_the_artifact_carries_the_answer_untouched() -> None:
    """Whitespace, casing and line breaks are the system's, not the adapter's."""
    answer = "  The sum is 52.0.\nMin = 1\n\n"
    artifact = run_case(lambda question, document: answer, "basic.csv", load_expected("basic.csv"))
    assert artifact["status"] == "answered"
    assert artifact["answer"] == answer, "the adapter repaired the system's output"


def test_a_failing_system_is_called_exactly_once_and_the_case_is_recorded() -> None:
    """No retry the product side does not get; the failure is a reported fact."""
    calls: list[tuple[str, str]] = []

    def refusing_system(question: str, document: str) -> str:
        calls.append((question, document))
        raise RuntimeError("provider boundary")

    artifact = run_case(refusing_system, "basic.csv", load_expected("basic.csv"))
    assert len(calls) == 1, "the adapter retried a failing system"
    assert artifact["status"] == "failed"
    assert artifact["answer"] is None
    assert artifact["failure"]["stage"] == "system"
    assert "RuntimeError: provider boundary" in artifact["failure"]["error"]
    assert artifact["question"], "the failed case does not record what it asked"


def test_scoring_reads_only_the_answer_and_the_key() -> None:
    """Two artifacts that differ in everything but the answer score the same.

    One carries a different system name, a different question, contexts
    full of the *correct* numbers and arbitrary metadata; the other is
    bare. Brief §5 clause 5 says scoring depends on the answer keys and
    the artifacts — and on the artifact, only the answer. The correct
    numbers in the failed artifact's contexts are the mutation: a scorer
    that read them would score it higher.
    """
    key = load_expected("basic.csv")
    wrong_answer = "the sum cannot be determined from this document"
    correct_numbers = "sum 55, min 1, max 10, mean 5.5, median 5.5"
    bare = build_artifact("basic.csv", question_for(key), wrong_answer)
    decorated = {
        **build_artifact("basic.csv", "a different question", wrong_answer),
        "system": "paper-qa",
        "contexts": [correct_numbers],
        "note": "arbitrary metadata",
    }
    assert score_artifact(bare, key).matched == 0
    assert score_artifact(bare, key) == score_artifact(decorated, key), (
        "the contexts changed the score, so scoring is reading something "
        "other than the answer and the key"
    )

    answered = {**decorated, "answer": correct_numbers}
    assert score_artifact(answered, key).matched > 0, (
        "correct numbers in the answer did not raise the score, so this "
        "witness cannot see what the scorer reads"
    )


def test_the_score_is_recall_over_the_answers_numbers_and_extra_numbers_are_not_penalised() -> None:
    """The scoring direction is recorded: it can only help a competitor.

    Extra numbers — values cited from the table, row labels — do not lower
    the score, because any stricter rule would be a rule about prose.
    """
    key = load_expected("single.csv")
    statistics = key["selections"][0]["expect"]["statistics"]
    correct = ", ".join(
        str(statistics[name])
        for name in STAT_ORDER
        if name in statistics and statistics[name] is not None
    )
    with_extras = f"row 2, row 3, columns 4 and 5, a year 2024; {correct}"
    score = score_artifact(build_artifact("single.csv", "q", with_extras), key)
    assert score.exact, f"extra numbers lowered the score: {score}"
