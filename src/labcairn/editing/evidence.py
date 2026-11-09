"""The evidence this ticket produces, and the copy that carries it there.

**What this module is for.** §5.7 item 4 asks for the substitute-set round trip
*measured*; §5.5 gives this window a dated evidence record; and the reopen
checklist — §4.9, an instrument `LC-P3-01` owns — consumes **this ticket's
output files**. A measurement that lives only inside a test run cannot be
handed to a person to open in WPS, so the artifacts have to exist on disk
outside the repository, with hashes and short paths, and the tree has to cite
them by row id rather than carry them.

**The independent copy is temporary, and this module says so in its own name.**
§5.6 is explicit: the independent-copy guarantee the edit loop assumes is
`LC-P3-03`'s deliverable, and *"an experiment's shortcut that is not labelled
is how a temporary thing becomes a product mechanism"*. What is here is a copy
of a manuscript's bytes into a directory the caller names, so the manuscript
that was read is never the file that is written. `ADR-0021` carries the same
word, and nothing in this module pretends to be the receipt loop.

**The write seam is not touched, and this is where that shows.** The product
writes files in one place, :mod:`labcairn.workspace.outputs`, and the
path-length question around its atomic temporary is §7's batch item. This
module writes **evidence**, at a path the operator supplies, and it refuses
when the visible path crosses the ceiling this machine enforces
(:data:`MAX_PATH`, measured live 2026-11-08 with ``LongPathsEnabled = 0``)
rather than discovering it from a `FileNotFoundError` in the middle of a run.

**Where the bytes are written, and why not here.** Every function in this
module is pure over paths and strings: :func:`visible_path` measures a path
and refuses it, :func:`checklist_rows` builds rows, :func:`host_snapshot`
states what was read from a version resource. The act of writing them
belongs to ``tests/evaluation_docx_edit_fidelity.py``, because
``THREAT-MODEL`` §1.2 enumerates every write primitive under
``src/labcairn/`` and this ticket does not own that document — an experiment
that added a second writer to the product tree would either redden that
witness or quietly widen it, and both are the wrong outcome for a G1 run.

**Host judgement lives here as empty cells, not as prose.** A reopen row is
filled by a person looking at a screen; §2 item 2 forbids automating that. So
every row written here carries the machine-side columns complete — artifact,
hash, byte size, path length, expected presence list — and the human columns
deliberately empty, with the verdict ``PENDING-HUMAN``. §5.10 says a row left
empty because nothing checks it will be filled is the same defect as a witness
deleted in a merge, which is why the emptiness is a value in the schema
rather than an absent field.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from labcairn.editing.survey import StructureClass

__all__ = [
    "HOSTS",
    "MAX_PATH",
    "PRESENCE_BY_CLASS",
    "ROW_COLUMNS",
    "PathBudgetError",
    "ReopenRow",
    "artifact_name",
    "host_snapshot",
    "ticket_id",
    "visible_path",
]

#: The longest visible path this machine accepts. Measured live 2026-11-08:
#: the registry key ``HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem``
#: carries ``LongPathsEnabled = 0``; a path of 259 characters was created and
#: a path of 260 was refused with ``FileNotFoundError``. §7 decides what the
#: *product* does about it; this constant is what the evidence writer does
#: about it in the meantime, and the record of the difference is the ADR's
#: §"what this does not decide".
MAX_PATH: Final[int] = 259

#: The columns a reopen row carries, in the order the checklist prints them.
#: **The human columns are in the list** so a row that has not been performed
#: is distinguishable from a row someone forgot to write.
ROW_COLUMNS: Final[tuple[str, ...]] = (
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

#: What the person is asked to look for, in the words a row can carry.
PRESENCE_BY_CLASS: Final[Mapping[StructureClass, str]] = {
    StructureClass.BODY_TEXT: "body-text",
    StructureClass.COMMENTS: "comments",
    StructureClass.COMMENT_PART: "comment-bodies",
    StructureClass.TRACKED_REVISIONS: "tracked-revisions",
    StructureClass.TABLES: "tables",
    StructureClass.EQUATIONS: "equations",
    StructureClass.IMAGES: "images",
    StructureClass.TEXT_BOXES: "text-boxes",
    StructureClass.FIELDS: "fields",
    StructureClass.CONTENT_CONTROLS: "content-controls",
    StructureClass.HYPERLINKS: "hyperlinks",
    StructureClass.MEDIA: "media-parts",
}

#: The hosts, in the roles §4.9 gives them. **No executable path is recorded
#: here**: a path through a user profile is an owner-side path, and §3 rule 8
#: keeps those out of a new file in the tree. The operator's own copy of the
#: checklist carries the paths, because the operator is the one launching.
HOSTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("primary", "WPS Office", "12.1.0.29690"),
    ("reference", "Microsoft Office 2010", "14.0.7252.5000"),
)


class PathBudgetError(Exception):
    """The visible path would cross the ceiling this machine enforces."""


def visible_path(directory: Path, name: str) -> Path:
    """The path a host would show, with the budget checked before anything is written."""
    path = directory / name
    text = str(path.absolute())
    if len(text) > MAX_PATH:
        raise PathBudgetError(
            f"{name} would sit at {len(text)} characters, over the {MAX_PATH}-character "
            "ceiling this machine enforces; shorten the evidence root or the sample id"
        )
    return path


def artifact_name(sample: str, option: str, form: str) -> str:
    """A short, stable file name for one artifact.

    **Short on purpose.** §7's wall is crossed by depth and by names, and a
    long name is the half an experiment controls. The name is the artifact,
    not a sentence about it: ``07-everything-at-once-surgical-marked.docx``.
    """
    return f"{sample}-{option}-{form}.docx"


@dataclass(frozen=True)
class ReopenRow:
    """One (artifact x host) judgement, half of it waiting for a person."""

    values: Mapping[str, str]

    def as_csv(self) -> str:
        return ",".join(
            json.dumps(self.values.get(column, ""), ensure_ascii=False) for column in ROW_COLUMNS
        )


def _long_paths_enabled() -> str:
    """Read the registry value this machine's path ceiling depends on.

    **The value is read, not remembered.** The 259-character ceiling is only a
    fact about a machine whose ``LongPathsEnabled`` value is ``0``; a record
    that prints the literal would keep saying so after the setting changed.
    On a host where the value cannot be read, the snapshot says so rather than
    inventing a zero.
    """
    if _this_platform_is_not_windows():
        return "unknown"
    return _long_paths_enabled_windows()


def _this_platform_is_not_windows() -> bool:
    """Whether this host is not Windows, asked through a call.

    **Compared through a function so no checker narrows it away.** A checker
    running on Linux constant-folds ``sys.platform`` and judges the Windows
    half of this module unreachable; routing the question through a call
    keeps the runtime behaviour identical while every platform's checker
    sees the same reachable body.
    """
    return sys.platform != "win32"


def _long_paths_enabled_windows() -> str:
    """The Windows-only half of :func:`_long_paths_enabled`.

    **Split out so every platform's type checker sees the same function.**
    ``winreg`` exists on Windows only: a checker running elsewhere reports the
    import unreachable and the module's attributes missing, which are false
    positives about the platform split, not about the reading. The runtime
    guard in the caller is the real protection; each use site carries the
    scoped ignore the project's convention asks for.
    """
    try:
        import winreg  # type: ignore[import-unreachable,unused-ignore]
    except ImportError:  # pragma: no cover - Windows always ships winreg
        return "unknown"
    try:
        with winreg.OpenKey(  # type: ignore[attr-defined,unused-ignore]
            winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined,unused-ignore]
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")  # type: ignore[attr-defined,unused-ignore]
    except OSError:
        return "unknown"
    return str(int(value))


def host_snapshot(measured_at: str, head: str) -> dict[str, str]:
    """The hosts as measured, with no host started.

    **A version read from a file's own resource, never from a running
    program.** The owner's decision of 2026-11-08 removes COM and ProgID
    automation from the options, and §2 item 2 says registering an automation
    surface is not permission to use it. These rows are the *input* to §4.9's
    checklist, which a person performs; they state what the machine could see
    about the installed hosts and nothing about what a host did with a file.
    """
    return {
        "measured_at": measured_at,
        "head": head,
        "long_paths_enabled": _long_paths_enabled(),
        "primary_host": HOSTS[0][1],
        "primary_version": HOSTS[0][2],
        "reference_host": HOSTS[1][1],
        "reference_version": HOSTS[1][2],
    }


def ticket_id() -> str:
    """The ticket the evidence belongs to, so a file name says it without a sentence."""
    return "LC-P3-02"
