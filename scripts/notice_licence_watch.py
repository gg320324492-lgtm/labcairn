"""The python closure's licence record, read against the closure itself.

**Why this file exists.** NOTICE §2.2 records the dependency closure as five
figures -- 171 requirement lines, 167 on Linux, 165 on macOS, 168 on Windows, a
union of 170 -- and a sixteen-row licence census. NOTICE §2.3 names four
dependencies whose *bundled* third-party material carries terms of its own, each by
the licence file's path inside its installed distribution. Nothing watched either.
The release gate reads each installed distribution's licence to decide whether a
release may ship, and `tests/test_release_workflow.py` watches the gate's font list
against the audit's font names; no test compares §2.2's figures or §2.3's paths with
what the closure actually is.

**What the physical sources are.**

  * `uv export --frozen --no-dev` over `uv.lock`, whose requirement lines carry each
    package's PEP 508 marker. The five figures are a computation over those markers
    against three platform environments, not a number to be remembered. Measured on
    this tree at `6cd8446`: 171 rows, 168 true on Windows, 165 on macOS, 167 on
    Linux, union 170, and exactly one package installing on none of the three with
    the marker `sys_platform == 'emscripten'`. Those are §2.2's five figures,
    computed from the lock.
  * The installed distributions. The release gate's licence audit -- embedded in
    `.github/workflows/release.yml` as a Python heredoc -- already normalises a
    distribution's licence into a label through `License-Expression`, then a short
    legacy `License` field tokenised by SPDX token, then License classifiers, then a
    licence-file text rule. This file extracts *that* function from the workflow text
    and applies it: a second copy of the labelling is a second thing that can drift,
    and the two disagreeing looks like a licence change.
  * The files §2.3 names, opened inside the installed distribution that holds them.

**How a claim is separated from its evidence.** §2.3's licence-file claims are taken
from §2.3's own words -- the phrase it places before each path it names -- and each
phrase is looked for in the file that path points at. The claim and the evidence are
therefore two different statements, which is what makes a disagreement a finding
rather than a restatement.

**Where a limit is stated rather than hidden.** Three packages' markers are false on
the machine running this -- `jeepney` and `secretstorage` on Linux, `httpx2-jsfetch`
on emscripten -- so no distribution of theirs is installed here and their terms
cannot be read from an artefact. `census_problems` compares §2.2's rows with the
labels the installed distributions carry *and requires the remaining deficit to be
exactly that foreign set*: a wrong count, a wrong label or a package that left the
closure while §2.2 kept its row all redden it, with no network involved. Reading the
foreign packages' own terms is `published_census_problems`, exercised on fixtures and
run for real by the release gate.
"""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
NOTICE_PATH: Final[Path] = REPO_ROOT / "NOTICE"
RELEASE_WORKFLOW: Final[Path] = REPO_ROOT / ".github" / "workflows" / "release.yml"

#: The three platform environments §2.2's per-platform counts are taken over. Only
#: the fields `packaging.markers` and the lock's own markers actually use are given:
#: a marker reading a field this table omits raises rather than silently evaluating
#: false, which is how a wrong count would otherwise arrive.
PLATFORM_ENVIRONMENTS: Final[dict[str, dict[str, str]]] = {
    "windows": {
        "sys_platform": "win32",
        "os_name": "nt",
        "platform_system": "Windows",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "platform_release": "10",
        "platform_version": "10.0.0",
        "python_version": "3.12",
        "python_full_version": "3.12.10",
    },
    "macos": {
        "sys_platform": "darwin",
        "os_name": "posix",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "platform_release": "24.0.0",
        "platform_version": "24.0.0",
        "python_version": "3.12",
        "python_full_version": "3.12.10",
    },
    "linux": {
        "sys_platform": "linux",
        "os_name": "posix",
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "platform_release": "6.8.0",
        "platform_version": "#1 SMP",
        "python_version": "3.12",
        "python_full_version": "3.12.10",
    },
}

#: A §2.2 census row. The counts are right-aligned -- `74`, `46`, `29` sit under two
#: spaces and every one-digit count under three -- so a pattern that required exactly
#: two leading spaces read three rows out of sixteen and reported the total as 149.
#: MULTILINE is not optional: without `^` matching at line starts the pattern can
#: only ever match the section's final line, which is how a first version found 3
#: rows and a total of 149.
_CENSUS_ROW: Final[re.Pattern[str]] = re.compile(r"^ +(\d+) {2,}(\S.*\S?)$", re.M)

#: One §2.3 bullet: `  * MPL-2.0 — certifi (MPL-2.0) and tqdm …`.
_BUNDLED_BULLET: Final[re.Pattern[str]] = re.compile(r"^ {2}\* (.*)$", re.M)

#: A distribution-relative licence path as §2.3 states it, e.g.
#: `pywin32-312.dist-info/licenses/adodbapi/license.txt`.
_DIST_INFO_PATH: Final[re.Pattern[str]] = re.compile(
    r"\b([A-Za-z0-9_.-]+\.dist-info(?:/[A-Za-z0-9_.+-]+)+)\b"
)

#: What a phrase in §2.3's prose commits the file it precedes to. Written as a
#: vocabulary of *licence names* rather than of any noun in the sentence: §2.3 says
#: "an LGPL notice for the bundled adodbapi module (`…/adodbapi/license.txt`)", and
#: `adodbapi` there names the module, not a term the file states -- the file is the
#: LGPL text and says nothing about adodbapi. A claim read from a module name turns a
#: correct record into a failure, which is the shape of a witness that fails for a
#: reason unrelated to the property.
_CLAIM_VOCABULARY: Final[dict[str, tuple[str, ...]]] = {
    "lgpl": ("GNU LESSER GENERAL PUBLIC LICENSE",),
    "gpl": ("GNU GENERAL PUBLIC LICENSE",),
    "mpl": ("Mozilla Public License",),
    "scintilla": ("Scintilla",),
    "freetype": ("FREETYPE",),
    "brotli": ("brotli",),
    "zlib": ("zlib",),
    "openblas": ("OpenBLAS",),
    "gcc runtime library exception": ("GCC-exception", "GCC Runtime Library Exception"),
    "gcc-exception": ("GCC-exception",),
    "psf": ("PYTHON SOFTWARE FOUNDATION LICENSE",),
}

#: A §2.3 package-and-terms pair as the section writes it: `certifi (MPL-2.0)` and
#: `tqdm (MPL-2.0 AND MIT, so MIT is available as well)`. The name is what precedes
#: the parenthesised licence expression, and the first thing inside the parentheses
#: has to be a licence identifier -- which is what keeps §2.3's other parenthesised
#: use, a licence file's path (`its licence file (numpy-2.5.4.dist-info/…)`), from
#: being read as a package called `file`.
#:
#: The tail of the parenthesised expression is `[^()]*`, not a character class that
#: includes the parentheses themselves. A class containing `(` and `)` let the first
#: match run on through `) and tqdm (` and swallow the second package whole: the
#: pattern found `certifi` and reported nothing for `tqdm`, which read as §2.3 having
#: never recorded a condition the release gate allows tqdm under.
_PACKAGE_TERMS: Final[re.Pattern[str]] = re.compile(
    r"\b([a-z][a-z0-9_.-]{2,})\s*\(\s*"
    r"(MPL-\d[\d.]*|LGPL(?:-\d[\d.]*)?(?:-or-later)?|GPL-\d[\d.]+(?:-or-later)?|MIT|Apache-\d[\d.]*|BSD-\d-Clause|PSF-\d[\d.]*)"
    r"[^()]*\)",
    re.I,
)

#: A licence token inside a §2.3 parenthesised expression: `MPL-2.0`, `MIT`,
#: `GPL-3.0-or-later`, `LGPL`.
_LICENCE_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"\b(MPL-\d[\d.]*|LGPL(?:-\d[\d.]+(?:-or-later)?)?|GPL-\d[\d.]+(?:-or-later)?|MIT|Apache-\d[\d.]*|BSD-\d-Clause|PSF-\d[\d.]*)\b"
)

#: A §2.3 bullet that opens with a package and the version it describes: `numpy
#: 2.5.4 — its licence file …`, `pywin32 312 — Windows-only.`. Applied to the bullet's
#: first line with the `* ` marker removed, and anchored: the unanchored form matched
#: `…to offer that file's source under MPL 2.0` inside the certifi bullet and produced
#: a package called `MPL` at version `2.0`.
_LEADING_PACKAGE_VERSION: Final[re.Pattern[str]] = re.compile(
    r"^([A-Za-z][A-Za-z0-9_.-]*) (\d[\w.-]*)\b"
)


@dataclass(frozen=True)
class RequirementRow:
    """One requirement the export names, with the marker the lock recorded."""

    name: str
    version: str
    marker: str | None

    @property
    def key(self) -> str:
        return f"{self.name.lower().replace('_', '-')}=={self.version}"


@dataclass
class ClosureRead:
    """The closure as the export and its markers state it.

    `distinct_rows` and `platform_union` are different numbers and §2.2 states both.
    The export resolves 171 `name==version` lines; the union of what the three
    supported platforms install is 170, because one distribution's marker is
    `sys_platform == 'emscripten'` and installs on none of them. Reading §2.2's
    "union is 170" as the export's line count is the mistake this separation exists
    to prevent.
    """

    rows: list[RequirementRow] = field(default_factory=list)
    distinct_rows: list[RequirementRow] = field(default_factory=list)
    per_platform: dict[str, list[RequirementRow]] = field(default_factory=dict)
    platform_union: list[RequirementRow] = field(default_factory=list)
    on_no_platform: list[RequirementRow] = field(default_factory=list)


@dataclass(frozen=True)
class PathClaim:
    """One §2.3 path, with the phrases §2.3's prose claims it carries."""

    path: str
    claims: tuple[str, ...]


@dataclass(frozen=True)
class BundledEntry:
    """One §2.3 entry: the package version it names, and the paths with their claims.

    `text` is the bullet as printed and `folded` is the same text with its line
    continuations joined. Claims are read from `text`, package-and-terms pairs from
    `folded`, because §2.3 wraps mid-expression:

        * MPL-2.0 — certifi (MPL-2.0) and tqdm (MPL-2.0 AND MIT, so MIT is
          available as well).

    A pattern over the raw bullet matches `certifi (MPL-2.0)` and matches nothing for
    tqdm, so the release gate's allow-list for tqdm would look like a condition §2.3
    never recorded. A path may wrap too, which is why the paths are not read from the
    folded text.
    """

    opening: str
    package: str | None
    version: str | None
    claims: tuple[PathClaim, ...]
    text: str
    folded: str


# ---------------------------------------------------------------------------
# The export, read.
# ---------------------------------------------------------------------------


def read_export_rows(export_text: str) -> list[RequirementRow]:
    """Parse `uv export --frozen --no-dev` output into requirement rows.

    The export's own shape matters. A requirement is `name==version`, optionally
    followed by ` ; marker`, and it ends with a backslash because its hashes travel
    on continuation lines that are themselves backslash-terminated:

        cohere==7.2.0 ; sys_platform != 'emscripten' \\
            --hash=sha256:… \\
            # via pydantic-ai-slim

    A parser that required the line to end at the version read 15 rows out of 171 and
    every figure below would have been wrong in the same direction; a parser that
    treated a `--hash=sha256:…` line as a requirement would count 606.
    """
    rows: list[RequirementRow] = []
    for line in export_text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        if line.startswith(("-e ", " ", "\t")):
            continue
        requirement, _, marker = line.partition(" ; ")
        requirement = requirement.strip().rstrip("\\").strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)$", requirement)
        if match is None:
            continue
        rows.append(
            RequirementRow(
                name=match.group(1),
                version=match.group(2),
                marker=marker.strip().rstrip("\\").strip() or None,
            )
        )
    if not rows:
        raise RuntimeError(
            "the export named no requirement rows -- the read found nothing in text uv "
            "produced, so every closure figure below would be vacuous"
        )
    return rows


def export_requirements(*, repo_root: Path = REPO_ROOT, timeout: int = 180) -> str:
    """Run `uv export --frozen --no-dev` against this tree's lock."""
    result = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"uv export --frozen --no-dev failed (exit {result.returncode}): "
            f"{result.stderr.strip()[-1200:]}"
        )
    return result.stdout


def marker_holds(marker: str | None, environment: Mapping[str, str]) -> bool:
    """Evaluate one requirement's marker against one platform environment.

    `packaging.markers` is the evaluator the release gate's audit uses, so a marker
    answered here is answered the same way by the gate that decides whether a release
    may ship.
    """
    if marker is None:
        return True
    from packaging.markers import InvalidMarker, Marker

    try:
        return Marker(marker).evaluate(dict(environment))
    except InvalidMarker as error:
        raise RuntimeError(f"the lock carries an unparseable marker {marker!r}: {error}") from error


def read_closure(export_text: str) -> ClosureRead:
    """The closure, split by platform, from the export's own markers."""
    rows = read_export_rows(export_text)
    distinct: dict[str, RequirementRow] = {}
    for row in rows:
        distinct[row.key] = row
    read = ClosureRead(rows=rows, distinct_rows=sorted(distinct.values(), key=lambda row: row.key))

    seen_on_any: set[str] = set()
    for platform, environment in PLATFORM_ENVIRONMENTS.items():
        kept = [row for row in read.distinct_rows if marker_holds(row.marker, environment)]
        read.per_platform[platform] = kept
        seen_on_any.update(row.key for row in kept)
    read.platform_union = [row for row in read.distinct_rows if row.key in seen_on_any]
    read.on_no_platform = [row for row in read.distinct_rows if row.key not in seen_on_any]
    return read


def closure_count_problems(read: ClosureRead, recorded: Mapping[str, int]) -> list[str]:
    """§2.2's five figures against the figures the lock's own markers produce.

    Each figure is looked up by name, so a §2.2 that stops printing one is a failure
    rather than a quietly smaller comparison. The union is compared against the union
    of the three platform sets -- not the export's line count -- because that is the
    number §2.2 says it is.
    """
    computed = {
        "total": len(read.rows),
        "linux": len(read.per_platform["linux"]),
        "macos": len(read.per_platform["macos"]),
        "windows": len(read.per_platform["windows"]),
        "union": len(read.platform_union),
    }
    problems: list[str] = []
    for figure, value in computed.items():
        if figure not in recorded:
            problems.append(f"§2.2 prints no {figure} closure figure to compare with")
        elif recorded[figure] != value:
            problems.append(
                f"§2.2 states {recorded[figure]} for {figure}; the lock's markers give {value}"
            )
    if len(read.rows) != len(read.distinct_rows):
        problems.append(
            f"the export names {len(read.rows)} requirement lines but only "
            f"{len(read.distinct_rows)} distinct name==version pairs, so §2.2's total "
            "counts a package more than once"
        )
    if read.on_no_platform and recorded.get("union") == recorded.get("total"):
        problems.append(
            "§2.2 states a union equal to its total while the lock pins a distribution "
            "no supported platform installs; one of those statements is out of date"
        )
    return problems


def uninstalled_rows(read: ClosureRead, installed: Mapping[str, str]) -> list[RequirementRow]:
    """The pinned rows this environment cannot answer from an installed distribution."""
    return [row for row in read.distinct_rows if canonical(row.name) not in installed]


def running_platform() -> str:
    """Which of §2.2's three platform environments this run is in."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def answerability(
    read: ClosureRead,
    installed: Mapping[str, str],
    platform: str | None = None,
) -> tuple[list[RequirementRow], list[RequirementRow]]:
    """Split the pins this run cannot label into the expected and the unexpected.

    ``foreign`` is the set §2.2 itself explains: the packages whose marker is false on
    the platform running this, which have no distribution here and no label to give.
    ``broken`` is the rest -- a pin whose marker is *true* here and which nothing
    installed answers. That is not a fact about licences, it is a fact about the
    environment, and conflating the two is how a damaged venv (a `dist-info` with no
    METADATA reports no version, so it answers nothing) reads as a record that went
    stale. Keeping them apart means a broken environment produces one clear message
    naming the packages, and the census arithmetic stays honest about what it counted.
    """
    here = platform or running_platform()
    environment = PLATFORM_ENVIRONMENTS[here]
    foreign: list[RequirementRow] = []
    broken: list[RequirementRow] = []
    for row in read.distinct_rows:
        if canonical(row.name) in installed:
            continue
        if marker_holds(row.marker, environment):
            broken.append(row)
        else:
            foreign.append(row)
    return foreign, broken


# ---------------------------------------------------------------------------
# The release gate's own labelling, extracted rather than copied.
# ---------------------------------------------------------------------------


def release_audit_namespace() -> dict[str, Any]:
    """The release licence audit's namespace, taken out of the workflow text.

    The workflow carries two Python heredocs and only one of them is the licence
    audit: running the other dies on the absence of a build ("expected exactly one
    sdist and one wheel"), which is a failure about a build that never happened rather
    than about a licence. The audit is selected by the function it defines.
    """
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    blocks = re.findall(r"<<'PY'\n(.*?)\n {10}PY\n", text, re.S)
    audits = [block for block in blocks if "def label_for" in block]
    if len(audits) != 1:
        raise RuntimeError(
            f"{len(audits)} heredocs in {RELEASE_WORKFLOW.relative_to(REPO_ROOT)} define "
            "label_for; the licence audit is expected to be exactly one"
        )
    body = audits[0]
    indents = [len(line) - len(line.lstrip()) for line in body.splitlines() if line.strip()]
    if not indents:
        raise RuntimeError("the release licence audit heredoc is empty")
    base = min(indents)
    dedented = "\n".join(line[base:] if line.strip() else "" for line in body.splitlines())
    head = dedented.split("installed = {}")[0]
    namespace: dict[str, Any] = {}
    exec(compile(head, "release.yml licence audit", "exec"), namespace)
    if not callable(namespace.get("label_for")):
        raise RuntimeError("the extracted audit text defines no callable label_for")
    return namespace


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", str(name)).lower()


def label_installed(rows: Sequence[RequirementRow]) -> dict[str, tuple[str, str]]:
    """Label each *installed* pinned row with the release gate's own labelling.

    Returns `canonical name -> (label, source)`; `source` is the field or file the
    label came from, which is what makes a disagreeing label diagnosable instead of
    merely wrong. A row with nothing installed for it is absent from the result, which
    is how the foreign set is found.
    """
    label_for = release_audit_namespace()["label_for"]
    by_name: dict[str, Any] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if name:
            by_name.setdefault(canonical(name), dist)
    labelled: dict[str, tuple[str, str]] = {}
    for row in rows:
        dist = by_name.get(canonical(row.name))
        if dist is None:
            continue
        if dist.version != row.version:
            # A distribution installed at a different version is not evidence about
            # this pin: the file it holds may be a different file.
            continue
        label, source = label_for(dist)
        labelled[canonical(row.name)] = (str(label), str(source))
    return labelled


def installed_versions(rows: Sequence[RequirementRow]) -> dict[str, str]:
    """`canonical name -> installed version`, for the pinned names only.

    A distribution whose metadata reports no version is not usable evidence and is
    left out of the map, which puts it in `uninstalled_rows` rather than silently
    pairing it with a pin it cannot vouch for.
    """
    wanted = {canonical(row.name) for row in rows}
    installed: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        key = canonical(name)
        if key not in wanted:
            continue
        version = dist.version
        if version is None:
            continue
        installed[key] = str(version)
    return installed


def closure_answerability_problems(broken: Sequence[RequirementRow], platform: str) -> list[str]:
    """The environment's own failure, stated as one instead of scattered as many.

    A pin whose marker is true on this platform and which nothing installed answers is
    not a fact about licences: it is a broken environment. Measured on this machine,
    the checkout's own `.venv` holds `numpy-2.5.4.dist-info` and `lxml-6.1.3.dist-info`
    directories with no METADATA, no RECORD and no version -- importable, and
    unanswerable. Left unnamed, each of those would arrive as a census disagreement,
    which is a red that blames NOTICE for a damaged venv. Reported here, a witness can
    say what it actually could not measure.
    """
    if not broken:
        return []
    return [
        f"{len(broken)} package(s) the lock pins for {platform} have no readable "
        f"installed distribution here: {', '.join(sorted(row.name for row in broken))}. "
        "This is the environment, not the record: the licence census cannot be measured "
        "in it."
    ]


def census_problems(
    recorded: Mapping[str, int],
    labels: Mapping[str, tuple[str, str]],
    foreign: Sequence[RequirementRow],
    broken: Sequence[RequirementRow] = (),
) -> list[str]:
    """§2.2's census rows against the labels the installed closure carries.

    Partial in an honest way, and the partiality is what the arithmetic has to account
    for. Two kinds of pin contribute no label here: the platform-foreign ones -- the
    ones §2.2 itself explains -- and the ones this environment cannot answer at all. So
    the total closes as

        sum(recorded) == (labels answered here) + foreign + unanswerable

    The per-label checks are safe either way (an unanswered pin contributes nothing, so
    it cannot make a row look too small), and they run regardless. The **total** is only
    evaluated when nothing is unanswerable: closing it against a number that includes a
    damaged installation would be arithmetic over an environment, not over the record,
    and a red that blames NOTICE for a broken venv is exactly the failure this split
    exists to prevent. When something is unanswerable the total is reported as not run.

    A row too small for what is installed reddens it, and a label §2.2 names no row for
    reddens it -- neither needs a network. A row too *large* passes on its own and is
    caught by the total, which is why the total is checked at all: it is the arm that
    notices a dependency leaving the closure while §2.2 keeps its row.
    """
    computed: dict[str, int] = {}
    for label, _source in labels.values():
        if label == "UNRESOLVED":
            continue
        computed[label] = computed.get(label, 0) + 1

    problems: list[str] = []
    for label, count in computed.items():
        if label not in recorded:
            problems.append(
                f"{count} installed distribution(s) carry {label}, which §2.2 names no row for"
            )
        elif recorded[label] < count:
            problems.append(
                f"§2.2 records {recorded[label]} {label}; {count} installed distributions carry it"
            )

    answered = sum(count for label, count in computed.items() if label in recorded)
    recorded_total = sum(recorded.values())
    if broken:
        problems.append(
            f"§2.2's census total ({recorded_total}) could not be closed here: "
            f"{len(broken)} package(s) §2.2 counts have nothing readable installed for "
            "this platform. The per-row checks above ran; the total did not."
        )
    elif recorded_total - answered != len(foreign):
        problems.append(
            f"§2.2's census rows add to {recorded_total}; {answered} are answered by installed "
            f"distributions here and {len(foreign)} package(s) install on no platform this one "
            f"supports ({', '.join(sorted(row.name for row in foreign)[:8])}), so the record no "
            "longer accounts for its own total"
        )
    unresolved = [name for name, (label, _source) in labels.items() if label == "UNRESOLVED"]
    if unresolved:
        problems.append(
            f"{len(unresolved)} installed pinned package(s) carry no recognisable licence "
            f"at all: {', '.join(sorted(unresolved)[:8])} -- §2.2 states every one of them "
            "resolved to a licence read out of the installed distribution"
        )
    return problems


def published_census_problems(
    recorded: Mapping[str, int],
    published_labels: Mapping[str, str],
) -> list[str]:
    """§2.2's census against labels read from the published record of every pin.

    Kept apart from `census_problems` because it answers a different question: the
    installed read says what is on *this* machine, and this says what the published
    record states about every pin, including the platform-foreign ones. It needs the
    network, which is why it is exercised on fixtures here and run for real by the
    release gate rather than by the shards.
    """
    computed: dict[str, int] = {}
    for label in published_labels.values():
        if label == "UNRESOLVED":
            continue
        computed[label] = computed.get(label, 0) + 1
    problems: list[str] = []
    for label, count in recorded.items():
        if computed.get(label, 0) != count:
            problems.append(
                f"§2.2 records {count} {label}; {computed.get(label, 0)} published records carry it"
            )
    for label, count in computed.items():
        if label not in recorded:
            problems.append(f"{count} published records carry {label}, which §2.2 names no row for")
    return problems


# ---------------------------------------------------------------------------
# §2.3's bundled-licence entries, against the installed files.
# ---------------------------------------------------------------------------


def bundled_entries(notice_text: str) -> list[BundledEntry]:
    """§2.3's entries, each with its version and the paths *with their claims*.

    A bullet's body runs to the next bullet, because the paths wrap across lines. Each
    path's claim is the prose between it and the previous path (or the start of the
    bullet), reduced to the vocabulary's licence words: §2.3 says "an LGPL notice for
    the bundled adodbapi module (`…/adodbapi/license.txt`)" and "the Scintilla licence
    for the bundled Scintilla sources (`…/Scintilla/License.txt`)", and pairing the
    claim with the path in document order is what stops one file being credited with
    the other file's clause.
    """
    section = _subsection(notice_text, "2.3")
    starts = list(_BUNDLED_BULLET.finditer(section))
    if not starts:
        raise RuntimeError("§2.3 names no entry -- the read found nothing")
    entries: list[BundledEntry] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        body = section[match.start() : end]
        # `_BUNDLED_BULLET` captures the text after `  * `, but `body` is sliced from
        # `match.start()`, which is the start of the whole bullet including the marker.
        # The version is read from the bullet's first line with the marker removed, or
        # every entry reports "names no package version to match".
        first_line = body.split("\n", 1)[0].lstrip().removeprefix("* ").strip()
        version = _LEADING_PACKAGE_VERSION.match(first_line)
        claims: list[PathClaim] = []
        positions = list(_DIST_INFO_PATH.finditer(body))
        previous = 0
        for path_match in positions:
            window = body[previous : path_match.start()]
            # A bullet that names exactly one file claims everything else it says
            # about that file: numpy's entry names the path first and states the
            # clauses afterwards -- "carries the GCC Runtime Library Exception 3.1
            # for the OpenBLAS build statically linked into numpy.libs, stated as
            # \"GPL-3.0-or-later WITH GCC-exception-3.1\"" -- so a claim window that
            # stopped at the path would check nothing about that file and pass it
            # vacuously.
            #
            # A bullet naming two files (pywin32) is the reason the window is not
            # simply extended for everyone: there the prose *between* the paths names
            # the first one ("…an LGPL notice for the bundled adodbapi module
            # (`…/adodbapi/license.txt`) and the Scintilla licence for the bundled
            # Scintilla sources (`…/Scintilla/License.txt`)"), and extending the last
            # window backwards would credit the Scintilla licence with the LGPL
            # clause. Document order is what keeps each file credited with its own
            # claim; the trailing text of a multi-file bullet -- "beside the
            # PSF-licensed pywin32 code itself", which is about the package's own
            # code rather than either named file -- is deliberately not attached to
            # either path.
            if len(positions) == 1:
                window += body[path_match.end() :]
            claims.append(PathClaim(path=path_match.group(1), claims=_claim_words(window)))
            previous = path_match.end()
        entries.append(
            BundledEntry(
                opening=match.group(1),
                package=version.group(1) if version else None,
                version=version.group(2) if version else None,
                claims=tuple(claims),
                text=body,
                folded=" ".join(part.strip() for part in body.splitlines() if part.strip()),
            )
        )
    return entries


def _claim_words(text: str) -> tuple[str, ...]:
    """The licence vocabulary words a piece of §2.3 prose states."""
    lowered = text.lower()
    found: list[str] = []
    for phrase in _CLAIM_VOCABULARY:
        if phrase in lowered and phrase not in found:
            found.append(phrase)
    # `gpl` is a substring of `lgpl`: an entry that says only LGPL must not be read as
    # also claiming a plain GPL in the same file.
    if "lgpl" in found and "gpl" in found and "gnu general public" not in lowered:
        found.remove("gpl")
    return tuple(found)


def dist_info_is_readable(dist_info_dir: Path) -> bool:
    """Whether an installed `dist-info` directory is usable as evidence at all.

    A `dist-info` with no `METADATA` is a damaged installation, not an absent package:
    measured on this machine the checkout's own `.venv` holds
    `numpy-2.5.4.dist-info` and `lxml-6.1.3.dist-info` containing nothing but an empty
    `licenses/` tree, and `importlib.metadata` reports no version for either. Such a
    directory proves nothing in either direction -- it cannot confirm that §2.3's path
    is right, and it must not be used to claim §2.3's path is wrong. Separating "not
    installed" from "installed and unreadable" is what keeps a broken venv from
    producing a red that reads as a licence finding.
    """
    return (dist_info_dir / "METADATA").is_file()


def bundled_entry_problems(
    entries: Sequence[BundledEntry],
    site_packages: Path,
) -> tuple[list[str], list[str]]:
    """§2.3's licence-file claims against the files the installed distributions hold.

    Returns `(problems, unanswerable)`. Three states are distinguished:

      * the file is there and does not state the clause §2.3 credits it with -- a
        finding about NOTICE, and the one a file-exists-only check would miss, because
        §2.3 does not claim "a licence file exists", it claims which licence that file
        states;
      * the distribution is not installed at all -- a finding about NOTICE when §2.3
        names a path inside a distribution this closure does not hold;
      * the distribution is installed but its `dist-info` cannot be read -- **not** a
      finding about NOTICE, and reported in `unanswerable` so a witness can say the arm
      did not run rather than saying it passed or that the record is wrong.
    """
    problems: list[str] = []
    unanswerable: list[str] = []
    for entry in entries:
        for claim in entry.claims:
            dist_info, _, _remainder = claim.path.partition("/")
            dist_dir = site_packages / dist_info
            if not dist_dir.is_dir():
                problems.append(
                    f"§2.3 names {claim.path}, and no distribution named "
                    f"{dist_info} is installed here"
                )
                continue
            if not dist_info_is_readable(dist_dir):
                unanswerable.append(claim.path)
                continue
            path = site_packages / claim.path
            if not path.is_file():
                problems.append(
                    f"§2.3 names {claim.path}, which is not a file the installed {dist_info} holds"
                )
                continue
            if not claim.claims:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                problems.append(f"§2.3's {claim.path} could not be read: {error}")
                continue
            missing: list[str] = []
            for phrase in claim.claims:
                alternatives = _CLAIM_VOCABULARY[phrase]
                if not any(alternative.lower() in text.lower() for alternative in alternatives):
                    missing.append(phrase)
            if missing:
                problems.append(
                    f"§2.3 credits {claim.path} with {', '.join(missing)}; the installed "
                    f"{dist_info} holds that file and it states none of them"
                )
    return problems, unanswerable


def installed_version_problems(
    entries: Sequence[BundledEntry],
    installed: Mapping[str, str],
) -> list[str]:
    """§2.3's stated versions against the versions this tree resolves.

    A licence file is evidence only about the artefact it belongs to. If §2.3 describes
    `pywin32 312` and this tree resolves `pywin32 313`, the path §2.3 names may hold a
    different file with different contents, and the section has to be re-measured.

    Only a version §2.3 actually states is checked. Its first entry names certifi and
    tqdm by name and gives no version at all -- which is a legitimate thing for a
    record to do, and demanding a version there would turn a correct section into a
    failure for a reason unrelated to any licence.
    """
    problems: list[str] = []
    for entry in entries:
        if entry.package is None or entry.version is None:
            continue
        key = canonical(entry.package)
        if key not in installed:
            continue  # not installable here: the file arm already reports that
        if installed[key] != entry.version:
            problems.append(
                f"§2.3 describes {entry.package} {entry.version}; "
                f"this tree resolves {installed[key]}"
            )
    return problems


def package_terms_problems(
    entries: Sequence[BundledEntry],
    labels: Mapping[str, tuple[str, str]],
    pinned: Mapping[str, str],
) -> list[str]:
    """§2.3's `package (LICENCE)` claims against the labels the closure carries.

    §2.3's first entry makes its claim in exactly this shape -- `certifi (MPL-2.0)` and
    `tqdm (MPL-2.0 AND MIT, so MIT is available as well)` -- and it gives no version,
    so the version arm cannot check it. What *is* checkable is the licence: the label
    the installed distribution carries is the artefact's own statement of its terms,
    and an installed label that names none of the licences §2.3 credits that package
    with is the record disagreeing with the artefact. A package §2.3 names that this
    closure does not pin at all is the other failure, and it says so.
    """
    problems: list[str] = []
    for entry in entries:
        for match in _PACKAGE_TERMS.finditer(entry.folded):
            package = canonical(match.group(1))
            claimed = set(_LICENCE_TOKEN.findall(match.group(2)))
            if not claimed:
                continue
            if package not in pinned:
                problems.append(
                    f"§2.3 names {package} as carrying {', '.join(sorted(claimed))}, and this "
                    "closure pins no such package"
                )
                continue
            entry_label = labels.get(package)
            if entry_label is None:
                continue  # not installed on this platform: the file arm reports that
            label = entry_label[0]
            if not any(token.lower() in label.lower() for token in claimed):
                problems.append(
                    f"§2.3 credits {package} with {', '.join(sorted(claimed))}; the installed "
                    f"distribution's own licence metadata reads {label!r} (from {entry_label[1]})"
                )
    return problems


def conditional_crosscheck_problems(
    entries: Sequence[BundledEntry],
    labels: Mapping[str, tuple[str, str]],
) -> list[str]:
    """§2.3's conditional-licence packages against the release gate's own allow-list.

    Two artefacts, neither of which is NOTICE: the gate's `CONDITIONAL` map comes out
    of the workflow text, and the labels come out of installed metadata. §2.3 names the
    packages it treats as carrying a condition; the gate decides which packages may
    actually ship under one. If they disagree, either the release ships something §2.3
    never recorded or §2.3 records a condition the gate would refuse.
    """
    namespace = release_audit_namespace()
    conditional = namespace.get("CONDITIONAL") or {}
    # §2.3's packages are taken from the shape it writes them in -- `certifi
    # (MPL-2.0)`, `tqdm (MPL-2.0 AND MIT, so MIT is available as well)` -- and not
    # from every word in the bullet. A scan over the prose produced `and`, `is`, `so`
    # and `mpl-2.0` as package names, and each one then looked like a §2.3 entry the
    # release gate refused to allow.
    named: dict[str, set[str]] = {}
    for entry in entries:
        for match in _PACKAGE_TERMS.finditer(entry.folded):
            package = match.group(1)
            licences = set(_LICENCE_TOKEN.findall(match.group(2)))
            if not licences:
                continue
            named.setdefault(canonical(package), set()).update(licences)

    allowed_by_package: dict[str, set[str]] = {}
    for licence, allowed in conditional.items():
        for package in allowed:
            allowed_by_package.setdefault(canonical(package), set()).add(licence)

    problems: list[str] = []
    for licence, allowed in conditional.items():
        for package in sorted(allowed):
            if canonical(package) not in named:
                problems.append(
                    f"the release gate allows {package} under {licence}, and §2.3 names no "
                    "conditional entry for it"
                )
    for package, licences in sorted(named.items()):
        for licence in sorted(licences):
            if licence not in allowed_by_package.get(package, set()):
                problems.append(
                    f"§2.3 names {package} as carrying {licence}, which the release gate's "
                    "CONDITIONAL map does not allow it under"
                )
    carried = {
        licence
        for _name, (label, _source) in labels.items()
        for licence in conditional
        if licence in label
    }
    for licence in sorted(carried - set(conditional)):
        problems.append(
            f"an installed distribution carries {licence}, which the release gate records no "
            "conditional allowance for -- §2.3's list and the gate's map disagree about the closure"
        )
    return problems


def _conditional_names(conditional: Mapping[str, Iterable[str]]) -> list[str]:
    names: list[str] = []
    for allowed in conditional.values():
        names.extend(allowed)
    return names


# ---------------------------------------------------------------------------
# NOTICE read.
# ---------------------------------------------------------------------------


def read_notice(notice_path: Path = NOTICE_PATH) -> str:
    return notice_path.read_text(encoding="utf-8")


_SECTION_HEADING: Final[re.Pattern[str]] = re.compile(r"^\d+(\.\d+)*\.?  \S")


def _subsection(notice_text: str, heading: str) -> str:
    lines = notice_text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{heading}  ")), -1)
    if start < 0:
        raise RuntimeError(f"NOTICE has no subsection {heading}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _SECTION_HEADING.match(lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def closure_counts(notice_text: str) -> dict[str, int]:
    """§2.2's five closure figures, as the section prints them."""
    section = " ".join(_subsection(notice_text, "2.2").split("\n"))
    wanted = (
        ("total", r"resolves (\d+) requirement lines"),
        ("linux", r"(\d+) on Linux"),
        ("macos", r"(\d+) on macOS"),
        ("windows", r"(\d+) on Windows"),
        ("union", r"union is (\d+)"),
    )
    counts: dict[str, int] = {}
    missing: list[str] = []
    for figure, pattern in wanted:
        match = re.search(pattern, section)
        if match is None:
            missing.append(figure)
        else:
            counts[figure] = int(match.group(1))
    if missing:
        raise RuntimeError(f"§2.2 prints no closure figure for: {', '.join(missing)}")
    return counts


def census_rows(notice_text: str) -> dict[str, int]:
    """§2.2's licence census: label -> count."""
    section = _subsection(notice_text, "2.2")
    rows: dict[str, int] = {}
    for match in _CENSUS_ROW.finditer(section):
        label = match.group(2).strip()
        if not label or label.lower().startswith(("total", "the ")):
            continue
        rows[label] = int(match.group(1))
    if not rows:
        raise RuntimeError("§2.2 prints no licence census row -- the read found nothing")
    return rows


_WORD_COUNTS: Final[dict[str, int]] = {
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def census_row_count_claim(notice_text: str) -> int | None:
    """How many distinct licence results §2.2 claims its census prints."""
    section = " ".join(_subsection(notice_text, "2.2").split("\n"))
    match = re.search(r"the (\w+) distinct results were", section)
    if match is None:
        return None
    return _WORD_COUNTS.get(match.group(1).lower())


def census_row_count_problems(recorded: Mapping[str, int], claimed: int | None) -> list[str]:
    """§2.2's own claim about its row count, against the rows it prints."""
    if claimed is None:
        return ["§2.2 states no count of distinct licence results, so its row count is unchecked"]
    if claimed != len(recorded):
        return [
            f"§2.2 states {claimed} distinct licence results and prints {len(recorded)} census "
            "rows; one of the two is out of date"
        ]
    return []


# ---------------------------------------------------------------------------
# The site-packages this run is in.
# ---------------------------------------------------------------------------


def site_packages_of() -> Path:
    """The site-packages directory of the environment running this.

    Taken from an installed distribution rather than guessed from `sys.prefix`: the
    only thing that knows where a `dist-info` actually sits is the distribution that
    owns it, and a test may run in a virtualenv, in the checkout's own `.venv`, or in
    a runner's environment.
    """
    for dist in importlib.metadata.distributions():
        candidate = getattr(dist, "_path", None)
        if candidate is None:
            continue
        parent = Path(str(candidate)).parent
        if parent.is_dir():
            return parent
    raise RuntimeError(
        "no installed distribution reported a path, so no site-packages directory can be found"
    )


def main(argv: Sequence[str] = ()) -> int:
    """Print the closure figures, the census comparison and the §2.3 file check."""
    del argv
    notice_text = read_notice()
    read = read_closure(export_requirements())
    counts = closure_counts(notice_text)
    print(
        "closure: "
        + f"{len(read.rows)} rows, "
        + ", ".join(f"{platform} {len(rows)}" for platform, rows in read.per_platform.items())
        + f", union {len(read.platform_union)}, on no platform {len(read.on_no_platform)}"
    )
    for problem in closure_count_problems(read, counts):
        print(f"  CLOSURE {problem}")

    labels = label_installed(read.distinct_rows)
    installed = installed_versions(read.distinct_rows)
    foreign, broken = answerability(read, installed)
    census = census_rows(notice_text)
    print(
        f"census rows: {len(census)}; labels read here: {len(labels)}; foreign here: {len(foreign)}"
    )
    for problem in closure_answerability_problems(broken, running_platform()):
        print(f"  ENVIRONMENT {problem}")
    for problem in census_problems(census, labels, foreign, broken):
        print(f"  CENSUS {problem}")
    for problem in census_row_count_problems(census, census_row_count_claim(notice_text)):
        print(f"  CENSUS {problem}")

    entries = bundled_entries(notice_text)
    print(f"§2.3 entries: {len(entries)}")
    site = site_packages_of()
    bundled_problems, unreadable = bundled_entry_problems(entries, site)
    for problem in bundled_problems:
        print(f"  BUNDLED {problem}")
    if unreadable:
        print(
            f"  ENVIRONMENT {len(unreadable)} §2.3 licence path(s) sit in a dist-info that "
            f"cannot be read here ({', '.join(sorted(unreadable))}); that arm did not run"
        )
    for problem in installed_version_problems(entries, installed):
        print(f"  VERSION {problem}")
    pinned = {canonical(row.name): row.version for row in read.distinct_rows}
    for problem in package_terms_problems(entries, labels, pinned):
        print(f"  TERMS {problem}")
    for problem in conditional_crosscheck_problems(entries, labels):
        print(f"  CONDITIONAL {problem}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
