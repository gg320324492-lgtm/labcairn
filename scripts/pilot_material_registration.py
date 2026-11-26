"""Register the pilot's desensitised copy: one JSON record, measured and checked.

**The hole this closes.** The pilot's authorisation is signed
(``docs/acceptance/LC-P4-PILOT-providers-config.md`` §6 grants
``model_suggestions`` over ``pilot/LC-P4-PILOT/desensitised-copy``), but the
copy that grant covers was never registered.  A signed grant over an
unregistered material is a hole nothing in the tree can see: no record says
which bytes were approved, so no later reader can tell whether the material
that arrived is the material the advisor signed for.

**What this tool writes.**  One record per copy -- a JSON file under
``docs/pilot/registrations/`` -- carrying the checklist's part D as fields:

* the material id every later record points at (D-1);
* the authorisation the copy is covered by (D-2);
* the metadata set: counts and digests only (D-3);
* the fingerprint: the copy's sha256 and the original it was derived from
  (D-4);
* the storage path in the authorised environment (D-5);
* the checklist result -- **left empty** (D-6).

**What it never holds.**  No byte of the material, no sentence of the
manuscript, no comment body, no tracked-change text.  The tool hashes the
copy and counts the outline; it does not read the copy as text, and it does
not copy the copy anywhere.  The record's vocabulary is closed -- the tool
builds the record itself, field by field, and a key it does not know is a
key it refuses.  The two places where a word could go -- an operator's name
and a copy's file name -- are held to a name's length and a name's number
of words.

**The grant is read, not claimed.**  The command line names the
authorisation record in this repository, and the tool reads the grant out
of it: the one whose ``scope`` covers the copy's path.  A scope typed on
the command line would be the operator's claim about the grant.

**Who signs.**  ``create`` writes the record with the checklist result
*empty*.  The result -- the date, the operator and the per-item pass/fail --
is the owner's, and ``sign`` is the act that fills it.  ``sign`` measures
the copy it is given -- it has to be the copy the record registers -- and
refuses a record whose digest does not match it, so a signature cannot
drift onto a different copy (C-4's single-pass rule) and cannot be given
to bytes nobody looked at.

**Three subcommands.**

    python scripts/pilot_material_registration.py create [...]
    python scripts/pilot_material_registration.py check docs/pilot/registrations/<id>.json
    python scripts/pilot_material_registration.py sign  docs/pilot/registrations/<id>.json [...]

``create`` measures the digests itself, writes the record and checks it.
``check`` measures a record against the checklist and, with ``--copy``,
against the copy's bytes -- a record whose digest does not match the copy
fails the check.  ``sign`` fills the checklist result and refuses a set of
items the checklist does not have, or does not have all of.

The rule the records obey is the repository's own: **every digest is
measured at the moment the record is written, never carried forward from an
older record.**
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

#: Where the records live, relative to the repository root.
REGISTRATIONS_SUBDIR = Path("docs") / "pilot" / "registrations"

#: The authorised roots a copy may live in.  G0 §4: the raw files stay in the
#: authorised environment, and the repository holds digests, counts, ids and
#: paths only.  The environment variable overrides the default so that a
#: record can be produced on a machine whose authorised root is elsewhere --
#: the pilot's own root is the default, and the rule that never moves is the
#: one below it: the copy is never inside this repository.
DEFAULT_MATERIAL_ROOTS: tuple[str, ...] = ("E:/trial-material",)

#: The environment variable that names the authorised roots, separated by
#: the platform's path separator.
MATERIAL_ROOTS_ENV = "LABCAIRN_MATERIAL_ROOTS"

#: The checklist the record's signature covers, relative to the repository
#: root.
CHECKLIST_RELPATH = "docs/plans/LC-P4-PILOT-desensitisation-checklist.md"

#: The record's own identity.  A file that is not one of these is not a
#: registration record, whatever else it holds.
RECORD_TYPE = "pilot-material-registration"
RECORD_VERSION = 1

#: The item the checklist result cannot contain: the result *is* that item.
RESULT_ITEM_ID = "D-6"

#: The values a per-item result may take.
RESULT_VALUES: tuple[str, ...] = ("pass", "fail")

#: A material id is a stable, lowercase token: it names a record in a path.
MATERIAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: A digest is 64 lowercase hex digits -- what hashlib writes, nothing else.
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: A person's name, as the record spells it: a name, not a paragraph.
#:
#: The length and the word count are what keep it a name. A name is short
#: and has few words; a sentence from the manuscript has neither, and the
#: record has to be a place a sentence cannot reach.
PERSON_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 ._-]{0,39}$")

#: How many words a name or a file name may have. A name has at most a
#: few; a sentence has as many as it needs.
MAX_WORDS = 4

#: A short token: a format name, a file format's spelling.
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")

#: A bare file name -- no directory, so the record holds no path twice.
FILE_NAME_PATTERN = re.compile(r"^[^/\\]{1,64}$")

#: A record pointer: a repository-relative path, a grant id, a subject
#: reference.  No traversal, no absolute path, no drive letter.
REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{0,191}$")

#: A scope is a reference that also carries the glob's wildcards.
SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._*+/-]{0,191}$")

#: A calendar date, as the owner writes them: YYYY-MM-DD and nothing else.
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: A checklist item id, as the checklist's tables spell them.
ITEM_ID_PATTERN = re.compile(r"^[A-E]-\d+$")

#: The record's fields.  The vocabulary is closed: a key outside these sets
#: is a key the tool refuses to write and the checker refuses to accept,
#: because a record with a free-text field is a record that can hold a
#: sentence of the material.
RECORD_KEYS: frozenset[str] = frozenset(
    {
        "record_type",
        "record_version",
        "material_id",
        "registered_at",
        "registered_by",
        "copy",
        "metadata",
        "authorisation",
        "storage",
        "checklist",
    }
)
COPY_KEYS: frozenset[str] = frozenset(
    {
        "file_name",
        "byte_size",
        "sha256",
        "format",
        "origin_sha256",
        "origin_byte_size",
    }
)
METADATA_KEYS: frozenset[str] = frozenset(
    {
        "page_count",
        "word_count",
        "figure_count",
        "table_count",
        "comment_count",
        "revision_mark_count",
        "heading_count",
        "heading_outline_sha256",
    }
)
AUTHORISATION_KEYS: frozenset[str] = frozenset(
    {
        "grant_id",
        "record",
        "subject_ref",
        "scope",
        "granted_by",
        "granted_at",
        "expires_at",
    }
)
STORAGE_KEYS: frozenset[str] = frozenset({"root", "relative_path"})
CHECKLIST_KEYS: frozenset[str] = frozenset({"document", "applies_to_sha256", "result"})
RESULT_KEYS: frozenset[str] = frozenset({"date", "operator", "items"})

#: The formats whose file signature the tool knows, and the bytes that
#: signature starts with.  A record that calls a copy a ``docx`` while the
#: bytes say otherwise is a record that is wrong about its own material.
FORMAT_SIGNATURES: dict[str, bytes] = {
    "docx": b"PK\x03\x04",
    "docm": b"PK\x03\x04",
    "xlsx": b"PK\x03\x04",
    "pptx": b"PK\x03\x04",
    "pdf": b"%PDF-",
}


class RegistrationError(Exception):
    """A refusal the tool can state in one line."""


# ---------------------------------------------------------------------------
# Repository, roots and paths
# ---------------------------------------------------------------------------


def _git(*arguments: str) -> str:
    """Run git in the current repository and return its stripped stdout."""
    result = subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RegistrationError(
            f"git {' '.join(arguments)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


@functools.lru_cache(maxsize=1)
def repository_root() -> Path:
    """The repository this tool lives in.

    Not the one the current working directory belongs to: the guard that
    keeps the material out of the repository has to mean *this* repository
    whatever directory the operator happened to run the tool from. The
    script's own location says which repository that is.

    Resolved once per process: the tool runs in one place, and asking git
    again for every check costs more than it buys.
    """
    here = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=here,
    )
    if result.returncode != 0:
        raise RegistrationError(
            f"{here} is not a repository; the tool has to be run from the repository it belongs to"
        )
    return here


def authorised_roots() -> tuple[str, ...]:
    """The roots a copy may live in, as they are configured here.

    The environment variable names several roots, separated by semicolons.
    The separator is a semicolon and not the platform's own, because a
    Windows root carries a drive letter and a colon is part of the path.
    """
    configured = os.environ.get(MATERIAL_ROOTS_ENV, "").strip()
    if not configured:
        return DEFAULT_MATERIAL_ROOTS
    return tuple(part.strip() for part in configured.split(";") if part.strip())


def _is_inside(child: Path, parent: Path) -> bool:
    """Whether ``child`` is ``parent`` or lives under it."""
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _same_path(left: Path, right: Path) -> bool:
    """Whether two paths name the same place.

    Compared as paths and not as strings: ``E:\\trial-material`` and
    ``E:/trial-material`` are one directory on Windows, and a record that
    was written with one spelling has to pass a check that reads it with
    the other.
    """
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _is_authorised_root(root: str) -> bool:
    """Whether a root is one of the authorised ones, however it is spelled."""
    return any(_same_path(Path(root), Path(candidate)) for candidate in authorised_roots())


def _registered_copy_path(storage: Any) -> Path | None:
    """The path the record says the copy lives at, or None if it says nothing."""
    if not isinstance(storage, dict):
        return None
    root = storage.get("root")
    relative = storage.get("relative_path")
    if not _nonempty_str(root) or not _nonempty_str(relative):
        return None
    return Path(root) / relative


def _require_outside_repository(path: Path, what: str) -> None:
    """Refuse a path that would put the material inside this repository."""
    if _is_inside(path, repository_root()):
        raise RegistrationError(
            f"{what} is inside the repository ({path}); the material's bytes never "
            f"enter the repository, and neither does anything that carries them"
        )


def _relative_to_root(path: Path, root: Path) -> str:
    """The path under ``root``, in posix form.

    A path that is not under the root at all, or that escapes it with
    ``..``, is refused rather than repaired: a record that names a path the
    operator did not mean is worse than no record.
    """
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise RegistrationError(
            f"{path} is not under the storage root {root}; the copy must live in "
            f"the authorised environment"
        ) from error
    text = relative.as_posix()
    if text in {"", "."}:
        raise RegistrationError(f"{path} is the storage root itself, not a copy inside it")
    return text


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """The sha256 of a file's bytes, measured now.

    The file is opened in binary and read in blocks.  It is never decoded:
    the material is measured, not read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def measure_file(path: Path, what: str) -> tuple[int, str]:
    """The size and the sha256 of a file, measured now."""
    if not path.exists():
        raise RegistrationError(f"the {what} does not exist: {path}")
    if not path.is_file():
        raise RegistrationError(f"the {what} is not a file: {path}")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise RegistrationError(f"the {what} cannot be read: {path} ({error})") from error
    return size, sha256_file(path)


def measure_outline(path: Path) -> tuple[int, str]:
    """The heading count and the digest of an outline file, measured now.

    The outline is a plain file the operator exports from the copy -- one
    heading per line.  The tool measures it and keeps the digest and the
    count; the headings themselves stay in the authorised environment.
    """
    if not path.exists():
        raise RegistrationError(f"the heading outline file does not exist: {path}")
    _, digest = measure_file(path, "heading outline file")
    headings = 0
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                headings += 1
    return headings, digest


def _check_format_signature(path: Path, declared: str) -> None:
    """Refuse a declared format the bytes disagree with."""
    signature = FORMAT_SIGNATURES.get(declared.lower())
    if signature is None:
        return
    if not path.is_file():
        raise RegistrationError(f"the copy is not a file: {path}")
    try:
        with path.open("rb") as handle:
            head = handle.read(len(signature))
    except OSError as error:
        raise RegistrationError(f"the copy cannot be read: {path} ({error})") from error
    if head != signature:
        raise RegistrationError(
            f"the copy is declared {declared!r} but its bytes do not start with that "
            f"format's signature; the record would be wrong about its own material"
        )


# ---------------------------------------------------------------------------
# The checklist
# ---------------------------------------------------------------------------


def checklist_item_ids(text: str) -> list[str]:
    """The checklist's item ids, in the order the document lists them.

    They are read from the document rather than repeated here, so a checklist
    that grows an item makes the signature cover it without this file being
    edited.
    """
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and ITEM_ID_PATTERN.match(cells[0]):
            found.append(cells[0])
    return found


def signed_item_ids(text: str) -> list[str]:
    """The item ids the owner's signature has to cover.

    Every item the checklist lists, except the result item itself: the
    result is D-6, so D-6 cannot also be one of the things the result
    asserts about.
    """
    return [item for item in checklist_item_ids(text) if item != RESULT_ITEM_ID]


# ---------------------------------------------------------------------------
# The grant
# ---------------------------------------------------------------------------

#: The fields a grant has to carry to be one.
GRANT_KEYS: frozenset[str] = frozenset(
    {"grant_id", "scope", "subject_ref", "granted_by", "granted_at", "expires_at"}
)

#: The fields of the record's authorisation section, and the grant's own
#: spelling of them.
GRANT_FIELDS: tuple[tuple[str, str], ...] = (
    ("grant_id", "grant_id"),
    ("subject_ref", "subject_ref"),
    ("scope", "scope"),
    ("granted_by", "granted_by"),
    ("granted_at", "granted_at"),
    ("expires_at", "expires_at"),
)


def _json_blocks(text: str) -> list[Any]:
    """The JSON blocks in a markdown file, parsed."""
    blocks: list[Any] = []
    for chunk in re.findall(r"```json[ \t]*\n(.*?)```", text, flags=re.DOTALL):
        try:
            blocks.append(json.loads(chunk))
        except json.JSONDecodeError:
            continue
    return blocks


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    """Every object inside a parsed document, at any depth."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def grants_in(record_path: Path) -> list[dict[str, str]]:
    """The grants a repository record carries, read from the record itself.

    A grant is a JSON object that carries the six fields a grant has. The
    records that hold one are markdown files with JSON blocks in them, so
    every fenced JSON block is parsed and every object in it that looks
    like a grant is collected.

    **The point of reading them here.** A scope typed on the command line
    is the operator's claim about the grant; a scope read out of the
    authorisation record is the grant. The tool checks the copy against
    the second one, so the check cannot be satisfied by a claim.
    """
    try:
        text = record_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RegistrationError(
            f"the authorisation record cannot be read: {record_path} ({error})"
        ) from error
    found: list[dict[str, str]] = []
    for block in _json_blocks(text):
        for candidate in _walk_dicts(block):
            if set(candidate) >= GRANT_KEYS:
                found.append(
                    {
                        field: str(candidate[grant_field])
                        for field, grant_field in GRANT_FIELDS
                        if isinstance(candidate[grant_field], (str, int, float))
                    }
                )
    return found


def grant_covering(grants: list[dict[str, str]], relative_path: str) -> dict[str, str]:
    """The one grant that covers the copy's path.

    Exactly one has to cover it: none means the material is outside every
    grant the authorisation record carries, and more than one means the
    record does not say which grant the copy is registered under.
    """
    covering = [grant for grant in grants if scope_covers(grant.get("scope", ""), relative_path)]
    if not covering:
        scopes = ", ".join(sorted({grant.get("scope", "") for grant in grants})) or "none"
        raise RegistrationError(
            f"no grant in the authorisation record covers the copy's path "
            f"{relative_path!r}; the grant(s) it carries cover {scopes}"
        )
    if len(covering) > 1:
        ids = ", ".join(sorted(grant.get("grant_id", "?") for grant in covering))
        raise RegistrationError(
            f"{len(covering)} grants in the authorisation record cover the copy's "
            f"path ({ids}); the record does not say which one the copy is registered "
            f"under"
        )
    return covering[0]


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_few_words(value: str) -> bool:
    """Whether a value reads as a label rather than as a sentence.

    A name has a few words; a sentence from the manuscript has as many as
    it needs. This is the check that keeps the two free-text-ish fields of
    the record -- an operator's name and a copy's file name -- places a
    sentence cannot reach.
    """
    return len(value.split()) <= MAX_WORDS


def _is_person(value: Any) -> bool:
    """Whether a value is a name the record can hold."""
    return isinstance(value, str) and bool(PERSON_PATTERN.match(value)) and _has_few_words(value)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_timestamp(value: Any) -> bool:
    """A UTC ISO-8601 timestamp, as the tool writes them."""
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _is_date(value: Any) -> bool:
    """A calendar date, as the owner writes them."""
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _scope_pattern(scope: str) -> re.Pattern[str]:
    """The scope's glob as a pattern.

    ``**`` spans the rest of the path, ``*`` spans one segment, and
    everything else is literal. The match ignores case where the
    filesystem does: on Windows ``Pilot`` and ``pilot`` are one
    directory, and a scope that refuses the other spelling would refuse a
    copy that is inside it.
    """
    parts: list[str] = []
    for segment in scope.split("/"):
        if segment == "**":
            parts.append(".*")
        elif segment == "*":
            parts.append("[^/]*")
        else:
            parts.append(re.escape(segment))
    flags = re.IGNORECASE if os.name == "nt" else 0
    return re.compile("^" + "/".join(parts) + "$", flags)


def scope_covers(scope: str, relative_path: str) -> bool:
    """Whether the grant's scope covers the copy's path in the store."""
    return bool(_scope_pattern(scope).match(relative_path))


def _relative_path_is_safe(relative_path: str) -> bool:
    """Whether a stored relative path stays inside the store."""
    if not relative_path or relative_path.startswith(("/", "\\")):
        return False
    if ":" in relative_path:
        return False
    segments = relative_path.replace("\\", "/").split("/")
    return all(segment not in {"", ".", ".."} for segment in segments)


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


def build_record(
    *,
    material_id: str,
    operator: str,
    copy_path: Path,
    original_path: Path,
    storage_root: str,
    relative_path: str,
    file_format: str,
    counts: dict[str, int],
    heading_count: int,
    heading_digest: str,
    authorisation: dict[str, str],
) -> dict[str, Any]:
    """Assemble the record from the measurements and the supplied values.

    The record is built here, field by field, from a fixed vocabulary.  There
    is no free-text slot and no "notes" field, so there is nowhere for a
    sentence of the material to go.
    """
    copy_size, copy_digest = measure_file(copy_path, "copy")
    origin_size, origin_digest = measure_file(original_path, "original")
    return {
        "record_type": RECORD_TYPE,
        "record_version": RECORD_VERSION,
        "material_id": material_id,
        "registered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registered_by": operator,
        "copy": {
            "file_name": copy_path.name,
            "byte_size": copy_size,
            "sha256": copy_digest,
            "format": file_format,
            "origin_sha256": origin_digest,
            "origin_byte_size": origin_size,
        },
        "metadata": {
            "page_count": counts["page_count"],
            "word_count": counts["word_count"],
            "figure_count": counts["figure_count"],
            "table_count": counts["table_count"],
            "comment_count": counts["comment_count"],
            "revision_mark_count": counts["revision_mark_count"],
            "heading_count": heading_count,
            "heading_outline_sha256": heading_digest,
        },
        "authorisation": dict(authorisation),
        "storage": {
            "root": storage_root,
            "relative_path": relative_path,
        },
        "checklist": {
            "document": CHECKLIST_RELPATH,
            "applies_to_sha256": copy_digest,
            "result": None,
        },
    }


def write_record(record: dict[str, Any], out_path: Path) -> None:
    """Write the record as JSON, one file, and nothing else beside it."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def check_record(
    record: Any,
    *,
    expected_stem: str | None = None,
    repo_root: Path | None = None,
    copy_path: Path | None = None,
    require_signed: bool = False,
) -> list[str]:
    """Measure a record against the checklist and the copy.

    Every problem is named, so an incomplete record can be repaired in one
    pass.  An empty list means the record holds.
    """
    problems: list[str] = []

    def problem(field: str, message: str) -> None:
        problems.append(f"{field}: {message}")

    if not isinstance(record, dict):
        return [f"record: expected a JSON object, found {type(record).__name__}"]

    extra = sorted(set(record) - RECORD_KEYS)
    if extra:
        problem("record", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    missing = sorted(RECORD_KEYS - set(record))
    if missing:
        problem("record", f"missing fields: {', '.join(missing)}")

    if record.get("record_type") != RECORD_TYPE:
        problem("record_type", f"expected {RECORD_TYPE!r}")
    if record.get("record_version") != RECORD_VERSION:
        problem("record_version", f"expected {RECORD_VERSION}")

    material_id = record.get("material_id")
    if not _nonempty_str(material_id):
        problem("material_id", "missing or empty")
    elif not MATERIAL_ID_PATTERN.match(material_id):
        problem("material_id", f"{material_id!r} is not a lowercase id token")
    elif expected_stem is not None and material_id != expected_stem:
        problem(
            "material_id", f"{material_id!r} does not match the file name stem {expected_stem!r}"
        )

    if not _is_timestamp(record.get("registered_at")):
        problem("registered_at", "missing, empty, or not a UTC ISO-8601 timestamp")
    if not _nonempty_str(record.get("registered_by")):
        problem("registered_by", "missing or empty")
    elif not _is_person(record["registered_by"]):
        problem("registered_by", "is not a name the record can hold")

    _check_copy(record.get("copy"), problem)
    _check_metadata(record.get("metadata"), problem)
    authorisation_fields = _check_authorisation(record.get("authorisation"), repo_root, problem)
    storage = record.get("storage")
    _check_storage(storage, authorisation_fields, problem)

    _check_checklist(
        record.get("checklist"), record.get("copy"), repo_root, require_signed, problem
    )

    if copy_path is not None:
        _check_against_copy(record.get("copy"), copy_path, problem)

    return problems


def _check_copy(copy: Any, problem: Any) -> None:
    if not isinstance(copy, dict):
        problem("copy", "missing or not an object")
        return
    extra = sorted(set(copy) - COPY_KEYS)
    if extra:
        problem("copy", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    if not _nonempty_str(copy.get("file_name")):
        problem("copy.file_name", "missing or empty")
    elif not FILE_NAME_PATTERN.match(copy["file_name"]):
        problem("copy.file_name", "is not a bare file name")
    elif not _has_few_words(Path(copy["file_name"]).stem):
        problem("copy.file_name", "reads as a sentence rather than a name")
    size = copy.get("byte_size")
    if not _is_int(size) or size <= 0:
        problem("copy.byte_size", "missing, or not a positive whole number")
    digest = copy.get("sha256")
    if not _nonempty_str(digest):
        problem("copy.sha256", "missing or empty")
    elif not SHA256_PATTERN.match(digest):
        problem("copy.sha256", "is not a 64-hex-digit sha256 digest")
    if not _nonempty_str(copy.get("format")):
        problem("copy.format", "missing or empty")
    elif not TOKEN_PATTERN.match(copy["format"]):
        problem("copy.format", "is not a short token")
    origin_digest = copy.get("origin_sha256")
    if not _nonempty_str(origin_digest):
        problem("copy.origin_sha256", "missing or empty")
    elif not SHA256_PATTERN.match(origin_digest):
        problem("copy.origin_sha256", "is not a 64-hex-digit sha256 digest")
    origin_size = copy.get("origin_byte_size")
    if not _is_int(origin_size) or origin_size <= 0:
        problem("copy.origin_byte_size", "missing, or not a positive whole number")


def _check_metadata(metadata: Any, problem: Any) -> None:
    if not isinstance(metadata, dict):
        problem("metadata", "missing or not an object")
        return
    extra = sorted(set(metadata) - METADATA_KEYS)
    if extra:
        problem("metadata", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    for field in (
        "page_count",
        "word_count",
        "figure_count",
        "table_count",
        "comment_count",
        "revision_mark_count",
        "heading_count",
    ):
        value = metadata.get(field)
        if not _is_int(value) or value < 0:
            problem(f"metadata.{field}", "missing, or not a whole number of zero or more")
    digest = metadata.get("heading_outline_sha256")
    if not _nonempty_str(digest):
        problem("metadata.heading_outline_sha256", "missing or empty")
    elif not SHA256_PATTERN.match(digest):
        problem("metadata.heading_outline_sha256", "is not a 64-hex-digit sha256 digest")


def _check_authorisation(
    authorisation: Any, repo_root: Path | None, problem: Any
) -> dict[str, str]:
    if not isinstance(authorisation, dict):
        problem("authorisation", "missing or not an object")
        return {}
    extra = sorted(set(authorisation) - AUTHORISATION_KEYS)
    if extra:
        problem("authorisation", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    for field in ("grant_id", "subject_ref"):
        value = authorisation.get(field)
        if not _nonempty_str(value):
            problem(f"authorisation.{field}", "missing or empty")
        elif not REFERENCE_PATTERN.match(value) or ".." in value:
            problem(f"authorisation.{field}", "is not a reference the record can hold")
    scope = authorisation.get("scope")
    if not _nonempty_str(scope):
        problem("authorisation.scope", "missing or empty")
    elif not SCOPE_PATTERN.match(scope):
        problem("authorisation.scope", "is not a scope the record can hold")
    if not _nonempty_str(authorisation.get("record")):
        problem("authorisation.record", "missing or empty")
    elif not REFERENCE_PATTERN.match(authorisation["record"]):
        problem("authorisation.record", "is not a repository-relative path")
    elif repo_root is not None:
        _check_the_grant_it_cites(authorisation, repo_root, problem)
    if not _nonempty_str(authorisation.get("granted_by")):
        problem("authorisation.granted_by", "missing or empty")
    elif not _is_person(authorisation["granted_by"]):
        problem("authorisation.granted_by", "is not a name the record can hold")
    granted_at = authorisation.get("granted_at")
    expires_at = authorisation.get("expires_at")
    if not _is_timestamp(granted_at):
        problem("authorisation.granted_at", "missing, empty, or not a UTC ISO-8601 timestamp")
    if not _is_timestamp(expires_at):
        problem("authorisation.expires_at", "missing, empty, or not a UTC ISO-8601 timestamp")
    if (
        _is_timestamp(granted_at)
        and _is_timestamp(expires_at)
        and (datetime.fromisoformat(expires_at) <= datetime.fromisoformat(granted_at))
    ):
        problem("authorisation.expires_at", "is not after authorisation.granted_at")
    return {key: value for key, value in authorisation.items() if isinstance(value, str)}


def _check_the_grant_it_cites(authorisation: dict[str, str], repo_root: Path, problem: Any) -> None:
    """The grant the record names has to be the grant the record cites.

    The record is a copy of what an authorisation record says. When the
    authorisation record changes -- a scope narrowed, a grant withdrawn --
    the registration that cites it is stale, and a stale registration is
    one nobody notices until the material is sent somewhere it may not go.
    """
    relative = authorisation["record"]
    path = repo_root / relative
    if not path.is_file():
        problem("authorisation.record", f"names a file that is not in the repository: {relative}")
        return
    try:
        grants = grants_in(path)
    except RegistrationError as error:
        problem("authorisation.record", str(error))
        return
    grant_id = authorisation.get("grant_id", "")
    matching = [grant for grant in grants if grant.get("grant_id") == grant_id]
    if not matching:
        problem(
            "authorisation.grant_id",
            f"names a grant that the record it cites does not carry: {grant_id}",
        )
        return
    for field, _grant_field in GRANT_FIELDS:
        if field == "grant_id":
            continue
        if authorisation.get(field) != matching[0].get(field):
            problem(
                f"authorisation.{field}",
                f"is {authorisation.get(field)!r} but the grant in {relative} says "
                f"{matching[0].get(field)!r}; the record is stale",
            )


def _check_storage(storage: Any, authorisation: dict[str, str], problem: Any) -> None:
    if not isinstance(storage, dict):
        problem("storage", "missing or not an object")
        return
    extra = sorted(set(storage) - STORAGE_KEYS)
    if extra:
        problem("storage", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    root = storage.get("root")
    if not _nonempty_str(root):
        problem("storage.root", "missing or empty")
    elif not _is_authorised_root(root):
        problem(
            "storage.root",
            f"{root!r} is not one of the authorised roots ({', '.join(authorised_roots())})",
        )
    relative_path = storage.get("relative_path")
    if not _nonempty_str(relative_path):
        problem("storage.relative_path", "missing or empty")
        return
    if not _relative_path_is_safe(relative_path):
        problem("storage.relative_path", "is not a path inside the store")
        return
    scope = authorisation.get("scope")
    if _nonempty_str(scope) and not scope_covers(scope, relative_path):
        problem(
            "storage.relative_path",
            f"is not inside the scope the authorisation grants ({scope})",
        )


def _check_checklist(
    checklist: Any,
    copy: Any,
    repo_root: Path | None,
    require_signed: bool,
    problem: Any,
) -> None:
    if not isinstance(checklist, dict):
        problem("checklist", "missing or not an object")
        return
    extra = sorted(set(checklist) - CHECKLIST_KEYS)
    if extra:
        problem("checklist", f"holds fields the vocabulary does not have: {', '.join(extra)}")
    document = checklist.get("document")
    if not _nonempty_str(document):
        problem("checklist.document", "missing or empty")
    elif document != CHECKLIST_RELPATH:
        problem("checklist.document", f"names {document!r}, not the pilot's checklist")
    elif repo_root is not None and not (repo_root / CHECKLIST_RELPATH).exists():
        problem("checklist.document", "names a file that is not in the repository")

    copy_digest = copy.get("sha256") if isinstance(copy, dict) else None
    applies_to = checklist.get("applies_to_sha256")
    if not _nonempty_str(applies_to):
        problem("checklist.applies_to_sha256", "missing or empty")
    elif not SHA256_PATTERN.match(applies_to):
        problem("checklist.applies_to_sha256", "is not a 64-hex-digit sha256 digest")
    elif _nonempty_str(copy_digest) and applies_to != copy_digest:
        problem(
            "checklist.applies_to_sha256",
            "is not the digest of the registered copy; the result would apply to another copy",
        )

    result = checklist.get("result")
    if result is None:
        if require_signed:
            problem("checklist.result", "is empty; the owner's signature is what is missing")
        return
    if not isinstance(result, dict):
        problem("checklist.result", "is neither empty nor an object")
        return
    extra = sorted(set(result) - RESULT_KEYS)
    if extra:
        problem(
            "checklist.result", f"holds fields the vocabulary does not have: {', '.join(extra)}"
        )
    if not _is_date(result.get("date")):
        problem("checklist.result.date", "missing, empty, or not a YYYY-MM-DD date")
    if not _nonempty_str(result.get("operator")):
        problem("checklist.result.operator", "missing or empty")
    elif not _is_person(result["operator"]):
        problem("checklist.result.operator", "is not a name the record can hold")
    items = result.get("items")
    if not isinstance(items, dict):
        problem("checklist.result.items", "missing or not an object")
        return
    if repo_root is None:
        return
    checklist_path = repo_root / CHECKLIST_RELPATH
    if not checklist_path.exists():
        return
    expected = signed_item_ids(checklist_path.read_text(encoding="utf-8"))
    missing = [item for item in expected if item not in items]
    unknown = sorted(item for item in items if item not in expected)
    if missing:
        problem("checklist.result.items", f"does not cover {', '.join(missing)}")
    if unknown:
        problem(
            "checklist.result.items",
            f"covers items the checklist does not have: {', '.join(unknown)}",
        )
    for item, value in sorted(items.items()):
        if value not in RESULT_VALUES:
            problem(
                f"checklist.result.items.{item}",
                f"is {value!r}, not one of {', '.join(RESULT_VALUES)}",
            )


def _check_against_copy(copy: Any, copy_path: Path, problem: Any) -> None:
    """Compare the record against the copy's bytes, measured now."""
    if not isinstance(copy, dict):
        problem("copy", "missing or not an object")
        return
    try:
        size, digest = measure_file(copy_path, "copy")
    except RegistrationError as error:
        problem("copy", str(error))
        return
    if copy.get("sha256") != digest:
        problem(
            "copy.sha256",
            f"is {copy.get('sha256')!r} but the copy at {copy_path} hashes to {digest}; "
            f"the registered material is not the material on disk",
        )
    if copy.get("byte_size") != size:
        problem(
            "copy.byte_size",
            f"is {copy.get('byte_size')!r} but the copy at {copy_path} is {size} bytes",
        )


# ---------------------------------------------------------------------------
# The commands
# ---------------------------------------------------------------------------


def _require_material_id(material_id: str) -> None:
    if not MATERIAL_ID_PATTERN.match(material_id):
        raise RegistrationError(
            f"the material id {material_id!r} is not a lowercase id token "
            f"(letters, digits and dashes)"
        )


def _require_person(value: str, what: str) -> None:
    if not _is_person(value):
        raise RegistrationError(f"the {what} {value!r} is not a name the record can hold")


def _require_reference(value: str, what: str) -> None:
    if not REFERENCE_PATTERN.match(value) or ".." in value:
        raise RegistrationError(f"the {what} {value!r} is not a reference the record can hold")


def _require_scope(value: str) -> None:
    if not SCOPE_PATTERN.match(value):
        raise RegistrationError(f"the scope {value!r} is not a scope the record can hold")


def _require_counts(counts: dict[str, int]) -> None:
    for field, value in counts.items():
        if not _is_int(value) or value < 0:
            raise RegistrationError(f"the {field} {value!r} is not a whole number of zero or more")


def command_create(arguments: argparse.Namespace) -> int:
    """Write the registration record, measuring every digest."""
    _require_material_id(arguments.material_id)
    _require_person(arguments.operator, "operator")

    roots = authorised_roots()
    storage_root = arguments.storage_root or roots[0]
    if not _is_authorised_root(storage_root):
        raise RegistrationError(
            f"the storage root {storage_root!r} is not one of the authorised roots "
            f"({', '.join(roots)})"
        )

    copy_path = Path(arguments.copy)
    original_path = Path(arguments.original)
    outline_path = Path(arguments.outline)
    _require_outside_repository(copy_path, "the copy")
    _require_outside_repository(original_path, "the original")
    _require_outside_repository(outline_path, "the heading outline")
    for path, what in (
        (copy_path, "copy"),
        (original_path, "original"),
        (outline_path, "heading outline file"),
    ):
        if not path.exists():
            raise RegistrationError(f"the {what} does not exist: {path}")
        if not path.is_file():
            raise RegistrationError(f"the {what} is not a file: {path}")

    root_path = Path(storage_root)
    relative_path = _relative_to_root(copy_path, root_path)
    if not _is_inside(outline_path, root_path):
        raise RegistrationError(
            f"the heading outline ({outline_path}) is not under the storage root "
            f"{root_path}; the outline holds the copy's headings and belongs to "
            f"the authorised environment"
        )

    repo_root = repository_root()
    grant_record = arguments.grant_record
    _require_reference(grant_record, "authorisation record")
    grant_path = repo_root / grant_record
    if not grant_path.is_file():
        raise RegistrationError(
            f"the authorisation record is not a file in the repository: {grant_record}"
        )
    grant = grant_covering(grants_in(grant_path), relative_path)

    authorisation = {
        "grant_id": grant["grant_id"],
        "record": grant_record,
        "subject_ref": grant["subject_ref"],
        "scope": grant["scope"],
        "granted_by": grant["granted_by"],
        "granted_at": grant["granted_at"],
        "expires_at": grant["expires_at"],
    }
    for field, value in authorisation.items():
        if not _nonempty_str(value):
            raise RegistrationError(f"the authorisation's {field} is missing or empty")
    _require_reference(authorisation["grant_id"], "grant id")
    _require_reference(authorisation["subject_ref"], "subject reference")
    _require_scope(authorisation["scope"])
    _require_person(authorisation["granted_by"], "grantor")

    counts = {
        "page_count": arguments.pages,
        "word_count": arguments.words,
        "figure_count": arguments.figures,
        "table_count": arguments.tables,
        "comment_count": arguments.comments,
        "revision_mark_count": arguments.revision_marks,
    }
    _require_counts(counts)

    heading_count, heading_digest = measure_outline(outline_path)

    record = build_record(
        material_id=arguments.material_id,
        operator=arguments.operator,
        copy_path=copy_path,
        original_path=original_path,
        storage_root=storage_root,
        relative_path=relative_path,
        file_format=arguments.format,
        counts=counts,
        heading_count=heading_count,
        heading_digest=heading_digest,
        authorisation=authorisation,
    )
    _check_format_signature(copy_path, arguments.format)

    out_path = (
        Path(arguments.out)
        if arguments.out
        else repo_root / REGISTRATIONS_SUBDIR / (f"{arguments.material_id}.json")
    )
    if out_path.stem != arguments.material_id:
        raise RegistrationError(
            f"a registration record is named for its material id "
            f"({arguments.material_id}.json), and {out_path.name} is not"
        )
    _validate_out_path(out_path, repo_root)
    if out_path.exists():
        if not arguments.force:
            raise RegistrationError(f"{out_path} already exists; pass --force to replace it")
        _require_no_signature(out_path, arguments.discard_signature)

    write_record(record, out_path)

    problems = check_record(
        record,
        expected_stem=out_path.stem,
        repo_root=repo_root,
        copy_path=copy_path,
    )
    if problems:
        out_path.unlink(missing_ok=True)
        raise RegistrationError(
            "the record the tool wrote does not pass its own check:\n  " + "\n  ".join(problems)
        )

    print(f"wrote {out_path}")
    print(f"material id: {record['material_id']}")
    print(f"copy sha256: {record['copy']['sha256']}")
    print(f"origin sha256: {record['copy']['origin_sha256']}")
    print("the checklist result is empty; the owner's signature is what is missing")
    return 0


def _require_no_signature(out_path: Path, discard: bool) -> None:
    """Refuse to replace a record that carries the owner's signature.

    A signature is the one thing in the record that is the owner's, and a
    tool command that erases it silently is not a deliberate act. The
    record has to be removed by hand for that to happen.
    """
    try:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(existing, dict):
        return
    checklist = existing.get("checklist")
    if not isinstance(checklist, dict) or checklist.get("result") is None:
        return
    if discard:
        return
    raise RegistrationError(
        f"{out_path} carries the owner's signature (D-6); replacing it would "
        f"discard that signature, and a tool command does not do that — remove "
        f"the record yourself if you mean to"
    )


def _validate_out_path(out_path: Path, repo_root: Path) -> None:
    """Refuse to write a record anywhere but the registrations folder."""
    if not _is_inside(out_path, repo_root):
        return
    expected = (repo_root / REGISTRATIONS_SUBDIR).resolve()
    if not _is_inside(out_path, expected):
        raise RegistrationError(
            f"{out_path} is inside the repository but outside "
            f"{REGISTRATIONS_SUBDIR.as_posix()}; a registration record lives in the "
            f"registrations folder and nowhere else"
        )


def _read_record(record_path: Path) -> Any:
    """A record file, read. Anything unreadable is a refusal, not a crash."""
    if not record_path.exists():
        raise RegistrationError(f"the record does not exist: {record_path}")
    try:
        text = record_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RegistrationError(f"the record cannot be read: {record_path} ({error})") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RegistrationError(f"the record is not valid JSON: {error}") from error


def _require_the_registered_copy(record: Any, copy_path: Path) -> None:
    """Refuse a copy that is not the one the record registers.

    The record says where the copy lives. A check that measures some
    other file cannot say whether the material sitting at the registered
    path is the material that was approved -- which is the question the
    import step asks.
    """
    if not isinstance(record, dict):
        return
    registered = _registered_copy_path(record.get("storage"))
    if registered is None:
        raise RegistrationError(
            "the record does not say where its copy lives, so there is nothing "
            "to measure the copy against"
        )
    if not _same_path(copy_path, registered):
        raise RegistrationError(
            f"the copy at {copy_path} is not the copy the record registers "
            f"({registered}); the check is about the material at the registered path"
        )


def command_check(arguments: argparse.Namespace) -> int:
    """Check a record, and with ``--copy`` the copy's bytes."""
    repo_root = repository_root()
    record_path = Path(arguments.record)
    record = _read_record(record_path)

    copy_path = Path(arguments.copy) if arguments.copy else None
    if copy_path is not None:
        _require_the_registered_copy(record, copy_path)

    problems = check_record(
        record,
        expected_stem=record_path.stem,
        repo_root=repo_root,
        copy_path=copy_path,
        require_signed=arguments.require_signed,
    )
    if problems:
        print(f"{record_path}: {len(problems)} problem(s)")
        for entry in problems:
            print(f"  - {entry}")
        return 1
    print(f"{record_path}: the record holds")
    if isinstance(record, dict):
        checklist = record.get("checklist")
        if isinstance(checklist, dict) and checklist.get("result") is None:
            print("the checklist result is empty; the owner's signature is what is missing")
    return 0


def command_sign(arguments: argparse.Namespace) -> int:
    """Fill the checklist result -- the owner's signature."""
    repo_root = repository_root()
    record_path = Path(arguments.record)
    record = _read_record(record_path)
    if not isinstance(record, dict):
        raise RegistrationError("the record is not a JSON object")

    _require_person(arguments.operator, "operator")
    if not _is_date(arguments.date):
        raise RegistrationError(f"the date {arguments.date!r} is not a YYYY-MM-DD date")

    # **The signature is made against the material.** The copy is measured
    # here, not taken on trust from the record: a signature that binds to a
    # digest nobody re-measured is a signature on a memory.
    copy_path = Path(arguments.copy)
    _require_the_registered_copy(record, copy_path)
    problems = check_record(
        record,
        expected_stem=record_path.stem,
        repo_root=repo_root,
        copy_path=copy_path,
    )
    if problems:
        raise RegistrationError(
            "the record does not hold against the material it names:\n  " + "\n  ".join(problems)
        )

    checklist_path = repo_root / CHECKLIST_RELPATH
    if not checklist_path.exists():
        raise RegistrationError(f"the checklist is not in the repository: {CHECKLIST_RELPATH}")
    expected = signed_item_ids(checklist_path.read_text(encoding="utf-8"))

    items_path = Path(arguments.items)
    if not items_path.exists():
        raise RegistrationError(f"the item result file does not exist: {items_path}")
    try:
        items = json.loads(items_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistrationError(f"the item result file cannot be read: {error}") from error
    if not isinstance(items, dict):
        raise RegistrationError("the item result file is not a JSON object of item ids and results")

    missing = [item for item in expected if item not in items]
    unknown = sorted(item for item in items if item not in expected)
    if missing:
        raise RegistrationError(
            f"the item result does not cover {', '.join(missing)}; every item the "
            f"checklist lists has to be marked"
        )
    if unknown:
        raise RegistrationError(
            f"the item result covers items the checklist does not have: {', '.join(unknown)}"
        )
    for item, value in sorted(items.items()):
        if value not in RESULT_VALUES:
            raise RegistrationError(
                f"the result for {item} is {value!r}, not one of {', '.join(RESULT_VALUES)}"
            )

    checklist = record.get("checklist")
    if not isinstance(checklist, dict):
        raise RegistrationError("the record has no checklist section to sign")
    if checklist.get("result") is not None and not arguments.force:
        raise RegistrationError(
            f"{record_path} already carries a checklist result; a signature is "
            f"replaced deliberately, so pass --force to sign it again"
        )
    checklist["result"] = {
        "date": arguments.date,
        "operator": arguments.operator,
        "items": {item: items[item] for item in expected},
    }

    problems = check_record(
        record,
        expected_stem=record_path.stem,
        repo_root=repo_root,
        require_signed=True,
    )
    if problems:
        raise RegistrationError(
            "the signed record does not pass the check:\n  " + "\n  ".join(problems)
        )

    write_record(record, record_path)
    print(f"signed {record_path}")
    print(f"the result applies to {checklist.get('applies_to_sha256')}")
    return 0


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The command line this tool answers to."""
    parser = argparse.ArgumentParser(
        prog="pilot_material_registration",
        description="Register the pilot's desensitised copy: measure, write, check.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create", help="write the registration record")
    create.add_argument("--material-id", required=True, help="the pilot's stable id for the copy")
    create.add_argument(
        "--copy", required=True, help="the desensitised copy, in the authorised environment"
    )
    create.add_argument("--original", required=True, help="the original the copy was derived from")
    create.add_argument(
        "--outline", required=True, help="the heading outline exported from the copy"
    )
    create.add_argument(
        "--storage-root", default=None, help="the authorised root the copy lives in"
    )
    create.add_argument("--format", required=True, help="the copy's file format, e.g. docx")
    create.add_argument("--pages", type=int, required=True, help="the copy's page count")
    create.add_argument("--words", type=int, required=True, help="the copy's word count")
    create.add_argument("--figures", type=int, required=True, help="the copy's figure count")
    create.add_argument("--tables", type=int, required=True, help="the copy's table count")
    create.add_argument("--comments", type=int, required=True, help="the copy's comment count")
    create.add_argument(
        "--revision-marks", type=int, required=True, help="the copy's revision-mark count"
    )
    create.add_argument("--operator", required=True, help="who is registering the copy")
    create.add_argument(
        "--grant-record",
        required=True,
        help="the authorisation record in the repository that carries the grant",
    )
    create.add_argument("--out", default=None, help="where to write the record")
    create.add_argument("--force", action="store_true", help="replace a record that already exists")
    create.add_argument(
        "--discard-signature",
        action="store_true",
        help="replace a record that carries the owner's signature, discarding it",
    )
    create.set_defaults(handler=command_create)

    check = subcommands.add_parser("check", help="check a record, and with --copy its material")
    check.add_argument("record", help="the registration record to check")
    check.add_argument("--copy", default=None, help="the copy to measure the record against")
    check.add_argument(
        "--require-signed",
        action="store_true",
        help="fail when the checklist result is empty",
    )
    check.set_defaults(handler=command_check)

    sign = subcommands.add_parser("sign", help="fill the checklist result -- the owner's signature")
    sign.add_argument("record", help="the registration record to sign")
    sign.add_argument(
        "--copy",
        required=True,
        help="the copy the signature is made against; it is measured, not trusted",
    )
    sign.add_argument("--operator", required=True, help="who signs")
    sign.add_argument("--date", required=True, help="the date of the signature, YYYY-MM-DD")
    sign.add_argument(
        "--items", required=True, help="a JSON file of item ids and pass/fail results"
    )
    sign.add_argument(
        "--force",
        action="store_true",
        help="sign a record that already carries a result",
    )
    sign.set_defaults(handler=command_sign)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """The tool's entry point.  Returns the exit code."""
    parser = build_parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    handler = arguments.handler
    try:
        return int(handler(arguments))
    except RegistrationError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
