"""The pilot's material registration, watched.

**What this file watches.** ``scripts/pilot_material_registration.py`` writes
and checks the JSON records under ``docs/pilot/registrations/`` that register
the pilot's desensitised copy -- the record that makes the signed
authorisation (``docs/acceptance/LC-P4-PILOT-providers-config.md`` §6)
answerable to the question *which bytes were approved*. A record nothing
checks is prose with a suffix, and a tool that accepts its own incomplete
output is no gate at all.

So this file drives the script the way its callers do -- through its own
``main``, over real files in a temporary directory -- and witnesses the
properties that make the records trustworthy:

- ``create`` writes a record whose seven parts are all present and
  non-empty, and whose digests are the digests of the bytes it claims:
  measured here, independently of the tool;
- the record holds **no content** of the copy: a marker written into the
  copy's bytes appears nowhere in the record;
- the tool never reads the copy as text -- the copy's bytes are not
  decodable, and the tool succeeds on them anyway;
- ``check`` accepts a complete record and names every problem in an
  incomplete one, and **fails when the registered digest does not match the
  copy** -- the failure this whole apparatus exists to catch;
- ``create`` refuses a copy inside the repository, a copy outside the
  authorised root, a copy the grant's scope does not cover, and a material
  id that already has a record;
- ``sign`` fills the checklist result, refuses an item set the checklist
  does not have, and binds the result to the digest of the copy that is
  registered;
- the checklist and the runbook name the record and the tool, and the
  checklist carries no signed result -- the owner's signature is what is
  still missing.

**Nothing here reads or writes this checkout's own records.** The tool is
pointed at a temporary material root and a temporary output path; the
repository's own ``docs/pilot/registrations/`` is only read, and only to
check that whatever is in it holds.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "pilot_material_registration.py"
CHECKLIST_PATH = REPO_ROOT / "docs" / "plans" / "LC-P4-PILOT-desensitisation-checklist.md"
RUNBOOK_PATH = REPO_ROOT / "docs" / "plans" / "LC-P4-PILOT-runbook.md"
REGISTRATIONS_DIR = REPO_ROOT / "docs" / "pilot" / "registrations"

#: A sentence that is in the copy and in nothing else. If it turns up in the
#: record, the record is holding content.
CONTENT_MARKER = "CONFIDENTIAL-SENTENCE-MUST-NOT-REACH-THE-RECORD-7f3a"

#: The grant the pilot's real-model request went through.
GRANT_ID = "grant-model-suggestions-pilot/LC-P4-PILOT"
GRANT_RECORD = "docs/acceptance/LC-P4-PILOT-providers-config.md"
GRANT_SUBJECT_REF = "pilot/LC-P4-PILOT/desensitised-copy"
GRANT_SCOPE = "pilot/LC-P4-PILOT/desensitised-copy/**"

_spec = importlib.util.spec_from_file_location(
    "pilot_material_registration_under_test", SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None, (
    "scripts/pilot_material_registration.py could not be loaded as a module"
)
registration: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(registration)
registration_main = registration.main


def _run(*arguments: str) -> tuple[int, str, str]:
    """Run the tool the way its callers do, and read its status separately."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = registration_main(list(arguments))
    return code, out.getvalue(), err.getvalue()


class Material:
    """A synthetic copy, its original and its heading outline."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.store = root / "pilot" / "LC-P4-PILOT" / "desensitised-copy"
        self.store.mkdir(parents=True, exist_ok=True)
        self.copy = self.store / "pilot-paper-001.pdf"
        # The bytes are deliberately not valid UTF-8: a tool that read the
        # copy as text would fail on them.
        self.copy.write_bytes(b"%PDF-1.7\n" + CONTENT_MARKER.encode("utf-8") + b"\xff\xfe\x00")
        self.original = root / "source" / "original.pdf"
        self.original.parent.mkdir(parents=True, exist_ok=True)
        self.original.write_bytes(b"%PDF-1.7\noriginal bytes\n")
        self.outline = root / "outline.txt"
        self.outline.write_text("1 Introduction\n2 Method\n3 Results\n", encoding="utf-8")

    @property
    def relative_path(self) -> str:
        return self.copy.relative_to(self.root).as_posix()


@pytest.fixture
def material(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Material:
    """A synthetic material outside the repository, and a tool that knows it."""
    monkeypatch.setenv(
        registration.MATERIAL_ROOTS_ENV,
        str(tmp_path),
    )
    return Material(tmp_path)


def _create_arguments(material: Material, out: Path, **overrides: str | None) -> list[str]:
    """The command line that registers the synthetic copy."""
    arguments: dict[str, str | None] = {
        "--material-id": "pilot-paper-001",
        "--copy": str(material.copy),
        "--original": str(material.original),
        "--outline": str(material.outline),
        "--format": "pdf",
        "--pages": "42",
        "--words": "12345",
        "--figures": "7",
        "--tables": "3",
        "--comments": "18",
        "--revision-marks": "25",
        "--operator": "advisor",
        "--grant-record": GRANT_RECORD,
        "--out": str(out),
    }
    arguments.update(overrides)
    flat: list[str] = []
    for key, value in arguments.items():
        flat.append(key)
        if value is not None:
            flat.append(value)
    return flat


def _create(material: Material, out: Path, **overrides: str | None) -> tuple[int, str, str]:
    return _run("create", *_create_arguments(material, out, **overrides))


def _load(out: Path) -> dict[str, Any]:
    """The record, as the tool wrote it."""
    return cast(dict[str, Any], json.loads(out.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# The record the tool writes
# ---------------------------------------------------------------------------


def test_create_writes_a_record_with_every_part_and_measured_digests(
    material: Material, tmp_path: Path
) -> None:
    """Every part is present, and the digests are the digests of the bytes."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    assert out.exists()

    record = _load(out)
    assert set(record) == set(registration.RECORD_KEYS)
    assert record["record_type"] == registration.RECORD_TYPE
    assert record["material_id"] == "pilot-paper-001"

    copy = record["copy"]
    assert isinstance(copy, dict)
    assert set(copy) == set(registration.COPY_KEYS)
    assert copy["sha256"] == hashlib.sha256(material.copy.read_bytes()).hexdigest()
    assert copy["byte_size"] == material.copy.stat().st_size
    assert copy["origin_sha256"] == hashlib.sha256(material.original.read_bytes()).hexdigest()
    assert copy["origin_byte_size"] == material.original.stat().st_size

    metadata = record["metadata"]
    assert isinstance(metadata, dict)
    assert set(metadata) == set(registration.METADATA_KEYS)
    assert metadata["page_count"] == 42
    assert metadata["comment_count"] == 18
    assert metadata["revision_mark_count"] == 25
    assert metadata["heading_count"] == 3
    assert (
        metadata["heading_outline_sha256"]
        == hashlib.sha256(material.outline.read_bytes()).hexdigest()
    )

    authorisation = record["authorisation"]
    assert isinstance(authorisation, dict)
    assert set(authorisation) == set(registration.AUTHORISATION_KEYS)
    assert authorisation["grant_id"] == GRANT_ID
    assert authorisation["scope"] == GRANT_SCOPE

    storage = record["storage"]
    assert isinstance(storage, dict)
    assert set(storage) == set(registration.STORAGE_KEYS)
    assert storage["root"] == str(material.root)
    assert storage["relative_path"] == material.relative_path

    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    assert set(checklist) == set(registration.CHECKLIST_KEYS)
    assert checklist["document"] == registration.CHECKLIST_RELPATH
    assert checklist["applies_to_sha256"] == copy["sha256"]


def test_the_record_is_written_unsigned(material: Material, tmp_path: Path) -> None:
    """The checklist result is the owner's, and the tool leaves it empty."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    assert checklist["result"] is None


def test_the_record_holds_no_content_of_the_copy(material: Material, tmp_path: Path) -> None:
    """Not one byte of the copy reaches the record."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    written = out.read_bytes()
    assert CONTENT_MARKER.encode("utf-8") not in written
    assert material.copy.read_bytes() not in written
    # The record is a small, structured file -- not a document.
    assert len(written) < 4096


def test_the_tool_never_reads_the_copy_as_text(material: Material, tmp_path: Path) -> None:
    """The copy's bytes are not decodable, and the tool succeeds on them."""
    with pytest.raises(UnicodeDecodeError):
        material.copy.read_bytes().decode("utf-8")
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err


def test_the_tool_refuses_a_declared_format_the_bytes_disagree_with(
    material: Material, tmp_path: Path
) -> None:
    """A record that calls a copy a docx while the bytes say otherwise is wrong."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--format": "docx"})
    assert code == 2
    assert "signature" in err


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def test_check_accepts_a_complete_record(material: Material, tmp_path: Path) -> None:
    """A record the tool wrote passes its own check."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    code, printed, err = _run("check", str(out), "--copy", str(material.copy))
    assert code == 0, printed + err
    assert "the record holds" in printed


def test_check_fails_when_the_digest_does_not_match_the_copy(
    material: Material, tmp_path: Path
) -> None:
    """The failure this apparatus exists to catch: a digest that is not the copy's."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    record = _load(out)
    copy = record["copy"]
    assert isinstance(copy, dict)
    copy["sha256"] = "0" * 64
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    code, printed, err = _run("check", str(out), "--copy", str(material.copy))
    assert code == 1
    assert "copy.sha256" in printed
    assert "hashes to" in printed


def test_check_fails_on_a_missing_field(material: Material, tmp_path: Path) -> None:
    """A record missing a part is not a registration record."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    record = _load(out)
    del record["material_id"]
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    code, printed, err = _run("check", str(out))
    assert code == 1
    assert "material_id" in printed


def test_check_fails_on_a_field_the_vocabulary_does_not_have(
    material: Material, tmp_path: Path
) -> None:
    """A record with a free-text slot is a record that can hold a sentence."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    record = _load(out)
    record["notes"] = CONTENT_MARKER
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    code, printed, err = _run("check", str(out))
    assert code == 1
    assert "notes" in printed


def test_check_fails_when_the_copy_is_not_where_the_record_says(
    material: Material, tmp_path: Path
) -> None:
    """The check is about the material at the registered path, and nowhere else."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    other = tmp_path / "elsewhere.pdf"
    other.write_bytes(material.copy.read_bytes())
    code, _, err = _run("check", str(out), "--copy", str(other))
    assert code == 2
    assert "is not the copy the record registers" in err

    other.write_bytes(b"%PDF-1.7\nother bytes\n")
    code, _, err = _run("check", str(out), "--copy", str(other))
    assert code == 2
    assert "is not the copy the record registers" in err


def test_check_requires_the_signature_when_it_is_asked(material: Material, tmp_path: Path) -> None:
    """The import step's gate: an unsigned record does not pass."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    code, printed, err = _run("check", str(out))
    assert code == 0, printed + err
    assert "signature is what is missing" in printed

    code, printed, err = _run("check", str(out), "--require-signed")
    assert code == 1
    assert "checklist.result" in printed


def test_check_reports_every_problem_at_once(material: Material, tmp_path: Path) -> None:
    """An incomplete record is repairable in one pass."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    record = _load(out)
    metadata = record["metadata"]
    assert isinstance(metadata, dict)
    metadata["page_count"] = -1
    del record["registered_by"]
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    code, printed, err = _run("check", str(out))
    assert code == 1
    assert "metadata.page_count" in printed
    assert "registered_by" in printed


# ---------------------------------------------------------------------------
# What the tool refuses
# ---------------------------------------------------------------------------


def test_create_refuses_a_copy_inside_the_repository(material: Material, tmp_path: Path) -> None:
    """The material's bytes never enter the repository."""
    inside = REPO_ROOT / "docs" / "pilot" / "not-a-copy.pdf"
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--copy": str(inside)})
    assert code == 2
    assert "inside the repository" in err
    assert not out.exists()
    assert not inside.exists()


def test_create_refuses_a_copy_outside_the_authorised_root(
    material: Material, tmp_path: Path
) -> None:
    """The copy lives in the authorised environment, or the record is not written."""
    elsewhere = tmp_path.parent / f"{tmp_path.name}-outside" / "pilot-paper-001.pdf"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    elsewhere.write_bytes(b"%PDF-1.7\n" + CONTENT_MARKER.encode("utf-8"))
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--copy": str(elsewhere)})
    assert code == 2
    assert "not under the storage root" in err
    assert not out.exists()


def test_create_refuses_a_copy_the_grant_does_not_cover(material: Material, tmp_path: Path) -> None:
    """The registered copy has to be inside the scope the signed grant covers.

    The scope is read out of the authorisation record the citation names,
    so an operator cannot widen it on the command line.
    """
    outside = material.root / "somewhere-else" / "pilot-paper-001.pdf"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(material.copy.read_bytes())
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--copy": str(outside)})
    assert code == 2
    assert "no grant in the authorisation record covers" in err
    assert GRANT_SCOPE in err
    assert not out.exists()


def test_create_refuses_a_material_id_that_already_has_a_record(
    material: Material, tmp_path: Path
) -> None:
    """A record is written once; replacing it takes --force."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    code, _, err = _create(material, out)
    assert code == 2
    assert "already exists" in err
    code, _, err = _create(material, out, **{"--force": None})
    assert code == 0, err


def test_create_refuses_a_record_written_outside_the_registrations_folder(
    material: Material, tmp_path: Path
) -> None:
    """Inside the repository, a record lives in the registrations folder."""
    out = REPO_ROOT / "docs" / "pilot" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 2
    assert "registrations folder" in err
    assert not out.exists()


def test_create_refuses_a_record_not_named_for_its_material_id(
    material: Material, tmp_path: Path
) -> None:
    """A record is named for the material it registers."""
    out = tmp_path / "records" / "not-the-material-id.json"
    code, _, err = _create(material, out)
    assert code == 2
    assert "named for its material id" in err
    assert not out.exists()


def test_create_refuses_a_negative_count(material: Material, tmp_path: Path) -> None:
    """A count is a count."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--comments": "-1"})
    assert code == 2
    assert "comment_count" in err


def test_create_refuses_a_material_id_that_is_not_an_id(material: Material, tmp_path: Path) -> None:
    """A material id names a record in a path."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--material-id": "Pilot Paper 001"})
    assert code == 2
    assert "material id" in err


# ---------------------------------------------------------------------------
# The signature
# ---------------------------------------------------------------------------


def _item_ids() -> list[str]:
    """The items the checklist lists, read from the checklist itself."""
    return cast(list[str], registration.signed_item_ids(CHECKLIST_PATH.read_text(encoding="utf-8")))


def _signed_items() -> dict[str, str]:
    """Every checklist item marked as passed."""
    return dict.fromkeys(_item_ids(), "pass")


def test_sign_fills_the_result_and_binds_it_to_the_registered_copy(
    material: Material, tmp_path: Path
) -> None:
    """One act fills the result, and it applies to the copy that is registered."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    items = tmp_path / "items.json"
    items.write_text(json.dumps(_signed_items()), encoding="utf-8")
    code, printed, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 0, err

    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    result = checklist["result"]
    assert isinstance(result, dict)
    assert result["date"] == "2026-11-26"
    assert result["operator"] == "owner"
    assert set(result["items"]) == set(_item_ids())
    assert checklist["applies_to_sha256"] == record["copy"]["sha256"]

    code, printed, err = _run("check", str(out), "--require-signed")
    assert code == 0, printed + err


def test_sign_refuses_to_replace_a_signature_silently(material: Material, tmp_path: Path) -> None:
    """A signature is replaced deliberately, the way a record is replaced."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    items = tmp_path / "items.json"
    items.write_text(json.dumps(_signed_items()), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 0, err

    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-27",
        "--items",
        str(items),
    )
    assert code == 2
    assert "already carries a checklist result" in err

    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    result = checklist["result"]
    assert isinstance(result, dict)
    assert result["date"] == "2026-11-26"

    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-27",
        "--items",
        str(items),
        "--force",
    )
    assert code == 0, err
    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    result = checklist["result"]
    assert isinstance(result, dict)
    assert result["date"] == "2026-11-27"


def test_sign_refuses_an_item_set_that_is_not_the_checklists(
    material: Material, tmp_path: Path
) -> None:
    """Every item the checklist lists is marked, and nothing else is."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    items = tmp_path / "items.json"
    incomplete = _signed_items()
    incomplete.pop(_item_ids()[0])
    items.write_text(json.dumps(incomplete), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 2
    assert "does not cover" in err

    extra = _signed_items()
    extra["A-99"] = "pass"
    items.write_text(json.dumps(extra), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 2
    assert "does not have" in err

    wrong = _signed_items()
    wrong[_item_ids()[0]] = "maybe"
    items.write_text(json.dumps(wrong), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 2
    assert "pass" in err


# ---------------------------------------------------------------------------
# What the review found
# ---------------------------------------------------------------------------


def test_sign_refuses_when_the_material_drifted_after_the_registration(
    material: Material, tmp_path: Path
) -> None:
    """A signature is made against the bytes, not against a memory of them.

    The direction that matters is the material's: the copy changes on
    disk after it was registered, and the signature has to notice.
    """
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    material.copy.write_bytes(b"%PDF-1.7\ndifferent bytes\n")

    items = tmp_path / "items.json"
    items.write_text(json.dumps(_signed_items()), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 2
    assert "copy.sha256" in err

    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    assert checklist["result"] is None, "a signature was written over drifted material"


def test_create_refuses_to_replace_a_signed_record(material: Material, tmp_path: Path) -> None:
    """A tool command does not erase the owner's signature."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err

    items = tmp_path / "items.json"
    items.write_text(json.dumps(_signed_items()), encoding="utf-8")
    code, _, err = _run(
        "sign",
        str(out),
        "--copy",
        str(material.copy),
        "--operator",
        "owner",
        "--date",
        "2026-11-26",
        "--items",
        str(items),
    )
    assert code == 0, err

    code, _, err = _create(material, out, **{"--force": None})
    assert code == 2
    assert "carries the owner's signature" in err

    record = _load(out)
    checklist = record["checklist"]
    assert isinstance(checklist, dict)
    result = checklist["result"]
    assert isinstance(result, dict)
    assert result["date"] == "2026-11-26"


def test_a_name_that_is_a_sentence_is_refused(material: Material, tmp_path: Path) -> None:
    """The operator's name is a name; the record is not a place for a sentence."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--operator": CONTENT_MARKER})
    assert code == 2
    assert "operator" in err
    assert not out.exists()

    code, _, err = _create(
        material, out, **{"--operator": "the quick brown fox jumps over the lazy dog"}
    )
    assert code == 2
    assert "operator" in err
    assert not out.exists()


def test_a_missing_copy_is_a_refusal_not_a_crash(material: Material, tmp_path: Path) -> None:
    """Every failure is a one-line refusal; none of them is a traceback."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    missing = tmp_path / "not-here.pdf"
    code, _, err = _create(material, out, **{"--copy": str(missing)})
    assert code == 2
    assert "does not exist" in err
    assert "Traceback" not in err


def test_an_outline_inside_the_repository_is_refused(material: Material, tmp_path: Path) -> None:
    """The outline holds the copy's headings; it belongs to the authorised root."""
    inside = REPO_ROOT / "docs" / "pilot" / "outline-in-repo.txt"
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--outline": str(inside)})
    assert code == 2
    assert "inside the repository" in err
    assert not out.exists()


@pytest.mark.skipif(os.name != "nt", reason="a separator is a separator only on Windows")
def test_a_root_spelled_differently_is_the_same_root(
    material: Material, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One directory has one name, however it is spelled.

    **The spelling that differs is the separator's, and that is Windows's
    alone.** A backslash is a path separator on Windows and an ordinary
    character in a name on POSIX, so ``/tmp/x`` and ``\\tmp\\x`` are two
    different places on a runner and one place on a workstation. The
    platform-neutral half of the property is witnessed below.
    """
    spelled = str(material.root).replace("/", "\\")
    monkeypatch.setenv(registration.MATERIAL_ROOTS_ENV, spelled)
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    code, printed, err = _run("check", str(out))
    assert code == 0, printed + err


def test_a_root_spelled_with_a_trailing_separator_is_the_same_root(
    material: Material, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One directory has one name, however it is spelled.

    **The spelling that differs is one every platform shares**: a trailing
    separator, or a redundant component. Both name the same directory on
    Windows and on POSIX, so this is the half of the property that does not
    need a platform to be true.

    Red by: the tool comparing the authorised root as a string and refusing
    a copy under a root that carries a trailing separator.
    """
    monkeypatch.setenv(registration.MATERIAL_ROOTS_ENV, str(material.root) + os.sep)
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    code, printed, err = _run("check", str(out))
    assert code == 0, printed + err


@pytest.mark.skipif(os.name != "nt", reason="the case rule is the filesystem's")
def test_the_scope_matches_the_way_the_filesystem_matches(
    material: Material, tmp_path: Path
) -> None:
    """On Windows a directory is one directory however it is spelled."""
    store = material.root / "PILOT" / "LC-P4-PILOT" / "desensitised-copy"
    store.mkdir(parents=True, exist_ok=True)
    copy = store / "pilot-paper-001.pdf"
    copy.write_bytes(material.copy.read_bytes())
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out, **{"--copy": str(copy)})
    assert code == 0, err


def test_the_grant_comes_from_the_record_the_citation_names(
    material: Material, tmp_path: Path
) -> None:
    """The scope in the record is the scope in the authorisation record."""
    out = tmp_path / "records" / "pilot-paper-001.json"
    code, _, err = _create(material, out)
    assert code == 0, err
    record = _load(out)
    authorisation = record["authorisation"]
    assert isinstance(authorisation, dict)
    text = (REPO_ROOT / GRANT_RECORD).read_text(encoding="utf-8")
    assert authorisation["scope"] in text
    assert authorisation["grant_id"] in text
    assert authorisation["subject_ref"] in text


# ---------------------------------------------------------------------------
# The documents
# ---------------------------------------------------------------------------


def test_the_checklist_names_the_record_and_the_tool() -> None:
    """The checklist says where the registration lives and what fills it."""
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "docs/pilot/registrations/" in text
    assert "scripts/pilot_material_registration.py" in text


def test_the_checklist_carries_no_signed_result() -> None:
    """The owner's signature is what is missing, and the document says so."""
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    rows = [
        line
        for line in text.splitlines()
        if line.strip().startswith("|") and line.strip().strip("|").split("|")[0].strip() == "D-6"
    ]
    assert rows, "the checklist's part D no longer has a D-6 row"
    for row in rows:
        assert re.search(r"\d{4}-\d{2}-\d{2}", row) is None, (
            "the checklist's D-6 row carries a date; the result is the owner's to write"
        )
    assert "the owner" in text.lower()


def test_the_runbook_imports_a_registered_copy() -> None:
    """Steps 1 and 2 name the registration, so the import has something to check."""
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "scripts/pilot_material_registration.py" in text
    assert "docs/pilot/registrations/" in text


def test_every_record_in_the_repository_holds() -> None:
    """Whatever the repository carries, the tool's own check accepts."""
    assert REGISTRATIONS_DIR.is_dir(), (
        "the folder the records live in is not in the tree, so the witness that "
        "checks what is in it can never fail"
    )
    records = sorted(REGISTRATIONS_DIR.glob("*.json"))
    for record_path in records:
        code, printed, err = _run("check", str(record_path))
        assert code == 0, f"{record_path}: {printed}{err}"


def test_the_records_directory_and_the_tool_agree() -> None:
    """The folder the tool writes into is the folder the repository has."""
    assert Path("docs") / "pilot" / "registrations" == registration.REGISTRATIONS_SUBDIR
    assert (REPO_ROOT / registration.REGISTRATIONS_SUBDIR).parent.exists()
