"""The twelve-row closeout tool, watched.

**The property.** The tool that turns a finished twelve-row rerun into a
record has to answer one question correctly: *may this issue be closed?* And
the answer is not the one a row-level ``PASS`` suggests.

**Why it needs watching.** The failure this file exists to catch is a
**conclusion drawn from the wrong rows**. #191's fix is a change to an OOXML
construct, and a construct fix is only shown to be a fix once the caption is
seen on every host that opens the file -- and on Word the caption cannot be
seen while Word refuses the file, which is #192. So #192's fix is a
*precondition* of #191's evidence, and #191's four required rows include the
two Word rows #192 owns. A tool that closed an issue because its rows read
``PASS`` would close #191 on the strength of a WPS observation, and #192
would close on the strength of a WPS row that cannot substitute for it.

**The four cases.** A clean table finds nothing; a table whose hash is not
the artefact's is refused; a Word row that claims ``PASS`` without the
Word-observation marker is refused; and a table whose Word rows record a
refusal does **not** close #191 -- which is the case the whole tool is for.

**The pack is synthetic.** The artefacts here are bytes this file writes, so
the test says what it means: the tool is given a pack, it measures the
pack's artefacts, and it believes a row only when the row's hash is the
artefact's hash.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.negative

#: The tool under test. It is a script rather than a package, so it is run
#: the way the owner runs it -- through the interpreter, as a process.
SCRIPT: Path = Path(__file__).resolve().parent.parent / "scripts" / "closeout_12_rows.py"

#: The 27 columns of the reopen ledger, in order. The test states them
#: itself rather than reading them out of the tool: a witness that quotes
#: the implementation's own table checks nothing.
LEDGER_HEADER: tuple[str, ...] = (
    "row_id",
    "ticket",
    "sample_id",
    "artifact",
    "file_path",
    "file_path_chars",
    "sha256_before",
    "byte_size_before",
    "host_name",
    "host_file_version",
    "host_version_measured_at",
    "expected_presence",
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
    "verdict",
    "notes",
)

#: The families each sample's rows expect to see, and the hosts the two
#: roles are run on.
SAMPLES: Mapping[str, tuple[str, ...]] = {
    "05-image-and-relationship": ("body-text", "images", "media-parts"),
    "07-everything-at-once": (
        "body-text",
        "comment-bodies",
        "comments",
        "equations",
        "hyperlinks",
        "images",
        "media-parts",
        "tables",
        "tracked-revisions",
    ),
    "08-refusals-elsewhere-in-the-document": (
        "body-text",
        "content-controls",
        "fields",
        "images",
        "media-parts",
        "text-boxes",
    ),
}

HOSTS: Mapping[str, str] = {
    "primary": "WPS Office",
    "reference": "Microsoft Office 2019",
}

WORD_MARKER = "word-observation-confirmed"


def _rows_of(pack: Path) -> list[dict[str, str]]:
    """The pack's twelve template rows, built with the artefacts beside them."""
    outputs = pack / "artifacts" / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for sample, families in SAMPLES.items():
        for variant in ("clean", "marked"):
            artifact = f"{sample}-surgical-{variant}.docx"
            payload = f"PK\x03\x04{sample}-{variant}".encode()
            (outputs / artifact).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            # The generator writes Windows paths with the separators
            # doubled, and the ledger counts the collapsed spelling.
            spelling = str(outputs / artifact).replace("\\", "\\\\")
            for role, host in HOSTS.items():
                rows.append(
                    {
                        "row_id": f"{sample}-surgical-{variant}-{role}",
                        "ticket": "LC-P3-02",
                        "sample_id": sample,
                        "artifact": artifact,
                        "file_path": spelling,
                        "file_path_chars": str(len(spelling.replace("\\\\", "\\"))),
                        "sha256_before": digest,
                        "byte_size_before": str(len(payload)),
                        "host_name": host,
                        "host_file_version": "16.0.17932.21140",
                        "host_version_measured_at": "2026-11-18",
                        "expected_presence": "|".join(families),
                    }
                )
    with (pack / "rerun-rows-template-12.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LEDGER_HEADER), lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in LEDGER_HEADER})
    return rows


def _build_pack(root: Path) -> tuple[Path, list[dict[str, str]]]:
    """A synthetic rerun pack: the twelve-row template and the artefacts."""
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    rows = _rows_of(pack)
    return pack, rows


def _observation(row: Mapping[str, str]) -> dict[str, str]:
    """A clean, passing observation for one row."""
    families = [part for part in row["expected_presence"].split("|") if part]
    presence = "|".join(f"{family}:yes" for family in families)
    word = row["host_name"] == HOSTS["reference"]
    notes = f"seen in {row['host_name']}; {WORD_MARKER}" if word else f"seen in {row['host_name']}"
    return {
        "operator": "owner",
        "opened_at": "2026-11-18T09:00:00+08:00",
        "open_result": "opened",
        "prompt_verbatim_or_NONE": "NONE",
        "presence_after_open": presence,
        "close_action": "closed-no-save",
        "reopened_at": "2026-11-18T09:05:00+08:00",
        "presence_after_reopen": presence,
        "reopen_result": "opened",
        "save_performed": "no",
        "sha256_after": row["sha256_before"],
        "byte_size_after": row["byte_size_before"],
        "hash_changed": "no",
        "verdict": "PASS",
        "notes": notes,
    }


def _filled_table(
    path: Path,
    rows: Sequence[Mapping[str, str]],
    overrides: Mapping[str, Mapping[str, str]] | None = None,
) -> Path:
    """Write the filled twelve-row table, with the given cells overridden."""
    changes = overrides or {}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LEDGER_HEADER), lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            record = dict(row)
            record.update(_observation(row))
            record.update(changes.get(str(row["row_id"]), {}))
            writer.writerow({column: record.get(column, "") for column in LEDGER_HEADER})
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the tool the way the owner runs it."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


def _summary(
    pack: Path, filled: Path, *extra: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Run the tool with ``--json`` and read the summary it printed."""
    result = _run("--pack-dir", str(pack), "--filled-csv", str(filled), "--json", *extra)
    payload: dict[str, Any] = json.loads(result.stdout)
    return result, payload


def _verdicts(summary: Mapping[str, Any]) -> dict[str, str]:
    """The issue verdicts, keyed by the issue number."""
    return {str(judgement["issue"]): str(judgement["verdict"]) for judgement in summary["issues"]}


def _findings(summary: Mapping[str, Any], severity: str) -> list[dict[str, str]]:
    return [finding for finding in summary["findings"] if finding["severity"] == severity]


def _word_rows(rows: Sequence[Mapping[str, str]]) -> list[str]:
    """The row ids of the 08 family's Word rows."""
    return [
        str(row["row_id"])
        for row in rows
        if row["sample_id"] == "08-refusals-elsewhere-in-the-document"
        and row["host_name"] == HOSTS["reference"]
    ]


def test_a_clean_table_finds_nothing(tmp_path: Path) -> None:
    """A table that agrees with the pack, the vocabulary and the boundary
    produces no findings at all.

    The verdicts are still not ``CLOSED-READY``: the owner's part -- the
    screenshots, the recorded decisions -- is not on file, and the tool says
    so rather than counting the absence as agreement.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)

    result, summary = _summary(pack, filled)

    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["findings"] == [], summary["findings"]
    assert _verdicts(summary) == {
        "189": "NOT-SETTLED-BY-THE-MACHINE",
        "191": "NOT-SETTLED-BY-THE-MACHINE",
        "192": "NOT-SETTLED-BY-THE-MACHINE",
    }


def test_a_row_whose_hash_is_not_the_artefacts_is_refused(tmp_path: Path) -> None:
    """A row that was not run against the pack's artefact is not evidence.

    The cell carries a digest the artefact does not have. The tool measures
    the artefact itself and refuses the row -- and the issue the row feeds
    does not close on it.
    """
    pack, rows = _build_pack(tmp_path)
    target = str(rows[0]["row_id"])
    filled = _filled_table(
        tmp_path / "filled.csv",
        rows,
        {
            target: {"sha256_before": "0" * 64},
        },
    )

    result, summary = _summary(pack, filled)

    assert result.returncode == 1, result.stdout
    blockers = _findings(summary, "BLOCKER")
    assert any(
        "sha256_before" in finding["message"] and finding["subject"] == target
        for finding in blockers
    ), blockers
    # The row belongs to #189, and #189's evidence is the eight 05/07 rows.
    assert _verdicts(summary)["189"] == "NOT-CLOSED"


def test_a_word_row_that_claims_pass_without_the_marker_is_refused(
    tmp_path: Path,
) -> None:
    """A Word row without the Word-observation marker is not a Word observation.

    The row says the file was seen and says ``PASS``, and its notes are the
    WPS row's notes copied across. A tool that read the verdict cell would
    close #191 and #192 on it.
    """
    pack, rows = _build_pack(tmp_path)
    word_rows = _word_rows(rows)
    assert len(word_rows) == 2
    filled = _filled_table(
        tmp_path / "filled.csv",
        rows,
        {
            word_rows[0]: {"notes": "seen on the desktop"},
        },
    )

    result, summary = _summary(pack, filled)

    assert result.returncode == 1, result.stdout
    blockers = _findings(summary, "BLOCKER")
    assert any(
        WORD_MARKER in finding["message"] and finding["subject"] == word_rows[0]
        for finding in blockers
    ), blockers
    verdicts = _verdicts(summary)
    assert verdicts["191"] == "NOT-CLOSED"
    assert verdicts["192"] == "NOT-CLOSED"


def test_a_refusal_on_the_word_rows_does_not_close_191(tmp_path: Path) -> None:
    """The case the tool exists for: two Word rows that record a refusal.

    The other ten rows read ``PASS``. The two Word rows of the 08 family
    record what Word did: it refused the file, and the refusal was recorded
    as such. **#191 is not closed.** Its closure condition needs all four 08
    rows, and the two Word rows are the ones #192 owns -- on Word the
    caption cannot be seen while Word refuses the file, so #192's fix is a
    precondition of #191's evidence.

    The table's own ``verdict`` cell is checked against the row's record, so
    a row that *claims* ``PASS`` while its ``open_result`` says ``failed`` is
    refused as well: the cell is not evidence of anything.
    """
    pack, rows = _build_pack(tmp_path)
    word_rows = _word_rows(rows)
    filled = _filled_table(
        tmp_path / "filled.csv",
        rows,
        {
            word_rows[0]: {
                "verdict": "REFUSAL-RECORDED",
                "open_result": "failed",
                "reopen_result": "failed",
                "prompt_verbatim_or_NONE": "Word cannot open this file.",
                "presence_after_open": "body-text:no",
                "presence_after_reopen": "body-text:no",
                "notes": "Word refused the file; the refusal was recorded",
            },
            word_rows[1]: {
                "verdict": "REFUSAL-RECORDED",
                "open_result": "failed",
                "reopen_result": "failed",
                "prompt_verbatim_or_NONE": "Word cannot open this file.",
                "presence_after_open": "body-text:no",
                "presence_after_reopen": "body-text:no",
                "notes": "Word refused the file; the refusal was recorded",
            },
        },
    )

    result, summary = _summary(pack, filled)

    assert result.returncode == 1, result.stdout
    verdicts = _verdicts(summary)
    assert verdicts["191"] == "NOT-CLOSED", summary["issues"]
    assert verdicts["192"] == "NOT-CLOSED", summary["issues"]

    # **The ten rows that pass do not carry the issue.** #191's closure
    # condition names four rows, and two of them are unmet.
    judged = next(judgement for judgement in summary["issues"] if judgement["issue"] == "191")
    assert len(judged["required_rows"]) == 4, judged["required_rows"]
    assert {item["row_id"] for item in judged["unmet"]} == set(word_rows), judged


def test_a_word_row_claiming_pass_while_its_record_says_failed_is_refused(
    tmp_path: Path,
) -> None:
    """The verdict cell does not override the row's own record.

    Every cell of the table reads ``PASS``, and the two Word rows' own
    records say the file did not open. The tool believes the record.
    """
    pack, rows = _build_pack(tmp_path)
    word_rows = _word_rows(rows)
    filled = _filled_table(
        tmp_path / "filled.csv",
        rows,
        {
            word_rows[0]: {
                "open_result": "failed",
                "reopen_result": "failed",
                "prompt_verbatim_or_NONE": "Word cannot open this file.",
                "presence_after_open": "body-text:no",
                "presence_after_reopen": "body-text:no",
            },
        },
    )

    result, summary = _summary(pack, filled)

    assert result.returncode == 1, result.stdout
    blockers = _findings(summary, "BLOCKER")
    assert any("contradicts the cell" in finding["message"] for finding in blockers), blockers
    verdicts = _verdicts(summary)
    assert verdicts["191"] == "NOT-CLOSED", summary["issues"]
    assert verdicts["192"] == "NOT-CLOSED", summary["issues"]


def test_190_is_out_of_scope(tmp_path: Path) -> None:
    """The closure table says, in the place a reader looks, that #190 is not
    closed by this rerun and cannot be.

    #190 is a WPS rendering limitation whose one row is not among the
    twelve; its closure route is a dated support-matrix entry. A reader who
    took the twelve rows as evidence about #190 would close an issue that
    nothing in the rerun touched.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)

    result = _run("--pack-dir", str(pack), "--filled-csv", str(filled))
    report = result.stdout

    assert result.returncode == 0, report + result.stderr
    assert "#190" in report
    assert "not in this round's scope" in report
    assert "support-matrix" in report


def test_the_run_writes_nothing_without_write(tmp_path: Path) -> None:
    """The default is to report, not to write.

    A closeout tool that writes by default is a tool that can overwrite the
    evidence it is reading.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)
    out_dir = tmp_path / "out"

    result = _run("--pack-dir", str(pack), "--filled-csv", str(filled), "--out-dir", str(out_dir))

    assert result.returncode == 0, result.stdout + result.stderr
    assert not out_dir.exists()
    assert not list(tmp_path.glob("closeout-*"))
    assert not list(tmp_path.glob("rerun12-append-*"))


def test_write_records_the_append_record_and_leaves_the_ledger_alone(
    tmp_path: Path,
) -> None:
    """``--write`` writes the four artefacts, and never the 44-row ledger.

    The append record carries the new observation on the ledger's own 27
    columns, and says in every row that it is a second observation and not a
    replacement. The ledger is named, read for its digest, and left exactly
    as it was.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)
    ledger = tmp_path / "reopen-rows-filled-2026-11-10.csv"
    ledger.write_bytes(b"row_id,verdict\r\nrow-1,PASS\r\n")
    before = ledger.read_bytes()
    out_dir = tmp_path / "out"

    result, summary = _summary(
        pack, filled, "--out-dir", str(out_dir), "--ledger", str(ledger), "--write"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert ledger.read_bytes() == before, "the 44-row ledger was written to"

    written = [Path(path) for path in summary["written"]]
    assert len(written) == 4, written
    assert all(path.exists() for path in written), written

    append_csv = next(path for path in written if path.suffix == ".csv")
    with append_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        body = list(reader)
    assert tuple(header) == LEDGER_HEADER, header
    assert len(body) == 12, len(body)

    with append_csv.open("r", newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    for record in records:
        assert "does not amend it and does not replace it" in record["notes"], record
        assert "a second observation of the same row" in record["notes"], record

    manifest = next(path for path in written if path.suffix == ".json")
    payload: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["ledger"]["written"] is False
    assert payload["ledger"]["sha256"] == hashlib.sha256(before).hexdigest()


def test_the_tool_refuses_to_write_over_the_ledger(tmp_path: Path) -> None:
    """An output that would land on the ledger is refused.

    The tool is told where the 44-row ledger is; if one of the artefacts it
    is about to write would land on that file, it stops -- with the ledger's
    bytes unchanged.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)
    # The name the append record would carry under this run id.
    ledger = tmp_path / "rerun12-append-ledger-collision.csv"
    ledger.write_bytes(b"row_id,verdict\r\nrow-1,PASS\r\n")
    before = ledger.read_bytes()

    result = _run(
        "--pack-dir",
        str(pack),
        "--filled-csv",
        str(filled),
        "--out-dir",
        str(tmp_path),
        "--ledger",
        str(ledger),
        "--write",
        "--run-id",
        "ledger-collision",
    )

    assert ledger.read_bytes() == before
    assert result.returncode == 2, result.stdout + result.stderr
    assert "refusing to write over the 44-row ledger" in result.stderr


def test_the_tool_runs_against_a_pack_anywhere(tmp_path: Path) -> None:
    """The pack is a parameter, not a place.

    The tool was moved into this repository because it used to live in one
    directory on one machine. It reads whatever pack it is pointed at, and it
    names no path of its own: the same run, from the same tree, works on a
    pack that is somewhere else entirely.
    """
    elsewhere = tmp_path / "somewhere" / "else"
    elsewhere.mkdir(parents=True)
    pack, rows = _build_pack(elsewhere)
    filled = _filled_table(elsewhere / "filled.csv", rows)

    result, summary = _summary(pack, filled)

    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["findings"] == []
    assert summary["pack_dir"] == str(pack)


def test_a_write_that_replaces_a_file_keeps_the_earlier_one(tmp_path: Path) -> None:
    """A file that is already there is copied aside before it is replaced.

    The tool writes through a temp file, a read-back check and an atomic
    replace, and it copies the file that was there first. A run that
    replaces an artefact has therefore not destroyed the earlier one, which
    is what makes the replace safe to run twice.
    """
    pack, rows = _build_pack(tmp_path)
    filled = _filled_table(tmp_path / "filled.csv", rows)
    out_dir = tmp_path / "out"

    first = _run(
        "--pack-dir",
        str(pack),
        "--filled-csv",
        str(filled),
        "--out-dir",
        str(out_dir),
        "--write",
        "--run-id",
        "backup",
    )
    assert first.returncode == 0, first.stdout + first.stderr
    append_csv = out_dir / "rerun12-append-backup.csv"
    before = append_csv.read_bytes()

    second = _run(
        "--pack-dir",
        str(pack),
        "--filled-csv",
        str(filled),
        "--out-dir",
        str(out_dir),
        "--write",
        "--run-id",
        "backup",
    )
    assert second.returncode == 0, second.stdout + second.stderr

    backup = out_dir / "rerun12-append-backup.csv.bak-backup"
    assert backup.exists(), sorted(path.name for path in out_dir.iterdir())
    assert backup.read_bytes() == before
