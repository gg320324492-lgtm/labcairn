"""LC-P2-18's task package: one corpus, byte-identical on both sides.

**What this module builds, and why a package exists at all.** The brief
(``docs/plans/LC-P2-18-competitor-baseline-brief.md`` §3) requires the two
sides of the comparison to run the same tasks, and the honest form of "the
same tasks" is not two pointers into this repository's test tree — the
competitor side has no checkout of this repository and should not pretend
to read one. So the inputs are **packaged**: one output directory holding
every task file both sides consume, written once, hashed in a manifest,
and handed to each side as plain files. A side that ran the same tasks
ran the same bytes; the manifest is what lets an aligner check that claim
later instead of trusting it.

**What is in the package.** The three task faces the frozen baseline
carries numbers for (brief §1):

* ``numeric-extraction`` — the eleven corpus fixtures of
  :data:`~tests.evaluation.corpus.CORPUS_FIXTURES`, copied byte for byte
  from ``tests/fixtures/analysis/``, each beside its committed answer key
  and the question text the adapter's template builds from that key.
* ``unsupported-claim-detection`` — the public corpus's ``no_evidence``
  fixture: its two material files, the question whose honest answer is an
  abstention, and the question's own key extracted verbatim from
  ``tests/fixtures/public/MANIFEST.json``.
* ``recovery-correctness`` — the four crash windows of
  :class:`labcairn.recovery.contracts.CrashPoint`, each written as a task
  statement (a fault at this boundary, and what recovery must make true)
  beside the invariant the specification requires. These four describe a
  capability face a document-QA system has no surface for; the brief
  rules (§1) that a competitor's zero there is a fact about the
  competitor's scope, reported as such. The package carries the task
  statements so the matched-task claim is about bytes, not about goodwill.

**What the package deliberately does not contain.** No scoring code, no
side's answers, no model declaration — a package is the *tasks*, and the
same package feeds our side's run, the competitor's run, and the aligner.
Nothing here calls a provider and nothing here scores an answer; the
``recovery-correctness`` keys state invariants, not numbers.

**Where the package goes.** Outside the repository — the runner input is
runtime state, not a tree artifact. :func:`build_package` refuses an
output directory inside the repository for the same reason the test
suite's ``--basetemp`` is kept outside: a run's scratch must not be able
to contaminate the tree it measures. The path is always the caller's;
nothing here hardcodes one.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from analysis_fixtures import build_spreadsheet_fixtures, expected_path

from .corpus import CORPUS_FIXTURES
from .paperqa_adapter import question_for
from .public_corpus import MANIFEST_NAME, PUBLIC_CORPUS_DIR

__all__ = [
    "PACKAGE_SCHEMA",
    "RECOVERY_CASES",
    "TASK_FACES",
    "PackageBuildError",
    "PackageInvalidError",
    "PackageOutputInsideRepositoryError",
    "build_package",
    "find_repository_root",
    "package_manifest_sha256",
    "validate_package",
]

#: The package manifest's schema tag. A reader refuses a manifest that does
#: not declare it, the same way the public corpus's reader does.
PACKAGE_SCHEMA: Final = "labcairn.competitor-task-package/1"

#: The three task faces, in the order the brief's §1 names them. The order
#: is the package's own order everywhere: call plan, alignment report,
#: record.
TASK_FACES: Final[tuple[str, ...]] = (
    "numeric-extraction",
    "unsupported-claim-detection",
    "recovery-correctness",
)

#: The recovery task's four cases. Each entry is (crash point, the window's
#: task statement, the invariant recovery must make true, the ADR rows the
#: statement compresses). The statements are written from
#: ``labcairn.recovery.contracts.CrashPoint``'s own member docs and
#: ADR-0003 C2 — the specification, not a paraphrase of a test.
RECOVERY_CASES: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "before_attempted_commit",
        "A crash fires before the operation_attempted record commits: the "
        "operation was never attempted, so nothing about it is durable.",
        "recovery finds nothing to reconcile — no intent, event or effect "
        "from the crashed operation exists after restart",
        "ADR-0003 C2 row 1 / AT-1",
    ),
    (
        "after_attempted_before_write",
        "A crash fires after the operation_attempted record commits but "
        "before the side effect runs: the intent is durable and the effect "
        "did not happen.",
        "recovery replays the operation exactly once",
        "ADR-0003 C2 row 2 / AT-5",
    ),
    (
        "after_write_before_confirm",
        "A crash fires after the side effect ran but before the "
        "operation_confirmed record commits: the intent is durable, the "
        "receipt is not, and the effect's bytes are on disk.",
        "recovery treats the state as uncertain and reconciles against the "
        "world before replaying, so the effect is never applied twice",
        "ADR-0003 C2 row 2 / AT-2, AT-4",
    ),
    (
        "after_confirm_before_notify",
        "A crash fires after the operation_confirmed record commits but "
        "before the client is told: nothing about the operation is "
        "uncertain and nothing must be re-run.",
        "recovery delivers the lost notification without re-executing the operation",
        "ADR-0003 C2 row 3 / AT-3",
    ),
)


class PackageBuildError(RuntimeError):
    """The package could not be built from the tree it was asked to read."""


class PackageOutputInsideRepositoryError(PackageBuildError):
    """The requested output directory sits inside the repository."""


class PackageInvalidError(RuntimeError):
    """A package directory does not match its own manifest.

    A runner or an aligner that consumed a package whose bytes do not
    match the manifest's hashes would be scoring one corpus while claiming
    another, so validation refuses rather than proceeding.
    """

    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def find_repository_root(start: Path) -> Path:
    """The repository root containing *start*, by its own git metadata."""
    start = start if start.is_dir() else start.parent
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PackageBuildError(
            f"cannot locate a repository root above {start}: {result.stderr.strip()}"
        )
    return Path(result.stdout.strip())


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(path: Path, payload: Any) -> None:
    _write_bytes(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())


def _public_question(
    manifest: Mapping[str, Any], fixture_id: str, question_id: str
) -> dict[str, Any]:
    """One question's full definition, extracted from the public manifest."""
    for fixture in manifest["fixtures"]:
        if fixture["id"] == fixture_id:
            for question in fixture["questions"]:
                if question["id"] == question_id:
                    return dict(question)
    raise PackageBuildError(f"{question_id} not found in the public fixture manifest")


def _recovery_task_files() -> dict[str, dict[str, Any]]:
    """The recovery face's scenario statements and keys, keyed by file name."""
    scenarios: dict[str, dict[str, Any]] = {}
    for point, statement, invariant, rows in RECOVERY_CASES:
        scenarios[f"recovery-correctness/scenarios/{point}.json"] = {
            "case": point,
            "task": statement,
            "adr_rows": rows,
        }
        scenarios[f"recovery-correctness/answer-keys/{point}.json"] = {
            "case": point,
            "expected": invariant,
            "adr_rows": rows,
        }
    return scenarios


#: The core-properties timestamps a generated spreadsheet carries inside:
#: ``created`` and ``modified``, whose values are the generation moment.
_CORE_TIMESTAMP: Final = re.compile(rb"<dcterms:(created|modified)([^>]*)>[^<]*</dcterms:\1>")


def _deterministic_zip(data: bytes) -> bytes:
    """Rebuild a zip archive with every timestamp pinned, so bytes are stable.

    The spreadsheets are generated, not committed — ``openpyxl`` stamps
    each archive entry with the current time *and* writes the generation
    moment into the document properties inside, so two generations of the
    "same" file differ in bytes and any hash recorded of them moves. The
    package's manifest pins bytes, so a generated spreadsheet is rebuilt
    here with a fixed entry timestamp and a fixed core-properties
    timestamp, its entries in their original order and otherwise
    untouched: the cells are the cells it generated, only the unstated
    stamping is pinned.
    """
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename.endswith("docProps/core.xml"):
                payload = _CORE_TIMESTAMP.sub(
                    rb"<dcterms:\1\2>2000-01-01T00:00:00Z</dcterms:\1>", payload
                )
            entry = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = info.external_attr
            target.writestr(entry, payload)
    return buffer.getvalue()


def build_package(out_dir: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Assemble the two-side task package at *out_dir* and return its manifest.

    Every file is written from the tree's own fixtures — nothing is
    generated on the way except the question texts (the adapter's template,
    applied to the committed keys) and the recovery statements (written
    from the crash contract). The manifest records every file's SHA-256 and
    the tree path each one came from, so the package can be audited back
    into the tree it was built from.
    """
    resolved_out = out_dir.resolve()
    if repo_root is None:
        repo_root = find_repository_root(Path(__file__).resolve())
    repo_root = repo_root.resolve()
    if resolved_out == repo_root or repo_root in resolved_out.parents:
        raise PackageOutputInsideRepositoryError(
            f"{resolved_out} is inside the repository at {repo_root}; a "
            "runner input directory must live outside it"
        )

    files: dict[str, str] = {}
    sources: dict[str, str] = {}

    def put(relpath: str, payload: bytes, source: str) -> None:
        _write_bytes(resolved_out / "tasks" / relpath, payload)
        # The manifest keys the payload's task-relative path, so the hash
        # map is stable if a task's files are ever rehomed.
        files[relpath] = hashlib.sha256(payload).hexdigest()
        sources[relpath] = source

    # -- numeric extraction: fixtures, keys, questions -----------------------
    spreadsheets = build_spreadsheet_fixtures()
    for fixture in CORPUS_FIXTURES:
        source = expected_path(fixture)
        key = source.read_bytes()
        put(f"numeric-extraction/answer-keys/{fixture}.expected.json", key, str(source))
        key_data = json.loads(key)
        put(
            f"numeric-extraction/questions/{fixture}.question.txt",
            question_for(key_data).encode(),
            f"question_for({source.name})",
        )
        if fixture in spreadsheets:
            put(
                f"numeric-extraction/fixtures/{fixture}",
                _deterministic_zip(spreadsheets[fixture]),
                f"analysis_fixtures.build_spreadsheet_fixtures()['{fixture}'], "
                "repacked with pinned timestamps so its bytes are stable",
            )
        else:
            fixture_file = source.with_name(fixture)
            put(
                f"numeric-extraction/fixtures/{fixture}",
                fixture_file.read_bytes(),
                str(fixture_file),
            )

    # -- unsupported claim detection: material, key, question ----------------
    manifest_path = repo_root / PUBLIC_CORPUS_DIR / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_bytes())
    no_evidence = _public_question(manifest, "no_evidence", "no_evidence.buffer_ph")
    for entry in next(
        fixture["material"] for fixture in manifest["fixtures"] if fixture["id"] == "no_evidence"
    ):
        material_file = manifest_path.parent / entry["path"]
        put(
            f"unsupported-claim-detection/material/{Path(entry['path']).name}",
            material_file.read_bytes(),
            str(material_file),
        )
    key_payload = {
        "question_id": no_evidence["id"],
        "prompt": no_evidence["prompt"],
        "answer": no_evidence["answer"],
        "expected_artifact_checks": no_evidence["expected_artifact_checks"],
    }
    key_bytes = (json.dumps(key_payload, indent=2, sort_keys=True) + "\n").encode()
    put(
        "unsupported-claim-detection/answer-keys/no_evidence.buffer_ph.json",
        key_bytes,
        f"questions[no_evidence.buffer_ph] of {manifest_path}",
    )
    put(
        "unsupported-claim-detection/questions/no_evidence.buffer_ph.question.txt",
        no_evidence["prompt"].encode(),
        "the public manifest's own prompt text",
    )

    # -- recovery correctness: scenario statements and invariant keys --------
    for relpath, payload in _recovery_task_files().items():
        put(relpath, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(), relpath)

    task_counts = {
        face: sum(1 for relpath in files if relpath.startswith(f"{face}/")) for face in TASK_FACES
    }
    manifest_document = {
        "schema": PACKAGE_SCHEMA,
        "tasks": [{"face": face, "file_count": task_counts[face]} for face in TASK_FACES],
        "files": dict(sorted(files.items())),
        "sources": dict(sorted(sources.items())),
    }
    _write_json(resolved_out / "manifest.json", manifest_document)
    return manifest_document


def read_manifest(package_dir: Path) -> dict[str, Any]:
    """The package's manifest, with the schema tag checked."""
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise PackageInvalidError((f"no manifest at {manifest_path}",))
    document: dict[str, Any] = json.loads(manifest_path.read_bytes())
    if document.get("schema") != PACKAGE_SCHEMA:
        raise PackageInvalidError(
            (
                f"manifest at {manifest_path} declares schema {document.get('schema')!r}, "
                f"not {PACKAGE_SCHEMA!r}",
            )
        )
    return document


def package_manifest_sha256(package_dir: Path) -> str:
    """The manifest file's own SHA-256 — a package's identity for a run record.

    Every side's run record and the aligner's output carry it, so a
    comparison can be checked to have happened over one corpus: the same
    manifest bytes, not merely the same file name.
    """
    return _hash_file(package_dir / "manifest.json")


def task_case_files(package_dir: Path, face: str) -> dict[str, str]:
    """The *face*'s case file hashes: task file to SHA-256, from the manifest.

    A face's **cases** are its answer keys — one per case the side must
    produce an artifact for. The other files (fixtures, material,
    questions, scenarios) are a case's inputs, not cases of their own.
    """
    manifest = read_manifest(package_dir)
    return {
        relpath: digest
        for relpath, digest in manifest["files"].items()
        if relpath.startswith(f"{face}/answer-keys/")
    }


def validate_package(package_dir: Path) -> None:
    """Check a package directory against its own manifest, or refuse.

    Every file named in the manifest must be present with the exact bytes
    the manifest hashes, and nothing may sit in ``tasks/`` that the
    manifest does not name — a file the manifest does not know about is a
    file no side's run can be held to.
    """
    manifest = read_manifest(package_dir)
    reasons: list[str] = []
    tasks_dir = package_dir / "tasks"
    if not tasks_dir.is_dir():
        reasons.append(f"no tasks/ directory under {package_dir}")
    for relpath, digest in sorted(manifest["files"].items()):
        path = tasks_dir / relpath
        if not path.is_file():
            reasons.append(f"missing task file {relpath}")
            continue
        actual = _hash_file(path)
        if actual != digest:
            reasons.append(f"task file {relpath} hashes to {actual}, not the manifest's {digest}")
    declared = {f"tasks/{relpath}" for relpath in manifest["files"]}
    if tasks_dir.is_dir():
        for path in sorted(tasks_dir.rglob("*")):
            if path.is_file():
                relative = path.relative_to(package_dir).as_posix()
                if relative not in declared:
                    reasons.append(f"undeclared file in package: {relative}")
    faces_present = {face for face in TASK_FACES if task_case_files(package_dir, face)}
    if faces_present != set(TASK_FACES):
        missing = sorted(set(TASK_FACES) - faces_present)
        reasons.append(f"task faces missing from the manifest: {missing}")
    if reasons:
        raise PackageInvalidError(tuple(reasons))


def copy_package(package_dir: Path, target: Path) -> None:
    """Hand a side its byte-identical copy of the package.

    Both sides receive a **copy**, never the original directory: a runner
    that wrote its artifacts beside the master package would entangle the
    two sides' outputs. :func:`shutil.copytree` without symlinks, so the
    copy is plain files either side can read.
    """
    shutil.copytree(package_dir, target, symlinks=False, dirs_exist_ok=False)


@dataclass(frozen=True, slots=True)
class PackageSummary:
    """What building or validating a package reports back to a caller."""

    #: The package's root directory.
    root: Path
    #: Files per task face, in :data:`TASK_FACES` order.
    case_counts: dict[str, int]
    #: The manifest's own SHA-256, the package's identity for a run record.
    manifest_sha256: str


def summarize(package_dir: Path) -> PackageSummary:
    """Counts and identity for a package that has already been validated."""
    read_manifest(package_dir)
    counts = {face: len(task_case_files(package_dir, face)) for face in TASK_FACES}
    return PackageSummary(
        root=package_dir,
        case_counts=counts,
        manifest_sha256=_hash_file(package_dir / "manifest.json"),
    )
