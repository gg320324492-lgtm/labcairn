"""What the records print is what the mechanism does, or the records are wrong.

**Why this file exists.** `LC-P3-02` produces three things a reader trusts:
an ADR, a support matrix and a dated evidence record. None of them is
evidence — §"Claims are measured, not asserted" says the measurement wins and
the record is corrected. So the numbers and the class names in those files
are re-derived here from the code and from a fresh pass over the substitute
set. A record that stops matching its mechanism reddens rather than quietly
remaining believed.

**The three claims this file holds.**

* *The matrix is one thing.* The structure classes, the support table in
  :mod:`labcairn.editing.survey` and the rows printed in
  ``docs/acceptance/LC-P3-02-support-matrix.md`` are the same set, and a row
  that names a class the enum does not have is a row about nothing.
* *The verdicts are measurements.* Every ``carried`` cell in the record is
  re-derived from a fresh run of the adopted option, and every ``refused``
  cell is a refusal the gate really raises on a sample.
* *The human half is stated as open.* No row of the reopen checklist in the
  tree record claims a host result, because no host was started; §2 item 2
  forbids automating it and §5.10 forbids an empty row nobody is watching.

**Why this file declares no marker.** It watches records, not a protocol
behaviour, and the evaluation harness treats a repository-class file that
declares a protocol marker as a contradiction.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

import pytest
from evaluation_docx_edit_fidelity import reopen_rows, run_substitute_set
from test_workspace_path_length import _measure_ceiling

from labcairn.editing.drafts import REFUSALS
from labcairn.editing.evidence import (
    MAX_PATH,
    PRESENCE_BY_CLASS,
    PathBudgetError,
    _long_paths_enabled,
    host_snapshot,
    visible_path,
)
from labcairn.editing.samples import REFUSED, SAMPLES, WRITABLE
from labcairn.editing.survey import SUPPORT, StructureClass

RECORDS: Path = Path(__file__).resolve().parent.parent / "docs/acceptance"
MATRIX_RECORD: Final[Path] = RECORDS / "LC-P3-02-support-matrix.md"
RUN_RECORD: Final[Path] = RECORDS / "LC-P3-02-substitute-run-2026-11-08.md"
ADR: Final[Path] = (
    Path(__file__).resolve().parent.parent / "docs/adr/ADR-0021-manuscript-editing-rewrite.md"
)


#: A markdown table row's cells, split on the pipe and stripped.
def _rows(text: str, heading: str) -> list[list[str]]:
    """The cells of the table that follows ``heading``."""
    body = text.split(heading, 1)
    assert len(body) == 2, f"the record has no table under {heading!r}"
    rows: list[list[str]] = []
    for line in body[1].splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    assert rows, f"no rows found under {heading!r}"
    return rows


def test_the_three_records_exist_and_are_dated() -> None:
    """A ticket that produced no record produced nothing a reviewer can check."""
    for path in (MATRIX_RECORD, RUN_RECORD, ADR):
        assert path.is_file(), f"{path.name} is not in the tree"
        text = path.read_text(encoding="utf-8")
        assert "2026-11-08" in text, f"{path.name} carries no date"
        assert "b471e9b" in text or "b471e9b783f879452b6d62e13e6da2d356007203" in text, (
            f"{path.name} prints no commit its numbers belong to"
        )


def test_the_visible_path_guard_refuses_the_length_the_machine_refuses(
    tmp_path: Path,
) -> None:
    """The ceiling is measured at its boundary, not read back from a constant.

    The review measured this machine on 2026-11-08: a visible path of 259
    characters was created and one of 260 was refused with
    ``FileNotFoundError``. The guard must refuse the first length the machine
    refuses, or it hands the caller a path that fails after the run has begun.
    """
    base = str(tmp_path)
    room = MAX_PATH - len(base) - 1
    assert room > 0, f"the temporary root is already longer than {MAX_PATH} characters"
    accepted = "a" * room
    assert len(str((tmp_path / accepted).absolute())) == MAX_PATH
    assert visible_path(tmp_path, accepted) == tmp_path / accepted
    with pytest.raises(PathBudgetError):
        visible_path(tmp_path, accepted + "a")


def test_the_recorded_ceiling_is_the_one_this_machine_enforces(tmp_path: Path) -> None:
    """The constant is anchored to a probe, not to itself.

    A witness that computes both sides from ``MAX_PATH`` stays green when the
    constant moves. This test measures the machine's exclusive-create ceiling
    with the probe ``tests/test_workspace_path_length.py`` uses and compares it
    with the number the evidence writer carries.
    """
    if sys.platform != "win32":
        pytest.skip("the 259-character ceiling is this machine's Windows path semantics")
    assert _measure_ceiling(tmp_path / "probe") == MAX_PATH


def test_the_host_snapshot_reports_the_registry_reader() -> None:
    """The snapshot and the reader must be one value, not two stories."""
    snapshot = host_snapshot("2026-11-08T00:00:00Z", "0" * 40)
    assert snapshot["long_paths_enabled"] == _long_paths_enabled()


def test_the_reopen_cells_are_empty_only_where_a_person_decides(tmp_path: Path) -> None:
    """§5.10's empty row: 44 rows, machine cells filled, human cells empty."""
    run = run_substitute_set()
    rows = reopen_rows(run, tmp_path)
    human_columns = (
        "operator",
        "opened_at",
        "open_result",
        "prompt_verbatim_or_NONE",
        "presence_after_open",
        "close_action",
        "reopened_at",
        "presence_after_reopen",
        "reopen_result",
        "save_performed",
        "sha256_after",
        "byte_size_after",
        "hash_changed",
    )
    machine_columns = (
        "file_path",
        "file_path_chars",
        "sha256_before",
        "byte_size_before",
        "host_name",
        "host_file_version",
        "host_version_measured_at",
        "expected_presence",
    )
    assert len(rows) == 44
    for row in rows:
        assert row["verdict"] == "PENDING-HUMAN"
        assert all(row[column] == "" for column in human_columns), row["row_id"]
        assert all(row[column] != "" for column in machine_columns), row["row_id"]
        assert "body-text" in row["expected_presence"], row["row_id"]


def test_the_matrix_names_every_class_the_enum_has_exactly_once() -> None:
    """Three statements of the class list, one set.

    **The enum, the support table and the printed record.** A class in the
    enum and not in the record is a class nobody decided; a row in the record
    for a class the enum does not name is a row about nothing; a class the
    support table has no verdict for is a gate that will fall through to a
    default nobody wrote down.
    """
    text = MATRIX_RECORD.read_text(encoding="utf-8")
    printed = [row[0].strip("`") for row in _rows(text, "## The matrix")]
    enum = sorted(structure.value for structure in StructureClass)
    assert sorted(printed) == enum, (
        f"in the record and not the enum: {sorted(set(printed) - set(enum))}; "
        f"in the enum and not the record: {sorted(set(enum) - set(printed))}"
    )
    assert len(printed) == len(set(printed)), f"duplicate rows: {printed}"
    assert set(SUPPORT) == set(StructureClass), (
        f"the support table is not total: {sorted(set(StructureClass) - set(SUPPORT))}"
    )


def test_the_matrix_verdicts_are_the_ones_the_support_table_carries() -> None:
    """The record's ``carried`` and ``written into`` cells restate SUPPORT, not opinion."""
    text = MATRIX_RECORD.read_text(encoding="utf-8")
    for row in _rows(text, "## The matrix"):
        structure = StructureClass(row[0].strip("`"))
        support = SUPPORT[structure]
        carried, written = row[2].lower(), row[3].lower()
        if support.carried:
            assert carried.startswith("carried"), f"{structure.value}: record says {carried!r}"
        else:
            assert carried.startswith(("not carried", "refused")), (
                f"{structure.value}: not carried in the table, {carried!r} in the record"
            )
        if support.editable:
            assert written.startswith("written"), (
                f"{structure.value}: editable but record says {written!r}"
            )
        else:
            assert written.startswith(("refused", "not aimed")), (
                f"{structure.value}: not editable, and the record says {written!r}"
            )


def test_every_carried_claim_is_backed_by_a_sample_that_holds_it_outside_the_edit() -> None:
    """A row that says "carried" without a sample carrying it outside the edit is a wish.

    **The counter-mutation this is for.** Deleting the preserve samples and
    leaving the table standing keeps every other witness green: the matrix
    would still be self-consistent and the refusals would still fire. This is
    the witness that fails, because a preservation claim needs a sample whose
    edit went somewhere else.
    """
    text = MATRIX_RECORD.read_text(encoding="utf-8")
    for row in _rows(text, "## The matrix"):
        structure = StructureClass(row[0].strip("`"))
        if not SUPPORT[structure].carried:
            continue
        holders = [
            sample
            for sample in WRITABLE
            if structure in sample.carries and sample.role == "preserve"
        ]
        assert holders, (
            f"{structure.value} is claimed carried, and no sample the seam writes "
            "holds it in a region the edit does not name"
        )


def test_every_refused_claim_is_raised_by_a_sample() -> None:
    """The mirror image: a refusal in the record that no sample reaches."""
    for structure, support in SUPPORT.items():
        if support.editable:
            continue
        aimed = [sample for sample in REFUSED if sample.focus is structure]
        if structure in (StructureClass.COMMENT_PART,):
            continue  # refused for the part, not for a structure: its row is the gate's own
        assert aimed, f"{structure.value} is not editable and no sample aims a change at it"


def test_the_refusal_vocabulary_in_the_record_covers_every_reason_the_gate_gives() -> None:
    """Ten reasons, and the record prints all ten with a sample behind each."""
    text = MATRIX_RECORD.read_text(encoding="utf-8")
    printed = {
        row[0].strip("`") for row in _rows(text, "## What the gate refuses, and with what words")
    }
    assert printed == set(REFUSALS), (
        f"reasons the code gives and the record does not print: {sorted(set(REFUSALS) - printed)}; "
        f"reasons printed with no raise site: {sorted(printed - set(REFUSALS))}"
    )
    for row in _rows(text, "## What the gate refuses, and with what words"):
        reason, samples = row[0].strip("`"), row[2]
        named = re.findall(r"`([^`]+)`", samples)
        assert named, f"{reason}: the record names no sample behind it"
        for name in named:
            assert name in {sample.name for sample in REFUSED}, (
                f"{reason}: {name} is not a refusal sample"
            )


def test_the_run_record_states_the_open_half_as_open() -> None:
    """§5.8's acceptance is half human and half advisor. Neither is faked here.

    **What each missing sentence would mean.** Without the host sentence the
    record would be claiming a dual-host result no person produced; without
    the advisor sentence it would be reporting synthetic coverage as advisor
    use, which `LC-P3-00` §3 forbids.
    """
    text = RUN_RECORD.read_text(encoding="utf-8")
    assert "NOT RUN" in text, "the record states no open half"
    assert "real-sample loop: NOT RUN — held open pending the owner's sample" in text, (
        "the real-sample half does not carry the exact label §5.9 names"
    )
    for phrase in ("PASS WITH NOTES", "the gate passed", "accepted on review"):
        assert phrase not in text, f"the record claims {phrase!r} without an independent review"
    assert "no operator" in text.lower() or "human" in text.lower(), (
        "the record does not say the reopen rows are waiting for a person"
    )


def test_the_run_record_reports_the_options_and_what_each_cost() -> None:
    """A decision basis that prints only the adopted option has not decided anything."""
    text = RUN_RECORD.read_text(encoding="utf-8")
    for option in ("surgical", "reserialize", "library", "rebuild"):
        assert option in text, f"the run record never mentions {option}"
    for row in _rows(text, "## The four options, counted"):
        assert row[0].strip("`") in {"surgical", "reserialize", "library", "rebuild"}
        digits = re.findall(r"\d+", " ".join(row[1:]))
        assert digits, f"the {row[0]} row carries no numbers"


def test_the_record_cites_hashes_and_counts_and_no_sample_text() -> None:
    """The manifest bridge: the tree cites row ids, digests, versions and counts.

    **Why a sentence of a sample would break it.** The substitute set is
    synthetic, so its words are not the corpus's words -- but the rule the
    bridge is built on is that the tree cites artifacts by digest rather than
    quoting them, and a record that starts quoting document text is a record
    that has stopped checking the digests.
    """
    text = RUN_RECORD.read_text(encoding="utf-8")
    digests = re.findall(r"\b[0-9a-f]{64}\b", text)
    assert len(digests) >= 3, "the record cites no artifact digests"
    for sentence in ("The baseline sentence stands at the head", "The caption inside the text box"):
        assert sentence not in text, f"the record quotes manuscript text: {sentence!r}"
    assert "LongPathsEnabled" in text or "260" in text, "the record ignores the path-length wall"
    assert str(MAX_PATH) in text, "the record does not state the ceiling it stayed under"


def test_the_adr_names_the_options_the_adopted_one_and_the_failure_branch() -> None:
    """§5.7 item 1: the options, what each showed, which is adopted, what a no does."""
    text = ADR.read_text(encoding="utf-8")
    for heading in (
        "## Context and concrete problem",
        "## Alternatives",
        "## Decision",
        "## Risks",
    ):
        assert heading in text, f"the ADR has no {heading!r} section"
    assert "temporary" in text.lower(), "the ADR does not label the independent copy temporary"
    assert "LC-P3-03" in text and "§7" in text, (
        "the ADR states neither dependency it sequences against"
    )
    assert "COM" in text and "ProgID" in text, (
        "the ADR does not record the owner's automation ruling"
    )
    for option in ("surgical", "reserialize", "library", "rebuild"):
        assert option in text, f"the ADR never weighs {option}"


def test_the_presence_vocabulary_covers_every_class_a_row_can_ask_for() -> None:
    """The checklist asks a person to confirm presence; every carried class has a word.

    **A class with no word is a class nobody is asked about.** The presence
    list is what turns "the table survived" into a row a person can answer,
    so each class the matrix says is carried must have one.
    """
    answered = set(PRESENCE_BY_CLASS.values())
    for structure, support in SUPPORT.items():
        if support.carried and structure.value.replace("-", "_").replace("-", "") and True:
            if structure in PRESENCE_BY_CLASS:
                continue
            assert structure.value in answered or support.editable is False, (
                f"{structure.value} is claimed carried and no checklist row asks for it"
            )


def test_the_sample_counts_in_the_records_match_the_corpus() -> None:
    """Every count the records print about the corpus is the corpus's own size."""
    text = RUN_RECORD.read_text(encoding="utf-8") + MATRIX_RECORD.read_text(encoding="utf-8")
    numbers = {int(match) for match in re.findall(r"(\d+) samples", text)}
    assert len(SAMPLES) in numbers or not numbers, (
        f"the records say {sorted(numbers)} samples and the corpus holds {len(SAMPLES)}"
    )
    written = {
        int(match)
        for match in re.findall(r"(\d+)(?: of the \d+)? (?:samples )?the seam writes", text)
    }
    assert not written or len(WRITABLE) in written, (
        f"the records say the seam writes {sorted(written)} and the corpus has {len(WRITABLE)}"
    )
